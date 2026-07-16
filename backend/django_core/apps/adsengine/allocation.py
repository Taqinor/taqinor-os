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
