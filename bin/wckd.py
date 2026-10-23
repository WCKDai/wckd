#!/usr/bin/env python3
"""wckd - reference orchestrator for the WCKD protocol (Want -> Canvass -> Keep/Kill -> Deliver).

  wckd new <slug> "<wish>" [--by NAME]       create a project from the template
  wckd status <slug>                          artifacts, validity, gates passed, current gate
  wckd validate <slug>                        validate every artifact against schemas/
  wckd next <slug>                            who runs next, with the exact prompt to hand them
  wckd gate <slug> <GATE> --by NAME [--human] [--decision PASS|FAIL|PASS_WITH_CONDITIONS|KILL|WAIT]
                                   [--condition "statement|owner|due_gate"]... [--note TEXT]
                                              record a gate; refuses when prerequisites are missing
                                              KILL/WAIT are terminal and need a --note reason
  wckd close <slug> <GATE> <index> --by NAME [--note TEXT]
                                              close condition <index> (1-based) on a gate record

The CLI does no domain work. It enforces order, validates artifacts, and records decisions.
Requires: pip install pyyaml jsonschema
"""
import argparse, datetime, hashlib, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS, WORKFLOWS, PROJECTS = ROOT / "schemas", ROOT / "workflows", ROOT / "projects"

try:
    import yaml
except ImportError:
    sys.exit("wckd needs PyYAML: pip install pyyaml")

FILE_SCHEMA = {"wish.json": "wish", "brief.json": "brief", "landscape.json": "landscape", "verdict.json": "verdict",
               "blueprint.json": "blueprint", "cost.json": "cost", "prospect.json": "prospect", "plan.json": "plan",
               "release.json": "release", "runbook.json": "runbook"}
DIR_SCHEMA = {"workorders": "workorder", "proofs": "validation", "breaches": "break", "gates": "gate", "messages": "message"}
HUMAN_GATES = {"G-W", "G-K", "G-D4"}
PASSING = {"PASS", "PASS_WITH_CONDITIONS"}
TERMINAL = {"KILL", "WAIT"}

# ---------------------------------------------------------------- helpers

def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

