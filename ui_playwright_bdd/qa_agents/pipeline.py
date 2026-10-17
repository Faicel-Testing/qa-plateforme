"""Native LangGraph pipeline. Tests/gate are deterministic; AI remains advisory."""
import argparse
import json
from pathlib import Path
import time
from typing import TypedDict
from uuid import uuid4
from langgraph.graph import END, START, StateGraph
from .bridge import ROOT
from .analysis import analyze_failure
from .evidence import gate, read_execution
from .execution import run_tests
from .prompts import VERSION
from .reports import now, save
from .data import command as data_command
import os


class PipelineState(TypedDict, total=False):
    run_id: str
    results_dir: str
    mode: str
    local_only: bool
    max_failures: int
    runner_timeout: int
    runner_error: str | None
    execution: dict
    test_gate: dict
    analyses: list[dict]
    events: list[dict]
    summary: dict
    data_status: dict


def build_graph(*, model=None, runner=run_tests, reader=read_execution, checkpointer=None):
    def event(state, name, started):
        return [*state.get("events", []), {"node": name, "duration_ms": round((time.monotonic() - started) * 1000)}]

    def prepare_data(state):
        started = time.monotonic()
        provider = os.environ.get("TEST_DATA_PROVIDER", "memory")
        if provider == "memory":
            return {"data_status": {"provider": "memory", "status": "SKIPPED"},
                    "events": event(state, "prepare_data", started)}
        if provider != "postgres":
            return {"runner_error": "Invalid TEST_DATA_PROVIDER", "data_status": {"status": "ERROR"}}
        print("[Data] Preparation du run dans PostgreSQL...", flush=True)
        try:
            data_command("prepare", state["run_id"])
            return {"data_status": {"provider": "postgres", "status": "READY"},
                    "events": event(state, "prepare_data", started)}
        except Exception:
            return {"runner_error": "PostgreSQL test data preparation failed; run data:init and data:status",
                    "data_status": {"provider": "postgres", "status": "ERROR"},
                    "events": event(state, "prepare_data", started)}

    def execute(state):
        print("[Pipeline] Execution des tests Playwright/Cucumber...", flush=True)
        started = time.monotonic()
        try:
            error = runner(state["run_id"], state["results_dir"], state["mode"], state.get("runner_timeout", 1800))
        except Exception as exc:
            error = "Runner unavailable: " + type(exc).__name__
        return {"runner_error": error, "events": event(state, "execute", started)}

    def validate(state):
        print("[Pipeline] Validation du manifeste et des resultats...", flush=True)
        started = time.monotonic()
        execution = reader(state["results_dir"], state["run_id"])
        return {"execution": execution, "test_gate": gate(execution, state.get("runner_error")),
                "events": event(state, "validate", started)}

    def triage(state):
        print("[Pipeline] Triage IA des echecs...", flush=True)
        started = time.monotonic()
        analyses = []
        failures = [r for r in state["execution"]["results"] if r["status"] in {"failed", "broken"}]
        for index, failure in enumerate(failures):
            record = {"test_id": failure["uuid"], "name": failure["name"], "prompt_version": VERSION}
            if index >= state.get("max_failures", 10):
                record.update(status="NOT_EVALUATED", reason="Analysis budget exhausted")
            else:
                try:
                    value = analyze_failure(failure, "triage", model=model)
                    record.update(status="HYPOTHESIS", triage=value)
                except Exception as exc:
                    record.update(status="NOT_EVALUATED", reason=type(exc).__name__)
            analyses.append(record)
        return {"analyses": analyses, "events": event(state, "triage", started)}

    def diagnose(state):
        print("[Pipeline] Diagnostic IA des echecs...", flush=True)
        started = time.monotonic()
        results = {r["uuid"]: r for r in state["execution"]["results"]}
        analyses = []
        for original in state["analyses"]:
            record = dict(original)
            if "triage" in record:
                try:
                    record["diagnosis"] = analyze_failure(results[record["test_id"]], "rca", model=model, triage=record["triage"])
                except Exception as exc:
                    record.update(status="NOT_EVALUATED", reason=type(exc).__name__)
            analyses.append(record)
        return {"analyses": analyses, "events": event(state, "diagnose", started)}

    def report(state):
        print("[Pipeline] Preparation du rapport...", flush=True)
        data_status = dict(state.get("data_status", {"status": "NOT_EVALUATED"}))
        if (data_status.get("provider") == "postgres" and data_status.get("status") == "READY"
                and state.get("runner_error") in {None, "Runner exited unsuccessfully"}):
            try:
                data_command("complete", state["run_id"])
                data_status["finalization"] = "COMPLETE"
            except Exception:
                data_status["finalization"] = "ERROR"
        test_gate = state["test_gate"]
        analyses = state.get("analyses", [])
        failures = test_gate["failed"] + test_gate["broken"]
        analysis_status = ("SKIPPED" if state.get("local_only") else "BLOCKED" if state["execution"]["errors"]
                           else "NOT_REQUIRED" if not failures else
                           "INCOMPLETE" if len(analyses) != failures or any(a["status"] == "NOT_EVALUATED" for a in analyses)
                           else "COMPLETE")
        # Re-reading an old run can explain it, but cannot authorize a new release.
        exit_code = 1 if test_gate["verdict"] == "FAIL" or analysis_status == "INCOMPLETE" else (2 if state["mode"] == "report" else 0)
        if data_status.get("finalization") == "ERROR":
            exit_code = 1
        return {"summary": {"schema_version": 1, "timestamp": now(), "run_id": state["run_id"],
                            "mode": state["mode"], "results_dir": state["results_dir"],
                            "data": data_status,
                            "test_gate": test_gate, "analysis_status": analysis_status,
                            "analyses": analyses, "events": state.get("events", []), "exit_code": exit_code}}

    graph = StateGraph(PipelineState)
    for name, node in [("prepare_data", prepare_data), ("execute", execute), ("validate", validate), ("triage", triage), ("diagnose", diagnose), ("report", report)]:
        graph.add_node(name, node)
    graph.add_conditional_edges(START, lambda s: "validate" if s["mode"] == "report" else "prepare_data", ["validate", "prepare_data"])
    graph.add_conditional_edges("prepare_data", lambda s: "validate" if s.get("runner_error") else "execute", ["validate", "execute"])
    graph.add_edge("execute", "validate")
    graph.add_conditional_edges("validate", lambda s: "triage" if (
        not s.get("local_only") and not s["execution"]["errors"] and
        any(r["status"] in {"failed", "broken"} for r in s["execution"]["results"])) else "report", ["triage", "report"])
    graph.add_conditional_edges("triage", lambda s: "report" if s["mode"] == "quick" else "diagnose", ["report", "diagnose"])
    graph.add_edge("diagnose", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)


