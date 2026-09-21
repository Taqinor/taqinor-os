"""Routes du module Notes de frais (``apps.frais``) — ODX15.

Nouveau préfixe ``/api/django/frais/…``. Les mêmes ViewSets sont AUSSI servis
par ``apps.compta.urls`` sous ``/api/django/compta/…`` : les routes historiques
sont conservées à l'identique pour ne casser aucun client (frontend, scripts,
tests FG135/FG136).

Basenames explicitement préfixés ``frais-…`` pour NE PAS entrer en collision
avec les noms d'URL du routeur compta (qui reverse ``notefrais-list`` etc.).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BaremeIndemniteViewSet,
    IndemniteChantierViewSet,
    NoteFraisViewSet,
    PlafondNoteFraisViewSet,
    RapportNoteFraisViewSet,
)

router = DefaultRouter()
router.register(r'notes-frais', NoteFraisViewSet, basename='frais-note')
router.register(r'rapports-notes-frais', RapportNoteFraisViewSet,
                basename='frais-rapport')
router.register(r'plafonds-notes-frais', PlafondNoteFraisViewSet,
                basename='frais-plafond')
router.register(r'baremes-indemnite', BaremeIndemniteViewSet,
                basename='frais-bareme')
router.register(r'indemnites-chantier', IndemniteChantierViewSet,
                basename='frais-indemnite')

urlpatterns = [
    path('', include(router.urls)),
]
