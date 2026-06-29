from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AffectationRosterViewSet,
    CertificationViewSet,
    CompetenceEmployeViewSet,
    CompetenceViewSet,
    DemandeCongeViewSet,
    DepartementViewSet,
    DocumentEmployeViewSet,
    DossierEmployeViewSet,
    ElementSortieViewSet,
    FeuilleTempsViewSet,
    HabilitationViewSet,
    HeuresSuppViewSet,
    IncidentPresenceViewSet,
    PointageViewSet,
    PosteViewSet,
    PresenceChantierViewSet,
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
router.register(r'feuilles-temps', FeuilleTempsViewSet)
router.register(r'heures-supp', HeuresSuppViewSet)
router.register(r'roster', AffectationRosterViewSet)
router.register(r'presences-chantier', PresenceChantierViewSet)
router.register(r'incidents-presence', IncidentPresenceViewSet)
router.register(r'competences', CompetenceViewSet)
router.register(r'competences-employe', CompetenceEmployeViewSet)
router.register(r'habilitations', HabilitationViewSet)
router.register(r'certifications', CertificationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
