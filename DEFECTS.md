# WCKD audit — v1.0 as delivered, checked against its own spec

Audit date: 2026-10-23. Every finding below was reproduced against the code as shipped, then either fixed in
`bin/wckd.py` / `schemas/` / `examples/` or left open with the reason.

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
   (records `closed_at`, `closed_by`, `closed_note`), plus those fields in the gate schema.

3. **G-C was a rubber stamp.** A landscape with one search query, one untried candidate, an empty graveyard
   and zero coverage rows passed G-C, because the schema allows empty arrays and the CLI checked validity
   only. That defeats the Prime Directive: a thin JSON file could skip the Canvass. *Fix:* G-C now enforces
   `PROTOCOL.md §5.2–5.7` and `GOALS G2` per capability — ≥5 distinct source classes (or a proven absence),
   ≥3 candidates evaluated (or a proven absence), at least one candidate tried or `trial_notes` saying why
   not, a coverage row naming a `best_fit` or a precise gap, no `stale` rows, and `checked_at` inside
   `brief.freshness_days`. An empty Graveyard now needs `landscape.graveyard_note` (new optional field) to
   pass: that criterion was previously unexpressible in any artifact.

4. **A `FAIL` at G-W/G-K/G-D4 could not be recorded.** The CLI exempted `FAIL` from the `--human` rule, but
   `gate.schema.json` demanded `human_signoff` for those gate ids unconditionally, so the record failed
   validation and was deleted. *Fix:* the schema now requires `human_signoff` only for a PASS or
   PASS_WITH_CONDITIONS at a human-veto gate. A FAIL, KILL or WAIT is not a human veto.

5. **Written G-W / G-K / G-D4 / G-D5 criteria were unenforced.** Added to `semantic_checks`: measurable
   capability statements with a measure; every in-scope Bar dimension with threshold and measurement method;
   `lessons_read` non-empty; blueprint scope free of KEEP capabilities; over-ceiling cost without a signed
   `bar_change`; `prospect.kill_criteria` non-empty; pre-mortem with ≥3 failure modes; crew independence;
   `reuse_ratio` matching the verdict arithmetic; cost re-estimated at G-D4; runbook owner, SLO alerts and
   re-entry triggers; ≥3 lessons and a `memory/LESSONS.md` to append them to.

6. **G-D5 crashed on `lessons.md`.** `gates.yaml` lists `lessons.md` among G-D5's requirements, but the CLI
   resolves every requirement through `FILE_SCHEMA` (JSON artifacts only), so `wckd gate <slug> G-D5` raised
   `KeyError: 'lessons.md'` and died. Every project that reached Kept hit this. *Fix:* non-schema requirements
   are now treated as free-form documents (exists and is non-empty) and hashed like the rest. Caught by the new
   end-to-end lifecycle test, not by any single-gate test — which is the argument for the lifecycle test.

7. **The worked example failed the protocol's own G2 rule.** `examples/air-quality-monitor/landscape.json`
   searched 5–6 source classes per capability (passed) but evaluated 1–2 candidates for C2, C3, C4, C5 and C6,
   where `GOALS G2` and `gates.yaml#G-C` require ≥3 or a proven absence — so with G-C enforcing the rule, the
   reference run could not pass its own Canvassed gate. *Fix:* a real re-canvass on 2026-10-23, not invented
   data — seven candidates added (AirGradient, Airthings Wave Plus, Grafana over HA history, cyd-scd41,
   Printables SCD41 enclosures, Sensor.Community airrohr, the Sensirion SCD41 module) with live URLs, dated
   evidence, honest `tried: false` and trial notes, plus six search-log rows. No new candidate beats the
   incumbent fit on any capability, so the verdicts stand; the example now passes G-W and G-C. The re-canvass
   script is kept at `tests/recanvass_example.py` so the provenance of those candidates is reproducible.

## Open

8. **Not machine-checkable, left to the Conductor by design:** provenance hashes taken at hand-off,
   confidence-class consistency inside `cost.json` line items, the *content* of the `memory/LEDGER.md` row
   (the row can be generated by `wckd score --ledger`, but only the Scribe can attest it is true),
   message-bus conformance, and whether a Bar threshold is realistic. The Conductor must read these.

9. **`brief.id` is not tied to the project slug.** A project can carry a brief whose `id` names another
   project (verified: the example brief passes under any slug). Harmless for gates, a provenance hazard for
   messages and hashes. Left as-is because the schema permits any id and renaming artifacts mid-project would
   break the ids that verdicts, landscapes and plans cross-reference.

10. **Physical work is enforced but not exercised on real hardware.** v1.1 added `workflows/physical.yaml`
    and the realm-conditional checks (certification targets, hazard analysis with controls, unit cost with MOQ
    and lead time, pilot batch, QC plan, serials, rehearsed recall, spares, recalibration). The obligations are
    machine-checked, but no real hardware run has been through them; the numbers (pilot batch of five, hazard
    minimum of three) are defaults, not field-proven thresholds.

11. **The new transports have known limits.** The MCP server speaks stdio with no auth (it runs with your
    filesystem rights — that is the trust boundary); `wckd serve` is localhost-bound and its bearer token is
    optional, so it is not an internet-facing service as shipped; `wckd run` executes steps sequentially, so
    steps marked `parallel_with` are run in order rather than concurrently. None of these violates the
    protocol; all three are the next layer of engineering, not silently missing behaviour.

## Verification

- `python3 -m unittest discover -s tests` — 45 tests: gate semantics, a full synthetic W→D5 lifecycle (gate by
  gate, `score`, the append-only ledger refusal), the run loop against a real command, MCP over stdio, HTTP,
  the physical refusals, manifest drift and conformance.
- `make check` — manifest drift, conformance, the suite, and the worked example through G-W, G-C and `score`.
- CI (`.github/workflows/test.yml`) — Python 3.10/3.11/3.12, a stdlib-only job (no PyYAML, no jsonschema), and
  an MCP smoke test over stdio.
