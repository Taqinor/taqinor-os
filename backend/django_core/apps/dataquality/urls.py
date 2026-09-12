"""URLs de la qualité de données (NTDATA14/15)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompletudeView, DoublonsView, PropositionFusionViewSet,
    RapportQualiteView, RegleQualiteViewSet,
)

router = DefaultRouter()
router.register(r'regles', RegleQualiteViewSet, basename='regle-qualite')
# NTDATA20 — file de revue des doublons (scanner / ignorer / fusionner).
router.register(r'fusions', PropositionFusionViewSet,
                basename='proposition-fusion')

urlpatterns = [
    # NTDATA15 — taux de conformité par règle (?entite= / ?evaluer=1).
    path('rapport/', RapportQualiteView.as_view(), name='qualite-rapport'),
    # NTDATA16 — complétude des champs critiques, par entité métier.
    path('completude/', CompletudeView.as_view(), name='qualite-completude'),
    # NTDATA17/19 — groupes de doublons candidats (clients / fournisseurs /
    # produits). LECTURE SEULE : rien n'est jamais fusionné ici.
    path('doublons/<str:entite>/', DoublonsView.as_view(),
         name='qualite-doublons'),
    path('', include(router.urls)),
]
