"""ODX23 — Gating ``ModuleToggle`` des notifications d'événements de module.

Un ``EventType`` appartenant sans ambiguïté à UN module métier (ex.
``WARRANTY_EXPIRING`` → ``sav``) ne doit plus notifier personne quand ce
module est désactivé pour la société du destinataire — même sémantique que
l'enforcement API (ODX4, 404) et le catalogue d'actions agent (ARC33) : un
module OFF disparaît de toutes les surfaces.

Whitelist FERMÉE et VOLONTAIREMENT PARTIELLE : seuls les types d'événement
dont l'app propriétaire est certaine sont mappés. Un ``EventType`` absent
d'``EVENT_MODULE`` (événements transverses/fondation — digest, annonces,
chat, approbations, NPS, monitoring…) n'est JAMAIS gaté ici — comportement
historique inchangé, jamais une régression par omission.
"""
from __future__ import annotations

from .models import EventType

EVENT_MODULE = {
    # crm
    EventType.LEAD_ASSIGNED: 'crm',
    EventType.LEAD_NEW: 'crm',
    EventType.HOT_LEAD_UNREAD: 'crm',
    EventType.LEAD_CALLBACK_REQUESTED: 'crm',
    EventType.LEAD_CALLBACK_SLA_BREACH: 'crm',
    # ventes (Devis + Facture + BonCommande vivent dans apps.ventes)
    EventType.DEVIS_ACCEPTED: 'ventes',
    EventType.DEVIS_OPENED: 'ventes',
    EventType.DEVIS_REPLY: 'ventes',
    EventType.DEVIS_NUDGE_DUE: 'ventes',
    EventType.DEVIS_EXPIRED: 'ventes',
    EventType.CLIENT_CONTACT_REQUEST: 'ventes',
    EventType.DEVIS_SUPERIOR_CONTACT_REQUESTED: 'ventes',
    EventType.FACTURE_OVERDUE: 'ventes',
    EventType.FACTURE_PAYEE: 'ventes',
    # installations (chantier)
    EventType.CHANTIER_DUE: 'installations',
    EventType.CHANTIER_ASSIGNE: 'installations',
    # sav
    EventType.WARRANTY_EXPIRING: 'sav',
    EventType.MAINTENANCE_DUE: 'sav',
    EventType.SAV_TICKET_OPENED: 'sav',
    EventType.SAV_TICKET_BREACHING: 'sav',
    EventType.SAV_ACTIVITE_DUE: 'sav',
    EventType.SAV_TICKET_FOLLOWED_UPDATE: 'sav',
    EventType.SAV_VISITES_AUTO_GENEREES: 'sav',
    EventType.SAV_TICKET_RESOLU: 'sav',
    EventType.SAV_EQUIPEMENT_REMPLACE: 'sav',
    # stock
    EventType.STOCK_LOW: 'stock',
    EventType.STOCK_EXPIRATION_SOON: 'stock',
    EventType.SUPPLIER_DOC_EXPIRING: 'stock',
    EventType.BCF_LATE: 'stock',
    EventType.BCF_CANCELLED: 'stock',
    EventType.BCF_RELANCE_PROPOSEE: 'stock',
    # gestion_projet
    EventType.PROJET_RETARD: 'gestion_projet',
    EventType.PROJET_STATUT_CHANGE: 'gestion_projet',
    # flotte
    EventType.FLOTTE_BUDGET_DEPASSEMENT: 'flotte',
    EventType.FLOTTE_ZONE_ALERTE: 'flotte',
    EventType.FLOTTE_DTC_CRITIQUE: 'flotte',
    # qhse
    EventType.INCIDENT_CRITICAL: 'qhse',
    # paie
    EventType.PAIE_RIB_DIVERGENCE: 'paie',
    EventType.PAIE_RUN_PRET: 'paie',
}


def event_module_disabled(event_type, company) -> bool:
    """``event_type`` appartient-il à un module désactivé pour ``company`` ?

    ``False`` (jamais gaté) pour un événement absent d'``EVENT_MODULE`` ou
    sans société. Best-effort : ne lève jamais (retombe sur ``False`` — ne
    bloque jamais une notification par excès de prudence).
    """
    module = EVENT_MODULE.get(event_type)
    if not module or company is None:
        return False
    try:
        from core.feature_flags import module_actif
        return not module_actif(company, module)
    except Exception:  # pragma: no cover - défensif
        return False
