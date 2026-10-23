#!/usr/bin/env python3
"""Semantic checks for the WCKD gate rules the JSON schemas cannot express.

Run: python3 -m unittest discover -s tests -v   (from the wckd root)
"""
import copy, json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
import importlib.util
spec = importlib.util.spec_from_file_location("wckd", ROOT / "bin" / "wckd.py")
wckd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wckd)

EX = ROOT / "examples" / "air-quality-monitor"


def J(p):
    return json.loads(Path(p).read_text())


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pdir = Path(self._tmp.name) / "proj"
        (self.pdir / "gates").mkdir(parents=True)
        self.brief = J(EX / "brief.json")
        self.land = J(EX / "landscape.json")

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, data):
        (self.pdir / name).write_text(json.dumps(data))

    def gate(self, gid, **kw):
        rec = {"gate_id": gid, "project": "proj", "at": "2026-10-23T00:00:00+00:00",
               "artifacts_checked": [], "criteria": [], "decision": "PASS",
               "signoffs": [{"by": "conductor", "role": "conductor", "at": "2026-10-23T00:00:00+00:00", "decision": "approve"}],
               "human_signoff": {"by": "human", "role": "human", "at": "2026-10-23T00:00:00+00:00", "decision": "approve"}}
        rec.update(kw)
        (self.pdir / "gates" / f"{gid}.json").write_text(json.dumps(rec))


class TestWant(Base):
    def test_unmeasurable_capability_blocks(self):
        self.brief["capabilities"][0]["measurable"] = False
        self.write("brief.json", self.brief)
        self.assertTrue(any("not measurable" in p for p in wckd.semantic_checks("G-W", self.pdir)))

    def test_bar_dimension_without_measure_blocks(self):
        self.brief["bar"]["dimensions"][0].pop("measure")
        self.write("brief.json", self.brief)
        self.assertTrue(any("no threshold or no measurement method" in p
                            for p in wckd.semantic_checks("G-W", self.pdir)))

    def test_lessons_unread_blocks(self):
        self.brief["lessons_read"] = []
        self.write("brief.json", self.brief)
        self.assertTrue(any("LESSONS.md was not consulted" in p for p in wckd.semantic_checks("G-W", self.pdir)))


class TestCanvass(Base):
    def test_empty_graveyard_needs_a_note(self):
        self.write("brief.json", self.brief)
        land = copy.deepcopy(self.land)
        land["graveyard"] = []
        self.write("landscape.json", land)
        self.assertTrue(any("graveyard is empty" in p for p in wckd.semantic_checks("G-C", self.pdir)))
        land["graveyard_note"] = "no prior attempts found in any of the seven source classes"
        self.write("landscape.json", land)
        self.assertFalse(any("graveyard is empty" in p for p in wckd.semantic_checks("G-C", self.pdir)))

    def test_thin_canvass_is_refused(self):
        self.write("brief.json", self.brief)
        land = copy.deepcopy(self.land)
        land["search_log"] = land["search_log"][:1]
        land["candidates"] = land["candidates"][:1]
        land["candidates"][0]["tried"] = False
        land["candidates"][0].pop("trial_notes", None)
        land["graveyard"], land["coverage"], land["absence_declarations"] = [], [], []
        self.write("landscape.json", land)
        problems = wckd.semantic_checks("G-C", self.pdir)
        self.assertTrue(any("source classes searched" in p for p in problems))
        self.assertTrue(any("candidates evaluated" in p for p in problems))
        self.assertTrue(any("no coverage row" in p for p in problems))

    def test_absence_declaration_overrides_candidate_count(self):
        self.write("brief.json", self.brief)
        land = copy.deepcopy(self.land)
        land["absence_declarations"] = [{"capability_id": "C5", "search_log_refs": [0, 1, 2, 3, 4],
                                         "statement": "no calibrated enclosure exists"}]
        self.write("landscape.json", land)
        self.assertFalse(any("C5: 1 candidates evaluated" in p for p in wckd.semantic_checks("G-C", self.pdir)))

    def test_short_absence_declaration_blocks(self):
        self.write("brief.json", self.brief)
        land = copy.deepcopy(self.land)
        land["absence_declarations"] = [{"capability_id": "C5", "search_log_refs": [0, 1], "statement": "nothing"}]
        self.write("landscape.json", land)
        self.assertTrue(any("without 5 search-log references" in p for p in wckd.semantic_checks("G-C", self.pdir)))

    def test_stale_coverage_blocks(self):
        self.write("brief.json", self.brief)
        land = copy.deepcopy(self.land)
        land["coverage"][0]["stale"] = True
        self.write("landscape.json", land)
        self.assertTrue(any("marked stale" in p for p in wckd.semantic_checks("G-C", self.pdir)))


