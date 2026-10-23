# WCKD Protocol — Specification v1.0

**W**ant · **C**anvass · **K**eep/Kill · **D**eliver. Pronounced "wicked."

This document is normative. "Must" and "never" are requirements; "should" is a strong default. `SOUL.md` says why; this says what.

## 1. Purpose

WCKD turns a named want into a working, priced, kept thing — or a documented kill — while building only the gap between what already exists and a written standard (the Bar). It applies identically to digital and physical work.

## 2. Vocabulary

| Term | Meaning | Artifact |
|---|---|---|
| Wish | The human's words, verbatim | `wish.json` |
| Brief | The want, structured: capabilities, constraints, non-goals, horizon, budget ceiling, done condition, and the Bar | `brief.json` |
| Bar | The standards set: per dimension, a threshold and a measurement method | `brief.bar` |
| Capability | One thing the result must be able to do; the unit of verdict | `brief.capabilities[]` |
| Landscape | What exists: candidates, trials, scores, coverage, proven absences | `landscape.json` |
| Graveyard | What was tried and died, and why | `landscape.graveyard[]` |
| Verdict | Per capability: KEEP / BEND / BUILD / WAIT / KILL, plus the overall decision | `verdict.json` |
| Blueprint | Architecture of the BEND + BUILD set only | `blueprint.json` |
| Ledger (cost) | Build, run, unit, exit and not-doing costs with confidence classes | `cost.json` |
| Prospect | Demand, ROI, risks, regulation, timing, kill criteria, tripwires | `prospect.json` |
| Plan | Work breakdown, milestones, critical path, crews, pre-mortem | `plan.json` |
| Work order | The unit of build, proof and break | `workorders/WO-*.json` |
| Proof | Independent validation record | `proofs/WO-*.proof.json` |
| Breach | Adversarial findings and their disposition | `breaches/BR-*.json` |
| Release | Rollout strategy, rollback drill, manufacturing handoff | `release.json` |
| Runbook | Operations: owner, SLOs, maintenance, opex, drift, re-entry | `runbook.json` |
| Gate record | Decision at a gate with evidence and sign-offs | `gates/G-*.json` |
| Message | The envelope every inter-agent communication uses | `schemas/message.schema.json` |
| Lessons | What this project teaches the next one | `lessons.md` → `memory/LESSONS.md` |

## 3. Phases, roles, artifacts, gates

| Phase | Roles | Produces | Gate | Human veto |
|---|---|---|---|---|
| W — Want | Listener, Barkeeper | brief | **G-W Briefed** | yes |
| C — Canvass | Scout, Appraiser, Cartographer | landscape | **G-C Canvassed** | no |
| K — Keep/Kill | Judge, Architect, Quartermaster, Prospector, Planner (+ Breaker for pre-mortem) | verdict, blueprint, cost, prospect, plan, queued work orders | **G-K Judged** | yes |
| D1 — Build | Builder | built work orders | **G-D1 Built** | no |
| D2 — Prove | Validator | proofs | **G-D2 Proven** | no |
| D3 — Harden | Breaker (+ Builder fixes, Validator retests) | breaches | **G-D3 Hardened** | no |
| D4 — Ship | Shipper | release | **G-D4 Shipped** | yes |
| D5 — Keep | Keeper, Scribe | runbook, lessons, ledger row | **G-D5 Kept** | no |

The Conductor spans all phases and runs the gates. The Scribe spans all phases and records provenance. Full criteria for each gate are in `workflows/gates.yaml`; the gate record schema is `schemas/gate.schema.json`.

Phases are strictly ordered. A phase may be re-entered (§11) but never skipped.

## 4. The Bar

4.1 The Bar is written in W by the Barkeeper and signed by the human at G-W.
4.2 Dimensions: `correctness`, `performance`, `reliability`, `security`, `safety`, `cost_build`, `cost_run`, `cost_unit`, `usability`, `maintainability`, `compliance`, `sustainability`, `exit`. A brief declares which are in scope; every in-scope dimension must have a threshold and a measurement method.
4.3 After G-W the Bar is immutable except through a signed `bar_change` recorded in `verdict.json` or a gate record. A Bar change always names who, why and what evidence.
4.4 The Bar is never lowered to make a verdict come out BUILD, and never raised to make it come out KILL. Both are protocol violations.
4.5 Every downstream artifact references Bar dimensions by name: candidate scores, work-order acceptance criteria, proofs, breach findings, SLOs.

## 5. Canvass rules

