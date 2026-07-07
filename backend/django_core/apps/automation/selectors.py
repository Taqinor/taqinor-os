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


def closed_rule_catalogue():
    """XPLT18 — catalogue FERMÉ des déclencheurs/actions/champs-date valides
    pour une ``AutomationRule``, exposé aux AUTRES apps (ex. ``apps.agent``,
    qui construit un brouillon de règle en langage naturel et doit valider le
    JSON produit par le LLM SANS jamais importer ``apps.automation.models``
    directement).

    Renvoie des types simples (listes/dicts de chaînes) — jamais les classes
    ``TriggerType``/``ActionType`` elles-mêmes — pour que l'appelant n'ait
    besoin d'aucune connaissance du modèle Django sous-jacent."""
    from .models import ActionType, DATE_TRIGGER_TARGETS, TriggerType

    date_targets = {
        f'{app_label}.{model}': sorted(fields)
        for (app_label, model), fields in DATE_TRIGGER_TARGETS.items()
    }
    return {
        'trigger_types': sorted(v for v, _ in TriggerType.choices),
        'action_types': sorted(v for v, _ in ActionType.choices),
        'date_trigger_targets': date_targets,
    }
