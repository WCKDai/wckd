# WCKD audit — v1.0 as delivered, checked against its own spec

Audit date: 2026-10-23. Every finding below was reproduced against the code as shipped, then either fixed
in `bin/wckd.py` / `schemas/gate.schema.json` or left open with the reason.

## Fixed

1. **KILL and WAIT could not be recorded.** `PROTOCOL.md §11.5`, `§14.4`, `gates.yaml#kill` and
   `wckd.workflow.yaml#on_overall_verdict` all make KILL/WAIT a legitimate outcome that ends (or sleeps) the
   project, but `wckd gate` accepted only `PASS | FAIL | PASS_WITH_CONDITIONS`, and the G-K semantic check
   refused any record whose `overall` was not `PROCEED`. Net effect: "kill is a win" was unimplementable —
   the project sat at `current gate: G-K` forever and `next` re-printed the blocking list.
   *Fix:* `--decision KILL|WAIT` added; terminal decisions skip artifact prerequisites (kill is available at
   any gate, any time), require a `--note` reason, are recorded with `decision: KILL|WAIT`, end the gate
   sequence, and route `next`/`status` to the Scribe.

2. **`PASS_WITH_CONDITIONS` conditions were written but never enforced.** `gates.yaml#pass_with_conditions`
   says "an open condition blocks that due gate"; nothing read `conditions[]`. *Fix:* any condition without
   `closed_at` whose `due_gate` is at or before the gate being recorded now blocks that gate, naming the
   originating gate, owner and statement. Added `wckd close <slug> <GATE> <index> --by NAME` to close one
   (records `closed_at`, `closed_by`, `closed_note`), plus `closed_by`/`closed_note` in the gate schema.

3. **G-C was a rubber stamp.** A landscape with one search query, one untried candidate, an empty graveyard
   and zero coverage rows passed G-C, because the schema allows empty arrays and the CLI checked validity
   only. That defeats the Prime Directive: a thin JSON file could skip the Canvass. *Fix:* G-C now enforces
   `PROTOCOL.md §5.2–5.7` and `GOALS G2` per capability — ≥5 distinct source classes (or a proven absence),
   ≥3 candidates evaluated (or a proven absence), at least one candidate tried or `trial_notes` saying why
   not, a coverage row naming a `best_fit` or a precise gap, no `stale` rows, and `checked_at` inside
   `brief.freshness_days`.

4. **A `FAIL` at G-W/G-K/G-D4 could not be recorded.** The CLI exempted `FAIL` from the `--human` rule, but
   `gate.schema.json` demanded `human_signoff` for those gate ids unconditionally, so the record failed
   validation and was deleted. *Fix:* the schema now requires `human_signoff` only for a PASS or
   PASS_WITH_CONDITIONS at a human-veto gate. A FAIL, KILL or WAIT is not a human veto.

5. **Written G-W / G-K / G-D4 / G-D5 criteria were unenforced.** Added to `semantic_checks`: measurable
   capability statements with a measure; every in-scope Bar dimension with threshold and measurement method;
   `lessons_read` non-empty; blueprint scope free of KEEP capabilities; over-ceiling cost without a signed
   `bar_change`; `prospect.kill_criteria` non-empty; pre-mortem with ≥3 failure modes; crew independence;
   cost re-estimated at G-D4; runbook owner, SLO alerts and re-entry triggers; ≥3 lessons and a
   `memory/LESSONS.md` to append them to.

## Open

6. **The worked example fails the protocol's own G2 rule.** `examples/air-quality-monitor/landscape.json`
   searches 5–6 source classes per capability (passes), but evaluates 1–2 candidates for C2, C3, C4, C5 and
   C6, where `GOALS G2` and `gates.yaml#G-C` require ≥3 or a proven absence. With G-C enforcing the rule, the
   reference run cannot pass its own Canvassed gate. Not patched by inventing candidates — that is the exact
   fabrication `SOUL.md` forbids. The example needs one or two more genuinely searched candidates per
   under-covered capability (or per-capability `absence_declarations` with five search-log references each),
   or G2 needs signing down at G-K through the protocol's own change path.

7. **Not machine-checkable, left to the Conductor by design:** graveyard non-empty (the landscape has no
   "this space has no history" field, so the criterion cannot be expressed), `reuse_ratio` arithmetic,
   provenance hashes at hand-off, confidence-class consistency inside `cost.json`, the `memory/LEDGER.md` row
   at G-D5, and message-bus conformance. The Conductor must read these; the CLI cannot.

8. **`brief.id` is not tied to the project slug.** A project can carry a brief whose `id` names another
   project (verified: the example brief passes under slug `t1`). Harmless for gates, a provenance hazard for
   messages and hashes. Left as-is because the schema permits any id and renaming artifacts mid-project would
   break the ids that verdicts, landscapes and plans cross-reference.

## Verification

`python3 -m unittest discover -s tests` — 19 semantic-check tests. End-to-end CLI runs: G-W pass/refuse on
the shipped brief, G-C refuse on a one-query canvass, G-C conditional block → `close` → unblock, terminal
KILL record that validates and routes to the Scribe.
