from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import portail_avancement
from .views import (
    ActionProjetViewSet,
    AffectationRessourceViewSet,
    BaselinePlanningViewSet,
    ClotureProjetViewSet,
    CommentaireProjetViewSet,
    CompteRenduReunionViewSet,
    DocumentProjetViewSet,
    LotSousTraitanceViewSet,
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
    PeriodeVerrouilleeTempsViewSet,
    PhaseProjetViewSet,
    PortailProjetTokenViewSet,
    ProjetChantierViewSet,
    ProjetLienViewSet,
    ProjetViewSet,
    RessourceProfilViewSet,
    RisqueViewSet,
    SousTraitantViewSet,
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
router.register(r'periodes-verrouillees-temps', PeriodeVerrouilleeTempsViewSet)
router.register(r'risques', RisqueViewSet)
router.register(r'actions', ActionProjetViewSet)
router.register(r'comptes-rendus', CompteRenduReunionViewSet)
router.register(r'documents', DocumentProjetViewSet)
router.register(r'commentaires', CommentaireProjetViewSet)
router.register(r'modeles', ModeleProjetViewSet)
router.register(r'modele-taches', ModeleTacheViewSet)
router.register(r'portail-tokens', PortailProjetTokenViewSet)
router.register(r'sous-traitants', SousTraitantViewSet)
router.register(r'lots-sous-traitance', LotSousTraitanceViewSet)
router.register(r'clotures', ClotureProjetViewSet)

urlpatterns = [
    # Portail PUBLIC (non authentifié) — placé AVANT le routeur pour éviter
    # toute capture par un viewset ; expose uniquement l'avancement non
    # financier d'un projet (PROJ37).
    path('portail/<str:token>/', portail_avancement, name='portail-avancement'),
    path('', include(router.urls)),
]
