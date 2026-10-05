"""Constantes partagées de l'API publique (N89).

Les évènements vivent ici ; les portées (scopes) vivent dans `portees.py`
(SPL307). Le modèle, les permissions, les serializers et les tests partagent
une source unique. Identifiants en anglais (code), libellés FR pour l'écran
Paramètres.
"""


# ── Évènements webhook ───────────────────────────────────────────────────────
EVENT_LEAD_CREATED = 'lead.created'
EVENT_LEAD_LOST = 'lead.lost'
EVENT_LEAD_STAGE_CHANGED = 'lead.stage_changed'
EVENT_DEVIS_SENT = 'devis.sent'
EVENT_DEVIS_ACCEPTED = 'devis.accepted'
EVENT_FACTURE_CREATED = 'facture.created'
EVENT_FACTURE_PAID = 'facture.paid'
EVENT_PAIEMENT_RECORDED = 'paiement.recorded'
EVENT_CHANTIER_COMPLETED = 'chantier.completed'
EVENT_INTERVENTION_COMPLETED = 'intervention.completed'
EVENT_TICKET_CREATED = 'ticket.created'
EVENT_TICKET_RESOLVED = 'ticket.resolved'
# XSTK23 — évènements inventaire.
EVENT_STOCK_SEUIL_ATTEINT = 'stock.seuil_atteint'
EVENT_LIVRAISON_LIVREE = 'livraison.livree'
# NTADM41 — évènements « licences & sièges » (adminops). Payload JAMAIS de
# donnée client — uniquement company_id + plan/sièges (voir
# apps.parametres.services_licence / apps.adminops.receivers).
EVENT_PLAN_CHANGED = 'plan.changed'
EVENT_SIEGES_QUOTA_ATTEINT = 'sieges.quota_atteint'
# NTUX32 — évènements des objets UX (apps.uxviews / apps.trash), consommés
# depuis `core.events` par `apps/publicapi/uxviews_event_receivers.py` (jamais
# un import direct `uxviews`/`trash` -> `publicapi`). Clés SOULIGNÉES (pas
# pointées) : littéralement celles nommées par le plan NTUX32.
EVENT_SAVED_VIEW_SHARED = 'saved_view_shared'
EVENT_RECORD_RESTORED = 'record_restored'
# CAL215 — calepinage VALIDÉ : une variante vient d'être RETENUE (le geste
# « c'est celle-là »). Émis par `apps/publicapi/calepinage_event_receivers.py`,
# qui écoute le modèle via le registre — jamais un import direct
# `apps.calepinage` -> `apps.publicapi`. Charge utile sans géométrie brute ni
# coût interne (mêmes limites que la ressource publique CAL214).
EVENT_CALEPINAGE_VALIDE = 'calepinage.valide'
# CALX368 — calepinage SIMULÉ : une simulation vient d'aboutir et son résultat
# est enregistré. Émis par `apps/publicapi/calepinage_event_receivers.py`, qui
# écoute le signal `core.events.calepinage_simule` posé par le service
# d'orchestration (`apps.calepinage.services.simulation`) — jamais un import
# direct `apps.calepinage` -> `apps.publicapi`. Charge utile : les clés de
# `PublicCalepinageSerializer` plus `p50_kwh`/`performance_ratio`, sans
# géométrie ni coût.
EVENT_CALEPINAGE_SIMULE = 'calepinage.simule'
# NTI18N43 — bascule de langue (document d'un client, ou défaut de la société),
# consommée depuis `core.events.langue_changed` par
# `apps/publicapi/i18n_event_receivers.py` (jamais un import direct
# `crm`/`parametres` -> `publicapi`). Clé SOULIGNÉE : littéralement celle
# nommée par le plan NTI18N43.
EVENT_LANGUE_CHANGED = 'langue_changed'
# NTOBS26 — évènements d'exploitation (apps.statuspage / core.maintenance_
# windows), consommés depuis `core.events` par
# `apps/publicapi/ops_event_receivers.py` (jamais un import direct
# `statuspage` -> `publicapi`). Clés SOULIGNÉES : littéralement celles nommées
# par le plan NTOBS26.
EVENT_INCIDENT_OPENED = 'incident_opened'
EVENT_INCIDENT_RESOLVED = 'incident_resolved'
EVENT_MAINTENANCE_WINDOW_ANNOUNCED = 'maintenance_window_announced'

