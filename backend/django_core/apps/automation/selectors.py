"""Sélecteurs LECTURE SEULE d'Automatisations exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les approbations
d'automatisation à travers ces fonctions plutôt qu'en important
`apps.automation.models` directement (voir CLAUDE.md, règle de modularité).
"""


def approvals_en_attente(company):
    """XKB1 — approbations d'automatisation EN ATTENTE d'une société
    (QuerySet). Sélecteur company-wide utilisé par l'agrégateur
    d'approbations cross-app (``apps/reporting``). Lecture seule, scopée
    société."""
    from .models import AutomationApproval
    return (AutomationApproval.objects
            .filter(company=company,
                    status=AutomationApproval.Status.PENDING)
            .select_related('rule')
            .order_by('date_creation', 'id'))
