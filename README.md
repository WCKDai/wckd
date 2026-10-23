# WCKD Protocol

*Pronounced "wicked."* **W**ant → **C**anvass → **K**eep/Kill → **D**eliver.

WCKD is a workflow for getting anything made — software, hardware, a product, an operation, a plan — by a set of specialized agents, with one rule baked into the name:

> **We don't build what already works. We don't fix what isn't broken.
> We build only the gap between what exists and the Bar.**

You name a want. A council learns what already exists, what works, what doesn't and why the dead attempts died. It judges every capability KEEP / BEND / BUILD / WAIT / KILL, designs only the gap, prices it (build, run, unit, exit — physical and digital), sizes the prospect and plans it. Crews then build it, prove it, break it, ship it and keep it running, with operating costs tracked against the plan.

A build that could have been a download, a purchase or a configuration change is a failure, even if it works.

## The four letters

|   | Phase | The question | Produces |
|---|---|---|---|
| **W** | Want | What do we want, to what standard? | `brief.json` — capabilities + **the Bar** |
| **C** | Canvass | What exists? What works? What died, and why? | `landscape.json` — candidates + **the Graveyard** |
| **K** | Keep / Kill | Per capability: keep, bend, build, wait or kill? | `verdict.json` + `blueprint` `cost` `prospect` `plan` |
| **D** | Deliver | Build → Prove → Harden → Ship → Keep | `workorders/` `proofs/` `breaches/` `release` `runbook` → `memory/` |

## The eight gates

| Gate | Phase | The question | Human veto |
|---|---|---|---|
| **G-W Briefed** | W | Is the want measurable, and is the Bar written? | **yes** |
| **G-C Canvassed** | C | Did we look wide, try things, and mine the Graveyard? | no |
| **G-K Judged** | K | Is every capability judged, only the gap designed, everything priced? | **yes** |
| **G-D1 Built** | D | Does every work order have a build log? | no |
| **G-D2 Proven** | D | Was it proved independently, from clean, against the Bar? | no |
| **G-D3 Hardened** | D | Was it attacked, and is every finding dispositioned? | no |
| **G-D4 Shipped** | D | Is the rollback rehearsed and monitoring live? | **yes** |
| **G-D5 Kept** | D | Owner, SLOs, opex, lessons, ledger row? | no |

Full criteria and required evidence: `workflows/gates.yaml`. KILL and WAIT are terminal decisions available at any gate, any time.

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

## Quickstart

```bash
pip install pyyaml jsonschema
make test                                    # 47 tests: gates, lifecycle, run loop, MCP, HTTP, both realms
ln -sf "$PWD/bin/wckd.py" ~/.local/bin/wckd  # or: python bin/wckd.py <cmd>

wckd new aqm "A home air-quality monitor that alerts my phone"
wckd next aqm                                # who runs next, what to hand them, what to write
wckd validate aqm                            # every artifact checked against schemas/
wckd gate aqm G-W --by "your name" --human   # human-veto gates: G-W, G-K, G-D4
wckd score aqm                               # GOALS.md G1–G12 scored from the artifacts
wckd status aqm
```

`next` prints the agent file, the inputs it must read and the artifact it must write. Hand that to any runtime — a Claude Code subagent, a Cowork task, a scheduled job, a person.

```bash
# the other outcomes the protocol needs
wckd gate aqm G-K --by "you" --decision KILL --note "space already solved; nothing to build"
wckd gate aqm G-K --by "you" --human --decision PASS_WITH_CONDITIONS \
     --condition "name the CO2 calibration source|barkeeper|G-D4"
wckd close aqm G-K 1 --by barkeeper          # close the condition when it is met
wckd score aqm --ledger --by Scribe          # append the row to memory/LEDGER.md (append-only)
```

## What the CLI actually enforces

Not vibes — the rules that can be checked mechanically:

- phase order: no gate before its predecessors, no build before a Canvassed PASS;
- artifact validity against `schemas/` (JSON Schema 2020-12), with sha256 of everything a gate checked;
- **G-C canvass teeth:** ≥5 source classes and ≥3 candidates per capability, or a proven absence; a trial or a
  stated reason; a coverage row naming a best fit or a precise gap; fresh checks; a non-empty Graveyard or an
  explicit note that the space has no history;
- **G-K:** a verdict per capability, blueprint scope free of KEEP, `reuse_ratio` arithmetic, cost inside the
  ceiling or a signed change, kill criteria, pre-mortem with ≥3 failure modes, crew independence;
- **G-D2** independence (`validator ≠ builder` plus the attestation), **G-D3** no open crit/high findings,
  **G-D4** rollback drill + monitoring + cost re-estimate, **G-D5** owner, SLO alerts, re-entry triggers, ≥3 lessons;