EVENT_CHOICES = [
    (EVENT_LEAD_CREATED, 'Nouveau lead'),
    (EVENT_LEAD_LOST, 'Lead perdu'),
    (EVENT_LEAD_STAGE_CHANGED, "Lead — étape changée"),
    (EVENT_DEVIS_SENT, 'Devis envoyé'),
    (EVENT_DEVIS_ACCEPTED, 'Devis accepté'),
    (EVENT_FACTURE_CREATED, 'Facture créée'),
    (EVENT_FACTURE_PAID, 'Facture payée'),
    (EVENT_PAIEMENT_RECORDED, 'Paiement enregistré'),
    (EVENT_CHANTIER_COMPLETED, 'Chantier clôturé'),
    (EVENT_INTERVENTION_COMPLETED, 'Intervention terminée'),
    (EVENT_TICKET_CREATED, 'Ticket SAV créé'),
    (EVENT_TICKET_RESOLVED, 'Ticket SAV résolu'),
    (EVENT_STOCK_SEUIL_ATTEINT, 'Stock — seuil atteint'),
    (EVENT_LIVRAISON_LIVREE, 'Livraison — livrée'),
    (EVENT_PLAN_CHANGED, 'Plan de licence — changé'),
    (EVENT_SIEGES_QUOTA_ATTEINT, 'Sièges — quota atteint'),
    (EVENT_SAVED_VIEW_SHARED, 'Vue partagée à l\'équipe'),
    (EVENT_RECORD_RESTORED, 'Élément restauré depuis la corbeille'),
    (EVENT_CALEPINAGE_VALIDE, 'Calepinage — variante retenue'),
    (EVENT_CALEPINAGE_SIMULE, 'Calepinage — simulation aboutie'),
    (EVENT_LANGUE_CHANGED, 'Langue changée (client ou société)'),
    (EVENT_INCIDENT_OPENED, 'Incident — ouvert'),
    (EVENT_INCIDENT_RESOLVED, 'Incident — résolu'),
    (EVENT_MAINTENANCE_WINDOW_ANNOUNCED, 'Fenêtre de maintenance — annoncée'),
]
ALL_EVENTS = [code for code, _ in EVENT_CHOICES]


# ── NTAPI1 — versions servies de l'API publique ─────────────────────────────
# Source UNIQUE des versions montées : le routeur (`public_urls.py`), l'alias
# legacy (`legacy_urls.py`), la résolution de version (`versioning.py`) et la
# doc (`docs.py`) lisent TOUS ces constantes — jamais une chaîne 'v1' en dur.
PUBLIC_API_DEFAULT_VERSION = 'v1'
PUBLIC_API_VERSIONS = ['v1']
# Racine historique NON versionnée, conservée 12 mois comme alias 301 → v1
# (aucune clé existante cassée : elle suit simplement la redirection).
PUBLIC_API_LEGACY_BASE = '/api/public/'
# Racine canonique versionnée (celle que la doc et l'OpenAPI annoncent).
PUBLIC_API_BASE = f'{PUBLIC_API_LEGACY_BASE}{PUBLIC_API_DEFAULT_VERSION}/'
# Fin de vie ANNONCÉE de l'alias non versionné (12 mois après NTAPI1). Lue par
# `legacy_urls.py` pour poser un en-tête `Sunset` sur chaque redirection : une
# intégration qui n'a pas migré le voit dans ses propres logs.
PUBLIC_API_LEGACY_SUNSET = '2027-09-12'


# ── NTAPI26 — environnement d'une clé (préfixe distinct, isolation bac à
# sable) ───────────────────────────────────────────────────────────────────
ENV_TEST = 'test'
ENV_LIVE = 'live'
ENV_CHOICES = [
    (ENV_TEST, 'Test (bac à sable, `tqk_test_…`)'),
    (ENV_LIVE, 'Live (données réelles, `tqk_live_…`)'),
]
ALL_ENVIRONMENTS = [code for code, _ in ENV_CHOICES]
