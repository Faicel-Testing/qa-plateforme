"""Offline regressions: real LangGraph + fake model, no browser/network/credentials."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from qa_agents.chains import typed_structured
from qa_agents.evidence import gate, read_execution
from qa_agents.execution import run_tests
from qa_agents.pipeline import build_graph, run
from qa_agents.schemas import Triage
from qa_agents.model import GatewayChatModel


TRIAGE = {"category": "unknown", "confidence": 0.2, "evidence": ["Timeout recorded"],
          "hypotheses": ["Element unavailable"], "missing_information": ["DOM"], "suggested_action": "Inspect trace"}
DIAGNOSIS = {"status": "INSUFFICIENT_EVIDENCE", "root_cause": "Not established", "evidence": ["Timeout recorded"],
             "missing_information": ["DOM"], "affected_layer": "unknown", "next_check": "Inspect trace", "proposed_fix": ""}


class FakeModel:
    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.calls = 0

    def invoke(self, messages, **kwargs):
        self.calls += 1
        output = next(self.outputs)
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(content=output if isinstance(output, str) else json.dumps(output))


def execution(status="passed"):
    return {"manifest": {"runId": "run-1", "completed": True, "startedAt": 100, "finishedAt": 200,
                         "exitCode": 0 if status == "passed" else 1, "resultCount": 1},
            "results": [{"uuid": "test-1", "name": "Login", "status": status, "start": 110, "stop": 190,
                         "statusDetails": {"message": "Timeout recorded"}}], "errors": []}


class EvidenceTests(unittest.TestCase):
    def read(self, data, expected="run-1"):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            if data["manifest"] is not None:
                (directory / "run-manifest.json").write_text(json.dumps(data["manifest"]), encoding="utf-8")
            for index, result in enumerate(data["results"]):
                (directory / f"{index}-result.json").write_text(json.dumps(result), encoding="utf-8")
            return read_execution(directory, expected)

    def test_valid_pass_and_failed_run(self):
        self.assertEqual(gate(self.read(execution()))["verdict"], "PASS")
        failed = self.read(execution("failed"))
        self.assertEqual(failed["errors"], [])  # A legitimate test failure is still valid evidence.
        self.assertEqual(gate(failed)["verdict"], "FAIL")

    def test_empty_missing_corrupt_and_wrong_execution_fail_closed(self):
        cases = []
        for field, value in [("completed", False), ("resultCount", 7), ("finishedAt", 50), ("timedOut", True)]:
            data = execution()
            data["manifest"][field] = value
            cases.append(data)
        cases.extend([{"manifest": None, "results": [], "errors": []},
                      {**execution(), "results": []}])
        for data in cases:
            with self.subTest(data=data):
                self.assertTrue(self.read(data)["errors"])
                self.assertEqual(gate(self.read(data))["verdict"], "FAIL")
        self.assertTrue(self.read(execution(), "different-run")["errors"])
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "bad-result.json").write_text("{", encoding="utf-8")
            self.assertTrue(read_execution(temporary, "run-1")["errors"])

    def test_old_result_duplicate_uuid_and_invalid_status(self):
        for change in ("old", "duplicate", "status"):
            data = execution()
            if change == "old":
                data["results"][0]["start"] = 1
            elif change == "duplicate":
                data["results"].append(copy.deepcopy(data["results"][0]))
                data["manifest"]["resultCount"] = 2
            else:
                data["results"][0]["status"] = "GO"
            with self.subTest(change=change):
                self.assertTrue(self.read(data)["errors"])

    def test_skipped_broken_unknown_never_pass(self):
        for status in ("skipped", "broken", "unknown"):
            self.assertEqual(gate(self.read(execution(status)))["verdict"], "FAIL")


class StructuredTests(unittest.TestCase):
    def test_real_langchain_model_with_offline_gateway_transport(self):
        requests = []
        def transport(operation, **payload):
            requests.append((operation, payload))
            return {"message": {"content": json.dumps(TRIAGE)}}
        result = typed_structured([{"role": "system", "content": "Instructions"},
                                   {"role": "user", "content": "Recorded failure"}], Triage,
                                  model=GatewayChatModel(transport=transport))
        self.assertEqual(result.category, "unknown")
        self.assertEqual(requests[0][0], "chat")
        self.assertEqual(requests[0][1]["messages"][0]["role"], "system")
        self.assertFalse(requests[0][1]["options"]["rag"])

    def test_invalid_schema_retried_then_validated(self):
        model = FakeModel({**TRIAGE, "confidence": 7}, TRIAGE)
        self.assertEqual(typed_structured([], Triage, model=model).category, "unknown")
        self.assertEqual(model.calls, 2)

    def test_incomplete_json_never_accepted(self):
        model = FakeModel('{"category":"unknown"', "{}")
        with self.assertRaises(ValueError):
            typed_structured([], Triage, model=model)

    def test_extra_fields_invalid_enum_and_boolean_confidence_rejected(self):
        for values in ({"category": "GO"}, {"confidence": True}, {"confidence": -1}, {"release": "GO"}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Triage.model_validate({**TRIAGE, **values})

    def test_provider_failure_not_retried(self):
        model = FakeModel(RuntimeError("provider unavailable"))
        with self.assertRaises(RuntimeError):
            typed_structured([], Triage, model=model)
        self.assertEqual(model.calls, 1)


class GraphTests(unittest.TestCase):
    def invoke(self, data, mode="full", model=None, **state):
        self.runner_calls = []
        def runner(*args):
            self.runner_calls.append(args)
        graph = build_graph(model=model or FakeModel(), runner=runner, reader=lambda *_: copy.deepcopy(data))
        return graph.invoke({"run_id": "run-1", "results_dir": "unused", "mode": mode,
                             "max_failures": 10, "local_only": False, **state})["summary"]

    def test_pass_skips_model_and_never_approves_release(self):
        model = FakeModel()
        report = self.invoke(execution(), model=model)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(model.calls, 0)
        self.assertEqual(len(self.runner_calls), 1)
        self.assertEqual(report["test_gate"]["release_authorization"], "NOT_EVALUATED")

    def test_failure_routes_to_triage_and_diagnosis(self):
        model = FakeModel(TRIAGE, DIAGNOSIS)
        report = self.invoke(execution("failed"), model=model)
        self.assertEqual(model.calls, 2)
        self.assertEqual(report["analysis_status"], "COMPLETE")
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["analyses"][0]["diagnosis"]["status"], "INSUFFICIENT_EVIDENCE")

    def test_quick_only_triages(self):
        model = FakeModel(TRIAGE)
        report = self.invoke(execution("failed"), mode="quick", model=model)
        self.assertEqual(model.calls, 1)
        self.assertNotIn("diagnosis", report["analyses"][0])

    def test_invalid_evidence_blocks_model(self):
        data = execution("failed")
        data["errors"] = ["Old results"]
        model = FakeModel()
        report = self.invoke(data, model=model)
        self.assertEqual(model.calls, 0)
        self.assertEqual(report["analysis_status"], "BLOCKED")
        self.assertEqual(report["exit_code"], 1)

    def test_unavailable_model_does_not_hide_test_failure(self):
        report = self.invoke(execution("failed"), model=FakeModel(RuntimeError("unavailable")))
        self.assertEqual(report["analysis_status"], "INCOMPLETE")
        self.assertEqual(report["test_gate"]["verdict"], "FAIL")

    def test_report_does_not_execute_tests_or_approve_old_run(self):
        report = self.invoke(execution(), mode="report")
        self.assertEqual(self.runner_calls, [])
        self.assertEqual(report["exit_code"], 2)

    def test_budget_and_local_only(self):
        data = execution("failed")
        data["results"].append({**data["results"][0], "uuid": "test-2"})
        report = self.invoke(data, mode="quick", model=FakeModel(TRIAGE), max_failures=1)
        self.assertEqual(report["analysis_status"], "INCOMPLETE")
        report = self.invoke(data, local_only=True)
        self.assertEqual(report["analysis_status"], "SKIPPED")
        self.assertEqual(report["exit_code"], 1)

    def test_runner_exception_is_reported(self):
        def broken(*args):
            raise OSError("spawn failed")
        graph = build_graph(runner=broken, reader=lambda *_: execution())
        report = graph.invoke({"run_id": "run-1", "results_dir": "unused", "mode": "full"})["summary"]
        self.assertEqual(report["exit_code"], 1)

    def test_dry_run_never_invokes_graph_or_writes(self):
        with patch("qa_agents.pipeline.run_tests", side_effect=AssertionError), patch("qa_agents.pipeline.save", side_effect=AssertionError):
            self.assertEqual(run(["quick", "--dry-run"]), 0)


class ExecutionTests(unittest.TestCase):
    def test_timeout_terminates_process_tree(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temporary:
            with patch("qa_agents.execution.environment", return_value={}), patch("qa_agents.execution.subprocess.Popen") as popen, patch("qa_agents.execution.terminate_tree") as terminate:
                popen.return_value.wait.side_effect = subprocess.TimeoutExpired("node", 10)
                self.assertEqual(run_tests("new-run", Path(temporary) / "results", "full", 10), "Runner deadline exceeded")
                terminate.assert_called_once_with(popen.return_value)

    def test_runner_scopes_results_and_disables_external_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "results"
            with patch("qa_agents.execution.environment", return_value={"PLANE_SYNC_RESULTS": "true"}), patch("qa_agents.execution.subprocess.Popen") as popen:
                popen.return_value.wait.return_value = 0
                self.assertIsNone(run_tests("new-run", directory, "quick", 10))
                command = popen.call_args.args[0]
                env = popen.call_args.kwargs["env"]
                self.assertEqual(command[-1], "smoke")
                self.assertEqual(env["QA_RUN_ID"], "new-run")
                self.assertEqual(env["PLANE_SYNC_RESULTS"], "false")
                self.assertEqual(env["ALLURE_RESULTS_DIR"], str(directory.resolve()))
                self.assertFalse(popen.call_args.kwargs.get("shell", False))

    def test_populated_directory_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "old-result.json").write_text("{}", encoding="utf-8")
            with patch("qa_agents.execution.subprocess.Popen") as popen, self.assertRaises(ValueError):
                run_tests("new-run", temporary, "full")
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
