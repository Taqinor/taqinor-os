"""ASG2 — Oubli hebdomadaire des posteriors (dd-assumption-engine §3.2).

La péremption d'une « vérité » marketing devient MATHÉMATIQUE : chaque semaine
SANS test, le posterior Beta(α, β) d'un ``AssumptionNode`` s'oublie vers son
prior Beta(α₀, β₀) au pas ::

    (α, β) ← (ρ·α + (1−ρ)·α₀,  ρ·β + (1−ρ)·β₀),   ρ = 0.5^(1/H)

où ``H`` est la demi-vie de la CLASSE du nœud (8 sem créatif, 13 angle, 26
audience/structure — ``AssumptionNode.HALF_LIFE_WEEKS``). C'est le pas d'évolution
d'un modèle état-espace (forme discount de West–Harrison) : la variance regonfle
vers le prior, un « acquis » redevient incertain À LA VITESSE DE SA CLASSE. La
propriété-clé (testée) : la distance au prior ``(α − α₀)`` est EXACTEMENT divisée
par 2 toutes les ``H`` semaines (``ρ^H = 0.5``) — c'est LA demi-vie.

**La saisonnalité n'est PAS de l'oubli** (§3.2, dernière phrase) : un nœud portant
des ``tags_saison`` garde des posteriors SÉPARÉS par saison, réactivés quand la
saison revient — cette horloge hebdomadaire ne le touche JAMAIS. Sans stockage
per-saison dans le modèle (hors périmètre de cette lane), la règle fidèle et
minimale est : un nœud saisonnier est EXCLU de l'oubli hebdomadaire.

Deux horloges distinctes (§3.2) : le bandit intra-test oublie par IMPRESSION
(``bandit.py``) ; l'arbre oublie par SEMAINE (ce module). Le cœur mathématique
(``rho``/``decay_step``/``decay_multi``) est **pur** : fonctions déterministes,
zéro I/O — seule la couche ``run_weekly_decay`` touche la base. La tâche Celery
``adsengine.decay_assumptions_weekly`` (dans ``tasks.py``, la SEULE surface
autodécouverte) l'appelle société par société.
"""
from __future__ import annotations

import datetime
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# Une « semaine sans test » = 7 jours écoulés depuis le dernier test.
WEEK_DAYS = 7


# ── Cœur mathématique PUR (§3.2) ──────────────────────────────────────────────
def rho(half_life_weeks):
    """Facteur d'oubli hebdomadaire ``ρ = 0.5^(1/H)`` (§3.2).

    À ``H`` semaines, ``ρ^H = 0.5`` : la distance au prior est divisée par 2 en
    une demi-vie. Lève ``ValueError`` si ``H <= 0``. Fonction pure.
    """
    if half_life_weeks <= 0:
        raise ValueError("La demi-vie H doit être strictement positive.")
    return 0.5 ** (1.0 / half_life_weeks)


def decay_step(alpha, beta, alpha0, beta0, half_life_weeks):
    """UN pas d'oubli hebdomadaire vers le prior (§3.2). Fonction pure.

    ``(α, β) ← (ρ·α + (1−ρ)·α₀, ρ·β + (1−ρ)·β₀)`` avec ``ρ = 0.5^(1/H)``.
    Renvoie ``(alpha', beta')``.
    """
    r = rho(half_life_weeks)
    one_minus = 1.0 - r
    return (r * alpha + one_minus * alpha0,
            r * beta + one_minus * beta0)


def decay_multi(alpha, beta, alpha0, beta0, half_life_weeks, weeks):
    """Applique ``weeks`` pas d'oubli d'affilée (§3.2). Fonction pure.

    Équivalent (et testé identique) à la forme fermée ``ρ^weeks·(x−x₀) + x₀``
    par coordonnée : la distance au prior décroît géométriquement en ``ρ``, donc
    est divisée par 2 toutes les ``H`` semaines. ``weeks`` négatif → ``ValueError``.
    """
    if weeks < 0:
        raise ValueError("weeks doit être >= 0.")
    a, b = float(alpha), float(beta)
    for _ in range(int(weeks)):
        a, b = decay_step(a, b, alpha0, beta0, half_life_weeks)
    return (a, b)


def beta_variance(alpha, beta):
    """Variance d'une loi Beta(α, β) : ``αβ / ((α+β)²(α+β+1))``. Pure.

    Sert aux tests dorés du regonflement de variance (§3.2 : l'oubli REGONFLE
    l'incertitude). ``α+β`` doit être > 0.
    """
    s = alpha + beta
    if s <= 0:
        raise ValueError("α+β doit être > 0.")
    return (alpha * beta) / (s * s * (s + 1.0))


# ── Couche modèle (I/O) ───────────────────────────────────────────────────────
def _node_half_life(node):
    """Demi-vie effective du nœud : la valeur posée (override §8.1), sinon le
    défaut de sa classe (``AssumptionNode.HALF_LIFE_WEEKS``)."""
    from .models import AssumptionNode
    return node.demi_vie_semaines or AssumptionNode.HALF_LIFE_WEEKS.get(
        node.classe)


def is_seasonal(node):
    """Vrai si le nœud porte un contexte saisonnier (``tags_saison`` non vide).

    Un nœud saisonnier est EXCLU de l'oubli hebdomadaire (§3.2) : sa vérité vit
    par saison, jamais sur l'horloge de semaine.
    """
    return bool(node.tags_saison)


def needs_weekly_decay(node, *, now=None):
    """Vrai si ce nœud doit être oublié CE tick hebdomadaire.

    Conditions (§3.2) : non saisonnier, non retiré, et « une semaine sans test »
    (jamais testé, ou dernier test il y a ≥ 7 jours). Un nœud testé cette semaine
    vient de recevoir de la donnée fraîche : on ne l'oublie pas.
    """
    from .models import AssumptionNode
    if is_seasonal(node):
        return False
    if node.statut == AssumptionNode.Statut.RETIRED:
        return False
    if node.last_tested_at is None:
        return True
    now = now or timezone.now()
    return node.last_tested_at <= now - datetime.timedelta(days=WEEK_DAYS)


def decay_node(node, *, save=True):
    """Applique UN pas d'oubli au posterior du nœud (in place).

    Oublie ``(node.alpha, node.beta)`` vers ``(node.alpha0, node.beta0)`` à la
    demi-vie de la classe. Renvoie le nœud. Ne vérifie PAS l'éligibilité (voir
    :func:`needs_weekly_decay`) — l'appelant décide.
    """
    a, b = decay_step(
        node.alpha, node.beta, node.alpha0, node.beta0,
        _node_half_life(node))
    node.alpha, node.beta = a, b
    if save:
        node.save(update_fields=['alpha', 'beta', 'updated_at'])
    return node


def run_weekly_decay(company, *, now=None):
    """Oublie d'un cran tous les nœuds ÉLIGIBLES d'une société (§3.2).

    Best-effort par nœud (un nœud en échec n'arrête pas les autres). Multi-tenant :
    la société est toujours passée explicitement. Renvoie le nombre de nœuds
    oubliés.
    """
    from .models import AssumptionNode
    now = now or timezone.now()
    decayed = 0
    for node in AssumptionNode.objects.filter(company=company):
        if not needs_weekly_decay(node, now=now):
            continue
        try:
            decay_node(node, save=True)
            decayed += 1
        except Exception:  # noqa: BLE001 — un nœud en échec n'arrête pas les autres
            logger.warning(
                'assumption_decay: échec oubli nœud=%s société=%s',
                node.pk, company.pk, exc_info=True)
            continue
    return decayed