- open `PASS_WITH_CONDITIONS` conditions block the gate they are due at;
- human sign-off required at G-W, G-K, G-D4 — and refused when absent.

What the CLI cannot check (graveyard substance, provenance hashes, message conformance) the Conductor must read.

## Deploy it on any agent

The rules live in files; the gates live in one CLI. Any of these transports is a full participant:

| Transport | Use it for | Start |
|---|---|---|
| **CLI** | a shell, a person, a script | `bin/wckd.py` (stdlib only) |
| **Handoff prompt** | any model that only reads text | `wckd handoff aqm --inline` → one block: SOUL, the role, the open gate's criteria, inputs, output path, JSON Schema |
| **MCP** | Claude Desktop/Code, Cursor, Windsurf, any MCP client | `{"mcpServers":{"wckd":{"command":"python3","args":["/path/to/wckd/bin/wckd_mcp.py"]}}}` — 12 tools |
| **HTTP** | a custom loop, n8n, a service | `wckd serve --port 8787 [--token X]` |
| **Orchestrated** | "run the protocol against my agent" | `wckd run aqm --agent "claude -p"` (or `codex exec`, an API wrapper, a person) |

`wckd run` takes the next step, renders the handoff, pipes it to your command with `WCKD_STEP`/`WCKD_ROLE`/
`WCKD_GATE` in the environment, validates what comes back, records the gates it may record, and **stops at
G-W, G-K and G-D4** for a human — it never signs for you.

**The machine contract.** `machine/` is the protocol compiled to JSON by `wckd manifest`: `protocol.json`
(phases, steps, gates, roles, vocabulary, tolerances, campaigns, physical obligations), `agents.json`, a
self-contained JSON Schema per artifact, and `schemas.bundle.json`. Implement WCKD in any language against
that, and run `wckd conformance` (16 language-independent cases: shipped artifacts must pass, mutants must
fail) to prove the schemas agree.

**No dependencies.** PyYAML is optional (the committed manifest is used instead) and jsonschema is optional
(required-key fallback). `WCKD_NO_YAML=1` exercises the stdlib-only path; CI runs it on every push.

## Digital and physical obligations

The same eight gates in both realms; each carries obligations a generic reading would miss.

**Digital** (`workflows/digital.yaml`): run cost is itemised line by line (compute, storage, egress, licences,
SaaS, support, patching), every KEEP decision carries a priced exit line, kept dependencies are watched in the
runbook, environments are named before cutover, and the release has a rehearsed rollback.

**Physical** (`workflows/physical.yaml`):

- **G-K** — certification targets per market, serviceability, a hazard analysis where every hazard has a
  control, unit cost at the planned volume with MOQ and lead-time notes, certification priced as NRE.
- **G-D3** — campaigns for physical stress, abuse, supply chain and cost (plus security when there is
  firmware), on units from more than one batch, with a cost campaign compared to the ledger.
- **G-D4** — a pilot batch of at least five, a QC sampling plan, serial tracking, and a repair/recall path
  rehearsed to a pass on real units.
- **G-D5** — spares and consumables, recalibration in the maintenance cadence, an end-of-life plan.

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
├── machine/             the protocol compiled to JSON: protocol, agents, standalone schemas, bundle
├── tests/               gate rules, a full lifecycle, the run loop, MCP, HTTP, physical refusals
├── CHANGELOG.md         what changed, and why
├── DEFECTS.md           this build audited against its own spec
├── projects/            your runs live here
└── bin/                 wckd.py (CLI) · wckd_mcp.py (MCP server)
```

## Plugging into a runtime

- **Claude Code / Cowork.** Copy `agents/*.md` into `.claude/agents/` — the frontmatter is already subagent format. Put `SOUL.md` at the top of `CLAUDE.md`. Point the Conductor at `bin/wckd.py`.
- **Any orchestrator / message bus.** `connections/connections.yaml` defines topics and handoffs; `schemas/message.schema.json` is the envelope every message must satisfy.
- **No automation at all.** The artifacts and gates *are* the protocol. A team of humans running it from this folder is fully conformant.

## Conformance

An implementation is WCKD-compliant when it satisfies `PROTOCOL.md §15`. The short version: no build before Canvassed; verdicts per capability; builder ≠ validator ≠ breaker; every gate has evidence; every cost has a confidence class; every project writes lessons.

## Status

Protocol v1.0, orchestrator v1.1.0. The delivered v1.0 was audited against its own spec (see `DEFECTS.md`) and
then made portable: a compiled JSON contract in `machine/`, a self-contained handoff prompt, an MCP server, an
HTTP mode, an orchestrator that can drive any agent, and enforced physical obligations. `CHANGELOG.md` has the
detail; `DEFECTS.md` has what is still left to the Conductor by design.

## License

MIT.
