#!/usr/bin/env python3
"""The orchestrator against a real command: prompt -> agent -> validated artifact -> gate, stopping at humans."""
import json, sys, unittest
from pathlib import Path

from tree import Tree, ROOT

STUB = ROOT / "tests" / "stub_agent.py"


class RunLoop(unittest.TestCase):
    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_run_produces_a_brief_then_stops_at_the_human_gate(self):
        self.t.cli("new", "p", "A CLI that prints hello")
        out = self.t.cli("run", "p", "--agent", f"{sys.executable} {STUB}", "--max-turns", "3")
        self.assertIn("step W1", out)
        self.assertIn("G-W Briefed is ready and needs a human", out)
        brief = json.loads((self.t.project() / "brief.json").read_text())
        self.assertEqual(brief["id"], "p")
        self.assertIn("all present artifacts valid", self.t.cli("validate", "p"))
        turns = sorted((self.t.project() / ".turns").glob("*.md"))
        self.assertEqual(len(turns), 1)
        self.assertIn("WCKD handoff", turns[0].read_text())

    def test_after_the_human_gate_it_records_the_next_gate_itself(self):
        self.t.cli("new", "p", "A CLI that prints hello")
        self.t.cli("run", "p", "--agent", f"{sys.executable} {STUB}", "--max-turns", "3")
        self.t.cli("gate", "p", "G-W", "--by", "Galahad", "--human")
        out = self.t.cli("run", "p", "--agent", f"{sys.executable} {STUB}", "--max-turns", "4")
        self.assertIn("G-C Canvassed recorded automatically", out)
        gate = json.loads((self.t.project() / "gates" / "G-C.json").read_text())
        self.assertEqual(gate["decision"], "PASS")
        self.assertIn("step K1", out)

    def test_an_agent_that_writes_nothing_is_caught(self):
        self.t.cli("new", "p", "A CLI that prints hello")
        out = self.t.cli("run", "p", "--agent", "true", "--max-turns", "4", "--max-stale", "2")
        self.assertIn("no artifact changed this turn", out)
        self.assertIn("stopping: the agent is not producing artifacts", out)

    def test_run_without_an_agent_explains_itself(self):
        self.t.cli("new", "p", "A CLI that prints hello")
        out = self.t.cli("run", "p", expect=1)
        self.assertIn("--agent is required", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
