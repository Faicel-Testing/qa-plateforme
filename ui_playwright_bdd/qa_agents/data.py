"""Deterministic data agent; no LLM and no access to the application database."""
import argparse
import json
import subprocess
from .bridge import ROOT, environment


def command(action, run_id=None):
    args = ["node", str(ROOT / "scripts/data-agent.cjs"), action]
    if run_id:
        args += ["--run-id", run_id]
    result = subprocess.run(args, cwd=ROOT, env=environment(), capture_output=True,
                            text=True, encoding="utf-8", timeout=60, check=False)
    if result.returncode:
        raise RuntimeError("Data agent unavailable: configure the dedicated PostgreSQL database and run npm run data:init")
    return json.loads(result.stdout)


def run(args):
    parser = argparse.ArgumentParser(description="PostgreSQL test data agent (no LLM)")
    parser.add_argument("action", choices=["init", "seed", "prepare", "status", "complete"])
    parser.add_argument("--run-id")
    options = parser.parse_args(args)
    if options.action in {"prepare", "complete"} and not options.run_id:
        parser.error("--run-id is required")
    print(json.dumps(command(options.action, options.run_id), indent=2))
    return 0
