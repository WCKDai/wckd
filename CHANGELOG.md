# Changelog

## 1.1.0 — deployable on any agent, physical column enforced

**Portability**

- `machine/` — the protocol compiled to JSON: `protocol.json` (phases, steps, gates, roles, vocab, tolerances,
  campaigns, physical obligations), `agents.json`, one self-contained JSON Schema per artifact, and a single
  `schemas.bundle.json`. Any language or agent can read the contract without Python, YAML or a schema registry.
- `wckd manifest [--check]` regenerates it; CI fails on drift.
- **Zero-dependency mode.** The CLI runs on the Python stdlib alone: PyYAML is optional (falls back to the
  committed manifest), jsonschema is optional (falls back to required-key checks). `WCKD_NO_YAML=1` exercises it.
- `wckd handoff <slug> [--step] [--role] [--inline] [--format md|json]` — a self-contained role prompt: SOUL,
  the role's rules and prohibitions, the open gate's criteria, the input paths, the output path and the JSON
  Schema, in one block. This is what makes a chat-only model a protocol participant.
- **MCP server** (`bin/wckd_mcp.py`, stdio JSON-RPC): 12 tools — projects, new, next, status, validate,
  handoff, gate, close, score, read/write artifact, protocol. Same rules, different transport.
- **HTTP mode** (`wckd serve`): `/health`, `/protocol`, `/projects`, `/projects/<slug>/{status,next,score,
  handoff,artifacts/*}`, POST artifacts and gates, optional bearer token.
- **`wckd run --agent "<cmd>"`** — the orchestrator: takes the next step, renders the handoff, pipes it to any
  command, validates what comes back, records non-human gates, stops at human gates and when an agent stalls.

**Protocol substance**

- Tolerances are data, not code: gates read `machine/protocol.json#tolerances`, so every implementation gates
  at the same numbers (5 source classes, 3 candidates, 3 lessons, 3 failure modes, reuse ≥0.60, opex +10 %).
- `workflows/campaigns.yaml` — minimum adversarial coverage per realm at G-D3 (digital: security, abuse, edge,
  load, chaos, cost; physical adds physical stress and supply chain). Enforced.
- `workflows/physical.yaml` — certification matrix by market, DFM checklist, sourcing and second-source rule,
  pilot batch gate, calibration traceability, recall rehearsal, end-of-life. Enforced where machine-checkable:
  G-K (certification targets, serviceability, hazard analysis with controls, unit cost with MOQ and lead time,
  certification NRE), G-D4 (pilot batch size, QC plan, serials, rehearsed repair/recall), G-D5 (spares,
  recalibration cadence), G-D3 (campaign categories for the realm).
- `blueprint.hazard_analysis` added: every hazard carries severity, likelihood and a control.
- `landscape.graveyard_note` added so "this space has no history" is expressible instead of silently passing.
- **`wckd conformance`** — 16 language-independent cases (shipped artifacts must pass, mutants must fail) run
  against the standalone schemas only.

**Fixed**

- G-D5 crashed with `KeyError: 'lessons.md'` on every project that reached Kept.
- `wckd status | head` traced back on SIGPIPE.

Tests: 45 (gate rules, a full synthetic W→D5 lifecycle, the run loop, MCP, HTTP, physical refusals, manifest
and conformance). CI covers Python 3.10–3.12 plus a stdlib-only job.

## 1.0.1 — the protocol made to pass its own gates

- KILL and WAIT became recordable terminal decisions; conditions block their due gate and can be closed.
- G-C got teeth (source classes, candidates, trials, coverage, freshness, Graveyard).
- Gate criteria that were written but unenforced are now checked (G-W, G-K, G-D4, G-D5, reuse arithmetic).
- The worked example was re-canvassed with real sources and now passes its own G2 rule.
- `wckd score` (GOALS G1–G12, `--ledger` append-only row), `wckd close`, CI, docs site.

## 1.0.0 — as delivered

Protocol, seventeen roles, eight gates, schemas, workflows, a worked example and a reference CLI.
