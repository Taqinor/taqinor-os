from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

urlpatterns = [
    path('ping/', views.ping, name='credit-ping'),
    path('', include(router.urls)),
]
