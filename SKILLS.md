# SKILLS.md

*The registry of everything a WCKD agent knows how to do. Agents list the skills they own in their frontmatter; a skill used by a role that doesn't own it is a protocol violation (see `PROTOCOL.md §7`). Each entry: what to do, what goes in, what comes out, what evidence must be left behind, and the way it most often fails.*

Format: `skill-id` · phase · owner → **Do** / **In** / **Out** / **Evidence** / **Fails when**

---

## W — Want

### `wish-to-brief` · W · Listener
**Do:** Restate the wish. Split it into capabilities (must / should / could), each with a measurable statement. Capture constraints, non-goals, horizon (first value, lifetime) and budget ceiling (build, run per month, per unit). Ask at most five questions, and only ones whose answer could change a verdict or the Bar.
**In:** `wish.json`, `memory/LESSONS.md` · **Out:** `brief.json` (everything except `bar`)
**Evidence:** questions and answers, verbatim, in `brief.questions_asked`.
**Fails when:** it writes solutions into the brief ("build a React app") instead of capabilities ("a person can see today's reading on their phone").

### `bar-setting` · W · Barkeeper
**Do:** For each Bar dimension in scope (correctness, performance, reliability, security, safety, cost, usability, maintainability, compliance, sustainability, exit), write a threshold and the method that will measure it. Check thresholds against the budget ceiling and memory; flag any dimension that is unrealistic at that budget.
**In:** `brief.json` draft, `memory/LESSONS.md` · **Out:** `brief.bar`
**Evidence:** for each threshold, why this number (source, precedent or human instruction).
**Fails when:** a threshold has no measurement method; the Bar is copied from a template without pruning.

### `done-condition-authoring` · W · Listener
**Do:** Write the single sentence that means "done" and the test a stranger could run to confirm it.
**In:** `brief.capabilities`, `brief.bar` · **Out:** `brief.done_condition`
**Evidence:** the test, as steps.
**Fails when:** "done" is a feeling ("works well") rather than an observation.

## C — Canvass

### `landscape-search` · C · Scout
**Do:** For each capability, search at least five of the seven source classes: open source; commercial / SaaS / COTS; internal and prior WCKD projects; academic, patents and standards; physical suppliers and catalogs; communities, forums and issue trackers; adjacent domains that solved the same shape of problem. Log every query.
**In:** `brief.json`, `memory/` · **Out:** `landscape.search_log`, `landscape.candidates`
**Evidence:** query, tool, date, result count, locators and versions for every hit kept.
**Fails when:** it stops at the first page; it searches only software for a physical want (or vice versa).

### `candidate-trial` · C · Scout
**Do:** For the top two or three candidates per capability, actually use the thing: install it, run it, call it, order the sample, bench it. Record what happened within the canvass time-box.
**In:** `landscape.candidates` · **Out:** `candidates[].tried`, `trial_notes`, measurements
**Evidence:** logs, screenshots, measurements, receipts.
**Fails when:** "tried" means "read the README."

### `failure-mining` · C · Appraiser
**Do:** For the problem space and for each candidate, find what was tried and died: abandoned repos, closed-won't-fix issues, post-mortems, recalls, discontinued products, forum threads of people giving up. Extract *why* each died and the lesson.
**In:** `landscape.candidates`, the web, memory · **Out:** `landscape.graveyard`
**Evidence:** locator and date for every grave.
**Fails when:** the Graveyard is empty for a space with any history.

### `bar-scoring` · C · Appraiser
**Do:** Score every candidate against every capability it could serve: fit 0–1, meets-bar true/false per dimension, with notes on what works and what doesn't.
**In:** `brief.bar`, `landscape.candidates` · **Out:** `candidates[].fit[]`, `works[]`, `doesnt[]`
**Evidence:** the measurement or source behind each score.
**Fails when:** scores are assigned without reference to a Bar threshold.

### `gap-mapping` · C · Cartographer
**Do:** Build the coverage matrix: capability × candidates evaluated × best fit × gap. State the gap precisely (which Bar dimension, by how much).
**In:** scored candidates, graveyard · **Out:** `landscape.coverage`
**Evidence:** links to the scores that produced each row.
**Fails when:** a gap is stated as "nothing good exists" instead of "best fit 0.7, misses reliability threshold by 2×."

