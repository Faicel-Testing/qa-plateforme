"""Validated contracts for the native QA pipeline. Model confidence is not a gate."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Triage(StrictOutput):
    category: Literal["real_bug", "flaky", "environment", "selector_bug", "test_bug", "unknown"]
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(min_length=1)
    hypotheses: list[str]
    missing_information: list[str]
    suggested_action: str = Field(min_length=1)


class Diagnosis(StrictOutput):
    status: Literal["HYPOTHESIS", "INSUFFICIENT_EVIDENCE"]
    root_cause: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    missing_information: list[str]
    affected_layer: Literal["ui", "pom", "step", "config", "ci", "unknown"]
    next_check: str = Field(min_length=1)
    proposed_fix: str


class SourceAction(StrictOutput):
    file_path: str

    @field_validator("file_path")
    @classmethod
    def source_path(cls, value):
        import re
        value = value.replace("\\", "/")
        if (not re.fullmatch(r"src/(features|steps|pages|core|hooks|support|config|utils|api)/[A-Za-z0-9_./-]+\.(ts|feature)", value)
                or any(part in {"", ".", ".."} for part in value.split("/"))):
            raise ValueError("Only normalized project source paths are allowed")
        return value


class ReadSource(SourceAction):
    action: Literal["read_file"]
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)

    @model_validator(mode="after")
    def line_range(self):
        if self.line_end < self.line_start or self.line_end - self.line_start >= 400:
            raise ValueError("Read at most 400 ordered lines")
        return self


class ProposeFix(SourceAction):
    action: Literal["propose_fix"]
    old: str = Field(min_length=1)
    replacement: str


class Conclude(StrictOutput):
    action: Literal["report_analysis"]
    diagnosis: Diagnosis


class InvestigationAction(RootModel[Annotated[ReadSource | ProposeFix | Conclude, Field(discriminator="action")]]):
    """Each tool action has its own strict arguments, not an optional-field bag."""


class Advice(StrictOutput):
    explanation: str = Field(min_length=1)
    next_checks: list[str]
    limitations: list[str] = Field(min_length=1)


class GeneratedCode(StrictOutput):
    content: str = Field(min_length=1, max_length=200000)
    missing_information: list[str]

    @field_validator("content")
    @classmethod
    def raw_code(cls, value):
        if not value.strip() or value.strip().startswith("```"):
            raise ValueError("Expected nonempty raw code without Markdown fences")
        return value


class RunManifest(BaseModel):
    # Compatible with the existing JS runner; additional provenance is retained there.
    model_config = ConfigDict(extra="ignore", strict=True)
    runId: str = Field(min_length=1)
    completed: bool
    startedAt: int = Field(ge=0)
    finishedAt: int = Field(ge=0)
    exitCode: int | None
    resultCount: int = Field(ge=0)
    timedOut: bool = False
    error: str | None = None


class TestResult(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    uuid: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: Literal["passed", "failed", "broken", "skipped", "unknown"]
    start: int = Field(ge=0)
    stop: int = Field(ge=0)
    statusDetails: dict = Field(default_factory=dict)
    labels: list[dict] = Field(default_factory=list)
