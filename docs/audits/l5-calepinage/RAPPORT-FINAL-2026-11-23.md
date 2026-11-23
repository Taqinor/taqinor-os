# Calepinage L5 — report of 23 November 2026 (DRAFT, being completed)

> Draft written at 11:05 UTC while round 3 runs. Sections marked « to complete » are filled in at the end of the run.
> Working state for a resumed session: `docs/audits/l5-calepinage/etat.md`.

## 1. In one paragraph

You asked for an L5 on the calepinage module: more functions, simpler, prettier, new mockups, and the unfinished work
of the last version finished. In about 14 hours: 14 new mockups (v2) were drawn; every one of the 388 fixes that had
been delivered without proof was replayed on the real screens; 284 repair and build tasks were written from what the
reviewers saw; about 160 of them are built; a first batch of 109 is merged on `main` (PR #1527); a second batch of
about 51, which contains the new shell and the first five screens rebuilt on the v2 mockups, is in PR #1529.
**Nothing is deployed: the ERP changes go live only when you run `scripts/deploy-prod.ps1`.** The checks you asked
for after the L5 (quotes calculated automatically, one engine, the lead « CPE Go Plus ») are section 7 — to complete.

## 2. What was found when the old fixes were replayed (round 2)

- 388 fixes had been delivered with tests but never seen working. Reviewers replayed 381 of them on a private local
  copy of the ERP: 239 judged good, 130 partial, 11 not done, 1 regression.
- I did not trust the « good » verdicts: a second, adversarial reviewer re-read the evidence of every one of them.
  **Only 132 were confirmed** (they are ticked, with the record `docs/audits/acceptation/ACAL/2026-11-23-bfb859c90.md`);
  95 were proven only in part (to replay); 12 were contradicted by their own screenshot (now repair tasks).
- So of 388 delivered fixes, about one third fully held. This is the real size of what was « not finished ».
- The worst defects found, all now fixed in code (round 3 is checking them on screen — to complete):
  the same production shown with four different values; yearly figures that were ten-year sums in multi-year weather
  mode (a yearly consumption of 121 976.8 kWh printed for 12 197.68); headline production counting panels connected
  to nothing; a ground-mounted field counted twice; a calepinage with « Pan existant » that no longer reopened;
  inputs lost on reopen (photo date, building height, obstacles, chosen module); a 4-face roof that placed 0 panels;
  on the phone, panels placed without seeing the roof and an offline visit report never sent.

## 3. What was built

- **Wave 1** (30 tasks) and **wave 2** (130 tasks so far), each with a failing test first.
- **The new look**: the workshop shell rebuilt on the v2 mockups (full-screen map, floating header, rail and step
  panel, dark blue for what is active, gold only for the next action), then the Roof, Panels, Electrical, Diagram
  and Results screens. Side-by-side captures mockup | real screen: `docs/audits/l5-calepinage/T2/preuves/`.
  By the builders' own captures: Roof (light) faithful; the others close. An independent verdict on the real screens
  is in progress (round 3) — to complete.
- **Mockups v2**: https://claude.ai/artifact/BJ5TrpZU3QvwHE3fWAteH5 (private link), 14 screens, one new screen
  « Montrer au client ». Files: `docs/audits/l5-calepinage/maquettes-v2/`.
- **Research**: `T2/R1-beaute-simplicite.md`, `T2/R2-fonctions.md` (15 useful functions the module lacks; 13 of them
  need a decision or money, so they are parked with the reason).

## 4. Merges and what you have to do

- **Merged**: PR #1527 (wave A, 109 tasks), 23/11 at 10:12 UTC. One additive migration: `calepinage/0043`.
- **Open**: PR #1529 (wave B) — to complete (CI, independent critic, merge).
- **Your gesture**: `scripts/deploy-prod.ps1` when you want this live. My advice: wait for the round-3 verdict
  in section 6.
- The public site deploys automatically at each merge. An independent critic checked that the pages your visitors
  use (`/devis/mon-toit`, `/proposition/<token>`) do not load the changed parts of the drawing engine. I could not
  test the Cloudflare preview: it redirects to the live site by design.

## 5. Decisions

### 5.1 Open — yours (nothing was decided for you where a client sees the number)

| Id | Question | My recommendation |
|---|---|---|
| D-ACAL-75 | A layout of 60 panels reopens with 5: replay the saved layout, or re-place? | replay the saved layout |
| D-ACAL-80 | Cold temperature for string voltage: typical-year minimum, or never warmer than −5 °C? | the lower of the two |
| D-ACAL-81 | Use NASA POWER as a second weather source without an official terms page? | wait for a written answer |
| D-ACAL-82 | Default values for four losses (soiling, initial degradation, unavailability, cables) | you give them, shown as « assumed » |
| D-ACAL-83 | Near shading measured at the centre of the roof face (gives « −72 % ») or on the placed panels? | on the placed panels; I will list the quotes it changes first |
| D-ACAL-84 | Which thermal line applies to a flush roof and to a frame? | frame = free-standing; flush = not calculated until sourced |
| D-ACAL-85 | Does P90 include model, weather and datasheet uncertainty? | yes, each one cited |
| D-ACAL-86 | Which production figure does the client read when quote and study report differ? | each names the other and why |
| D-ACAL-87 | Moroccan regulatory file types and their official names | you give or validate the names |
| D-ACAL-88 | What production « Montrer au client » shows before a complete result | the upper bound, said as « at most » |

All are in `docs/audits/decisions.yml`. D-ACAL-82 matters most for « a default for everything »: today no project has
a complete result on day one because four losses have no published value, and I did not invent them.

### 5.2 Taken alone — tell me if one is wrong

- All 388 old fixes replayed, and every « good » verdict re-read by a second reviewer before ticking anything.
- The v2 mockups keep the structure of the v1 screens (same places, new look).
- Two tasks declared impossible rather than filled with invented values (NASA POWER terms; the four losses).
- Bundle size budgets raised by the rule written in the file (roof tool 635 → 650 KB; total 4 130 → 4 145 KB), no
  new dependency.
- The v2 colour tokens are written in `rgb()` because two CRM tests read the shared stylesheet by pattern.
- When no ratio range is set by the company, the panel / inverter ratio is now « not judged » everywhere (the task
  said so). In production you may want to set a range, or tell me to keep a fallback warning.
- Five containers of your shared local stack stopped to free memory (database kept); I restart them at the end.

## 6. Round 3 — today's fixes replayed on the real screens (to complete)

## 7. The checks you asked for after the L5 (to complete)

1. Screens against the v2 mockups.
2. Every quote calculated automatically, with the right assumptions.
3. One engine: the CRM one.
4. The lead « CPE Go Plus » (1742).

## 8. What remains in the plan

- About 125 tasks of round 2 not built (mostly the lower-severity ones), the remaining screens of the v2 redesign
  (Documents, List, Quick start, Tablet, client views), 60 partly-proven old fixes to replay, and the functions
  parked behind decisions. All are written as tasks in `docs/plans/PLAN_AUDIT_CALEPINAGE.md` (group of 2026-11-23).

## 9. Your machine

- The C: disk filled up completely at 09:05 UTC (Docker stopped; I restarted it). There are about 110 working copies
  from old sessions under `.claude/worktrees/` (half a gigabyte each). I removed only mine.
- Docker has 5 GB in `.wslconfig`; 6 to 7 GB would make reviews faster. I did not touch the file.

## 10. Cost

Weekly quota: 3 % at the start, 46 % at 10:20 UTC — to complete.
