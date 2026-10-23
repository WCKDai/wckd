#!/usr/bin/env python3
"""A stub agent for tests: reads the WCKD handoff prompt on stdin and writes the artifact for the step.

It is not an LLM. It proves the harness: prompt -> agent -> validated artifact -> gate. Real agents
replace this file with `claude -p`, `codex exec`, an API call, or a person.
"""
import json, os, shutil, sys
from pathlib import Path

ROOT = Path(os.environ.get("WCKD_ROOT", "."))
STEP = os.environ.get("WCKD_STEP", "")
PROJECT = Path(os.environ["WCKD_ROOT"]) / "projects" / os.environ.get("WCKD_SLUG", "p")
PROMPT = sys.stdin.read()
AT = "2026-10-23T00:00:00+00:00"


def ev():
    return [{"kind": "url", "locator": "https://example.org/x", "summary": "stub evidence",
             "captured_at": AT, "captured_by": "scout", "confidence": 0.8, "grade": "found"}]


def prov(by):
    return {"produced_by": by, "produced_at": AT}


BRIEF = {
    "id": "p", "wish": "A CLI that prints hello", "restated": "A CLI that prints hello",
    "realm": "digital", "freshness_days": 90,
    "capabilities": [{"id": "C1", "statement": "a user can run a command and see hello",
                      "priority": "must", "measurable": True, "measure": "exit 0 and stdout == hello"}],
    "constraints": [{"kind": "time", "statement": "one day"}], "non_goals": ["localisation"],
    "horizon": {"first_value": "same day", "lifetime": "1 year"},
    "budget_ceiling": {"build": {"amount": 100, "currency": "USD", "confidence_class": "budgetary"},
                       "run_monthly": {"amount": 0, "currency": "USD", "confidence_class": "definitive"}},
    "bar": {"in_scope": ["correctness"],
            "set_by": {"by": "barkeeper", "role": "barkeeper", "at": AT, "decision": "approve"},
            "dimensions": [{"name": "correctness", "threshold": "stdout is exactly hello",
                            "measure": "shell capture of stdout", "why": "that is the whole want"}]},
    "done_condition": {"statement": "running the command prints hello", "test": ["run it", "compare stdout"]},
    "lessons_read": ["memory/LESSONS.md#protocol"], "questions_asked": [], "provenance": prov("listener")}


def main():
    if STEP.startswith("W"):
        (PROJECT / "brief.json").write_text(json.dumps(BRIEF, indent=2))
        print("stub: wrote brief.json")
    elif STEP.startswith("C"):
        src = ROOT / "examples" / "air-quality-monitor" / "landscape.json"
        if src.exists():
            shutil.copy(src, PROJECT / "landscape.json")
            print("stub: copied the example landscape")
    elif STEP.startswith("K"):
        print("stub: no plan yet; this test stops before K")
    else:
        print(f"stub: nothing to do for {STEP}")


if __name__ == "__main__":
    main()
