"""PUB18 — Writer d'ÉVIDENCE des posteriors de l'Arbre d'hypothèses (ASG).

Avant : seul le decay hebdo (ASG2) écrivait α/β — AUCUNE preuve RÉELLE (résultat
d'une expérience close, signature Odoo attribuée) n'incrémentait jamais une
croyance : l'« arbre vivant » n'apprenait pas, il ne faisait qu'oublier. Ce module
écrit ces évidences : à la clôture d'une ``Experiment``/d'un ``DecisionLog``
probant (et pour les signatures Odoo attribuées à un nœud testé), il déplace le
posterior Beta du nœud lié (α += succès, β += échecs), pose ``last_tested_at``, et
TRACE la mise à jour dans un ``DecisionLog`` (ASG3 : aucune écriture sans trace).

IDEMPOTENT : une même preuve (``idempotency_key``) n'est jamais recomptée — le
decay n'est donc plus le SEUL writer de α/β, mais une évidence ne compte qu'une
fois (une resynchro / un re-run ne double aucune croyance). Multi-tenant : le
nœud, l'expérience et le log partagent TOUJOURS la même société.

Le nœud d'hypothèse testé par une expérience est résolu via la trace de
``voi.schedule_next`` (``DecisionLog.allocations['winner_node_id']``) — le lien
que l'ordonnanceur VoI (ASG3) écrit à chaque ouverture de slot.
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _evidence_already_recorded(company, idempotency_key):
    """Vrai si une évidence portant cette clé a déjà été appliquée (repérée dans
    un ``DecisionLog`` antérieur). Sans clé, jamais dédupliqué (l'appelant en
    assume la responsabilité)."""
    if not idempotency_key:
        return False
    from .models import DecisionLog
    return DecisionLog.objects.filter(
        company=company, inputs__evidence_key=idempotency_key).exists()


def record_node_evidence(node, experiment, *, successes=0, failures=0,
                         source='experiment', reason_fr='',
                         idempotency_key=''):
    """Applique une évidence Bernoulli/Binomiale au posterior Beta d'un nœud.

    ``α += successes``, ``β += failures`` (bornés ≥ 0), pose ``last_tested_at``,
    et écrit un ``DecisionLog`` de la mise à jour rattaché à ``experiment`` (même
    société que le nœud — invariant multi-tenant). IDEMPOTENT via
    ``idempotency_key``. Renvoie ``(node, decision_log|None)`` — ``(node, None)``
    si déjà enregistré ou si aucune évidence (0/0)."""
    from .models import DecisionLog

    successes = max(int(successes), 0)
    failures = max(int(failures), 0)
    if successes == 0 and failures == 0:
        return node, None
    if experiment.company_id != node.company_id:
        raise ValueError(
            "Le nœud et l'expérience doivent appartenir à la même société.")
    if _evidence_already_recorded(node.company, idempotency_key):
        return node, None

    before = (float(node.alpha), float(node.beta))
    node.alpha = float(node.alpha) + successes
    node.beta = float(node.beta) + failures
    node.last_tested_at = timezone.now()
    node.save(update_fields=['alpha', 'beta', 'last_tested_at', 'updated_at'])

    summary = reason_fr or (
        f"Évidence {source} : +{successes} succès / +{failures} échecs sur "
        f"« {node.enonce_fr[:50]} » (α {before[0]:.1f}→{node.alpha:.1f}, "
        f"β {before[1]:.1f}→{node.beta:.1f}).")
    log = DecisionLog.objects.create(
        company=node.company, experiment=experiment,
        inputs={'evidence_key': idempotency_key, 'source': source,
                'successes': successes, 'failures': failures,
                'node_id': node.pk},
        posteriors={str(node.pk): [node.alpha, node.beta]},
        allocations={'evidence_node_id': node.pk},
        summary_fr=summary)
    logger.info(
        'evidence.record_node_evidence: nœud=%s +%s succès/+%s échecs '
        '(source=%s)', node.pk, successes, failures, source)
    return node, log


def node_for_experiment(experiment):
    """Résout le nœud d'hypothèse TESTÉ par une expérience via la trace de
    ``voi.schedule_next`` (``DecisionLog.allocations['winner_node_id']``). Renvoie
    le nœud le plus récemment ordonnancé (société-scopé), ou ``None``."""
    from .models import AssumptionNode, DecisionLog
    for log in (DecisionLog.objects
                .filter(company=experiment.company, experiment=experiment)
                .order_by('-created_at')):
        node_id = (log.allocations or {}).get('winner_node_id')
        if node_id:
            return AssumptionNode.objects.filter(
                company=experiment.company, pk=node_id).first()
    return None


def record_experiment_outcome(experiment, *, validated, successes=1,
                              failures=1, node=None):
    """À la CLÔTURE d'une ``Experiment`` probante, déplace le posterior du nœud
    lié — la preuve réelle qui manquait à l'arbre.

    Le nœud est résolu via ``node_for_experiment`` (trace VoI) sauf s'il est
    fourni explicitement. ``validated=True`` → succès (``α += successes``) : la
    croyance testée s'est CONFIRMÉE ; ``validated=False`` → échec
    (``β += failures``) : elle est INFIRMÉE. Idempotent par expérience
    (``experiment:<pk>:outcome``) : re-clôturer ne double pas l'évidence. NO-OP
    (``None, None``) si aucun nœud n'est rattaché à l'expérience."""
    node = node or node_for_experiment(experiment)
    if node is None:
        return None, None
    key = f'experiment:{experiment.pk}:outcome'
    n_ok = successes if validated else 0
    n_ko = 0 if validated else failures
    return record_node_evidence(
        node, experiment, successes=n_ok, failures=n_ko,
        source='experiment_outcome',
        reason_fr=(
            f"Clôture d'expérience « {experiment.name} » : hypothèse "
            + ("CONFIRMÉE" if validated else "INFIRMÉE")
            + " — posterior mis à jour (preuve réelle, pas du decay)."),
        idempotency_key=key)


def record_signature_evidence(node, experiment, *, signatures,
                              idempotency_key=''):
    """Signatures Odoo ATTRIBUÉES à un nœud testé = évidence positive FORTE
    (chaque signature confirme la croyance : ``α += signatures``). Idempotent via
    ``idempotency_key`` (ex. ``experiment:<pk>:signatures:<date>``). Renvoie
    ``(node, decision_log|None)``."""
    signatures = max(int(signatures), 0)
    return record_node_evidence(
        node, experiment, successes=signatures, failures=0,
        source='odoo_signature',
        reason_fr=(f"{signatures} signature(s) Odoo attribuée(s) à "
                   f"« {node.enonce_fr[:50]} » — évidence positive (preuve "
                   "argent, jamais le decay)."),
        idempotency_key=idempotency_key)
