"""ADSENG10 — Politique d'allocation + règles kill/promote (fonctions pures).

La couche « politique » au-dessus du cœur statistique (``bandit.py``,
ADSENG8). dd-science-core §2.4/§2.5/§2.6 :

- **Plancher d'exploration ABSOLU** : ``max(20% du budget, 20 MAD/jour)`` par bras
  vivant — JAMAIS le 1% de GrowthBook (1 MAD/jour tomberait sous le minimum de
  delivery de Meta ~10 MAD/jour et le bras cesserait de délivrer). Le budget
  restant est réparti selon les poids ``w_i`` du bandit.
- **Repondération QUOTIDIENNE** mais seulement quand chaque bras a ≥ 100
  impressions dans la fenêtre (la porte « 100 users » de GrowthBook) ; sinon on
  tient un partage égal (jamais bouger les poids sur trop peu de données).
- **Kill/promote HEBDOMADAIRE** : aucun kill autonome avant que le bras ait À LA
  FOIS ≥ 7 jours de vie ET ≥ 40 conversions proxy (burn-in) ; ensuite, kill si
  ``P(meilleur) < 5%`` tenu 3 jours consécutifs (garde contre un jour chanceux).

Toutes les fonctions sont **pures** (aucune I/O). Les défauts numériques
correspondent à ``GuardrailConfig`` (``exploration_floor_pct``,
``exploration_floor_mad``) — les services les passent en arguments.
"""
from __future__ import annotations

import numpy as np

# Défauts (dd-science-core §7 « Config defaults » ; miroir GuardrailConfig).
DEFAULT_FLOOR_PCT = 0.20          # exploration_floor_pct = 20 %
DEFAULT_MIN_ARM_MAD = 20.0        # exploration_floor_mad = 20 MAD/jour
MIN_IMPRESSIONS_FOR_REWEIGHT = 100    # porte GrowthBook « 100 users »
BURN_IN_MIN_DAYS = 7                  # ≥ 7 jours vivant avant kill
BURN_IN_MIN_CONVERSIONS = 40          # ≥ 40 conversions/bras avant kill
KILL_PROB_THRESHOLD = 0.05            # P(meilleur) < 5 %
KILL_STREAK_DAYS = 3                  # tenu 3 jours consécutifs
PHASE_ADVANCE_PROB = 0.80             # P(meilleur) ≥ 80 % ⇒ phase mûre (§4)
PHASE_WEEK_CAP = 4                    # ou plafond de 4 semaines (§4)


def exploration_floor(daily_budget_mad, floor_pct=DEFAULT_FLOOR_PCT,
                      min_arm_mad=DEFAULT_MIN_ARM_MAD):
    """Plancher d'exploration ABSOLU par bras (MAD/jour) = ``max(pct, min)``.

    dd-science-core §2.4 : le max entre un pourcentage du budget et un plancher
    dur en MAD. Fonction pure.
    """
    return max(floor_pct * float(daily_budget_mad), float(min_arm_mad))


def allocate_budget(prob, daily_budget_mad, floor_pct=DEFAULT_FLOOR_PCT,
                    min_arm_mad=DEFAULT_MIN_ARM_MAD):
    """Convertit les poids ``w_i`` du bandit en budget MAD/jour par bras.

    ``budget_i = floor + free · w_i`` où ``floor = exploration_floor(...)`` et
    ``free = max(budget − n·floor, 0)`` (dd-science-core §2.4). Les allocations
    somment au budget quotidien (propriété testée) et chaque bras reçoit au moins
    le plancher.

    **Cas pathologique** : si ``n·floor ≥ budget`` (trop de bras pour honorer le
    plancher — c'est pourquoi le nombre de bras est plafonné à 4), on ne peut pas
    honorer le plancher ; on renvoie alors un partage ÉGAL du budget (invariant
    « somme = budget » préservé). Fonction pure.
    """
    n = len(prob)
    if n == 0:
        return []
    budget = float(daily_budget_mad)
    floor = exploration_floor(budget, floor_pct, min_arm_mad)
    floored = floor * n
    if floored >= budget:
        # Plancher inatteignable : partage égal (préserve la somme = budget).
        return [budget / n] * n
    free = budget - floored
    return [floor + free * float(w) for w in prob]


def can_reweight(impressions_per_arm,
                 min_impressions=MIN_IMPRESSIONS_FOR_REWEIGHT):
    """Vrai seulement si CHAQUE bras a ≥ ``min_impressions`` dans la fenêtre.

    dd-science-core §2.5 : ne pas bouger les poids tant qu'un bras n'a pas franchi
    la porte « 100 users » de GrowthBook — sinon on tient un partage égal.
    Fonction pure.
    """
    if not impressions_per_arm:
        return False
    return all(int(i) >= min_impressions for i in impressions_per_arm)


