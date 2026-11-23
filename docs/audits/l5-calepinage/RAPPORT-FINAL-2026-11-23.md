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

## 6. Round 3 — today's fixes replayed on the real screens

Six fresh reviewers replayed, on the rebuilt private copy, the fixes delivered this morning (waves A and B).

| | Listed | Played | Good | Partial | Not done | Not tried |
|---|---|---|---|---|---|---|
| Shell and screens | 31 | 31 | 8 | 22 | 1 | 0 |
| Production figures | 20 | 18 | 13 | 3 | 2 | 2 |
| Layout, editor, sweep | 39 | 24 | 10 | 11 | 3 | 15 |
| Roof, obstacles, zones | 33 | 26 | 12 | 13 | 1 | 7 |
| Electrical, diagram | 45 | 36 | 27 | 8 | 1 | 9 |
| Phone | 5 | 5 | 3 | 2 | 0 | 0 |
| **Total** | **173** | **140** | **73** | **59** | **8** | **33** |

- As in round 2, a second reviewer re-read the « good » verdicts against their screenshots: of 64 re-read, **48
  confirmed**, 14 only partly proven, 2 contradicted. 47 tasks are ticked on that basis (record
  `docs/audits/acceptation/ACAL/2026-11-23-f7d5f1a7e.md`). 9 late « good » verdicts were not re-read and are not ticked.
- What holds: the new shell works with the real engine (no dead screen); the three worst defects of round 2 hold
  (« Pan existant » reopens, a ground field leaves one surface, the 4-face roof places its panels); the yearly figures
  are yearly; a layout of 60 reopens at 60.
- What round 3 found, all given to wave C (section 3): **a custom layout larger than the target was lost on reopen
  without a word** (16 saved, 5 shown, then 5 written back by a plain « Save »); the Undo button did nothing where
  Ctrl+Z worked; setbacks typed in changed nothing; « at most 16 panels » where 20 fit; a panel / inverter ratio of
  4.26 shown with a green tick; the report naming the default panel instead of the one placed; monthly bills not read
  back after reload; « connection expired » shown for a slow answer; the address card covering the zoom buttons.
- Not done for lack of budget: the 95 old fixes judged « partly proven » in round 2 were not replayed (35 serious, 60
  others). They stay unticked.

## 7. The checks you asked for after the L5

Sources: `docs/audits/l5-calepinage/controles/` — `C1-moteur-unique.md`, `C2-devis-automatiques.md`,
`C3-mesures-prod.md` (production read only: counts and ids, nothing written).

### 7.1 « All my quotes can be calculated automatically, from the bill and one profile » — measured on production

| Market | Leads | With a bill or kWh | Ready for the automatic quote | They stop on |
|---|---|---|---|---|
| Residential | 1 065 | 478 | **448** (94 %) | the city as typed: 29 leads (18 not in « Froid ») |
| Commercial | 80 | 42 | **4** | electricity contract 38 · opening days 37 · phase 35 |
| Industrial | 1 | 1 | 1 | — |
| Agricultural | 2 | 2 | 2 | — |

- **Residential works.** The 29 stops are spellings: « casa » (5), « casablaca », « kech », city names typed in
  Arabic, « maroc », a district. The lead card said « ready », then the engine refused. Wave C makes the card say
  « Missing: city » (to complete: delivered or not). Recognising these spellings changes the production of those
  quotes, so it is your decision: D-ACAL-95 (my recommendation: recognise common spellings and Arabic names).
- **Commercial does not work with the bill and a profile alone**: 38 of 42 leads with a bill stop. The contract stop
  is your own decision D-CIQ-23; the opening days come from D-CIQ-1 (no standard industrial profile); for the phase I
  found no decision of yours. If you want « bill + profile is enough », answer D-ACAL-92, 93 and 94.
