"""Code generation contract and fail-closed proposal boundary, without a live LLM."""
import io
from contextlib import redirect_stdout
from hashlib import sha256
import unittest
from qa_agents.codegen import generation_graph, run, fill
from test_pipeline import FakeModel


CONTENT = "Feature: Login\n  Scenario: Valid login\n    Given a registered user\n"
OUTPUT = {"content": CONTENT, "missing_information": []}
STATE = {"file": "src/features/login.feature", "kind": "gherkin", "messages": []}


class Bridge:
    def __init__(self, verification=None, dry=False, proposal=None):
        self.calls = []
        self.dry_run = dry
        self.verification = verification if verification is not None else {
            "status": "UNVERIFIED", "checks": [{"name": name, "status": "PASS"}
                                                for name in ("available", "syntax", "typescript-project")]}
        self.proposal = proposal

    def call(self, operation, **kwargs):
        self.calls.append(operation)
        if operation == "verify":
            return self.verification
        if operation == "propose":
            return self.proposal if self.proposal is not None else {
                "status": "preview" if self.dry_run else "pending", "file": kwargs["file"].replace("/", "\\"),
                "id": "proposal-1", "digest": sha256(kwargs["content"].encode()).hexdigest()}
        raise AssertionError(operation)


class CodegenTests(unittest.TestCase):
    def test_valid_candidate_requires_review(self):
        bridge = Bridge()
        result = generation_graph(bridge, FakeModel(OUTPUT)).invoke(STATE)
        self.assertEqual(bridge.calls, ["verify", "propose"])
        self.assertEqual(result["proposal"]["status"], "pending")
        self.assertEqual(result["verification"]["status"], "UNVERIFIED")

    def test_invalid_contract_never_calls_services(self):
        for output in [{}, {**OUTPUT, "file": "outside.ts"}, {**OUTPUT, "content": " "},
                       {**OUTPUT, "content": "```gherkin\nFeature: X\n```"}]:
            bridge = Bridge()
            with self.subTest(output=output), self.assertRaises(ValueError):
                generation_graph(bridge, FakeModel(output, output)).invoke(STATE)
            self.assertEqual(bridge.calls, [])

    def test_missing_prerequisites_prevent_proposal(self):
        bridge = Bridge()
        with self.assertRaises(ValueError):
            generation_graph(bridge, FakeModel({**OUTPUT, "missing_information": ["Expected behavior"]})).invoke(STATE)
        self.assertEqual(bridge.calls, [])

    def test_invalid_target_precedes_model_call(self):
        model = FakeModel()
        for file in ["../secret.ts", "src/features/../other.feature", "src/core/world.ts"]:
            with self.subTest(file=file), self.assertRaises(ValueError):
                generation_graph(Bridge(), model).invoke({**STATE, "file": file})
        self.assertEqual(model.calls, 0)

    def test_failed_missing_and_unknown_verifications_block_proposal(self):
        for verification in [{}, {"status": "UNVERIFIED", "checks": []},
                             {"status": "VALIDATED", "checks": [{"name": "syntax", "status": "PASS"}]},
                             {"status": "UNKNOWN"}, {"status": "REJECTED"},
                             {"status": "UNVERIFIED", "checks": [{"name": "syntax", "status": "FAIL"}]}]:
            bridge = Bridge(verification)
            with self.subTest(verification=verification), self.assertRaises(ValueError):
                generation_graph(bridge, FakeModel(OUTPUT)).invoke(STATE)
            self.assertEqual(bridge.calls, ["verify"])

    def test_typescript_requires_project_compilation(self):
        bridge = Bridge({"status": "UNVERIFIED", "checks": [
            {"name": name, "status": "PASS"} for name in ("available", "syntax")]})
        with self.assertRaises(ValueError):
            generation_graph(bridge, FakeModel(OUTPUT)).invoke({**STATE, "kind": "typescript", "file": "src/pages/Login.ts"})
        self.assertEqual(bridge.calls, ["verify"])

    def test_wrong_proposal_acknowledgement_is_not_success(self):
        for proposal in [{}, {"status": "applied"}, {"status": "pending", "id": "1", "file": STATE["file"], "digest": "wrong"}]:
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                generation_graph(Bridge(proposal=proposal), FakeModel(OUTPUT)).invoke(STATE)

    def test_preview_receipt_is_valid_only_in_preview_mode(self):
        result = generation_graph(Bridge(dry=True), FakeModel(OUTPUT)).invoke(STATE)
        self.assertEqual(result["proposal"]["status"], "preview")

    def test_dry_run_has_no_external_calls(self):
        bridge, model = Bridge(), FakeModel()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(["spec", "--dry-run"], bridge, model), 0)
        self.assertEqual(bridge.calls, [])
        self.assertEqual(model.calls, 0)

    def test_template_preserves_false_and_zero(self):
        self.assertEqual(fill("{a}/{b}/{c}", {"a": 0, "b": False, "c": None}), "0/False/Non fournie")

    def test_story_generation_includes_referenced_sources_only(self):
        class StoryBridge(Bridge):
            def call(self, operation, **kwargs):
                values = {
                    "story": {"key": "APP-1", "summary": "Login", "description": "src/features/login.feature"},
                    "prompt": "{us_description}", "skill": "Generate", "gherkin_contract": "English Gherkin",
                    "sources": {"errors": [], "files": [
                        {"file": "src/features/login.feature", "content": "REFERENCED_FEATURE"},
                        {"file": "src/features/other.feature", "content": "UNRELATED_FEATURE"},
                        {"file": "src/steps/login.ts", "content": "EXISTING_STEP; import { Login } from '../pages/Login';"},
                        {"file": "src/steps/other.ts", "content": "UNRELATED_STEP"},
                        {"file": "src/pages/Login.ts", "content": "EXISTING_PAGE"},
                        {"file": "src/fixtures/user.json", "content": "PRIVATE_FIXTURE"},
                    ]},
                }
                return values[operation] if operation in values else super().call(operation, **kwargs)

        class InspectModel(FakeModel):
            def invoke(self, messages, **kwargs):
                prompt = "\n".join(message.content for message in messages)
                for marker in ("REFERENCED_FEATURE", "EXISTING_STEP", "EXISTING_PAGE"):
                    assert marker in prompt
                for marker in ("UNRELATED_FEATURE", "UNRELATED_STEP", "PRIVATE_FIXTURE"):
                    assert marker not in prompt
                return super().invoke(messages, **kwargs)

        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(["gherkin", "APP-1"], StoryBridge(), InspectModel(OUTPUT)), 0)
