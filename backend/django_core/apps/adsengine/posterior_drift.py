"""PUB94 — Dérive des postérieurs + branches mortes (observabilité de L'Arbre).

Le filet qui attrape un moteur SILENCIEUSEMENT cassé. Chaque croyance de l'arbre
d'hypothèses (``AssumptionNode``, ASG1/PUB18) porte un postérieur Beta(α, β) qui
DOIT bouger : les tests le déplacent (ASG3), l'oubli hebdomadaire le ramène vers
le prior (ASG2). Deux pathologies muettes :

  * **branche morte** — un nœud FIGÉ AU PRIOR depuis N semaines : jamais testé (ou
    plus testé depuis longtemps) et retombé exactement sur son prior. Sa croyance
    n'apporte plus rien : à re-tester (via la file VoI) ou à retirer ;
  * **oscillation** — une croyance qui SWINGUE d'un extrême à l'autre : signe d'un
    bug de données AMONT (récompense proxy incohérente), pas d'un vrai apprentissage.

Le cœur (:func:`distance_to_prior`, :func:`oscillation_score`) est **pur** : zéro
I/O. La couche modèle (:func:`node_drift`, :func:`dead_branches`) lit
``AssumptionNode`` (in-app). La détection de branche morte est calculée EN DIRECT
depuis l'état courant du nœud (distance au prior + ancienneté + dernier test) — donc
SANS stockage d'historique ni migration : le flag ``dead_branch`` est exposé
directement SUR L'ARBRE (serializer). La détection d'oscillation, qui suppose une
série temporelle de snapshots, est fournie comme fonction pure (câblable dès qu'un
historique existe) sans imposer de table.
"""
from __future__ import annotations

import datetime

# En deçà de cette distance L1 au prior, le nœud est considéré « figé au prior ».
DEFAULT_EPSILON = 0.01
# Un nœud figé au prior depuis ce nombre de semaines est une branche morte.
DEFAULT_DEAD_BRANCH_WEEKS = 4
# Score d'oscillation au-dessus duquel une croyance est jugée instable.
DEFAULT_OSCILLATION_THRESHOLD = 0.5


# ── Cœur pur ─────────────────────────────────────────────────────────────────
def distance_to_prior(alpha, beta, alpha0, beta0):
    """Distance L1 du postérieur à son prior : ``|α−α₀| + |β−β₀|``. Pure.

    0 = le nœud est EXACTEMENT sur son prior (aucune évidence nette accumulée)."""
    return abs(float(alpha) - float(alpha0)) + abs(float(beta) - float(beta0))


def is_immobile(alpha, beta, alpha0, beta0, *, epsilon=DEFAULT_EPSILON):
    """Vrai si le postérieur est (essentiellement) figé sur son prior. Pure."""
    return distance_to_prior(alpha, beta, alpha0, beta0) <= epsilon


def oscillation_score(means):
    """Score d'oscillation d'une série de moyennes postérieures (oldest→newest).

    Fraction des points intérieurs où la direction du mouvement CHANGE de signe :
    0 = monotone/stable, → 1 = swingue à chaque pas (signe d'un bug de données
    amont, pas d'un vrai apprentissage). Fonction pure ; < 3 points → 0.0.
    """
    xs = [float(m) for m in (means or [])]
    if len(xs) < 3:
        return 0.0
    flips = 0
    for i in range(1, len(xs) - 1):
        d1 = xs[i] - xs[i - 1]
        d2 = xs[i + 1] - xs[i]
        if d1 * d2 < 0:
            flips += 1
    return flips / (len(xs) - 2)


def is_oscillating(means, *, threshold=DEFAULT_OSCILLATION_THRESHOLD,
                   min_points=4):
    """Vrai si la série oscille au-dessus du seuil (assez de points requis). Pure."""
    xs = list(means or [])
    if len(xs) < min_points:
        return False
    return oscillation_score(xs) >= threshold


# ── Couche modèle (I/O, society-scopé) ────────────────────────────────────────
def _weeks_between(later, earlier):
    """Semaines écoulées entre deux datetimes (float), ou None si absent."""
    if later is None or earlier is None:
        return None
    return (later - earlier).days / 7.0


