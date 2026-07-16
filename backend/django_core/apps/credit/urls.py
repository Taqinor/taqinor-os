from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'limites', views.LimiteCreditViewSet, basename='limitecredit')

urlpatterns = [
    path('ping/', views.ping, name='credit-ping'),
    path('', include(router.urls)),
]
