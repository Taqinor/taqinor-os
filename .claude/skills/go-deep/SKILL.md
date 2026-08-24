---
name: go-deep
description: House doctrine for deep investigations at three calibrated levels — "go deep" (L1), "go very deep" (L2), "go extremely deep" (L3) — with automatic level pick when Reda names none, and adaptive rounds (understand → dig → validate → final review). Invoke when those phrases appear (the prompt hook injects the detected level) or whenever a substantive audit/investigation needs calibrated depth.
---

# Go-deep — three levels, adaptive rounds

Depth adapts to the QUESTION, never to how emphatic the ask was. Depth is bought with
per-lane thoroughness and verification rigor; lane COUNT comes only from how many
genuinely independent surfaces the question has. (Anthropic's own production guidance:
scale agent count to query complexity — a simple fact-find is ONE agent; multi-agent
depth can cost up to ~15× a single chat, so it is reserved for value that covers it.)

## Level pick — automatic when Reda names none

Score the request on three axes, then announce the pick in ONE line
(« Niveau choisi : L2 — enjeux client-facing, 4 surfaces ») and proceed:

- **STAKES** — does it touch money numbers, client-facing output, auth/security, prod
  data, or an irreversible decision? Any checked-facts surface (numbers a client sees)
  is automatically ≥ L2.
- **BREADTH** — how many genuinely independent surfaces (files / domains / flows)?
- **UNCERTAINTY** — known-but-unverified ground (low) vs genuinely unknown/contested (high)?

Pick: **L1** = low stakes, ≤3 surfaces, or a confirmation pass. **L2** = real stakes OR
4-8 surfaces OR contested ground. **L3** = high stakes AND (broad OR contested) — the
« best in the world » class of ask. Reda's explicitly named level ALWAYS overrides the
auto-pick. If R1 reveals higher stakes than scored (e.g. an invented client-facing
number), escalate one level mid-run and SAY so in one line.

## The round skeleton (founder model — adaptive, not fixed)

- **R1 COMPRENDRE** — map the problem: targeted reads/research that enumerate the REAL
  problems, each with a file/fact reference. No fixes yet. Output = numbered problem list.
- **R2 CREUSER** — one lane per independent surface digs its problems to root cause and
  a concrete solution.
- **R3 VALIDER** — adversarial verification of EVERY finding and proposed solution
  against the real code, rendered output, or an executed check — never against a summary
  and never by the author agent (official guidance: fresh-context verifiers outperform
  self-critique).
- **R4 REVUE FINALE** — one completeness critic (« what's missing — a surface not
  covered, a claim unverified, a source unread? ») + synthesis + plain-language report.

Rounds are ADAPTIVE: a round that adds nothing new is « dry » — advance (or stop at the
level's dry-cap). A small question compresses R1+R2 into one pass; a hard one repeats
R2↔R3 until dry. Whatever the completeness critic finds becomes the next round's work —
that is how runs grow beyond 4 rounds when the material demands it.

## The levels

| | **L1 « go deep »** | **L2 « go very deep »** | **L3 « go extremely deep »** |
|---|---|---|---|
| Lanes | ≤ ~4 (surfaces merged) | one per surface, ≤ ~8-10 | one per surface, ≤ ~10-12 |
| Workers | sonnet effort medium-high; haiku scouts low | sonnet high; opus on high-risk surfaces | sonnet/opus high; opus on every high-risk surface |
| R3 rigor | 1 fresh verifier per finding | 2 independent verifiers on critical findings (different lenses) | 2-3 lenses per finding (always incl. a checked-facts lens on anything client-facing); loop-until-dry — stop only after 2 consecutive rounds finding nothing new |
| Fable budget | 0 | 1 — the final completeness critic | up to the house 1-3/run cap: adjudication, completeness critic, decisive synthesis — each with its DONE-LOG line |
| Round caps | ~2 discovery rounds | ~3 | until dry (hard cap ~5), plus interval verification DURING any long build phase |
| Typical total agents | ~3-7 | ~8-15 | ~15-35 |

## Non-negotiables at every level (CLAUDE.md, restated)

- **Sizing**: lanes = independent surfaces (378 numbers over 9 surfaces = ~9-12 lanes,
  never 161). Escalation buys DEPTH per lane — more rounds, higher effort, adversarial
  re-reads — never more lanes.
- **Every subagent carries an explicit `model:` + effort.** Never inherit the session
  model (and `CLAUDE_CODE_SUBAGENT_MODEL` stays UNSET — it would override the tags).
- **Grounding block verbatim in every agent prompt** (CLAUDE.md « Fleet quality &
  economics »); every done/found claim cites its evidence (file:line, command output,
  commit SHA).
- **Reviewer calibration**: correctness/spec findings only; style and hypothetical
  hardening are OPTIONAL, reported separately; checked-facts / zero-invented-number
  findings are ALWAYS correctness. TRIAGE (classify → decide) before dispatching any
  corrector fleet — never « fix all N » blindly.
- **Read-only fleets**: same-directory Workflow fan-outs (prompt cache is per directory —
  siblings read the first agent's prefix at ~10% rate), never worktrees. A big audit is
  ONE workflow (crash/stop in-session → completed agents replay from cache). Resume an
  agent only to DEEPEN its own lane; adversarial round-2 is always a FRESH agent.
- **Verify against the REAL rendered or executed output** — never a green build alone.
- **Report** covers what was checked AND what was NOT covered (no silent caps), with
  verified/refuted counts, in plain language for Reda.

Sources (verified 2026-08-24): official Claude Code docs — sub-agents (model/effort
precedence), workflows (fan-out cache stagger, resume), best-practices (reviewer
calibration, verification ladder), prompting-claude-fable-5 (fresh-context verifiers,
interval verification, grounding block); Anthropic engineering — multi-agent research
system (agent count scales with query complexity; ~15× token multiplier).
