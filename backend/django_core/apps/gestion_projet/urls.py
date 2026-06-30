from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionProjetViewSet,
    AffectationRessourceViewSet,
    BaselinePlanningViewSet,
    CommentaireProjetViewSet,
    CompteRenduReunionViewSet,
    DocumentProjetViewSet,
    BudgetProjetViewSet,
    CalendrierProjetViewSet,
    DependanceTacheViewSet,
    EquipeViewSet,
    IndisponibiliteViewSet,
    JalonViewSet,
    JourFerieViewSet,
    LigneBudgetProjetViewSet,
    ModeleProjetViewSet,
    ModeleTacheViewSet,
    PhaseProjetViewSet,
    ProjetChantierViewSet,
    ProjetLienViewSet,
    ProjetViewSet,
    RessourceProfilViewSet,
    RisqueViewSet,
    TacheViewSet,
    TimesheetViewSet,
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
router.register(r'timesheets', TimesheetViewSet)
router.register(r'risques', RisqueViewSet)
router.register(r'actions', ActionProjetViewSet)
router.register(r'comptes-rendus', CompteRenduReunionViewSet)
router.register(r'documents', DocumentProjetViewSet)
router.register(r'commentaires', CommentaireProjetViewSet)
router.register(r'modeles', ModeleProjetViewSet)
router.register(r'modele-taches', ModeleTacheViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