5.1 **Memory first.** The Canvass begins by reading `memory/LESSONS.md` and prior projects in `memory/LEDGER.md`. `landscape.lessons_read` records what was read.
5.2 **Seven source classes; at least five per capability:** (a) open source; (b) commercial, SaaS, COTS; (c) internal systems and prior WCKD projects; (d) academic work, patents, standards; (e) physical suppliers and catalogs; (f) communities, forums, issue trackers; (g) adjacent domains that solved the same shape of problem.
5.3 **Try, don't just read.** For the top two or three candidates per capability the Scout must actually use the thing where feasible within the canvass budget: install, run, call, order a sample, bench it. `candidates[].tried` is true only then.
5.4 **Failure mining.** The Appraiser must populate the Graveyard: attempts that died, why, and the lesson. A space with history and an empty Graveyard fails G-C.
5.5 **Absence must be proven.** "Nothing exists" is a claim; it is admissible only as an `absence_declaration` that cites the search log.
5.6 **Canvass budget.** Time-box the Canvass at roughly 5–10 % of the build budget ceiling, never zero, never skipped for urgency. If the budget runs out, the landscape records what was *not* checked.
5.7 **Freshness.** Every candidate carries `checked_at`. The Judge may demand a re-check for anything older than the brief's `freshness_days` (default 90).

## 6. Verdict taxonomy

Issued by the Judge, per capability, in `verdict.json`.

| Verdict | Meaning | Obligation |
|---|---|---|
| **KEEP** | An existing thing meets the Bar for this capability. Adopt it. | Name the candidate. Record its cost, license and lock-in in the Ledger. No build. |
| **BEND** | An existing thing nearly meets the Bar. Adapt, configure, extend or fork it. | Name the candidate and the delta. Only the delta enters the Blueprint. |
| **BUILD** | Nothing meets or nearly meets the Bar, and the Prospect says the gap is worth closing. | `why_not_keep` and `why_not_bend` are required, each citing landscape ids. |
| **WAIT** | Something is about to exist, or the timing is wrong. Defer. | A tripwire (condition + date) that re-opens the capability. |
| **KILL** | Not worth doing, not possible at the Bar and budget, or the want itself was wrong. | Rationale and evidence. The Scribe records it in memory so it is not re-asked blind. |

6.1 The overall verdict is PROCEED, WAIT or KILL for the want as a whole. PROCEED requires every capability to have a verdict and at least one capability not KILLed.
6.2 Verdicts are per capability, never per project. "Build it all" requires a BUILD verdict on each capability, each with its own why-nots.
6.3 Reuse ratio = (KEEP + BEND) ÷ all verdicts. It is reported in the verdict and scored (GOALS G1).
6.4 A verdict may be appealed once, by any role, with new evidence, via an `escalation` message. The Conductor routes it; the Judge re-issues or confirms; the human may overrule.

## 7. Separation of powers

7.1 For any work order, Builder ≠ Validator ≠ Breaker. An agent may hold different roles on different work orders.
7.2 The Judge does not architect; the Architect does not judge. The Quartermaster is not subject to the Planner's schedule; cost is reported, not negotiated.
7.3 The Conductor does no domain work: it does not search, judge, design, build, prove or break. It routes, checks, records and escalates.
7.4 The Breaker participates in K only for the pre-mortem and never fixes what it finds.
7.5 Skills are owned (`SKILLS.md`). A role invoking a skill it does not own is a violation the Conductor must record.

## 8. Evidence rules

8.1 Every claim that crosses an agent boundary carries at least one evidence object: `kind` (url, file, log, measurement, repro, sample, interview, memory), `locator`, `summary`, `captured_at`, `captured_by`, `confidence` (0–1).
8.2 Ranking: measured > tried > found > reasoned. An artifact states which it is.
8.3 Conflicting evidence is recorded as conflicting; it is never averaged or silently resolved.
8.4 Confidence is numeric and revised in later artifacts; an agent never reports a confidence it would not bet on.
8.5 Every artifact has provenance: who produced it, from which inputs (by path and hash), when. The Scribe audits this.

## 9. Cost rules

9.1 Four costs, always: **build**, **run** (per month), **exit**, and the **cost of not doing it**. Physical work adds **unit** (BOM, assembly, test, packaging, shipping, warranty reserve).
9.2 Confidence classes: `rom` (±50 %, rough order of magnitude), `budgetary` (±25 %), `definitive` (±10 %). Every ledger and every line that differs from the ledger's class is tagged.
9.3 Horizons: totals at 1, 12 and 36 months.
9.4 Digital run cost must itemize compute, storage, egress, licenses, SaaS, support, on-call and patching. Physical run cost must itemize power, consumables, spares, calibration, maintenance labor and disposal.
9.5 KEEP is not free. Licenses, fees, lock-in and the exit cost of a kept thing are priced.
9.6 Cost is re-estimated at every gate from G-K onward. A variance beyond the confidence class triggers an `escalation` and may trigger RE-JUDGE (§11).
9.7 The Keeper records actual opex monthly. Budget + 10 % is a tripwire.

## 10. Physical / digital parity

The same phases and gates apply. The activities map as follows:

| Step | Digital | Physical |
|---|---|---|
| Canvass trial | install, run, call | order sample, bench, measure |
| Build | code, configure, provision | CAD, BOM, firmware, fabricate, assemble |
| Prove | automated tests from clean environment | bench test on a fresh unit from the written instructions |
| Break | pentest, fuzz, load, chaos, cost attack | thermal, vibration, drop, EMI, misuse, wear, supply-chain, cost attack |
| Ship | canary / staged / blue-green | pilot batch, manufacturing handoff, logistics |
| Rollback | revert, feature flag | repair path, recall path, spares |
| Monitor | telemetry, SLOs, bills | field returns, calibration drift, consumables, bills |
| Patch | hotfix, dependency bump | firmware update, rework, part substitution |
| Exit | migrate, decommission | decommission, dispose, recycle |

