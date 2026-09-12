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
    ParametragePaieCompanyViewSet,
    ParametrePaieViewSet,
    PaysPaieViewSet,
    PeriodePaieViewSet,
    ProfilPaieViewSet,
    RegimeMutuelleViewSet,
    RubriqueEmployeViewSet,
    RubriqueViewSet,
    SaisieArretViewSet,
    SchemaComptablePaieViewSet,
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
# NTPAY12 — pays de paie (activation + moteur de calcul).
router.register(r'pays-paie', PaysPaieViewSet)
# NTPAY3 — plan comptable paie (schéma de ventilation éditable).
router.register(r'schemas-comptables-paie', SchemaComptablePaieViewSet)
# NTPAY23 — réglages globaux du module paie, par société (un seul).
router.register(r'parametrage', ParametragePaieCompanyViewSet)
router.register(r'mes-bulletins', CoffreFortBulletinViewSet,
                basename='coffrefort-bulletin')

urlpatterns = [
    path('', include(router.urls)),
]
