"""Routes du module Appels d'offres (``apps.ao``) — ODX11.

Nouveau préfixe ``/api/django/ao/…``. Les mêmes ViewSets sont AUSSI servis par
``apps.compta.urls`` sous ``/api/django/compta/…`` (routes historiques
conservées à l'identique pour ne casser aucun client). Les ViewSets gardent le
scoping ``request.user.company`` + l'assignation forcée de ``company`` (hérité
de ``_ComptaBaseViewSet`` = ``TenantMixin``).

Basenames explicitement préfixés ``ao-…`` pour NE PAS entrer en collision avec
les noms d'URL du routeur compta (qui reverse ``appeloffre-list`` etc.).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppelOffreViewSet,
    BatimentAOViewSet,
    BordereauPrixViewSet,
    CautionSoumissionViewSet,
    ChaineCotesViewSet,
    DossierSoumissionViewSet,
    EcheanceAOViewSet,
    ExigenceCPSViewSet,
    LigneBordereauViewSet,
    ObstacleAOViewSet,
    PieceConsultationViewSet,
    PieceSoumissionViewSet,
    PlanSourceViewSet,
    ReleveAOViewSet,
    QuestionAOViewSet,
    ResultatAOViewSet,
    SerieQuestionsViewSet,
    ToitureAOViewSet,
)

router = DefaultRouter()
router.register(r'appels-offres', AppelOffreViewSet, basename='ao-appel-offre')
router.register(r'pieces-consultation', PieceConsultationViewSet,
                basename='ao-piece-consultation')
router.register(r'exigences-cps', ExigenceCPSViewSet,
                basename='ao-exigence-cps')
router.register(r'batiments', BatimentAOViewSet, basename='ao-batiment')
router.register(r'toitures', ToitureAOViewSet, basename='ao-toiture')
router.register(r'plans-source', PlanSourceViewSet,
                basename='ao-plan-source')
router.register(r'obstacles', ObstacleAOViewSet,
                basename='ao-obstacle')
router.register(r'chaines-cotes', ChaineCotesViewSet,
                basename='ao-chaine-cotes')
router.register(r'releves', ReleveAOViewSet, basename='ao-releve')
router.register(r'series-questions', SerieQuestionsViewSet,
                basename='ao-serie-questions')
router.register(r'questions', QuestionAOViewSet,
                basename='ao-question')
router.register(r'bordereaux-prix', BordereauPrixViewSet,
                basename='ao-bordereau-prix')
router.register(r'lignes-bordereau', LigneBordereauViewSet,
                basename='ao-ligne-bordereau')
router.register(r'cautions-soumission', CautionSoumissionViewSet,
                basename='ao-caution-soumission')
router.register(r'dossiers-soumission', DossierSoumissionViewSet,
                basename='ao-dossier-soumission')
router.register(r'pieces-soumission', PieceSoumissionViewSet,
                basename='ao-piece-soumission')
router.register(r'echeances-ao', EcheanceAOViewSet, basename='ao-echeance')
router.register(r'resultats-ao', ResultatAOViewSet, basename='ao-resultat')

urlpatterns = [
    path('', include(router.urls)),
]
