"""Portées (scopes) de l'API publique — source unique (SPL307).
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
# NTAPI17 — flux d'évènements consommable (`/api/public/v1/events/`). Ce scope
# ouvre le CANAL, il n'accorde AUCUNE donnée à lui seul : chaque évènement
# reste filtré par le scope de lecture de SA famille (voir
# `events_feed.SCOPE_PAR_EVENEMENT`). Une clé qui ne porterait que ce scope lit
# un flux VIDE — le flux n'est jamais un contournement des scopes de lecture.
SCOPE_READ_EVENTS = 'read:events'

# NTUX33 — favoris épinglés (apps.uxviews.FavoriUtilisateur, NTUX12) et vues
# sauvegardées (apps.uxviews.SavedView, NTUX1) en LECTURE SEULE, pour une
# intégration interne (portail interne, dashboard BI tiers) qui a le
# consentement d'un utilisateur (voir `apps/publicapi/public_uxviews_views.py`
# — `?owner=<id>` est le proxy de ce consentement, une clé d'API n'ayant pas
# de notion de session). Un favori est STRICTEMENT personnel (NTUX12) : ce
# scope n'ouvre JAMAIS la lecture d'un favori sans `?owner=` explicite.
SCOPE_READ_FAVORIS = 'read:favoris'
SCOPE_READ_VUES = 'read:vues'

# CAL214 — calepinages (apps.calepinage) en LECTURE SEULE : identité,
# rattachement lead/client/devis, statut, empreinte du layout, puissance et
# nombre de modules RÉELLEMENT calculés, liens de sorties. Ce scope n'ouvre
# JAMAIS la géométrie brute (`roof_layout`, plans/rangées du moteur) ni aucun
# coût interne : voir `public_serializers.PublicCalepinageSerializer`.
SCOPE_READ_CALEPINAGES = 'read:calepinages'
# NTP2P39 — objets Procure-to-Pay (apps.installations : `DemandeAchat` FG310,
# `RFQ` FG311) en LECTURE SEULE, pour un donneur d'ordre ou un outil d'achat
# tiers qui suit l'avancement des réquisitions depuis son propre système.
# Identifiant tel que nommé au plan (``lecture_achats``) — il ne suit pas le
# préfixe ``read:`` des scopes historiques, c'est volontaire et figé ici (exception
# assumée, NTP2P39).
# CE SCOPE N'OUVRE AUCUN COÛT D'ACHAT : ni `prix_estime` de ligne, ni
# `RFQOffre.montant_ht` (documenté « Montants INTERNES »), ni aucune marge —
# voir `apps/publicapi/public_achats_views.py`, qui justifie chaque omission.
SCOPE_READ_ACHATS = 'lecture_achats'

# NTOBS27 — surface « Fiabilité » en LECTURE SEULE, pour qu'un client
# grand-compte branche son propre dashboard de gouvernance fournisseur :
# dernière sauvegarde + drill (NTOBS5), rapport SLA mensuel (NTOBS3) et résumé
# « Limites & usage » (NTOBS8), toujours scopés à la société de la clé.
# Identifiant tel que nommé au plan (``fiabilite:lecture``) — il ne suit pas le
# préfixe ``read:`` des scopes historiques, c'est volontaire et figé ici (même
# exception assumée que ``lecture_achats``, NTP2P39).
# CE SCOPE N'OUVRE AUCUN INTERNE D'INFRASTRUCTURE : ni clé d'objet MinIO, ni
# taille de dump, ni manifeste de bundle, ni la vue cross-tenant NTOBS4 des
# crédits dus — voir `apps/publicapi/public_fiabilite_views.py`, qui justifie
# chaque omission.
SCOPE_READ_FIABILITE = 'fiabilite:lecture'

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
    (SCOPE_READ_EVENTS,
     "Lire le flux d'évènements (limité aux familles déjà autorisées)"),
    (SCOPE_READ_FAVORIS,
     "Lire les favoris épinglés d'un utilisateur consentant (?owner=)"),
    (SCOPE_READ_VUES,
     "Lire les vues sauvegardées d'équipe, ou d'un utilisateur consentant (?owner=)"),
    (SCOPE_READ_CALEPINAGES,
     'Lire les calepinages (sans géométrie brute ni coût interne)'),
    (SCOPE_READ_ACHATS,
     "Lire les demandes d'achat et les demandes de prix (sans aucun prix d'achat)"),
    (SCOPE_READ_FIABILITE,
     'Lire la fiabilité (sauvegardes, rapport SLA mensuel, limites & usage)'),
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
