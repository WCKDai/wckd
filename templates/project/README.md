# Project folder layout

`wckd new <slug> "<wish>"` creates this structure under `projects/<slug>/`. Every file validates against `schemas/`.

```
projects/<slug>/
├── wish.json          W   verbatim want                       schemas/wish.schema.json
├── brief.json         W   capabilities + Bar + done condition  schemas/brief.schema.json
├── landscape.json     C   candidates, graveyard, coverage      schemas/landscape.schema.json
├── verdict.json       K   per-capability verdicts              schemas/verdict.schema.json
├── blueprint.json     K   the gap, designed                    schemas/blueprint.schema.json
├── cost.json          K   build / run / unit / exit / not-doing schemas/cost.schema.json
├── prospect.json      K   demand, ROI, risks, tripwires        schemas/prospect.schema.json
├── plan.json          K   WBS, crews, pre-mortem               schemas/plan.schema.json
├── workorders/        D   WO-001.json ...                      schemas/workorder.schema.json
├── proofs/            D   WO-001.proof.json ...                schemas/validation.schema.json
├── breaches/          D   BR-001.json ...                      schemas/break.schema.json
├── release.json       D   rollout + rollback drill             schemas/release.schema.json
├── runbook.json       D   operation                            schemas/runbook.schema.json
├── lessons.md         D   retro output (appended to memory/)
├── gates/             *   G-W.json ... G-D5.json               schemas/gate.schema.json
└── messages/          *   optional message log                 schemas/message.schema.json
```

Nothing in `K` may be written before `gates/G-C.json` says PASS. Nothing in `D` before `gates/G-K.json`. The CLI enforces this.
