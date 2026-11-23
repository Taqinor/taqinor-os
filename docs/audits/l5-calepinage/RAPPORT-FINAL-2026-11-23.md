# Calepinage L5 — report of 23 November 2026 (sections 1-10: state at 14:20 UTC · section 11: the evening)

> **Read section 11 first.** It is the evening update, written after you answered the decisions: it replaces
> what sections 4, 5.1 and 7.2 call « in progress » or « open ».

> Working state for a resumed session: `docs/audits/l5-calepinage/etat.md`.

## 1. In one paragraph

You asked for an L5 on the calepinage module: more functions, simpler, prettier, new mockups, the unfinished work of
the last version finished — then the checks (mockups, functions, every quote calculated automatically with the right
assumptions, one engine, the lead « CPE Go Plus »). In about 17 hours: 14 new mockups (v2) were drawn; every one of
the 388 fixes that had been delivered without proof was replayed on the real screens; 371 repair and build tasks were
written from what the reviewers saw; about 180 of them are built. Two batches are merged on `main`: PR #1527 (109
tasks) and PR #1529 (about 51 tasks: the new shell and five screens rebuilt on the v2 mockups). A third batch fixes
what the replay of today's work found: PR #1530 (in progress) and the « one engine » part (in progress, a fourth PR).
**Nothing is deployed: the ERP changes go live only when you run `scripts/deploy-prod.ps1`.**

**The three things to remember.** (1) The module is much closer to the mockups in its frame, but no screen is yet
« faithful »: what is drawn on the map (panel tint, roof outline, strings) is the gap. (2) Residential quotes
calculate themselves for 94 % of the leads that have a bill; commercial ones for 4 of 42 — that needs three decisions
from you. (3) On the lead « CPE Go Plus » your sent quote is right; the calepinage was calculating beside the quote,
and the fix is to make it take its design from the quote that was sent.

## 2. What was found when the old fixes were replayed (round 2)

- 388 fixes had been delivered with tests but never seen working. Reviewers replayed 381 of them on a private local
  copy of the ERP: 239 judged good, 130 partial, 11 not done, 1 regression.
- I did not trust the « good » verdicts: a second, adversarial reviewer re-read the evidence of every one of them.
  **Only 132 were confirmed** (they are ticked, with the record `docs/audits/acceptation/ACAL/2026-11-23-bfb859c90.md`);
  95 were proven only in part (to replay); 12 were contradicted by their own screenshot (now repair tasks).
- So of 388 delivered fixes, about one third fully held. This is the real size of what was « not finished ».
- The worst defects found, all fixed in code and confirmed on screen by round 3 (section 6):
  the same production shown with four different values; yearly figures that were ten-year sums in multi-year weather
  mode (a yearly consumption of 121 976.8 kWh printed for 12 197.68); headline production counting panels connected
  to nothing; a ground-mounted field counted twice; a calepinage with « Pan existant » that no longer reopened;
  inputs lost on reopen (photo date, building height, obstacles, chosen module); a 4-face roof that placed 0 panels;
  on the phone, panels placed without seeing the roof and an offline visit report never sent.

## 3. What was built

