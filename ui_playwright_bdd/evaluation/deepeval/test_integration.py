import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"
os.environ.pop("CONFIDENT_API_KEY", None)

from deepeval.models import DeepEvalBaseLLM
from pydantic import BaseModel
from evaluate import run, validate_samples, write_report
from judge import FrameworkJudge

class ScriptedJudge(DeepEvalBaseLLM):
    """Deterministic fixture, not an evaluation of model quality."""
    def __init__(self, verdict="yes", broken=False):
        self.verdict = verdict
        self.broken = broken
        self.calls = 0
        super().__init__(model="offline-fixture")

    def load_model(self):
        return self

    def get_model_name(self):
        return "offline-fixture"

    def generate(self, prompt, schema=None):
        self.calls += 1
        if self.broken:
            raise RuntimeError("provider failed SECRET")
        fields = schema.model_fields
        if "verdicts" in fields:
            return schema.model_validate({"verdicts": [{"verdict": self.verdict, "reason": "Fixture judgment"}]})
        if "reason" in fields:
            return schema.model_validate({"reason": "Fixture explanation"})
        field = next(iter(fields))
        return schema.model_validate({field: ["The deleted task is absent."]})

    async def a_generate(self, prompt, schema=None):
        return self.generate(prompt, schema)

def samples():
    return {"datasetReviewStatus": "DRAFT", "cases": [{"id": "delete", "input": "What happens after deletion?",
             "actual_output": "The task is absent.", "expected_output": "The task is absent.",
             "retrieval_context": ["After deletion the task no longer appears in the list."]}]}

class IntegrationTests(unittest.TestCase):
    def test_real_deepeval_metrics_pass_and_fail(self):
        for verdict, expected in [("yes", "PASS"), ("no", "FAIL")]:
            result = run(samples(), ScriptedJudge(verdict))
            self.assertEqual(result["status"], expected)
            self.assertEqual(len(result["results"][0]["metrics"]), 2)
            self.assertFalse(result["releaseAuthorized"])
            self.assertGreater(result["judgeCalls"], 0)

    def test_provider_failure_never_passes_or_exposes_content(self):
        result = run(samples(), ScriptedJudge(broken=True))
        self.assertEqual(result["status"], "ERROR")
        self.assertTrue(all(m["score"] is None for m in result["results"][0]["metrics"]))
        self.assertNotIn("SECRET", json.dumps(result))

    def test_collection_failure_does_not_call_judge(self):
        judge = ScriptedJudge()
        data = {"cases": [{"id": "bad", "status": "ERROR"}]}
        self.assertEqual(run(data, judge)["status"], "ERROR")
        self.assertEqual(judge.calls, 0)

    def test_empty_duplicate_missing_context_and_invalid_threshold_rejected(self):
        for data in [{"cases": []}, {"cases": samples()["cases"] * 2},
                     {"cases": [{"id": "missing", "input": "Q", "actual_output": "A"}]},
                     {**samples(), "settings": {"threshold": float("nan")}},
                     {**samples(), "settings": {"metrics": ["invented"]}}]:
            with self.assertRaises(ValueError):
                validate_samples(data)

    def test_collection_diagnostic_is_allowlisted_and_does_not_call_judge(self):
        judge = ScriptedJudge()
        data = {"cases": [{"id": "bad", "status": "ERROR", "diagnostic": {
            "code": "EMBEDDING_UNAVAILABLE", "message": "SECRET"}}]}
        result = run(data, judge)
        self.assertIn("--mode bm25", result["results"][0]["error"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(judge.calls, 0)

    def test_bridge_schema_and_call_budget(self):
        class Answer(BaseModel):
            reason: str
        with patch.dict(os.environ, {"DEEPEVAL_MAX_JUDGE_CALLS": "1"}), patch("judge.subprocess.run") as child:
            child.return_value = SimpleNamespace(returncode=0, stdout=json.dumps({"output": '{"reason":"ok"}'}))
            model = FrameworkJudge()
            self.assertEqual(model.generate("prompt", Answer).reason, "ok")
            self.assertIn("schema", json.loads(child.call_args.kwargs["input"]))
            with self.assertRaises(RuntimeError):
                model.generate("second prompt", Answer)

    def test_report_escapes_model_content_and_is_local(self):
        result = run(samples(), ScriptedJudge())
        result["results"][0]["input"] = "<script>alert(1)</script>"
        with tempfile.TemporaryDirectory() as directory:
            write_report(result, Path(directory))
            text = (Path(directory) / "report.html").read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;", text)
            self.assertNotIn("<script>alert", text)
            self.assertTrue((Path(directory) / "report.json").exists())

if __name__ == "__main__":
    unittest.main()
