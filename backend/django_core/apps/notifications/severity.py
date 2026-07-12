"""VX208 — Taxonomie STATIQUE de sévérité/catégorie/nature des `EventType`.

`EventType` avait 42+ valeurs sans rang de sévérité ni catégorie : la cloche
affichait un incident QHSE critique noyé sous des digests, et rien ne
distinguait une notification qui appelle une ACTION (assigner un lead, décider
une approbation) d'une simple INFO (un digest, une annonce publiée). Ce module
fournit trois dicts FERMÉS, indexés par la clé `EventType` — AUCUNE migration
(dérivé en lecture, jamais persisté). Un type non répertorié retombe sur les
défauts sûrs (`'normal'` / `'general'` / info) plutôt qu'une exception — ça ne
casse jamais si un futur `EventType` est ajouté sans être immédiatement classé
ici (l'agent qui l'ajoute est encouragé à le classer, mais ce n'est jamais
bloquant).

Utilisé par `serializers.NotificationSerializer` (exposé en lecture,
`severity`/`category`) et par le frontend (`NotificationBell.jsx`) pour :
  - trier un `INCIDENT_CRITICAL` au-dessus de N `DIGEST` (rang de sévérité) ;
  - grouper par catégorie + dédoublonner par `link` ;
  - séparer le compteur ACTIONS (rouge) du compteur INFOS (point gris) —
    `DIGEST` ne doit JAMAIS compter dans le badge d'actions (`digests.py:169`
    le pousse déjà dans `notify()`, donc dans `feedUnread`/badge, sans
    distinction — c'est le bug (b) que VX208 corrige).
"""
from __future__ import annotations

from .models import EventType

# ─────────────────────────────────────────────────────────────────────────────
# Sévérité — 'critique' > 'normal' > 'info'. Rang numérique pour le tri
# (0 = le plus sévère, remonte en tête de liste devant tout le reste).
# ─────────────────────────────────────────────────────────────────────────────

CRITIQUE = 'critique'
NORMAL = 'normal'
INFO = 'info'

_SEVERITY_RANK = {CRITIQUE: 0, NORMAL: 1, INFO: 2}

# Incidents / SLA franchis / urgences réelles — remontent toujours en tête,
# liseré rouge côté frontend.
EVENT_SEVERITY = {
    EventType.INCIDENT_CRITICAL: CRITIQUE,
    EventType.HOT_LEAD_UNREAD: CRITIQUE,
    EventType.LEAD_CALLBACK_SLA_BREACH: CRITIQUE,
    EventType.SAV_TICKET_BREACHING: CRITIQUE,
    EventType.DA_SOUMISE_STALE: CRITIQUE,
    EventType.APPROVAL_ESCALATED: CRITIQUE,
    EventType.FLOTTE_DTC_CRITIQUE: CRITIQUE,
    EventType.FLOTTE_ZONE_ALERTE: CRITIQUE,
    EventType.BCF_LATE: CRITIQUE,

    # Informationnel pur — jamais une action attendue de l'utilisateur.
    EventType.DIGEST: INFO,
    EventType.ANNONCE_PUBLISHED: INFO,
    EventType.ANNONCE_READ_REMINDER: INFO,
    EventType.DEVIS_OPENED: INFO,
    EventType.FACTURE_PAYEE: INFO,
    EventType.CONTRAT_SIGNE: INFO,
    EventType.SAV_TICKET_RESOLU: INFO,
    EventType.SAV_EQUIPEMENT_REMPLACE: INFO,
    EventType.PROJET_STATUT_CHANGE: INFO,
    EventType.MONITORING_RAPPORT: INFO,
    EventType.BON_COMMANDE_CREE: INFO,
    EventType.SAV_VISITES_AUTO_GENEREES: INFO,
    EventType.NPS_PROMOTEUR: INFO,
    EventType.POST_SOCIAL_RAPPEL: INFO,
    EventType.CHAT_MESSAGE: INFO,
}


def severity_of(event_type: str) -> str:
    """Sévérité de `event_type` — `'normal'` par défaut (jamais d'exception)."""
    return EVENT_SEVERITY.get(event_type, NORMAL)


def severity_rank(event_type: str) -> int:
    """Rang numérique pour le tri (0 = le plus sévère). Défaut = rang `normal`."""
    return _SEVERITY_RANK.get(severity_of(event_type), _SEVERITY_RANK[NORMAL])


# ─────────────────────────────────────────────────────────────────────────────
# Catégorie — regroupement d'affichage (frontend : groupement par catégorie).
# ─────────────────────────────────────────────────────────────────────────────

