"""Sélecteurs LECTURE SEULE d'Automatisations exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les approbations
d'automatisation à travers ces fonctions plutôt qu'en important
`apps.automation.models` directement (voir CLAUDE.md, règle de modularité).
"""


#: APAR43 — déclencheurs dont l'ÉMETTEUR vit dans un module PARQUÉ
#: (``core.parked``) : refusés à la création/modification d'une règle (400
#: « déclencheur indisponible (module parqué) »), absents du brouillon IA et
#: de l'écran. Les règles existantes ne sont PAS supprimées.
DECLENCHEURS_PARQUES = frozenset({
    'projet_status_change',   # gestion_projet
    'projet_phase_change',    # gestion_projet
    'rfq_attribuee',          # achats avancés (RFQ)
})


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
    from .actions import ACTIONS_INDISPONIBLES
    from .models import ActionType, DATE_TRIGGER_TARGETS, TriggerType

    date_targets = {
        f'{app_label}.{model}': sorted(fields)
        for (app_label, model), fields in DATE_TRIGGER_TARGETS.items()
    }
    return {
        # APAR43 — un déclencheur parqué n'est jamais proposé.
        'trigger_types': sorted(
            v for v, _ in TriggerType.choices
            if v not in DECLENCHEURS_PARQUES),
        # APAR25 — une action sans fournisseur (SMS) n'est pas proposée.
        'action_types': sorted(
            v for v, _ in ActionType.choices
            if v not in ACTIONS_INDISPONIBLES),
        'date_trigger_targets': date_targets,
    }
