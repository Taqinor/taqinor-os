"""ENF11 — Applique, après coup, les déclarations OpenAPI des APIView d'adsengine.

Pose ``extend_schema`` sur les méthodes des vues au démarrage (``apps.py``
``ready``) afin que ``views.py`` (fichier-mur) ne grossisse pas. Les formes
déclarées vivent dans ``schema_docs.py``. Aucune donnée renvoyée n'est modifiée."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from . import schema_docs as sd


def appliquer():
    from . import views as v
    from .serializers import InsightBreakdownSerializer

    EngineActionSerializer = v.EngineActionSerializer
    EngineAlertSerializer = v.EngineAlertSerializer
    CreativeGenerationBatchSerializer = v.CreativeGenerationBatchSerializer
    CreativeBacklogItemSerializer = v.CreativeBacklogItemSerializer
    CommentMirrorSerializer = v.CommentMirrorSerializer
    InstagramMediaMirrorSerializer = v.InstagramMediaMirrorSerializer
    InstagramCommentMirrorSerializer = v.InstagramCommentMirrorSerializer
    _qp = v._qp

    def pose(classe, methode, **kw):
        fn = getattr(classe, methode)
        setattr(classe, methode, extend_schema(**kw)(fn))

    pose(v.StatusView, 'get',
         responses=sd.STATUS)
    pose(v.WiringHealthView, 'get',
         responses=sd.WIRING_HEALTH)
    pose(v.CostPerSignatureView, 'get',
         responses=sd.COST_PER_SIGNATURE)
    pose(v.EngagementAudienceView, 'get',
         responses=sd.ENGAGEMENT_CATALOG)
    pose(v.EngagementAudienceView, 'post',
         request=sd.ENGAGEMENT_CREATE_REQUEST, responses=sd.ENGAGEMENT_CREATE)
    pose(v.GroundedGenerationView, 'post',
         request=sd.GROUNDED_REQUEST,
         responses={200: sd.GROUNDED_RESPONSE, 202: sd.GROUNDED_RESPONSE})
    pose(v.AudienceDeliveryEstimateView, 'post',
         request=sd.DELIVERY_ESTIMATE_REQUEST, responses=sd.DELIVERY_ESTIMATE)
    pose(v.AdChatterView, 'get',
         responses=sd.CHATTER_TIMELINE)
    pose(v.AdChatterView, 'post',
         request=sd.CHATTER_REQUEST, responses={201: sd.CHATTER_NOTE})
    pose(v.ImportChantierPhotoView, 'post',
         request=sd.IMPORT_PHOTO_REQUEST, responses={201: sd.IMPORT_PHOTO})
    pose(v.AlertSnoozeView, 'post',
         request=sd.ALERT_SNOOZE_REQUEST, responses=EngineAlertSerializer)
    pose(v.ProposeCuratedActionView, 'post',
         request=sd.PROPOSE_CURATED_REQUEST,
         responses={201: EngineActionSerializer})
    pose(v.VariantReportView, 'get',
         responses=sd.VARIANT_REPORT)
    pose(v.CampaignFunnelView, 'get',
         parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")],
         responses=sd.CAMPAIGN_FUNNEL)
    pose(v.AttributionBilanView, 'get',
         parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ).")],
         responses=sd.ATTRIBUTION_BILAN)
    pose(v.LeadsTimeseriesView, 'get',
         responses=sd.LEADS_TIMESERIES)
    pose(v.AudienceView, 'get',
         parameters=[_qp('ad', str, "Identifiant Meta de l'annonce.")],
         responses=sd.AUDIENCE)
    pose(v.VariantFunnelView, 'get',
         responses=sd.VARIANT_FUNNEL)
    pose(v.CohortReportView, 'get',
         parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")],
         responses=sd.COHORTS)
    pose(v.ReportExportView, 'get',
         responses={(200, 'text/csv'): OpenApiTypes.BINARY})
    pose(v.CreativeLeaderboardView, 'get',
         responses=sd.CREATIVE_LEADERBOARD)
    pose(v.RegretRegistryView, 'get',
         parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")],
         responses=sd.REGRET_REGISTRY)
    pose(v.MdeCalculatorView, 'get',
         responses=sd.MDE_CALCULATOR)
    pose(v.ExplorationLedgerView, 'get',
         parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")],
         responses=sd.EXPLORATION_LEDGER)
    pose(v.CreativeScatterView, 'get',
         responses=sd.CREATIVE_SCATTER)
    pose(v.AccountAuditView, 'get',
         responses=sd.ACCOUNT_AUDIT)
    pose(v.CommentFaqView, 'get',
         responses=sd.COMMENT_FAQ)
    pose(v.AdObjectionsView, 'get',
         responses=sd.AD_OBJECTIONS)
    pose(v.VisualFatigueView, 'get',
         responses=sd.VISUAL_FATIGUE)
    pose(v.WeatherTriggerView, 'get',
         responses=sd.WEATHER_TRIGGER)
    pose(v.CoverageReportView, 'get',
         parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")],
         responses=sd.COVERAGE_REPORT)
    pose(v.FactoryLaneRoiView, 'get',
         parameters=[_qp('debut', OpenApiTypes.DATE, "Début de période (AAAA-MM-JJ)."), _qp('fin', OpenApiTypes.DATE, "Fin de période (AAAA-MM-JJ).")],
         responses=sd.FACTORY_LANE_ROI)
    pose(v.MetaConnectionStatusView, 'get',
         responses=sd.CONNECTION_STATUS)
    pose(v.MetaConnectionStatusView, 'post',
         request=sd.CONNECTION_REGISTER_REQUEST, responses=sd.CONNECTION_REGISTER)
    pose(v.MetaConnectionHealthView, 'get',
         responses=sd.CONNECTION_HEALTH)
    pose(v.SyncStatusView, 'get',
         responses=sd.SYNC_STATUS)
    pose(v.TodayQueueView, 'get',
         responses=sd.TODAY_QUEUE)
    pose(v.GuardrailSingletonView, 'get',
         responses=sd.GUARDRAIL_SINGLETON)
    pose(v.GuardrailSingletonView, 'patch',
         request=sd.GUARDRAIL_SINGLETON_REQUEST, responses=sd.GUARDRAIL_SINGLETON)
    pose(v.MetricsDashboardView, 'get',
         responses=sd.METRICS_DASHBOARD)
    pose(v.MetricsLeadsView, 'get',
         responses=sd.METRICS_LEADS)
    pose(v.MetricsPacingView, 'get',
         responses=sd.METRICS_PACING)
    pose(v.MetricsDashboardV2View, 'get',
         responses=sd.DASHBOARD_V2)
    pose(v.ReconciliationListView, 'get',
         responses=sd.RECONCILIATION_LIST)
    pose(v.ReconciliationBackfillView, 'post',
         request=sd.RECONCILIATION_BACKFILL_REQUEST,
         responses=sd.RECONCILIATION_BACKFILL)
    pose(v.BriefLatestView, 'get',
         responses=sd.BRIEF_LATEST)
    pose(v.SimulationDetailView, 'get',
         responses=sd.SIMULATION_DETAIL)
    pose(v.BacklogListView, 'get',
         responses=sd.BACKLOG_LIST)
    pose(v.BacklogLotApproveView, 'post',
         request=None, responses=CreativeGenerationBatchSerializer)
    pose(v.BacklogDropAssetView, 'post',
         request={'multipart/form-data': sd.BACKLOG_DROP_REQUEST},
         responses={201: CreativeBacklogItemSerializer})
    pose(v.BreakdownsView, 'get',
         responses=InsightBreakdownSerializer(many=True))
    pose(v.MediaResolveView, 'get',
         responses=sd.MEDIA_RESOLVE)
    pose(v.AdPreviewsView, 'get',
         responses=sd.AD_PREVIEWS)
    pose(v.AdFullStoryView, 'get',
         responses=sd.AD_FULL_STORY)
    pose(v.RealLeadsView, 'get',
         responses=sd.REAL_LEADS)
    pose(v.AdsCockpitView, 'get',
         responses=sd.ADS_COCKPIT)
    pose(v.CommentListView, 'get',
         parameters=[
            _qp('ad_id', str, "Identifiant Meta de l'annonce."),
            _qp('post_id', str, 'Identifiant du post.'),
            _qp('hidden', bool, 'Filtre masqués.'),
            _qp('unanswered', bool, 'Seulement les non répondus.'),
         ],
         responses=CommentMirrorSerializer(many=True))
    pose(v.CommentCountsView, 'get',
         responses=sd.COMMENT_COUNTS)
    pose(v.CommentHideView, 'post',
         request=sd.COMMENT_HIDE_REQUEST, responses={201: EngineActionSerializer})
    pose(v.CommentReplyView, 'post',
         request=sd.COMMENT_MESSAGE_REQUEST, responses={201: EngineActionSerializer})
    pose(v.CommentDeleteView, 'post',
         request=None, responses={201: EngineActionSerializer})
    pose(v.CommentPrivateReplyView, 'post',
         request=sd.COMMENT_MESSAGE_REQUEST, responses={201: EngineActionSerializer})
    pose(v.InstagramMediaListView, 'get',
         responses=InstagramMediaMirrorSerializer(many=True))
    pose(v.InstagramQuotaView, 'get',
         responses=sd.IG_QUOTA)
    pose(v.InstagramPublishView, 'post',
         request=sd.IG_PUBLISH_REQUEST, responses={201: EngineActionSerializer})
    pose(v.InstagramCommentListView, 'get',
         parameters=[_qp('media_id', str, 'Identifiant Meta du média.')],
         responses=InstagramCommentMirrorSerializer(many=True))
    pose(v.InstagramCommentHideView, 'post',
         request=sd.COMMENT_HIDE_REQUEST, responses={201: EngineActionSerializer})
    pose(v.InstagramCommentReplyView, 'post',
         request=sd.COMMENT_MESSAGE_REQUEST, responses={201: EngineActionSerializer})
    pose(v.InstagramCommentDeleteView, 'post',
         request=None, responses={201: EngineActionSerializer})
    pose(v.InstagramMediaToggleCommentsView, 'post',
         request=sd.IG_TOGGLE_REQUEST, responses={201: EngineActionSerializer})
    pose(v.SignalsView, 'get',
         responses=sd.SIGNALS)
    pose(v.SignalCohortView, 'get',
         responses=sd.SIGNAL_COHORT)

    pose(v.AssumptionNodeViewSet, 'test_leads',
         parameters=[OpenApiParameter('test_id', int, OpenApiParameter.PATH)],
         responses=sd._rows('AdsTestLead', id=sd._int(), nom=sd._str(allow_blank=True),
                            stage_label=sd._str(allow_blank=True), url=sd._str()))