class TestVerdict(Base):
    def _k_artifacts(self):
        verdict = {"id": "v", "brief_id": "b", "landscape_id": "l", "overall": "PROCEED",
                   "overall_rationale": "r", "reuse_ratio": 1.0,
                   "decisions": [{"capability_id": c["id"], "verdict": "KEEP", "chosen_candidate": "cand-ha",
                                  "rationale": "fits", "confidence": 0.8,
                                  "evidence": [{"kind": "url", "locator": "x", "summary": "s", "captured_at": "2026-10-23T00:00:00+00:00",
                                                "captured_by": "judge", "confidence": 0.8}]} for c in self.brief["capabilities"]],
                   "signoffs": [{"by": "judge", "role": "judge", "at": "2026-10-23T00:00:00+00:00", "decision": "approve"}],
                   "provenance": {"produced_by": "judge", "produced_at": "2026-10-23T00:00:00+00:00"}}
        blueprint = {"id": "bp", "verdict_id": "v", "scope": {"build": [], "bend": []}, "components": [], "adrs": [],
                     "reversibility_plan": [], "non_goals": [], "open_risks": [],
                     "physical_spec": {"certification_targets": ["FCC Part 15 B", "CE"],
                                       "serviceability": "sensor door, no factory return"},
                     "hazard_analysis": [
                         {"id": "H1", "hazard": "mains contact", "severity": "high", "likelihood": 2, "control": "isolated PSU"},
                         {"id": "H2", "hazard": "sensor false low", "severity": "med", "likelihood": 3, "control": "weekly calibration check"},
                         {"id": "H3", "hazard": "dust on inlet", "severity": "low", "likelihood": 4, "control": "filter and cleaning cadence"}],
                     "provenance": {"produced_by": "architect", "produced_at": "2026-10-23T00:00:00+00:00"}}
        cost = {"id": "c", "within_ceiling": True,
                "build": {"people": [], "tools": [], "materials": [], "prototypes": [], "nre": [],
                          "certification": [{"item": "FCC Part 15 B", "amount": 1500, "confidence_class": "budgetary"}],
                          "total": 1500},
                "unit": {"volume": 50,
                         "bom": [{"item": "SCD41", "amount": 22, "confidence_class": "budgetary"}],
                         "assembly": [], "test": [], "packaging": [], "shipping": [], "warranty_reserve": [],
                         "moq_notes": "MOQ 10 on the enclosure", "lead_time_notes": "6 weeks on the sensor",
                         "total_per_unit": 61},
                "run_monthly": {"digital": [{"item": "host power", "amount": 2, "confidence_class": "budgetary"}],
                                "physical": [], "people": [], "total": 2},
                "exit": {"migration": [], "decommission": [], "disposal": [],
                         "kept_dependency_exits": [{"item": "leave Home Assistant", "amount": 0, "confidence_class": "rom"}],
                         "total": 0}}
        prospect = {"id": "p", "kill_criteria": ["no demand"]}
        plan = {"id": "pl", "milestones": [], "work_orders": [], "critical_path": [], "crews": [],
                "premortem": {"run_at": "2026-10-23T00:00:00+00:00", "with": "breaker",
                              "failures": [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}]},
                "schedule_confidence": 0.6,
                "provenance": {"produced_by": "planner", "produced_at": "2026-10-23T00:00:00+00:00"}}
        for n, d in (("brief.json", self.brief), ("verdict.json", verdict), ("blueprint.json", blueprint),
                     ("cost.json", cost), ("prospect.json", prospect), ("plan.json", plan)):
            self.write(n, d)

    def test_clean_proceed_has_no_problems(self):
        self._k_artifacts()
        self.assertEqual(wckd.semantic_checks("G-K", self.pdir), [])

    def test_blueprint_scope_may_not_contain_kept_capabilities(self):
        self._k_artifacts()
        bp = J(self.pdir / "blueprint.json")
        bp["scope"]["build"] = ["C1"]
        self.write("blueprint.json", bp)
        self.assertTrue(any("contains KEEP capabilities" in p for p in wckd.semantic_checks("G-K", self.pdir)))

    def test_over_ceiling_without_signed_change_blocks(self):
        self._k_artifacts()
        self.write("cost.json", {"id": "c", "within_ceiling": False})
        self.assertTrue(any("exceed the budget ceiling" in p for p in wckd.semantic_checks("G-K", self.pdir)))

    def test_premortem_needs_three_failure_modes(self):
        self._k_artifacts()
        pl = J(self.pdir / "plan.json")
        pl["premortem"]["failures"] = pl["premortem"]["failures"][:2]
        self.write("plan.json", pl)
        self.assertTrue(any("need >=3" in p for p in wckd.semantic_checks("G-K", self.pdir)))

    def test_no_kill_criteria_blocks(self):
        self._k_artifacts()
        self.write("prospect.json", {"id": "p", "kill_criteria": []})
        self.assertTrue(any("no kill_criteria" in p for p in wckd.semantic_checks("G-K", self.pdir)))

    def test_reuse_ratio_must_match_the_verdicts(self):
        self._k_artifacts()
        v = J(self.pdir / "verdict.json")
        v["reuse_ratio"] = 0.5
        self.write("verdict.json", v)
        self.assertTrue(any("does not match the verdicts" in p for p in wckd.semantic_checks("G-K", self.pdir)))

    def test_crew_independence(self):
        self._k_artifacts()
        pl = J(self.pdir / "plan.json")
        pl["crews"] = [{"work_order": "WO-1", "builder": "a", "validator": "a", "breaker": "b"}]
        self.write("plan.json", pl)
        self.assertTrue(any("violates builder != validator != breaker" in p for p in wckd.semantic_checks("G-K", self.pdir)))


