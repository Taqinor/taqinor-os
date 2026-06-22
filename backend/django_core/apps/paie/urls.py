from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BaremeIRViewSet, ParametrePaieViewSet, RubriqueViewSet

router = DefaultRouter()
router.register(r'parametres', ParametrePaieViewSet)
router.register(r'baremes', BaremeIRViewSet)
router.register(r'rubriques', RubriqueViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
