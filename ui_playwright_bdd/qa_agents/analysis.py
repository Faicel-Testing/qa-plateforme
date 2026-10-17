"""One implementation of triage/RCA shared by the pipeline and standalone agents."""
from .chains import typed_structured
from .model import GatewayChatModel
from .prompts import messages
from .schemas import Diagnosis, Triage


def analyze_failure(failure, operation, *, model=None, triage=None):
    if operation not in {"triage", "rca"}:
        raise ValueError("Unsupported analysis operation")
    schema = Triage if operation == "triage" else Diagnosis
    return typed_structured(messages("triage" if operation == "triage" else "diagnosis", failure, triage),
                            schema, model=model or GatewayChatModel(agent="quality")).model_dump()
