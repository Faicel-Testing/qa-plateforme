"""Standalone agents share the pipeline contracts; no network or browser required."""
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from qa_agents.advisor import evaluate, run as advisor_run
from qa_agents.analysis import analyze_failure
from qa_agents.audit import record
from qa_agents.bridge import Bridge
from qa_agents.bug import investigation_graph, run as bug_run
from qa_agents.quality import classify, run as quality_run
from qa_agents.schemas import InvestigationAction
from test_pipeline import FakeModel, execution, TRIAGE, DIAGNOSIS


def write_execution(directory, data=None):
    data = data or execution("failed")
    (directory / "run-manifest.json").write_text(json.dumps(data["manifest"]), encoding="utf-8")
    for index, result in enumerate(data["results"]):
        (directory / f"{index}-result.json").write_text(json.dumps(result), encoding="utf-8")


class FakeBridge:
    dry_run = True
    execution_env = {"QA_RUN_ID": "run-1"}

    def __init__(self, read="1: const value = 1;", proposal=None):
        self.calls = []
        self.read = read
        self.proposal = proposal or {"status": "preview", "file": "src/pages/Login.ts"}

    def call(self, operation, **payload):
        self.calls.append((operation, payload))
        if operation == "read_source":
            return self.read
        if operation == "repair_proposal":
            return self.proposal
        raise AssertionError("Unexpected tool: " + operation)


CONCLUSION = {"action": "report_analysis", "diagnosis": DIAGNOSIS}
READ = {"action": "read_file", "file_path": "src/pages/Login.ts", "line_start": 1, "line_end": 20}
PROPOSAL = {"action": "propose_fix", "file_path": "src/pages/Login.ts", "old": "const value = 1;", "replacement": "const value = 2;"}


class QualityTests(unittest.TestCase):
    def test_standalone_and_shared_contract_are_identical(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_execution(directory)
            for operation, expected, key in [("triage", TRIAGE, "triage"), ("rca", DIAGNOSIS, "diagnosis")]:
                results, failed = classify(directory, "run-1", FakeModel(expected), operation, dry=True)
                self.assertFalse(failed)
                self.assertEqual(results[0][key], analyze_failure(execution("failed")["results"][0], operation, model=FakeModel(expected)))
                self.assertEqual(results[0]["verification"]["status"], "UNVERIFIED")
            self.assertEqual(len(list(directory.iterdir())), 2)

    def test_wrong_run_never_calls_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_execution(directory)
            model = FakeModel()
            with self.assertRaises(ValueError):
                classify(directory, "other-run", model, "triage", dry=True)
            self.assertEqual(model.calls, 0)

    def test_invalid_response_never_becomes_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_execution(directory)
            results, failed = classify(directory, "run-1", FakeModel({}, {}), "triage", dry=True)
            self.assertTrue(failed)
            self.assertEqual(results[0]["status"], "NOT_EVALUATED")
            self.assertEqual(results[0]["verification"]["status"], "REJECTED")

    def test_budget_preserves_unanalyzed_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            data = execution("failed")
            data["results"].append({**data["results"][0], "uuid": "test-2"})
            data["manifest"]["resultCount"] = 2
            write_execution(directory, data)
            model = FakeModel(TRIAGE)
            results, failed = classify(directory, "run-1", model, "triage", dry=True, max_failures=1)
            self.assertTrue(failed)
            self.assertEqual(model.calls, 1)
            self.assertEqual(results[1]["status"], "NOT_EVALUATED")


class BugTests(unittest.TestCase):
    def invoke(self, bridge, outputs, repair=False, limit=5):
        graph = investigation_graph(bridge, FakeModel(*outputs), limit, repair)
        return graph.invoke({"failure": {**execution("failed")["results"][0]}, "context": "Source inventory",
                             "reads": [], "proposals": [], "iteration": 0}, {"recursion_limit": 2 * limit + 3})

    def test_conclusion_uses_shared_diagnosis_and_cannot_claim_fix(self):
        bridge = FakeBridge()
        result = self.invoke(bridge, [CONCLUSION])
        self.assertEqual(result["analysis"]["diagnosis"], DIAGNOSIS)
        self.assertFalse(result["analysis"]["fix_applied"])
        self.assertEqual(bridge.calls, [])

    def test_analyze_forbids_proposal_before_dispatch(self):
        bridge = FakeBridge()
        with self.assertRaises(ValueError):
            self.invoke(bridge, [PROPOSAL])
        self.assertEqual(bridge.calls, [])

    def test_repair_requires_read_before_proposal(self):
        bridge = FakeBridge()
        with self.assertRaises(ValueError):
            self.invoke(bridge, [PROPOSAL], repair=True)
        self.assertEqual(bridge.calls, [])

    def test_repair_proposes_only_and_still_requires_review(self):
        bridge = FakeBridge()
        result = self.invoke(bridge, [READ, PROPOSAL, CONCLUSION], repair=True)
        self.assertEqual([op for op, _ in bridge.calls], ["read_source", "repair_proposal"])
        self.assertFalse(result["analysis"]["fix_applied"])
        self.assertEqual(len(result["analysis"]["proposals"]), 1)

    def test_read_error_is_not_source_evidence(self):
        bridge = FakeBridge(read="ERROR: Outside source tree")
        with self.assertRaises(ValueError):
            self.invoke(bridge, [READ, PROPOSAL], repair=True)
        self.assertEqual(len(bridge.calls), 1)

    def test_unobserved_replacement_cannot_be_proposed(self):
        bridge = FakeBridge()
        with self.assertRaises(ValueError):
            self.invoke(bridge, [READ, {**PROPOSAL, "old": "unobserved assertion"}], repair=True)
        self.assertEqual(len(bridge.calls), 1)

    def test_final_iteration_only_accepts_conclusion(self):
        bridge = FakeBridge()
        with self.assertRaises(ValueError):
            self.invoke(bridge, [READ], limit=1)
        self.assertEqual(bridge.calls, [])

    def test_invalid_paths_ranges_and_extra_fields_rejected(self):
        for value in ["../outside.ts", "src/pages/../../secret.ts", "C:/secret.ts", "src/fixtures/user.ts"]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                InvestigationAction.model_validate({**READ, "file_path": value})
        for value in [{**READ, "line_end": 0}, {**READ, "line_end": 401}, {**READ, "line_start": True},
                      {**CONCLUSION, "fix_applied": True}, {"action": "apply_fix", **{k: v for k, v in PROPOSAL.items() if k != "action"}}]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                InvestigationAction.model_validate(value)


class AdvisorTests(unittest.TestCase):
    def test_gate_is_same_as_pipeline_and_never_calls_model(self):
        from qa_agents.evidence import gate
        for status in ("passed", "failed", "broken", "skipped"):
            model = FakeModel()
            data = execution(status)
            result = evaluate(data, model=model)
            self.assertEqual(result["test_gate"], gate(data))
            self.assertEqual(model.calls, 0)
            self.assertEqual(result["release_authorization"], "NOT_EVALUATED")

    def test_advice_cannot_override_gate(self):
        advice = {"explanation": "Failure recorded", "next_checks": ["Inspect logs"], "limitations": ["Not a release decision"]}
        result = evaluate(execution("failed"), explain=True, model=FakeModel(advice))
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["test_gate"]["verdict"], "FAIL")
        self.assertEqual(result["advice_status"], "UNVERIFIED")

    def test_model_vote_is_rejected(self):
        model = FakeModel({"verdict": "GO"}, {"verdict": "GO"})
        result = evaluate(execution(), explain=True, model=model)
        self.assertEqual(result["advice_status"], "NOT_EVALUATED")
        self.assertEqual(result["test_gate"]["verdict"], "PASS")
        self.assertEqual(result["exit_code"], 1)

    def test_corrupt_evidence_blocks_advice(self):
        data = execution()
        data["errors"].append("Execution ID mismatch")
        model = FakeModel()
        result = evaluate(data, explain=True, model=model)
        self.assertEqual(model.calls, 0)
        self.assertEqual(result["exit_code"], 1)

    def test_cli_gate_runs_offline_and_does_not_touch_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_execution(directory, execution())
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            with patch("qa_agents.advisor.save") as save, patch.object(Bridge, "call", side_effect=AssertionError("Network forbidden")), redirect_stdout(io.StringIO()):
                code = advisor_run(["gate", "--results-dir", str(directory), "--run-id", "run-1"])
            self.assertEqual(code, 0)
            self.assertEqual(save.call_args.args[1]["test_gate"]["verdict"], "PASS")
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})


