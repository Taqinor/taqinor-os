# S2 — Behaviour engine (deterministic, no LLM) — `apps/taches`

Scope: pure functions over stored data; the LLM assistant only *phrases* and *calls* them. Every number shown is a count/median/ratio of the user's own rows, or a value explicitly labelled « valeur par défaut ». Sources = those named in the brief (§2 « Behaviour science »); anything else is marked **choix de conception (CdC)**.

Repo facts re-checked this session: `notifications.WorkingHoursConfig` = per-company weekday bitmask (default Mon–Fri) + `Holiday` rows (models.py:338, :388); `calendar_utils.is_jour_ouvre(d, company)` (calendar_utils.py:135); `notify()` with `respect_quiet_hours=True` **defers** to `fenetre_notifications(company, now).prochaine_ouverture` instead of dropping (services.py:528-570, selectors.py:91). Consequence for §6: time-bound nudges must pre-check the window and SKIP, never let notify() defer them.

Running example: today = **Tuesday 17/11/2026**, one user, company calendar Mon–Fri.

---

## 1. Prioritisation — lexicographic, not a weight soup

**Candidates**: own open tasks (status not done/abandoned, not `en_attente`/blocked, not snoozed past today) + ERP obligations read via `records` selectors (Activity assigned to him, not done, `due_date ≤ today+3`, kind = planned activity, never chatter). Blocked/waiting tasks are shown apart (« En attente de… »), never ranked.

**Sort key** (tuple, ascending) — CdC, chosen because each element is one sentence the founder can verify, and a tie is broken by the next sentence, never by a hidden coefficient:

1. **Bande** — 1 « engagement »: due ≤ today (overdue or today) or ERP obligation dated ≤ today; 2 « important ou proche »: importance flag OR due within the next 3 working days (`is_jour_ouvre`); 3: rest.
2. **Priorité projet** (1 = haute … 3 = basse); the weekly « projet focus » (§7) counts as 1 for that week.
3. **Priorité tâche** (haute < normale < basse).
4. **Échéance** ascending (none = last).
5. **Reports** descending (`reportee_n`).
6. **Âge** (created_at ascending — older first).

