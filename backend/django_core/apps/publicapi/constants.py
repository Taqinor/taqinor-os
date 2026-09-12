"""Constantes partagées de l'API publique (N89).

Les scopes et les évènements vivent ici pour que le modèle, les permissions,
les serializers et les tests partagent une source unique. Identifiants en
anglais (code), libellés FR pour l'écran Paramètres.
"""

# ── Scopes (droits de lecture par objet métier) ──────────────────────────────
SCOPE_READ_LEADS = 'read:leads'
SCOPE_READ_DEVIS = 'read:devis'
SCOPE_READ_FACTURES = 'read:factures'
SCOPE_READ_CHANTIERS = 'read:chantiers'
# XSTK23 — lecture produits (disponibilité) : SKU/nom/marque/catégorie/quantité
# disponible UNIQUEMENT. Ni prix_achat ni prix_vente ni aucun coût.
SCOPE_READ_STOCK = 'read:stock'
# NTADM42 — statut de licence de la société porteuse de la clé
# (plan_code/modules_inclus/sieges_max/sieges_utilises UNIQUEMENT — jamais de
# prix ni d'historique).
SCOPE_READ_LICENCE = 'read:licence'
# NTSCM38 — planification supply chain (apps.scm) : prévisions de demande,
# politiques de stock (ROP/stock de sécurité, JAMAIS `prix_achat`) et le
# tableau de bord réappro consolidé, en LECTURE SEULE. Intégration externe
# (TMS, connecteur planification tiers).
SCOPE_READ_SCM = 'read:scm'
# NTJUR41 — affaires juridiques (apps.juridique) en LECTURE SEULE : registre
# des dossiers et budget d'un dossier, pour un usage externe RESTREINT
# (courtier d'assurance RC, cabinet partenaire). Le filtrage de
# CONFIDENTIALITÉ s'applique AUSSI à l'accès par clé : une clé n'est jamais un
# administrateur, donc elle ne voit JAMAIS un dossier `confidentiel`.
# Identifiant tel que nommé au plan (``juridique:read``) — il ne suit pas le
# préfixe ``read:`` des scopes historiques, c'est volontaire et figé ici.
SCOPE_READ_JURIDIQUE = 'juridique:read'
# NTAPI17 — flux d'évènements consommable (`/api/public/v1/events/`). Ce scope
# ouvre le CANAL, il n'accorde AUCUNE donnée à lui seul : chaque évènement
# reste filtré par le scope de lecture de SA famille (voir
# `events_feed.SCOPE_PAR_EVENEMENT`). Une clé qui ne porterait que ce scope lit
# un flux VIDE — le flux n'est jamais un contournement des scopes de lecture.
SCOPE_READ_EVENTS = 'read:events'

# NTCON31 — vertical BTP/EPC (apps.btp_chantier) en LECTURE SEULE : réserves
# de chantier, RFI, visas de documents et décomptes généraux, pour une MOE ou
# un maître d'ouvrage externe qui suit l'exécution depuis son propre outil.
# AUCUNE donnée de coût INTERNE n'est exposée par ce scope : ni déboursé
# (NTCON11), ni exposition aux pénalités (NTCON15), ni prix d'achat. Le DGD
# expose ses montants CONTRACTUELS (marché, avenants, situations, solde) —
# ce sont les chiffres que le client signe, pas la marge de l'entreprise.
SCOPE_READ_BTP = 'read:btp'

# XPLT5 — scopes d'ÉCRITURE (créer/mettre à jour un lead, créer une activité).
# La société est TOUJOURS forcée depuis la clé (jamais du body) ; les stages
# viennent de STAGES.py (jamais hardcodés).
SCOPE_WRITE_LEADS = 'leads:write'
SCOPE_WRITE_ACTIVITIES = 'activities:write'
# NTAPI18 — écriture ÉTENDUE. `devis:write` crée un devis BROUILLON rattaché à
# un lead/client existant (jamais un devis envoyé/accepté : l'API ne change
# aucun statut aval, règle #4) ; `tickets:write` ouvre un ticket SAV correctif.
# Les deux passent EXCLUSIVEMENT par les `services.py` des apps cibles.
SCOPE_WRITE_DEVIS = 'devis:write'
SCOPE_WRITE_TICKETS = 'tickets:write'

