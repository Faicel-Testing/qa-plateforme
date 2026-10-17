import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .bridge import ROOT


def now():
    return datetime.now(timezone.utc).isoformat()


def save(name, value, dry=False, directory=None):
    if dry:
        return
    directory = Path(directory) if directory else ROOT / "docs"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    temporary = directory / (name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