### `absence-proof` · C · Scout, Cartographer
**Do:** Declare that nothing exists for a capability only with the search log that proves the look: source classes, queries, dates, zero or disqualified results.
**In:** `landscape.search_log` · **Out:** `landscape.absence_declarations`
**Evidence:** the log itself.
**Fails when:** absence is asserted from experience.

## K — Keep / Kill

### `verdict-issuing` · K · Judge
**Do:** For every capability, issue KEEP, BEND, BUILD, WAIT or KILL with rationale, evidence and confidence. BUILD requires `why_not_keep` and `why_not_bend`. WAIT requires a tripwire. Issue the overall verdict (PROCEED / WAIT / KILL). Record any Bar change with a signature.
**In:** `brief.json`, `landscape.json` · **Out:** `verdict.json`
**Evidence:** every rationale cites landscape entries by id.
**Fails when:** verdicts are issued per project instead of per capability; BUILD is chosen because it is more interesting.

### `gap-architecture` · K · Architect
**Do:** Design only the BEND + BUILD set. Components, responsibilities, interfaces to KEPT parts, data flows, physical/digital boundary, ADRs with options and consequences, reversibility plan, explicit non-goals.
**In:** `verdict.json`, `landscape.json` · **Out:** `blueprint.json`
**Evidence:** each component maps to a verdict id.
**Fails when:** the blueprint contains anything the verdict said KEEP.

### `interface-contracting` · K · Architect
**Do:** For every boundary between a built part and a kept part, write the contract: protocol, schema, physical connector, tolerances, failure behavior, versioning.
**In:** `blueprint.components` · **Out:** `blueprint.components[].interfaces`
**Evidence:** the kept part's documented interface, by locator and version.
**Fails when:** an interface assumes behavior the kept part never promised.

### `cost-ledgering` · K · Quartermaster
**Do:** Price four things: build (people, tools, materials, prototypes, NRE, certification), run per month (compute, storage, egress, licenses, SaaS, power, consumables, support, maintenance, on-call), exit (migration, decommission, disposal), and the cost of not doing it. Price KEEP decisions too (licenses, fees, lock-in). Give totals at 1, 12 and 36 months. Tag the whole ledger with a confidence class and list assumptions and sensitivities.
**In:** `verdict.json`, `blueprint.json`, `landscape.candidates[].cost` · **Out:** `cost.json`
**Evidence:** price source and date for every line.
**Fails when:** run cost is "negligible"; people cost is omitted because "we're already paid."

### `unit-costing` · K · Quartermaster
**Do:** For physical builds: BOM at target volume, assembly, test, packaging, shipping, warranty reserve, spares. Note minimum order quantities and lead times.
**In:** `blueprint.physical_spec` · **Out:** `cost.unit`
**Evidence:** supplier quotes or catalog prices with dates.
**Fails when:** BOM is priced at quantity 1 for a 1,000-unit plan, or vice versa.

### `prospecting` · K · Prospector
**Do:** Demand signals, addressable users, year-one users, competition (from the landscape), differentiation, ROI and payback, timing, regulatory exposure, strategic fit. Write kill criteria and tripwires that would reverse the recommendation.
**In:** `brief.json`, `landscape.json`, `cost.json` · **Out:** `prospect.json`
**Evidence:** sources for demand and competition claims.
**Fails when:** the prospect has no condition under which it would say "don't."

### `risk-registering` · K · Prospector, Planner
**Do:** List risks with likelihood × impact, owner and mitigation. Include supply, regulatory, safety, security, cost, dependency (kept parts dying), and people risks.
**In:** blueprint, cost, landscape graveyard · **Out:** `prospect.risks`
**Evidence:** each risk cites a grave, a measurement or a source where one exists.
**Fails when:** every risk is "medium."

### `pre-mortem` · K · Breaker, Planner
**Do:** Assume the project failed a year from now. Write the three to five most likely reasons, drawing on the Graveyard. Add a mitigation or a tripwire for each to the plan.
**In:** `landscape.graveyard`, `blueprint.json`, `plan.json` draft · **Out:** `plan.premortem`
**Evidence:** each failure story cites a grave or a risk.
**Fails when:** failures are generic ("ran out of time").

### `work-breakdown` · K · Planner
**Do:** Decompose the blueprint into work orders small enough to prove independently. Milestones with exit criteria, dependencies, critical path, schedule confidence.
**In:** `blueprint.json`, `cost.json` · **Out:** `plan.json`, `workorders/*.json` (queued)
**Evidence:** every work order maps to a component and a Bar dimension.
**Fails when:** a work order can't be proven without the whole system.

