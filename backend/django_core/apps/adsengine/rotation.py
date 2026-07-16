"""ADSENG25 — Protocole de rotation créative (dd-creative-sci §a).

Chaque ad set porte **1 champion + 2 challengers** (3 ads). L'évaluation suit
le rythme du lundi (``WeeklyBrief`` — ENG11). Les nouveaux ads entrent depuis
le backlog (ADSENG27) ; les perdants sortent selon le signal du bandit (P1).

INVARIANT PORTEUR (dd-meta-mechanics §a — codé et testé) : **au plus UN nouvel
ad est ajouté par rotation**. Ajouter un ad RESET la phase d'apprentissage Meta
(coûteux) ; pauser un ad existant est GRATUIT. On étale donc les ajouts —
jamais deux ajouts simultanés, même si deux slots sont libres (le second slot
se remplit à la rotation suivante). Ce module ne CALCULE PAS les postérieurs :
il CONSOMME le ``p_best`` produit par le bandit (P1) — le couplage dégrade
proprement tant que le bandit n'est pas câblé (``p_best`` par défaut 0). La
lignée d'un lancement est encodée via ``identity`` (ADSENG23, lane parallèle —
dégrade si absent).

Ce module est de la LOGIQUE pure (dataclasses + fonctions) : aucun accès
réseau, aucune écriture Meta. Il PROPOSE des sorties/entrées ; l'application
passe par la boucle ``EngineAction`` propose→approuve→applique (ENG7), née
PAUSED (règle #3).
"""
from __future__ import annotations

import dataclasses
import datetime
import logging

logger = logging.getLogger(__name__)

# ── Composition d'un ad set ──────────────────────────────────────────────────
CHAMPION_COUNT = 1
CHALLENGER_COUNT = 2
ADS_PER_ADSET = CHAMPION_COUNT + CHALLENGER_COUNT  # 3

# ── Ration stricte : jamais > 1 ajout par rotation ───────────────────────────
MAX_NEW_ADS_PER_ROTATION = 1

# ── Critère de sortie P1 (bandit) ────────────────────────────────────────────
# P(best) sous le seuil pour DEUX évaluations hebdo de suite (règle des deux
# coups) ET au moins un autre bras vivant a un meilleur P(best).
EXIT_P_BEST_THRESHOLD = 0.15
EXIT_CONSECUTIVE_WEAK_WEEKS = 2

# ── Plancher d'exploration (avant toute éligibilité à la sortie) ─────────────
MIN_EXPLORATION_DAYS = 7
MIN_EXPLORATION_IMPRESSIONS = 1000

# ── Durée de vie max d'un challenger + fatigue (revue forcée, pas sortie) ────
MAX_LIFESPAN_WEEKS = 3
FATIGUE_FREQUENCY = 3.0

# Jour de rotation (lundi) — ``date.weekday() == 0``.
MONDAY = 0

# Verdicts de classification d'un bras.
KEEP = 'keep'
EXIT = 'exit'
REVIEW = 'review'


@dataclasses.dataclass(frozen=True)
class ArmSnapshot:
    """Instantané d'un bras (ad) au moment de l'évaluation.

    ``p_best`` vient du bandit (P1) ; ``weak_streak`` est le nombre de semaines
    consécutives FAIBLES (P(best) < seuil), la courante incluse — la règle des
    deux coups exige ``weak_streak >= 2``.
    """

    arm_id: object
    is_champion: bool = False
    age_days: int = 0
    impressions: int = 0
    frequency: float = 0.0
    p_best: float = 0.0
    weak_streak: int = 0
    is_active: bool = True


@dataclasses.dataclass(frozen=True)
class EntryPlan:
    """Un (seul) nouvel ad à introduire depuis le backlog, avec sa lignée."""

    source_ref: object
    launch_name: str
    reason_fr: str


@dataclasses.dataclass
class RotationDecision:
    """Décision d'une rotation : sorties (pauses), revues, et 0-1 entrée."""

    evaluated_at: datetime.date
    exits: list
    reviews: list
    entries: list
    reasons_fr: list

    @property
    def added_count(self):
        return len(self.entries)


def is_rotation_day(day):
    """Vrai si ``day`` est un lundi (rythme d'évaluation de la rotation)."""
    return day.weekday() == MONDAY


def next_weak_streak(previous_streak, p_best):
    """Fait avancer la série faible : +1 si le bras est faible cette semaine,
    remis à 0 sinon. Sert à matérialiser la règle des deux coups entre deux
    évaluations hebdo successives."""
    if p_best < EXIT_P_BEST_THRESHOLD:
        return int(previous_streak) + 1
    return 0


def exploration_complete(arm):
    """Vrai si le plancher d'exploration est atteint (≥7 j ET ≥1000
    impressions). En dessous, aucun bras n'est éligible à la sortie."""
    return (arm.age_days >= MIN_EXPLORATION_DAYS
            and arm.impressions >= MIN_EXPLORATION_IMPRESSIONS)


def classify_arm(arm, *, has_strictly_better):
    """Classe un bras : ``KEEP`` / ``EXIT`` / ``REVIEW``.

    ``EXIT`` (sortie bandit, deux coups) s'applique AUSSI au champion. Le
    champion n'est jamais retiré au simple tic calendaire (fin de vie / fatigue
    → ``KEEP``). Un challenger en fin de vie (>3 semaines) ou fatigué
    (fréquence ≥ seuil) passe en ``REVIEW`` (revue humaine proposée), jamais en
    sortie automatique.
    """
    if not exploration_complete(arm):
        return KEEP
    if (arm.weak_streak >= EXIT_CONSECUTIVE_WEAK_WEEKS
            and arm.p_best < EXIT_P_BEST_THRESHOLD
            and has_strictly_better):
        return EXIT
    if arm.is_champion:
        return KEEP
    if arm.age_days >= MAX_LIFESPAN_WEEKS * 7:
        return REVIEW
    if arm.frequency >= FATIGUE_FREQUENCY:
        return REVIEW
    return KEEP


