from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AvanceSalarieViewSet,
    BaremeIRViewSet,
    BulletinPaieViewSet,
    CumulAnnuelViewSet,
    ElementVariableViewSet,
    ParametrePaieViewSet,
    PeriodePaieViewSet,
    ProfilPaieViewSet,
    RubriqueEmployeViewSet,
    RubriqueViewSet,
    SaisieArretViewSet,
)

router = DefaultRouter()
router.register(r'parametres', ParametrePaieViewSet)
router.register(r'baremes', BaremeIRViewSet)
router.register(r'rubriques', RubriqueViewSet)
router.register(r'profils', ProfilPaieViewSet)
router.register(r'rubriques-employe', RubriqueEmployeViewSet)
router.register(r'periodes', PeriodePaieViewSet)
router.register(r'elements-variables', ElementVariableViewSet)
router.register(r'bulletins', BulletinPaieViewSet)
router.register(r'cumuls-annuels', CumulAnnuelViewSet)
router.register(r'avances', AvanceSalarieViewSet)
router.register(r'saisies', SaisieArretViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
