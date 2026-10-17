"""Read one explicit execution; never select or merge historical result directories."""
from pathlib import Path
from .schemas import RunManifest, TestResult


def read_execution(directory, expected_run_id):
    directory = Path(directory)
    errors, results, manifest = [], [], None
    try:
        manifest = RunManifest.model_validate_json((directory / "run-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        errors.append("Missing or invalid execution manifest")
    for file in sorted(directory.glob("*-result.json")):
        try:
            results.append(TestResult.model_validate_json(file.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            errors.append("Invalid Allure result: " + file.name)
    if not expected_run_id or manifest is None or manifest.runId != expected_run_id:
        errors.append("Execution ID mismatch or unspecified")
    if not results:
        errors.append("No test results")
    if len({r.uuid for r in results}) != len(results):
        errors.append("Duplicate Allure UUID")
    if manifest:
        if not manifest.completed or manifest.timedOut or manifest.error:
            errors.append("Execution incomplete")
        if manifest.finishedAt < manifest.startedAt:
            errors.append("Invalid execution interval")
        if manifest.resultCount != len(results):
            errors.append("Result count mismatch")
        if any(r.start < manifest.startedAt or r.stop < r.start or r.stop > manifest.finishedAt for r in results):
            errors.append("Results outside execution interval")
    return {"manifest": manifest.model_dump() if manifest else None,
            "results": [r.model_dump() for r in results], "errors": errors}


def gate(execution, runner_error=None):
    reasons = list(execution["errors"])
    results, manifest = execution["results"], execution["manifest"]
    if runner_error:
        reasons.append(runner_error)
    if not manifest or manifest["exitCode"] != 0:
        reasons.append("Runner did not succeed")
    if any(r["status"] != "passed" for r in results):
        reasons.append("Some tests failed, broke, were skipped or have unknown status")
    counts = {key: sum(r["status"] == key for r in results)
              for key in ("passed", "failed", "broken", "skipped", "unknown")}
    # Same conservative policy as pipeline-runtime.checkRun: every selected test must pass.
    return {"verdict": "FAIL" if reasons else "PASS", "policy": "all-selected-tests-pass-v1",
            "total": len(results), **counts, "reasons": reasons,
            "release_authorization": "NOT_EVALUATED"}
