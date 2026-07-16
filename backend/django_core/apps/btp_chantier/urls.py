from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    JournalChantierViewSet, ReserveChantierViewSet, RFIViewSet,
    VisaDocumentViewSet,
)

router = DefaultRouter()
router.register(
    r'reserves-chantier', ReserveChantierViewSet,
    basename='btp-reserve-chantier')
router.register(r'rfi', RFIViewSet, basename='btp-rfi')
router.register(r'visas', VisaDocumentViewSet, basename='btp-visa')
router.register(
    r'journal-chantier', JournalChantierViewSet, basename='btp-journal')

urlpatterns = [
    path('', include(router.urls)),
]
