"""ENF11 — Applique, après coup, les déclarations OpenAPI des APIView d'adsengine.

Pose ``extend_schema`` sur les méthodes des vues au démarrage (``apps.py``
``ready``) afin que ``views.py`` (fichier-mur) ne grossisse pas. Les formes
déclarées vivent dans ``schema_docs.py``. Aucune donnée renvoyée n'est modifiée."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from . import schema_docs as sd


def _declarations(v, InsightBreakdownSerializer):
    """(vue, méthode, arguments d'``extend_schema``) — une entrée par méthode HTTP."""
    EngineActionSerializer = v.EngineActionSerializer
    EngineAlertSerializer = v.EngineAlertSerializer
    CreativeGenerationBatchSerializer = v.CreativeGenerationBatchSerializer
    CreativeBacklogItemSerializer = v.CreativeBacklogItemSerializer
    CommentMirrorSerializer = v.CommentMirrorSerializer
    InstagramMediaMirrorSerializer = v.InstagramMediaMirrorSerializer
    InstagramCommentMirrorSerializer = v.InstagramCommentMirrorSerializer
    _qp = v._qp
    return [
        (v.StatusView, 'get', dict(responses=sd.STATUS)),
        (v.WiringHealthView, 'get', dict(responses=sd.WIRING_HEALTH)),
        (v.CostPerSignatureView, 'get', dict(responses=sd.COST_PER_SIGNATURE)),
        (v.EngagementAudienceView, 'get', dict(responses=sd.ENGAGEMENT_CATALOG)),
        (v.EngagementAudienceView, 'post', dict(request=sd.ENGAGEMENT_CREATE_REQUEST, responses=sd.ENGAGEMENT_CREATE)),
        (v.GroundedGenerationView, 'post', dict(request=sd.GROUNDED_REQUEST, responses={200: sd.GROUNDED_RESPONSE, 202: sd.GROUNDED_RESPONSE})),
        (v.AudienceDeliveryEstimateView, 'post', dict(request=sd.DELIVERY_ESTIMATE_REQUEST, responses=sd.DELIVERY_ESTIMATE)),
        (v.AdChatterView, 'get', dict(responses=sd.CHATTER_TIMELINE)),
        (v.AdChatterView, 'post', dict(request=sd.CHATTER_REQUEST, responses={201: sd.CHATTER_NOTE})),
        (v.ImportChantierPhotoView, 'post', dict(request=sd.IMPORT_PHOTO_REQUEST, responses={201: sd.IMPORT_PHOTO})),
        (v.AlertSnoozeView, 'post', dict(request=sd.ALERT_SNOOZE_REQUEST, responses=EngineAlertSerializer)),
        (v.ProposeCuratedActionView, 'post', dict(request=sd.PROPOSE_CURATED_REQUEST, responses={201: EngineActionSerializer})),
        (v.VariantReportView, 'get', dict(responses=sd.VARIANT_REPORT)),
        (v.CampaignFunnelView, 'get', dict(parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")], responses=sd.CAMPAIGN_FUNNEL)),
        (v.AttributionBilanView, 'get', dict(parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ).")], responses=sd.ATTRIBUTION_BILAN)),
        (v.LeadsTimeseriesView, 'get', dict(responses=sd.LEADS_TIMESERIES)),
        (v.AudienceView, 'get', dict(parameters=[_qp('ad', str, "Identifiant Meta de l'annonce.")], responses=sd.AUDIENCE)),
        (v.VariantFunnelView, 'get', dict(responses=sd.VARIANT_FUNNEL)),
        (v.CohortReportView, 'get', dict(parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")], responses=sd.COHORTS)),
        (v.ReportExportView, 'get', dict(responses={(200, 'text/csv'): OpenApiTypes.BINARY})),
        (v.CreativeLeaderboardView, 'get', dict(responses=sd.CREATIVE_LEADERBOARD)),
        (v.RegretRegistryView, 'get', dict(parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")], responses=sd.REGRET_REGISTRY)),
        (v.MdeCalculatorView, 'get', dict(responses=sd.MDE_CALCULATOR)),
        (v.ExplorationLedgerView, 'get', dict(parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")], responses=sd.EXPLORATION_LEDGER)),
        (v.CreativeScatterView, 'get', dict(responses=sd.CREATIVE_SCATTER)),
        (v.AccountAuditView, 'get', dict(responses=sd.ACCOUNT_AUDIT)),
        (v.CommentFaqView, 'get', dict(responses=sd.COMMENT_FAQ)),
        (v.AdObjectionsView, 'get', dict(responses=sd.AD_OBJECTIONS)),
        (v.VisualFatigueView, 'get', dict(responses=sd.VISUAL_FATIGUE)),
        (v.WeatherTriggerView, 'get', dict(responses=sd.WEATHER_TRIGGER)),
        (v.CoverageReportView, 'get', dict(parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")], responses=sd.COVERAGE_REPORT)),
        (v.FactoryLaneRoiView, 'get', dict(parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")], responses=sd.FACTORY_LANE_ROI)),
        (v.MetaConnectionStatusView, 'get', dict(responses=sd.CONNECTION_STATUS)),
        (v.MetaConnectionStatusView, 'post', dict(request=sd.CONNECTION_REGISTER_REQUEST, responses=sd.CONNECTION_REGISTER)),
        (v.MetaConnectionHealthView, 'get', dict(responses=sd.CONNECTION_HEALTH)),
        (v.SyncStatusView, 'get', dict(responses=sd.SYNC_STATUS)),
        (v.TodayQueueView, 'get', dict(responses=sd.TODAY_QUEUE)),
        (v.GuardrailSingletonView, 'get', dict(responses=sd.GUARDRAIL_SINGLETON)),
        (v.GuardrailSingletonView, 'patch', dict(request=sd.GUARDRAIL_SINGLETON_REQUEST, responses=sd.GUARDRAIL_SINGLETON)),
        (v.MetricsDashboardView, 'get', dict(responses=sd.METRICS_DASHBOARD)),
        (v.MetricsLeadsView, 'get', dict(responses=sd.METRICS_LEADS)),
        (v.MetricsPacingView, 'get', dict(responses=sd.METRICS_PACING)),
        (v.MetricsDashboardV2View, 'get', dict(responses=sd.DASHBOARD_V2)),
        (v.ReconciliationListView, 'get', dict(responses=sd.RECONCILIATION_LIST)),
        (v.ReconciliationBackfillView, 'post', dict(request=sd.RECONCILIATION_BACKFILL_REQUEST, responses=sd.RECONCILIATION_BACKFILL)),
        (v.BriefLatestView, 'get', dict(responses=sd.BRIEF_LATEST)),
        (v.SimulationDetailView, 'get', dict(responses=sd.SIMULATION_DETAIL)),
        (v.BacklogListView, 'get', dict(responses=sd.BACKLOG_LIST)),
        (v.BacklogLotApproveView, 'post', dict(request=None, responses=CreativeGenerationBatchSerializer)),
        (v.BacklogDropAssetView, 'post', dict(request={'multipart/form-data': sd.BACKLOG_DROP_REQUEST}, responses={201: CreativeBacklogItemSerializer})),
        (v.BreakdownsView, 'get', dict(responses=InsightBreakdownSerializer(many=True))),
        (v.MediaResolveView, 'get', dict(responses=sd.MEDIA_RESOLVE)),
        (v.AdPreviewsView, 'get', dict(responses=sd.AD_PREVIEWS)),
        (v.AdFullStoryView, 'get', dict(responses=sd.AD_FULL_STORY)),
        (v.RealLeadsView, 'get', dict(responses=sd.REAL_LEADS)),
        (v.AdsCockpitView, 'get', dict(responses=sd.ADS_COCKPIT)),
        (v.CommentListView, 'get', dict(parameters=[
            _qp('ad_id', str, "Identifiant Meta de l'annonce."),
            _qp('post_id', str, 'Identifiant du post.'),
            _qp('hidden', bool, 'Filtre masqués.'),
            _qp('unanswered', bool, 'Seulement les non répondus.'),
         ], responses=CommentMirrorSerializer(many=True))),
        (v.CommentCountsView, 'get', dict(responses=sd.COMMENT_COUNTS)),
        (v.CommentHideView, 'post', dict(request=sd.COMMENT_HIDE_REQUEST, responses={201: EngineActionSerializer})),
        (v.CommentReplyView, 'post', dict(request=sd.COMMENT_MESSAGE_REQUEST, responses={201: EngineActionSerializer})),
        (v.CommentDeleteView, 'post', dict(request=None, responses={201: EngineActionSerializer})),
        (v.CommentPrivateReplyView, 'post', dict(request=sd.COMMENT_MESSAGE_REQUEST, responses={201: EngineActionSerializer})),
        (v.InstagramMediaListView, 'get', dict(responses=InstagramMediaMirrorSerializer(many=True))),
        (v.InstagramQuotaView, 'get', dict(responses=sd.IG_QUOTA)),
        (v.InstagramPublishView, 'post', dict(request=sd.IG_PUBLISH_REQUEST, responses={201: EngineActionSerializer})),
        (v.InstagramCommentListView, 'get', dict(parameters=[_qp('media_id', str, 'Identifiant Meta du média.')], responses=InstagramCommentMirrorSerializer(many=True))),
        (v.InstagramCommentHideView, 'post', dict(request=sd.COMMENT_HIDE_REQUEST, responses={201: EngineActionSerializer})),
        (v.InstagramCommentReplyView, 'post', dict(request=sd.COMMENT_MESSAGE_REQUEST, responses={201: EngineActionSerializer})),
        (v.InstagramCommentDeleteView, 'post', dict(request=None, responses={201: EngineActionSerializer})),
        (v.InstagramMediaToggleCommentsView, 'post', dict(request=sd.IG_TOGGLE_REQUEST, responses={201: EngineActionSerializer})),
        (v.SignalsView, 'get', dict(responses=sd.SIGNALS)),
        (v.SignalCohortView, 'get', dict(responses=sd.SIGNAL_COHORT)),
        (v.AssumptionNodeViewSet, 'test_leads', dict(parameters=[OpenApiParameter('test_id', int, OpenApiParameter.PATH)], responses=sd._rows(
            'AdsTestLead', id=sd._int(), nom=sd._str(allow_blank=True),
            stage_label=sd._str(allow_blank=True), url=sd._str()))),
    ]


def appliquer():
    """Pose les déclarations sur les méthodes des vues (appelé par ``ready()``)."""
    from . import views as v
    from .serializers import InsightBreakdownSerializer

    for classe, methode, kw in _declarations(v, InsightBreakdownSerializer):
        setattr(classe, methode, extend_schema(**kw)(getattr(classe, methode)))
