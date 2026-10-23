# GOALS.md

*What winning means for WCKD, with numbers. The Conductor scores every project against this table at the Kept gate and writes the score to `memory/LEDGER.md`. Trends across projects drive protocol revisions.*

## North Star

Any want, named by a human, becomes a working, priced, kept thing — or a well-documented kill — with the least new work the world requires.

## Protocol goals

| # | Goal | Metric | Target | Scored at |
|---|---|---|---|---|
| G1 | Reuse before build | Reuse ratio = (KEEP + BEND) ÷ all capability verdicts | ≥ 0.60 | G-K |
| G2 | Nothing built blind | Source classes searched per capability; candidates evaluated per capability | ≥ 5 classes; ≥ 3 candidates or a proven absence | G-C |
| G3 | Honest kills | Share of wants ending KILL or WAIT, across the portfolio | 0.15 – 0.40 | portfolio |
| G4 | Priced truth | Actual vs. definitive estimate, 90 days after Kept | build ±25 %, run ±15 % | G-D5 + 90 d |
| G5 | Proven, not promised | Defects escaping after the Proven gate | 0 CRIT, 0 HIGH | G-D5 + 90 d |
| G6 | Broken before shipped | Breaker findings dispositioned (fixed or formally accepted) before Shipped | 100 % | G-D4 |
| G7 | Reversible delivery | Rollback or recall drill executed and passed before Shipped | 100 % | G-D4 |
| G8 | Kept, not abandoned | Runbook, owner, SLOs and opex budget exist; opex vs. budget | 100 %; ≤ budget + 10 % | G-D5 + 90 d |
| G9 | Memory compounds | Lessons written this project; lessons read at the next Canvass | ≥ 3 written; 100 % read | G-D5 / next G-C |
| G10 | Human in control | Gates with a recorded human decision | 100 % of G-W, G-K, G-D4 | each gate |
| G11 | The Bar holds | Bar changes after G-W, each signed | 100 % signed; ≤ 2 per project | G-D5 |
| G12 | Tried, not read | Top candidates actually installed, run or sampled during Canvass | ≥ 1 per capability where feasible | G-C |

Interpretation notes:
- G1 below 0.4 across several projects means Canvass is weak or the Judge is building for sport.
- G3 at 0 means the Judge is a rubber stamp. G3 above 0.5 means Want is producing bad briefs.
- G4 is measured against the *definitive* estimate issued at G-K, not the first rough order of magnitude.

## Phase exit goals

- **W — Briefed.** A stranger could read the brief and know what done looks like and how to measure it. Budget ceiling and horizon are explicit. Memory was consulted.
- **C — Canvassed.** We know what exists, what we tried, what works, what doesn't, and why the dead attempts died. Every capability has a best fit or a proven gap.
- **K — Judged.** Every capability has a verdict with evidence. Only the gap is designed. Build, run, unit and exit costs carry confidence classes. The prospect has kill criteria. The plan has a pre-mortem.
- **D — Delivered.** Built in increments; proven independently from clean; hardened against an adversary; shipped reversibly; kept with SLOs, an owner and a budget; lessons written.

## Anti-goals

Things that look like progress and aren't:

- Speed that skips Canvass.
- Building to impress.
- Perfect beyond the Bar.
- Costs hidden in "later."
- Agents validating themselves.
- A Judge that never kills.
- A Bar that moves to fit the answer.
- A Graveyard nobody reads.

## How goals change

SOUL.md and GOALS.md change only through the protocol itself: a want ("change goal G3's band"), a Canvass (what do other teams and standards do?), a Verdict, and a human signature at G-K. The protocol eats its own cooking.