def sha256(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load_json(p: Path):
    return json.loads(p.read_text())

def project_dir(slug):
    d = PROJECTS / slug
    if not d.exists():
        sys.exit(f"no project '{slug}' - run: wckd new {slug} \"<wish>\"")
    return d

def gates_def():
    return yaml.safe_load((WORKFLOWS / "gates.yaml").read_text())

def workflow_steps():
    wf = yaml.safe_load((WORKFLOWS / "wckd.workflow.yaml").read_text())
    return [s | {"phase": p["id"]} for p in wf["phases"] for s in p["steps"]]

# ---------------------------------------------------------------- validation

class Validators:
    def __init__(self):
        self.schemas = {p.stem.replace(".schema", ""): load_json(p) for p in SCHEMAS.glob("*.schema.json")}
        self.lib = None
        try:
            from jsonschema import Draft202012Validator
            from referencing import Registry, Resource
            from referencing.jsonschema import DRAFT202012
            reg = Registry().with_resources([(s["$id"], Resource.from_contents(s, default_specification=DRAFT202012))
                                             for s in self.schemas.values()])
            self.lib = {k: Draft202012Validator(s, registry=reg) for k, s in self.schemas.items()}
        except ImportError:
            print("note: jsonschema not installed; falling back to required-key checks (pip install jsonschema)", file=sys.stderr)

    def check(self, path: Path, schema: str):
        try:
            data = load_json(path)
        except Exception as e:
            return False, f"not valid JSON: {e}"
        if self.lib:
            errs = sorted(self.lib[schema].iter_errors(data), key=lambda e: list(e.path))
            if errs:
                e = errs[0]
                where = "/".join(str(x) for x in e.path) or "<root>"
                return False, f"{where}: {e.message[:160]}" + (f" (+{len(errs)-1} more)" if len(errs) > 1 else "")
            return True, ""
        missing = [k for k in self.schemas[schema].get("required", []) if k not in data]
        return (False, f"missing required: {', '.join(missing)}") if missing else (True, "")

def artifacts_of(pdir: Path, v: Validators):
    """Yield (relative path, exists, valid, error) for every known artifact slot."""
    out = []
    for f, s in FILE_SCHEMA.items():
        p = pdir / f
        if p.exists():
            ok, err = v.check(p, s); out.append((f, True, ok, err))
        else:
            out.append((f, False, False, ""))
    for d, s in DIR_SCHEMA.items():
        files = sorted((pdir / d).glob("*.json")) if (pdir / d).exists() else []
        if not files:
            out.append((d + "/", False, False, ""))
        for p in files:
            ok, err = v.check(p, s); out.append((f"{d}/{p.name}", True, ok, err))
    return out

# ---------------------------------------------------------------- gates

def gate_state(pdir: Path):
    """Return {gate_id: decision} for recorded gates."""
    st = {}
    for p in sorted((pdir / "gates").glob("*.json")) if (pdir / "gates").exists() else []:
        try:
            g = load_json(p); st[g["gate_id"]] = g["decision"]
        except Exception:
            pass
    return st

def verdict_overall(pdir: Path):
    p = pdir / "verdict.json"
    try:
        return load_json(p)["overall"] if p.exists() else None
    except Exception:
        return None

def required_for(gate: dict, pdir: Path):
    req = list(gate.get("requires", []))
    if gate.get("requires_if_proceed") and verdict_overall(pdir) == "PROCEED":
        req += gate["requires_if_proceed"]
    return req

def check_requirements(gate: dict, pdir: Path, v: Validators):
    """Return (ok, problems[], checked[]) for a gate's required artifacts."""
    problems, checked = [], []
    for r in required_for(gate, pdir):
        if r.endswith("/"):
            d = pdir / r.rstrip("/")
            files = sorted(d.glob("*.json")) if d.exists() else []
            if not files:
                problems.append(f"{r} is empty"); continue
            for p in files:
                ok, err = v.check(p, DIR_SCHEMA[r.rstrip("/")])
                checked.append({"path": f"{r}{p.name}", "valid": ok, "hash": sha256(p), **({"error": err} if err else {})})
                if not ok: problems.append(f"{r}{p.name}: {err}")
        else:
            p = pdir / r
            if not p.exists():
                problems.append(f"{r} missing"); continue
            ok, err = v.check(p, FILE_SCHEMA[r])
            checked.append({"path": r, "valid": ok, "hash": sha256(p), **({"error": err} if err else {})})
            if not ok: problems.append(f"{r}: {err}")
    problems += semantic_checks(gate["id"], pdir)
    return not problems, problems, checked

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

def parse_ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None

def gate_records(pdir: Path):
    """Every readable gate record in the project, in id order."""
    d, out = pdir / "gates", []
    if d.exists():
        for p in sorted(d.glob("*.json")):
            try:
                out.append(load_json(p))
            except Exception:
                pass
    return out

def terminal_state(pdir: Path):
    """The KILL or WAIT record that ended the project, if any. Terminal decisions are final."""
    for r in gate_records(pdir):
        if r.get("decision") in TERMINAL:
            return r
    return None

def open_conditions_blocking(gid: str, pdir: Path):
    """A PASS_WITH_CONDITIONS condition blocks the gate it is due at until closed_at is set."""
    order = gates_def()["order"]
    at = order.index(gid) if gid in order else len(order)
    probs = []
    for r in gate_records(pdir):
        for c in r.get("conditions") or []:
            if c.get("closed_at"):
                continue
            due = c.get("due_gate")
            if due in order and order.index(due) <= at:
                probs.append(f"open condition from {r.get('gate_id')} (due {due}, owner {c.get('owner')}): {c.get('statement')}")
    return probs

def semantic_checks(gid: str, pdir: Path):
    """Cheap cross-artifact checks the schemas cannot express. Returns a list of problems."""
    P = []
    def J(name):
        p = pdir / name
        return load_json(p) if p.exists() else None
    def many(d):
        dd = pdir / d
        return [load_json(p) for p in sorted(dd.glob("*.json"))] if dd.exists() else []
    try:
        if gid == "G-W":
            b = J("brief.json")
            if b:
                for c in b["capabilities"]:
                    if not c.get("measurable") or not (c.get("measure") or "").strip():
                        P.append(f"capability {c['id']} is not measurable (measurable=false or no measure)")
                dims = {d["name"]: d for d in b["bar"]["dimensions"]}
                for n in b["bar"]["in_scope"]:
                    d = dims.get(n)
                    if not d:
                        P.append(f"bar dimension {n} in scope but no threshold written")
                    elif not (d.get("threshold") or "").strip() or not (d.get("measure") or "").strip():
                        P.append(f"bar dimension {n} has no threshold or no measurement method")
                if not b.get("lessons_read"):
                    P.append("memory/LESSONS.md was not consulted (brief.lessons_read is empty)")
                if not (b.get("done_condition", {}).get("test") or []):
                    P.append("done_condition.test is empty; a stranger could not confirm done")

        elif gid == "G-C":
            b, L = J("brief.json"), J("landscape.json")
            if b and L:
                caps = {}
                for row in L.get("search_log", []):
                    e = caps.setdefault(row["capability_id"], {"classes": set(), "cands": set(), "tried": set(), "notes": 0})
                    e["classes"].add(row["source_class"])
                for c in L.get("candidates", []):
                    for f in c.get("fit", []):
                        e = caps.setdefault(f["capability_id"], {"classes": set(), "cands": set(), "tried": set(), "notes": 0})
                        e["cands"].add(c["id"])
                        if c.get("tried"):
                            e["tried"].add(c["id"])
                        if (c.get("trial_notes") or "").strip():
                            e["notes"] += 1
                absences = {a["capability_id"]: a for a in L.get("absence_declarations", [])}
                coverage = {r["capability_id"]: r for r in L.get("coverage", [])}
                fresh_days = b.get("freshness_days", 90)
                for cap in b["capabilities"]:
                    cid, e = cap["id"], caps.get(cap["id"], {"classes": set(), "cands": set(), "tried": set(), "notes": 0})
                    if cid in absences:
                        if len(absences[cid].get("search_log_refs") or []) < 5:
                            P.append(f"{cid}: absence declared without 5 search-log references")
                    else:
                        if len(e["classes"]) < 5:
                            P.append(f"{cid}: {len(e['classes'])}/5 source classes searched (need >=5, or a proven absence)")
                        if len(e["cands"]) < 3:
                            P.append(f"{cid}: {len(e['cands'])} candidates evaluated (need >=3, or a proven absence)")
                        if not e["tried"] and not e["notes"]:
                            P.append(f"{cid}: no candidate was tried and no trial_notes say why not")
                    row = coverage.get(cid)
                    if not row:
                        P.append(f"{cid}: no coverage row (Cartographer did not map the gap)")
                    elif row.get("stale"):
                        P.append(f"{cid}: coverage row is marked stale")
                    elif not row.get("best_fit") and not (row.get("gap") or "").strip():
                        P.append(f"{cid}: coverage row names neither a best_fit nor a precise gap")
                seen = set()
                for c in L.get("candidates", []):
                    for f in c.get("fit", []):
                        if f["capability_id"] in seen:
                            continue
                        seen.add(f["capability_id"])
                        at = parse_ts(c.get("checked_at"))
                        if at and (now_utc() - at).days > fresh_days:
                            P.append(f"candidate {c['id']} checked {(now_utc() - at).days} days ago (freshness_days={fresh_days}); re-check")

        elif gid == "G-K":
            b, vd, bp, pl = J("brief.json"), J("verdict.json"), J("blueprint.json"), J("plan.json")
            co, pr = J("cost.json"), J("prospect.json")
            if b and vd:
                caps = {c["id"] for c in b["capabilities"]}
                decided = {d["capability_id"] for d in vd["decisions"]}
                if caps - decided:
                    P.append(f"capabilities without a verdict: {sorted(caps - decided)}")
                kept = {d["capability_id"] for d in vd["decisions"] if d["verdict"] == "KEEP"}
                if bp:
                    inscope = set(bp["scope"]["build"]) | set(bp["scope"]["bend"])
                    if inscope & kept:
                        P.append(f"blueprint scope contains KEEP capabilities: {sorted(inscope & kept)}")
                if vd["overall"] != "PROCEED":
                    P.append(f"overall verdict is {vd['overall']}: record it with --decision {vd['overall']} after the Scribe writes memory")
                elif co and co.get("within_ceiling") is False and not (vd.get("bar_changes") or (b.get("bar") or {}).get("changes")):
                    P.append("cost totals exceed the budget ceiling with no signed bar_change / ceiling_change")
                if pr and not pr.get("kill_criteria"):
                    P.append("prospect.json has no kill_criteria; the project cannot fail on paper")
                if pl:
                    fails = (pl.get("premortem") or {}).get("failures") or []
                    if len(fails) < 3:
                        P.append(f"premortem names {len(fails)} failure modes; need >=3")
                    for c in pl["crews"]:
                        if len({c["builder"], c["validator"], c["breaker"]}) < 3:
                            P.append(f"crew for {c['work_order']} violates builder != validator != breaker")

        elif gid == "G-D1":
            for wo in many("workorders"):
                if wo["status"] in ("queued", "building", "blocked"):
                    P.append(f"{wo['id']} status {wo['status']}")

        elif gid == "G-D2":
            proofs = {pr["workorder_id"]: pr for pr in many("proofs")}
            for wo in many("workorders"):
                pr = proofs.get(wo["id"])
                if not pr:
                    P.append(f"{wo['id']} has no proof")
                    continue
                if pr["result"] != "PROVEN":
                    P.append(f"{wo['id']} proof result {pr['result']}")
                if pr["validator"] == pr["builder"] or not pr["independence_attestation"]["independent"]:
                    P.append(f"{wo['id']} proof is not independent")

        elif gid == "G-D3":
            for br in many("breaches"):
                for f in br["findings"]:
                    if f["disposition"] == "open" and f["severity"] in ("crit", "high"):
                        P.append(f"open {f['severity']} finding {f['id']} in {br['id']}")
                if br["verdict"] != "HARDENED":
                    P.append(f"{br['id']} verdict {br['verdict']}")

        elif gid == "G-D4":
            r, co = J("release.json"), J("cost.json")
            if r:
                if r["rollback"]["drill_result"] != "pass":
                    P.append("rollback drill did not pass")
                if not r["monitoring_live_before_cutover"]:
                    P.append("monitoring not live before cutover")
                if not r["findings_all_dispositioned"]:
                    P.append("breach findings not all dispositioned")
            if co:
                gates = {x.get("at_gate") for x in co.get("reestimates", [])}
                if "G-D4" not in gates and not (r and r.get("cost_reestimate_at_gate")):
                    P.append("cost was not re-estimated at this gate (PROTOCOL 9.6)")

        elif gid == "G-D5":
            rb, lessons = J("runbook.json"), pdir / "lessons.md"
            if rb:
                if rb["owner"]["name"].strip().lower() in ("", "the team", "team"):
                    P.append("runbook owner must be a person or rota")
                for s in rb["slos"]:
                    if not (s.get("alert") or "").strip():
                        P.append(f"SLO {s['name']} has no alert")
                if not rb.get("reentry_triggers"):
                    P.append("runbook has no re-entry triggers")
            n = len([l for l in lessons.read_text().splitlines() if l.lstrip().startswith(("-", "*", "1", "2", "3", "4", "5", "6", "7", "8", "9"))]) if lessons.exists() else 0
            if n < 3:
                P.append(f"lessons.md has {n} lessons; need >= 3")
            if not (pdir.parent.parent / "memory" / "LESSONS.md").exists():
                P.append("memory/LESSONS.md is missing; lessons cannot compound")
    except (KeyError, TypeError) as e:
        P.append(f"semantic check hit a malformed artifact: {e}")
    P += open_conditions_blocking(gid, pdir)
    return P

# ---------------------------------------------------------------- commands

def cmd_new(a):
    d = PROJECTS / a.slug
    if d.exists(): sys.exit(f"project '{a.slug}' already exists")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", a.slug): sys.exit("slug: lowercase letters, digits, hyphens")
    for sub in ("workorders", "proofs", "breaches", "gates", "messages"):
        (d / sub).mkdir(parents=True)
    shutil.copy(ROOT / "templates" / "project" / "README.md", d / "README.md")
    (d / "wish.json").write_text(json.dumps({"id": a.slug, "text": a.wish, "by": a.by, "at": now()}, indent=2) + "\n")
    print(f"created projects/{a.slug}/  (wish.json written)\n")
    cmd_next(a)

def cmd_validate(a):
    pdir, v = project_dir(a.slug), Validators()
    bad = 0
    for rel, exists, ok, err in artifacts_of(pdir, v):
        if not exists: continue
        print(f"  {'ok ' if ok else 'BAD'}  {rel}" + (f"  -> {err}" if err else ""))
        bad += (not ok)
    print(f"\n{'all present artifacts valid' if not bad else f'{bad} invalid artifact(s)'}")
    return bad

def cmd_status(a):
    pdir, v = project_dir(a.slug), Validators()
    print(f"project: {a.slug}\n  wish: {load_json(pdir / 'wish.json')['text']}\n")
    print("artifacts:")
    for rel, exists, ok, err in artifacts_of(pdir, v):
        mark = "ok " if (exists and ok) else ("BAD" if exists else "-- ")
        print(f"  {mark}  {rel}" + (f"  -> {err}" if err else ""))
    st, gd = gate_state(pdir), gates_def()
    print("\ngates:")
    for g in gd["gates"]:
        print(f"  {st.get(g['id'], '-'):20s} {g['id']} {g['name']}")
    cur = next((g for g in gd["gates"] if st.get(g["id"]) not in PASSING), None)
    t = terminal_state(pdir)
    if t:
        print(f"\nstate: {t['decision']} recorded at {t['gate_id']} on {t['at']} - project ended. "
              f"The Scribe writes lessons and the LEDGER row (S1).")
    else:
        print(f"\ncurrent gate: {cur['id'] + ' ' + cur['name'] if cur else 'none - project is Kept; the Keeper operates it'}")

def cmd_next(a):
    pdir, v, gd = project_dir(a.slug), Validators(), gates_def()
    st = gate_state(pdir)
    steps = workflow_steps()
    ov = verdict_overall(pdir)
    t = terminal_state(pdir)
    if t:
        s = next(x for x in steps if x["id"] == "S1")
        print(f"project ended: {t['decision']} recorded at {t['gate_id']} ({t['at']}).")
        if not (pdir / "lessons.md").exists():
            print_step(s, a.slug, "lessons.md")
        else:
            print("lessons.md is written. No steps remain: re-entry starts a new project (RE_WANT) "
                  "or a scoped canvass (RE_CANVASS); the reasons are in memory.")
        return
    if ov in ("KILL", "WAIT") and st.get("G-K") not in PASSING:
        s = next(x for x in steps if x["id"] == "S1")
        print(f"overall verdict is {ov}. The project {'ends' if ov == 'KILL' else 'sleeps until a tripwire fires'} here.")
        print_step(s, a.slug, "lessons.md"); return
    cur = next((g for g in gd["gates"] if st.get(g["id"]) not in PASSING), None)
    if not cur:
        print("every gate is passed. Operation: the Keeper reviews SLOs weekly, records opex monthly, checks drift quarterly (workflows/wckd.workflow.yaml#operation)."); return
    ok, problems, _ = check_requirements(cur, pdir, v)
    print(f"current gate: {cur['id']} {cur['name']}   (phase {cur['phase']})")
    if ok:
        human = "  --human" if cur["id"] in HUMAN_GATES else ""
        print(f"\nall required artifacts present and valid. Review the criteria in workflows/gates.yaml, then:\n"
              f"  python bin/wckd.py gate {a.slug} {cur['id']} --by \"<name>\"{human}")
        if cur["id"] in HUMAN_GATES: print("  (this gate needs the human's sign-off)")
        return
    print("\nblocking:")
    for p in problems: print(f"  - {p}")
    # map missing/invalid artifacts to the steps that produce them
    wanted = []
    for p in problems:
        base = p.split(":")[0].split(" ")[0]
        base = base.split("/")[0] + "/" if "/" in base and not base.endswith(".json") else base
        wanted.append(base)
    todo, seen = [], set()
    for s in steps:
        if s["phase"] != cur["phase"] and not (cur["phase"] == "D" and s["phase"] == "D"): continue
        outs = " ".join(s.get("out", []))
        if any(w.rstrip("/") in outs for w in wanted) and s["id"] not in seen:
            seen.add(s["id"]); todo.append(s)
    if not todo:  # semantic problem rather than a missing artifact: point at the phase's steps
        todo = [s for s in steps if s["phase"] == cur["phase"]]
    print("\nrun next (in this order; parallel where marked):")
    for s in todo:
        print_step(s, a.slug, None)

def print_step(s, slug, override_out):
    outs = [override_out] if override_out else s.get("out", [])
    par = f"   [parallel with {', '.join(s['parallel_with'])}]" if s.get("parallel_with") else ""
    print(f"\n  step {s['id']} {s['name']} -> agent: {s['agent']}{par}")
    print(f"    hand them:  agents/{s['agent']}.md  (they load SOUL.md, GOALS.md, SKILLS.md first)")
    print(f"    they read:  {', '.join(s.get('in', []))}")
    print(f"    they write: {', '.join(outs)}   (schemas/<artifact>.schema.json)")
    if s.get("notes"): print(f"    note:       {s['notes']}")
    print(f"    then:       python bin/wckd.py validate {slug}")

def cmd_gate(a):
    pdir, v, gd = project_dir(a.slug), Validators(), gates_def()
    gate = next((g for g in gd["gates"] if g["id"] == a.gate), None)
    if not gate: sys.exit(f"unknown gate {a.gate}; one of {gd['order']}")
    st = gate_state(pdir)
    t = terminal_state(pdir)
    if t and t.get("gate_id") != a.gate:
        sys.exit(f"project ended: {t['decision']} recorded at {t['gate_id']} ({t['at']}). "
                 f"Re-entry starts a new project (RE_WANT) or a scoped canvass (RE_CANVASS); record again at {t['gate_id']} only for re-entry.")
    idx = gd["order"].index(a.gate)
    prior = [g for g in gd["order"][:idx] if st.get(g) not in PASSING]
    if prior: sys.exit(f"cannot record {a.gate}: earlier gate(s) not passed: {prior}")
    if a.decision in TERMINAL and not (a.note or "").strip():
        sys.exit(f"--decision {a.decision} needs a --note giving the reason; the Scribe records it in memory")
    if a.gate in HUMAN_GATES and not a.human and a.decision not in TERMINAL and a.decision != "FAIL":
        sys.exit(f"{a.gate} needs the human's sign-off: add --human (you are attesting a human decided)")
    check_this = a.decision not in TERMINAL
    ok, problems, checked = check_requirements(gate, pdir, v)
    if check_this and a.decision != "FAIL" and not ok:
        print("refusing to pass the gate:"); [print(f"  - {p}") for p in problems]; sys.exit(2)
    conds = []
    for c in a.condition or []:
        parts = [x.strip() for x in c.split("|")]
        if len(parts) != 3: sys.exit('each --condition is "statement|owner|due_gate"')
        conds.append({"statement": parts[0], "owner": parts[1], "due_gate": parts[2]})
    if a.decision == "PASS_WITH_CONDITIONS" and not conds: sys.exit("PASS_WITH_CONDITIONS needs at least one --condition")
    rec = {"gate_id": a.gate, "project": a.slug, "at": now(), "reentry": a.gate in st,
           "artifacts_checked": checked,
           "criteria": [{"statement": c, "met": a.decision in PASSING} for c in gate["criteria"]],
           "decision": a.decision, "signoffs": [{"by": a.by, "role": "conductor", "at": now(), "decision": {"PASS": "approve", "PASS_WITH_CONDITIONS": "approve_with_conditions"}.get(a.decision, "reject")}]}
    if conds: rec["conditions"] = conds
    if a.human: rec["human_signoff"] = {"by": a.by, "role": "human", "at": now(), "decision": "approve" if a.decision != "FAIL" else "reject"}
    if a.note: rec["notes"] = a.note
    out = pdir / "gates" / f"{a.gate}.json"
    out.write_text(json.dumps(rec, indent=2) + "\n")
    okv, err = v.check(out, "gate")
    if not okv: out.unlink(); sys.exit(f"gate record did not validate: {err}")
    print(f"recorded {a.gate} {gate['name']}: {a.decision}  -> {out.relative_to(ROOT)}")
    if a.decision in TERMINAL:
        print(f"\nproject ended: {a.decision} at {a.gate}. Next: the Scribe (S1) writes lessons.md and the LEDGER row, "
              f"so the next person does not start blind.")
        return
    if a.decision in PASSING: cmd_next(a)

def cmd_close(a):
    pdir, v = project_dir(a.slug), Validators()
    p = pdir / "gates" / f"{a.gate}.json"
    if not p.exists(): sys.exit(f"no gate record {a.gate} in projects/{a.slug}/gates/")
    rec = load_json(p)
    conds = rec.get("conditions") or []
    if not conds: sys.exit(f"{a.gate} has no conditions to close")
    if not 1 <= a.index <= len(conds): sys.exit(f"condition index must be 1..{len(conds)}")
    c = conds[a.index - 1]
    if c.get("closed_at"): sys.exit(f"condition {a.index} is already closed at {c['closed_at']}")
    c["closed_at"], c["closed_by"] = now(), a.by
    if a.note: c["closed_note"] = a.note
    p.write_text(json.dumps(rec, indent=2) + "\n")
    ok, err = v.check(p, "gate")
    if not ok: sys.exit(f"gate record no longer validates: {err}")
    print(f"closed condition {a.index} on {a.gate}: {c['statement']}  (by {a.by})")
    left = [i + 1 for i, x in enumerate(conds) if not x.get("closed_at")]
    print("open conditions on this gate: " + (", ".join(map(str, left)) if left else "none"))

# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(prog="wckd", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("new"); p.add_argument("slug"); p.add_argument("wish"); p.add_argument("--by", default="human"); p.set_defaults(fn=cmd_new)
    for name, fn in (("status", cmd_status), ("validate", cmd_validate), ("next", cmd_next)):
        p = sp.add_parser(name); p.add_argument("slug"); p.set_defaults(fn=fn)
    p = sp.add_parser("gate"); p.add_argument("slug"); p.add_argument("gate"); p.add_argument("--by", required=True)
    p.add_argument("--human", action="store_true"); p.add_argument("--decision", default="PASS", choices=["PASS", "FAIL", "PASS_WITH_CONDITIONS", "KILL", "WAIT"])
    p.add_argument("--condition", action="append"); p.add_argument("--note"); p.set_defaults(fn=cmd_gate)
    p = sp.add_parser("close"); p.add_argument("slug"); p.add_argument("gate"); p.add_argument("index", type=int)
    p.add_argument("--by", required=True); p.add_argument("--note"); p.set_defaults(fn=cmd_close)
    a = ap.parse_args()
    rc = a.fn(a)
    sys.exit(rc if isinstance(rc, int) else 0)

if __name__ == "__main__":
    main()