def allocate_daily(prob, impressions_per_arm, daily_budget_mad,
                   floor_pct=DEFAULT_FLOOR_PCT, min_arm_mad=DEFAULT_MIN_ARM_MAD,
                   min_impressions=MIN_IMPRESSIONS_FOR_REWEIGHT):
    """Allocation quotidienne GATÉE par la porte de repondération.

    Si chaque bras a ≥ ``min_impressions`` : répartition pondérée par le bandit
    (:func:`allocate_budget`). Sinon : partage ÉGAL du budget (on tient tant que
    les données sont trop maigres — dd-science-core §2.5). La somme vaut toujours
    le budget. Fonction pure.
    """
    n = len(prob)
    if n == 0:
        return []
    if can_reweight(impressions_per_arm, min_impressions):
        return allocate_budget(prob, daily_budget_mad, floor_pct, min_arm_mad)
    return [float(daily_budget_mad) / n] * n


def is_burned_in(days_live, conversions, min_days=BURN_IN_MIN_DAYS,
                 min_conversions=BURN_IN_MIN_CONVERSIONS):
    """Burn-in atteint : ≥ ``min_days`` de vie ET ≥ ``min_conversions``.

    dd-science-core §2.5 : AUCUN kill autonome tant que les DEUX conditions ne
    sont pas réunies. Fonction pure.
    """
    return int(days_live) >= min_days and int(conversions) >= min_conversions


def consecutive_below(values, threshold):
    """Longueur de la série FINALE de valeurs strictement sous ``threshold``.

    Utilitaire pour la règle de kill (P(meilleur) < 5 % tenu N jours) : compte
    combien de mises à jour quotidiennes RÉCENTES consécutives sont sous le
    seuil. Fonction pure.
    """
    streak = 0
    for v in reversed(list(values)):
        if float(v) < float(threshold):
            streak += 1
        else:
            break
    return streak


def killable(days_live, conversions, prob_best_i, streak_below,
             min_days=BURN_IN_MIN_DAYS, min_conversions=BURN_IN_MIN_CONVERSIONS,
             kill_threshold=KILL_PROB_THRESHOLD, min_streak=KILL_STREAK_DAYS):
    """Un bras est-il tuable en autonome ? (dd-science-core §2.5).

    Vrai UNIQUEMENT si burn-in atteint (:func:`is_burned_in`) ET
    ``prob_best_i < kill_threshold`` ET la série sous le seuil dure au moins
    ``min_streak`` jours consécutifs. Toute condition manquante ⇒ False (jamais
    de kill prématuré). Fonction pure — l'application reste propose→approuve.
    """
    return (is_burned_in(days_live, conversions, min_days, min_conversions)
            and float(prob_best_i) < float(kill_threshold)
            and int(streak_below) >= min_streak)


def challenger_phase_complete(prob_best_max, weeks_running,
                              min_prob=PHASE_ADVANCE_PROB,
                              week_cap=PHASE_WEEK_CAP):
    """Signal (hebdo) « phase mûre » consommé pour promouvoir un challenger.

    dd-science-core §4 : n'avancer une phase que lorsqu'un bras atteint
    ``P(meilleur) ≥ 80 %`` OU que le plafond de 4 semaines est atteint (on garde
    alors le leader, sans forcer une décision). Ne PROMEUT rien lui-même — un
    créatif promu naît toujours PAUSED via une ``EngineAction`` propose (règle #3).
    Fonction pure.
    """
    return (float(prob_best_max) >= float(min_prob)
            or int(weeks_running) >= week_cap)


# ── PUB92 — Arrêt par PERTE ESPÉRÉE (règle NOUVELLE, À CÔTÉ de la précédente) ──
# challenger_phase_complete (ci-dessus, INCHANGÉE — byte-identique) arrête sur
# P(meilleur) ≥ 80 % OU 4 semaines. Sur données MINCES, ces deux seuils sont
# grossiers : ils stoppent trop tard une victoire nette et forcent une décision
# sur une vraie égalité au plafond. La règle bayésienne « expected loss » est plus
# nette : on arrête quand le COÛT ATTENDU DE SE TROMPER (committer sur le leader
# alors qu'un autre bras était meilleur) tombe sous un seuil en MAD. C'est le
# critère « threshold of caring » de Stucchio/GrowthBook, exprimé en MAD/jour.
#
# Cette fonction NE REMPLACE PAS challenger_phase_complete : les deux vivent côte à
# côte (golden tests des deux), le moteur choisit laquelle consommer. Pure (numpy
# déterministe sous graine, comme bandit.py — aucune I/O).
EXPECTED_LOSS_K = 10_000            # tirages Monte-Carlo (miroir bandit.DEFAULT_K)
EXPECTED_LOSS_SEED = 0             # graine → déterministe / auditable
DEFAULT_STOP_THRESHOLD_MAD = 5.0   # coût attendu de se tromper < 5 MAD/jour


