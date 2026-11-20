---
name: go-deep
description: House doctrine for calibrated depth at five levels — "go deep" / "go L1" (L1), "go very deep" / "go L2" (L2), "go extremely deep" / "go L3" (L3), "go L4" / "go ship-grade" (L4, ship-grade loop — rounds of fresh reviewers on the REAL running product, fixes landed by file-disjoint lanes and counter-verified by fresh agents, until a numeric exit contract written at tour 0 is met), "go L5" / "go all the way" (L5, campaign — L4 plus freeze-before-touch, an estimate of what remains, independent judges, a real-life stage and a guard per defect class, across sessions with state on disk). Every level first detects the regime (NEW / EXISTING / MIXED, read on origin/main). The automatic pick chooses only L1-L3 and PROPOSES L4/L5 with their cost. Invoke when those phrases appear (the prompt hook injects the level) or whenever a substantive audit/investigation/review needs calibrated depth.
---

# Go-deep — five levels, one regime probe

Depth adapts to the QUESTION, never to how emphatic the ask was. Depth is bought with
per-lane thoroughness and verification rigor; lane COUNT comes only from how many
genuinely independent surfaces the question has. (Anthropic's own production guidance:
scale agent count to query complexity — a simple fact-find is ONE agent; multi-agent
depth can cost up to ~15× a single chat, so it is reserved for value that covers it.)
L1-L3 UNDERSTAND (investigate, verify, report); L4-L5 SHIP (change the product until a written
contract is met). Files named below without a path live in `gabarits/` next to this file.

## Regime — detected before any level runs

EXISTING breaks what works (3 then 2 regressions, ≈ 25 % of « proven » fixes half-done in the
19-20/11 rounds); NEW invents or over-specifies (a first PR of 324 files). The regime fixes the
ORDER of steps and the PROOF demanded; the level fixes the volume. Commands: `regime.md`.

- **Read `origin/main`, never the worktree** (`git fetch origin main` first): a stale worktree
  showed 0 files for a module that had 344 on `main`.
- **Signals** (seconds, light identifiers): files under `apps/<m>/`, `features|pages/<m>/` and a
  plan named after it with `[x]` ticked (strong); its tests and e2e specs; an owner in
  `docs/ownership.yml`; CODEMAP mentions (hint only — « copilote »: 11 mentions, 0 files under
  that name). Request verbs (« ajoute » vs « améliore / refais ») are hints, never the decision.
- **Decision = promises already served.** Split the request into 5-15 promises; for each, the
  route / screen / action / test serving it, else absent; « partial » if the gesture exists but
  not the asked case. P = (served + ½ partial) / total. **NEW**: P < 20 % and ≥ 2 strong signals
  absent. **EXISTING**: P > 80 %. **MIXED**: in between, or a new capability whose host (app +
  pattern file) exists. Uncalibrated thresholds: log P and the verdict in the state file.
- **One line, then proceed**: « Régime : EXISTANT · L4 · origin/main@<sha9> — <n> fichiers, plan
  <x>/<y> cochées, promesses servies <s>/<t>. Dis « neuf / mixte / existant » pour imposer. »
  Reda's word overrides, like a named level. **Switch mid-run**, in one line, the moment R1 or
  tour 0 contradicts the class (the module lives elsewhere, the API is absent).
- **Where the rule errs** (`regime.md` §5): parked shell or plan with 0 ticked → NEW; code behind
  an off switch → EXISTING without users; « redo » meaning a rewrite → EXISTING in strangler mode
  (new behind a switch, old kept), never NEW; merge ≠ deployed: read activation, never assume prod.

