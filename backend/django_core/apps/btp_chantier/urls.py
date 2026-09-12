from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AbonnementRapportPhotoViewSet, AvenantChantierViewSet,
    ChantierDebourseVsFactureView,
    ChantierClotureBtpView, ChantierExportDossierBtpView,
    ChantierIntervenantsView,
    ChantierPenalitesParLotView, ChantierPlanningLotsView,
    ChantierRapportAvancementView,
    DecompteGeneralViewSet, DiffusionPlanViewSet,
    JournalChantierViewSet, LotViewSet, ParametresBtpView,
    PPSPSChantierViewSet, ReserveChantierViewSet, RFIViewSet,
    VisaDocumentViewSet, avenant_public_approuver, avenant_public_detail,
    diffusion_public_ouvrir,
)

router = DefaultRouter()
router.register(
    r'reserves-chantier', ReserveChantierViewSet,
    basename='btp-reserve-chantier')
router.register(r'rfi', RFIViewSet, basename='btp-rfi')
router.register(r'visas', VisaDocumentViewSet, basename='btp-visa')
router.register(
    r'journal-chantier', JournalChantierViewSet, basename='btp-journal')
router.register(
    r'avenants-chantier', AvenantChantierViewSet, basename='btp-avenant')
router.register(
    r'decomptes-generaux', DecompteGeneralViewSet, basename='btp-dgd')
router.register(
    r'diffusions-plan', DiffusionPlanViewSet, basename='btp-diffusion')
router.register(r'lots', LotViewSet, basename='btp-lot')
router.register(r'ppsps', PPSPSChantierViewSet, basename='btp-ppsps')
router.register(
    r'abonnements-rapport-photo', AbonnementRapportPhotoViewSet,
    basename='btp-abonnement-rapport-photo')

urlpatterns = [
    path(
        'avenants-chantier/public/<str:token>/', avenant_public_detail,
        name='btp-avenant-public-detail'),
    path(
        'avenants-chantier/public/<str:token>/approuver/',
        avenant_public_approuver, name='btp-avenant-public-approuver'),
    path(
        'diffusions-plan/public/<str:token>/ouvrir/',
        diffusion_public_ouvrir, name='btp-diffusion-public-ouvrir'),
    path(
        'chantiers/<int:chantier_id>/debourse-vs-facture/',
        ChantierDebourseVsFactureView.as_view(),
        name='btp-chantier-debourse-vs-facture'),
    path(
        'parametres/', ParametresBtpView.as_view(),
        name='btp-parametres'),
    path(
        'chantiers/<int:chantier_id>/cloture-btp/',
        ChantierClotureBtpView.as_view(),
        name='btp-chantier-cloture'),
    path(
        'chantiers/<int:chantier_id>/rapport-avancement/',
        ChantierRapportAvancementView.as_view(),
        name='btp-chantier-rapport-avancement'),
    path(
        'chantiers/<int:chantier_id>/export-dossier-btp/',
        ChantierExportDossierBtpView.as_view(),
        name='btp-chantier-export-dossier'),
    path(
        'chantiers/<int:chantier_id>/intervenants/',
        ChantierIntervenantsView.as_view(),
        name='btp-chantier-intervenants'),
    path(
        'chantiers/<int:chantier_id>/penalites-par-lot/',
        ChantierPenalitesParLotView.as_view(),
        name='btp-chantier-penalites-par-lot'),
    path(
        'chantiers/<int:chantier_id>/planning-lots/',
        ChantierPlanningLotsView.as_view(),
        name='btp-chantier-planning-lots'),
    path('', include(router.urls)),
]
