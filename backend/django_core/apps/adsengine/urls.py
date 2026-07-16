"""Routes du moteur publicitaire Meta Ads, montées sous
``/api/django/adsengine/`` (voir ``erp_agentique/urls.py``).

ENG1 expose ``status/`` ; ENG2 ajoute le CRUD ``connexions/`` (connexion Meta).
Les routeurs ViewSet suivants (garde-fous, actions) s'ajoutent ici aux tâches
suivantes de la lane.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EngineActionViewSet, GuardrailConfigViewSet, MetaConnectionViewSet,
    StatusView,
)

router = DefaultRouter()
router.register(r'connexions', MetaConnectionViewSet, basename='meta-connexion')
router.register(r'garde-fous', GuardrailConfigViewSet, basename='guardrail')
router.register(r'actions', EngineActionViewSet, basename='engine-action')

urlpatterns = [
    path('status/', StatusView.as_view(), name='adsengine-status'),
    path('', include(router.urls)),
]