### `crew-assignment` · K · Planner
**Do:** Assign a builder, a validator and a breaker to every work order such that no one holds two of the three roles on the same order.
**In:** `plan.work_orders` · **Out:** `plan.crews`, `workorders[].assigned_to`
**Evidence:** the assignment table.
**Fails when:** the same agent builds and proves, "just for small ones."

## D — Deliver

### `increment-build` · D · Builder
**Do:** Build one work order at a time, in the smallest increments that can be shown working. Follow the spec and the kept interfaces. Keep a build log. Run self-checks, then hand off; do not mark proven.
**In:** `workorders/WO.json`, `blueprint.json` · **Out:** the deliverable, `workorders[].build_log`, status `built`
**Evidence:** commits, build outputs, self-check results.
**Fails when:** the builder "improves" the spec without a message to the Architect.

### `fabricate` · D · Builder
**Do:** For physical work orders: CAD, BOM revision, firmware, assembly instructions, test fixture. Build the prototype or pilot unit. Photograph and measure.
**In:** `workorders/WO.json`, `blueprint.physical_spec` · **Out:** files, units, `build_log`
**Evidence:** drawings, photos, measurements, serials.
**Fails when:** the as-built differs from the as-designed and nobody wrote it down.

### `test-authoring` · D · Validator
**Do:** From the work order's acceptance criteria and the Bar, write tests before reading the builder's code or touching the unit. Each test names the Bar dimension it proves.
**In:** `workorders/WO.json`, `brief.bar` · **Out:** `proofs/WO.proof.json#tests`
**Evidence:** the test definitions.
**Fails when:** tests are written from the implementation instead of the spec.

### `clean-reproduction` · D · Validator
**Do:** Reproduce the build from a clean environment or a fresh unit, using only the written instructions. Note every undocumented step.
**In:** the deliverable, `build_log` · **Out:** `proof.reproduced_from_clean`
**Evidence:** the clean-environment log.
**Fails when:** validation runs on the builder's machine or bench.

### `acceptance-proof` · D · Validator
**Do:** Run the tests. Record expected vs observed. Issue PROVEN, PARTIAL or FAILED with defects listed. Sign an independence attestation.
**In:** tests, deliverable · **Out:** `proofs/WO.proof.json`
**Evidence:** raw test output, measurements.
**Fails when:** PARTIAL is treated as PROVEN downstream.

### `security-attack` · D · Breaker
**Do:** Attack the deliverable as an adversary: auth, injection, secrets, supply chain, update path, physical ports, debug interfaces. Record exploit paths and blast radius.
**In:** deliverable, blueprint · **Out:** `breaches/BR.json#findings[category=security]`
**Evidence:** reproduction steps.
**Fails when:** it stops at a checklist.

### `abuse-and-edge-attack` · D · Breaker
**Do:** Misuse it: wrong inputs, hostile users, concurrency, time zones, empty states, power loss mid-write, the one unit in a thousand with a bad part.
**In:** deliverable · **Out:** findings `category=abuse|edge`
**Evidence:** reproduction steps.
**Fails when:** edges are reasoned about instead of exercised.

### `load-and-chaos` · D · Breaker
**Do:** Push past the Bar's performance and reliability thresholds. Kill dependencies, slow the network, fill the disk, pull the kept service. Observe recovery.
**In:** deliverable, `brief.bar` · **Out:** findings `category=load|chaos`, measurements
**Evidence:** load profiles and traces.
**Fails when:** load testing stops at the threshold instead of beyond it.

### `physical-stress` · D · Breaker
**Do:** For hardware: thermal, vibration, drop, humidity, EMI, power transients, wear, misuse by a child, misuse by a technician. Inspect for drift over time.
**In:** units · **Out:** findings `category=physical`
**Evidence:** test conditions and photos.
**Fails when:** one golden unit is tested and declared representative.

### `cost-attack` · D · Breaker, Quartermaster
**Do:** Try to make the thing expensive: runaway queries, retry storms, log floods, egress spikes, consumable burn, warranty abuse. Compare to `cost.run_monthly`.
**In:** deliverable, `cost.json` · **Out:** findings `category=cost`
**Evidence:** cost deltas measured.
**Fails when:** nobody checks that a bug can turn into a bill.