class TestDeliver(Base):
    def wo(self, status="built"):
        return {"id": "WO-1", "plan_id": "pl", "component_id": "c", "realm": "digital", "spec": "s",
                "acceptance": [{"criterion": "does x", "bar_dimension": "correctness"}],
                "deliverables": ["bin"], "status": status, "build_log": [],
                "assigned_to": {"builder": "builder", "validator": "validator", "breaker": "breaker"},
                "provenance": {"produced_by": "planner", "produced_at": "2026-10-23T00:00:00+00:00"}}

    def test_unbuilt_work_order_blocks_d1(self):
        (self.pdir / "workorders").mkdir()
        self.write("workorders/WO-1.json", self.wo("queued"))
        self.assertTrue(any("status queued" in p for p in wckd.semantic_checks("G-D1", self.pdir)))

    def test_self_proof_blocks_d2(self):
        (self.pdir / "workorders").mkdir(); (self.pdir / "proofs").mkdir()
        self.write("workorders/WO-1.json", self.wo())
        self.write("proofs/WO-1.proof.json", {"id": "p", "workorder_id": "WO-1", "validator": "builder", "builder": "builder",
                                              "independence_attestation": {"independent": True, "note": "trust me"},
                                              "environment": {"description": "builder laptop", "clean": False},
                                              "tests": [], "reproduced_from_clean": False, "result": "PROVEN", "defects": [],
                                              "evidence": [], "provenance": {"produced_by": "validator", "produced_at": "2026-10-23T00:00:00+00:00"}})
        self.assertTrue(any("not independent" in p for p in wckd.semantic_checks("G-D2", self.pdir)))

    def test_open_crit_blocks_d3(self):
        (self.pdir / "breaches").mkdir()
        self.write("breaches/BR-1.json", {"id": "BR-1", "target": {"kind": "wo", "ref": "WO-1"}, "breaker": "breaker",
                                          "independence_attestation": {"independent": True, "note": "n"},
                                          "campaigns": [], "verdict": "HARDENED",
                                          "findings": [{"id": "F1", "title": "auth bypass", "severity": "crit", "category": "security",
                                                        "repro": "steps", "blast_radius": "all", "disposition": "open", "evidence": []}],
                                          "provenance": {"produced_by": "breaker", "produced_at": "2026-10-23T00:00:00+00:00"}})
        self.assertTrue(any("open crit finding" in p for p in wckd.semantic_checks("G-D3", self.pdir)))


