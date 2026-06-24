from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DemandeCongeViewSet,
    DepartementViewSet,
    DocumentEmployeViewSet,
    DossierEmployeViewSet,
    ElementSortieViewSet,
    PointageViewSet,
    PosteViewSet,
    RemunerationViewSet,
    SoldeCongeViewSet,
    TypeAbsenceViewSet,
)

router = DefaultRouter()
router.register(r'departements', DepartementViewSet)
router.register(r'postes', PosteViewSet)
router.register(r'employes', DossierEmployeViewSet)
router.register(r'remunerations', RemunerationViewSet)
router.register(r'documents', DocumentEmployeViewSet)
router.register(r'elements-sortie', ElementSortieViewSet)
router.register(r'types-absence', TypeAbsenceViewSet)
router.register(r'soldes-conge', SoldeCongeViewSet)
router.register(r'demandes-conge', DemandeCongeViewSet)
router.register(r'pointages', PointageViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
