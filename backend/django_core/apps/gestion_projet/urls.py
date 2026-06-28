from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AffectationRessourceViewSet,
    BaselinePlanningViewSet,
    CalendrierProjetViewSet,
    DependanceTacheViewSet,
    EquipeViewSet,
    JalonViewSet,
    JourFerieViewSet,
    PhaseProjetViewSet,
    ProjetChantierViewSet,
    ProjetLienViewSet,
    ProjetViewSet,
    RessourceProfilViewSet,
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
router.register(r'baselines', BaselinePlanningViewSet)
router.register(r'ressources', RessourceProfilViewSet)
router.register(r'equipes', EquipeViewSet)
router.register(r'affectations', AffectationRessourceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
