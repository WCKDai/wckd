#!/usr/bin/env python3
"""The MCP transport: handshake, tool list, and a full turn through tools/call."""
import json, subprocess, sys, unittest

from tree import Tree, ROOT


class Mcp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = Tree()

    @classmethod
    def tearDownClass(cls):
        cls.t.close()

    def session(self, messages):
        lines = "\n".join(json.dumps(m) for m in messages) + "\n"
        r = subprocess.run([sys.executable, str(self.t.root / "bin" / "wckd_mcp.py")], input=lines,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stderr.strip(), "", r.stderr)
        return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]

    def call(self, rid, name, args):
        return {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": name, "arguments": args}}

    def test_handshake_and_tools(self):
        out = self.session([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(len(out), 2)                      # the notification is never answered
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "wckd")
        tools = {t["name"] for t in out[1]["result"]["tools"]}
        self.assertIn("wckd_handoff", tools)
        self.assertIn("wckd_write_artifact", tools)
        self.assertEqual(len(tools), 12)

    def test_full_turn_through_tools(self):
        out = self.session([
            self.call(1, "wckd_new", {"slug": "mcp", "wish": "A CLI that says hi"}),
            self.call(2, "wckd_write_artifact", {"slug": "mcp", "path": "brief.json", "content": {"nope": 1}}),
            self.call(3, "wckd_next", {"slug": "mcp"}),
            self.call(4, "wckd_handoff", {"slug": "mcp", "format": "md"}),
            self.call(5, "wckd_protocol", {}),
            self.call(6, "wckd_projects", {}),
        ])
        by_id = {r["id"]: r for r in out}
        self.assertFalse(by_id[1]["result"]["isError"])
        self.assertTrue(by_id[2]["result"]["isError"])      # schema-invalid artifact refused
        self.assertIn("does not validate", by_id[2]["result"]["content"][0]["text"])
        self.assertIn("current gate: G-W", by_id[3]["result"]["content"][0]["text"])
        self.assertIn("WCKD handoff", by_id[4]["result"]["content"][0]["text"])
        proto = json.loads(by_id[5]["result"]["content"][0]["text"])
        self.assertEqual(len(proto["roles"]), 17)
        self.assertEqual(len(proto["gates"]), 8)
        projects = json.loads(by_id[6]["result"]["content"][0]["text"])
        self.assertEqual([p["slug"] for p in projects], ["mcp"])

    def test_unknown_tool_and_missing_arguments(self):
        out = self.session([
            self.call(1, "nope", {}),
            self.call(2, "wckd_gate", {"slug": "mcp"}),
        ])
        self.assertEqual(out[0]["error"]["code"], -32602)
        self.assertIn("missing arguments", out[1]["error"]["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
