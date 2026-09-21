from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ContactClientViewSet

router = DefaultRouter()
router.register(r'contacts-client', ContactClientViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