class TestScore(Base):
    def test_scores_follow_the_artifacts(self):
        self.write("brief.json", self.brief)
        self.write("landscape.json", self.land)
        self.write("verdict.json", {"id": "v", "brief_id": "b", "landscape_id": "l", "overall": "PROCEED",
                                    "overall_rationale": "r", "reuse_ratio": 0.83,
                                    "decisions": [{"capability_id": c["id"], "verdict": "KEEP" if c["id"] != "C6" else "BUILD",
                                                   "chosen_candidate": "cand-ha", "rationale": "r", "confidence": 0.8,
                                                   "why_not_keep": "g", "why_not_bend": "g", "cited_candidates": ["cand-ha"],
                                                   "evidence": [{"kind": "url", "locator": "x", "summary": "s",
                                                                 "captured_at": "2026-10-23T00:00:00+00:00",
                                                                 "captured_by": "judge", "confidence": 0.8}]}
                                                  for c in self.brief["capabilities"]],
                                    "signoffs": [{"by": "judge", "role": "judge", "at": "2026-10-23T00:00:00+00:00",
                                                  "decision": "approve"}],
                                    "provenance": {"produced_by": "judge", "produced_at": "2026-10-23T00:00:00+00:00"}})
        rows = {r["goal"]: r for r in wckd.compute_goals(self.pdir)}
        self.assertEqual(rows["G1"]["status"], "pass")          # 5 of 6 KEEP/BEND
        self.assertEqual(rows["G3"]["status"], "na")            # portfolio band needs 5 projects
        self.assertEqual(rows["G9"]["status"], "unknown")       # no lessons yet
        (self.pdir / "lessons.md").write_text("# l\n\n- one - *(a)*\n- two - *(b)*\n- three - *(c)*\n")
        rows = {r["goal"]: r for r in wckd.compute_goals(self.pdir)}
        self.assertEqual(rows["G9"]["status"], "pass")
        self.assertEqual(wckd.count_lessons(self.pdir / "lessons.md"), 3)

    def test_ledger_row_shape(self):
        self.write("brief.json", self.brief)
        rows = [{"goal": g, "status": "pass", "detail": "d"} for g in wckd.GOAL_IDS]
        row = wckd.ledger_row("proj", self.pdir, rows, {})
        self.assertEqual(row.count("|"), 24)                    # 23 separators: 12 goal marks + 11 other cells
        self.assertTrue(row.startswith("| proj |"))


