"""Narrow JSON transport to the existing, guarded framework services."""
import json
import os
from pathlib import Path
import subprocess
from dotenv import load_dotenv
from .observability import child_environment, traced

ROOT = Path(__file__).resolve().parent.parent


def environment():
    load_dotenv(ROOT / ".env", override=False)
    env = os.environ.copy()
    env.update(PYTHONIOENCODING="utf-8", LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false")
    if env.get("NODE_EXTRA_CA_CERTS"):
        env["NODE_EXTRA_CA_CERTS"] = str((ROOT / env["NODE_EXTRA_CA_CERTS"]).resolve())
    return env


class BridgeError(RuntimeError):
    pass


class Bridge:
    def __init__(self, agent="quality", dry_run=False, execution_env=None):
        self.agent = agent
        self.dry_run = dry_run
        self.execution_env = execution_env or {}
        if set(self.execution_env) - {"ALLURE_RESULTS_DIR", "QA_RUN_ID"}:
            raise ValueError("Only execution-scoped environment overrides are allowed")

    @traced("bridge.service")
    def call(self, operation, **payload):
        request = {"operation": operation, "agent": self.agent, "dryRun": self.dry_run, **payload}
        env = environment()
        env.update(child_environment())
        env.update(self.execution_env)
        # The gateway worker must not route back into Python (recursive transport).
        env["QA_PYTHON_BRIDGE"] = "1"
        try:
            result = subprocess.run(
                ["node", str(ROOT / "scripts/python-bridge.cjs")],
                input=json.dumps(request, ensure_ascii=False), encoding="utf-8",
                errors="replace", capture_output=True, cwd=ROOT, env=env,
                timeout=600, check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise BridgeError("Framework service deadline exceeded") from error
        try:
            response = json.loads(result.stdout)
        except (ValueError, TypeError) as error:
            raise BridgeError("Invalid framework service response; no result accepted") from error
        if not response.get("ok"):
            raise BridgeError(response.get("error", "Framework service failed"))
        if result.returncode:
            raise BridgeError("Framework service exited unsuccessfully")
        return response.get("value")
