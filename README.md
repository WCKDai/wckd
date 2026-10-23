# WCKD Protocol

*Pronounced "wicked."* **W**ant → **C**anvass → **K**eep/Kill → **D**eliver.

WCKD is a workflow for getting anything made — software, hardware, a product, an operation, a plan — by a set of specialized agents, with one rule baked into the name:

> **We don't build what already works. We don't fix what isn't broken.
> We build only the gap between what exists and the Bar.**

You name a want. A council learns what already exists, what works, what doesn't and why the dead attempts died. It judges every capability KEEP / BEND / BUILD / WAIT / KILL, designs only the gap, prices it (build, run, unit, exit — physical and digital), sizes the prospect and plans it. Crews then build it, prove it, break it, ship it and keep it running, with operating costs tracked against the plan.

## The four letters

|   | Phase | The question | Produces |
|---|---|---|---|
| **W** | Want | What do we want, to what standard? | `brief.json` — capabilities + **the Bar** |
| **C** | Canvass | What exists? What works? What died, and why? | `landscape.json` — candidates + **the Graveyard** |
| **K** | Keep / Kill | Per capability: keep, bend, build, wait or kill? | `verdict.json` + `blueprint` `cost` `prospect` `plan` |
| **D** | Deliver | Build → Prove → Harden → Ship → Keep | `workorders/` `proofs/` `breaches/` `release` `runbook` → `memory/` |

Eight gates, each with written criteria and required evidence (`workflows/gates.yaml`). A human holds the veto at **Briefed**, **Judged** and **Shipped**.

## The seventeen roles

| Phase | Role | One line |
|---|---|---|
| all | **Conductor** | Runs the protocol. Enforces order and gates. Routes. Escalates. Does no domain work. |
| all | **Scribe** | Ledger, provenance, retros, lessons. Makes the next project cheaper. |
| W | **Listener** | Turns a one-line wish into a brief with capabilities and a done condition. |
| W | **Barkeeper** | Sets the Bar: thresholds and how each will be measured. Guards it afterwards. |
| C | **Scout** | Finds everything that exists, across ≥5 source classes. Tries the top candidates. |
| C | **Appraiser** | What works, what doesn't, why. Scores fit against the Bar. Mines failures into the Graveyard. |
| C | **Cartographer** | Assembles the landscape: coverage, gaps, proven absences. |
| K | **Judge** | Issues verdicts per capability. BUILD must justify why not KEEP or BEND. Kills when warranted. |
| K | **Architect** | Designs the gap only. Interfaces to kept parts. ADRs. Reversibility. |
| K | **Quartermaster** | Build, run, unit and exit costs with confidence classes. Physical and digital. |
| K | **Prospector** | Demand, ROI, risks, regulation, timing, kill criteria, tripwires. |
| K | **Planner** | Work breakdown, milestones, critical path, crews, pre-mortem. |
| D | **Builder** | Builds work orders in small increments, to spec. Never proves its own work. |
| D | **Validator** | Independent proof from a clean environment, against spec and Bar. |
| D | **Breaker** | Adversary: security, abuse, load, chaos, physical stress, cost blow-ups. |
| D | **Shipper** | Rollout strategy, rollback drill, pilot batch / manufacturing handoff, go/no-go. |
| D | **Keeper** | Runbook, SLOs, maintenance cadence, opex tracking, drift detection, re-entry triggers. |

## Layout

```
wckd/
├── README.md            this file
├── SOUL.md              who the agents are; what they will never do
├── GOALS.md             what winning means, with numbers
├── SKILLS.md            every skill an agent can invoke
├── PROTOCOL.md          the formal spec: phases, gates, verdicts, evidence, cost rules
├── workflows/
│   ├── wckd.workflow.yaml   the pipeline: phases → steps → agents → artifacts
│   ├── gates.yaml           criteria, evidence and sign-off for all eight gates
│   └── loops.yaml           build/prove/break loop and re-entry triggers
├── agents/              one prompt per role (Claude Code subagent frontmatter)
├── schemas/             JSON Schema (2020-12) for every artifact that crosses an agent boundary
├── connections/
│   ├── connections.yaml     topics, handoffs, broadcasts, escalation, turnaround
│   └── tools.yaml           tool classes and which roles may use them
├── memory/
│   ├── LEDGER.md            append-only record of every project and its scores
│   └── LESSONS.md           read at the start of every Canvass
├── templates/project/   what a new project folder looks like
├── examples/air-quality-monitor/   a worked W → C → K run (reuse ratio 0.83)
├── projects/            your runs live here
└── bin/wckd.py          reference orchestrator: new / next / validate / gate / status
```

## Run a project

```bash
pip install pyyaml jsonschema
python bin/wckd.py new aqm "A home air-quality monitor that alerts my phone"
python bin/wckd.py next aqm       # who runs next, and the exact prompt to hand them
python bin/wckd.py validate aqm   # every artifact checked against schemas/
python bin/wckd.py gate aqm G-W --by "your name" --human
python bin/wckd.py status aqm
```

`next` prints the agent file, the inputs it must read and the artifact it must write. Hand that to any runtime — a Claude Code subagent, a Cowork task, a scheduled job, a person. The CLI refuses to record a gate when artifacts are missing or invalid, and refuses to skip phases.

## Plugging into a runtime

- **Claude Code / Cowork.** Copy `agents/*.md` into `.claude/agents/` — the frontmatter is already subagent format. Put `SOUL.md` at the top of `CLAUDE.md`. Point the Conductor at `bin/wckd.py`.
- **Any orchestrator / message bus.** `connections/connections.yaml` defines topics and handoffs; `schemas/message.schema.json` is the envelope every message must satisfy.
- **No automation at all.** The artifacts and gates *are* the protocol. A team of humans running it from this folder is fully conformant.

## Conformance

An implementation is WCKD-compliant when it satisfies `PROTOCOL.md §15`. The short version: no build before Canvassed; verdicts per capability; builder ≠ validator ≠ breaker; every gate has evidence; every cost has a confidence class; every project writes lessons.