class TestPhysical(Base):
    """The physical column has its own obligations; a digital-only reading of the gate must fail."""

    def _physical_project(self):
        self.brief["realm"] = "physical"
        self.write("brief.json", self.brief)
        self.write("verdict.json", {"id": "v", "brief_id": "b", "landscape_id": "l", "overall": "PROCEED",
                                    "overall_rationale": "r", "reuse_ratio": 0.83,
                                    "decisions": [{"capability_id": c["id"], "verdict": "KEEP", "chosen_candidate": "cand-ha",
                                                   "rationale": "r", "confidence": 0.8,
                                                   "evidence": [{"kind": "url", "locator": "x", "summary": "s",
                                                                 "captured_at": "2026-10-23T00:00:00+00:00",
                                                                 "captured_by": "judge", "confidence": 0.8}]}
                                                  for c in self.brief["capabilities"]],
                                    "signoffs": [{"by": "judge", "role": "judge", "at": "2026-10-23T00:00:00+00:00",
                                                  "decision": "approve"}],
                                    "provenance": {"produced_by": "judge", "produced_at": "2026-10-23T00:00:00+00:00"}})

    def test_gk_refuses_a_physical_blueprint_with_no_hazards_or_certification(self):
        self._physical_project()
        self.write("blueprint.json", {"id": "bp", "verdict_id": "v", "scope": {"build": [], "bend": []},
                                      "components": [], "adrs": [], "reversibility_plan": [], "non_goals": [],
                                      "open_risks": [],
                                      "provenance": {"produced_by": "architect", "produced_at": "2026-10-23T00:00:00+00:00"}})
        self.write("cost.json", {"id": "c", "within_ceiling": True})
        self.write("prospect.json", {"id": "pr", "kill_criteria": ["no demand"]})
        self.write("plan.json", {"id": "pl", "milestones": [], "work_orders": [], "critical_path": [], "crews": [],
                                 "premortem": {"run_at": "2026-10-23T00:00:00+00:00", "with": ["breaker"],
                                               "failures": [{"story": "a", "mitigation_or_tripwire": "b"}] * 3},
                                 "schedule_confidence": 0.6,
                                 "provenance": {"produced_by": "planner", "produced_at": "2026-10-23T00:00:00+00:00"}})
        problems = wckd.semantic_checks("G-K", self.pdir)
        self.assertTrue(any("certification_targets is empty" in p for p in problems))
        self.assertTrue(any("hazard_analysis" in p for p in problems))
        self.assertTrue(any("cost.unit is missing" in p for p in problems))

    def test_gd4_refuses_a_physical_release_with_no_pilot_batch(self):
        self._physical_project()
        self.write("release.json", {"id": "r", "plan_id": "pl", "strategy": "pilot", "environments": [],
                                    "steps": [{"order": 1, "action": "build", "criteria_to_proceed": ["ok"], "signs": ["shipper"]}],
                                    "go_no_go": {"criteria": [], "signoffs": []},
                                    "rollback": {"method": "repair", "drill_at": "2026-10-23T00:00:00+00:00",
                                                 "drill_result": "pass", "drill_time": "1 h", "max_acceptable_time": "1 d"},
                                    "monitoring_live_before_cutover": True, "findings_all_dispositioned": True,
                                    "cost_reestimate_at_gate": "G-D4", "outcome": {"status": "shipped"},
                                    "hardware": {"pilot_batch_size": 2, "manufacturing_handoff": "CM",
                                                 "qc_sampling_plan": "", "serial_tracking": "",
                                                 "logistics": "courier",
                                                 "repair_recall_path": {"description": "swap unit",
                                                                        "rehearsed_at": "2026-10-23T00:00:00+00:00",
                                                                        "rehearsal_result": "fail"}},
                                    "provenance": {"produced_by": "shipper", "produced_at": "2026-10-23T00:00:00+00:00"}})
        problems = wckd.semantic_checks("G-D4", self.pdir)
        self.assertTrue(any("pilot_batch_size is 2" in p for p in problems))
        self.assertTrue(any("qc_sampling_plan is empty" in p for p in problems))
        self.assertTrue(any("repair/recall path was not rehearsed" in p for p in problems))

    def test_gd3_requires_the_campaign_categories_for_the_realm(self):
        self._physical_project()
        (self.pdir / "breaches").mkdir()
        self.write("breaches/BR-1.json", {"id": "BR-1", "target": {"kind": "wo", "ref": "WO-1"}, "breaker": "breaker",
                                          "independence_attestation": {"independent": True, "note": "n"},
                                          "campaigns": [{"category": "security", "ran": True, "method": "ports", "outcome": "none"}],
                                          "verdict": "HARDENED", "findings": [],
                                          "cost_compared_to_ledger": "", "provenance": {"produced_by": "breaker", "produced_at": "2026-10-23T00:00:00+00:00"}})
        problems = wckd.semantic_checks("G-D3", self.pdir)
        joined = " ".join(problems)
        self.assertIn("physical", joined)
        self.assertIn("supply_chain", joined)
        self.assertIn("cost campaign", joined)


