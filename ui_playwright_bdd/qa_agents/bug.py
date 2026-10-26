"""Bounded LangGraph diagnosis with source tools and review-only repair."""
import html
import argparse
import json
import os
import re
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .bridge import Bridge
from .model import GatewayChatModel
from .chains import typed_structured
from .observability import callbacks
from .reports import now, save
from .schemas import InvestigationAction
from .prompts import SYSTEM, VERSION
from .audit import record as audit
from .selection import add_selection, selected, load_failures


class Investigation(TypedDict, total=False):
    failure: dict
    context: str
    reads: list
    iteration: int
    decision: dict
    analysis: dict
    proposals: list
    recorded_api: dict


def investigation_graph(bridge, model, max_iter=5, repair=False):
    if not 1 <= max_iter <= 20:
        raise ValueError("Iteration budget must be between 1 and 20")

    def decide(state):
        iteration = state.get("iteration", 0) + 1
        final = iteration == max_iter
        instruction = ("Lis les sources utiles puis conclus avec report_analysis et le contrat Diagnosis partagé. "
                       "read_file lit au plus 400 lignes. ")
        instruction += ("propose_fix est autorisé après lecture de la cible : proposition soumise à revue, jamais appliquée. "
                        if repair else "propose_fix est interdit en mode analyse. ")
        instruction += ("Les sources préchargées comptent comme lectures. Vérifie leur contenu avant de déclarer "
                        "une configuration manquante. Distingue code actuel et traces du run. "
                        "Un ECONNRESET ne prouve pas une panne globale ; un échec de création du compte "
                        "empêche de conclure sur la validation Todo. Ne demande pas un timeout ou un retry "
                        "déjà visibles dans le code fourni. ")
        instruction += "Les URL peuvent être masquées par la gateway : distingue cible enregistrée et cible non enregistrée. "
        if final:
            instruction += "Budget épuisé : seule report_analysis est autorisée, même si les preuves sont insuffisantes."
        payload = {"failure": state["failure"], "source_inventory": state["context"], "source_reads": state.get("reads", []),
                   "recorded_api": state.get("recorded_api", {"status": "NOT_RECORDED"})}
        decision = typed_structured([{"role": "system", "content": SYSTEM + "\n" + instruction},
                                     {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                                    InvestigationAction, model=model).model_dump()
        allowed = {"read_file", "report_analysis"} | ({"propose_fix"} if repair else set())
        if decision.get("action") not in allowed or (final and decision["action"] != "report_analysis"):
            raise ValueError("Invalid action or iteration budget exhausted without conclusion")
        print(f"Bug turn {iteration}/{max_iter}: {decision['action']}", flush=True)
        return {"iteration": iteration, "decision": decision}

    def tools(state):
        decision = state["decision"]
        if decision["action"] == "read_file":
            content = bridge.call("read_source", args=decision)
            if not isinstance(content, str) or content.startswith("ERROR:"):
                raise ValueError("Source read rejected; no evidence accepted")
            key = decision.get("file_path", "")
            return {"reads": [*state.get("reads", []), [key, content]]}
        if decision["file_path"] not in {entry[0] for entry in state.get("reads", [])}:
            raise ValueError("Read the repair target before proposing a change")
        observed = "\n".join(re.sub(r"(?m)^\d+: ?", "", text) for file, text in state.get("reads", [])
                             if file == decision["file_path"])
        if decision["old"] not in observed:
            raise ValueError("Replacement text was not observed in the source reads")
        proposal = bridge.call("repair_proposal", file=decision["file_path"], old=decision["old"], replacement=decision["replacement"])
        if not bridge.dry_run and (proposal.get("status") != "pending" or not proposal.get("id") or not proposal.get("digest")):
            raise ValueError("Proposal not recorded for review")
        return {"proposals": [*state.get("proposals", []), {"id": proposal.get("id"), "digest": proposal.get("digest"), "file": proposal.get("file")}],
                "reads": [*state.get("reads", []), ["proposal", "REVIEW REQUIRED; fix_applied=false"]]}

    def conclude(state):
        analysis = {"diagnosis": state["decision"]["diagnosis"], "name": state["failure"]["name"],
                    "test_id": state["failure"]["uuid"], "prompt_version": VERSION,
                    "fix_applied": False, "status": "HYPOTHESIS", "proposals": state.get("proposals", [])}
        analysis["source_files_read"] = [file for file, _ in state.get("reads", []) if file != "proposal"]
        analysis["recorded_api"] = state.get("recorded_api", {"status": "NOT_RECORDED"})
        analysis["verification"] = audit("bug", "analyze", analysis,
                                          {"run_id": bridge.execution_env.get("QA_RUN_ID"), "sourceReads": state.get("reads", [])},
                                          dry=bridge.dry_run)
        return {"analysis": analysis}

    graph = StateGraph(Investigation)
    graph.add_node("decide", decide)
    graph.add_node("tools", tools)
    graph.add_node("conclude", conclude)
    graph.add_edge(START, "decide")
    graph.add_conditional_edges("decide", lambda s: "conclude" if s["decision"]["action"] == "report_analysis" else "tools")
    graph.add_edge("tools", "decide")
    graph.add_edge("conclude", END)
    return graph.compile()


def run(args):
    parser = argparse.ArgumentParser(description="Python bug investigation; repair creates review proposals only")
    parser.add_argument("command", choices=["analyze", "repair", "report"])
    parser.add_argument("--max-iter", type=int, default=int(os.getenv("AGENT_MAX_ITER", "5")))
    parser.add_argument("--max-failures", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    add_selection(parser)
    if not args or args == ["help"]:
        parser.print_help()
        return 0
    options = parser.parse_args(args)
    command, limit, dry = options.command, options.max_iter, options.dry_run
    if not 1 <= limit <= 20 or not 1 <= options.max_failures <= 100:
        parser.error("--max-iter must be 1..20; --max-failures must be 1..100")
    if dry:
        print("NOT_EVALUATED: bug plan only; no model, tools or writes")
        return 0
    directory, run_id = selected(options, parser)
    _, items = load_failures(directory, run_id)
    bridge = Bridge("bug", dry, {"ALLURE_RESULTS_DIR": str(directory), "QA_RUN_ID": run_id})
    graph = investigation_graph(bridge, GatewayChatModel(agent="bug", transport=bridge.call), limit, command == "repair")
    analyses = []
    for index, failure in enumerate(items):
        if index >= options.max_failures:
            analyses.append({"name": failure["name"], "test_id": failure["uuid"], "status": "NOT_EVALUATED", "error": "Analysis budget exhausted", "fix_applied": False})
            continue
        print("Bug:", failure["name"], flush=True)
        try:
            bundle = bridge.call("source_bundle", failure=failure)
            state = graph.invoke({"failure": failure, "context": bundle["inventory"], "reads": bundle["reads"],
                                  "recorded_api": bundle["recorded_api"], "iteration": 0, "proposals": []},
                                 {"recursion_limit": 2 * limit + 3, "callbacks": callbacks()})
            analyses.append(state["analysis"])
        except Exception as error:
            analyses.append({"name": failure["name"], "status": "NOT_EVALUATED", "fix_applied": False, "error": type(error).__name__})
    report = {"schema_version": 2, "ts": now(), "run_id": run_id, "resultsDir": str(directory), "analyses": analyses}
    save("bug-analysis.json", report, dry, directory)
    if command == "report" and not dry:
        rows = "".join("<article><h2>" + html.escape(a["name"]) + "</h2><p>" + html.escape(a["status"]) + "</p><pre>" + html.escape(a.get("diagnosis", {}).get("root_cause", a.get("error", ""))) + "</pre></article>" for a in analyses)
        (directory / "bug-report.html").write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Bug analysis</title><h1>Hypothèses à vérifier</h1>' + rows + "</html>", encoding="utf-8")
    if any(a["status"] == "NOT_EVALUATED" for a in analyses):
        return 1
    # A repair command never declares that the application was repaired by the model.
    return 2 if command == "repair" and items else 0
