"""Bind CLI and subprocess services to one explicit run."""
import os
from pathlib import Path
from .bridge import ROOT
from .evidence import read_execution


def add_selection(parser):
    parser.add_argument("--results-dir", type=Path, default=os.getenv("ALLURE_RESULTS_DIR"))
    parser.add_argument("--run-id", default=os.getenv("QA_RUN_ID"))


def selected(options, parser):
    if not options.results_dir or not options.run_id:
        parser.error("Specify --results-dir and --run-id (or ALLURE_RESULTS_DIR and QA_RUN_ID)")
    return (ROOT / options.results_dir).resolve(), options.run_id


def load_failures(directory, run_id):
    data = read_execution(directory, run_id)
    if data["errors"]:
        raise ValueError("Invalid execution evidence: " + "; ".join(data["errors"]))
    items = [{**r, "message": r["statusDetails"].get("message", ""),
              "trace": r["statusDetails"].get("trace", "")}
             for r in data["results"] if r["status"] in {"failed", "broken"}]
    return data, items