| | NEW | EXISTING | MIXED |
|---|---|---|---|
| L1-L3 | R1 from the request, references, contracts; R3 checks against sources and the contract | R1 from `origin/main` code and the real output; anchors `file::symbol`; R3 replays on the running product | R1 on the touched surface + its pattern file only |
| L4 tour 0 | conception: references, contract first (PACT10), product decisions (Tensions 3), mockups for UI; built by a plan run, invisible until activated | inventory promise by promise; goldens of the numbers already served, recorded on the intact commit; instrument up | inventory of the touched surface; pattern file + « do not change » list in every lane brief |
| L4 rounds | start once the first screen runs; round 1 judges against the mockups; contract tests green on both halves | fresh reviewers on the real screen; counter-verification hunts regressions first | one round on the touched central screens; foreign files add-only |
| L5 adds | the promise list as data, every entry failing, with its oracle, before any code | characterization of every served behaviour in scope before any change | goldens of the touched surface; new half passes ITS acceptance AND old goldens hold |
| Own risk | blank page, over-spec, one giant PR | regression, half-fixes, urge to rewrite, seams | two ways of doing one thing; other owners' files |
| Lane brief says | « build only your lane's promises; the contract file is the interface » | « fix without touching the rest; never assume something is missing — grep for it first » (agents re-create what they did not find) | same as EXISTING + « follow `<pattern file>` » |

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
**The auto-pick never chooses L4 or L5.** For a ship-grade ask (« several rounds », « make it the
best », a « done » module to polish) it runs at most L3 and PROPOSES once, in one line: « L4
possible : ≤ 25 points de quota par tour, <k> tours permis par le quota — dis « go L4 » ». A
hook-injected L4/L5 whose phrase sits only inside pasted or quoted material is ignored.

## The round skeleton (L1-L3)

- **R1 COMPRENDRE** — map the problem: targeted reads/research that enumerate the REAL
  problems, each with a file/fact reference. No fixes yet. Output = numbered problem list.
- **R2 CREUSER** — one lane per independent surface digs its problems to root cause and
  a concrete solution.
- **R3 VALIDER** — adversarial verification of EVERY finding and proposed solution
  against the real code, rendered output, or an executed check — never against a summary
  and never by the author agent (fresh-context verifiers outperform self-critique).
- **R4 REVUE FINALE** — one completeness critic (« what's missing — a surface not
  covered, a claim unverified, a source unread? ») + synthesis + plain-language report.