- **Wave 1** (30 tasks) and **wave 2** (130 tasks), each with a failing test first; then **wave C** (PR #1530, in progress),
  the repairs found by replaying waves 1 and 2 on the real screens:
  - a saved layout reopens exactly as saved (the silent loss of a custom layout is fixed at its root: a background
    recalculation no longer re-places a layout the user holds);
  - the Undo button undoes; a typed setback removes panels; « at most N panels » is the true maximum of the roof;
  - monthly bills are read back after reload; the simulation reads and names the panel that is placed; charge
    windows that do not apply no longer erase the battery; panels connected to nothing are said;
  - screens: the address card no longer hides the zoom or swallows clicks; a slow answer is no longer « connection
    expired »; a message never covers the action button; one gold button style; the progress bar shows the current
    step; in dark theme the map without photo is dark.
- **The new look**: the workshop shell rebuilt on the v2 mockups (full-screen map, floating header, rail and step
  panel, dark blue for what is active, gold only for the next action), then the Roof, Panels, Electrical, Diagram
  and Results screens. Side-by-side captures mockup | real screen: `docs/audits/l5-calepinage/T2/preuves/`.
  By the builders' own captures: Roof (light) faithful; the others close. An independent verdict on the real screens
  is section 7.4: 0 faithful, 6 close, 6 far.
- **Mockups v2**: https://claude.ai/artifact/BJ5TrpZU3QvwHE3fWAteH5 (private link), 14 screens, one new screen
  « Montrer au client ». Files: `docs/audits/l5-calepinage/maquettes-v2/`.
- **Research**: `T2/R1-beaute-simplicite.md`, `T2/R2-fonctions.md` (15 useful functions the module lacks; 13 of them
  need a decision or money, so they are parked with the reason).

## 4. Merges and what you have to do

- **Merged**: PR #1527 (wave A, 109 tasks), 23/11 at 10:12 UTC — one additive migration, `calepinage/0043`.
  PR #1529 (wave B, about 51 tasks), 23/11 at 12:27 UTC — no migration.
- **Wave C**: PR #1530 — in progress: its checks are running, an independent critic read it (one blocker, fixed
  before merging: after a slow save the screen could say « Saved » for someone else's write), a reviewer is replaying
  it on real screens. Then the « one engine » part, a fourth PR — in progress (7 of 11 tasks built).
- The merge queue removed waves A and B once each, for server tests that nobody had run: on a `claude/*` branch the
  PR run does not run the server tests, only the merge queue does. I fixed and re-queued both times, on the standing
  rule of your CLAUDE.md. For wave C I ran the whole calepinage server suite locally before queueing.
- **Your gesture**: `scripts/deploy-prod.ps1` when you want this live. After the « one engine » part is deployed, one
  more: `manage.py relier_calepinages_devis_envoye` (it lists; `--appliquer` re-attaches) — see 7.3.
- The public site deploys automatically at each merge. An independent critic checked that the pages your visitors
  use (`/devis/mon-toit`, `/proposition/<token>`) do not load the changed parts of the drawing engine. I could not
  test the Cloudflare preview: it redirects to the live site by design.

## 5. Decisions

### 5.1 Open — yours (nothing was decided for you where a client sees the number)

| Id | Question | My recommendation |
|---|---|---|
| D-ACAL-82 | **Most blocking.** Default values for four losses (soiling, initial degradation, unavailability, cables). While open, no result is complete and the real-layout production reaches no quote | you give them, shown as « assumed »; the only published value I found is 2 % for initial degradation |
| D-ACAL-92 | Commercial or industrial lead with no electricity contract declared: automatic quote or not? (38 of 42 leads stop here) | assume low-voltage tariff, say it, mark the quote as an estimate |
| D-ACAL-93 | Same lead with no phase declared (35 of 42) — I found no decision of yours behind this refusal | assume three-phase, say it |
| D-ACAL-94 | What does an industrial lead need for its consumption rhythm? | a profile per sector that you enter in Settings |
| D-ACAL-95 | Residential lead whose city is not recognised and has no GPS (29 leads: « casa », Arabic names…) | recognise common spellings and Arabic names |
| D-ACAL-80 | Cold temperature for string voltage: typical-year minimum, or never warmer than −5 °C? | the lower of the two |
| D-ACAL-81 | Use NASA POWER as a second weather source without an official terms page? | wait for a written answer |
| D-ACAL-83 | Near shading measured at the centre of the roof face (gives « −72 % ») or on the placed panels? | on the placed panels; I will list the quotes it changes first |
| D-ACAL-84 | Which thermal line applies to a flush roof and to a frame? | frame = free-standing; flush = not calculated until sourced |
| D-ACAL-85 | Does P90 include model, weather and datasheet uncertainty? | yes, each one cited |
| D-ACAL-86 | Which production figure does the client read when quote and study report differ? | each names the other and why |
| D-ACAL-87 | Moroccan regulatory file types and their official names | you give or validate the names |
| D-ACAL-88 | What production « Montrer au client » shows before a complete result | the upper bound, said as « at most » |

All are in `docs/audits/decisions.yml`, each with its options. I decided none of them: each changes a number a client
reads.

### 5.2 Taken alone — tell me if one is wrong

- **D-ACAL-75 — a saved layout is replayed as saved**, never re-placed on reopen. Round 3 showed work being lost in
  silence; replaying changes no saved number.
- **D-ACAL-91 — the panel / inverter ratio is judged by the quote engine's rule** (your company range if set, else
  the quote's 1.35; a hybrid by its published capacity). This replaces what I had chosen alone this morning (« not
  judged » without a company range), which round 3 showed as a ratio of 4.26 with a green tick.
