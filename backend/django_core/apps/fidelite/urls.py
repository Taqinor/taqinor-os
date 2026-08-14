from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CompteFideliteViewSet, ProgrammeFideliteViewSet

router = DefaultRouter()
router.register(r'programmes', ProgrammeFideliteViewSet,
                basename='fidelite-programme')
router.register(r'comptes', CompteFideliteViewSet, basename='fidelite-compte')

urlpatterns = [
    path('', include(router.urls)),
]
