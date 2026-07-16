"""Routes du moteur publicitaire Meta Ads, montées sous
``/api/django/adsengine/`` (voir ``erp_agentique/urls.py``).

ENG1 expose ``status/`` ; ENG2 ajoute le CRUD ``connexions/`` (connexion Meta).
Les routeurs ViewSet suivants (garde-fous, actions) s'ajoutent ici aux tâches
suivantes de la lane.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MetaConnectionViewSet, StatusView

router = DefaultRouter()
router.register(r'connexions', MetaConnectionViewSet, basename='meta-connexion')

urlpatterns = [
    path('status/', StatusView.as_view(), name='adsengine-status'),
    path('', include(router.urls)),
]