class TestDigital(Base):
    """Digital obligations: itemised run cost, priced exits, watched kept dependencies."""

    def _digital_project(self):
        self.brief["realm"] = "digital"
        self.write("brief.json", self.brief)
        self.write("verdict.json", {"id": "v", "brief_id": "b", "landscape_id": "l", "overall": "PROCEED",
                                    "overall_rationale": "r", "reuse_ratio": 0.83,
                                    "decisions": [{"capability_id": c["id"], "verdict": "KEEP",
                                                   "chosen_candidate": "cand-ha", "rationale": "r", "confidence": 0.8,
                                                   "evidence": [{"kind": "url", "locator": "x", "summary": "s",
                                                                 "captured_at": "2026-10-23T00:00:00+00:00",
                                                                 "captured_by": "judge", "confidence": 0.8}]}
                                                  for c in self.brief["capabilities"]],
                                    "signoffs": [{"by": "judge", "role": "judge", "at": "2026-10-23T00:00:00+00:00",
                                                  "decision": "approve"}],
                                    "provenance": {"produced_by": "judge", "produced_at": "2026-10-23T00:00:00+00:00"}})

    def test_run_cost_must_be_itemised_and_kept_exits_priced(self):
        self._digital_project()
        self.write("cost.json", {"id": "c", "within_ceiling": True,
                                 "run_monthly": {"digital": [], "physical": [], "people": [], "total": 5},
                                 "exit": {"migration": [], "decommission": [], "disposal": [],
                                          "kept_dependency_exits": [], "total": 0}})
        problems = wckd.semantic_checks("G-K", self.pdir)
        self.assertTrue(any("run_monthly.digital is empty" in p for p in problems))
        self.assertTrue(any("kept_dependency_exits is empty" in p for p in problems))

    def test_kept_dependencies_must_be_watched_at_gd5(self):
        self._digital_project()
        self.write("runbook.json", {"id": "rb", "release_id": "r",
                                    "owner": {"name": "Galahad", "kind": "person"},
                                    "slos": [{"name": "up", "bar_dimension": "reliability", "target": "99%",
                                              "measure": "probe", "alert": "a1"}],
                                    "alerts": [{"id": "a1", "condition": "down", "route": "tg", "owner": "Galahad"}],
                                    "oncall": {"rota": "weekly", "escalation": ["human"]},
                                    "maintenance_cadence": [], "patching_policy": "monthly",
                                    "kept_dependencies_watched": [],
                                    "opex_budget_monthly": {"amount": 5, "currency": "USD", "confidence_class": "budgetary"},
                                    "opex_actual": [], "drift_checks": [],
                                    "reentry_triggers": [{"condition": "a", "action": "RE_WANT"},
                                                         {"condition": "b", "action": "RE_CANVASS"},
                                                         {"condition": "c", "action": "RE_JUDGE"}],
                                    "end_of_life": {"when": "2027", "how": "delete", "tell_users": "changelog"},
                                    "provenance": {"produced_by": "keeper", "produced_at": "2026-10-23T00:00:00+00:00"}})
        (self.pdir / "lessons.md").write_text("- a - *(x)*\n- b - *(y)*\n- c - *(z)*\n")
        problems = wckd.semantic_checks("G-D5", self.pdir)
        self.assertTrue(any("not watched in runbook.kept_dependencies_watched" in p for p in problems))


class TestManifest(Base):
    def test_manifest_is_current_and_conforms(self):
        from tree import Tree
        t = Tree()
        try:
            out = t.cli("manifest", "--check")
            self.assertIn("up to date", out)
            out = t.cli("conformance")
            self.assertIn("16/16 conformance cases pass", out)
        finally:
            t.close()

    def test_compiled_protocol_has_every_role_and_gate(self):
        from tree import Tree
        t = Tree()
        try:
            proto = json.loads((t.root / "machine" / "protocol.json").read_text())
            self.assertEqual(len(proto["gates"]), 8)
            self.assertEqual(len(proto["roles"]), 17)
            self.assertEqual(len(proto["phases"]), 4)
            self.assertEqual(proto["tolerances"]["min_source_classes"], 5)
        finally:
            t.close()


class TestConditions(Base):
    def test_open_condition_blocks_its_due_gate(self):
        self.gate("G-W", decision="PASS_WITH_CONDITIONS",
                  conditions=[{"statement": "name the calibration source", "owner": "barkeeper", "due_gate": "G-C"}])
        self.assertTrue(any("open condition from G-W" in p for p in wckd.semantic_checks("G-C", self.pdir)))
        self.assertFalse(any("open condition" in p for p in wckd.semantic_checks("G-W", self.pdir)))

    def test_closed_condition_does_not_block(self):
        self.gate("G-W", decision="PASS_WITH_CONDITIONS",
                  conditions=[{"statement": "name the calibration source", "owner": "barkeeper", "due_gate": "G-C",
                               "closed_at": "2026-10-23T01:00:00+00:00", "closed_by": "barkeeper"}])
        self.assertFalse(any("open condition" in p for p in wckd.semantic_checks("G-C", self.pdir)))

    def test_terminal_record_is_detected(self):
        self.gate("G-W", decision="KILL", notes="already solved")
        t = wckd.terminal_state(self.pdir)
        self.assertIsNotNone(t)
        self.assertEqual(t["decision"], "KILL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
