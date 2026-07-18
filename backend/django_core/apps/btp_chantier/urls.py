from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AvenantChantierViewSet, ChantierDebourseVsFactureView,
    DecompteGeneralViewSet, DiffusionPlanViewSet, JournalChantierViewSet,
    ReserveChantierViewSet, RFIViewSet, VisaDocumentViewSet,
    avenant_public_approuver, avenant_public_detail, diffusion_public_ouvrir,
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
    path('', include(router.urls)),
]
