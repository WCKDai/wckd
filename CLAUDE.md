# WCKD — instructions for Claude Code / Cowork in this repo

You are operating inside the WCKD protocol. Before anything else, read `SOUL.md`, then `GOALS.md`, then `SKILLS.md`. Your role for a given step is the agent file the Conductor hands you under `agents/`; stay inside that role's `skills` and `may_not` lists.

Rules that override everything else in this session:
1. No building before `gates/G-C.json` says PASS. Canvass first, always.
2. Verdicts are per capability. BUILD needs `why_not_keep` and `why_not_bend`.
3. Builder ≠ Validator ≠ Breaker on any work order. Never prove your own work.
4. Every claim that crosses an agent boundary carries evidence (`schemas/common.schema.json#/$defs/evidence`).
5. Every cost carries a confidence class. Run cost is a number.
6. Gates G-W, G-K and G-D4 need the human.

Workflow: `python bin/wckd.py next <slug>` tells you who runs next and what to write. Validate with `python bin/wckd.py validate <slug>` before handing off. Agent definitions in `agents/` are already in subagent frontmatter format and can be copied into `.claude/agents/`.
