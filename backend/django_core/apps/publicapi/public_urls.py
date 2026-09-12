"""Routes de l'API publique de DONNÉES (N89), montées sous /api/public/v1/.

Distinct de `apps.ventes.public_urls` (liens PDF tokenisés sous
/api/django/public/) : ici c'est l'API REST de données par clé d'API.

NTAPI1 — cette urlconf est VERSION-AGNOSTIQUE : elle est montée par l'urlconf
racine sous le préfixe de version (`/api/public/v1/`), jamais l'inverse. Aucune
route ne réécrit `v1/` en dur — les chemins servis restent EXACTEMENT les mêmes
qu'avant (`/api/public/v1/licence/statut/`, `/api/public/v1/scm/…` étaient déjà
écrits avec le segment `v1/` en dur ici ; il vient désormais du mont). La racine
historique SANS version reste servie 12 mois par `legacy_urls.py` (301/308 → v1).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .public_views import (
    PublicLeadViewSet, PublicDevisViewSet,
    PublicFactureViewSet, PublicChantierViewSet, PublicProduitViewSet,
)
from .public_write_views import (
    PublicLeadCreateView, PublicLeadUpdateView, PublicActivityCreateView,
    PublicDevisCreateView, PublicTicketCreateView,
)
from .bulk_views import (
    PublicExportCreateView, PublicImportCreateView, PublicJobViewSet,
    PublicCsvPullExportView,
)
from .public_sandbox_views import SandboxResetView
from .public_changelog_views import PublicChangelogView
from .public_errors_views import PublicErrorCatalogView
from .public_events_views import PublicEventFeedView
from .public_oauth_views import PublicOAuthTokenView
from .public_licence_views import PublicLicenceStatutView
from .public_scm_views import (
    PublicPolitiqueStockViewSet, PublicPrevisionDemandeViewSet,
    PublicScmTableauBordReapproView,
)
from .public_btp_views import (
    PublicDecompteGeneralViewSet, PublicRFIViewSet,
    PublicReserveChantierViewSet, PublicVisaDocumentViewSet,
)
from .public_uxviews_views import PublicFavoriViewSet, PublicSavedViewViewSet

router = DefaultRouter()
router.register(r'leads', PublicLeadViewSet, basename='public-lead')
router.register(r'devis', PublicDevisViewSet, basename='public-devis')
router.register(r'factures', PublicFactureViewSet, basename='public-facture')
router.register(r'chantiers', PublicChantierViewSet, basename='public-chantier')
router.register(r'produits', PublicProduitViewSet, basename='public-produit')
# NTAPI16/43 — suivi + reprise des jobs bulk (list/retrieve + action `relancer`).
router.register(r'jobs', PublicJobViewSet, basename='public-job')
# NTSCM38 — planification supply chain (apps.scm), scope `read:scm`. Sous-préfixe
# `scm/…` (comme `licence/…`, NTADM42) plutôt que la racine des ressources
# historiques (leads/devis/…) — même routeur, mêmes garanties testées par
# `tests_ntapi42_contract_consistency`. NTAPI1 — le segment de version vient du
# mont racine, plus du préfixe écrit ici : le chemin servi est inchangé.
router.register(
    r'scm/previsions-demande', PublicPrevisionDemandeViewSet,
    basename='public-scm-prevision-demande')
router.register(
    r'scm/politiques-stock', PublicPolitiqueStockViewSet,
    basename='public-scm-politique-stock')
# NTCON31 — vertical BTP/EPC (apps.btp_chantier), scope `read:btp`. Sous-préfixe
# `btp/…` (même choix que `scm/…` et `licence/…`) : même routeur, mêmes
# garanties testées par `tests_ntapi42_contract_consistency`.
router.register(
    r'btp/reserves', PublicReserveChantierViewSet,
    basename='public-btp-reserve')
router.register(r'btp/rfi', PublicRFIViewSet, basename='public-btp-rfi')
router.register(
    r'btp/visas', PublicVisaDocumentViewSet, basename='public-btp-visa')
router.register(
    r'btp/decomptes-generaux', PublicDecompteGeneralViewSet,
    basename='public-btp-dgd')
# NTUX33 — favoris épinglés + vues sauvegardées (apps.uxviews), scopes
# `read:favoris`/`read:vues`. Racine des ressources historiques (comme
# leads/devis/…) : pas de sous-préfixe dédié, ce sont des ressources
# transverses au même titre.
router.register(r'favoris', PublicFavoriViewSet, basename='public-favori')
router.register(
    r'saved-views', PublicSavedViewViewSet, basename='public-saved-view')

urlpatterns = [
    # XPLT5 — écriture (scopes leads:write / activities:write), distincte du
    # routeur lecture seule ci-dessus.
    path('leads-write/', PublicLeadCreateView.as_view(),
         name='public-lead-write-create'),
    path('leads-write/<int:pk>/', PublicLeadUpdateView.as_view(),
         name='public-lead-write-update'),
    path('leads-write/<int:pk>/activites/', PublicActivityCreateView.as_view(),
         name='public-activity-write-create'),
    # NTAPI18 — écriture étendue : devis BROUILLON (scope devis:write) et
    # ticket SAV correctif (scope tickets:write). Aucun statut aval touché.
    path('devis-write/', PublicDevisCreateView.as_view(),
         name='public-devis-write-create'),
    path('tickets-write/', PublicTicketCreateView.as_view(),
         name='public-ticket-write-create'),
    # NTAPI14/15 — jobs bulk export/import asynchrones (202 + suivi via `jobs/`).
    path('exports/', PublicExportCreateView.as_view(),
         name='public-exports-create'),
    path('imports/', PublicImportCreateView.as_view(),
         name='public-imports-create'),
    # NTAPI30 — pull CSV live synchrone (token en query string, lecture seule)
    # pour `=IMPORTDATA()` Google Sheets/Excel Web.
    path('exports/<str:entite>.csv', PublicCsvPullExportView.as_view(),
         name='public-exports-csv-pull'),
    # NTAPI19 — jeton OAuth2 client_credentials (endpoint non authentifié :
    # c'est lui qui authentifie, d'où son throttle dédié par IP).
    path('oauth/token/', PublicOAuthTokenView.as_view(),
         name='public-oauth-token'),
    # NTAPI17 — flux d'évènements consommable par curseur (CDC léger).
    path('events/', PublicEventFeedView.as_view(), name='public-event-feed'),
    # NTAPI27 — reset du bac à sable (clé `test` seule).
    path('sandbox/reset/', SandboxResetView.as_view(),
         name='public-sandbox-reset'),
    # NTAPI24 — fil « changelog API » dédié (public, aucune clé requise).
    path('changelog/', PublicChangelogView.as_view(),
         name='public-changelog'),
    # NTAPI4 — catalogue d'erreurs consultable (public, aucune clé requise) :
    # cible du `doc_url` de chaque enveloppe d'erreur NTAPI3.
    path('errors/', PublicErrorCatalogView.as_view(),
         name='public-error-catalog'),
    # NTADM42 — statut de licence (plan/modules/sièges) de la société de la clé.
    path('licence/statut/', PublicLicenceStatutView.as_view(),
         name='public-licence-statut'),
    # NTSCM38 — tableau de bord réappro consolidé (NTSCM7), objet unique.
    path('scm/tableau-bord-reappro/', PublicScmTableauBordReapproView.as_view(),
         name='public-scm-tableau-bord-reappro'),
    path('', include(router.urls)),
]