def _best_of_others(active, arm):
    """Meilleur ``p_best`` parmi les autres bras vivants (0 si aucun)."""
    return max((o.p_best for o in active if o.arm_id != arm.arm_id),
               default=0.0)


def _launch_name(source_ref, *, identity_fn=None, objective='', audience=''):
    """Nom de lancement encodant objectif/audience/variante (lignée ADSENG23).

    Priorité : ``identity_fn`` injecté → module ``identity`` (ADSENG23, lane
    parallèle) → repli déterministe. Toute erreur d'un chemin optionnel dégrade
    vers le repli — jamais d'exception propagée dans la décision de rotation.
    """
    ref = getattr(source_ref, 'pk', None) or getattr(
        source_ref, 'id', None) or source_ref
    if identity_fn is not None:
        try:
            return identity_fn(objective=objective, audience=audience,
                               variant=str(ref))
        except Exception:  # noqa: BLE001 - chemin optionnel, on dégrade
            logger.debug('rotation: identity_fn a échoué — repli')
    try:  # ADSENG23 peut être un lane parallèle non encore fondu
        from . import identity as _identity
        gen = getattr(_identity, 'generate_launch_identity', None)
        if callable(gen):
            result = gen(objective=objective, audience=audience,
                         variant=str(ref))
            if isinstance(result, dict):
                name = result.get('name') or result.get('ad')
                if name:
                    return name
            elif result:
                return str(result)
    except Exception:  # noqa: BLE001 - identity absent/incompatible → repli
        logger.debug('rotation: identity absent/incompatible — repli')
    return f'rotation-{objective or "ad"}-{audience or "aud"}-{ref}'


def plan_rotation(arms, *, backlog=(), today=None, identity_fn=None,
                  objective='', audience=''):
    """Planifie une rotation pour UN ad set.

    ``arms`` : ``ArmSnapshot`` des ads en place. ``backlog`` : candidats
    ordonnés (items de backlog ou tout objet portant ``pk``/``id``). Renvoie
    une ``RotationDecision`` : les sorties (pauses — plusieurs possibles,
    gratuit), les revues, et **au plus une** entrée (ration stricte). Ne touche
    jamais Meta.
    """
    today = today or datetime.date.today()
    arms = list(arms)
    active = [a for a in arms if a.is_active]

    exits, reviews, reasons = [], [], []
    for arm in active:
        has_better = _best_of_others(active, arm) > arm.p_best
        verdict = classify_arm(arm, has_strictly_better=has_better)
        if verdict == EXIT:
            exits.append(arm.arm_id)
            reasons.append(
                f"Bras {arm.arm_id} sous {EXIT_P_BEST_THRESHOLD:.0%} de "
                f"P(best) sur {arm.weak_streak} semaines — pause (gratuit).")
        elif verdict == REVIEW:
            reviews.append(arm.arm_id)
            reasons.append(
                f"Bras {arm.arm_id} en fin de vie / fatigué — revue "
                "proposée.")

    remaining = len(active) - len(exits)
    free_slots = max(0, ADS_PER_ADSET - remaining)
    # RATION : au plus MAX_NEW_ADS_PER_ROTATION, quels que soient les slots.
    to_add = min(free_slots, MAX_NEW_ADS_PER_ROTATION, len(backlog))

    entries = []
    for item in list(backlog)[:to_add]:
        name = _launch_name(item, identity_fn=identity_fn,
                            objective=objective, audience=audience)
        entries.append(EntryPlan(
            source_ref=getattr(item, 'pk', None) or getattr(
                item, 'id', None) or item,
            launch_name=name,
            reason_fr=(
                "Entrée d'un nouvel ad depuis le backlog (ration : un seul "
                "ajout par rotation — ajouter reset l'apprentissage Meta).")))

    # Défense en profondeur : jamais deux ajouts (même si un appelant force).
    if len(entries) > MAX_NEW_ADS_PER_ROTATION:
        entries = entries[:MAX_NEW_ADS_PER_ROTATION]

    return RotationDecision(
        evaluated_at=today, exits=exits, reviews=reviews,
        entries=entries, reasons_fr=reasons)


def snapshot_from_arm(arm, *, p_best=0.0, weak_streak=0, today=None):
    """Bridge modèle → ``ArmSnapshot`` : agrège les ``ArmDailyStat`` d'un
    ``ExperimentArm`` (impressions cumulées, âge). ``p_best`` et
    ``weak_streak`` viennent du bandit (P1) — injectés, jamais recalculés ici.
    """
    from django.db.models import Sum

    today = today or datetime.date.today()
    stats = arm.daily_stats.all()
    agg = stats.aggregate(imp=Sum('impressions'))
    impressions = int(agg.get('imp') or 0)
    first = stats.order_by('date').values_list('date', flat=True).first()
    age_days = (today - first).days if first else 0
    latest = stats.order_by('-date').first()
    frequency = 0.0
    if latest is not None:
        frequency = float(getattr(latest, 'frequency', 0.0) or 0.0)
    return ArmSnapshot(
        arm_id=arm.pk, is_champion=False, age_days=age_days,
        impressions=impressions, frequency=frequency,
        p_best=float(p_best or 0.0), weak_streak=int(weak_streak or 0),
        is_active=bool(getattr(arm, 'is_active', True)))