- **D-ACAL-89 — when the calepinage follows the sent quote, the draft it leaves keeps nothing.**
- **D-ACAL-90 — the production simulation stays a click**; meanwhile the Results step of a sent quote shows the
  quote's production instead of being empty.
- All 388 old fixes replayed, and every « good » verdict re-read by a second reviewer before ticking anything.
- The v2 mockups keep the structure of the v1 screens (same places, new look).
- Two tasks declared impossible rather than filled with invented values (NASA POWER terms; the four losses).
- Bundle size budgets raised by the rule written in the file (roof tool 635 → 650 KB; total 4 130 → 4 145 KB), no
  new dependency.
- The v2 colour tokens are written in `rgb()` because two CRM tests read the shared stylesheet by pattern.
- The 95 old fixes that were only « partly proven » were not replayed a second time: the budget went to fixing what
  round 3 found. They stay unticked.
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
  « Missing: city » (in the « one engine » PR, in progress). Recognising these spellings changes the production of those
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
- Being built (the « one engine » PR, 7 of 11 tasks done at 14:20 UTC): the quote states its retained design; the calepinage takes its
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
  panels: not established — it needs a machine with a graphics card, the task is written. The rest is written as
  tasks.
- My own check of the boards agrees with the reviewer. I did not see the real aerial photo: the private copy has no
  map key.

## 8. What remains in the plan

Everything below is written as tasks, in `docs/plans/PLAN_AUDIT_CALEPINAGE.md` (group of 2026-11-23, 371 lines) and,
for files owned by others, in the lead, quote, settings, stock and cross-cutting plans.

- **To be « faithful » to the mockups**: the picture on the map (panel tint — cause not yet established, it needs a
  machine with a graphics card; gold roof outline; strings drawn), then the six screens not rebuilt on v2
  (Documents, Quick start, Tablet, Phone survey, Phone client view, Presentation).
- **About 190 tasks of rounds 2 and 3 not built**, mostly medium severity: wording, small layout defects, cases the
  reviewers could not play.
- **One engine, second half**: the C&I quote engine importing the shared hybrid rule; one temperature policy for
  string length; the calepinage using the consumption profile chosen in the CRM.
- **Automatic quotes**: say the silent assumptions (residential and C&I); the four gated tasks behind D-ACAL-92 to 95.
- **95 old fixes** proven only in part, to replay; **the functions parked behind decisions** (D-ACAL-80 to 88).

## 9. Your machine

- The C: disk filled up completely at 09:05 UTC (Docker stopped; I restarted it). There are about 110 working copies
  from old sessions under `.claude/worktrees/` (half a gigabyte each). I removed only mine.
- Docker has 5 GB in `.wslconfig`; 6 to 7 GB would make reviews faster. I did not touch the file.

## 10. Cost

Weekly quota: 3 % at the start of the campaign (21/11), 46 % at 10:20 UTC today, 60 % at 13:15 UTC. I expect about 65 % at the end.
Two calls to the most expensive model, within the house rule: the final critics of waves A and B (both found real
defects that were fixed before merging). None on wave C.

## 11. The evening of 23/11 — after your answers

### 11.1 What you decided, and what it did

You answered all the open decisions between 13:30 and 17:10 UTC (they are in `docs/audits/decisions.yml`, D-ACAL-75 to
97, each with your words). The ones that change what the ERP calculates:

| You decided | What was built from it (PR #1530) |
|---|---|
| The four losses: « search yourself on right values », then « Yes, these values » | Soiling 3 % a year, first-hours loss 1.5 % (1 % for TOPCon and HJT), unavailability 2 %, cables 1.5 % DC + 1 % AC — each shown as « assumed », with its source, on the Quick start page. Sources: `controles/R-pertes-par-defaut.md` |
| No contract declared: assume low voltage · no phase: assume three-phase · the shift pattern is enough | A commercial lead with a bill, a city and a business category now gets its automatic quote; each assumption is said with the field to fill; the quote is marked as an estimate |
| Recognise city spellings | « casa », « kech », Arabic names… are recognised; « maroc » is refused and the lead card now says « Missing: city » |
| « Simulation must start by itself » | Saving a complete layout starts the simulation on the server; the Results step shows it without a click |
| Near shade « on the placed panels » | Shade is measured where the panels are, not at the centre of the roof face |
| Sent quotes: « propose a revised quote » | The Results step shows both productions, named, and « Revise the quote »; the sent quote is never changed |
| Cold temperature: « the site's typical minimum » | One rule for the quote and the calepinage (strings are sized at the site's cold, not at −5 °C everywhere) |
| « Place them automatically » | A new calepinage of a lead with a bill places the number of panels the bill needs as soon as the roof is closed |
| P90 « count all of them » · NASA POWER « yes, use it » · « frame = free, flush = insulated » | Built on the server; see 11.3 for what the screen did not show |
| **« One engine in the whole ERP, results stored once on the lead »** (D-ACAL-97) | Designed today, not built — see 11.5 |

