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
  wckd score <slug> [--strict] [--ledger --by NAME]
                                              score GOALS.md G1-G12 from the artifacts;
                                              --ledger appends the row to memory/LEDGER.md (append-only)

The CLI does no domain work. It enforces order, validates artifacts, and records decisions.
Requires: pip install pyyaml jsonschema
"""
import argparse, copy, datetime, hashlib, json, os, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS, WORKFLOWS, PROJECTS = ROOT / "schemas", ROOT / "workflows", ROOT / "projects"

try:
    import yaml
except ImportError:      # the committed machine/*.json makes YAML optional at run time
    yaml = None
if os.environ.get("WCKD_NO_YAML"):   # test the no-dependency path on a machine that has PyYAML
    yaml = None

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
    if yaml and (WORKFLOWS / "gates.yaml").exists():
        return yaml.safe_load((WORKFLOWS / "gates.yaml").read_text())
    mp = machine_protocol() or {}
    if not mp.get("gates"):
        sys.exit("no workflows/gates.yaml and no machine/protocol.json: cannot read the gate definitions")
    return {"order": mp["order"], "gates": mp["gates"]}

def workflow_steps():
    if yaml and (WORKFLOWS / "wckd.workflow.yaml").exists():
        phases = yaml.safe_load((WORKFLOWS / "wckd.workflow.yaml").read_text())["phases"]
    else:
        phases = (machine_protocol() or {}).get("phases") or []
        if not phases:
            sys.exit("no workflows/wckd.workflow.yaml and no machine/protocol.json: cannot read the pipeline")
    return [s | {"phase": p["id"]} for p in phases for s in p["steps"]]

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
            if r in FILE_SCHEMA:
                ok, err = v.check(p, FILE_SCHEMA[r])
            else:      # free-form document required by gates.yaml (lessons.md): presence and substance
                ok, err = (True, "") if p.read_text().strip() else (False, "document is empty")
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

def manifest_section(name):
    return (machine_protocol() or {}).get(name) or {}


def realm_of(pdir: Path):
    p = pdir / "brief.json"
    if not p.exists():
        return "digital"
    return load_json(p).get("realm") or "digital"


def campaign_rules(realm):
    camp = (manifest_section("campaigns").get("campaigns") or {})
    hit = camp.get(realm) or camp.get("hybrid") or {}
    return hit.get("required", [])


def physical_rule(*path, default=None):
    node = manifest_section("physical")
    for k in path:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def realm_gate_checks(gid: str, pdir: Path, T: dict):
    """Realm-conditional obligations: adversarial coverage at G-D3, and the physical column where it applies."""
    P = []

    def J(n):
        p = pdir / n
        return load_json(p) if p.exists() else None

    realm = realm_of(pdir)

    if gid == "G-D3":
        breaches = []
        d = pdir / "breaches"
        if d.exists():
            for p in sorted(d.glob("*.json")):
                try:
                    breaches.append(load_json(p))
                except Exception:
                    pass
        ran = set()
        for br in breaches:
            for c in br.get("campaigns", []):
                if c.get("ran") or (c.get("why_not") or "").strip():
                    ran.add(c.get("category"))
        need = campaign_rules(realm)
        missing = [c for c in need if c not in ran]
        if missing:
            P.append(f"{realm}: no adversarial campaign recorded for {', '.join(missing)} (workflows/campaigns.yaml)")
        if breaches and not any((br.get("cost_compared_to_ledger") or "").strip() for br in breaches):
            P.append("no cost campaign is compared against cost.run_monthly")
        return P

    if realm not in ("physical", "hybrid"):
        return P

    if gid == "G-K":
        bp, co = J("blueprint.json"), J("cost.json")
        if bp:
            spec = bp.get("physical_spec") or {}
            if not (spec.get("certification_targets") or []):
                P.append("physical: blueprint.physical_spec.certification_targets is empty; name the markets and marks")
            if not (spec.get("serviceability") or "").strip():
                P.append("physical: serviceability is unstated; how is a sensor or battery replaced?")
            need_haz = physical_rule("hazard_analysis", "min_entries", default=3)
            haz = bp.get("hazard_analysis") or []
            if len(haz) < need_haz:
                P.append(f"physical: hazard_analysis has {len(haz)} entries; need >={need_haz}")
            for h in haz:
                if not (h.get("control") or "").strip():
                    P.append(f"physical: hazard {h.get('id')} has no control (put it in open_risks if it has none)")
        if co:
            unit = co.get("unit")
            if not unit:
                P.append("physical: cost.unit is missing (BOM, assembly, test, packaging, shipping, warranty)")
            else:
                if not unit.get("total_per_unit"):
                    P.append("physical: cost.unit.total_per_unit is zero or missing")
                if not (unit.get("moq_notes") or "").strip():
                    P.append("physical: cost.unit.moq_notes is empty; minimum order quantities are unpriced")
                if not (unit.get("lead_time_notes") or "").strip():
                    P.append("physical: cost.unit.lead_time_notes is empty")
            if not ((co.get("build") or {}).get("certification") or []):
                P.append("physical: build.certification is empty; certification is NRE, price it")

    elif gid == "G-D4":
        rel = J("release.json")
        if rel:
            hw = rel.get("hardware") or {}
            if not hw:
                P.append("physical: release.hardware is missing (pilot batch, handoff, QC, serials, recall)")
            else:
                min_units = physical_rule("pilot_batch", "min_units", default=T.get("pilot_batch_min", 5))
                if int(hw.get("pilot_batch_size") or 0) < int(min_units):
                    P.append(f"physical: pilot_batch_size is {hw.get('pilot_batch_size')}; need >={min_units}")
                for k in ("qc_sampling_plan", "serial_tracking", "logistics"):
                    if not (hw.get(k) or "").strip():
                        P.append(f"physical: release.hardware.{k} is empty")
                rr = hw.get("repair_recall_path") or {}
                if rr.get("rehearsal_result") != "pass":
                    P.append("physical: repair/recall path was not rehearsed to a pass on real units")

    elif gid == "G-D5":
        rb = J("runbook.json")
        if rb:
            if not rb.get("spares_and_consumables"):
                P.append("physical: runbook.spares_and_consumables is empty")
            cadence = " ".join((t.get("task") or "").lower() for t in rb.get("maintenance_cadence", []))
            if "calibrat" not in cadence:
                P.append("physical: maintenance cadence has no recalibration task")
    return P


def semantic_checks(gid: str, pdir: Path):
    """Cheap cross-artifact checks the schemas cannot express. Returns a list of problems."""
    P = []
    T = tolerances()
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
                fresh_days = b.get("freshness_days", T["freshness_days"])
                for cap in b["capabilities"]:
                    cid, e = cap["id"], caps.get(cap["id"], {"classes": set(), "cands": set(), "tried": set(), "notes": 0})
                    if cid in absences:
                        if len(absences[cid].get("search_log_refs") or []) < T["min_source_classes"]:
                            P.append(f"{cid}: absence declared without {T['min_source_classes']} search-log references")
                    else:
                        if len(e["classes"]) < T["min_source_classes"]:
                            P.append(f"{cid}: {len(e['classes'])}/{T['min_source_classes']} source classes searched (need >={T['min_source_classes']}, or a proven absence)")
                        if len(e["cands"]) < T["min_candidates"]:
                            P.append(f"{cid}: {len(e['cands'])} candidates evaluated (need >={T['min_candidates']}, or a proven absence)")
                        if not e["tried"] and not e["notes"]:
                            P.append(f"{cid}: no candidate was tried and no trial_notes say why not")
                    row = coverage.get(cid)
                    if not row:
                        P.append(f"{cid}: no coverage row (Cartographer did not map the gap)")
                    elif row.get("stale"):
                        P.append(f"{cid}: coverage row is marked stale")
                    elif not row.get("best_fit") and not (row.get("gap") or "").strip():
                        P.append(f"{cid}: coverage row names neither a best_fit nor a precise gap")
                if not L.get("graveyard") and not (L.get("graveyard_note") or "").strip():
                    P.append("graveyard is empty and no graveyard_note says the space has no history")
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
                if vd.get("decisions"):
                    r = sum(1 for d in vd["decisions"] if d["verdict"] in ("KEEP", "BEND")) / len(vd["decisions"])
                    if abs(r - vd.get("reuse_ratio", -1)) > 0.02:
                        P.append(f"reuse_ratio {vd.get('reuse_ratio')} does not match the verdicts ({r:.2f}); G1 is scored on the arithmetic")
                if co and co.get("within_ceiling") is False and not (vd.get("bar_changes") or (b.get("bar") or {}).get("changes")):
                    P.append("cost totals exceed the budget ceiling with no signed bar_change / ceiling_change")
                if pr and not pr.get("kill_criteria"):
                    P.append("prospect.json has no kill_criteria; the project cannot fail on paper")
                if pl:
                    fails = (pl.get("premortem") or {}).get("failures") or []
                    if len(fails) < T["min_premortem"]:
                        P.append(f"premortem names {len(fails)} failure modes; need >={T['min_premortem']}")
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
            if n < T["min_lessons"]:
                P.append(f"lessons.md has {n} lessons; need >= {T['min_lessons']}")
            if not (pdir.parent.parent / "memory" / "LESSONS.md").exists():
                P.append("memory/LESSONS.md is missing; lessons cannot compound")
    except (KeyError, TypeError) as e:
        P.append(f"semantic check hit a malformed artifact: {e}")
    P += realm_gate_checks(gid, pdir, T)
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
    pdir = project_dir(a.slug)
    ctx = current_context(pdir)
    if ctx["terminal"]:
        t = ctx["terminal"]
        print(f"project ended: {t['decision']} recorded at {t['gate_id']} ({t['at']}).")
        if not (pdir / "lessons.md").exists():
            print_step(ctx["steps"][0], a.slug, "lessons.md")
        else:
            print("lessons.md is written. No steps remain: re-entry starts a new project (RE_WANT) "
                  "or a scoped canvass (RE_CANVASS); the reasons are in memory.")
        return
    if ctx["verdict_terminal"]:
        ov = ctx["verdict_terminal"]
        print(f"overall verdict is {ov}. The project {'ends' if ov == 'KILL' else 'sleeps until a tripwire fires'} here.")
        print_step(ctx["steps"][0], a.slug, "lessons.md"); return
    cur = ctx["gate"]
    if not cur:
        print("every gate is passed. Operation: the Keeper reviews SLOs weekly, records opex monthly, "
              "checks drift quarterly (workflows/wckd.workflow.yaml#operation)."); return
    print(f"current gate: {cur['id']} {cur['name']}   (phase {cur['phase']})")
    if ctx["ok"]:
        human = "  --human" if cur["id"] in HUMAN_GATES else ""
        print(f"\nall required artifacts present and valid. Review the criteria in workflows/gates.yaml, then:\n"
              f"  python bin/wckd.py gate {a.slug} {cur['id']} --by \"<name>\"{human}")
        if cur["id"] in HUMAN_GATES: print("  (this gate needs the human's sign-off)")
        return
    print("\nblocking:")
    for p in ctx["problems"]: print(f"  - {p}")
    print("\nrun next (in this order; parallel where marked):")
    for s in ctx["steps"]:
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

# ---------------------------------------------------------------- goals

GOAL_MARK = {"pass": "✓", "fail": "✗", "na": "n/a", "unknown": "—"}
GOAL_IDS = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"]


def count_lessons(p: Path):
    """Lines that look like lessons: a bullet or a numbered item."""
    if not p.exists():
        return 0
    n = 0
    for line in p.read_text().splitlines():
        s = line.lstrip()
        if s.startswith(("-", "*")) or re.match(r"^\d+[.)]\s", s):
            n += 1
    return n


def compute_goals(pdir: Path):
    """Score GOALS.md G1-G12 from the artifacts present. Unmeasurable yet is '-' or 'n/a', never a pass."""
    def J(n):
        p = pdir / n
        return load_json(p) if p.exists() else None
    brief, land, verd, cost, plan, rel, runb = (J(n) for n in ("brief.json", "landscape.json", "verdict.json",
                                                               "cost.json", "plan.json", "release.json", "runbook.json"))
    T = tolerances()
    out = []

    def add(gid, status, detail):
        out.append({"goal": gid, "status": status, "detail": detail})

    # G1 reuse before build
    if verd and verd.get("decisions"):
        vs = [d["verdict"] for d in verd["decisions"]]
        ratio = sum(1 for v in vs if v in ("KEEP", "BEND")) / len(vs)
        add("G1", "pass" if ratio >= T["reuse_ratio_min"] else "fail",
            f"reuse {ratio:.2f} (target >={T['reuse_ratio_min']:.2f})")
    else:
        add("G1", "unknown", "no verdict yet")

    # G2 nothing built blind
    if brief and land:
        caps = [c["id"] for c in brief["capabilities"]]
        absences = {a["capability_id"] for a in land.get("absence_declarations", [])}
        classes, cands = {}, {}
        for r in land.get("search_log", []):
            classes.setdefault(r["capability_id"], set()).add(r["source_class"])
        for c in land.get("candidates", []):
            for f in c.get("fit", []):
                cands.setdefault(f["capability_id"], set()).add(c["id"])
        thin = [c for c in caps if c not in absences
                and (len(classes.get(c, ())) < T["min_source_classes"] or len(cands.get(c, ())) < T["min_candidates"])]
        lo_c = min((len(classes.get(c, ())) for c in caps), default=0)
        lo_n = min((len(cands.get(c, ())) for c in caps), default=0)
        add("G2", "pass" if not thin else "fail",
            f"min {lo_c} source classes / {lo_n} candidates per capability (target {T['min_source_classes']}/{T['min_candidates']})")
    else:
        add("G2", "unknown", "no landscape yet")

    # G3 honest kills, at portfolio level
    overalls = []
    for p in sorted(PROJECTS.glob("*/verdict.json")):
        try:
            overalls.append(load_json(p).get("overall"))
        except Exception:
            pass
    if len(overalls) >= 5:
        share = sum(1 for o in overalls if o in ("KILL", "WAIT")) / len(overalls)
        add("G3", "pass" if 0.15 <= share <= 0.40 else "fail", f"{share:.2f} of {len(overalls)} projects killed or waited (0.15-0.40)")
    else:
        add("G3", "na", f"portfolio band needs >=5 projects, have {len(overalls)}")

    # G4 priced truth: run estimate vs actual
    if cost and runb and runb.get("opex_actual"):
        est = (cost.get("run_monthly") or {}).get("total")
        actuals = [a.get("amount") for a in runb["opex_actual"] if isinstance(a.get("amount"), (int, float))]
        if isinstance(est, (int, float)) and est and actuals:
            act = actuals[-1]
            add("G4", "pass" if abs(act - est) <= 0.15 * est else "fail",
                f"run {est:.2f} estimate vs {act:.2f} actual (target +-15%)")
        else:
            add("G4", "unknown", "cost or opex_actual not numeric")
    else:
        add("G4", "unknown", "no opex actuals yet; scored 90 days after Kept")

    # G5 proven, not promised: crit/high findings that exist at all
    findings = []
    bdir = pdir / "breaches"
    if bdir.exists():
        for p in sorted(bdir.glob("*.json")):
            try:
                findings += load_json(p).get("findings", [])
            except Exception:
                pass
    if findings:
        esc = [f for f in findings if f.get("severity") in ("crit", "high")]
        add("G5", "pass" if not esc else "fail", f"{len(esc)} crit/high findings of {len(findings)}")
    else:
        add("G5", "unknown", "no breach record yet")

    # G6 broken before shipped
    if rel:
        add("G6", "pass" if rel.get("findings_all_dispositioned") else "fail", "every finding dispositioned before Shipped")
    else:
        add("G6", "unknown", "not shipped")

    # G7 reversible delivery
    if rel:
        drill = (rel.get("rollback") or {}).get("drill_result", "missing")
        add("G7", "pass" if drill == "pass" else "fail", f"rollback drill: {drill}")
    else:
        add("G7", "unknown", "not shipped")

    # G8 kept, not abandoned
    if runb:
        owner = ((runb.get("owner") or {}).get("name") or "").strip()
        slos_ok = all((s.get("alert") or "").strip() for s in runb.get("slos", []))
        budget = (runb.get("opex_budget_monthly") or {}).get("amount")
        acts = [a.get("amount") for a in runb.get("opex_actual", []) if isinstance(a.get("amount"), (int, float))]
        within = (not acts or not budget) or max(acts) <= budget * 1.10
        ok = owner and owner.lower() not in ("the team", "team") and slos_ok and within
        add("G8", "pass" if ok else "fail", f"owner '{owner}', {len(runb.get('slos', []))} SLOs with alerts, opex within budget+10%")
    else:
        add("G8", "unknown", "no runbook")

    # G9 memory compounds
    lessons = pdir / "lessons.md"
    if lessons.exists():
        n = count_lessons(lessons)
        add("G9", "pass" if n >= T["min_lessons"] else "fail", f"{n} lessons written (target >={T['min_lessons']})")
    else:
        add("G9", "unknown", "no lessons.md yet")

    # G10 human in control
    recs = {r["gate_id"]: r for r in gate_records(pdir)}
    passed_human = [g for g in ("G-W", "G-K", "G-D4") if (recs.get(g) or {}).get("decision") in PASSING]
    if passed_human:
        missing = [g for g in passed_human if not recs[g].get("human_signoff")]
        add("G10", "pass" if not missing else "fail", f"human sign-off recorded at {', '.join(passed_human)}")
    else:
        add("G10", "unknown", "no human-veto gate passed yet")

    # G11 the Bar holds
    changes = []
    if brief:
        changes += (brief.get("bar") or {}).get("changes") or []
    if verd:
        changes += verd.get("bar_changes") or []
    unsig = [c for c in changes if len(c.get("signoffs") or []) < 2]
    add("G11", "pass" if (len(changes) <= 2 and not unsig) else "fail",
        f"{len(changes)} bar change(s), {len(unsig)} unsigned (target <=2, all signed)")

    # G12 tried, not read
    if brief and land:
        tried = {}
        for c in land.get("candidates", []):
            if c.get("tried"):
                for f in c.get("fit", []):
                    tried.setdefault(f["capability_id"], set()).add(c["id"])
        caps = [c["id"] for c in brief["capabilities"]]
        missing = [c for c in caps if not tried.get(c)]
        add("G12", "pass" if not missing else "fail", f"{len(caps) - len(missing)}/{len(caps)} capabilities have a candidate actually tried")
    else:
        add("G12", "unknown", "no landscape yet")
    return out


def ledger_row(slug, pdir: Path, rows, gate_state_map):
    def J(n):
        p = pdir / n
        return load_json(p) if p.exists() else None
    b, v, co = J("brief.json"), J("verdict.json"), J("cost.json")
    wish = ((b or {}).get("restated") or (b or {}).get("wish") or "").replace("|", "/")
    if len(wish) > 60:
        wish = wish[:57] + "..."
    overall = (v or {}).get("overall", "—")
    ratio = f"{(v or {}).get('reuse_ratio', 0):.2f}" if v else "—"
    if co:
        cur, cls = co.get("currency", "USD"), co.get("confidence_class", "rom")
        build = f"{(co.get('build') or {}).get('total', '—')} {cur} → — ({cls})"
        run = f"{(co.get('run_monthly') or {}).get('total', '—')} {cur} → — ({cls})"
    else:
        build = run = "—"
    recs = {r["gate_id"]: r for r in gate_records(pdir)}
    dates = [(recs.get(g) or {}).get("at", "—")[:10] for g in ("G-W", "G-K", "G-D4", "G-D5")]
    marks = " | ".join(GOAL_MARK[r["status"]] for r in rows)
    lessons = "lessons.md" if (pdir / "lessons.md").exists() else "—"
    return (f"| {slug} | {wish} | {overall} | {ratio} | {build} | {run} | "
            + " | ".join(dates) + f" | {marks} | {lessons} |")


def cmd_score(a):
    pdir = project_dir(a.slug)
    rows = compute_goals(pdir)
    print(f"project: {a.slug}\n")
    width = max(len(r["detail"]) for r in rows)
    for r in rows:
        print(f"  {r['goal']:4s} {GOAL_MARK[r['status']]:5s} {r['detail']}")
    fails = [r["goal"] for r in rows if r["status"] == "fail"]
    unknown = [r["goal"] for r in rows if r["status"] != "pass"]
    print(f"\n{len(rows) - len(unknown)}/{len(rows)} goals pass" + (f"; failing: {', '.join(fails)}" if fails else "")
          + (f"; not yet measurable: {', '.join(g for g in unknown if g not in fails)}" if len(unknown) > len(fails) else ""))
    if a.ledger:
        if not a.by:
            sys.exit("--ledger needs --by NAME (who is writing the row)")
        led = ROOT / "memory" / "LEDGER.md"
        text = led.read_text()
        if re.search(rf"^\| {re.escape(a.slug)} \|", text, re.M):
            sys.exit(f"memory/LEDGER.md already has a row for {a.slug}; the ledger is append-only, corrections are new rows")
        row = ledger_row(a.slug, pdir, rows, gate_state(pdir))
        led.write_text(text.rstrip("\n") + "\n" + row + f"\n<!-- row by {a.by} at {now()} -->\n")
        print(f"\nappended to memory/LEDGER.md (by {a.by}):\n{row}")
    if a.strict and fails:
        sys.exit(1)

# ---------------------------------------------------------------- manifest / portability

MACHINE = ROOT / "machine"
VERSION = "1.1.0"
TOLERANCES = {"min_source_classes": 5, "min_candidates": 3, "min_lessons": 3, "min_premortem": 3,
              "reuse_ratio_min": 0.60, "freshness_days": 90, "opex_tripwire_pct": 10,
              "min_tried_per_capability": 1, "pilot_batch_min": 5}

_MACHINE_CACHE = {}


def machine_protocol():
    """The compiled protocol manifest. Generated by `wckd manifest`, consumed by any runtime."""
    if "p" not in _MACHINE_CACHE:
        p = MACHINE / "protocol.json"
        _MACHINE_CACHE["p"] = load_json(p) if p.exists() else None
    return _MACHINE_CACHE["p"]


def tolerances():
    """Numbers the protocol binds itself to, so every implementation gates at the same place."""
    t = dict(TOLERANCES)
    mp = machine_protocol() or {}
    t.update(mp.get("tolerances") or {})
    return t


def frontmatter(p: Path):
    """Parse an agent file: `---` frontmatter + body. Uses PyYAML when present, a small fallback otherwise."""
    text = p.read_text()
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    raw, body = parts[1], parts[2]
    if yaml:
        meta = yaml.safe_load(raw) or {}
    else:
        meta = {}
        for line in raw.splitlines():
            if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            meta[k.strip()] = _mini_scalar(v)
    return meta, body.lstrip("\n")


def _mini_scalar(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        items, cur, q = [], "", None
        for ch in v[1:-1]:
            if q:
                if ch == q:
                    q = None
                else:
                    cur += ch
            elif ch in "\"'":
                q = ch
            elif ch == ",":
                items.append(cur.strip()); cur = ""
            else:
                cur += ch
        if cur.strip():
            items.append(cur.strip())
        return [i for i in items if i]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def _roles_manifest():
    roles = []
    for p in sorted((ROOT / "agents").glob("*.md")):
        meta, body = frontmatter(p)
        roles.append({
            "id": meta.get("name", p.stem), "phase": meta.get("phase"), "description": meta.get("description"),
            "consumes": meta.get("consumes", []), "produces": meta.get("produces", []),
            "skills": meta.get("skills", []), "tools": meta.get("tools", []),
            "may_not": meta.get("may_not", []), "hands_off_to": meta.get("hands_off_to"),
            "prompt_file": f"agents/{p.name}", "prompt": body.strip(),
        })
    return roles


def _rewrite_refs(node, common_defs, local_defs, out_defs, scope="local"):
    """Inline external refs so one artifact validates from one file, in any language."""
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k == "$ref" and isinstance(v, str):
                if v.startswith("common.schema.json#/$defs/"):
                    name = v.rsplit("/", 1)[-1]; key = "common_" + name
                    node[k] = "#/$defs/" + key
                    if key not in out_defs:
                        out_defs[key] = {}
                        out_defs[key].update(_rewrite_refs(copy.deepcopy(common_defs[name]), common_defs, local_defs, out_defs, "common"))
                elif v.startswith("#/$defs/"):
                    name = v.rsplit("/", 1)[-1]
                    # inside a copied common definition, a bare local ref still means a common definition
                    key = ("common_" if scope == "common" else "local_") + name
                    node[k] = "#/$defs/" + key
                    if key not in out_defs:
                        out_defs[key] = {}
                        src = common_defs[name] if scope == "common" else local_defs[name]
                        out_defs[key].update(_rewrite_refs(copy.deepcopy(src), common_defs, local_defs, out_defs, scope))
            else:
                _rewrite_refs(v, common_defs, local_defs, out_defs, scope)
    elif isinstance(node, list):
        for i, x in enumerate(node):
            _rewrite_refs(x, common_defs, local_defs, out_defs, scope)
    return node


def _standalone(schema, commons):
    out = copy.deepcopy(schema)
    out.pop("$id", None)
    local_defs = out.pop("$defs", {}) or {}
    out_defs = {}
    out = _rewrite_refs(out, commons, local_defs, out_defs)
    if out_defs:
        out["$defs"] = out_defs
    return out


def build_manifest():
    """Return {relative path: file text} for every machine-readable protocol file."""
    if yaml is None:
        sys.exit("regenerating the manifest needs PyYAML: pip install pyyaml "
                 "(the committed machine/*.json works without it)")
    wf = yaml.safe_load((WORKFLOWS / "wckd.workflow.yaml").read_text())
    gd = yaml.safe_load((WORKFLOWS / "gates.yaml").read_text())
    loops = yaml.safe_load((WORKFLOWS / "loops.yaml").read_text())
    camp = yaml.safe_load((WORKFLOWS / "campaigns.yaml").read_text()) if (WORKFLOWS / "campaigns.yaml").exists() else {}
    phys = yaml.safe_load((WORKFLOWS / "physical.yaml").read_text()) if (WORKFLOWS / "physical.yaml").exists() else {}
    common = load_json(SCHEMAS / "common.schema.json")

    def enum(defname):
        return common["$defs"][defname].get("enum", [])

    phases = []
    for ph in wf["phases"]:
        phases.append({"id": ph["id"], "name": ph["name"], "question": ph.get("question"),
                       "entry": ph.get("entry"), "time_box": ph.get("time_box"), "gate": ph.get("gate"),
                       "steps": [{k: v for k, v in s.items() if k in
                                  ("id", "name", "agent", "skills", "in", "out", "notes", "parallel_with",
                                   "after", "with", "per", "independence", "gate", "loop", "on_overall_verdict")}
                                 for s in ph["steps"]]})

    protocol = {
        "protocol": wf.get("protocol", "WCKD"),
        "protocol_version": wf.get("version"),
        "tool_version": VERSION,
        "pronounced": wf.get("pronounced", "wicked"),
        "prime_directive": (wf.get("prime_directive") or "").strip(),
        "phases": phases,
        "order": gd["order"],
        "gates": [{k: v for k, v in g.items() if k in
                   ("id", "name", "phase", "requires", "requires_if_proceed", "criteria", "signoff",
                    "human_signoff", "on_fail")} for g in gd["gates"]],
        "loops": loops,
        "roles": _roles_manifest(),
        "vocab": {
            "verdicts": ["KEEP", "BEND", "BUILD", "WAIT", "KILL"],
            "overall": ["PROCEED", "WAIT", "KILL"],
            "decisions": ["PASS", "FAIL", "PASS_WITH_CONDITIONS", "KILL", "WAIT"],
            "terminal_decisions": ["KILL", "WAIT"],
            "bar_dimensions": enum("bar_dimension"), "source_classes": enum("source_class"),
            "evidence_kinds": enum("evidence_kind"), "severities": enum("severity"),
            "realms": enum("realm"), "priorities": enum("priority"), "roles": enum("role"),
            "confidence_classes": {k: v for k, v in
                                   (("rom", "+-50%"), ("budgetary", "+-25%"), ("definitive", "+-10%"))},
        },
        "artifacts": {**{f: s for f, s in FILE_SCHEMA.items()}, **{d: s for d, s in DIR_SCHEMA.items()}},
        "human_veto_gates": sorted(HUMAN_GATES),
        "tolerances": dict(TOLERANCES),
        "campaigns": camp,
        "physical": phys,
    }

    files = {"machine/protocol.json": json.dumps(protocol, indent=2) + "\n"}

    agent_manifest = {"generated_from": "agents/*.md", "roles": protocol["roles"]}
    files["machine/agents.json"] = json.dumps(agent_manifest, indent=2) + "\n"

    # one self-contained schema per artifact: external refs inlined, no registry needed
    standalones = {}
    for p in sorted(SCHEMAS.glob("*.schema.json")):
        name = p.stem.replace(".schema", "")
        if name == "common":
            continue
        standalones[name] = _standalone(load_json(p), common["$defs"])
        files[f"machine/schemas/{name}.standalone.json"] = json.dumps(standalones[name], indent=2) + "\n"

    # a single bundle for validators that want one file
    bundle = {"$schema": "https://json-schema.org/draft/2020-12/schema",
              "$id": "https://wckd.protocol/machine/schemas.bundle.json",
              "title": "WCKD artifact schemas, self-contained",
              "artifacts": standalones}
    files["machine/schemas.bundle.json"] = json.dumps(bundle, indent=2) + "\n"
    return files


def cmd_manifest(a):
    files = build_manifest()
    if a.check:
        drift = []
        for rel, content in files.items():
            p = ROOT / rel
            if not p.exists() or p.read_text() != content:
                drift.append(rel)
        if drift:
            print("machine/ is stale; run: wckd manifest\n  " + "\n  ".join(drift))
            sys.exit(1)
        print(f"machine/ up to date ({len(files)} files)")
        return
    for rel, content in files.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        print("wrote", rel)

# ---------------------------------------------------------------- handoff (any agent, any runtime)

def todo_for(cur, problems, steps):
    """Map gate problems back to the steps that produce the missing or invalid artifacts."""
    wanted = []
    for p in problems:
        base = p.split(":")[0].split(" ")[0]
        base = base.split("/")[0] + "/" if "/" in base and not base.endswith(".json") else base
        wanted.append(base)
    todo, seen = [], set()
    for s in steps:
        if s["phase"] != cur["phase"] and not (cur["phase"] == "D" and s["phase"] == "D"):
            continue
        outs = " ".join(s.get("out", []))
        if any(w.rstrip("/") in outs for w in wanted) and s["id"] not in seen:
            seen.add(s["id"]); todo.append(s)
    if not todo:
        todo = [s for s in steps if s["phase"] == cur["phase"]]
    return todo


def current_context(pdir: Path):
    """What to do next: the open gate, its problems, and the steps that close them."""
    gd, st, steps = gates_def(), gate_state(pdir), workflow_steps()
    t = terminal_state(pdir)
    s1 = [s for s in steps if s["id"] == "S1"]
    if t:
        return {"gate": None, "ok": False, "problems": [], "steps": s1, "terminal": t, "verdict_terminal": None}
    ov = verdict_overall(pdir)
    if ov in ("KILL", "WAIT") and st.get("G-K") not in PASSING:
        return {"gate": None, "ok": False, "problems": [], "steps": s1, "terminal": None, "verdict_terminal": ov}
    cur = next((g for g in gd["gates"] if st.get(g["id"]) not in PASSING), None)
    if not cur:
        return {"gate": None, "ok": True, "problems": [], "steps": [], "terminal": None, "verdict_terminal": None}
    ok, problems, _ = check_requirements(cur, pdir, Validators())
    return {"gate": cur, "ok": ok, "problems": problems,
            "steps": [] if ok else todo_for(cur, problems, steps),
            "terminal": None, "verdict_terminal": None}


def _artifact_schema_name(out: str):
    out = out.replace("#", "")
    if out in FILE_SCHEMA:
        return FILE_SCHEMA[out]
    head = out.split("/")[0] + "/"
    if head in DIR_SCHEMA:
        return DIR_SCHEMA[head]
    return None


def gate_for_step(step):
    gd = gates_def()
    if step.get("gate"):
        return next((g for g in gd["gates"] if g["id"] == step["gate"]), None)
    return next((g for g in gd["gates"] if g["phase"] == step["phase"]), None)


def _role_by_id(rid):
    for r in (machine_protocol() or {}).get("roles", []):
        if r["id"] == rid:
            return r
    p = ROOT / "agents" / f"{rid}.md"
    if p.exists():
        meta, body = frontmatter(p)
        return {"id": rid, "description": meta.get("description"), "prompt": body.strip(),
                "skills": meta.get("skills", []), "tools": meta.get("tools", []),
                "may_not": meta.get("may_not", []), "produces": meta.get("produces", []),
                "consumes": meta.get("consumes", [])}
    return None


def build_handoff(pdir: Path, slug: str, step: dict, gate: dict, inline: bool):
    role = _role_by_id(step["agent"]) or {"id": step["agent"], "prompt": "", "skills": [], "tools": [], "may_not": []}
    outs = [o for o in step.get("out", []) if not o.startswith("the deliverable")]
    primary = outs[0] if outs else ""
    schema_name = _artifact_schema_name(primary)
    schema = None
    if schema_name:
        sp = MACHINE / "schemas" / f"{schema_name}.standalone.json"
        schema = load_json(sp) if sp.exists() else load_json(SCHEMAS / f"{schema_name}.schema.json")

    soul = (ROOT / "SOUL.md").read_text()
    gate_lines = ""
    if gate:
        gate_lines = (f"Open gate: {gate['id']} {gate['name']} (phase {gate['phase']}).\n"
                      "It passes only when all of these are true:\n" +
                      "".join(f"  - {c}\n" for c in gate.get("criteria", [])) +
                      f"Human sign-off required: {'yes' if gate.get('human_signoff') else 'no'}.\n")

    inputs = []
    for rel in step.get("in", []):
        rel = rel.replace("../../", "")
        p = (pdir / rel.split("#")[0]) if not rel.startswith("memory/") else (ROOT / rel.split("#")[0])
        if not p.exists():
            p = ROOT / rel.split("#")[0]
        item = {"path": rel, "exists": p.exists()}
        if p.exists() and inline and p.stat().st_size < 400_000:
            item["content"] = p.read_text()
        inputs.append(item)

    system = "\n\n".join([
        "# WCKD — who you are",
        soul,
        f"# Your role: {role['id']}",
        role.get("description") or "",
        role.get("prompt") or "",
        "## You may not", "\n".join(f"- {m}" for m in (role.get("may_not") or [])) or "- (nothing listed)",
        "## Skills you own", ", ".join(role.get("skills") or []) or "(none listed)",
    ])

    user = "\n".join([
        f"# Step {step['id']} {step['name']} — project {slug}",
        gate_lines,
        f"Write exactly this artifact: {', '.join(outs) or '(the deliverable)'}",
        f"Output path: projects/{slug}/{primary}" if primary else "",
        f"Schema: machine/schemas/{schema_name}.standalone.json" if schema_name else "",
        "## Inputs",
        *[f"- {i['path']} ({'present' if i['exists'] else 'MISSING'})" for i in inputs],
        "\n## Rules for this turn",
        "1. Stay inside the role. Do not do another role's job, even if it looks quick.",
        "2. Write the artifact as JSON that validates against the schema. No prose around it.",
        "3. Every claim that crosses a boundary carries evidence {kind, locator, summary, captured_at, captured_by, confidence}.",
        "4. State what you did not check. Silence about scope is a lie by omission.",
        "5. Do not mark anything proven, hardened or shipped that you did not produce.",
        step.get("notes") or "",
        "## Schema (JSON Schema 2020-12)",
        "```json", json.dumps(schema, indent=2) if schema else "{}", "```",
    ]).strip()

    md = (f"# WCKD handoff — {slug} — step {step['id']} {step['name']}\n\n"
          f"Role: **{step['agent']}**  ·  phase {step['phase']}  ·  gate {gate['id'] if gate else '—'}\n\n"
          f"Give the block below to any model or agent as its system prompt, then the second block as the task.\n\n"
          f"## System\n\n{system}\n\n## Task\n\n{user}\n")
    return {"project": slug, "step": step["id"], "name": step["name"], "role": step["agent"],
            "phase": step["phase"], "gate": gate["id"] if gate else None,
            "output": f"projects/{slug}/{primary}" if primary else None,
            "schema": f"machine/schemas/{schema_name}.standalone.json" if schema_name else None,
            "system": system, "user": user, "markdown": md, "inputs": inputs}


def cmd_handoff(a):
    pdir = project_dir(a.slug)
    ctx = current_context(pdir)
    if a.step:
        steps = workflow_steps()
        hit = [s for s in steps if s["id"] == a.step]
        if not hit:
            sys.exit(f"unknown step {a.step}; steps: {', '.join(s['id'] for s in steps)}")
        step = hit[0]
        gate = gate_for_step(step) or {}
        steps_to_emit = [step]
    else:
        if ctx["terminal"]:
            sys.exit(f"project ended ({ctx['terminal']['decision']} at {ctx['terminal']['gate_id']}): nothing to hand off")
        if not ctx["gate"]:
            sys.exit("every gate is passed: nothing to hand off; the Keeper operates it now")
        steps_to_emit, gate = ctx["steps"], ctx["gate"]
    if a.role:
        steps_to_emit = [s for s in steps_to_emit if s["agent"] == a.role]
        if not steps_to_emit:
            sys.exit(f"role {a.role} has no open step in this gate; open steps: "
                     f"{', '.join(s['agent'] for s in ctx['steps'])}")

    out_chunks = []
    for step in steps_to_emit:
        h = build_handoff(pdir, a.slug, step, gate, a.inline)
        out_chunks.append(json.dumps(h, indent=2) if a.format == "json" else h["markdown"])
    text = "\n\n<!-- next step -->\n\n".join(out_chunks)
    if a.out:
        p = Path(a.out) if a.out.startswith("/") else pdir / a.out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        print(f"wrote {p}  ({len(text)} chars, {len(steps_to_emit)} step(s))")
    else:
        print(text)

# ---------------------------------------------------------------- transports: http + run + conformance

def capture(fn, ns):
    """Run a CLI command and return what it printed (used by the HTTP and MCP transports)."""
    import contextlib, io as _io
    buf = _io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            fn(ns)
    except SystemExit as e:
        if e.code not in (0, None):
            raise RuntimeError(buf.getvalue().strip() or f"exit {e.code}")
        return buf.getvalue().strip()
    return buf.getvalue().strip()


def api_projects():
    out = []
    for d in sorted(PROJECTS.glob("*/")):
        if not (d / "wish.json").exists():
            continue
        try:
            wish = load_json(d / "wish.json").get("text", "")
        except Exception:
            wish = ""
        st, t = gate_state(d), terminal_state(d)
        out.append({"slug": d.name, "wish": wish, "gates": st, "state": (t or {}).get("decision", "open"),
                    "current_gate": next((g for g in gates_def()["order"] if st.get(g) not in PASSING), None)})
    return out


def api_write_artifact(slug, rel, content):
    pdir = (PROJECTS / slug).resolve()
    target = (pdir / rel).resolve()
    if pdir not in target.parents:
        raise RuntimeError(f"path escapes the project: {rel}")
    text = content if isinstance(content, str) else json.dumps(content, indent=2)
    if target.suffix == ".json":
        data = json.loads(text)
        name = FILE_SCHEMA.get(rel) or DIR_SCHEMA.get(rel.split("/")[0] + "/")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        if name:
            ok, err = Validators().check(tmp, name)
            if not ok:
                tmp.unlink()
                raise RuntimeError(f"{rel} does not validate against {name}: {err}")
        tmp.replace(target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return target


def cmd_serve(a):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse, parse_qs

    class H(BaseHTTPRequestHandler):
        server_version = f"wckd/{VERSION}"

        def _json(self, code, obj):
            body = json.dumps(obj, indent=2).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authed(self):
            if not a.token:
                return True
            ok = self.headers.get("Authorization") == f"Bearer {a.token}"
            if not ok:
                self._json(401, {"error": "unauthorized"})
            return ok

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            return json.loads(self.rfile.read(n).decode() or "{}")

        def do_GET(self):
            if not self._authed():
                return
            u = urlparse(self.path)
            q = parse_qs(u.query)
            parts = [p for p in u.path.split("/") if p]
            try:
                if parts == ["health"]:
                    return self._json(200, {"ok": True, "protocol": "WCKD", "tool_version": VERSION})
                if parts == ["protocol"]:
                    return self._json(200, machine_protocol() or {})
                if parts == ["projects"]:
                    return self._json(200, api_projects())
                if len(parts) >= 2 and parts[0] == "projects":
                    slug = parts[1]
                    pdir = PROJECTS / slug
                    if not pdir.exists():
                        return self._json(404, {"error": f"no project {slug}"})
                    if len(parts) == 2:
                        return self._json(200, {"slug": slug, "status": capture(cmd_status, argparse.Namespace(slug=slug)),
                                                "gates": gate_state(pdir)})
                    if parts[2] == "next":
                        return self._json(200, {"slug": slug, "next": capture(cmd_next, argparse.Namespace(slug=slug))})
                    if parts[2] == "score":
                        return self._json(200, {"slug": slug, "score": capture(cmd_score, argparse.Namespace(
                            slug=slug, ledger=False, by=None, strict=False))})
                    if parts[2] == "handoff":
                        fmt = (q.get("format") or ["md"])[0]
                        text = capture(cmd_handoff, argparse.Namespace(
                            slug=slug, step=(q.get("step") or [None])[0], role=(q.get("role") or [None])[0],
                            inline=bool(q.get("inline")), out=None, format=fmt))
                        if fmt == "json":
                            return self._json(200, json.loads(text))
                        return self._json(200, {"markdown": text})
                    if parts[2] == "artifacts":
                        rel = "/".join(parts[3:])
                        p = (pdir / rel).resolve()
                        if (pdir.resolve() not in p.parents) or not p.exists():
                            return self._json(404, {"error": f"no artifact {rel}"})
                        if p.suffix == ".json":
                            return self._json(200, load_json(p))
                        return self._json(200, {"text": p.read_text()})
                return self._json(404, {"error": "unknown route"})
            except Exception as e:
                return self._json(400, {"error": str(e)})

        def do_POST(self):
            if not self._authed():
                return
            u = urlparse(self.path)
            parts = [p for p in u.path.split("/") if p]
            try:
                body = self._body()
                if parts == ["projects"]:
                    out = capture(cmd_new, argparse.Namespace(slug=body["slug"], wish=body["wish"],
                                                              by=body.get("by", "api")))
                    return self._json(201, {"created": body["slug"], "next": out})
                if len(parts) >= 4 and parts[0] == "projects" and parts[2] == "artifacts":
                    rel = "/".join(parts[3:])
                    p = api_write_artifact(parts[1], rel, body.get("content"))
                    return self._json(200, {"wrote": rel, "bytes": p.stat().st_size})
                if len(parts) >= 4 and parts[0] == "projects" and parts[2] == "gates":
                    gate = parts[3]
                    out = capture(cmd_gate, argparse.Namespace(
                        slug=parts[1], gate=gate, by=body.get("by", "api"),
                        human=bool(body.get("human")), decision=body.get("decision", "PASS"),
                        condition=body.get("conditions"), note=body.get("note")))
                    return self._json(200, {"gate": gate, "output": out})
                return self._json(404, {"error": "unknown route"})
            except KeyError as e:
                return self._json(400, {"error": f"missing field {e}"})
            except Exception as e:
                return self._json(400, {"error": str(e)})

        def log_message(self, *args):
            if not a.quiet:
                super().log_message(*args)

    srv = ThreadingHTTPServer((a.bind, a.port), H)
    print(f"wckd {VERSION} serving {ROOT} on http://{a.bind}:{a.port}"
          f"{' (token required)' if a.token else ''}\n"
          "GET /health /protocol /projects /projects/<slug>/{next,score,handoff,artifacts/*}\n"
          "POST /projects /projects/<slug>/artifacts/<path> /projects/<slug>/gates/<gate>")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


def _artifact_snapshot(pdir: Path):
    h = hashlib.sha256()
    for p in sorted(pdir.rglob("*")):
        if p.is_file() and ".turns" not in p.parts:
            h.update(str(p.relative_to(pdir)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def cmd_run(a):
    """Drive the protocol against any agent command: prompt in on stdin, artifact written by the agent."""
    pdir = project_dir(a.slug)
    turns_dir = pdir / ".turns"
    turns_dir.mkdir(exist_ok=True)
    if not a.agent:
        sys.exit("--agent is required: the command that plays a role (it reads the prompt on stdin). "
                 "Use --dry-run to see the prompts instead.")
    stale = 0
    for turn in range(1, a.max_turns + 1):
        ctx = current_context(pdir)
        if ctx["terminal"]:
            print(f"[run] project ended: {ctx['terminal']['decision']} at {ctx['terminal']['gate_id']}"); return
        if not ctx["gate"]:
            print("[run] every gate is passed; the Keeper operates it now."); return
        gate = ctx["gate"]
        if ctx["ok"]:
            if gate["id"] in HUMAN_GATES:
                print(f"[run] {gate['id']} {gate['name']} is ready and needs a human. Stop.\n"
                      f"      wckd gate {a.slug} {gate['id']} --by \"<your name>\" --human")
                return
            out = capture(cmd_gate, argparse.Namespace(slug=a.slug, gate=gate["id"], by=a.by, human=False,
                                                       decision="PASS", condition=None, note="recorded by wckd run"))
            print(f"[run] {gate['id']} {gate['name']} recorded automatically")
            continue
        if not ctx["steps"]:
            print(f"[run] {gate['id']} is blocked but no step claims the missing artifacts:\n  " +
                  "\n  ".join(ctx["problems"])); return
        step = ctx["steps"][0]
        h = build_handoff(pdir, a.slug, step, gate, inline=True)
        pf = turns_dir / f"{turn:02d}-{step['id']}-{step['agent']}.md"
        pf.write_text(h["markdown"])
        print(f"[run] turn {turn}: step {step['id']} {step['name']} as {step['agent']} -> {pf}")
        before = _artifact_snapshot(pdir)
        env = dict(os.environ, WCKD_ROOT=str(ROOT), WCKD_SLUG=a.slug, WCKD_STEP=step["id"],
                   WCKD_ROLE=step["agent"], WCKD_GATE=gate["id"], WCKD_PROMPT=str(pf))
        import subprocess
        r = subprocess.run(f"cd {_shq(str(pdir))} && {a.agent} < {_shq(str(pf))}", shell=True, env=env).returncode
        if r != 0:
            print(f"[run] agent exited {r}; stopping. Read the agent's output above, fix the role prompt, rerun.")
            return
        if _artifact_snapshot(pdir) == before:
            stale += 1
            print(f"[run] no artifact changed this turn ({stale}/{a.max_stale})")
            if stale >= a.max_stale:
                print("[run] stopping: the agent is not producing artifacts. Check the handoff prompt and the schema.")
                return
        else:
            stale = 0
    print(f"[run] stopped after {a.max_turns} turns; run again to continue")


def _shq(s):
    return "'" + str(s).replace("'", "'\\''") + "'"


def cmd_conformance(a):
    """Language-independent conformance: valid artifacts must pass, mutants must fail, standalone schemas only."""
    from jsonschema import Draft202012Validator
    cases, bad = [], 0
    examples = {"wish": "examples/air-quality-monitor/wish.json",
                "brief": "examples/air-quality-monitor/brief.json",
                "landscape": "examples/air-quality-monitor/landscape.json",
                "verdict": "examples/air-quality-monitor/verdict.json"}
    for name, path in examples.items():
        sp = MACHINE / "schemas" / f"{name}.standalone.json"
        schema = load_json(sp) if sp.exists() else load_json(SCHEMAS / f"{name}.schema.json")
        v = Draft202012Validator(schema)
        data = load_json(ROOT / path)
        errs = list(v.iter_errors(data))
        cases.append((f"{name}: shipped example", not errs, errs[0].message[:100] if errs else ""))
        for mutant_name, mutate in _mutants(name, data):
            try:
                m = mutate(json.loads(json.dumps(data)))
            except Exception:
                continue
            errs = list(v.iter_errors(m))
            cases.append((f"{name}: {mutant_name} must fail", bool(errs), "accepted an invalid artifact"))
    for name, ok, detail in cases:
        bad += not ok
        print(f"  {'ok ' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if (detail and not ok) else ""))
    print(f"\n{len(cases) - bad}/{len(cases)} conformance cases pass"
          + ("" if not bad else f" — {bad} failing"))
    return 1 if bad else 0


def _mutants(name, data):
    """Cheap structural mutants: every schema must reject them."""
    def drop_required():
        def f(d):
            key = json.loads((SCHEMAS / f"{name}.schema.json").read_text())["required"][0]
            d.pop(key, None)
            return d
        return ("missing required key", f)

    def bad_type():
        def f(d):
            for k, v in d.items():
                if isinstance(v, str):
                    d[k] = 12345
                    break
            return d
        return ("wrong type", f)

    yield drop_required()
    yield bad_type()
    yield ("extra property", lambda d: {**d, "__not_a_wckd_field": True})

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
    p = sp.add_parser("score"); p.add_argument("slug"); p.add_argument("--ledger", action="store_true")
    p.add_argument("--by"); p.add_argument("--strict", action="store_true"); p.set_defaults(fn=cmd_score)
    p = sp.add_parser("handoff"); p.add_argument("slug"); p.add_argument("--step"); p.add_argument("--role")
    p.add_argument("--inline", action="store_true"); p.add_argument("--out"); p.add_argument("--format", default="md", choices=["md", "json"])
    p.set_defaults(fn=cmd_handoff)
    p = sp.add_parser("manifest"); p.add_argument("--check", action="store_true"); p.set_defaults(fn=cmd_manifest)
    p = sp.add_parser("serve"); p.add_argument("--port", type=int, default=8787)
    p.add_argument("--bind", default="127.0.0.1"); p.add_argument("--token"); p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_serve)
    p = sp.add_parser("run"); p.add_argument("slug"); p.add_argument("--agent")
    p.add_argument("--by", default="wckd-run"); p.add_argument("--max-turns", type=int, default=12)
    p.add_argument("--max-stale", type=int, default=2); p.set_defaults(fn=cmd_run)
    p = sp.add_parser("conformance"); p.set_defaults(fn=cmd_conformance)
    a = ap.parse_args()
    try:
        rc = a.fn(a)
    except BrokenPipeError:      # `wckd status | head` must not traceback
        try:
            sys.stdout.close()
        except Exception:
            pass
        os._exit(0)
    sys.exit(rc if isinstance(rc, int) else 0)

if __name__ == "__main__":
    main()
