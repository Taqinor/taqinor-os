"""ASG4 — Cascade d'invalidation de l'arbre d'hypothèses (§3.5).

L'arbre est un DAG léger, pas un arbre pur (§3.5). Quand la croyance d'un nœud
BASCULE (un test le contredit, un humain l'invalide), ses dépendants deviennent
SUSPECTS et doivent être re-testés — mais **jamais automatiquement** : ils sont
marqués ``stale`` (périmés) + une alerte 🔵 (INFO) est levée, et c'est TOUT. Le
re-test ne passe QUE par la file VoI (ASG3) quand un slot s'ouvre — la cascade ne
déclenche JAMAIS un test, une expérience, ni une allocation (invariant testé).

Deux familles d'arêtes suivies (§3.1/§3.5) :
  * **hiérarchiques** — ``parent`` → ``children`` (« si le hook parent bascule,
    ses variantes enfants deviennent suspectes ») ;
  * **non hiérarchiques** — ``invalidation_links`` (M2M orienté : « si ce nœud
    bascule, celui-là aussi devient suspect ») pour les interactions que l'arbre
    one-variable-at-a-time rate.

La cascade traverse ces deux familles en profondeur (BFS), borne les cycles par un
ensemble ``visited``, et est IDEMPOTENTE : un nœud déjà ``stale``/``retired`` n'est
ni re-marqué ni re-alerté. Multi-tenant : la traversée reste dans la société du
nœud d'origine (les FK/M2M sont déjà company-scopées côté modèle).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _dependents(node):
    """Nœuds directement invalidés par ``node`` : ses enfants hiérarchiques
    (``children``) + ses cibles d'``invalidation_links`` (arêtes orientées). Dédup
    par pk (un nœud à la fois enfant ET lié n'est visité qu'une fois)."""
    seen = {}
    for child in node.children.all():
        seen[child.pk] = child
    for linked in node.invalidation_links.all():
        seen[linked.pk] = linked
    return list(seen.values())


def invalidate_cascade(node, *, reason_fr='', actor=None):
    """Marque ``stale`` (+ alerte 🔵) tous les dépendants d'un nœud basculé (§3.5).

    Part de ``node`` (le nœud dont la croyance a basculé — son propre statut est
    posé par l'appelant, pas ici), traverse en profondeur ``children`` +
    ``invalidation_links``, et pour chaque dépendant NON déjà ``stale``/``retired``
    : pose ``statut = stale`` et lève une ``EngineAlert`` INFO (🔵). **Ne
    déclenche AUCUN test** : ``last_tested_at`` n'est jamais touché, aucune
    ``Experiment``/``DecisionLog`` n'est créée. Idempotent (dédup par pk + garde
    de statut). Renvoie ``{'invalidated': [pk...], 'alerts': n}``.
    """
    from .models import AssumptionNode

    reason_fr = reason_fr or (
        f"Nœud « {node.enonce_fr[:50]} » basculé : dépendants marqués périmés "
        "(re-test via la file VoI uniquement, jamais automatique).")

    invalidated = []
    alerts = 0
    visited = {node.pk}
    frontier = _dependents(node)
    while frontier:
        current = frontier.pop()
        if current.pk in visited:
            continue
        visited.add(current.pk)
        # Traverse TOUJOURS les dépendants (même si le nœud était déjà stale :
        # la cascade doit atteindre un enfant NON stale plus bas dans l'arbre).
        frontier.extend(_dependents(current))
        # Un nœud déjà périmé ou retiré n'est ni re-marqué ni re-alerté.
        if current.statut in (
                AssumptionNode.Statut.STALE, AssumptionNode.Statut.RETIRED):
            continue
        current.statut = AssumptionNode.Statut.STALE
        current.save(update_fields=['statut', 'updated_at'])
        _raise_stale_alert(current, node, reason_fr)
        invalidated.append(current.pk)
        alerts += 1

    logger.info(
        'assumption_graph: cascade nœud=%s société=%s → %s périmé(s)',
        node.pk, node.company_id, len(invalidated))
    return {'invalidated': invalidated, 'alerts': alerts}


def _raise_stale_alert(stale_node, origin_node, reason_fr):
    """Lève une ``EngineAlert`` INFO (🔵) signalant un nœud périmé par cascade.

    Sévérité INFO = 🔵 (``rules.SEVERITY_INFO``). Ne propose AUCUNE action (pas
    de re-test) : c'est un signal, pas un déclencheur."""
    from .models import EngineAlert

    return EngineAlert.objects.create(
        company=stale_node.company,
        alert_type=EngineAlert.Type.ANOMALIE,
        severity=EngineAlert.Severity.INFO,
        message=(
            f"🔵 Hypothèse « {stale_node.enonce_fr[:50]} » périmée : le nœud "
            f"« {origin_node.enonce_fr[:40]} » a basculé. À re-tester via la "
            "file (jamais automatique)."),
        entity_key=f'assumption:{stale_node.pk}',
        detail={
            'node_id': stale_node.pk,
            'origin_node_id': origin_node.pk,
            'reason': 'cascade_invalidation',
            'reason_fr': reason_fr,
        })
