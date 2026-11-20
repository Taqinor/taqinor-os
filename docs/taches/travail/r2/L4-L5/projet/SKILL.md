---
name: go-deep
description: House doctrine for calibrated depth at five levels, each starting with a regime probe (NEW / EXISTING / MIXED, read on origin/main). L1 "go deep" / "go L1" — a quick verified investigation of a few surfaces. L2 "go very deep" / "go L2" — real stakes or 4-8 surfaces, two verifiers on critical findings. L3 "go extremely deep" / "go L3" — high stakes and broad or contested ground, loop until dry. L4 "go L4" / "go ship-grade" — only when Reda names it, rounds of fresh reviewers on the real running product until a numeric exit contract is met. L5 "go L5" / "go all the way" — only when Reda names it, a multi-session campaign adding freeze-before-touch, a real-life stage and class guards. The auto-pick chooses only L1-L3 and proposes L4/L5 with their cost; invoke when those phrases appear (the prompt hook injects the level) or whenever a substantive audit/investigation needs calibrated depth.
---

# Go-deep — five levels, adaptive rounds

Depth adapts to the QUESTION, never to how emphatic the ask was. Depth is bought with
per-lane thoroughness and verification rigor; lane COUNT comes only from how many
genuinely independent surfaces the question has. (Anthropic's own production guidance:
scale agent count to query complexity — a simple fact-find is ONE agent; multi-agent
depth can cost up to ~15× a single chat, so it is reserved for value that covers it.)
L1-L3 UNDERSTAND (investigate, verify, report). L4-L5 SHIP (change the product until a written
contract is met): their procedures live in `L4.md` and `L5.md` next to this file, their
templates in `gabarits/`, and every choice with its source in `conception.md`.

## Regime — detected before any level runs

Building NEW invents or over-specifies (a first PR of 324 files); improving EXISTING breaks
what works (3 then 2 regressions in the 19-20/11 rounds). The regime fixes the ORDER of steps
and the PROOF demanded; the level fixes the volume. Commands: `gabarits/regime.md`.

- **Read `origin/main`, never the worktree** (`git fetch origin main` first): a stale worktree
  showed 0 files for a module that had 344 on `main`.
- **Search the whole tree** (`.claude/`, `scripts/`, `docs/`, apps, front) by the request's
  names AND their synonyms (widget / tuile, task / tâche). A request about a tool or method
  (a skill, a script, a CI job) is classed by the same rule on the artifact it targets.
- **Decision = promises already served**, P = (served + ½ partial) / total. **NEW**: P < 20 %,
  no module and no host found under the names (homonyms do not count), no plan task ticked
  beyond scaffolding. **EXISTING**: P > 80 %.
  **MIXED**: everything else, contradictory signals included — the rule is total. 20 / 80 % are
  starting values, not calibrated: log P and the verdict.
- A plain question that builds and changes nothing gets the regime line without the promise
  list.
- **One line, then proceed**: « Régime : EXISTANT · L2 · origin/main@<sha9> — <n> fichiers,
  promesses servies <s>/<t>. Dis « neuf / mixte / existant » pour imposer. » Reda's word
  overrides; switch mid-run, in one line, the moment R1 contradicts the class.
- At L1-L3 the regime steers R1 and R3: NEW → from the request, references and contracts;
  EXISTING → from `origin/main` code and the real output, R3 replays on the running product;
  MIXED → the touched surface and its pattern file only.

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
number), escalate one level mid-run and SAY so in one line — never past L3.
**The auto-pick never chooses L4 or L5.** For a ship-grade ask (« several rounds », « make it
the best », a « done » module to polish) it runs at most L3 and PROPOSES once, in one line:
« L4 possible : <k> tours permis par le quota (<u> % utilisé) — dis « go L4 » ». When the hook
says several levels or an ambiguous mention were cited, read Reda's own sentence and follow it.

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

L4 and L5 are not more of the same: they change the product. Their summaries follow; their
numbers, caps and steps are in `L4.md` / `L5.md`.

## L4 « ship-grade » — summary (read `L4.md` in full before tour 0)

- **What**: tour 0 writes a numeric exit contract; then rounds of fresh reviewers USE the real
  running product on a private review instrument; a consolidation checks every finding against
  the code and names defect classes; file-disjoint lanes fix; fresh reviewers counter-verify;
  CI gates; the work merges by waves — until the contract is met or a cap stops it.
- **When**: only when Reda names it. Typical case: a module « done » by plan, CI and acceptance
  that still fails its users on the real screen (152 findings at round 1 on 19-20/11).
- **Cost**: measured once — tour 0 + 3 rounds + final ≈ 74 points of the weekly quota (6 → 80 %,
  part of it another session's), 16 reviewers, ≈ 40 fix agents (run retro §3, `conception.md`).
  Rounds allowed come from the quota formula in `L4.md` (starting values, not calibrated); the final verification
  and the server-diff critique have their own reserve and always run before the merge.
- **Needs**: a desktop session (quota readable), a local Docker for the instrument, an owner
  plan for the corrections. No instrument (cloud session) → no L4: L3 plus METHODE §C.4.7
  runner specs, and say so.
- **Do not expect**: a dry round (the curve went 152 → 78 → 27 fixed « avant le merge » → 2
  blockers, never zero); anything seen on a real device or over a real week (that is L5);
  a deploy (Claude stops at the merge).

## L5 « all the way » — summary (read `L4.md`, then `L5.md`, before tour 0)

- **What**: L4 plus what L4 cannot do — freeze served behaviour before touching it, class guards
  proved red on the original defect, proven journeys turned into acceptance specs, iPhone journeys
  replayed under WebKit, a simulated week for rhythm modules, a real-life stage with Reda, and a
  read-only look at prod after Reda's deploy. Estimates of what remains are experiments only.
- **When**: only when Reda names it. It spans several sessions BY NATURE (days of real use,
  weekly quota windows); each session ends at a merge; the state file is the resume point.
- **Cost**: not measured. Known extras: a freeze lane, extra reviewers, Reda's time on a real
  device, at least two weekly windows. Say « coût non mesuré » in the cost line.
- **Not worth it** when the scope is small or rarely used, no real user or device exists, L4's
  last round already met the contract, the module will be replaced soon, or the quota allows
  fewer than 2 rounds.
- **Do not expect**: the real-life stage without Reda's gestures (deploy, flag, his device).

## Guardrails common to L4 and L5

- **Never prod, never a deploy, never another session's stack**: the instrument serves only
  pushed code, mail forced to console, no real key — its tour-0 control STOPS the run otherwise
  (`gabarits/instrument-de-revue.md`). Never start Docker « to see ».
- **Cost line before tour 0**, quota read with `mcp__ccd_session_mgmt__get_usage` (« Weekly · all
  models »); unreadable → tour 0 only and the cost line asks Reda for the figure.
- **State pushed at every checkpoint** (`gabarits/etat.md`): worktrees idle for 7 days are deleted
  by the nightly cleanup, and context ≥ 70 % means write the state before continuing.
- **Fable** only in CLAUDE.md's cases (a)(b)(c); the orchestrator keeps the session model (never
  switch `/model` mid-session) — start an L4 in an opus session when you can.
- Corrections land in the OWNER's plan, in that plan's format (`L4.md` « Where corrections go »).

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
  corrector fleet — never « fix all N » blindly. In L4/L5 the exit contract IS the spec.
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
system (agent count scales with query complexity; ~15× token multiplier). L4/L5 and the
regime probe: designed 2026-11-20 from the measured 19-20/11 rounds and six research lanes,
checked by three fresh verifiers — each choice, its source and its status in `conception.md`.