Rounds are ADAPTIVE: a round that adds nothing new is « dry » — advance (or stop at the
level's dry-cap). A small question compresses R1+R2 into one pass; a hard one repeats
R2↔R3 until dry. Whatever the completeness critic finds becomes the next round's work.

## The levels

| | **L1 « go deep »** | **L2 « go very deep »** | **L3 « go extremely deep »** | **L4 « ship-grade »** | **L5 « all the way »** |
|---|---|---|---|---|---|
| Lanes | ≤ ~4 (surfaces merged) | one per surface, ≤ ~8-10 | one per surface, ≤ ~10-12 | 4-6 reviewers per round, one role × axis each; fix lanes from `plan_lanes.py`, fewer than 8 while the instrument runs | L4 + 2 reviewers sharing one stratum per round + a freeze lane |
| Workers | sonnet medium-high; haiku scouts low | sonnet high; opus on high-risk surfaces | sonnet/opus high; opus on every high-risk surface | reviewers + consolidation opus high; fix lanes at their `plan_lanes.py` tier; haiku low for CI logs | as L4; freeze lane sonnet |
| R3 rigor | 1 fresh verifier per finding | 2 independent verifiers on critical findings | 2-3 lenses per finding (checked-facts lens on client-facing); loop-until-dry | every finding checked against code; every fix counter-verified by a fresh reviewer (closed verdicts) until non-fait + partiel ≤ 10 %, then all A + 25 % | L4 + overlap estimate, blind pair judgments, pass^3 on critical journeys, locked goldens |
| Fable budget | 0 | 1 — completeness critic | house 1-3/run cap, each with its DONE-LOG line | 1 — the final critique; the orchestrator is opus | up to 3: final critique, adjudication, harness revalidation |
| Round caps | ~2 | ~3 | until dry (hard cap ~5) + interval verification during builds | 3 rounds + final, cut by quota (Guardrails) | per session window as L4; campaign ≤ 5 rounds + real-life stage |
| Typical agents | ~3-7 | ~8-15 | ~15-35 | measured once: 16 reviewers, ≈ 40 fix agents, 3 consolidations | estimate: ≈ 1.3-1.5 × L4 for the same rounds |
| Weekly quota | not measured | not measured | audit L3 ≤ 8 M tokens (METHODE §B.3) | measured once ≈ 74 points for 3 rounds + final (some from another session) → plan ≤ 25 / round | estimate ≈ 1.3-1.5 × L4, over ≥ 2 weekly windows |

## L4 « ship-grade » — fresh reviewers on the real product, until a numeric contract

A module « done » by plan, CI and acceptance still gave 152 findings on its real screen at
round 1; this loop took it to 2 blockers. Below, with its measured defects removed.

0. **Tour 0** (orchestrator + ≤ 2 agents): regime and cost lines; claims (`plan_claims.py claim
   file:<plan> app:<m>`); inventory (EXISTING) or conception (NEW); the **exit contract before any
   review** (`contrat-de-sortie.md` — a target absent from it never blocks later); the instrument
   (`instrument-de-revue.md`); registry (`registre.md`) and state file (`etat.md`), pushed.
1. **Reviewers** — fresh, one role × one axis (function / simplicity / beauty × phone / desktop),
   own account, `brief-relecteur.md`: use the product like its user, PROVE each finding (gestures
   + capture + expected), A/B/C, compare to NAMED best products, say what is good and what was not
   tried; floor = qa-explorer STEP 2 oracles 1-10 + STEP 3 rules 1-12 (cite, never copy). Beauty
   by PAIRS (before/after, us/reference) plus DOM measures, never an absolute score alone.
   Findings are registry rows; message ≤ 15 lines. From round 2, FIRST counter-verify the scope's
   fixes with `vérifie`'s closed verdicts (METHODE §C.4: ok / partiel / non-fait / faux /
   régression / déjà-présent), hunting twins; THEN look fresh.
2. **Consolidation** (one opus): each finding checked against the code (`file::symbol`, never
   `file:line` — METHODE anti-pattern 11) with a `verdict_consolidation` (discards per reviewer
   and axis = the only noise measure); product choices ruled (Tensions 3); **CLASSES named**: a root
   behaviour behind ≥ 2 findings gets `fiche-invariant.md` with the grepped list of EVERY place it
   can be violated — lanes fix the class, not the symptom. Corrections become one-line tasks of
   the owner's plan (`@lane @files @model @after`); lanes come from `plan_lanes.py`, never by hand.
3. **A global contract change goes ALONE, first** (error code, shared shape, shared component
   API): its own lane, green before the wave, with the table of what changes — a late 400 → 409
   cost 5 CI round-trips. Found by CI mid-wave: no new lane starts until it lands.
4. **Fix lanes** (`brief-lane.md`), worktrees launched ONE per message: red test, root cause,
   twins, one commit each; visible fixes proved on the instrument, « after » capture looked at.
   For A findings and classes a separate test-writer commits the proving test FIRST, on the branch
   lanes start from; the fold refuses a lane that touches it. Exits: fixed / **contested** (finding
   wrong — evidence) / **impossible** (not without weakening — why); only the orchestrator drops a test.
5. **Fold, then seam**: the orchestrator folds `--no-ff` reading only the 15-line report and the
   registry diff (cross-lane requests become rows); then ONE seam lane alone on the tree replays
   e2e on the assembled build and walks every screen — disjoint files are not disjoint behaviour.
6. **CI first**: draft PR at the first fold, Auto-fix on; a haiku scout reads each red log (≤ 10
   lines back) and the red goes to the lane owning the file; nothing disabled or exempted.
7. **Breaker per finding**: attempts 1-2 by its lane, 3 by a fresh fixer one tier up re-reviewed on
   that diff only, then « parked with decision » or « smallest unblocking change » — never a 4th.
