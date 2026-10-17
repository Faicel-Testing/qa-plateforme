"""One JSON request per process; no secret or prompt is written to stderr."""
import json
import sys
from .chains import dispatch


def main():
    try:
        request = json.load(sys.stdin)
        result = dispatch(request["method"], request["args"], request.get("agent", "quality"))
        json.dump({"ok": True, "value": result}, sys.stdout, ensure_ascii=False)
        return 0
    except Exception as error:
        # Exception messages from external libraries may contain request data.
        json.dump({"ok": False, "error": "LangChain operation failed: " + type(error).__name__}, sys.stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
