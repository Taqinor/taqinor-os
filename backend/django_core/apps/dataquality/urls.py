"""URLs de la qualité de données (NTDATA14/15)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CompletudeView, RapportQualiteView, RegleQualiteViewSet

router = DefaultRouter()
router.register(r'regles', RegleQualiteViewSet, basename='regle-qualite')

urlpatterns = [
    # NTDATA15 — taux de conformité par règle (?entite= / ?evaluer=1).
    path('rapport/', RapportQualiteView.as_view(), name='qualite-rapport'),
    # NTDATA16 — complétude des champs critiques, par entité métier.
    path('completude/', CompletudeView.as_view(), name='qualite-completude'),
    path('', include(router.urls)),
]
