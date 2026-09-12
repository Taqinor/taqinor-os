"""URLs de la qualité de données (NTDATA14/15)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RapportQualiteView, RegleQualiteViewSet

router = DefaultRouter()
router.register(r'regles', RegleQualiteViewSet, basename='regle-qualite')

urlpatterns = [
    # NTDATA15 — taux de conformité par règle (?entite= / ?evaluer=1).
    path('rapport/', RapportQualiteView.as_view(), name='qualite-rapport'),
    path('', include(router.urls)),
]