EVENT_CATEGORY = {
    EventType.LEAD_ASSIGNED: 'ventes',
    EventType.LEAD_NEW: 'ventes',
    EventType.DEVIS_ACCEPTED: 'ventes',
    EventType.DEVIS_OPENED: 'ventes',
    EventType.DEVIS_REPLY: 'ventes',
    EventType.DEVIS_NUDGE_DUE: 'ventes',
    EventType.HOT_LEAD_UNREAD: 'ventes',
    EventType.CLIENT_CONTACT_REQUEST: 'ventes',
    EventType.DEVIS_SUPERIOR_CONTACT_REQUESTED: 'ventes',
    EventType.LEAD_CALLBACK_REQUESTED: 'ventes',
    EventType.LEAD_CALLBACK_SLA_BREACH: 'ventes',
    EventType.DEVIS_EXPIRED: 'ventes',
    EventType.FACTURE_OVERDUE: 'finance',
    EventType.FACTURE_PAYEE: 'finance',
    EventType.BON_COMMANDE_CREE: 'finance',
    EventType.CHANTIER_DUE: 'chantier',
    EventType.CHANTIER_ASSIGNE: 'chantier',
    EventType.WARRANTY_EXPIRING: 'sav',
    EventType.MAINTENANCE_DUE: 'sav',
    EventType.SAV_TICKET_OPENED: 'sav',
    EventType.SAV_TICKET_BREACHING: 'sav',
    EventType.SAV_ACTIVITE_DUE: 'sav',
    EventType.SAV_TICKET_FOLLOWED_UPDATE: 'sav',
    EventType.SAV_VISITES_AUTO_GENEREES: 'sav',
    EventType.SAV_TICKET_RESOLU: 'sav',
    EventType.SAV_EQUIPEMENT_REMPLACE: 'sav',
    EventType.STOCK_LOW: 'stock',
    EventType.STOCK_EXPIRATION_SOON: 'stock',
    EventType.SUPPLIER_DOC_EXPIRING: 'stock',
    EventType.BCF_LATE: 'stock',
    EventType.BCF_CANCELLED: 'stock',
    EventType.BCF_RELANCE_PROPOSEE: 'stock',
    EventType.CHAT_MESSAGE: 'communication',
    EventType.CHAT_MENTION: 'communication',
    EventType.ANNONCE_PUBLISHED: 'communication',
    EventType.ANNONCE_READ_REMINDER: 'communication',
    EventType.DIGEST: 'communication',
    EventType.APPROVAL_REQUESTED: 'approbations',
    EventType.APPROVAL_DECIDED: 'approbations',
    EventType.APPROVAL_REMINDER: 'approbations',
    EventType.APPROVAL_ESCALATED: 'approbations',
    EventType.DA_DECIDEE: 'approbations',
    EventType.DA_SOUMISE_STALE: 'approbations',
    EventType.PROJET_RETARD: 'projet',
    EventType.PROJET_STATUT_CHANGE: 'projet',
    EventType.FLOTTE_BUDGET_DEPASSEMENT: 'flotte',
    EventType.FLOTTE_ZONE_ALERTE: 'flotte',
    EventType.FLOTTE_DTC_CRITIQUE: 'flotte',
    EventType.GED_SIGNATURE_EXPIRATION_PROCHE: 'ged',
    EventType.CONTRAT_SIGNE: 'ged',
    EventType.INCIDENT_CRITICAL: 'qhse',
    EventType.POST_SOCIAL_RAPPEL: 'marketing',
    EventType.NPS_PROMOTEUR: 'marketing',
    EventType.MONITORING_RAPPORT: 'exploitation',
    EventType.PAIE_RIB_DIVERGENCE: 'rh',
    EventType.PAIE_RUN_PRET: 'rh',
}

_CATEGORY_DEFAULT = 'general'


def category_of(event_type: str) -> str:
    """Catégorie d'affichage de `event_type` — `'general'` par défaut."""
    return EVENT_CATEGORY.get(event_type, _CATEGORY_DEFAULT)


# ─────────────────────────────────────────────────────────────────────────────
# Nature — ACTION attendue de l'utilisateur, vs simple INFO. `DIGEST` est
# TOUJOURS une info (jamais une action) : c'est le cœur du bug (b) — avant ce
# fix, un digest gonflait le même badge qu'une vraie action.
# ─────────────────────────────────────────────────────────────────────────────

ACTION_EVENT_TYPES = frozenset({
    EventType.LEAD_ASSIGNED,
    EventType.LEAD_NEW,
    EventType.HOT_LEAD_UNREAD,
    EventType.CLIENT_CONTACT_REQUEST,
    EventType.DEVIS_SUPERIOR_CONTACT_REQUESTED,
    EventType.LEAD_CALLBACK_REQUESTED,
    EventType.LEAD_CALLBACK_SLA_BREACH,
    EventType.DEVIS_NUDGE_DUE,
    EventType.CHANTIER_DUE,
    EventType.CHANTIER_ASSIGNE,
    EventType.FACTURE_OVERDUE,
    EventType.WARRANTY_EXPIRING,
    EventType.MAINTENANCE_DUE,
    EventType.STOCK_LOW,
    EventType.STOCK_EXPIRATION_SOON,
    EventType.SAV_TICKET_OPENED,
    EventType.SAV_TICKET_BREACHING,
    EventType.SAV_ACTIVITE_DUE,
    EventType.CHAT_MENTION,
    EventType.APPROVAL_REQUESTED,
    EventType.APPROVAL_REMINDER,
    EventType.APPROVAL_ESCALATED,
    EventType.SUPPLIER_DOC_EXPIRING,
    EventType.BCF_LATE,
    EventType.PROJET_RETARD,
    EventType.FLOTTE_BUDGET_DEPASSEMENT,
    EventType.FLOTTE_ZONE_ALERTE,
    EventType.FLOTTE_DTC_CRITIQUE,
    EventType.GED_SIGNATURE_EXPIRATION_PROCHE,
    EventType.DEVIS_EXPIRED,
    EventType.INCIDENT_CRITICAL,
    EventType.PAIE_RIB_DIVERGENCE,
    EventType.DA_DECIDEE,
    EventType.DA_SOUMISE_STALE,
    EventType.ANNONCE_READ_REMINDER,
})


def is_action(event_type: str) -> bool:
    """True si `event_type` attend une action de l'utilisateur.

    `DIGEST` (et tout type absent de `ACTION_EVENT_TYPES`) n'en attend
    aucune : c'est une simple info, jamais comptée dans le badge ACTIONS."""
    if event_type == EventType.DIGEST:
        return False
    return event_type in ACTION_EVENT_TYPES
