from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReserveChantierViewSet

router = DefaultRouter()
router.register(
    r'reserves-chantier', ReserveChantierViewSet,
    basename='btp-reserve-chantier')

urlpatterns = [
    path('', include(router.urls)),
]
