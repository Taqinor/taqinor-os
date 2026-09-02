"""SOL14 — module PROPRIÉTAIRE d'un type d'événement de notification.

LA RÈGLE (SOL14, appliquée dans tout le dépôt) :

    Un ``ModuleToggle`` gate TROIS choses, et trois seulement :
      1. l'accès HTTP (404 du ``DisabledModuleMiddleware``),
      2. les TÂCHES PLANIFIÉES (le beat saute les sociétés module-off),
      3. l'AFFICHAGE (tuiles KPI, écran des notifications, grille d'apps).
    Il ne gate JAMAIS la sémantique interne d'un service : un service appelé
    directement (import, autre app, migration, commande) fait exactement ce
    qu'il a toujours fait. Sinon un module éteint corromprait silencieusement
    des calculs que personne n'a demandé de changer.

Ici : la grille « événement × canaux » de l'écran Notifications proposait des
événements d'applications que la société n'a pas — un utilisateur réglait des
canaux pour des notifications qui ne partiront jamais.

Une clé ABSENTE de cette table n'est JAMAIS filtrée. On ne devine pas par
préfixe : ``devis_*`` appartient à ``ventes``, ``chantier_*`` à
``installations``, ``caisse_ecart_anormal`` à ``pos``, ``da_*`` aux achats —
un préfixe se tromperait, et masquer un événement par erreur prive un
utilisateur d'une alerte sans qu'il comprenne pourquoi. Seuls les événements
DONT LE MODULE EST CERTAIN sont listés.
"""
from __future__ import annotations

#: type d'événement → clé de module (manifeste ODX2) qui le produit.
EVENT_TYPE_MODULE = {
    # Vertical parqué en édition solaire.
    'education_reinscription_relance': 'education',
    # Modules optionnels (éteints à la création d'un tenant — SOL8).
    'transport_etape_retard': 'transport',
    'scm_previsions_generees': 'scm',
    'scm_cycle_sop_ouvert': 'scm',
    'scm_ecart_prevision_important': 'scm',
    'caisse_ecart_anormal': 'pos',
    'paie_rib_divergence': 'paie',
    'paie_run_pret': 'paie',
    # Modules gardés, mais désactivables par société (ODX6).
    'flotte_budget_depassement': 'flotte',
    'flotte_zone_alerte': 'flotte',
    'flotte_dtc_critique': 'flotte',
    'projet_retard': 'gestion_projet',
    'projet_statut_change': 'gestion_projet',
    'ged_signature_expiration_proche': 'ged',
    'chat_message': 'chat',
    'chat_mention': 'chat',
    'monitoring_rapport': 'monitoring',
    'veille_ao_nouveaux_avis': 'veille_ao',
    'veille_ao_alarme_silence': 'veille_ao',
    'idea_vote': 'innovation',
    'idea_received': 'innovation',
    'idea_retenue': 'innovation',
    'idea_realisee': 'innovation',
    'innovation_campagne': 'innovation',
    'feedback_digest': 'innovation',
    'feedback_starred': 'innovation',
}


def event_types_masques(company):
    """Types d'événement à NE PAS proposer à cette société (jamais None)."""
    if company is None:
        return frozenset()
    from core.feature_flags import modules_desactives

    hors = modules_desactives(company)
    if not hors:
        return frozenset()
    return frozenset(
        event_type for event_type, module in EVENT_TYPE_MODULE.items()
        if module in hors
    )