def positive(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def run(args):
    parser = argparse.ArgumentParser(description="Native Python/LangGraph QA pipeline; no external publication or source changes")
    parser.add_argument("mode", choices=["quick", "full", "report"])
    parser.add_argument("--dry-run", action="store_true", help="Show graph only; no tests, model calls or writes")
    parser.add_argument("--local-only", action="store_true", help="Calculate the test gate without LLM calls")
    parser.add_argument("--results-dir", type=Path, help="Required for report mode; one existing execution")
    parser.add_argument("--run-id", help="Expected manifest ID, required for report mode")
    parser.add_argument("--max-failures", type=positive, default=10)
    parser.add_argument("--runner-timeout", type=positive, default=1800, help="Seconds")
    options = parser.parse_args(args)
    if options.mode == "report" and (not options.results_dir or not options.run_id):
        parser.error("report requires --results-dir and --run-id")
    if options.mode != "report" and (options.results_dir or options.run_id):
        parser.error("New test runs always receive a unique ID and directory")
    if options.max_failures > 100:
        parser.error("--max-failures must not exceed 100")
    graph = build_graph()
    if options.dry_run:
        print(graph.get_graph().draw_mermaid())
        print("NOT_EVALUATED: no test execution, model call or release approval")
        return 0
    run_id = options.run_id or f"python-{uuid4().hex}"
    directory = options.results_dir.resolve() if options.results_dir else ROOT / "allure-runs" / run_id / "results"
    print(f"[Pipeline] Mode: {options.mode} | Run: {run_id}", flush=True)
    print(f"[Pipeline] Resultats: {directory}", flush=True)
    state = graph.invoke({"run_id": run_id, "results_dir": str(directory), "mode": options.mode,
                          "local_only": options.local_only, "max_failures": options.max_failures,
                          "runner_timeout": options.runner_timeout, "events": [], "analyses": []})
    summary = state["summary"]
    # Reports are separate from imported evidence; IDs from manifests are never used as paths.
    report_dir = ROOT / "logs" / "python-pipeline" / uuid4().hex
    save("summary.json", summary, directory=report_dir)
    print(json.dumps({"run_id": run_id, "test_gate": summary["test_gate"],
                      "analysis_status": summary["analysis_status"], "report": str(report_dir / "summary.json")},
                     ensure_ascii=False, indent=2))
    return summary["exit_code"]
