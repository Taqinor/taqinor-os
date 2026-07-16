"""Routes du moteur publicitaire Meta Ads, montées sous
``/api/django/adsengine/`` (voir ``erp_agentique/urls.py``).

ENG1 expose ``status/`` ; ENG2 ajoute le CRUD ``connexions/`` (connexion Meta).
Les routeurs ViewSet suivants (garde-fous, actions) s'ajoutent ici aux tâches
suivantes de la lane.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnomalyEventViewSet, ArmDailyStatViewSet, CostPerSignatureView,
    CreativeAssetViewSet, CreativeBacklogItemViewSet,
    CreativeGenerationBatchViewSet, CreativePolicyViewSet, DecisionLogViewSet,
    EngineActionViewSet, EngineAlertViewSet, ExperimentArmViewSet,
    ExperimentViewSet, FlightPhaseViewSet, FlightPlanViewSet,
    GuardrailConfigViewSet, MetaConnectionViewSet, PacingStateViewSet,
    ReconciliationSnapshotViewSet, RulePolicyViewSet, StatusView,
    WiringHealthView,
)

router = DefaultRouter()
router.register(r'connexions', MetaConnectionViewSet, basename='meta-connexion')
router.register(r'garde-fous', GuardrailConfigViewSet, basename='guardrail')
router.register(r'actions', EngineActionViewSet, basename='engine-action')
router.register(r'alertes', EngineAlertViewSet, basename='engine-alert')
router.register(r'creatifs', CreativeAssetViewSet, basename='creative-asset')
router.register(r'policy-creative', CreativePolicyViewSet,
                basename='creative-policy')
# ADSENG3 — expérimentation
router.register(r'experiences', ExperimentViewSet, basename='experiment')
router.register(r'bras', ExperimentArmViewSet, basename='experiment-arm')
router.register(r'stats-bras', ArmDailyStatViewSet, basename='arm-daily-stat')
router.register(r'decisions', DecisionLogViewSet, basename='decision-log')
# ADSENG4 — gardien + trésorerie
router.register(r'regles', RulePolicyViewSet, basename='rule-policy')
router.register(r'anomalies', AnomalyEventViewSet, basename='anomaly-event')
router.register(r'pacing', PacingStateViewSet, basename='pacing-state')
# ADSENG5 — créa + vol
router.register(r'lots-creatifs', CreativeGenerationBatchViewSet,
                basename='creative-batch')
router.register(r'backlog-creatif', CreativeBacklogItemViewSet,
                basename='creative-backlog')
router.register(r'plans-vol', FlightPlanViewSet, basename='flight-plan')
router.register(r'phases-vol', FlightPhaseViewSet, basename='flight-phase')
router.register(r'reconciliations', ReconciliationSnapshotViewSet,
                basename='reconciliation')

urlpatterns = [
    path('status/', StatusView.as_view(), name='adsengine-status'),
    path('metrics/cout-par-signature/', CostPerSignatureView.as_view(),
         name='adsengine-cout-par-signature'),
    path('wiring-health/', WiringHealthView.as_view(),
         name='adsengine-wiring-health'),
    path('', include(router.urls)),
]
