"""Routes du moteur publicitaire Meta Ads, montées sous
``/api/django/adsengine/`` (voir ``erp_agentique/urls.py``).

ENG1 expose ``status/`` ; ENG2 ajoute le CRUD ``connexions/`` (connexion Meta).
Les routeurs ViewSet suivants (garde-fous, actions) s'ajoutent ici aux tâches
suivantes de la lane.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .incrementality import GeoHoldoutReportView
from .odoo_views import OdooCostPerSignatureView
from .views import (
    AccountAuditView,
    AdCampaignMirrorViewSet, AdPreviewsView, AdsCockpitView, AlertSnoozeView,
    AnnotationViewSet, AnomalyEventViewSet,
    ArmDailyStatViewSet, AssumptionNodeViewSet,
    FactEntryViewSet, FactTableViewSet,
    BacklogDropAssetView, BacklogListView, BacklogLotApproveView,
    BreakdownsView, BriefLatestView, CampaignFunnelView, CohortReportView,
    CommentCountsView, CommentDeleteView, CommentHideView, CommentListView,
    CommentPrivateReplyView, CommentReplyView,
    AudienceDeliveryEstimateView, EngagementAudienceView,
    CostPerSignatureView, CreativeLeaderboardView, CreativeScatterView,
    CreativeAssetViewSet, CreativeBacklogItemViewSet,
    CreativeGenerationBatchViewSet, CreativePolicyViewSet, DecisionLogViewSet,
    EngineActionViewSet, EngineAlertViewSet, ExperimentArmViewSet,
    GroundedGenerationView,
    ExperimentViewSet, FlightPhaseViewSet, FlightPlanViewSet,
    GuardrailConfigViewSet, GuardrailSingletonView,
    InstagramCommentDeleteView, InstagramCommentHideView,
    InstagramCommentListView, InstagramCommentReplyView,
    InstagramMediaListView, InstagramMediaToggleCommentsView,
    InstagramPublishView, InstagramQuotaView, MediaResolveView,
    MetaConnectionHealthView,
    MetaConnectionStatusView, MetaConnectionViewSet, MetricsDashboardV2View,
    MetricsDashboardView,
    MetricsLeadsView, MetricsPacingView, ProposeCuratedActionView, RealLeadsView,
    ReconciliationListView, ReconciliationSnapshotViewSet, ReportExportView,
    RulePolicyViewSet, SignalCohortView, SignalsView, SimulationDetailView,
    SimulationListView, StatusView,
    VariantFunnelView, VariantReportView, WiringHealthView,
)
from .whatsapp_webhook import WhatsAppCloudWebhookView

router = DefaultRouter()
router.register(r'connexions', MetaConnectionViewSet, basename='meta-connexion')
router.register(r'garde-fous', GuardrailConfigViewSet, basename='guardrail')
# ASG1 — Assumption Engine (arbre vivant de croyances testées).
router.register(r'noeuds-hypothese', AssumptionNodeViewSet,
                basename='assumption-node')
# PUB49 — annotations de courbe (notes de décision épinglées à une date).
router.register(r'annotations', AnnotationViewSet, basename='annotation')
# AGEN1 — génération autonome : table de faits versionnée (§10.2 point 1).
router.register(r'table-faits', FactTableViewSet, basename='fact-table')
router.register(r'faits', FactEntryViewSet, basename='fact-entry')
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
    # ADSDEEP61 — Dashboard v2 : conversations réelles + MER mixte (2 devises).
    path('metrics/dashboard-v2/', MetricsDashboardV2View.as_view(),
         name='adsengine-metrics-dashboard-v2'),
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
    # PUB16 — génération IA ancrée (« Générer des variantes ancrées »).
    path('generation/variantes-ancrees/', GroundedGenerationView.as_view(),
         name='adsengine-generation-variantes-ancrees'),
    # ADSENG33 — drill-downs de reporting (table variante / entonnoir / cohortes
    # / export CSV).
    path('reporting/variantes/', VariantReportView.as_view(),
         name='adsengine-reporting-variantes'),
    path('reporting/entonnoir/', CampaignFunnelView.as_view(),
         name='adsengine-reporting-entonnoir'),
    # PUB36 — même entonnoir NEW→SIGNED cumulatif, résolu PAR AD plutôt que
    # par campagne (à quelle étape chaque annonce perd ses leads).
    path('reporting/entonnoir-variantes/', VariantFunnelView.as_view(),
         name='adsengine-reporting-entonnoir-variantes'),
    path('reporting/cohortes/', CohortReportView.as_view(),
         name='adsengine-reporting-cohortes'),
    path('reporting/export/', ReportExportView.as_view(),
         name='adsengine-reporting-export'),
    # ADSDEEP47 — leaderboard créatif (hook/angle/format, spend-weighted) +
    # nuage hook rate × dépense (quadrants FR).
    path('reporting/creatifs/classement/', CreativeLeaderboardView.as_view(),
         name='adsengine-reporting-creatifs-classement'),
    path('reporting/creatifs/nuage/', CreativeScatterView.as_view(),
         name='adsengine-reporting-creatifs-nuage'),
    # ADSDEEP63 — audit de compte à la demande (structure/naming, fragmentation
    # budgétaire, fatigue, tracking, fenêtres de données), 100 % lecture.
    path('reporting/audit/', AccountAuditView.as_view(),
         name='adsengine-reporting-audit'),
    # PUB38 — rapport d'incrémentalité geo-holdout (zone tenue vs zones
    # actives), 100 % lecture, aucune action automatique.
    path('reporting/incrementalite/', GeoHoldoutReportView.as_view(),
         name='adsengine-reporting-incrementalite'),
    # PUB48 — reporte UNE alerte (snooze) jusqu'à une date ; ne masque QUE la
    # liste active (``history()`` reste complet).
    path('alertes/<int:alert_id>/snooze/', AlertSnoozeView.as_view(),
         name='adsengine-alerte-snooze'),
    # ADSDEEP9 — ventilations (audience & diffusion) d'un objet publicitaire.
    path('breakdowns/', BreakdownsView.as_view(), name='adsengine-breakdowns'),
    # ADSDEEP19 — comptes de leads RÉELS par ad / campagne (MetaLeadMirror).
    path('metrics/real-leads/', RealLeadsView.as_view(),
         name='adsengine-real-leads'),
    # ADSDEEP22 — cockpit par ad (écran-console quotidien). Les conversations
    # WhatsApp par ad y sont une COLONNE (PUB12 : l'ancien endpoint dédié
    # metrics/conversations-per-ad/, sans consommateur, était redondant → retiré).
    path('metrics/ads-cockpit/', AdsCockpitView.as_view(),
         name='adsengine-ads-cockpit'),
    # ADSDEEP12 — résolveur de médias frais (URL jouable non persistée).
    path('media/<str:ref>/', MediaResolveView.as_view(),
         name='adsengine-media-resolve'),
    # ADSDEEP13 — proxy previews (iframe Meta, jamais persistée).
    path('ads/<str:ad_meta_id>/previews/', AdPreviewsView.as_view(),
         name='adsengine-ad-previews'),
    # ADSDEEP24 — récepteur webhook WhatsApp Cloud API (CTWA referral). Public,
    # gated WHATSAPP_CLOUD_VERIFY_TOKEN + WHATSAPP_CLOUD_APP_SECRET (404 sinon).
    path('whatsapp/webhook/', WhatsAppCloudWebhookView.as_view(),
         name='adsengine-whatsapp-webhook'),
    # ADSDEEP53/54 — boîte de réception des commentaires (posts + dark posts).
    path('commentaires/', CommentListView.as_view(),
         name='adsengine-comments-list'),
    path('commentaires/compteurs/', CommentCountsView.as_view(),
         name='adsengine-comments-counts'),
    path('commentaires/<int:comment_id>/masquer/', CommentHideView.as_view(),
         name='adsengine-comments-hide'),
    path('commentaires/<int:comment_id>/repondre/', CommentReplyView.as_view(),
         name='adsengine-comments-reply'),
    path('commentaires/<int:comment_id>/supprimer/',
         CommentDeleteView.as_view(), name='adsengine-comments-delete'),
    path('commentaires/<int:comment_id>/reponse-privee/',
         CommentPrivateReplyView.as_view(),
         name='adsengine-comments-private-reply'),
    # ADSDEEP55/56 — Instagram (compte Business relié).
    path('instagram/medias/', InstagramMediaListView.as_view(),
         name='adsengine-ig-media-list'),
    path('instagram/quota/', InstagramQuotaView.as_view(),
         name='adsengine-ig-quota'),
    path('instagram/publier/', InstagramPublishView.as_view(),
         name='adsengine-ig-publish'),
    path('instagram/commentaires/', InstagramCommentListView.as_view(),
         name='adsengine-ig-comments-list'),
    path('instagram/commentaires/<int:comment_id>/masquer/',
         InstagramCommentHideView.as_view(), name='adsengine-ig-comments-hide'),
    path('instagram/commentaires/<int:comment_id>/repondre/',
         InstagramCommentReplyView.as_view(),
         name='adsengine-ig-comments-reply'),
    path('instagram/commentaires/<int:comment_id>/supprimer/',
         InstagramCommentDeleteView.as_view(),
         name='adsengine-ig-comments-delete'),
    path('instagram/medias/<str:media_meta_id>/commentaires-actif/',
         InstagramMediaToggleCommentsView.as_view(),
         name='adsengine-ig-media-toggle-comments'),
    # PUB22 — proposition d'action CURÉE (duplicate/set_schedule/create_ad_study)
    # via son producteur backend (toujours à travers propose_action). Placé AVANT
    # le routeur pour que « actions/proposer/<kind>/ » gagne sur « actions/<pk>/ ».
    path('actions/proposer/<str:kind>/', ProposeCuratedActionView.as_view(),
         name='adsengine-propose-curated'),
    # SIG4 — console de signaux (deux scores de santé + quadrant de garde-fous
    # durs + drill-down par cohorte). Vues minces sur health.py / signal_guards.py
    # / cohorts.py — company-scopées, lecture ``adsengine_view``.
    path('signaux/', SignalsView.as_view(), name='adsengine-signaux'),
    path('signaux/cohorte/', SignalCohortView.as_view(),
         name='adsengine-signaux-cohorte'),
    # ADSDEEP59 — audiences d'engagement (picker composeur d'adset) + estimation
    # d'audience avant usage. NON gated consentement (aucune donnée CRM envoyée).
    path('audiences/engagement/', EngagementAudienceView.as_view(),
         name='adsengine-audiences-engagement'),
    path('audiences/delivery-estimate/',
         AudienceDeliveryEstimateView.as_view(),
         name='adsengine-audiences-delivery-estimate'),
    path('', include(router.urls)),
]