8. **Mechanical stop** — no new round once one holds: contract met; round cap; quota stop. « Dry »
   = two DIFFERENT reviewers on one scope with no new A (evaluator agreement runs 5-65 %). The
   curve never reaches zero: do not aim for a dry round.
9. **Last round**: each new finding « avant le merge » (first-hour visible, data loss, wrong
   number, common gesture broken) or « peut attendre » → `[ ]` tasks in the owner's plan file.
10. **Merge per round**: by the queue once CI is green and one fresh opus has critiqued the
    round's server diff (security, company/account isolation, data loss; error-autopilot's
    taxonomy). The last round adds ONE fresh targeted verification on the real screen, and its
    critique, over `git diff <T0 sha>..HEAD`, is the Fable pass. Stop at the merge; release claims
    after it; tear the instrument down.
11. **Retro**: per class, « would the system catch it alone next time? » In L4 the class's read-only
    test IS its guard; any further guard is a `[ ]` task of its owner, one per CLASS in an existing
    family, never one per finding (METHODE anti-pattern 15). CI bug classes →
    `plan_drain_ci_bug_classes`; registry curves → state file.

## L5 « all the way » — what L4 cannot do

Not more agents: six capabilities L4 lacks, run as a CAMPAIGN over sessions whose state lives on
disk; each session first gets its bearings (fetch, read state, replay baseline e2e), then works.

1. **Freeze before touching.** EXISTING: characterization goldens of every served number and
   gesture in scope, recorded on the intact commit, locked in CI, never updated by a fixing lane.
   NEW: the promise list as data, every entry failing, each with its oracle, before code.
2. **Estimate what remains.** Two reviewers on one common stratum (two central screens), same
   build: Chapman N = (n+1)(K+1)/(k+1) − 1, shown as a range and « lower bound », unstable with few
   common findings — report it, never decide on it alone. Experiment: seeded defects → recall.
3. **Independent judges.** Beauty by two blind reviewers on pairs against a named reference,
   agreement reported, anchored on ~20 cases Reda scored once; another model family on A findings
   and the server diff only with Reda's yes (paid dependency).
4. **Real-life stage.** Reda on a real device, 30 min of written journeys; 5 days of real use, 3
   debrief questions; activation by flag; a minimal front error log; qa-explorer `dataset: anon`.
5. **Compose.** Every class guard proved RED on the original defect before it counts; each proven
   journey becomes `frontend/e2e/acceptation/<g>.spec.js`, written AFTER the finding; critical
   journeys run k = 3 (pass^k).
6. **Revalidate the harness.** Each component encodes an assumption about what the model cannot
   do: on a new model remove ONE, rerun a known round, keep it only if it still pays; interval
   verification (fresh sub-agents against the contract) runs DURING long lanes.

Cost: ≈ +25 % reviewers, one freeze lane, Reda's time (30 min + 5 days), two weekly windows.
**Not worth it** when the scope is small or rarely used; no real user or device exists (stage 4 is
the point); L4's last round met the contract with 0 A and per-reviewer yield ≤ 1/3 of round 1; the
module is to be replaced soon; or the quota allows fewer than 2 rounds.

## Guardrails — cost, box, instrument

- **Cost line before tour 0**: « Coût estimé : <k> tours × ≤ 25 points, quota à <u> %. » Rounds
  allowed k = floor((90 − u − 5) / 25), at most 3 (10 points stay for Reda's other work, 5 for the
  final). k = 0 → tour 0 only, on disk, resumed after the reset. No new round when u ≥ 65; at 90 %:
  commit, push, write state, stop. Read u with the session usage tool (untried: note at tour 0
  whether it gives the weekly %), else the last known u plus points spent, in the state file.
  The cost line is for Reda: never put a budget or countdown into an agent's prompt.
- **Checkpoints** (state file + push): after tour 0, each reviewer round, consolidation, fold, CI
  result, and before each merge. The orchestrator reads conclusions, never dumps.