def _leader_index(posteriors):
    """Index du bras leader = plus forte moyenne postérieure ``α/(α+β)``. Pure."""
    means = [a / (a + b) if (a + b) > 0 else 0.0 for a, b in posteriors]
    return int(max(range(len(means)), key=lambda i: means[i]))


def expected_loss_rate(posteriors, *, leader_index=None, k=EXPECTED_LOSS_K,
                       seed=EXPECTED_LOSS_SEED, rng=None):
    """Perte espérée (en points de TAUX) de committer sur le leader. Pure.

    ``E[max(0, max_j θ_j − θ_leader)]`` estimée par Monte-Carlo sur les postérieurs
    Beta (déterministe sous ``seed``). C'est la « perte espérée » bayésienne : ce
    qu'on abandonne EN MOYENNE en figeant le leader alors qu'un autre bras pouvait
    être meilleur. 0 pour < 2 bras. ``leader_index`` None → plus forte moyenne.
    """
    n = len(posteriors)
    if n < 2:
        return 0.0
    if leader_index is None:
        leader_index = _leader_index(posteriors)
    generator = rng if rng is not None else np.random.default_rng(seed)
    draws = np.column_stack([generator.beta(a, b, k) for a, b in posteriors])
    best = draws.max(axis=1)
    leader = draws[:, leader_index]
    return float(np.maximum(best - leader, 0.0).mean())


def expected_loss_mad(posteriors, daily_budget_mad, *, leader_index=None,
                      k=EXPECTED_LOSS_K, seed=EXPECTED_LOSS_SEED, rng=None):
    """Perte espérée QUOTIDIENNE en MAD de committer sur le leader. Pure.

    ``perte_relative = perte_espérée_taux / moyenne(θ_leader)`` (fraction de
    performance abandonnée) puis ``× budget/jour`` → MAD/jour exposés à une
    mauvaise allocation. 0 pour < 2 bras ou un leader de taux nul (rien à perdre
    à ce budget). Déterministe sous ``seed``.
    """
    n = len(posteriors)
    if n < 2:
        return 0.0
    if leader_index is None:
        leader_index = _leader_index(posteriors)
    a, b = posteriors[leader_index]
    leader_mean = a / (a + b) if (a + b) > 0 else 0.0
    if leader_mean <= 0:
        return 0.0
    loss_rate = expected_loss_rate(
        posteriors, leader_index=leader_index, k=k, seed=seed, rng=rng)
    relative = loss_rate / leader_mean
    return float(relative * float(daily_budget_mad))


def expected_loss_stop(posteriors, daily_budget_mad, *,
                       threshold_mad=DEFAULT_STOP_THRESHOLD_MAD,
                       leader_index=None, k=EXPECTED_LOSS_K,
                       seed=EXPECTED_LOSS_SEED, rng=None):
    """PUB92 — Règle d'arrêt à PERTE ESPÉRÉE (NOUVELLE, à côté de
    :func:`challenger_phase_complete` qui reste inchangée).

    Arrête quand la perte espérée quotidienne (:func:`expected_loss_mad`) de
    committer sur le leader tombe SOUS ``threshold_mad``. Plus net sur données
    minces : une victoire nette a une perte espérée quasi nulle (stop tôt), tandis
    qu'une vraie égalité incertaine garde une perte espérée élevée (on continue).
    Ne PROMEUT / n'applique rien (règle #3). Renvoie ::

        {'should_stop': bool, 'expected_loss_mad': float,
         'threshold_mad': float, 'leader_index': int}

    Déterministe sous ``seed``. Fonction pure.
    """
    n = len(posteriors)
    if n == 0:
        return {'should_stop': False, 'expected_loss_mad': 0.0,
                'threshold_mad': float(threshold_mad), 'leader_index': None}
    if leader_index is None:
        leader_index = _leader_index(posteriors)
    loss_mad = expected_loss_mad(
        posteriors, daily_budget_mad, leader_index=leader_index,
        k=k, seed=seed, rng=rng)
    return {
        'should_stop': loss_mad < float(threshold_mad),
        'expected_loss_mad': round(loss_mad, 4),
        'threshold_mad': float(threshold_mad),
        'leader_index': leader_index,
    }