Hybrid wants carry both columns, and the Blueprint names the boundary between them.

## 11. Loops and re-entry

11.1 **The BPB loop.** Build → Prove → Break repeats per work order until PROVEN and HARDENED. A breach finding returns the work order to the Builder (fix), then the Validator (retest), then the Breaker (confirm). Only the Breaker closes a finding.
11.2 **RE-CANVASS.** Any role may request one when an assumption about the landscape breaks (a kept dependency dies, a new candidate appears, a trial contradicts a score). The Conductor approves; the Scout runs a scoped canvass; the Judge re-issues affected verdicts.
11.3 **RE-JUDGE.** Triggered by cost variance beyond class, a CRIT breach that cannot be fixed within the Bar, a failed proof that implicates the blueprint, or a prospect tripwire.
11.4 **RE-WANT.** Triggered by the Keeper when the Bar is no longer met in operation, opex exceeds budget + 10 %, or the human's want has changed. Returns to W with the existing artifacts as inputs.
11.5 **KILL** is available at every gate, at any time, to the Judge or the human. A kill is recorded in the ledger and memory with its reason.
11.6 Every re-entry is a message of type `escalation` with a `proposed_phase`, and produces a new gate record for the re-passed gate.

## 12. Human veto

12.1 The human must sign G-W, G-K and G-D4. The CLI and the Conductor refuse to record those gates without a human sign-off.
12.2 The human may veto any gate, change the Bar (with a signed `bar_change`), overrule a verdict on appeal, or kill the project.
12.3 Agents surface kill recommendations, cost overruns and CRIT findings to the human immediately via broadcast (`connections/connections.yaml`), never only at the next gate.

## 13. Memory

13.1 `memory/LEDGER.md` is append-only: one row per project, with verdict summary, reuse ratio, estimate vs actual, gate dates, goal scores and a pointer to lessons.
13.2 `memory/LESSONS.md` is read at the start of every Canvass and every Bar-setting. Each project appends at least three lessons, each citing the artifact that taught it.
13.3 Kills are memory. A killed want and its reasons are recorded so the next person asking is not starting blind.
13.4 Prior projects are a source class (§5.2c). A prior WCKD build is a candidate like any other and may be KEPT, BENT or buried.

## 14. Running a project

1. `wckd new <slug> "<wish>"` — creates `projects/<slug>/wish.json`.
2. Listener → brief (minus Bar). Barkeeper → Bar. Listener → done condition. **G-W** with human.
3. Scout → search log, candidates, trials. Appraiser → works/doesn't, scores, Graveyard. Cartographer → coverage, absences. **G-C**.
4. Judge → verdict. In parallel: Architect → blueprint; Quartermaster → cost; Prospector → prospect. Then Planner → plan + queued work orders, pre-mortem with Breaker. **G-K** with human. (If overall verdict is KILL or WAIT, Scribe records and the project ends or sleeps here.)
5. Per work order: Builder → built. Validator → proof. Breaker → breach; loop until hardened. **G-D1**, **G-D2**, **G-D3**.
6. Shipper → release with rollback drill (or pilot batch and recall path). Keeper → runbook draft with monitoring live. **G-D4** with human.
7. Keeper → runbook final, opex tracking, drift checks. Scribe → lessons, ledger row, goal scores. **G-D5**.
8. Operation: Keeper watches SLOs, opex and drift; re-enters W, C or K on triggers (§11).

Each step is a `next` call away: `wckd next <slug>` prints the role, its agent file, its inputs and the artifact it must write.

## 15. Conformance checklist

An implementation is WCKD-compliant when all of the following hold:

- [ ] No build activity before a recorded G-C PASS.
- [ ] Every capability in the brief has a verdict; every BUILD has why-not-keep and why-not-bend with landscape citations.
- [ ] The blueprint contains only BEND and BUILD scope.
- [ ] For every work order, Builder ≠ Validator ≠ Breaker, recorded.
- [ ] Every gate record lists checked artifacts (with hashes), criteria with evidence, and sign-offs; G-W, G-K, G-D4 carry a human sign-off.
- [ ] Every cost figure carries a confidence class; build, run, exit and not-doing costs are present; unit cost is present for physical work.
- [ ] A rollback (or repair/recall) drill is recorded before G-D4.
- [ ] A runbook with owner, SLOs, alerts, maintenance cadence, opex budget and re-entry triggers exists at G-D5.
- [ ] At least three lessons are appended to memory at G-D5, and `landscape.lessons_read` is non-empty at G-C.
- [ ] The Graveyard is never deleted.
- [ ] Bar changes after G-W are signed.

Everything else — tooling, model choice, message bus, team size — is an implementation detail.
