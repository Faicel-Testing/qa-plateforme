"""DeepEval custom model using the framework's metered Node transport."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import time
from deepeval.models import DeepEvalBaseLLM

ROOT = Path(__file__).resolve().parents[2]

class FrameworkJudge(DeepEvalBaseLLM):
    def __init__(self):
        self.calls = 0
        self.interval = float(os.environ.get("DEEPEVAL_JUDGE_INTERVAL_SECONDS", "0"))
        if not 0 <= self.interval <= 60:
            raise ValueError("Judge interval must be between 0 and 60 seconds")
        self.last_call = None
        self.max_calls = int(os.environ.get("DEEPEVAL_MAX_JUDGE_CALLS", "30"))
        if not 1 <= self.max_calls <= 1000:
            raise ValueError("DEEPEVAL_MAX_JUDGE_CALLS must be between 1 and 1000")
        provider = os.environ.get("DEEPEVAL_JUDGE_PROVIDER", "groq")
        if provider != "groq":
            raise ValueError("DeepEval supports Groq only")
        self.name = "groq/" + os.environ.get("DEEPEVAL_JUDGE_MODEL", "openai/gpt-oss-120b")
        super().__init__(model=self.name)

    def load_model(self):
        return self

    def get_model_name(self):
        return self.name

    def generate(self, prompt, schema=None):
        if self.calls >= self.max_calls:
            raise RuntimeError("Judge call budget exhausted")
        if self.last_call is not None:
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_call)))
        self.last_call = time.monotonic()
        self.calls += 1
        request = {"prompt": prompt}
        if schema is not None:
            request["schema"] = schema.model_json_schema()
        completed = subprocess.run(
            [os.environ.get("NODE_BINARY", "node"), str(ROOT / "scripts/deepeval-judge.js")],
            input=json.dumps(request, ensure_ascii=False), text=True, encoding="utf-8",
            capture_output=True, cwd=ROOT, timeout=100,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            raise RuntimeError("Judge provider failed; inspect task metrics and provider configuration")
        output = json.loads(completed.stdout)["output"]
        return schema.model_validate_json(output) if schema is not None else output

    async def a_generate(self, prompt, schema=None):
        # Evaluation runs synchronously to bound cost and avoid CPU overload.
        return self.generate(prompt, schema)