### 11.2 What is in PR #1530 — merged on `main` on 23/11 at 23:33 UTC

Everything built after wave B: wave C (fixes from the replay of waves A and B, and the first « one engine » half:
the calepinage reads the quote's design), wave D (your decisions above), their seams, and the fixes below.
About 50 tasks, 215 code files, no migration. It is one PR on purpose (your rule: one CI at a time).

### 11.3 Replayed on the real screens — three times

A reviewer who built nothing replays each batch on a private copy of the ERP, by clicks.

- **Replay 1 (wave C)** found that the main fix was NOT working although its test was green: a saved layout of 16
  panels came back as another number. The real cause was found only with a real browser (three places re-placed the
  panels behind the fix) and corrected. **Replay 2** confirmed it: 16 placed → reload 16 → save 16.
- **Replay 3 (wave D, tonight)**: 21 checks. Good: the automatic quote of a commercial lead with only a bill, a city
  and a category; city spellings; auto-sizing from the bill; the simulation starting by itself; both productions shown
  with « Revise the quote »; the ratio sentence naming its limit. It also found gaps, fixed tonight in the same PR:

| Seen on the real screen | Fix |
|---|---|
| A 2 × 8 factory was still refused without a start hour | start hour assumed (8 h for one shift, 6 h for two), said — **to confirm, D-ACAL-99** |
| A factory with a dirham bill and no declared voltage was refused | low voltage assumed, said (your D-ACAL-92) |
| The four residential assumptions were sent by the server but the screen showed none; reopening a quote showed no assumption at all | shown on screen and kept with the quote |
| After « Fill the settings », the result was still « incomplete » | cause: the panel sheet has no power tolerance. Measured on production: **none of your 3 panel sheets has one** — so no result would ever have been complete, and no real-layout production would have reached a quote. Now counted as 0 % (neither loss nor gain), said « assumed » — **to confirm, D-ACAL-98** |
| An incomplete layout still launched a calculation, and the page said both « something is missing » and « simulation running » | one launcher only (the server) |
| A complete result still said « upper bound — 9 losses not filled » | the screen no longer shows it when the result is complete; the sentence the server sends is still worded that way (written as a task) |
| Thermal line, P90 parts, NASA POWER comparison: served, not displayed | displayed |
| Choosing the panel and the inverter in the Electrical step lists did not count as « designated » (so the simulation never started by itself) | choosing now designates — replayed on the real screen |
| The Panels step said « ≈ 67 % of consumption » and the Results step « 36 % of consumption » under the same name | two different quantities, now named differently (production ÷ consumption / self-consumed ÷ consumption); the « one engine » work will leave one |

- **Not played**: near shade with obstacles (the reviewer ran out of time); the study report PDF with the two
  productions; the « equal productions, one figure » case; NASA POWER when the service answers (unreachable from the
  private copy). These tasks stay « code delivered, live proof due ».
- **Tonight's fixes themselves** are proven by tests (red first, then green); two were also replayed on the real
  screen by the lane that fixed them (designation in the Electrical step; saving). The others were not replayed
  by a fresh reviewer: I stopped there rather than start a fourth replay tonight. One defect could not be
  reproduced (after saving a brand-new calepinage the header kept « unsaved changes »): written as a live check.

### 11.4 The independent final critic

One last read of the whole PR by a model that built nothing (third and last call to the most expensive model in
this campaign). Verdict: mergeable after two fixes. Both are fixed, plus two defects it found in the new code:

- The recognised city could differ from one server process to another for texts like « Mohammedia, Casa » → fixed
  (fixed order; a city of the table wins over a spelling). **Checked on production, read only: of your 70 sent or
  accepted quotes, 49 have no GPS, and the new recognition gives the same city for all 49. No sent quote changes.**
- The quote tests were calling the real PVGIS service → blocked in tests.
- The « with battery » option sized its extension inverter at −5 °C while the rest used the site's cold → fixed.
- A calepinage attached to the draft revision of a quote already received could jump to another quote → refused.
- Verified clean: no migration, every new read filtered by company, no purchase price anywhere, sent C&I quotes not
  recalculated, no simulation loop, your public pages do not load the changed drawing code.

- **The merge queue removed the PR twice** (22:21 and 23:08 UTC), each time for ONE backend test that only the
  queue runs. First: an older test of the agricultural questionnaire expected « quote possible » for a lead with
  no phase, while wave D makes the lead card require the phase (the pumping quote engine refuses without it) —
  test corrected to the engine's rule. Second: a fingerprint that proves « this moved function was not edited »
  had to be recaptured, because tonight's last lane edited that function on purpose (it now stores the
  assumptions with the quote). Both fixed and re-queued, on the standing rule of your CLAUDE.md. Lesson banked:
  when the lead-card rule or the automatic-quote builder changes, the whole CRM suite and the split fingerprints
  are run before queueing, not only the changed test files.