- **Agricultural**: by your decisions the bill sizes nothing (head, flow, phase, visit of the water point).
- **Assumptions that are made but not said, or half said** (your rule of 17/11): in residential, presence during the
  day (984 of 1 065 leads have none declared; the banner does not name the field), summer = winter, 30° due south,
  kWh derived from dirhams; in commercial and industrial, 30° due south when GPS is missing and the estimated
  profile (dropped from the automatic quote's log). Tasks are written in the quote plan; they change no number.
- **Defaults without a source I could read**: summer = winter over 12 months; fallback panel of 710 Wc. Two rest on
  a code comment only: total losses 20 % (« fondateur 18/08 ») and 14 % for PVGIS.
- **The most blocking decision is D-ACAL-82** (four losses without a value). While it is open every calepinage
  result stays « incomplete », and an incomplete result is rejected by the quote: so the production of the real
  layout, which you decided must feed new quotes (D-ACAL-36, 44, 46), reaches no quote at all today.

### 7.2 « One engine, the CRM one »

- Today **four engines** calculate the same installation (the C&I quote engine, the residential quote engine, the
  calepinage on the server, the workshop in the browser) plus two side tables. I found **five different limits** for
  the panel / inverter ratio, two temperature policies for string length, and the calepinage read nothing of the
  quote's study (not the retained option, not the inverter, not the strings, not the production).
- Built in wave C (to complete: delivered or not): the quote states its retained design; the calepinage takes its
  target, its inverter, its string length and its production from it; when the calepinage differs it says « gap with
  the quote » instead of raising an alert against its own constants; one ratio rule, the quote's; a hybrid inverter is
  judged by its published capacity (your rule D-HYB-1); the calepinage follows the quote that was sent.
- Not built, written as tasks: the C&I quote engine importing the same hybrid rule from the shared core (it keeps its
  own copy for now — I did not touch the quote engine), one temperature policy for both, the calepinage using the
  consumption profile chosen in the CRM.

### 7.3 The lead « CPE Go Plus » (1742)

**Your sent quote (564) is not the problem; the calepinage was calculating beside it.** Cause by cause:

| What you saw | Cause | Fixed by |
|---|---|---|
| The calepinage is attached to draft 554, not to the sent quote 564 | It only followed a quote on a revision; each automatic quote is a new v1 | wave C (ACAL1955) + one command to run after deploy |
| 48 panels instead of the 35 of the recommended option | 48 is what the roof holds (also the « with battery » option); the drawing never recorded which option it was for; the target was always « without battery » | wave C (ACAL1951) |
| A different inverter (hybrid 20 kW) than the quote's | It was picked by hand in the calepinage, and a manual pick wins | wave C (ACAL1952): the quote's inverter by default, a manual pick shown as a gap |
| Ratio 1.72 « above 1.35 » | The calepinage ignored your hybrid rule: that inverter publishes 40 kWc, the field is 34.32 | wave C (ACAL1954) |
| String length 12 « against 16 » | 16 is a constant from tender files, not the quote; the quote itself has 12 | wave C (ACAL1953) |
| Production « not simulated » | The simulation only runs on a click; the quote's production was never read | wave C (ACAL1956): the quote's production is shown until the layout is simulated |

On production, of 5 calepinages attached to a quote, 3 have a panel count different from the quote's recommended
option and none has a simulation. After you deploy, `manage.py relier_calepinages_devis_envoye` lists the calepinages
to re-attach (today: one, the 9); with `--appliquer` it re-attaches them. That writes on production: your gesture.

### 7.4 Screens against the v2 mockups — independent verdict

A reviewer who built nothing put each real screen beside its mockup, same size, and measured both.
Boards « mockup | real »: `docs/audits/l5-calepinage/T3/preuves/B3-*.png`. Report: `T3/B3.md`.

| | Faithful | Close | Far | Not comparable |
|---|---|---|---|---|
| Before today's rebuild (round 2) | 0 | 3 | 8 | 2 |
| After (round 3) | **0** | **6** | **6** | 2 |

- **Close (6)**: Roof (light and dark), Panels, Electrical, Incomplete result, List. On these the shell is identical
  to the mockup to the pixel (header, rail, step panel 384 × 796, gold button 340 × 52, colours, type).
- **Far (6)**: Documents, Quick start, Tablet, Phone survey, Phone client view, Presentation — not rebuilt on v2 yet.
- **Not comparable (2)**: Diagram and Complete result, because the demo data cannot reach those states (panel sheets
  without electrical values; the four losses of D-ACAL-82).
- **Why no screen is « faithful » yet**: what is drawn ON the map. Placed panels are plain black instead of tinted by
  sunlight, the roof outline has grey doubled dimensions instead of a gold outline with one dimension per edge, the
  strings are not drawn. The frame is right; the picture inside is not. Wave C looks for the cause of the black
  panels (to complete). The rest is written as tasks.
- My own check of the boards agrees with the reviewer. I did not see the real aerial photo: the private copy has no
  map key.

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
