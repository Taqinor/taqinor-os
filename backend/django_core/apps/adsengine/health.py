"""SIG1 — Deux scores de santé SÉPARÉS (dd-assumption-engine §11).

Poids FIXES, posés en config (``GuardrailConfig.health_*``), RÉVISÉS
TRIMESTRIELLEMENT par un humain — **jamais appris** (Goodhart : un poids CTR
appris pousserait au clickbait, un poids conversations appris pousserait au
curieux ; §11 « le composite reste HORS de l'optimiseur »).

Ce module est **pur** : ZÉRO I/O, ZÉRO import de ``models`` — même discipline
que ``bandit.py``/``rewards.py``/``allocation.py`` (déterminisme, auditabilité).
Il reçoit des dicts de signaux déjà normalisés (0..1, 1 = meilleur) et une
config (objet portant les 4 poids ``health_*``), et rend un score 0..1.

**INVARIANT DUR (testé dans ``tests/test_health.py``) : un score de santé est
AFFICHAGE + ALERTE SEULEMENT — il n'est JAMAIS lu ni consommé par le bandit ou
l'allocation.** Une vente lente (signal OPÉRATIONS) ne doit JAMAIS salir
l'allocation créative — d'où DEUX scores séparés, jamais un composite unique
qui les mélangerait.
"""
from __future__ import annotations

DEFAULT_CREATIVE_WEIGHT_CTR = 60
DEFAULT_CREATIVE_WEIGHT_FRESHNESS = 40
DEFAULT_OPS_WEIGHT_CPL = 60
DEFAULT_OPS_WEIGHT_DELIVERY = 40


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _weighted_average(pairs):
    """``pairs`` = [(poids, valeur_0_1), ...]. Renvoie 0.0 si le total des
    poids est nul ou négatif (config dégénérée — jamais une division par 0)."""
    total_weight = sum(weight for weight, _ in pairs)
    if total_weight <= 0:
        return 0.0
    total = sum(weight * _clamp01(value) for weight, value in pairs)
    return _clamp01(total / total_weight)


def creative_health(signals, config):
    """SIG1 — Score de santé CRÉATIF ∈ [0, 1] (CTR + fraîcheur).

    ``signals`` attend ``ctr`` et ``freshness`` — déjà normalisés 0..1
    (1 = meilleur). ``config`` porte ``health_creative_weight_ctr`` /
    ``health_creative_weight_freshness`` (défauts si l'attribut est absent —
    utilisable avec un objet de test minimal)."""
    w_ctr = getattr(
        config, 'health_creative_weight_ctr', DEFAULT_CREATIVE_WEIGHT_CTR)
    w_fresh = getattr(
        config, 'health_creative_weight_freshness',
        DEFAULT_CREATIVE_WEIGHT_FRESHNESS)
    return _weighted_average([
        (w_ctr, signals.get('ctr', 0.0)),
        (w_fresh, signals.get('freshness', 0.0)),
    ])


def operations_health(signals, config):
    """SIG1 — Score de santé OPÉRATIONS ∈ [0, 1] (CPL + livraison).

    ``signals`` attend ``cpl`` et ``delivery`` — déjà normalisés 0..1
    (1 = meilleur : ``cpl`` est l'INVERSE du coût, un CPL bas doit déjà
    arriver ici proche de 1). ``config`` porte ``health_ops_weight_cpl`` /
    ``health_ops_weight_delivery``."""
    w_cpl = getattr(config, 'health_ops_weight_cpl', DEFAULT_OPS_WEIGHT_CPL)
    w_delivery = getattr(
        config, 'health_ops_weight_delivery', DEFAULT_OPS_WEIGHT_DELIVERY)
    return _weighted_average([
        (w_cpl, signals.get('cpl', 0.0)),
        (w_delivery, signals.get('delivery', 0.0)),
    ])