Estimate fit is NOT in the score; it is used only by the plan filler (§2). A task with `reportee_n ≥ 3` is not pushed harder: it is tagged « à trancher » and goes to triage (faire aujourd'hui / replanifier / découper / abandonner) — CdC: repeated postponement signals an ill-defined task; escalating it is the guilt pattern the brief says to avoid.

**Explanation string** = the facts behind elements 1-5 that are non-default, max 3, joined by « · »:

| Task | Facts | Rank | UI line |
|---|---|---|---|
| T1 Relancer client devis 452 (ERP Activity) | due 17/11, projet Ventes P1 | 1 | « échéance aujourd'hui · relance client (devis 452) · projet prioritaire » |
| T4 Payer fournisseur | due 16/11, Admin P2, prio haute | 2 | « en retard depuis hier · priorité haute » |
| T5 Préparer formation | important, Équipe P1 | 3 | « importante · projet prioritaire » |
| T2 Dossier subvention | important, due ven. 20/11, Admin P2, reportée 3× | 4 | « importante · échéance vendredi · reportée 3 fois → à trancher » |
| T3 Mettre à jour le site | Site P3, age 21 days | 5 | « en attente depuis 21 jours » |

(T1 before T4: both band 1, project P1 < P2.)

## 2. Daily plan proposal

**Capacity** `capacite_jour()` returns `(nb_cible, minutes_budget, source)`:
- `nb_cible` = the pace target (§3).
- `minutes_budget` = median of *minutes réalisées* over the last 9 non-missing days (§3 definition), where minutes réalisées = Σ over done tasks of (actual duration if recorded, else estimate × calibration factor §4, else 30 min). CdC (median, same 9-day window as the pace for coherence).
- Cold start (< 5 non-missing days): **5 tâches, 240 min — shown as « valeur par défaut, pas encore calculée sur toi »**. 5 mirrors Todoist Karma's default (brief, weak evidence); 240 min is CdC.
- Explicit preference overrides inference: « vendredis courts : 120 min » ⇒ Friday budget = 120, source = « ton réglage ».
- Unestimated tasks count 30 min (CdC) and the UI says so: « dont 2 sans estimation, comptées 30 min ».

**Algorithm** `proposer_plan()`:
1. Keep tasks he already put on today (`jour_prevu = today`) — never removed.
2. **Overdue triage** (separate card, before the plan): each overdue item gets a pre-selected default — « aujourd'hui » if priority haute or important, else « replanifier → prochain jour ouvré »; options also « abandonner ». No red counter, no « X en retard » headline; title « À décider (3) ».
3. **Reserve the important slot**: the highest-ranked important task enters first (guaranteed room for ≥ 1 important task).
4. Fill by rank while `nb < nb_cible`; a task whose addition exceeds `minutes_budget × 1.10` is skipped and the next one is tried (CdC tolerance 10 %).
5. `ce_soir` tasks go into a « Ce soir » section, counted in the plan and in the pace, not in the minutes budget (CdC — evening tasks are usually personal/short).

Worked example — target 5, budget 270 min (median of his last 9 days: 220, 250, 255, 260, **270**, 280, 300, 310, 340). Estimates: T1 15, T4 10 (triage: aujourd'hui), T5 120, T2 90 × factor 1.5 = 135, T3 60.
Reserve T5 → 120. T1 → 135. T4 → 145. T2 → 280 ≤ 297 (270 × 1.10) ✓. T3 → 340 > 297 ✗. Result 4 tasks, 280 min.
UI: « 4 tâches proposées, ≈ 4 h 40 estimées (budget habituel 4 h 30). Ton objectif de 5 dépasse ton temps habituel ; ajoute une petite tâche si tu veux. »

**Stability**: the engine PROPOSES; nothing is written until « Valider mon plan ». The accepted plan is snapshotted (`PlanJour`, task list + order + `accepte_le`). After acceptance the engine never reorders or removes anything; user additions are flagged `ajoutee_apres_validation`. Capacity warning when he adds beyond budget (Sunsama pattern, brief): « Ta journée fait 6 h 10 estimées pour 4 h 30 habituelles. »

## 3. Pace (« rythme »)

**Done task (count = 1)**: own task whose status became done on local date D (Africa/Casablanca); a recurring occurrence = 1; a parent with sub-tasks = 1 (sub-tasks count 0 — anti-splitting); an ERP Activity with `done_by = him`, `done_at` on D, kind = planned activity (open question Q1). Reopened ⇒ removed from D (stats recomputed). Abandoned = 0.

**Missing day** (excluded from the window, never a zero) — CdC adapting WalkIT's « non-missing »:
- declared off-day or inside vacation mode; or
- 0 done AND no plan accepted AND no task touched that day (no data ≠ a bad day);
- a non-working day (`is_jour_ouvre` false: weekend/holiday) with 0 done.
A working day with a plan accepted and 0 done counts as 0. A Saturday with 3 done counts (he worked).

**Minimum history**: 5 non-missing days in the last 28 calendar days before any computed target (CdC; WalkIT uses 9 — with 5-8 days we use what exists). Before that: default 5, labelled.

**POUSSER** (source: WalkIT, Adams 2017): `cible = ceil(P60(last 9 non-missing counts))`, P60 by linear interpolation (position 0.6 × (n−1)). Guards (CdC): `cible ≤ max(last 9)` (never more than his own best recent day) and `cible ≤ cible_d'hier + 1`. It may rise, stay or fall (as in WalkIT).
Example: counts sorted [2, 3, 4, 4, 5, 6, 6, 7, 8] → position 4.8 → 5 + 0.8 × (6−5) = 5.8 → **6**; max 8 ✓; yesterday's target 5 → 6 ≤ 6 ✓. Median = 5.
UI: « Objectif du jour : 6 — un peu au-dessus de ta journée type (5), calculé sur tes 9 derniers jours travaillés. »

**TENIR** — no published rule (brief); **entirely CdC**: at the switch, `reference R = round_half_up(median(last 9))`, frozen; band `[R − b, R + b]` with `b = max(1, round(0.2 × R))`. Daily target = R. Drift = median of the last 5 non-missing days outside the band; at most one drift message per 7 days. Overshoot matters as much as undershoot — « c'est assez » means protect him from overwork: above the band, the plan proposal is capped at R + b tasks and the message offers POUSSER.
Example: R = 5, b = 1, band 4-6. Last 5 days [3, 2, 4, 3, 5] → median 3 < 4 → « Ces 5 derniers jours : médiane 3, sous ta zone 4-6. Garder 5 ou passer à 4 ? » (two buttons, no judgement).

**Anti-gaming** (brief: count alone is gameable; Zhu 2018 [S]): the day's goal is « atteint » only if count ≥ cible AND (≥ 1 important task done OR none was open). Always shown next to the count: plan-completion ratio (done ∩ plan / plan) and important done. Split detection: if the median estimate of done tasks in the current 9-day window < 50 % of the previous window's (both n ≥ 10), an informational line: « Tes tâches terminées sont plus petites que d'habitude (médiane 15 min contre 40). » (CdC).

**Recovery**: no streaks anywhere (brief: highlighting broken streaks reduces continuation [S]). A bad day only moves the 9-day percentile; the next morning reads « Nouvelle journée — objectif 5 », never a reference to yesterday's miss. Weekly view = totals vs previous week (informational feedback, Deci, Koestner & Ryan 1999).

Learning goals: for a project flagged « nouveau / exploratoire », its tasks are excluded from the count target and the morning card asks for one process intention instead (Seijts & Latham 2005).

## 4. Estimate calibration

Actual duration sources, by reliability: (a) optional ▶/■ timer (`demarree_le`, accumulated `duree_reelle_min`); (b) optional one-tap at completion: « plus court / comme prévu / plus long / X min » (the three chips map to 0.75 / 1.0 / 1.5 — CdC, stored as `source = estimation_ressentie`, used only if no minutes); (c) **never** `done_at − created_at` or `done_at − previous done_at`: idle time and multitasking make it unreliable — not used.

Similarity key, narrowest level with n ≥ 5 observations wins (CdC): (projet, tranche de taille) → projet → étiquette → global. Size bands on the estimate: ≤ 15, 16-60, > 60 min. Factor = median(actual / estimate) of the last 30 observations at that level. Shown only when outside [0.8, 1.25] (CdC):
« Tes tâches « Admin » de 16-60 min ont pris en médiane 1,5 × ton estimation (8 tâches) → 90 min prévues ≈ 2 h 15. »
This is the Buehler, Griffin & Ross 1994 (study 4) remedy: connect past similar experience to the prediction. The factor feeds the plan budget; the stored estimate is never silently changed.

## 5. Behaviour profile (private, derived, recomputable)

| Observation | Formula | Min data | Sentence |
|---|---|---|---|
| Heures de complétion | histogram of done_at hour, last 28 days | 30 completions | « 34 % de tes 61 tâches terminées l'ont été entre 9 h et 11 h. » (never used to assign hours — chronotype evidence, brief) |
| Jours forts | mean count per weekday, last 8 weeks, non-missing only | 4 days per weekday | « Le mardi est ton jour le plus fourni (6,2 en moyenne sur 7 mardis). » |
| Reports chroniques | tasks with reportee_n ≥ 3; per project share of tasks reported ≥ 1 | 1 task / 10 tasks | « 4 tâches reportées 3 fois ou plus — on les tranche ? » |
| Projets négligés | P1 project with open tasks and 0 done in 14 days; or done-share rank vs priority rank inverted | 14 days | « Ton projet prioritaire « Formation » n'a rien vu avancer depuis 14 jours (5 tâches ouvertes). » |
| Tenue du plan | weekly plan-completion ratio, last 4 weeks | 3 plans/week | « Plans tenus : 62 %, 70 %, 71 %, 78 % sur 4 semaines. » |
| Délai capture→fait | median days created→done, per project | 10 done | « Une tâche « Ventes » est faite en médiane 2 jours après sa création. » |
| Part d'importantes | important done / done, 28 days | 20 done | « 18 % de tes tâches terminées étaient importantes. » |
| Biais d'estimation | §4 factor | 5 per key | §4 sentence |

**Explicit preferences** = `PreferenceTaches(user, cle, valeur JSON, source ∈ {reglage, assistant}, modifie_le)`, closed key enum: `mode_rythme` (pousser/tenir + R), `heure_limite_rappels` (e.g. 19:00), `jours_courts` {weekday: minutes}, `jours_off` [weekday], `vacances` {du, au}, `rappels` {kind: on/off/heure}, `semaine_revue` (weekday, hour). A stated preference always wins over inference and is shown as « ton réglage ». When the assistant hears « c'est assez », it calls the same internal action that sets `mode_rythme=tenir` and answers with the computed R — the LLM never stores free-text facts.
Privacy: rows scoped to `company` AND `user`; no viewset exposes another user's profile, admins included (CdC); « Effacer mon profil » deletes `StatJour`, `BilanJour` reflections, `PreferenceTaches`, `RappelEnvoi` (tasks kept).

## 6. Nudge policy

| Kind | Default | Condition to send |
|---|---|---|
| matin | 08:30 working days (aligned with the founder's existing « messages ≥ 8 h 30 » decision in memory) | no plan accepted yet today |
| midi | OFF by default, 13:30 | plan accepted, < 50 % done |
| soir | 18:00 | plan accepted today |
| hebdo | Friday 16:00 (CdC, editable) | ≥ 1 project active |
| dérive / projet négligé | never a push of its own | appended as one line to the next matin/hebdo |

- **Hard cap**: 2 pushes/day, 3 on the weekly-review day (CdC — brief: no source for N).
- **Decay** (Klasnja 2018: effect fades ~3 %/day, gone by day 29): a nudge is « ignoré » if its deep link is not opened within 3 h AND the target screen was not visited that day. 3 consecutive ignored → every other day; 6 → paused, with one in-app line « J'ai arrêté le rappel du matin : tu ne l'ouvrais plus. Le réactiver ? ». Prefer moments he opens the app: if he planned before 08:30, no morning push.
- **Rotation**: 3 title/body variants per kind, variant = day ordinal mod 3. Example soir v1: « Bilan : 3 sur 4 faites » / « Il reste « Dossier subvention ». Demain, plus tard ou abandon ? » → `/taches/bilan`.
- **Windows**: send only if `fenetre_notifications(company, now).ouverte` AND now < `heure_limite_rappels`; otherwise SKIP (never let `notify()` defer — a morning plan at 14:00 is noise).
- **Dedupe**: `MarqueurEmissionBalayage(company, event_type, cle=f"{user_id}:{kind}", periode=date)`.
- **Kill switches**: settings flag `TACHES_RAPPELS_ACTIFS` (+ `.env.example`), per-kind preference, module toggle. The app badge (`setAppBadge` = remaining plan tasks) is not a nudge and not capped.

## 7. Rituals (all skippable, no penalty)

- **Matin (≈ 2 min)**: yesterday in one line (« Hier : 4 faites dont 1 importante »), triage card, proposal (§2), pace target (§3), one optional if-then line per important task (« Si 9 h, alors je commence le dossier ») — Gollwitzer & Sheeran 2006, d = .65 as an upper bound. Output: `PlanJour`.
- **Soir**: done list; each unfinished plan task needs an explicit choice (demain [pre-selected] / date / plus tard / abandonner) confirmed by one « Valider »; one optional reflection line ≤ 280 chars (Di Stefano et al.). Skipped ⇒ nothing moves; leftovers appear in tomorrow's triage, never auto-moved.
- **Hebdo**: per project — done count and minutes, open count, stuck tasks (no change ≥ 14 days or reportee_n ≥ 3), last week's intention; he writes one intention line per project and may pick one « projet focus » (score element 2 next week).

## 8. Storage and pure functions

Fields/tables needed (all `TenantModel`, `user` FK, scoped): **Tache** + `reportee_n`, `en_attente_de`, `ce_soir`, `parent`, `demarree_le`, `duree_reelle_min`, `source_duree`, `abandonnee_le`, `important`; **Projet** + `priorite` (1-3), `exploratoire`; **PlanJour** (user, date unique, `accepte_le`, `cible_nb`, `budget_min`, `source_cible`, `mode_rythme`) + **LignePlan** (tache, ordre, `ajoutee_apres_validation`); **StatJour** (user, date unique, `nb_faites`, `nb_importantes_faites`, `nb_plan`, `nb_plan_faites`, `minutes_realisees`, `manquant`, `raison_manquant`) — recomputable cache; **BilanJour** (reflexion, decisions JSON); **IntentionSemaine** (projet, semaine, texte, focus); **PreferenceTaches**; **RappelEnvoi** (kind, date, variante, envoye_le, ouvert_le).

Pure functions (no ORM inside; callers pass plain data):
- `cle_tri(tache, aujourdhui, jours_ouvres) -> (tuple, raisons)`; `expliquer(raisons) -> str`
- `trier_en_retard(taches, aujourdhui) -> [(tache, action_defaut)]`
- `est_jour_manquant(stat, est_ouvre, off_declare) -> bool`
- `fenetre_non_manquante(stats, aujourdhui, n=9, horizon=28) -> [int]`
- `percentile_lineaire(valeurs, p) -> float`
- `cible_pousser(comptes9, cible_hier) -> int | None`
- `reference_tenir(comptes9) -> int`; `bande_tenir(R) -> (min, max)`; `derive_tenir(R, comptes5) -> 'sous' | 'dans' | 'au-dessus'`
- `jour_atteint(nb, cible, nb_imp_faites, nb_imp_ouvertes) -> bool`
- `capacite_jour(stats, prefs, jour) -> Capacite(nb, minutes, source)`
- `proposer_plan(candidats_tries, capacite, deja_prevues) -> Proposition(taches, minutes, avertissement)`
- `facteur_calibrage(observations, cle) -> (facteur, n, niveau) | None`
- `profil(stats, taches, aujourdhui) -> [Observation(cle, valeur, n, phrase)]`
- `rappels_dus(maintenant, prefs, etat_jour, historique, fenetre_ouverte) -> [Rappel]`
- `etat_decroissance(historique_kind) -> 'normal' | 'un_jour_sur_deux' | 'pause'`
- `texte_rappel(kind, donnees, ordinal) -> (titre, corps, lien)`

Test-first examples: the arithmetic in §2 (280 min, 4 tasks), §3 (5.8 → 6; R = 5 band 4-6; median 3 → 'sous').

## 9. Deliberately NOT done

Points/badges/rewards (Deci, Koestner & Ryan 1999; Hamari 2014) · streaks (broken-streak evidence [S]) · chronotype time-slotting (> 80 % of 65 studies: no main effect) · silent auto-rescheduling (Motion/Reclaim complaints) · overdue guilt counters · fixed-frequency prompts (Klasnja 2018) · durations inferred from timestamps (§4) · numbers or memory produced by the LLM (all figures come from §8).

## Open questions for the founder

Q1 Do ERP activities (relances CRM) count in the daily pace, or only his own tasks? Q2 TENIR band ±1 (≈ ±20 %) acceptable? Q3 Weekly review on Friday 16:00 or Sunday evening? Q4 Do weekends count when he works them (current design: yes)? Q5 Nudge cap 2/day OK? Q6 Cold-start defaults 5 tasks / 4 h OK?
