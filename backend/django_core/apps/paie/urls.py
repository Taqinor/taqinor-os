from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdhesionMutuelleViewSet,
    AvanceSalarieViewSet,
    BaremeIRViewSet,
    BulletinPaieViewSet,
    CoffreFortBulletinViewSet,
    CumulAnnuelViewSet,
    EcheanceDeclarativeViewSet,
    ElementVariableViewSet,
    LigneVirementViewSet,
    OrdreVirementViewSet,
    ParametrePaieViewSet,
    PeriodePaieViewSet,
    ProfilPaieViewSet,
    RegimeMutuelleViewSet,
    RubriqueEmployeViewSet,
    RubriqueViewSet,
    SaisieArretViewSet,
    StructurePaieViewSet,
    TypeEntreePonctuelleViewSet,
)

router = DefaultRouter()
router.register(r'parametres', ParametrePaieViewSet)
router.register(r'baremes', BaremeIRViewSet)
router.register(r'rubriques', RubriqueViewSet)
router.register(r'types-entree-ponctuelle', TypeEntreePonctuelleViewSet)
router.register(r'profils', ProfilPaieViewSet)
router.register(r'rubriques-employe', RubriqueEmployeViewSet)
router.register(r'structures', StructurePaieViewSet)
router.register(r'regimes-mutuelle', RegimeMutuelleViewSet)
router.register(r'adhesions-mutuelle', AdhesionMutuelleViewSet)
router.register(r'periodes', PeriodePaieViewSet)
router.register(r'elements-variables', ElementVariableViewSet)
router.register(r'bulletins', BulletinPaieViewSet)
router.register(r'cumuls-annuels', CumulAnnuelViewSet)
router.register(r'avances', AvanceSalarieViewSet)
router.register(r'saisies', SaisieArretViewSet)
router.register(r'ordres-virement', OrdreVirementViewSet)
router.register(r'lignes-virement', LigneVirementViewSet)
router.register(r'echeances-declaratives', EcheanceDeclarativeViewSet)
router.register(r'mes-bulletins', CoffreFortBulletinViewSet,
                basename='coffrefort-bulletin')

urlpatterns = [
    path('', include(router.urls)),
]
