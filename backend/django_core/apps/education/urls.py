from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    AnneeScolaireViewSet, ClasseViewSet, CreneauEmploiDuTempsViewSet,
    EcheancierScolariteViewSet, EleveViewSet, EvaluationViewSet,
    FamilleViewSet, GrilleTarifaireViewSet, InscriptionCantineViewSet,
    InscriptionViewSet, MatiereClasseViewSet, MatiereViewSet,
    MenuCantineViewSet, NiveauViewSet, NoteViewSet,
    ParametresEducationViewSet, PresenceViewSet, RemiseViewSet, SeanceViewSet)

router = DefaultRouter()
router.register(
    r'annees-scolaires', AnneeScolaireViewSet, basename='education-annee-scolaire')
router.register(r'niveaux', NiveauViewSet, basename='education-niveau')
router.register(r'classes', ClasseViewSet, basename='education-classe')
router.register(r'familles', FamilleViewSet, basename='education-famille')
router.register(r'eleves', EleveViewSet, basename='education-eleve')
router.register(
    r'inscriptions', InscriptionViewSet, basename='education-inscription')
router.register(
    r'grilles-tarifaires', GrilleTarifaireViewSet,
    basename='education-grille-tarifaire')
router.register(r'remises', RemiseViewSet, basename='education-remise')
router.register(
    r'echeanciers', EcheancierScolariteViewSet,
    basename='education-echeancier')
router.register(r'seances', SeanceViewSet, basename='education-seance')
router.register(r'presences', PresenceViewSet, basename='education-presence')
router.register(r'matieres', MatiereViewSet, basename='education-matiere')
router.register(
    r'matieres-classe', MatiereClasseViewSet, basename='education-matiere-classe')
router.register(
    r'evaluations', EvaluationViewSet, basename='education-evaluation')
router.register(r'notes', NoteViewSet, basename='education-note')
router.register(
    r'parametres', ParametresEducationViewSet, basename='education-parametres')
router.register(
    r'emploi-du-temps', CreneauEmploiDuTempsViewSet,
    basename='education-emploi-du-temps')
router.register(
    r'menus-cantine', MenuCantineViewSet, basename='education-menu-cantine')
router.register(
    r'inscriptions-cantine', InscriptionCantineViewSet,
    basename='education-inscription-cantine')

urlpatterns = [
    path('', include(router.urls)),
]
