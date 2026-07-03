"""Services d'écriture d'Automatisations exposés aux AUTRES apps (XKB1).

Réutilise EXACTEMENT les règles déjà appliquées par
``AutomationApprovalViewSet.approve``/``.reject`` (voir ``apps/automation/
views.py``) : seule une approbation ``PENDING`` est décidable, l'approbateur
et l'horodatage sont posés côté serveur, une approbation relance l'action
différée via ``engine.run_approved``.
"""
from django.utils import timezone


class DecisionError(Exception):
    """Décision invalide sur une approbation (statut non éligible)."""


def decider_approval(approval, *, approve, user):
    """XKB1 — approuve/rejette une ``AutomationApproval`` en attente.

    Lève ``DecisionError`` si l'approbation n'est pas ``PENDING``. Une
    approbation relance l'action différée (``engine.run_approved``) ; un rejet
    n'exécute jamais l'action."""
    from . import engine
    from .models import AutomationApproval

    if approval.status != AutomationApproval.Status.PENDING:
        raise DecisionError('Décision déjà prise.')

    approval.status = (
        AutomationApproval.Status.APPROVED if approve
        else AutomationApproval.Status.REJECTED)
    approval.decided_by = user
    approval.decided_at = timezone.now()
    approval.save(update_fields=['status', 'decided_by', 'decided_at'])
    if approve:
        engine.run_approved(approval, user=user)
    return approval