# Ordre = ordre d'affichage dans l'écran Paramètres.
SCOPE_CHOICES = [
    (SCOPE_READ_LEADS, 'Lire les leads'),
    (SCOPE_READ_DEVIS, 'Lire les devis'),
    (SCOPE_READ_FACTURES, 'Lire les factures'),
    (SCOPE_READ_CHANTIERS, 'Lire les chantiers'),
    (SCOPE_READ_STOCK, 'Lire le stock (disponibilité, sans coûts)'),
    (SCOPE_READ_LICENCE, 'Lire le statut de licence (plan, modules, sièges)'),
    (SCOPE_READ_SCM, 'Lire la planification supply chain (prévisions, politiques de stock, réappro)'),
    (SCOPE_READ_JURIDIQUE,
     'Lire les dossiers juridiques non confidentiels et leur budget'),
    (SCOPE_READ_EVENTS,
     "Lire le flux d'évènements (limité aux familles déjà autorisées)"),
    (SCOPE_READ_BTP,
     'Lire le suivi de chantier BTP (réserves, RFI, visas, décomptes)'),
    (SCOPE_WRITE_LEADS, 'Créer/mettre à jour des leads'),
    (SCOPE_WRITE_ACTIVITIES, 'Créer des activités (notes) sur un lead'),
    (SCOPE_WRITE_DEVIS, 'Créer un devis brouillon (jamais envoyé/accepté)'),
    (SCOPE_WRITE_TICKETS, 'Créer un ticket SAV correctif'),
]
ALL_SCOPES = [code for code, _ in SCOPE_CHOICES]

# NTAPI14/15 — le scope requis pour exporter/importer une ENTITÉ est le MÊME
# que celui de la lecture/écriture synchrone de cette ressource (jamais un
# scope bulk séparé qui dupliquerait le contrôle d'accès). Une entité absente
# de ces mappings est simplement non exportable/importable en bulk.
EXPORT_SCOPE_BY_ENTITY = {
    'leads': SCOPE_READ_LEADS,
    'devis': SCOPE_READ_DEVIS,
    'factures': SCOPE_READ_FACTURES,
    'chantiers': SCOPE_READ_CHANTIERS,
    'produits': SCOPE_READ_STOCK,
}
IMPORT_SCOPE_BY_ENTITY = {
    'leads': SCOPE_WRITE_LEADS,
    'activites': SCOPE_WRITE_ACTIVITIES,
}


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
# NTSCM39 — évènements de planification supply chain (apps.scm), consommés
# depuis `core.events` par `apps/publicapi/scm_event_receivers.py`.
EVENT_SCM_RUPTURE_IMMINENTE = 'scm.rupture_imminente_detectee'
EVENT_SCM_CYCLE_SOP_CLOTURE = 'scm.cycle_sop_cloture'
# NTCON31 — évènements du vertical BTP/EPC (apps.btp_chantier), consommés
# depuis `core.events` par `apps/publicapi/btp_event_receivers.py` (jamais un
# import direct `btp_chantier` -> `publicapi`).
EVENT_BTP_RESERVE_LEVEE = 'reserve.levee'
EVENT_BTP_RFI_REPONDU = 'rfi.repondu'
EVENT_BTP_VISA_APPROUVE = 'visa.approuve'
EVENT_BTP_DGD_FINALISE = 'dgd.finalise'
# NTUX32 — évènements des objets UX (apps.uxviews / apps.trash), consommés
# depuis `core.events` par `apps/publicapi/uxviews_event_receivers.py` (jamais
# un import direct `uxviews`/`trash` -> `publicapi`). Clés SOULIGNÉES (pas
# pointées) : littéralement celles nommées par le plan NTUX32.
EVENT_SAVED_VIEW_SHARED = 'saved_view_shared'
EVENT_RECORD_RESTORED = 'record_restored'

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
    (EVENT_SCM_RUPTURE_IMMINENTE, 'Supply chain — rupture imminente détectée'),
    (EVENT_SCM_CYCLE_SOP_CLOTURE, 'Supply chain — cycle S&OP clôturé'),
    (EVENT_BTP_RESERVE_LEVEE, 'BTP — réserve levée'),
    (EVENT_BTP_RFI_REPONDU, 'BTP — RFI répondu'),
    (EVENT_BTP_VISA_APPROUVE, 'BTP — visa approuvé'),
    (EVENT_BTP_DGD_FINALISE, 'BTP — décompte général finalisé'),
    (EVENT_SAVED_VIEW_SHARED, 'Vue partagée à l\'équipe'),
    (EVENT_RECORD_RESTORED, 'Élément restauré depuis la corbeille'),
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
