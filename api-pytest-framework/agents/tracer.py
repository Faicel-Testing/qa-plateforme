# ============================================================
# Tracer — Instrumentation des appels LLM
# ============================================================
# Enregistre chaque appel LLM dans logs/traces.jsonl.
# Format JSONL : une ligne JSON par appel, lisible par observability-agent.
#
# Utilisé par llm.py automatiquement — pas d'import manuel nécessaire.
# Chaque entrée contient :
#   ts, agent, fn, model, duration_ms, prompt_len, response_len,
#   success, confidence, error, retries
# ============================================================

import os, json, time, inspect, datetime

FRAMEWORK  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGS_DIR   = os.path.join(FRAMEWORK, "logs")
TRACE_FILE = os.path.join(LOGS_DIR, "traces.jsonl")

os.makedirs(LOGS_DIR, exist_ok=True)


def _detect_agent() -> str:
    """Remonte la stack pour trouver quel agent a appelé llm.*"""
    agents_dir = os.path.normpath(os.path.dirname(__file__))
    for frame_info in inspect.stack():
        fpath = os.path.normpath(frame_info.filename)
        if fpath.startswith(agents_dir) and "llm.py" not in fpath and "tracer.py" not in fpath:
            name = os.path.basename(fpath).replace(".py", "")
            return name
    return "unknown"


def record(
    fn: str,
    duration_ms: float,
    prompt_len: int,
    response_len: int,
    success: bool,
    model: str = "",
    confidence: float = None,
    error: str = None,
    retries: int = 0,
):
    """Écrit une entrée de trace dans logs/traces.jsonl."""
    entry = {
        "ts":           datetime.datetime.utcnow().isoformat() + "Z",
        "agent":        _detect_agent(),
        "fn":           fn,
        "model":        model,
        "duration_ms":  round(duration_ms, 1),
        "prompt_len":   prompt_len,
        "response_len": response_len,
        "success":      success,
        "retries":      retries,
    }
    if confidence is not None:
        entry["confidence"] = round(confidence, 3)
    if error:
        entry["error"] = str(error)[:200]

    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class Span:
    """Context manager pour tracer un bloc d'appel LLM."""

    def __init__(self, fn: str, prompt: str = "", model: str = ""):
        self.fn         = fn
        self.prompt_len = len(prompt)
        self.model      = model
        self._start     = None
        self.response   = ""
        self.confidence = None
        self.retries    = 0
        self.error      = None

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms  = (time.time() - self._start) * 1000
        success      = exc_type is None
        if exc_val and not self.error:
            self.error = str(exc_val)
        record(
            fn=self.fn,
            duration_ms=duration_ms,
            prompt_len=self.prompt_len,
            response_len=len(self.response),
            success=success,
            model=self.model,
            confidence=self.confidence,
            error=self.error,
            retries=self.retries,
        )
        return False  # ne supprime pas l'exception


def load_traces() -> list:
    """Charge toutes les traces depuis logs/traces.jsonl."""
    if not os.path.exists(TRACE_FILE):
        return []
    traces = []
    with open(TRACE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return traces


def clear_traces():
    """Vide le fichier de traces (nouveau run)."""
    if os.path.exists(TRACE_FILE):
        os.remove(TRACE_FILE)
