"""Routes de l'API publique de DONNÉES (N89), montées sous /api/public/.

Distinct de `apps.ventes.public_urls` (liens PDF tokenisés sous
/api/django/public/) : ici c'est l'API REST de données par clé d'API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .public_views import (
    PublicLeadViewSet, PublicDevisViewSet,
    PublicFactureViewSet, PublicChantierViewSet, PublicProduitViewSet,
)
from .public_write_views import (
    PublicLeadCreateView, PublicLeadUpdateView, PublicActivityCreateView,
)
from .bulk_views import (
    PublicExportCreateView, PublicImportCreateView, PublicJobViewSet,
    PublicCsvPullExportView,
)
from .public_sandbox_views import SandboxResetView
from .public_changelog_views import PublicChangelogView
from .public_licence_views import PublicLicenceStatutView
from .public_scm_views import (
    PublicPolitiqueStockViewSet, PublicPrevisionDemandeViewSet,
    PublicScmTableauBordReapproView,
)

router = DefaultRouter()
router.register(r'leads', PublicLeadViewSet, basename='public-lead')
router.register(r'devis', PublicDevisViewSet, basename='public-devis')
router.register(r'factures', PublicFactureViewSet, basename='public-facture')
router.register(r'chantiers', PublicChantierViewSet, basename='public-chantier')
router.register(r'produits', PublicProduitViewSet, basename='public-produit')
# NTAPI16/43 — suivi + reprise des jobs bulk (list/retrieve + action `relancer`).
router.register(r'jobs', PublicJobViewSet, basename='public-job')
# NTSCM38 — planification supply chain (apps.scm), scope `read:scm`. Préfixe
# `v1/scm/…` (comme `v1/licence/…`, NTADM42) plutôt que la racine des
# ressources historiques (leads/devis/…) — même routeur, mêmes garanties
# testées par `tests_ntapi42_contract_consistency`.
router.register(
    r'v1/scm/previsions-demande', PublicPrevisionDemandeViewSet,
    basename='public-scm-prevision-demande')
router.register(
    r'v1/scm/politiques-stock', PublicPolitiqueStockViewSet,
    basename='public-scm-politique-stock')

urlpatterns = [
    # XPLT5 — écriture (scopes leads:write / activities:write), distincte du
    # routeur lecture seule ci-dessus.
    path('leads-write/', PublicLeadCreateView.as_view(),
         name='public-lead-write-create'),
    path('leads-write/<int:pk>/', PublicLeadUpdateView.as_view(),
         name='public-lead-write-update'),
    path('leads-write/<int:pk>/activites/', PublicActivityCreateView.as_view(),
         name='public-activity-write-create'),
    # NTAPI14/15 — jobs bulk export/import asynchrones (202 + suivi via `jobs/`).
    path('exports/', PublicExportCreateView.as_view(),
         name='public-exports-create'),
    path('imports/', PublicImportCreateView.as_view(),
         name='public-imports-create'),
    # NTAPI30 — pull CSV live synchrone (token en query string, lecture seule)
    # pour `=IMPORTDATA()` Google Sheets/Excel Web.
    path('exports/<str:entite>.csv', PublicCsvPullExportView.as_view(),
         name='public-exports-csv-pull'),
    # NTAPI27 — reset du bac à sable (clé `test` seule).
    path('sandbox/reset/', SandboxResetView.as_view(),
         name='public-sandbox-reset'),
    # NTAPI24 — fil « changelog API » dédié (public, aucune clé requise).
    path('changelog/', PublicChangelogView.as_view(),
         name='public-changelog'),
    # NTADM42 — statut de licence (plan/modules/sièges) de la société de la clé.
    path('v1/licence/statut/', PublicLicenceStatutView.as_view(),
         name='public-licence-statut'),
    # NTSCM38 — tableau de bord réappro consolidé (NTSCM7), objet unique.
    path('v1/scm/tableau-bord-reappro/', PublicScmTableauBordReapproView.as_view(),
         name='public-scm-tableau-bord-reappro'),
    path('', include(router.urls)),
]
