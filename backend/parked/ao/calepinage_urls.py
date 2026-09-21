"""AOF61/AOF62 — routes de l'API de calepinage, dans leur PROPRE fichier.

Elles vivent à part de ``apps/ao/urls.py`` pour une raison mécanique : le
routeur historique y est consommé par ``ContratApiAO`` et par le routeur
``compta``, et trois lanes écrivent simultanément dans ce module. Un fichier
dédié + un unique ``include()`` en fin d'``urls.py`` donnent le même résultat
sans conflit de fusion.

``SimpleRouter`` (et non ``DefaultRouter``) : le second routeur ne doit PAS
publier une seconde racine d'API à ``''`` — elle entrerait en collision avec
celle du routeur historique.

Préfixe complet : ``/api/django/ao/calepinage/…``.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .calepinage_views import (
    CalculerCalepinageView,
    CalepinageVarianteViewSet,
    LancerCalepinageView,
    ResultatCalepinageView,
)

# Pas d'``app_name`` : les noms de route AO sont PLATS et préfixés ``ao-``
# (``apps/ao/urls.py``). Introduire un espace de noms ici obligerait la moitié
# des ``reverse()`` du module à s'écrire différemment de l'autre moitié.

#: Actions de variante d'AOF62 (``retenir`` / ``comparer`` / ``sensibilites``
#: / ``marches``). Le viewset n'a AUCUN mixin de CRUD : le routeur ne génère
#: donc que les routes de ses ``@action``.
router = SimpleRouter()
router.register(r'calepinage/variantes', CalepinageVarianteViewSet,
                basename='ao-calepinage-variante')

urlpatterns = [
    path('calepinage/calculer/', CalculerCalepinageView.as_view(),
         name='ao-calepinage-calculer'),
    path('calepinage/lancer/', LancerCalepinageView.as_view(),
         name='ao-calepinage-lancer'),
    path('calepinage/resultat/<int:job_id>/',
         ResultatCalepinageView.as_view(), name='ao-calepinage-resultat'),
    path('', include(router.urls)),
]
