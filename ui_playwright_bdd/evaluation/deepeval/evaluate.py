"""Local DeepEval runner. Metric failures never become passing scores."""
import argparse
import html
import importlib.metadata
import json
import math
import os
from pathlib import Path
import time

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"
os.environ.pop("CONFIDENT_API_KEY", None)

from deepeval.metrics import (FaithfulnessMetric, AnswerRelevancyMetric,
                              ContextualPrecisionMetric, ContextualRecallMetric)
from deepeval.test_case import LLMTestCase
from judge import FrameworkJudge

METRICS = {"faithfulness": FaithfulnessMetric, "answer_relevancy": AnswerRelevancyMetric,
           "contextual_precision": ContextualPrecisionMetric, "contextual_recall": ContextualRecallMetric}

def validate_samples(data):
    cases = data.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("Expected 1 to 100 evaluation cases")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"] or case["id"] in ids:
            raise ValueError("Cases require unique nonempty IDs")
        ids.add(case["id"])
        if case.get("status") == "ERROR":
            continue
        for key in ("input", "actual_output"):
            if not isinstance(case.get(key), str) or not case[key].strip() or len(case[key]) > 50000:
                raise ValueError("Missing, empty or oversized input/actual_output")
        contexts = case.get("retrieval_context")
        if not isinstance(contexts, list) or not contexts or not all(isinstance(c, str) and c.strip() for c in contexts) or sum(map(len, contexts)) > 100000:
            raise ValueError("Expected nonempty bounded retrieval_context")
    settings = data.get("settings", {})
    names = settings.get("metrics", ["faithfulness", "answer_relevancy"])
    threshold = settings.get("threshold", 0.7)
    if not names or any(name not in METRICS for name in names) or len(set(names)) != len(names):
        raise ValueError("Unknown or duplicate metric")
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Invalid metric threshold")
    if any(name.startswith("contextual_") for name in names):
        if any(c.get("status") != "ERROR" and (not isinstance(c.get("expected_output"), str) or not c["expected_output"].strip()) for c in cases):
            raise ValueError("Contextual metrics require expected_output")
    return names, threshold

def run(data, judge, factories=None):
    names, threshold = validate_samples(data)
    factories = factories or METRICS
    results = []
    for case in data["cases"]:
        row = {"id": case["id"], "input": case.get("input", ""), "metrics": [], "status": "ERROR"}
        started = time.monotonic()
        if case.get("status") == "ERROR":
            row["error"] = "Source collection failed; evaluation not performed"
            # Only allowlisted local diagnostics, never arbitrary provider output.
            diagnostics = {
                "EMBEDDING_UNAVAILABLE": "Ollama embeddings unavailable. Start the configured service, or explicitly use --mode bm25.",
                "EMBEDDING_MODEL_MISSING": "The configured embedding model is missing in Ollama. Install it, or explicitly use --mode bm25.",
                "GENERATION_FAILED": "Answer generation failed; inspect provider configuration and gateway logs.",
                "CORPUS_CHANGED": "Corpus changed during collection; collect a new sample.",
                "RETRIEVAL_FAILED": "Retrieval failed; inspect retrieval configuration and gateway logs.",
            }
            code = case.get("diagnostic", {}).get("code") if isinstance(case.get("diagnostic"), dict) else None
            if code in diagnostics:
                row["error"] = diagnostics[code] + " Evaluation not performed."
        else:
            test_case = LLMTestCase(input=case["input"], actual_output=case["actual_output"],
                                   expected_output=case.get("expected_output"), retrieval_context=case["retrieval_context"])
            for name in names:
                metric_started = time.monotonic()
                try:
                    metric = factories[name](threshold=threshold, model=judge, async_mode=False, include_reason=True)
                    metric.measure(test_case)
                    score = metric.score
                    if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1 or metric.error:
                        raise ValueError("Invalid metric score")
                    row["metrics"].append({"name": name, "score": score, "threshold": threshold,
                                           "status": "PASS" if metric.is_successful() else "FAIL", "reason": metric.reason,
                                           "durationMs": (time.monotonic() - metric_started) * 1000})
                except Exception as error:
                    # Provider responses may contain prompts: persist only the exception class.
                    row["metrics"].append({"name": name, "score": None, "threshold": threshold, "status": "ERROR",
                                           "error": type(error).__name__, "durationMs": (time.monotonic() - metric_started) * 1000})
            states = [m["status"] for m in row["metrics"]]
            row["status"] = "ERROR" if "ERROR" in states else "FAIL" if "FAIL" in states else "PASS"
        row["durationMs"] = (time.monotonic() - started) * 1000
        results.append(row)
    states = [r["status"] for r in results]
    return {"schemaVersion": 1, "framework": "DeepEval", "version": importlib.metadata.version("deepeval"),
            "judge": judge.get_model_name(), "judgeCalls": judge.calls,
            "datasetReviewStatus": data.get("datasetReviewStatus", "DRAFT"),
            "status": "ERROR" if "ERROR" in states else "FAIL" if "FAIL" in states else "PASS",
            "releaseAuthorized": False, "results": results,
            "limitations": "LLM-judge scores are fallible. Draft references and thresholds need human calibration. This report does not validate a release."}

def write_report(report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    escape = lambda value: html.escape(str(value))
    rows = []
    for case in report["results"]:
        details = "<br>".join(escape(f'{m["name"]}: {m["score"]} / seuil {m["threshold"]} — {m["status"]}') +
                              "<br><small>" + escape(m.get("reason") or m.get("error", "")) + "</small>" for m in case["metrics"])
        rows.append(f'<tr><td>{escape(case["id"])}<br>{escape(case["input"])}</td><td>{escape(case["status"])}</td><td>{details or escape(case.get("error", ""))}</td><td>{case["durationMs"]/1000:.2f} s</td></tr>')
    text = f'''<!doctype html><html lang="fr"><meta charset="utf-8"><title>Évaluation DeepEval</title>
<style>body{{font:16px system-ui;background:#101827;color:#edf3ff;margin:32px}}h1{{color:#65d6d0}}table{{border-collapse:collapse;width:100%}}td,th{{padding:14px;border-bottom:1px solid #34445b;text-align:left}}small{{color:#b5c6da}}</style>
<h1>DeepEval — {escape(report["status"])}</h1><p>Version {escape(report["version"])} — Juge : {escape(report["judge"])} — {report["judgeCalls"]} appels logiques</p>
<p>Références : {escape(report["datasetReviewStatus"])}. Les scores ne garantissent pas la vérité métier et n'autorisent aucune release.</p>
<p>Coûts et tokens : exécuter <code>npm run metrics:report</code> ; les appels du juge sont classés « evaluation ».</p>
<table><tr><th>Cas</th><th>Statut</th><th>Métriques</th><th>Durée</th></tr>{''.join(rows)}</table></html>'''
    (directory / "report.html").write_text(text, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        validate_samples(data)
        report = run(data, FrameworkJudge())
        write_report(report, args.output)
        print(json.dumps({"status": report["status"], "cases": len(report["results"]), "judgeCalls": report["judgeCalls"]}))
        return 2 if report["status"] == "ERROR" else 1 if report["status"] == "FAIL" else 0
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "error.json").write_text(json.dumps({"status": "ERROR", "error": type(error).__name__}), encoding="utf-8")
        print("DeepEval failed before completion: " + type(error).__name__)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