### 11.5 One engine (your decision D-ACAL-97)

Your words: « one engine used everywhere and if the engine was used somewhere we just keep its values and use them
everywhere no need to recompute ». What I found: four engines calculate the same installation today.
What is ready: the design (`controles/C4-un-seul-moteur.md`: one entry point, the result stored once on the lead,
recalculated only when an input changes and saying why, sent quotes never touched) with your four answers (default
roof when none is drawn; a draft quote follows unless edited by hand; without a lead the calepinage carries the
result; while drawing, panels and kWc only), and **55 tasks in nine steps**, written in the plans of the files'
owners. As you chose, it is built in a fresh session: start it with « work on all plans », or name the group
« un seul moteur ». It is the biggest remaining piece: until it is built, the calepinage reads the quote's design
when a quote exists (wave C) and still calculates by itself otherwise.

### 11.6 To confirm — four choices I had to take tonight

They are recorded as D-ACAL-98 to 101 with their alternatives. Each changes a number or a status a client can read
on NEW quotes only; nothing sent changes.

1. **Panel sheet without power tolerance → 0 %** (D-ACAL-98). The alternative is to assume the usual 0/+3 %
   (a 0.75 % gain). Better still: type the tolerance on your 3 panel sheets.
2. **Shift start hour assumed: 8 h for one shift, 6 h for two** (D-ACAL-99).
3. **Assumed low-voltage tariff: « BT patenté » for a shop, « BT force motrice » for a factory** (D-ACAL-100).
4. **C&I quotes are printed « estimate, subject to a visit » for four reasons** (assumed contract, no hourly
   profile, unknown surface, the lead's visit flag) — the PDF already had this rule but never received the flag
   (D-ACAL-101).

### 11.7 What you have to do

1. **Deploy when you want it live**: `scripts/deploy-prod.ps1`. The three PRs of today (#1527, #1529, #1530) are
   merged; nothing of today is live until then.
2. After the deploy, in this order: Calepinage → Settings → Quick start → « Fill the empty settings » (it shows each
   value and its source before writing). Then `manage.py relier_calepinages_devis_envoye` lists the calepinages to
   re-attach to their sent quote (today: one, on the lead CPE Go Plus); `--appliquer` does it.
3. Answer the four confirmations above when you have a minute.

### 11.8 What remains

- **One engine**: 55 tasks (11.5).
- **Screens not rebuilt on the v2 mockups**: Documents, Quick start, Tablet, Phone survey, Phone client view,
  Presentation; and the picture on the map (panel tint, gold outline, strings drawn).
- **Live proofs due**: near shade with obstacles, the study report PDF, the 95 older fixes proven only in part.
- **Small leftovers written as tasks** (15, in the plans of the files' owners): the residential quote does not yet
  use the site's cold temperature; the lead card's « C&I catalogue ready » check misses five price-less items the
  engine then refuses; the Expert mode page after creation is unfinished; an « empty target » case after
  « Generate the quote » that nobody could reproduce; four tests that were already red on `main` at night
  (three of the study report, one of the C&I quote pages).

### 11.9 Cost

Weekly quota at 20:20 UTC: **78 % (all models), 69 % on the most expensive model** (higher now: two more lanes and a
reviewer ran after that reading); it resets on 28/11 at 11:00 UTC.
You told me quality comes before quota; I kept the reviews and the replays. Three calls to the most expensive model
as sub-agents (the final critics of waves A, B and C+D); each found real defects that were fixed before merging.