def node_drift(node, *, now=None, min_weeks=DEFAULT_DEAD_BRANCH_WEEKS,
               epsilon=DEFAULT_EPSILON):
    """Dérive d'UN nœud : distance au prior, immobilité, et statut branche morte.

    Une **branche morte** est un nœud NON retiré, figé sur son prior (distance ≤
    epsilon), assez ANCIEN (≥ ``min_weeks``) ET non testé depuis ≥ ``min_weeks``
    (ou jamais). Calcul EN DIRECT depuis l'état courant — aucun historique stocké.
    Renvoie un dict JSON-sûr.
    """
    from django.utils import timezone

    from .models import AssumptionNode

    now = now or timezone.now()
    dist = distance_to_prior(node.alpha, node.beta, node.alpha0, node.beta0)
    immobile = dist <= epsilon
    retired = node.statut == AssumptionNode.Statut.RETIRED

    age_weeks = _weeks_between(now, node.created_at)
    if node.last_tested_at is None:
        weeks_since_test = age_weeks   # jamais testé : ancienneté = âge du nœud
    else:
        weeks_since_test = _weeks_between(now, node.last_tested_at)

    dead = bool(
        immobile and not retired
        and age_weeks is not None and age_weeks >= min_weeks
        and (weeks_since_test is None or weeks_since_test >= min_weeks))
    return {
        'distance_to_prior': round(dist, 6),
        'immobile': immobile,
        'dead_branch': dead,
        'weeks_since_test': (round(weeks_since_test, 2)
                             if weeks_since_test is not None else None),
        'retired': retired,
    }


def is_dead_branch(node, *, now=None, min_weeks=DEFAULT_DEAD_BRANCH_WEEKS,
                   epsilon=DEFAULT_EPSILON):
    """Vrai si ``node`` est une branche morte (flag exposé SUR L'ARBRE)."""
    return node_drift(
        node, now=now, min_weeks=min_weeks, epsilon=epsilon)['dead_branch']


def dead_branches(company, *, now=None, min_weeks=DEFAULT_DEAD_BRANCH_WEEKS,
                  epsilon=DEFAULT_EPSILON):
    """Liste des nœuds branche-morte d'une société (society-scopé)."""
    from .models import AssumptionNode

    out = []
    for node in AssumptionNode.objects.filter(company=company):
        drift = node_drift(node, now=now, min_weeks=min_weeks, epsilon=epsilon)
        if drift['dead_branch']:
            out.append({
                'node_id': node.pk, 'enonce_fr': node.enonce_fr,
                'classe': node.classe, **drift})
    return out


def flag_dead_branches(company, *, now=None, min_weeks=DEFAULT_DEAD_BRANCH_WEEKS):
    """PUB94 — Lève une alerte INFO (🔵) BRAKE-ONLY par branche morte détectée.

    Le filet hebdomadaire : signale un nœud silencieusement figé (moteur amont
    cassé ou hypothèse abandonnée) — jamais un test/une action auto (règle #3 :
    le re-test ne passe que par la file VoI). Idempotent par nœud (dédup
    ``entity_key``). Renvoie le nombre de branches mortes signalées.
    """
    from .models import EngineAlert

    branches = dead_branches(company, now=now, min_weeks=min_weeks)
    flagged = 0
    for b in branches:
        entity_key = f'dead_branch:{b["node_id"]}'
        _, created = EngineAlert.objects.get_or_create(
            company=company, entity_key=entity_key, resolved=False,
            defaults={
                'alert_type': EngineAlert.Type.ANOMALIE,
                'severity': EngineAlert.Severity.INFO,
                'message': (
                    f"🔵 Branche morte : l'hypothèse « {b['enonce_fr'][:50]} » "
                    f"est figée sur son prior depuis ≥ {min_weeks} semaines — "
                    "à re-tester (file VoI) ou à retirer. Jamais automatique."),
                'detail': b})
        if created:
            flagged += 1
    return flagged


# Ancienneté par défaut d'un snapshot hebdo (documentation ; le beat l'utilise).
WEEK = datetime.timedelta(days=7)
