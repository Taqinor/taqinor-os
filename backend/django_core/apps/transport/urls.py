from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(
    'ordres-transport', views.OrdreTransportViewSet, basename='ordres-transport')

urlpatterns = [
    path('', include(router.urls)),
]
