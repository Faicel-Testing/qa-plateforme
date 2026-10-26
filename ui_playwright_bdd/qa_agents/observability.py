"""Optional, metadata-only Langfuse/OpenTelemetry tracing; business errors propagate."""
from contextlib import contextmanager
from functools import wraps
import os
import re
from urllib.parse import urlsplit

_client = None
_attempted = False
ALLOWED = {"qa.run_id", "qa.operation", "qa.agent", "qa.success", "qa.exit_code",
           "gen_ai.request.model", "langfuse.observation.type", "langfuse.trace.name"}


def attributes(values):
    return {k: v for k, v in values.items() if k in ALLOWED and
            (isinstance(v, (bool, int, float)) or isinstance(v, str) and re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,150}", v))}


def client():
    global _client, _attempted
    if os.getenv("LANGFUSE_ENABLED") != "true":
        return None
    if _attempted:
        return _client
    _attempted = True
    try:
        from langfuse import Langfuse
        url = urlsplit(os.getenv("LANGFUSE_BASE_URL", "http://127.0.0.1:3000"))
        if url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            return None
        if not (url.scheme == "https" or url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}):
            return None
        _client = Langfuse(base_url=url.geturl(), public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                           secret_key=os.environ["LANGFUSE_SECRET_KEY"], timeout=5, flush_at=10, flush_interval=1,
                           should_export_span=lambda s: s.instrumentation_scope.name == "qa-framework")
    except Exception:
        _client = None
    return _client


def _context():
    from opentelemetry import context, trace
    from opentelemetry.propagate import extract
    current = context.get_current()
    if trace.get_current_span(current).get_span_context().is_valid:
        return current
    return extract({"traceparent": os.environ.get("QA_TRACEPARENT", "")}, context=current)


@contextmanager
def observation(name, values=None, parent=None):
    if client() is None:
        yield None
        return
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    with trace.get_tracer("qa-framework").start_as_current_span(name, context=parent or _context(),
            attributes=attributes({"langfuse.observation.type": "span", "qa.run_id": os.getenv("QA_TRACE_RUN_ID", ""), **(values or {})}),
            record_exception=False, set_status_on_exception=False) as span:
        try:
            yield span
        except Exception:
            span.set_status(Status(StatusCode.ERROR, "OPERATION_FAILED"))
            raise
        else:
            successful = (getattr(span, "attributes", None) or {}).get("qa.success") is not False
            span.set_status(Status(StatusCode.OK) if successful else Status(StatusCode.ERROR, "TASK_UNSUCCESSFUL"))


def traced(name):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            with observation(name):
                return fn(*args, **kwargs)
        return wrapped
    return decorate


def child_environment():
    if client() is None:
        return {}
    from opentelemetry.propagate import inject
    carrier = {}
    inject(carrier, context=_context())
    return {"QA_TRACEPARENT": carrier["traceparent"], "QA_TRACE_RUN_ID": os.getenv("QA_TRACE_RUN_ID", "")} if carrier.get("traceparent") else {}


def set_run_id(run_id):
    os.environ["QA_TRACE_RUN_ID"] = run_id
    if client() is not None:
        from opentelemetry import trace
        trace.get_current_span().set_attributes(attributes({"qa.run_id": run_id}))


def flush():
    if _client is not None:
        try:
            from opentelemetry import trace
            trace.get_tracer_provider().force_flush(timeout_millis=2000)
        except Exception:
            pass


def callbacks():
    if client() is None:
        return []
    return [_callback()]


_handler = None


def _callback():
    global _handler
    if _handler is not None:
        return _handler
    from langchain_core.callbacks import BaseCallbackHandler
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from threading import Lock

    class MetadataCallback(BaseCallbackHandler):
        """Track chains/models/tools without retaining their inputs, outputs or errors."""
        def __init__(self):
            self.spans = {}
            self.lock = Lock()

        def _start(self, kind, run_id, parent_run_id, name=None):
            with self.lock:
                parent = self.spans.get(parent_run_id)
                ctx = trace.set_span_in_context(parent) if parent else _context()
                safe = name if isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_.:-]{1,80}", name) else kind
                span = trace.get_tracer("qa-framework").start_span("langchain." + safe, context=ctx,
                    attributes=attributes({"langfuse.observation.type": kind, "qa.run_id": os.getenv("QA_TRACE_RUN_ID", "")}))
                self.spans[run_id] = span

        def _end(self, run_id, failed=False):
            with self.lock:
                span = self.spans.pop(run_id, None)
            if span is not None:
                span.set_status(Status(StatusCode.ERROR, "OPERATION_FAILED") if failed else Status(StatusCode.OK))
                span.end()

        def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
            self._start("chain", run_id, parent_run_id, kwargs.get("name"))

        def on_chain_end(self, outputs, *, run_id, **kwargs): self._end(run_id)
        def on_chain_error(self, error, *, run_id, **kwargs): self._end(run_id, True)
        def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs): self._start("generation", run_id, parent_run_id)
        def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, **kwargs): self._start("generation", run_id, parent_run_id)
        def on_llm_end(self, response, *, run_id, **kwargs): self._end(run_id)
        def on_llm_error(self, error, *, run_id, **kwargs): self._end(run_id, True)
        def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs): self._start("tool", run_id, parent_run_id)
        def on_tool_end(self, output, *, run_id, **kwargs): self._end(run_id)
        def on_tool_error(self, error, *, run_id, **kwargs): self._end(run_id, True)
    _handler = MetadataCallback()
    return _handler
