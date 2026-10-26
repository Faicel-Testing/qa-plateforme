"""Unified CLI. Native AI workflows plus explicit deterministic JS adapters."""
import json
import subprocess
import sys
from .bridge import ROOT, environment

ADAPTERS = {name: name for name in ["runner", "reporting", "observability", "governance", "ci", "allure", "review-change", "qa-workflow"]}
ADAPTERS["pipeline-legacy"] = "pipeline"
ADAPTERS["advisor-legacy"] = "advisor"


def adapter(agent, args):
    env = environment()
    env["QA_AGENT_RUNTIME"] = "python"
    # Preload only this adapter. Child framework services route through the gateway.
    command = ["node", "--require", str(ROOT / "scripts/python-llm.cjs"), str(ROOT / "scripts/agents" / (ADAPTERS[agent] + "-agent.js")), *args]
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    return result.returncode if result.returncode >= 0 else 1


def _main(argv=None):
    environment()
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in {"--help", "help"}:
        print("Python QA agents: pipeline planning codegen quality bug advisor data " + " ".join(ADAPTERS) + " doctor selftest")
        return 0
    agent, *options = args
    if agent == "data":
        from .data import run
        return run(options)
    if agent == "selftest":
        import unittest
        suite = unittest.defaultTestLoader.discover(str(ROOT / "qa_agents/tests"), pattern="test_*.py")
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if agent == "pipeline":
        print("[Pipeline] Chargement de LangGraph et des agents...", flush=True)
        from .pipeline import run
        return run(options)
    if agent == "doctor":
        from importlib.metadata import version
        from .model import GatewayChatModel
        from .codegen import generation_graph
        from .bridge import Bridge
        from .pipeline import build_graph
        generation_graph(Bridge("codegen", True), GatewayChatModel(agent="codegen"))
        build_graph()
        print(json.dumps({"python": sys.version.split()[0], "langchain": version("langchain"), "langgraph": version("langgraph"),
                          "native": ["pipeline", "planning", "codegen", "quality", "bug", "advisor"], "adapters": list(ADAPTERS),
                          "gateway": "existing guarded Node gateway", "remoteTracing": False}, indent=2))
        return 0
    if agent in {"planning", "codegen", "quality", "bug", "advisor"}:
        from importlib import import_module
        print(f"Python / LangChain: {agent}", flush=True)
        return import_module("qa_agents." + agent).run(options)
    if agent in ADAPTERS:
        print(f"Python / LangChain: {agent} (framework adapter)", flush=True)
        return adapter(agent, options)
    raise ValueError("Unknown agent")


def main(argv=None):
    environment()
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] not in {"pipeline", "planning", "codegen", "quality", "bug", "advisor", "data", *ADAPTERS} or "--dry-run" in args:
        return _main(args)
    from .observability import observation, flush
    try:
        with observation("agent." + args[0], {"qa.agent": args[0], "langfuse.observation.type": "agent"}) as span:
            result = _main(args)
            if span is not None:
                span.set_attributes({"qa.exit_code": result if isinstance(result, int) else 0, "qa.success": result in (None, 0)})
            return result
    finally:
        flush()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as error:
        print("Agent failed: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