- **Box** (4 cores / 34 GB): CPU is the limit — 8 lanes used 94-99 % without a stack; start below
  8 with the instrument up and measure. ≈ 1 GB per worktree: ask Reda early for deletion consent;
  `cmd /c rmdir` the `node_modules` junction before `git worktree remove`. Never start Docker « to
  see » (it relaunches another stack with a real sending key).
- **Instrument** (`instrument-de-revue.md`): never prod; only code already pushed; mail forced to
  an in-memory/console backend; no real third-party key (env from `.env.example`, never the real
  `.env`); its own database, cache, ports; never another session's containers, databases or
  accounts, never `docker compose`. No instrument (cloud session) → no L4: run L3 plus METHODE
  §C.4.7 runner specs, and say so.
- **Orchestrator**: start L4/L5 in an opus session; in a Fable one, say so in the cost line (2×
  opus per token) — never switch `/model` mid-session.

## Tensions settled (each precises a CLAUDE.md rule, none overrides it)

1. **WOW23 TEST ECONOMICS**: lanes run eslint and only the test they fix, neighbours are CI's,
   and the instrument has the 3-bis status (it doubles no CI job) and never gates a push.
2. **MERGE FLOOR (~100 unmerged)**: the cap counts plan tasks, and an L4 round is one WOW23 wave
   merged the instant its CI is green (step 10), so no PR outlives a round.
3. **Questions (METHODE §B.6 vs « aucune question »)**: by default NEW and MIXED ask ONE batch of
   product decisions at the end of tour 0, recommendation first, EXISTING asks none; under « no
   questions » every regime rules by the written rule (simplest for the user, else the mockup,
   else the best products), logs each choice with its cost-if-wrong, keeps it reversible and never
   records it as Reda's decision.
4. **Cost (Fewest steps; METHODE §B.3 8 M cap)**: the 8 M cap governs audits; L4/L5 are never
   auto-picked, announce their cost first and stay inside the quota formula.
5. **3-bis**: reviewers tick nothing; acceptance records, and every A / wrong-number / data-loss
   finding before it drives a fix, are replayed once by the orchestrator or a fresh agent.

## Non-negotiables at every level (CLAUDE.md, restated)

- **Sizing**: lanes = independent surfaces (378 numbers over 9 surfaces = ~9-12 lanes, never
  161). Escalation buys DEPTH per lane — more rounds, effort, adversarial re-reads — never lanes.
- **Every subagent carries an explicit `model:` + effort.** Never inherit the session
  model (and `CLAUDE_CODE_SUBAGENT_MODEL` stays UNSET — it would override the tags).
- **Grounding block verbatim in every agent prompt** (CLAUDE.md « Fleet quality &
  economics »); every done/found claim cites its evidence (file::symbol, command output, SHA).
- **Reviewer calibration**: correctness/spec findings only; style and hypothetical hardening are
  OPTIONAL, apart; checked-facts / zero-invented-number findings are ALWAYS correctness; in L4/L5
  the exit contract IS the spec (a beauty axis judges beauty). TRIAGE before any corrector fleet.
- **Read-only fleets**: same-directory Workflow fan-outs, never worktrees; a big audit is ONE
  workflow. Resume an agent only to DEEPEN its lane; adversarial round-2 is always FRESH.
- **Verify against the REAL rendered or executed output** — never a green build alone.
- **Report** what was checked AND what was NOT (L4/L5: no real device unless L5 stage 4 ran),
  with verified/refuted counts, in plain language for Reda.

Sources: L1-L3 verified 2026-08-24 (official Claude Code docs; Anthropic multi-agent research
system). L4/L5 designed 2026-11-20 from the measured 19-20/11 rounds and six research lanes
(Anthropic harnesses and evaluators; Superpowers fix loop; Every compound engineering; RITE,
capture-recapture, Google SRE checklists; characterization tests; ImpossibleBench, METR) — each
choice and its source: `conception.md` next to this file. Revalidate L4/L5 on the next model.
