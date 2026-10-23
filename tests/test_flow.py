#!/usr/bin/env python3
"""End-to-end: a synthetic want through all eight gates, scored and written to the ledger.

Runs against a throwaway copy of the protocol tree (bin, schemas, workflows, memory, templates), so the
repository's own projects/ and memory/ are never touched. The artifact contents here are test fixtures for a
fictional digital want: no external claim is made in them.
"""
import json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AT = "2026-10-23T00:00:00+00:00"


def ev(by="scout"):
    return [{"kind": "url", "locator": "https://example.org/x", "summary": "fixture evidence",
             "captured_at": AT, "captured_by": by, "confidence": 0.8, "grade": "found"}]


def prov(by):
    return {"produced_by": by, "produced_at": AT}


class Flow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / "wckd"
        cls.root.mkdir()
        for d in ("bin", "schemas", "workflows", "templates", "memory"):
            shutil.copytree(ROOT / d, cls.root / d)
        (cls.root / "projects").mkdir()
        cls.cli = [sys.executable, str(cls.root / "bin" / "wckd.py")]
        cls.run_ok("new", "hello", "A CLI that prints hello")
        cls.p = cls.root / "projects" / "hello"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def run_ok(cls, *args, expect=0):
        r = subprocess.run(cls.cli + list(args), capture_output=True, text=True)
        if r.returncode != expect:
            raise AssertionError(f"{' '.join(args)} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
        return r.stdout + r.stderr

    def w(self, name, data):
        p = self.p / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2))

    # ---------------------------------------------------------------- artifacts

    def test_01_want_and_canvass(self):
        self.w("brief.json", {
            "id": "hello", "wish": "A CLI that prints hello", "restated": "A CLI that prints hello",
            "realm": "digital", "freshness_days": 90,
            "capabilities": [{"id": "C1", "statement": "a user can run a command and see hello",
                              "priority": "must", "measurable": True, "measure": "exit 0 and stdout == hello"}],
            "constraints": [{"kind": "time", "statement": "one day"}],
            "non_goals": ["localisation"], "horizon": {"first_value": "same day", "lifetime": "1 year"},
            "budget_ceiling": {"build": {"amount": 100, "currency": "USD", "confidence_class": "budgetary"},
                               "run_monthly": {"amount": 0, "currency": "USD", "confidence_class": "definitive"}},
            "bar": {"in_scope": ["correctness"], "set_by": {"by": "barkeeper", "role": "barkeeper", "at": AT, "decision": "approve"},
                    "dimensions": [{"name": "correctness", "threshold": "stdout is exactly hello",
                                    "measure": "shell capture of stdout", "why": "that is the whole want"}]},
            "done_condition": {"statement": "running the command prints hello", "test": ["run it", "compare stdout"]},
            "lessons_read": ["memory/LESSONS.md#protocol"], "questions_asked": [], "provenance": prov("listener")})
        self.run_ok("gate", "hello", "G-W", "--by", "Galahad", "--human")

        cands = []
        for i, kind in enumerate(["open_source", "commercial_cots", "internal_prior",
                                  "academic_patent_standard", "community_issue_tracker"], start=1):
            cands.append({"id": f"cand{i}", "name": f"existing hello tool {i}", "kind": kind,
                          "locator": f"https://example.org/{i}", "checked_at": AT, "tried": i == 1,
                          "trial_notes": "ran it once" if i == 1 else "read-only inside the time box",
                          "works": ["prints hello"], "doesnt": ["not installable here" if i > 1 else "none"],
                          "fit": [{"capability_id": "C1", "score": 0.9 if i == 1 else 0.3, "meets_bar": i == 1}],
                          "evidence": ev()})
        self.w("landscape.json", {
            "id": "hello-land", "brief_id": "hello", "time_box": "10 min",
            "lessons_read": ["memory/LESSONS.md#protocol"],
            "search_log": [{"capability_id": "C1", "source_class": c["kind"], "query": "hello cli",
                            "tool": "web_search", "at": AT, "results_count": 3, "kept": [c["id"]]} for c in cands],
            "candidates": cands,
            "graveyard": [{"id": "grave1", "name": "shell alias", "what_it_tried": "alias hello=echo hello",
                           "why_it_died": "not portable", "lesson": "install a script", "evidence": ev()}],
            "coverage": [{"capability_id": "C1", "source_classes_searched": [c["kind"] for c in cands],
                          "candidates_evaluated": [c["id"] for c in cands],
                          "best_fit": {"candidate_id": "cand1", "score": 0.9}, "gap": ""}],
            "absence_declarations": [], "summary": "one candidate meets the Bar; adopt it",
            "provenance": prov("cartographer")})
        self.run_ok("gate", "hello", "G-C", "--by", "conductor")

    def test_02_judge(self):
        self.w("verdict.json", {
            "id": "hello-v", "brief_id": "hello", "landscape_id": "hello-land",
            "decisions": [{"capability_id": "C1", "verdict": "KEEP", "chosen_candidate": "cand1",
                           "rationale": "cand1 meets the Bar measured; nothing to build", "keep_cost_note": "free",
                           "evidence": ev("judge"), "confidence": 0.9}],
            "overall": "PROCEED", "overall_rationale": "reuse 1.0; adopt cand1",
            "reuse_ratio": 1.0,
            "signoffs": [{"by": "judge", "role": "judge", "at": AT, "decision": "approve"}],
            "provenance": prov("judge")})
        self.w("blueprint.json", {"id": "hello-bp", "verdict_id": "hello-v", "scope": {"build": [], "bend": []},
                                  "components": [{"id": "c-int", "name": "adoption glue", "realm": "digital",
                                                  "responsibility": "put cand1 on PATH and smoke-test it",
                                                  "serves": ["C1"],
                                                  "kept_dependencies": [{"candidate_id": "cand1", "version": "1.0"}],
                                                  "interfaces": [{"with": "cand1", "contract": "executable name hello",
                                                                  "failure_behavior": "exit non-zero",
                                                                  "versioning": "pinned", "documented_at": "README"}]}],
                                  "adrs": [], "reversibility_plan": [{"component_id": "c-int", "how_to_back_out": "delete the script"}],
                                  "non_goals": [], "open_risks": [], "provenance": prov("architect")})
        self.w("cost.json", {
            "id": "hello-cost", "blueprint_id": "hello-bp", "currency": "USD", "confidence_class": "budgetary",
            "build": {"people": [], "tools": [], "materials": [], "prototypes": [], "nre": [], "certification": [], "total": 0},
            "run_monthly": {"digital": [], "physical": [], "people": [], "total": 0},
            "exit": {"migration": [], "decommission": [], "disposal": [],
                     "kept_dependency_exits": [{"item": "delete the adopted script", "amount": 0, "confidence_class": "definitive"}],
                     "total": 0},
            "not_doing": {"monthly": 0, "basis": "nothing to operate"},
            "keep_costs": [], "horizons": {"m1": 0, "m12": 0, "m36": 0}, "within_ceiling": True,
            "assumptions": ["zero-cost adoption"], "sensitivity": [], "provenance": prov("quartermaster")})
        self.w("prospect.json", {
            "id": "hello-pr", "brief_id": "hello",
            "demand": {"signals": ["one user asked"], "users_addressable": "1", "users_year1": "1"},
            "competition": [], "differentiation": "none needed; it exists",
            "roi": {"investment": {"amount": 0, "currency": "USD", "confidence_class": "definitive"},
                 "value_year1": {"amount": 1, "currency": "USD", "confidence_class": "rom"},
                 "payback_months": "0-1"},
            "regulatory": [], "timing": {"why_now": "trivial"},
            "risks": [], "kill_criteria": ["nobody runs it for a week"],
            "tripwires": [{"signal": "no use in 30 days", "by": "2026-11-23", "then": "KILL"}],
            "recommendation": {"decision": "PROCEED", "confidence": 0.9, "rationale": "meets the Bar with no build"},
            "provenance": prov("prospector")})
        self.w("plan.json", {
            "id": "hello-plan", "blueprint_id": "hello-bp",
            "milestones": [{"id": "M1", "name": "adopted", "exit_criteria": ["cand1 prints hello"], "due": "2026-10-24"}],
            "work_orders": ["WO-001"], "critical_path": ["WO-001"],
            "crews": [{"work_order": "WO-001", "builder": "builder-1", "validator": "validator-1", "breaker": "breaker-1"}],
            "premortem": {"run_at": AT, "with": ["breaker"], "failures": [
                {"story": "the script is not on PATH", "mitigation_or_tripwire": "install path checked"},
                {"story": "shell quoting breaks", "mitigation_or_tripwire": "tested in bash and sh"},
                {"story": "someone expects colour output", "mitigation_or_tripwire": "declared a non-goal"}]},
            "schedule_confidence": 0.9, "provenance": prov("planner")})
        self.w("workorders/WO-001.json", {
            "id": "WO-001", "plan_id": "hello-plan", "component_id": "cand1", "capability_ids": ["C1"],
            "realm": "digital", "spec": "install cand1 as the hello command",
            "acceptance": [{"criterion": "prints hello and exits 0", "bar_dimension": "correctness"}],
            "inputs": [], "deliverables": ["/usr/local/bin/hello"], "depends_on": [],
            "assigned_to": {"builder": "builder-1", "validator": "validator-1", "breaker": "breaker-1"},
            "status": "queued", "build_log": [], "provenance": prov("planner")})
        out = self.run_ok("gate", "hello", "G-K", "--by", "Galahad", "--human")
        self.assertIn("G-K Judged: PASS", out)

    def test_03_deliver(self):
        wo = json.loads((self.p / "workorders" / "WO-001.json").read_text())
        wo["status"] = "built"
        wo["build_log"] = [{"at": AT, "by": "builder-1", "did": "installed the script", "saw": "hello prints hello"}]
        self.w("workorders/WO-001.json", wo)
        self.run_ok("gate", "hello", "G-D1", "--by", "conductor")

        self.w("proofs/WO-001.proof.json", {
            "id": "WO-001.proof", "workorder_id": "WO-001", "validator": "validator-1", "builder": "builder-1",
            "independence_attestation": {"independent": True, "note": "different agent, clean container"},
            "environment": {"description": "fresh container", "clean": True},
            "tests_written_before_reading_implementation": True,
            "tests": [{"name": "prints hello", "bar_dimension": "correctness", "method": "run hello",
                       "expected": "hello", "observed": "hello", "pass": True}],
            "measurements": [], "reproduced_from_clean": True, "undocumented_steps": [],
            "result": "PROVEN", "defects": [], "evidence": ev("validator"), "provenance": prov("validator")})
        self.run_ok("gate", "hello", "G-D2", "--by", "conductor")

        self.w("breaches/BR-001.json", {
            "id": "BR-001", "target": {"kind": "workorder", "ref": "WO-001"}, "breaker": "breaker-1",
            "independence_attestation": {"independent": True, "note": "did not build or prove"},
            "campaigns": [{"category": "security", "ran": True, "method": "shell injection via args",
                           "outcome": "no injection path; argument is not interpolated"},
                          {"category": "cost", "ran": True, "method": "run it 1000 times", "outcome": "0 USD"}],
            "findings": [], "cost_compared_to_ledger": "run cost 0 vs 0", "verdict": "HARDENED",
            "provenance": prov("breaker")})
        self.run_ok("gate", "hello", "G-D3", "--by", "conductor")

        cost = json.loads((self.p / "cost.json").read_text())
        cost["reestimates"] = [{"at_gate": "G-D4", "at": AT, "build_total": 0, "run_monthly_total": 0,
                                "variance_within_class": True, "note": "nothing to buy"}]
        self.w("cost.json", cost)
        self.w("release.json", {
            "id": "hello-rel", "plan_id": "hello-plan", "strategy": "staged",
            "environments": ["local"], "steps": [{"order": 1, "action": "install the script",
                                                  "criteria_to_proceed": ["hello prints hello"], "signs": ["shipper"]}],
            "go_no_go": {"criteria": ["proof PROVEN", "no open crit"], "signoffs": [
                {"by": "shipper", "role": "shipper", "at": AT, "decision": "approve"}]},
            "rollback": {"method": "delete the script", "drill_at": AT, "drill_result": "pass",
                         "drill_time": "20 s", "max_acceptable_time": "2 min"},
            "monitoring_live_before_cutover": True, "findings_all_dispositioned": True,
            "cost_reestimate_at_gate": "G-D4", "outcome": {"status": "shipped"},
            "provenance": prov("shipper")})
        self.w("runbook.json", {
            "id": "hello-rb", "release_id": "hello-rel", "owner": {"name": "Galahad", "kind": "person"},
            "slos": [{"name": "prints hello", "bar_dimension": "correctness", "target": "100%",
                      "measure": "daily smoke run", "alert": "alert-1"}],
            "alerts": [{"id": "alert-1", "condition": "smoke run fails", "route": "telegram", "owner": "Galahad"}],
            "oncall": {"rota": "weekly", "escalation": ["human", "conductor"]},
            "maintenance_cadence": [{"task": "review smoke results", "every": "week", "owner": "Galahad"}],
            "patching_policy": "rebuild from the pinned script",
            "kept_dependencies_watched": [{"candidate_id": "cand1", "version": "1.0", "watch": "release notes"}],
            "opex_budget_monthly": {"amount": 0, "currency": "USD", "confidence_class": "definitive"},
            "opex_actual": [{"month": "2026-10", "amount": 0, "evidence": ev("keeper")}],
            "drift_checks": [], "reentry_triggers": [{"condition": "Bar no longer met for 2 periods", "action": "RE_WANT"},
                                                       {"condition": "a newer candidate appears", "action": "RE_CANVASS"},
                                                       {"condition": "opex exceeds budget by 10% two months running", "action": "RE_JUDGE"}],
            "end_of_life": {"when": "2027-10", "how": "delete the script", "tell_users": "changelog"},
            "provenance": prov("keeper")})
        out = self.run_ok("gate", "hello", "G-D4", "--by", "Galahad", "--human")
        self.assertIn("G-D4 Shipped: PASS", out)

        (self.p / "lessons.md").write_text(
            "# Lessons\n\n- adopting an existing tool beat building one - *(verdict.json)*\n"
            "- the trial found the install path issue before the build did - *(landscape.json)*\n"
            "- a 20 s rollback drill was enough because the deliverable is a single script - *(release.json)*\n")
        out = self.run_ok("gate", "hello", "G-D5", "--by", "conductor")
        self.assertIn("G-D5 Kept: PASS", out)

    def test_04_score_and_ledger(self):
        out = self.run_ok("score", "hello")
        for goal in ("G1", "G2", "G6", "G7", "G8", "G9", "G10", "G11", "G12"):
            self.assertRegex(out, rf"\n  {goal}\s+[✓—n/a]")
        self.assertNotIn("failing", out, out)
        out = self.run_ok("score", "hello", "--ledger", "--by", "Scribe")
        ledger = (self.root / "memory" / "LEDGER.md").read_text()
        self.assertIn("| hello |", ledger)
        self.assertIn("| PROCEED |", ledger)
        # append-only: a second write is refused
        r = subprocess.run(self.cli + ["score", "hello", "--ledger", "--by", "Scribe"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("append-only", r.stdout + r.stderr)


class LedgerIsAppendOnly(unittest.TestCase):
    def test_repo_ledger_untouched_by_tests(self):
        self.assertTrue((ROOT / "memory" / "LEDGER.md").exists())
        self.assertNotIn("| hello |", (ROOT / "memory" / "LEDGER.md").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
