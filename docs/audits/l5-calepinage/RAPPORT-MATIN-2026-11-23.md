# Calepinage L5 — morning report, 23 November 2026 (interim)

The L5 is still running, as you asked (more than 12 hours). Nothing is merged and nothing is deployed: all the work
is on the draft pull request Taqinor/taqinor-os#1527, whose last full CI run is green. The lead « CPE Go Plus » and
the « one engine, the CRM one » work have NOT been started: they come in the checks phase, after the L5.

## 1. What is done

- **Starting inventory.** The calepinage plan held 894 tasks: 436 ticked, 51 open, 19 waiting on you, and **388
  whose code was delivered but never proven on the real screen**. That last number is the unfinished part of the
  previous version.
- **New mockups (v2).** 14 screens redrawn in one visual language: the map fills the screen, the tools float over it,
  dark blue for what is active, gold only for the next action. One screen is new: « Montrer au client », a big-screen
  view without prices. Link (private): https://claude.ai/artifact/BJ5TrpZU3QvwHE3fWAteH5 — three small drawing
  defects are known: the map is too short on the phone screen, the base of the house is slightly hidden on the
  client phone screen, and one label sits too close to the drawer handle on the tablet.
- **Research.** Two studies, on beauty and simplicity (`T2/R1-beaute-simplicite.md`) and on functions
  (`T2/R2-fonctions.md`, 15 useful functions the module lacks).
- **First wave of fixes.** Among the open tasks, 30 are built and on the pull request, 3 are contested (the task
  was wrong) and 2 are impossible without inventing values. 4 more wait because they need the review stack.
- **Round 2: every delivered fix replayed on the real product.** Reviewers used a private local copy of the ERP,
  with no real key and no real data. So far 312 of the 388 fixes have a verdict:

| Verdict | Count |
|---|---|
| Works as the task says | 188 |
| Works only in part | 112 |
| Not done | 11 |
| Broke something that worked | 1 |
| Still being replayed | 76 |

So about 4 delivered fixes in 10 do not fully hold on the screen. That is why I am replaying all 388 and not a
sample.

## 2. The most serious problems found (to be fixed in the next waves)

1. **The same production shows different numbers on different screens** (4 362, 4 542, 5 131 and 5 173 kWh for one
   project; coverage 66 % on screen and 48 % in the PDF).
2. **The study report prints a ceiling as « P50 8 198 kWh »** where the workshop says 5 571 and the proposal 6 047.
3. **The headline production counts panels that are connected to nothing** (13 053 kWh against 10 419).
4. **A layout of 60 panels reopens with 5, and saves 5**: the work is lost. This is the open decision D-ACAL-75.
5. **A ground-mounted field is counted twice** (106 modules).
6. **A calepinage that uses « Pan existant » no longer reopens** (the one regression).
7. **No complete result on day one**, even after « Démarrage rapide »: 19 losses have no value. Four of them have no
   published source, so I did not invent them. This needs your decision on default values (section 4).
8. **On the phone**, the saleswoman places panels without seeing the roof, « Relevé de visite » and « Montrer au
   client » are buried at the bottom of « Avancé », and a visit report made offline is never sent when the network
   comes back.
9. **Inputs are lost when a project is reopened**: photo date, building height, obstacles, unchecked surfaces.
10. **A background calculation that the server cannot finish stays at « 5 % » forever**, with no failure message.
    The production worker is capped at 2 GB and never recycles its memory; I have not measured production itself.

The full list, with screenshots, is in `docs/audits/l5-calepinage/T2/` (one report per reviewer) and in
`registre/constats/`.

## 3. What comes next, in order

1. Finish round 2: four reviewers are still working, then the beauty reviewer compares the 13 screens with the
   mockups.
2. Turn every verdict into tasks in the plan (in progress, in five lots).
3. Fix by waves, each wave pushed to CI and merged through the merge queue when green.
4. Tick the 188 fixes that work, after an independent re-read of a sample of 37 (in progress).
5. Round 3: replay the fixes of round 2 and a fresh look.
6. **Then the checks phase**: screens against the v2 mockups, every quote calculated automatically with the right
   assumptions, one engine (the CRM one), and the lead « CPE Go Plus ».
7. The final detailed report.

## 4. Decisions I took alone (all reversible — tell me if one is wrong)

- I replay all 388 delivered fixes instead of a sample.
- The v2 mockups keep the structure of the v1 screens: same places, new look.
- Two tasks were declared impossible rather than filled with invented values: the NASA POWER terms of use (no
  official page found), and four default losses (soiling, initial degradation, unavailability, cable losses).
- I stopped five containers of your shared local stack to free memory (the database was kept). I restart them at
  the end.
- I did not touch your `.wslconfig`. Docker has 5 GB there, which froze once tonight.

## 5. What I will need from you (nothing blocks the work now)

- **Default values for the four losses above**: you said the ERP must have a default for everything. I can propose
  values, but they are your call because they change a production figure.
- **Cold temperature for string voltage**: one site plan uses +4.6 °C where −5 °C was expected. To confirm.
- **D-ACAL-75** (the 60-panel layout that reopens at 5) and the other open decisions, listed in the final report.
- **Deploy**: nothing to deploy yet. When a wave is merged I will say « mergé — à déployer par toi :
  `scripts/deploy-prod.ps1` ».
- Optional: raise Docker memory to 6 or 7 GB in `.wslconfig`; the reviews would run faster.

## 6. Cost so far

Weekly quota: 30 % used (3 % at the start). I aim to finish the L5 under 65 %.
