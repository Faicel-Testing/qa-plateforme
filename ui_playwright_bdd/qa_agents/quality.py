"""Complete-source audits and evidence-qualified triage in Python."""
import argparse
import os
from .bridge import Bridge
from .model import GatewayChatModel
from .chains import chat
from .reports import now, save
from .analysis import analyze_failure
from .audit import record as audit
from .prompts import VERSION
from .selection import add_selection, selected, load_failures


def audit_verdicts(prepared, reviews, local_only):
    files, local = prepared["files"], prepared["local"]
    reviewed = {file for review in reviews if review["status"] == "COMPLETE" for file in review["files"]}
    findings = [item for review in reviews for item in review.get("findings", [])]
    rejected = [item for review in reviews for item in review.get("rejectedFindings", [])]
    verdicts = []
    for name, prefix, checks in [("Features Gherkin", "src/features/", ["cucumber"]),
                                  ("Step Definitions", "src/steps/", ["typescript", "cucumber"])]:
        required = [f for f in files if (f["file"].endswith(".feature") if prefix == "src/features/" else not f["file"].endswith(".feature"))
                    or f["file"].startswith(("src/hooks/", "src/core/"))]
        targets = [f for f in files if f["file"].startswith(prefix)]
        complete = bool(targets) and not local_only and not prepared["errors"] and all(f["file"] in reviewed for f in required)
        local_fail = any(local[c]["status"] == "FAIL" for c in checks)
        local_ok = all(local[c]["status"] == "PASS" for c in checks)
        relevant = [f for f in findings if f.get("file") in {r["file"] for r in required}]
        verdict = "INVALID" if local_fail else "NOT_EVALUATED" if not complete or not local_ok or rejected else (
            "INVALID" if any(f["severity"] == "error" for f in relevant) else "WARNING" if relevant else "VALID")
        status = "SKIPPED" if local_only else "INCOMPLETE" if not complete else "NEEDS_REVIEW" if rejected else "COMPLETE"
        reason = f"{len(reviewed)}/{len(files)} complete sources reviewed. Local checks: " + ", ".join(c + "=" + local[c]["status"] for c in checks)
        verdicts.append({"check": name, "verdict": verdict, "analysisStatus": status, "targetFiles": len(targets),
                         "reasoning": reason, "detail": reason, "findings": relevant,
                         "coverage": {"totalFiles": len(required), "reviewedFiles": sum(f["file"] in reviewed for f in required)},
                         "evidence": {"localChecks": local, "reviews": reviews, "errors": prepared["errors"], "omitted": prepared["omitted"],
                                      "files": [{k: v for k, v in f.items() if k != "content"} for f in files]}})
    return verdicts


def verify(bridge, model, local_only=False, dry=False):
    print("Quality: local TypeScript/Cucumber checks and full source inventory", flush=True)
    prepared = bridge.call("audit_prepare", maxChars=int(os.getenv("VERIFY_MAX_PROMPT_CHARS", "24000")))
    reviews = []
    if not local_only:
        for index, batch in enumerate(prepared["batches"], 1):
            print(f"Audit batch {index}/{len(prepared['batches'])}: {len(batch['files'])} complete files", flush=True)
            try:
                raw = chat([{"role": "user", "content": batch["prompt"]}], {"temperature": 0, "rag": False}, model=model)["message"]["content"]
                review = bridge.call("audit_validate", raw=raw, files=batch["files"], local=prepared["local"])
            except Exception as error:
                review = {"status": "UNAVAILABLE", "reason": type(error).__name__}
            reviews.append({**review, "batch": index, "files": [f["file"] for f in batch["files"]]})
            if review["status"] == "UNAVAILABLE":
                break
    verdicts = audit_verdicts(prepared, reviews, local_only)
    verdicts.append(bridge.call("allure_verify"))
    counts = {status: sum(v["verdict"] == status for v in verdicts) for status in ["VALID", "WARNING", "INVALID", "NOT_EVALUATED"]}
    save("verify-report.json", {"schemaVersion": 3, "ts": now(), "mode": "local-only" if local_only else "full", "counts": counts, "verdicts": verdicts}, dry)
    for verdict in verdicts:
        print(verdict["check"], verdict["verdict"], verdict["analysisStatus"], flush=True)
    return verdicts, bool(counts["INVALID"] or (not local_only and counts["NOT_EVALUATED"]))


def classify(directory, run_id, model, operation, dry=False, max_failures=10):
    _, items = load_failures(directory, run_id)
    results = []
    for index, failure in enumerate(items):
        print(operation, failure["name"], flush=True)
        context = {"run_id": run_id, "test_id": failure["uuid"]}
        record = {**context, "name": failure["name"], "prompt_version": VERSION}
        if index >= max_failures:
            results.append({**record, "status": "NOT_EVALUATED", "error": "Analysis budget exhausted"})
            continue
        try:
            result = analyze_failure(failure, operation, model=model)
        except Exception as error:
            verification = audit("quality", operation, None, context, dry=dry, accepted=False)
            results.append({**record, "status": "NOT_EVALUATED", "error": type(error).__name__, "verification": verification})
        else:
            verification = audit("quality", operation, result, context, dry=dry)
            results.append({**record, "status": "HYPOTHESIS", "triage" if operation == "triage" else "diagnosis": result,
                            "verification": verification})
    report = {"schema_version": 2, "ts": now(), "run_id": run_id, "resultsDir": str(directory), "analyses": results}
    save(operation + "-report.json", report, dry, directory)
    if not items:
        print("No recorded failed/broken tests; this is not a release approval.")
    return results, any(r["status"] == "NOT_EVALUATED" for r in results)


def run(args):
    parser = argparse.ArgumentParser(description="Python quality: shared triage/RCA contracts, source verification")
    parser.add_argument("command", choices=["verify", "triage", "rca", "full"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--max-failures", type=int, default=10)
    add_selection(parser)
    if not args or args == ["help"]:
        parser.print_help()
        return 0
    options = parser.parse_args(args)
    command, dry, local_only = options.command, options.dry_run, options.local_only
    if not 1 <= options.max_failures <= 100:
        parser.error("--max-failures must be between 1 and 100")
    if local_only and command != "verify":
        parser.error("--local-only is supported only for quality verify")
    if dry:
        print("NOT_EVALUATED: quality plan only; no model, tools or writes")
        return 0
    directory, run_id = selected(options, parser)
    load_failures(directory, run_id)  # Validate once before any source audit/model call.
    bridge = Bridge("quality", dry, {"ALLURE_RESULTS_DIR": str(directory), "QA_RUN_ID": run_id})
    model = GatewayChatModel(agent="quality", transport=bridge.call)
    operations = ["triage", "rca", "verify"] if command == "full" else [command]
    report = {"schema_version": 2, "ts": now(), "run_id": run_id, "status": "RUNNING"}
    failed = False
    for operation in operations:
        try:
            result, error = verify(bridge, model, local_only, dry) if operation == "verify" else classify(directory, run_id, model, operation, dry, options.max_failures)
        except Exception as error:
            result, error = {"status": "NOT_EVALUATED", "error": type(error).__name__}, True
        report[operation] = result
        failed = failed or error
        if command == "full":
            save("quality-full-report.json", report, dry, directory)
    report["status"] = "INCOMPLETE_OR_FAILED" if failed else "COMPLETE"
    if command == "full":
        save("quality-full-report.json", report, dry, directory)
        save("quality-analysis.json", report, dry, directory)
    return 1 if failed else 0
