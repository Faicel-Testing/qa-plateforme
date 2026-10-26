"""Synthetic LangGraph/LangChain + real Node retrieval integration proof."""
import json
import os
import subprocess
from uuid import uuid4
from langgraph.graph import StateGraph, START, END
from .bridge import ROOT, environment, Bridge
from .model import GatewayChatModel
from .chains import chat
from .observability import observation, callbacks, child_environment, set_run_id, flush


def run():
    environment()
    set_run_id("observability-" + uuid4().hex)
    with observation("installation.python", {"langfuse.observation.type": "agent", "qa.operation": "installation-check"}) as root:
        if root is None or not root.is_recording():
            raise RuntimeError("LANGFUSE_PYTHON_CONTEXT_UNAVAILABLE")
        python_trace_id = format(root.get_span_context().trace_id, "032x")
        def retrieve(state):
            Bridge("quality").call("coverage")
            env = {**os.environ, **child_environment(), "RAG_RERANK_ENABLED": "false"}
            result = subprocess.run(["node", str(ROOT / "scripts/check-langfuse-node.cjs")], cwd=ROOT, env=env,
                                    text=True, encoding="utf-8", capture_output=True, timeout=1200, check=True)
            return {**state, "node": json.loads(result.stdout)}

        def validate(state):
            model = GatewayChatModel(transport=lambda operation, **kwargs: {"message": {"content": "OK"}})
            response = chat([{"role": "user", "content": "Synthetic check; input must not be exported"}], model=model)
            if response["message"]["content"] != "OK":
                raise ValueError("Contract failed")
            return state

        graph = StateGraph(dict)
        graph.add_node("retrieval", retrieve)
        graph.add_node("contract", validate)
        graph.add_edge(START, "retrieval")
        graph.add_edge("retrieval", "contract")
        graph.add_edge("contract", END)
        result = graph.compile().invoke({}, {"callbacks": callbacks()})
        result["node"]["pythonTraceId"] = python_trace_id
        if result["node"]["traceId"] != python_trace_id:
            raise RuntimeError("LANGFUSE_TRACE_MISMATCH")
    flush()
    print(json.dumps(result["node"]))


if __name__ == "__main__":
    try:
        run()
    finally:
        flush()
