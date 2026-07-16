from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReserveChantierViewSet, RFIViewSet

router = DefaultRouter()
router.register(
    r'reserves-chantier', ReserveChantierViewSet,
    basename='btp-reserve-chantier')
router.register(r'rfi', RFIViewSet, basename='btp-rfi')

urlpatterns = [
    path('', include(router.urls)),
]
