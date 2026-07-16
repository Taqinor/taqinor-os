from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChambreViewSet, PlanTarifaireViewSet, TypeChambreViewSet

router = DefaultRouter()
router.register(r'types-chambre', TypeChambreViewSet)
router.register(r'chambres', ChambreViewSet)
router.register(r'plans-tarifaires', PlanTarifaireViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
