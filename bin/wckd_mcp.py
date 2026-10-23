#!/usr/bin/env python3
"""wckd_mcp — the WCKD protocol as an MCP server (stdio, JSON-RPC 2.0, stdlib only).

Any MCP-capable agent (Claude Desktop/Code, Cursor, Windsurf, a custom loop) can now run WCKD:
list projects, ask who runs next, get a self-contained handoff prompt, write a validated artifact,
record a gate, score the goals. The CLI does no domain work; neither does this — it is the same
protocol surface, reached over a different transport.

    {"mcpServers": {"wckd": {"command": "python3", "args": ["/path/to/wckd/bin/wckd_mcp.py"]}}}

Wire protocol: one JSON object per line on stdin/stdout. No dependencies beyond the Python stdlib
(and PyYAML, only if you edit workflows/ without regenerating machine/).
"""
import contextlib, importlib.util, io, json, os, sys, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_wckd():
    spec = importlib.util.spec_from_file_location("wckd", ROOT / "bin" / "wckd.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wckd = _load_wckd()


# ---------------------------------------------------------------- helpers

def _run(fn, ns):
    """Call a CLI command, capturing its stdout. Raises ToolError on SystemExit."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            fn(ns)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0
        out = buf.getvalue().strip()
        if code not in (0, None):
            raise ToolError(out or f"command failed with exit {code}")
        return out
    except Exception:
        raise ToolError(buf.getvalue().strip() + "\n" + traceback.format_exc(limit=3))
    return buf.getvalue().strip()


class ToolError(Exception):
    pass


def _ns(**kw):
    from argparse import Namespace
    return Namespace(**kw)


def _safe_artifact(slug, rel):
    pdir = (wckd.PROJECTS / slug).resolve()
    target = (pdir / rel).resolve()
    if pdir not in target.parents and target != pdir:
        raise ToolError(f"path escapes the project directory: {rel}")
    return target


def _schema_for(rel):
    if rel in wckd.FILE_SCHEMA:
        return wckd.FILE_SCHEMA[rel]
    head = rel.split("/")[0] + "/"
    return wckd.DIR_SCHEMA.get(head)


def tool_projects(_):
    out = []
    for d in sorted(wckd.PROJECTS.glob("*/")):
        if not (d / "wish.json").exists():
            continue
        try:
            wish = wckd.load_json(d / "wish.json")
        except Exception:
            wish = {}
        st = wckd.gate_state(d)
        t = wckd.terminal_state(d)
        out.append({"slug": d.name, "wish": wish.get("text", ""), "gates": st,
                    "state": (t or {}).get("decision", "open"),
                    "current_gate": next((g for g in wckd.gates_def()["order"] if st.get(g) not in wckd.PASSING), None)})
    return out


def tool_read_artifact(args):
    slug, rel = args["slug"], args["path"]
    p = _safe_artifact(slug, rel)
    if not p.exists():
        raise ToolError(f"{rel} does not exist in {slug}")
    return p.read_text() if p.suffix != ".json" else wckd.load_json(p)


def tool_write_artifact(args):
    slug, rel, content = args["slug"], args["path"], args["content"]
    p = _safe_artifact(slug, rel)
    text = content if isinstance(content, str) else json.dumps(content, indent=2)
    if p.suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ToolError(f"{rel} is not valid JSON: {e}")
        name = _schema_for(rel)
        if name:
            tmp = p.with_suffix(".tmp.json")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, indent=2) + "\n")
            ok, err = wckd.Validators().check(tmp, name)
            if not ok:
                tmp.unlink()
                raise ToolError(f"{rel} does not validate against schemas/{name}: {err}")
            tmp.replace(p)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, indent=2) + "\n")
        return f"wrote {rel} ({os.path.getsize(p)} bytes, schema {name or 'none'})"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return f"wrote {rel} ({os.path.getsize(p)} bytes)"


TOOLS = [
    {"name": "wckd_projects", "description": "List WCKD projects with their gate state and whether they ended in KILL/WAIT.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}, "fn": tool_projects},
    {"name": "wckd_new", "description": "Create a project from a verbatim wish. Returns the first step to run.",
     "inputSchema": {"type": "object", "required": ["slug", "wish"],
                     "properties": {"slug": {"type": "string"}, "wish": {"type": "string"},
                                    "by": {"type": "string", "default": "human"}}, "additionalProperties": False},
     "fn": lambda a: _run(wckd.cmd_new, _ns(slug=a["slug"], wish=a["wish"], by=a.get("by", "human")))},
    {"name": "wckd_next", "description": "Who runs next: the open gate, what is blocking it, and the steps that close it.",
     "inputSchema": {"type": "object", "required": ["slug"],
                     "properties": {"slug": {"type": "string"}}, "additionalProperties": False},
     "fn": lambda a: _run(wckd.cmd_next, _ns(slug=a["slug"]))},
    {"name": "wckd_status", "description": "Artifact presence and validity, gate decisions, and the current gate.",
     "inputSchema": {"type": "object", "required": ["slug"],
                     "properties": {"slug": {"type": "string"}}, "additionalProperties": False},
     "fn": lambda a: _run(wckd.cmd_status, _ns(slug=a["slug"]))},
    {"name": "wckd_validate", "description": "Validate every present artifact against schemas/.",
     "inputSchema": {"type": "object", "required": ["slug"],
                     "properties": {"slug": {"type": "string"}}, "additionalProperties": False},
     "fn": lambda a: _run(wckd.cmd_validate, _ns(slug=a["slug"]))},
    {"name": "wckd_handoff", "description": "A self-contained role prompt for the next step (or a named step): system prompt, task, output path and JSON Schema inlined. Hand it to any model.",
     "inputSchema": {"type": "object", "required": ["slug"],
                     "properties": {"slug": {"type": "string"}, "step": {"type": "string"},
                                    "role": {"type": "string"}, "inline": {"type": "boolean", "default": True},
                                    "format": {"type": "string", "enum": ["md", "json"], "default": "json"}},
                     "additionalProperties": False},
     "fn": lambda a: _run(wckd.cmd_handoff, _ns(slug=a["slug"], step=a.get("step"), role=a.get("role"),
                                                inline=a.get("inline", True), out=None,
                                                format=a.get("format", "json")))},
    {"name": "wckd_gate", "description": "Record a gate decision. Refuses when prerequisites, evidence or a human sign-off are missing. KILL and WAIT are terminal and need a note.",
     "inputSchema": {"type": "object", "required": ["slug", "gate", "by"],
                     "properties": {"slug": {"type": "string"}, "gate": {"type": "string"},
                                    "by": {"type": "string"},
                                    "decision": {"type": "string", "enum": ["PASS", "FAIL", "PASS_WITH_CONDITIONS", "KILL", "WAIT"]},
                                    "human": {"type": "boolean", "default": False},
                                    "note": {"type": "string"},
                                    "conditions": {"type": "array", "items": {"type": "string"},
                                                   "description": "statement|owner|due_gate"}},
                     "additionalProperties": False},
     "fn": lambda a: _run(wckd.cmd_gate, _ns(slug=a["slug"], gate=a["gate"], by=a["by"],
                                             human=a.get("human", False),
                                             decision=a.get("decision", "PASS"),
                                             condition=a.get("conditions") or None,
                                             note=a.get("note")))},
    {"name": "wckd_close", "description": "Close condition <index> (1-based) on a recorded gate.",
     "inputSchema": {"type": "object", "required": ["slug", "gate", "index", "by"],
                     "properties": {"slug": {"type": "string"}, "gate": {"type": "string"},
                                    "index": {"type": "integer", "minimum": 1}, "by": {"type": "string"},
                                    "note": {"type": "string"}}, "additionalProperties": False},
     "fn": lambda a: _run(wckd.cmd_close, _ns(slug=a["slug"], gate=a["gate"], index=a["index"],
                                              by=a["by"], note=a.get("note")))},
    {"name": "wckd_score", "description": "Score GOALS.md G1–G12 from the artifacts; optionally append the ledger row.",
     "inputSchema": {"type": "object", "required": ["slug"],
                     "properties": {"slug": {"type": "string"}, "ledger": {"type": "boolean", "default": False},
                                    "by": {"type": "string"}, "strict": {"type": "boolean", "default": False}},
                     "additionalProperties": False},
     "fn": lambda a: _run(wckd.cmd_score, _ns(slug=a["slug"], ledger=a.get("ledger", False),
                                              by=a.get("by"), strict=a.get("strict", False)))},
    {"name": "wckd_read_artifact", "description": "Read one project artifact (JSON parsed, other text raw).",
     "inputSchema": {"type": "object", "required": ["slug", "path"],
                     "properties": {"slug": {"type": "string"}, "path": {"type": "string"}},
                     "additionalProperties": False}, "fn": tool_read_artifact},
    {"name": "wckd_write_artifact", "description": "Write one artifact. JSON is validated against its schema before it lands; an invalid artifact is refused, never written.",
     "inputSchema": {"type": "object", "required": ["slug", "path", "content"],
                     "properties": {"slug": {"type": "string"}, "path": {"type": "string"},
                                    "content": {"type": ["string", "object"],
                                                "description": "JSON string/object for .json, raw text otherwise"}},
                     "additionalProperties": False}, "fn": tool_write_artifact},
    {"name": "wckd_protocol", "description": "The compiled protocol manifest: phases, steps, gates, roles, verdicts, tolerances, campaigns, physical obligations.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "fn": lambda a: wckd.machine_protocol() or {}},
]


# ---------------------------------------------------------------- JSON-RPC

def respond(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def handle(req):
    method = req.get("method")
    rid = req.get("id")
    if rid is None:                      # notification: never answered
        return
    if method == "initialize":
        respond(rid, {"protocolVersion": req.get("params", {}).get("protocolVersion", "2025-06-18"),
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "wckd", "version": wckd.VERSION},
                      "instructions": "WCKD: no build before a Canvassed PASS. Call wckd_next, then wckd_handoff "
                                      "for the role prompt, write the artifact with wckd_write_artifact, then "
                                      "wckd_gate. Human sign-off is required at G-W, G-K and G-D4."})
        return
    if method == "ping":
        respond(rid, {})
        return
    if method == "tools/list":
        respond(rid, {"tools": [{k: v for k, v in t.items() if k != "fn"} for t in TOOLS]})
        return
    if method == "tools/call":
        params = req.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        tool = next((t for t in TOOLS if t["name"] == name), None)
        if not tool:
            respond(rid, error={"code": -32602, "message": f"unknown tool {name}"})
            return
        missing = [k for k in tool["inputSchema"].get("required", []) if k not in args]
        if missing:
            respond(rid, error={"code": -32602, "message": f"missing arguments: {', '.join(missing)}"})
            return
        try:
            result = tool["fn"](args)
            text = result if isinstance(result, str) else json.dumps(result, indent=2)
            respond(rid, {"content": [{"type": "text", "text": text}], "isError": False})
        except ToolError as e:
            respond(rid, {"content": [{"type": "text", "text": str(e)}], "isError": True})
        except Exception:
            respond(rid, {"content": [{"type": "text", "text": traceback.format_exc(limit=4)}], "isError": True})
        return
    respond(rid, error={"code": -32601, "message": f"method not found: {method}"})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except json.JSONDecodeError:
            respond(None, error={"code": -32700, "message": "parse error"})


if __name__ == "__main__":
    main()
