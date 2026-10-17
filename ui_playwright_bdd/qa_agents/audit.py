"""Compatible verification journal containing hashes, never raw evidence/prompts."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from .bridge import ROOT
from .reports import now


def record(agent, operation, output, context, *, dry=False, accepted=True):
    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    result = {"schemaVersion": 1, "agent": agent, "operation": operation,
              "status": "UNVERIFIED" if accepted else "REJECTED", "timestamp": now(),
              "runId": context.get("run_id"), "outputHash": digest(output), "contextHash": digest(context),
              "scope": "Pydantic output contract only; not a proof of business correctness",
              "limitations": ["Independent reproduction/review required"],
              "checks": [{"name": "contract", "status": "PASS" if accepted else "FAIL"}]}
    if not dry:
        target = Path(os.getenv("QA_VERIFICATION_FILE") or ROOT / "logs/agent-verification" / f"{agent}-{uuid4().hex}.jsonl")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result
