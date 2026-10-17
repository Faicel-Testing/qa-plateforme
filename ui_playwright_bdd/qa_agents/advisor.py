"""Native advisor: deterministic test gate, optional explanation, never a model vote."""
import argparse
import json
from .bridge import Bridge
from .chains import typed_structured
from .evidence import gate, read_execution
from .model import GatewayChatModel
from .prompts import SYSTEM, VERSION
from .reports import now, save
from .schemas import Advice
from .selection import add_selection, selected
from .audit import record as audit


def evaluate(execution, *, explain=False, model=None):
    test_gate = gate(execution)
    report = {"schema_version": 2, "ts": now(), "test_gate": test_gate,
              "summary": f"{test_gate['passed']}/{test_gate['total']} tests passed. Test gate: {test_gate['verdict']}.",
              "release_authorization": "NOT_EVALUATED", "advice_status": "NOT_REQUESTED"}
    if explain and not execution["errors"]:
        prompt = [{"role": "system", "content": SYSTEM + "\nExplique le gate calculé sans le modifier. "
                   "Propose les prochains contrôles. Aucun vote, aucune décision de release."},
                  {"role": "user", "content": json.dumps({"computed_test_gate": test_gate}, ensure_ascii=False)}]
        try:
            report["advice"] = typed_structured(prompt, Advice, model=model or GatewayChatModel(agent="advisor")).model_dump()
            report.update(advice_status="UNVERIFIED", prompt_version=VERSION)
        except Exception as exc:
            report.update(advice_status="NOT_EVALUATED", error=type(exc).__name__)
    elif explain:
        report["advice_status"] = "NOT_EVALUATED"
    report["exit_code"] = 1 if test_gate["verdict"] == "FAIL" or report["advice_status"] == "NOT_EVALUATED" else 0
    return report


def run(args):
    parser = argparse.ArgumentParser(description="Python advisor: test gate and advisory explanation, no release approval")
    parser.add_argument("command", choices=["gate", "advise", "report"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local-only", action="store_true", help="Never call the model")
    add_selection(parser)
    if not args or args == ["help"]:
        parser.print_help()
        return 0
    options = parser.parse_args(args)
    if options.dry_run:
        print("NOT_EVALUATED: advisor plan only; no model, tools or writes")
        return 0
    directory, run_id = selected(options, parser)
    bridge = Bridge("advisor", execution_env={"ALLURE_RESULTS_DIR": str(directory), "QA_RUN_ID": run_id})
    report = evaluate(read_execution(directory, run_id),
                      explain=options.command == "advise" and not options.local_only,
                      model=GatewayChatModel(agent="advisor", transport=bridge.call))
    report.update(run_id=run_id, results_dir=str(directory))
    if report["advice_status"] in {"UNVERIFIED", "NOT_EVALUATED"}:
        audit("advisor", "advise", report.get("advice"), {"run_id": run_id}, accepted=report["advice_status"] == "UNVERIFIED")
    # Keep the evidence directory immutable for approval snapshots.
    save("advisor-python-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report["exit_code"]