class CompatibilityTests(unittest.TestCase):
    def test_all_dry_runs_have_no_model_tool_or_write(self):
        for entry, command in [(quality_run, "full"), (bug_run, "repair"), (advisor_run, "advise")]:
            with patch.object(Bridge, "call", side_effect=AssertionError), redirect_stdout(io.StringIO()):
                self.assertEqual(entry([command, "--dry-run"]), 0)

    def test_gate_cli_rejects_implicit_latest_run(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(SystemExit):
            advisor_run(["gate"])

    def test_audit_has_hashes_and_is_compatible_with_legacy(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "verify.jsonl"
            with patch.dict(os.environ, {"QA_VERIFICATION_FILE": str(target)}):
                result = record("quality", "triage", {"sensitive": "private-data"}, {"run_id": "run-1"})
            text = target.read_text(encoding="utf-8")
            self.assertNotIn("private-data", text)
            self.assertEqual(json.loads(text)["schemaVersion"], 1)
            self.assertEqual(result["status"], "UNVERIFIED")

    def test_bridge_disallows_unrelated_environment_override(self):
        with self.assertRaises(ValueError):
            Bridge(execution_env={"NODE_TLS_REJECT_UNAUTHORIZED": "0"})

    def test_advisor_native_and_legacy_are_explicit(self):
        from qa_agents.__main__ import ADAPTERS, main
        self.assertNotIn("advisor", ADAPTERS)
        self.assertEqual(ADAPTERS["advisor-legacy"], "advisor")
        with patch("qa_agents.__main__.environment"), patch("qa_agents.advisor.run", return_value=0) as native:
            self.assertEqual(main(["advisor", "gate", "--dry-run"]), 0)
            native.assert_called_once_with(["gate", "--dry-run"])


if __name__ == "__main__":
    unittest.main()
