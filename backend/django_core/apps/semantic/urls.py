"""URLs de la couche sémantique (NTDATA9 / NTDATA10 / NTDATA43).

Le CRUD des métriques (NTDATA10) est un routeur DRF à identifiant NUMÉRIQUE
(``lookup_value_regex``) : ``metriques/<id>/`` ne peut donc jamais avaler une
CLÉ. Les lectures PAR CLÉ (``valeur``, ``lignage``) sont des routes explicites
déclarées AVANT le routeur.

L'HISTORIQUE se lit par IDENTIFIANT — une version appartient à UNE ligne de
définition, même si sa clé change en cours de route. La VALEUR et le LIGNAGE se
lisent par CLÉ : c'est par la clé qu'un widget, un rapport ou une alerte
référence une métrique. Les motifs ne se recouvrent pas (``<int:pk>`` contre
``<str:cle>``) et chaque route a SA classe de vue : deux routes sur la même vue
collisionnent d'``operationId`` au schéma OpenAPI (précédent NTDATA5).
"""
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    GlossaireView, MetricDefinitionViewSet, MetriqueExpliquerView,
    MetriqueLignageView, MetriqueValeurView, MetriqueVersionsView,
)

router = SimpleRouter()
router.register(r'metriques', MetricDefinitionViewSet, basename='metrique')

urlpatterns = [
    # NTDATA9 — historique figé des définitions successives d'une métrique.
    path('metriques/<int:pk>/versions/', MetriqueVersionsView.as_view(),
         name='metrique-versions'),
    # NTDATA10 — la valeur d'une métrique par sa clé (résolveur NTDATA8).
    path('metriques/<str:cle>/valeur/', MetriqueValeurView.as_view(),
         name='metrique-valeur'),
    # NTDATA43 — lignage : d'où vient ce chiffre.
    path('metriques/<str:cle>/lignage/', MetriqueLignageView.as_view(),
         name='metrique-lignage'),
    # NTDATA44 — « expliquer ce chiffre » : lignage + lignes sources.
    path('metriques/<str:cle>/expliquer/', MetriqueExpliquerView.as_view(),
         name='metrique-expliquer'),
    # NTDATA49 — dictionnaire de données lisible par tout utilisateur interne.
    path('glossaire/', GlossaireView.as_view(), name='semantic-glossaire'),
    path('', include(router.urls)),
]
