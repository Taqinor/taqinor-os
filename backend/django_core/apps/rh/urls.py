from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DepartementViewSet,
    DocumentEmployeViewSet,
    DossierEmployeViewSet,
    RemunerationViewSet,
)

router = DefaultRouter()
router.register(r'departements', DepartementViewSet)
router.register(r'employes', DossierEmployeViewSet)
router.register(r'remunerations', RemunerationViewSet)
router.register(r'documents', DocumentEmployeViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
