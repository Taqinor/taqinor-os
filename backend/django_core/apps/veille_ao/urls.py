"""Routes du module « Veille appels d'offres » (``apps.veille_ao``) — VAO6.

Préfixe ``/api/django/veille_ao/…``, monté depuis ``_APP_URLS`` dans
``erp_agentique/urls.py``.

Le 2ᵉ segment d'URL est **identique à la clé de manifeste** (`veille_ao`, avec
un underscore, pas un tiret) : le gatage 404 des modules désactivés
(``core.permissions.DisabledModuleMiddleware``) dérive du segment, et un
segment en tiret imposerait une entrée ``core/permissions.PREFIX_TO_MODULE``.
Une garde le vérifie dans ``tests/test_smoke.py``.

VAO12 — les basenames sont préfixés ``veille-ao-`` : le dépôt monte plusieurs
routeurs et deux entrées de même nom feraient renvoyer silencieusement la
mauvaise URL à ``reverse()``.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeclencherCollecteView, SanteVeilleView
from .viewsets import (
    AvisMarcheViewSet, ExecutionCollecteViewSet, MotCleVeilleViewSet,
    RegleExclusionViewSet, SourceVeilleViewSet,
)

router = DefaultRouter()
router.register(r'sources', SourceVeilleViewSet,
                basename='veille-ao-source')
router.register(r'avis', AvisMarcheViewSet, basename='veille-ao-avis')
router.register(r'mots-cles', MotCleVeilleViewSet,
                basename='veille-ao-mot-cle')
router.register(r'regles-exclusion', RegleExclusionViewSet,
                basename='veille-ao-regle-exclusion')
# VAO24 — le journal d'exécution, en lecture seule.
router.register(r'executions', ExecutionCollecteViewSet,
                basename='veille-ao-execution')

urlpatterns = [
    # VAO23 — le chemin est LITTÉRAL, fixé par le texte de tâche et déjà
    # publié par le client frontend : « POST /api/django/veille_ao/collecter/ ».
    path('collecter/', DeclencherCollecteView.as_view(),
         name='veille-ao-collecter'),
    # VAO24/VAO35/VAO37 — l'état agrégé, calculé UNE fois côté serveur.
    path('sante/', SanteVeilleView.as_view(), name='veille-ao-sante'),
    path('', include(router.urls)),
]
