from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CalendrierProjetViewSet,
    DependanceTacheViewSet,
    JalonViewSet,
    JourFerieViewSet,
    PhaseProjetViewSet,
    ProjetChantierViewSet,
    ProjetLienViewSet,
    ProjetViewSet,
    TacheViewSet,
)

router = DefaultRouter()
router.register(r'projets', ProjetViewSet)
router.register(r'projet-chantiers', ProjetChantierViewSet)
router.register(r'projet-liens', ProjetLienViewSet)
router.register(r'phases', PhaseProjetViewSet)
router.register(r'taches', TacheViewSet)
router.register(r'dependances', DependanceTacheViewSet)
router.register(r'jalons', JalonViewSet)
router.register(r'calendriers', CalendrierProjetViewSet)
router.register(r'jours-feries', JourFerieViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
