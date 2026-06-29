from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AffectationRessourceViewSet,
    BaselinePlanningViewSet,
    BudgetProjetViewSet,
    CalendrierProjetViewSet,
    DependanceTacheViewSet,
    EquipeViewSet,
    IndisponibiliteViewSet,
    JalonViewSet,
    JourFerieViewSet,
    LigneBudgetProjetViewSet,
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
router.register(r'indisponibilites', IndisponibiliteViewSet)
router.register(r'budgets', BudgetProjetViewSet)
router.register(r'lignes-budget', LigneBudgetProjetViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