### `rollout-design` · D · Shipper
**Do:** Choose a strategy (canary, staged, blue/green, pilot batch) and write the steps, environments, go/no-go criteria and who signs. Monitoring must be live before cutover.
**In:** `plan.json`, `runbook` draft · **Out:** `release.json`
**Evidence:** environment inventory, criteria.
**Fails when:** the first users are all the users.

### `rollback-drill` · D · Shipper
**Do:** Rehearse undoing the release before doing it. Measure the time. For hardware, rehearse the repair or recall path on real units.
**In:** `release.rollback` · **Out:** `release.rollback.drill_result`
**Evidence:** drill log and timing.
**Fails when:** rollback is a document, not a rehearsal.

### `manufacturing-handoff` · D · Shipper
**Do:** For physical builds: pilot batch size, supplier confirmations, work instructions, QC sampling plan, packaging, logistics, serial tracking, recall path.
**In:** `blueprint.physical_spec`, `cost.unit` · **Out:** `release.hardware`
**Evidence:** supplier confirmations, QC plan.
**Fails when:** the pilot batch is skipped to hit volume.

### `runbook-authoring` · D · Keeper
**Do:** Owner, SLOs, alerts, on-call, maintenance cadence, spares and consumables, patching policy, end-of-life plan, re-entry triggers.
**In:** `release.json`, `cost.json`, `blueprint.json` · **Out:** `runbook.json`
**Evidence:** every SLO names its measurement.
**Fails when:** the owner is "the team."

### `slo-and-alerting` · D · Keeper
**Do:** Turn Bar thresholds into SLOs with measurement and alert routes. For physical things: field-return rates, calibration drift, consumable levels.
**In:** `brief.bar` · **Out:** `runbook.slos`, `runbook.alerts`
**Evidence:** alert configuration.
**Fails when:** an SLO exists with no alert, or an alert with no owner.

### `opex-tracking` · D · Keeper
**Do:** Record actual operating cost monthly against `cost.run_monthly`. Raise a tripwire at budget + 10 %.
**In:** bills, meters, `cost.json` · **Out:** `runbook.opex_actual`
**Evidence:** invoices and meter readings.
**Fails when:** the ledger is updated only when someone asks.

### `drift-detection` · D · Keeper
**Do:** Periodically re-check the Bar against reality: are thresholds still met, have kept dependencies changed or died, has the world shipped something that makes a BUILD a KEEP now?
**In:** `runbook`, `landscape` · **Out:** `runbook.drift_checks`, re-entry messages
**Evidence:** measurements and dependency versions.
**Fails when:** drift is noticed by users first.

### `retro-and-lessons` · D · Scribe
**Do:** At Kept: what the Canvass missed, what the Judge got wrong, where cost diverged, what broke that the pre-mortem didn't predict. Write at least three lessons that would change the next Canvass or Verdict.
**In:** every artifact in the project · **Out:** `lessons.md`, `memory/LESSONS.md` (appended), `memory/LEDGER.md` (row)
**Evidence:** each lesson cites the artifact that taught it.
**Fails when:** lessons are compliments.

## Cross-phase

### `evidence-packaging` · all · all
**Do:** Attach to every claim an evidence object: kind, locator, summary, captured-at, captured-by, confidence.
**In:** any claim · **Out:** `evidence[]`
**Fails when:** confidence is always 0.9.

### `escalation` · all · all → Conductor → human
**Do:** When blocked, when evidence conflicts, when a Bar change is needed, or when a finding is CRIT: send an `escalation` message with both positions written down and a proposed decision.
**In:** the conflict · **Out:** `message.type=escalation`
**Fails when:** the escalation hides the agent's own preference.

### `gate-review` · all · Conductor
**Do:** Check every required artifact exists and validates; check every criterion with its evidence; collect sign-offs; record PASS, FAIL or PASS_WITH_CONDITIONS; refuse human-veto gates without a human.
**In:** `workflows/gates.yaml`, project artifacts · **Out:** `gates/G-X.json`
**Fails when:** conditions on a PASS_WITH_CONDITIONS are never closed.

### `ledger-writing` · all · Scribe
**Do:** Append project id, verdict summary, reuse ratio, costs (estimate vs actual), gate dates, goal scores and lessons pointer to `memory/LEDGER.md`. Never edit history.
**In:** project artifacts · **Out:** `memory/LEDGER.md`
**Fails when:** a row is rewritten to look better.
