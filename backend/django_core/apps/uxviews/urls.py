from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SavedViewViewSet

router = DefaultRouter()
router.register(r'saved-views', SavedViewViewSet, basename='savedview')

urlpatterns = [
    path('', include(router.urls)),
]
