"""Routes du moteur publicitaire Meta Ads, montées sous
``/api/django/adsengine/`` (voir ``erp_agentique/urls.py``).

ENG1 expose ``status/`` ; ENG2 ajoute le CRUD ``connexions/`` (connexion Meta).
Les routeurs ViewSet suivants (garde-fous, actions) s'ajoutent ici aux tâches
suivantes de la lane.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CostPerSignatureView, CreativeAssetViewSet, EngineActionViewSet,
    EngineAlertViewSet, GuardrailConfigViewSet, MetaConnectionViewSet,
    StatusView, WiringHealthView,
)

router = DefaultRouter()
router.register(r'connexions', MetaConnectionViewSet, basename='meta-connexion')
router.register(r'garde-fous', GuardrailConfigViewSet, basename='guardrail')
router.register(r'actions', EngineActionViewSet, basename='engine-action')
router.register(r'alertes', EngineAlertViewSet, basename='engine-alert')
router.register(r'creatifs', CreativeAssetViewSet, basename='creative-asset')

urlpatterns = [
    path('status/', StatusView.as_view(), name='adsengine-status'),
    path('metrics/cout-par-signature/', CostPerSignatureView.as_view(),
         name='adsengine-cout-par-signature'),
    path('wiring-health/', WiringHealthView.as_view(),
         name='adsengine-wiring-health'),
    path('', include(router.urls)),
]
