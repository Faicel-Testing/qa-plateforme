"""Plane-only planning and coverage orchestration."""
import json
from .bridge import Bridge
from .chains import chat
from .model import GatewayChatModel


def run(args):
    bridge = Bridge("planning", dry_run="--dry-run" in args)
    positional = [a for a in args if not a.startswith("--")]
    command = positional[0] if positional else "help"
    sub = positional[1] if len(positional) > 1 else None
    if command == "coverage":
        coverage = bridge.call("coverage")
        if sub in {None, "analyze", "gaps"}:
            print(json.dumps(coverage, ensure_ascii=False, indent=2))
        elif sub == "suggest":
            prompt = "Suggest missing Gherkin scenarios from these coverage facts. Tags alone do not prove requirement coverage. English Gherkin keywords, French descriptions. Return only Scenario blocks:\n" + json.dumps(coverage, ensure_ascii=False)
            content = chat([{"role": "user", "content": prompt}], model=GatewayChatModel(agent="planning"))["message"]["content"]
            bridge.call("verify", kind="suggest", output=content)
            print("UNVERIFIED SUGGESTION\n" + content)
        else:
            raise ValueError("Unknown coverage command")
        return 0
    operations = {"check": "plane_check", "stories": "stories", "testcases": "testcases", "cycles": "cycles", "sprint": "cycles"}
    if command not in operations:
        print("planning: check | stories [create] | testcases | cycles list | coverage analyze/gaps/suggest")
        return 0 if command == "help" else 1
    if command in {"cycles", "sprint"} and sub not in {None, "list"}:
        raise ValueError("Only cycles list is supported")
    if command == "stories" and sub not in {None, "list", "create"}:
        raise ValueError("Unknown stories action")
    operation = "import_stories" if command == "stories" and sub == "create" else operations[command]
    print(json.dumps(bridge.call(operation), ensure_ascii=False, indent=2))
    return 0
