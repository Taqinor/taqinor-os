"""Routes du moteur publicitaire Meta Ads, montées sous
``/api/django/adsengine/`` (voir ``erp_agentique/urls.py``).

ENG1 expose ``status/`` ; ENG2 ajoute le CRUD ``connexions/`` (connexion Meta).
Les routeurs ViewSet suivants (garde-fous, actions) s'ajoutent ici aux tâches
suivantes de la lane.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .odoo_views import OdooCostPerSignatureView
from .views import (
    AdCampaignMirrorViewSet, AdPreviewsView, AnomalyEventViewSet,
    ArmDailyStatViewSet,
    BacklogDropAssetView, BacklogListView, BacklogLotApproveView,
    BreakdownsView, BriefLatestView, CampaignFunnelView, CohortReportView,
    CostPerSignatureView,
    CreativeAssetViewSet, CreativeBacklogItemViewSet,
    CreativeGenerationBatchViewSet, CreativePolicyViewSet, DecisionLogViewSet,
    EngineActionViewSet, EngineAlertViewSet, ExperimentArmViewSet,
    ExperimentViewSet, FlightPhaseViewSet, FlightPlanViewSet,
    GuardrailConfigViewSet, GuardrailSingletonView, MediaResolveView,
    MetaConnectionHealthView,
    MetaConnectionStatusView, MetaConnectionViewSet, MetricsDashboardView,
    MetricsLeadsView, MetricsPacingView, PacingStateViewSet, RealLeadsView,
    ReconciliationListView, ReconciliationSnapshotViewSet, ReportExportView,
    RulePolicyViewSet, SimulationDetailView, SimulationListView, StatusView,
    VariantReportView, WiringHealthView,
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
# ADSENGINT2 — miroirs de campagne (liste + sync-now + creative-ranking).
router.register(r'campaigns', AdCampaignMirrorViewSet,
                basename='ad-campaign-mirror')

urlpatterns = [
    path('status/', StatusView.as_view(), name='adsengine-status'),
    path('metrics/cout-par-signature/', CostPerSignatureView.as_view(),
         name='adsengine-cout-par-signature'),
    # ADSENG-ODOO — même chiffre, dénominateur = signatures RÉELLES Odoo.
    path('metrics/cost-per-signature-odoo/',
         OdooCostPerSignatureView.as_view(),
         name='adsengine-cost-per-signature-odoo'),
    path('wiring-health/', WiringHealthView.as_view(),
         name='adsengine-wiring-health'),
    # ── ADSENGINT1/ADSENGINT2 — endpoints console (vues minces) ──────────────
    # ENG22 — connexion Meta (statut + save write-only) + santé du câblage.
    path('connection/', MetaConnectionStatusView.as_view(),
         name='adsengine-connection'),
    path('connection/health/', MetaConnectionHealthView.as_view(),
         name='adsengine-connection-health'),
    # ENG22 — garde-fous singleton (GET/PATCH sans id).
    path('guardrail/', GuardrailSingletonView.as_view(),
         name='adsengine-guardrail'),
    # ENG23 — dashboard « un chiffre » + drill-down leads + pacing.
    path('metrics/dashboard/', MetricsDashboardView.as_view(),
         name='adsengine-metrics-dashboard'),
    path('metrics/leads/', MetricsLeadsView.as_view(),
         name='adsengine-metrics-leads'),
    path('metrics/pacing/', MetricsPacingView.as_view(),
         name='adsengine-metrics-pacing'),
    # ENG42 — réconciliation (liste reshaped pour l'écran).
    path('reconciliation/', ReconciliationListView.as_view(),
         name='adsengine-reconciliation'),
    # ENG26 — dernier brief hebdomadaire.
    path('brief/', BriefLatestView.as_view(), name='adsengine-brief'),
    # ENG44 — simulations (catalogue de scénarios + shell de rapport).
    path('simulations/', SimulationListView.as_view(),
         name='adsengine-simulations'),
    path('simulations/<str:key>/', SimulationDetailView.as_view(),
         name='adsengine-simulation-detail'),
    # ENG41 — backlog par campagne + approbation de lot + dépôt d'asset.
    path('backlog/', BacklogListView.as_view(), name='adsengine-backlog'),
    path('backlog/lots/<int:lot_id>/approuver/',
         BacklogLotApproveView.as_view(), name='adsengine-backlog-lot-approve'),
    path('backlog/<int:campagne_id>/assets/',
         BacklogDropAssetView.as_view(), name='adsengine-backlog-drop-asset'),
    # ADSENG33 — drill-downs de reporting (table variante / entonnoir / cohortes
    # / export CSV).
    path('reporting/variantes/', VariantReportView.as_view(),
         name='adsengine-reporting-variantes'),
    path('reporting/entonnoir/', CampaignFunnelView.as_view(),
         name='adsengine-reporting-entonnoir'),
    path('reporting/cohortes/', CohortReportView.as_view(),
         name='adsengine-reporting-cohortes'),
    path('reporting/export/', ReportExportView.as_view(),
         name='adsengine-reporting-export'),
    # ADSDEEP9 — ventilations (audience & diffusion) d'un objet publicitaire.
    path('breakdowns/', BreakdownsView.as_view(), name='adsengine-breakdowns'),
    # ADSDEEP19 — comptes de leads RÉELS par ad / campagne (MetaLeadMirror).
    path('metrics/real-leads/', RealLeadsView.as_view(),
         name='adsengine-real-leads'),
    # ADSDEEP12 — résolveur de médias frais (URL jouable non persistée).
    path('media/<str:ref>/', MediaResolveView.as_view(),
         name='adsengine-media-resolve'),
    # ADSDEEP13 — proxy previews (iframe Meta, jamais persistée).
    path('ads/<str:ad_meta_id>/previews/', AdPreviewsView.as_view(),
         name='adsengine-ad-previews'),
    path('', include(router.urls)),
]
