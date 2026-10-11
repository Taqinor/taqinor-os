"""ENF11 — Déclarations OpenAPI (drf-spectacular) des ``APIView`` d'adsengine.

Chaque ``inline_serializer`` décrit la forme RÉELLE renvoyée par la vue
correspondante (lue dans ``views.py``/``metrics.py``/``reporting.py``…). Ce
module ne dépend d'aucun autre module de l'app (pas de cycle d'import) : les
vues l'importent, jamais l'inverse. Aucune donnée renvoyée au client n'est
modifiée — ce sont uniquement des déclarations de schéma.

Conventions : montants = chaîne décimale (``CharField``), taux = ``FloatField``
nullable, ``*_at``/dates = chaîne ISO-8601.
"""
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers as s


def _o(_name, /, *, null=False, optional=False, **fields):
    """Objet imbriqué/inline ; ``null``/``optional`` qualifient le champ parent."""
    kw = {}
    if null:
        kw['allow_null'] = True
    if optional:
        kw['required'] = False
    return inline_serializer(name=_name, fields=fields, **kw)


def _str(**kw):
    return s.CharField(**kw)


def _snull(**kw):
    return s.CharField(allow_null=True, **kw)


def _int(**kw):
    return s.IntegerField(**kw)


def _flt(**kw):
    return s.FloatField(**kw)


def _bool(**kw):
    return s.BooleanField(**kw)


def _rows(_name, /, **fields):
    """Liste de lignes typées (champ imbriqué)."""
    return inline_serializer(name=_name, fields=fields, many=True)


def path_int(name):
    return OpenApiParameter(name, int, OpenApiParameter.PATH)


def path_str(name):
    return OpenApiParameter(name, str, OpenApiParameter.PATH)


# ── Générique ─────────────────────────────────────────────────────────────────
DETAIL = _o('AdsDetail', detail=_str())

PERIODE = _o('AdsPeriode', debut=_str(), fin=_str())
_PERIODE_FIELD = dict(debut=_str(), fin=_str())

# ── StatusView ────────────────────────────────────────────────────────────────
STATUS = _o('AdsStatus', ok=_bool())

# ── WiringHealthView ──────────────────────────────────────────────────────────
WIRING_HEALTH = _o(
    'AdsWiringHealth',
    keys=s.DictField(child=_bool()),
    connection=_o('AdsWiringConnection', exists=_bool(), enabled=_bool(),
                  has_token=_bool()),
    last_successful_sync=_snull(),
    last_lead_ads_webhook=_snull(),
    last_capi_event=_snull(),
    guardian=_o('AdsGuardianHealth', evaluator_last_run=_snull(),
                stale=_bool(), healthy=_bool(), max_age_hours=_flt()),
    rate_limit=_o('AdsRateLimit', null=True, usage_pct=_flt(allow_null=True),
                  tier=_str(allow_blank=True), throttled=_bool()),
    page_asset_access=_o('AdsPageAssetAccess', status=_str(), message=_str()),
    boucles_en_attente=_rows(
        'AdsPendingLoop', id=_str(), nom=_str(), actif=_bool(),
        cles_requises=s.ListField(child=_str()), remediation_fr=_str()),
)

# ── CostPerSignatureView ──────────────────────────────────────────────────────
COST_PER_SIGNATURE = _o(
    'AdsCostPerSignature',
    total_spend=_str(), total_signed=_int(), cost_per_signature=_snull(),
    campagnes=_rows(
        'AdsCostPerSignatureCampagne',
        campaign_meta_id=_str(), campaign_name=_str(), attribution_key=_str(),
        spend=_str(), signed_count=_int(), cost_per_signature=_snull(),
        signed_lead_ids=s.ListField(child=_int()), objective=_str(allow_blank=True),
        result_metric=_str(allow_blank=True),
        result_metric_label=_str(allow_blank=True)),
)

# ── Audiences d'engagement / estimation ───────────────────────────────────────
ENGAGEMENT_CATALOG = _o(
    'AdsEngagementCatalog',
    presets=_rows('AdsEngagementPreset', key=_str(), label=_str(),
                  source_type=_str(), event=_str(), retention_days=_int()))
ENGAGEMENT_CREATE_REQUEST = _o(
    'AdsEngagementCreateRequest',
    preset_key=_str(), name=_str(required=False, allow_null=True),
    source_id=_str(required=False, allow_null=True))
ENGAGEMENT_CREATE = _o(
    'AdsEngagementCreate', preset=_str(), audience_id=_str(allow_blank=True),
    retention_days=_int(required=False), error=_str(required=False))
DELIVERY_ESTIMATE_REQUEST = _o(
    'AdsDeliveryEstimateRequest', targeting_spec=s.DictField(),
    optimization_goal=_str(required=False))
DELIVERY_ESTIMATE = _o(
    'AdsDeliveryEstimate', estimate=s.JSONField(required=False),
    error=_str(required=False))

# ── GroundedGenerationView ────────────────────────────────────────────────────
GROUNDED_REQUEST = _o(
    'AdsGroundedGenerationRequest', seed_brief=_str(),
    components=s.ListField(child=_str(), required=False))
GROUNDED_RESPONSE = _o('AdsGroundedGeneration', enabled=_bool(), detail=_str())

# ── AdChatterView ─────────────────────────────────────────────────────────────
CHATTER_ENTITY_TYPES = ['campaign', 'adset', 'ad']
CHATTER_TIMELINE = _rows(
    'AdsChatterItem', kind=_str(), body=_str(), at=_str(),
    author=_snull(required=False), source=_str(),
    auto=_bool(required=False), severity=_str(required=False))
CHATTER_REQUEST = _o(
    'AdsChatterNoteRequest',
    entity_type=s.ChoiceField(choices=CHATTER_ENTITY_TYPES),
    entity_id=_str(), body=_str())
CHATTER_NOTE = _o(
    'AdsChatterNote', id=_int(), kind=_str(), body=_str(), at=_str(),
    author=_str(), source=_str())

# ── ImportChantierPhotoView ───────────────────────────────────────────────────
IMPORT_PHOTO_REQUEST = _o(
    'AdsImportChantierPhotoRequest', chantier_id=_int(), attachment_id=_int(),
    client_id=_int(required=False, allow_null=True),
    puissance_kwc=_str(required=False, allow_null=True),
    ville=_str(required=False, allow_null=True),
    note=_str(required=False, allow_blank=True),
    auto_flagged=_bool(required=False))
IMPORT_PHOTO = _o('AdsImportChantierPhoto', imported=_bool(), asset_id=_int(),
                  message=_str())

# ── AlertSnoozeView / ProposeCuratedActionView ────────────────────────────────
ALERT_SNOOZE_REQUEST = _o('AdsAlertSnoozeRequest', until=s.DateField())
PROPOSE_CURATED_REQUEST = _o(
    'AdsProposeCuratedRequest', reason_fr=_str(required=False, allow_null=True))

# ── Reporting (drill-downs ADSENG33 & co) ─────────────────────────────────────
_VARIANT_ROW = dict(
    meta_id=_str(), name=_str(), spend=_str(), leads=_int(), qualified=_int(),
    signed=_int(), cost_per_lead=_snull(), cost_per_lead_source=_str(),
    cost_per_qualified_lead=_snull(), cost_per_signature=_snull(),
    lead_ids=s.ListField(child=_int()),
    signed_lead_ids=s.ListField(child=_int()), junk=_int(),
    junk_rate=_flt(allow_null=True), appointments=_int(), no_show=_int(),
    no_show_rate=_flt(allow_null=True))
VARIANT_REPORT = _o(
    'AdsVariantReport',
    variants=_rows('AdsVariantRow', **_VARIANT_ROW),
    unresolved=s.DictField(),
    organic_excluded_count=_int(),
    variantes=_rows(
        'AdsVariantFront', id=_str(), nom=_str(),
        impressions=s.IntegerField(allow_null=True),
        reponses_whatsapp=_int(), cout_mad=_str(),
        cout_par_reponse=_snull()))

_FUNNEL_STEP = _rows('AdsFunnelStep', stage=_str(), reached=_int())
CAMPAIGN_FUNNEL = _o(
    'AdsCampaignFunnel',
    etapes=_rows('AdsFunnelAggStep', key=_str(), label=_str(), valeur=_int()),
    campaigns=_rows(
        'AdsCampaignFunnelRow', campaign_key=_str(), total=_int(), cold=_int(),
        perdu=_int(), funnel=_FUNNEL_STEP))

ATTRIBUTION_BILAN = _o(
    'AdsAttributionBilan', configured=_bool(), total=_int(), attributed=_int(),
    unattributed=_int(),
    tiers=_rows('AdsAttributionTier', key=_str(), label=_str(), count=_int()),
    unattributed_by_source=_rows(
        'AdsUnattributedSource', source_name=_str(), count=_int()),
    note=_str(allow_blank=True), odoo_error=_str(required=False))

LEADS_TIMESERIES = _o(
    'AdsLeadsTimeseries', configured=_bool(), granularity=_str(),
    points=_rows('AdsLeadsPoint', period=_str(), leads_total=_int(),
                 leads_attributed=_int(), spend=_snull()),
    odoo_error=_str(required=False))

_AUDIENCE_SEG = dict(
    spend=_snull(), impressions=s.IntegerField(allow_null=True),
    clicks=s.IntegerField(allow_null=True),
    results=s.IntegerField(allow_null=True),
    conversations=s.IntegerField(allow_null=True),
    reach=s.IntegerField(allow_null=True))
AUDIENCE = _o(
    'AdsAudience', configured=_bool(),
    by_gender=_rows('AdsAudienceGender', key=_str(allow_blank=True),
                    label=_str(), **_AUDIENCE_SEG),
    by_age=_rows('AdsAudienceAge', age=_str(), **_AUDIENCE_SEG),
    coverage=_rows('AdsBreakdownCoverage', dimension=_str(), label=_str(),
                   rows=_int(), last_date=_snull()))

VARIANT_FUNNEL = _o(
    'AdsVariantFunnel',
    variants=_rows(
        'AdsVariantFunnelRow', meta_id=_str(), name=_str(), total=_int(),
        cold=_int(), perdu=_int(), funnel=_FUNNEL_STEP),
    unresolved=_o(
        'AdsVariantFunnelUnresolved', meta_id=_str(allow_blank=True),
        name=_str(allow_blank=True), total=_int(), cold=_int(), perdu=_int(),
        funnel=_FUNNEL_STEP),
    organic_excluded_count=_int())

COHORTS = _rows(
    'AdsCohort', cohort_week=_str(), total_leads=_int(), signed_total=_int(),
    lag_buckets=_rows('AdsCohortLag', lag_weeks=_int(), signed=_int(),
                      complete=_bool()),
    cohorte=_str(), taille=_int(), signatures=_int(),
    lag_jours_median=s.IntegerField(allow_null=True))

CREATIVE_LEADERBOARD = _o(
    'AdsCreativeLeaderboard', dimension=_str(), periode=PERIODE,
    classement=_rows(
        'AdsLeaderboardRow', tag=_str(), spend=_str(), results=_int(),
        cost_per_result=_snull(), ad_count=_int(),
        hook_rate_weighted=_flt(allow_null=True)),
    untagged_count=_int())

CREATIVE_SCATTER = _o(
    'AdsCreativeScatter', periode=PERIODE,
    points=_rows(
        'AdsScatterPoint', ad_meta_id=_str(), name=_str(),
        hook_tag=_str(allow_blank=True), angle_tag=_str(allow_blank=True),
        format_tag=_str(allow_blank=True), spend=_str(), hook_rate=_flt(),
        quadrant=_str(), quadrant_label_fr=_str(),
        hold_rate=_flt(allow_null=True),
        ratio_15s_to_6s=_flt(allow_null=True),
        retention=s.DictField(child=_flt(allow_null=True)),
        watch_time_avg_s=_flt(allow_null=True)),
    median_hook_rate=_flt(allow_null=True),
    median_spend=_flt(allow_null=True))

_INTERVAL = _o('AdsRegretInterval', low=_flt(), high=_flt())
REGRET_REGISTRY = _o(
    'AdsRegretRegistry', total_regret_mad=_flt(), interval=_INTERVAL,
    insufficient_data=_bool(),
    par_type=_rows(
        'AdsRegretParType', tested_variable=_str(),
        tested_variable_label=_str(), regret_mad=_flt(), experiments=_int(),
        insufficient_data=_bool(), interval=_INTERVAL),
    experiences=s.ListField(child=s.DictField()))

MDE_CALCULATOR = _o(
    'AdsMdeCalculator', p=_flt(), volume=_flt(), cible_relative=_flt(),
    jours_pour_cible=s.JSONField(), phrase_fr=_str(),
    mde_par_horizon=_rows('AdsMdeHorizon', jours=_int(),
                          mde_relatif_pct=_flt(allow_null=True)))

EXPLORATION_LEDGER = _o(
    'AdsExplorationLedger',
    mois=_rows(
        'AdsExplorationMonth', mois=_str(), exploration_mad=_flt(),
        exploitation_mad=_flt(), total_mad=_flt(),
        exploration_pct=_flt(allow_null=True), decisions=_int()))

ACCOUNT_AUDIT = _o(
    'AdsAccountAudit', genere_le=_str(),
    sections=s.DictField(child=s.DictField()),
    score_tile=_o('AdsAuditScoreTile', score=s.JSONField(),
                  ok_count=_int(), attention_count=_int(),
                  total_sections=_int(), delta_hebdo=s.JSONField(allow_null=True),
                  genere_le=_snull()))

_THEME_ROW = dict(theme=_str(), label_fr=_str(), count=_int(),
                  echantillons=s.ListField(child=_str()))
COMMENT_FAQ = _o(
    'AdsCommentFaq', themes=_rows('AdsCommentTheme', **_THEME_ROW),
    seed_brief_candidates=s.ListField(child=_str()), total_comments=_int(),
    total_questions=_int())
AD_OBJECTIONS = _o(
    'AdsAdObjections',
    par_ad=_rows('AdsAdObjectionRow', meta_id=_str(), name=_str(allow_blank=True),
                 objections=_rows('AdsObjectionTheme', **_THEME_ROW),
                 angles_suggeres=s.ListField(child=_str())),
    non_resolues=_o('AdsObjectionsUnresolved',
                    objections=_rows('AdsObjectionThemeUnres', **_THEME_ROW)))

VISUAL_FATIGUE = _o(
    'AdsVisualFatigue',
    signals=_rows(
        'AdsVisualFatigueSignal', visual_asset_key=_str(), creas_count=_int(),
        distinct_hooks=_int(), ad_meta_ids=s.ListField(child=_str()),
        severity=_str(), message_fr=_str(),
        ctr_decline_pct=_flt(allow_null=True)))

WEATHER_TRIGGER = _o(
    'AdsWeatherTrigger',
    suggestions=s.ListField(child=s.DictField()))

COVERAGE_REPORT = _o(
    'AdsCoverageReport',
    formats=_o(
        'AdsCoverageFormats',
        jamais_modelises=_rows('AdsFormatNever', format=_str(), label_fr=_str()),
        modelises_jamais_utilises=_rows('AdsFormatUnused', format=_str(),
                                        label_fr=_str()),
        formats_utilises=_rows('AdsFormatUsed', format=_str(), label_fr=_str(),
                               count=_int())),
    segments=_o(
        'AdsCoverageSegments',
        segments_non_couverts=s.ListField(child=s.DictField()),
        periode=PERIODE, median_spend=_flt(allow_null=True)))

FACTORY_LANE_ROI = _o(
    'AdsFactoryLaneRoi',
    lanes=_rows(
        'AdsFactoryLane', lane=_str(), assets_count=_int(),
        cost_cents_total=_int(), results=_int(), spend_mad=_str(),
        cost_per_result_centimes=_flt(allow_null=True)),
    periode=PERIODE)

REPORT_EXPORT_CSV = 'text/csv'

# ── Connexion Meta ────────────────────────────────────────────────────────────
CONNECTION_STATUS = _o(
    'AdsConnectionStatus', connected=_bool(),
    ad_account_id_masque=_str(allow_blank=True), currency=_str())
CONNECTION_REGISTER_REQUEST = _o(
    'AdsConnectionRegisterRequest',
    app_id=_str(required=False), app_secret=_str(required=False),
    access_token=_str(required=False), ad_account_id=_str(required=False),
    page_id=_str(required=False), pixel_id=_str(required=False))
CONNECTION_REGISTER = _o(
    'AdsConnectionRegister', connected=_bool(),
    ad_account_id_masque=_str(allow_blank=True))
CONNECTION_HEALTH = _o(
    'AdsConnectionHealth',
    statuses=_rows(
        'AdsConnectionHealthRow', key=_str(), ok=_bool(), detail=_str(allow_blank=True),
        days_runway=s.JSONField(required=False, allow_null=True),
        balance=s.JSONField(required=False, allow_null=True),
        currency=_str(required=False, allow_blank=True),
        page_subscribed=s.BooleanField(required=False, allow_null=True),
        has_pages_manage_metadata=_bool(required=False)))

SYNC_STATUS = _o(
    'AdsSyncStatus',
    types=_rows('AdsSyncType', type=_str(), label=_str(),
                last_ok_at=_snull(), age_minutes=s.IntegerField(allow_null=True),
                stale=_bool()),
    stale=_bool(),
    worst=_o('AdsSyncWorst', null=True, type=_str(), label=_str(),
             last_ok_at=_snull(), age_minutes=s.IntegerField(allow_null=True),
             stale=_bool()))

TODAY_QUEUE = _o(
    'AdsTodayQueue',
    items=_rows('AdsTodayItem', id=_str(), categorie=_str(),
                categorie_label=_str(), titre=_str(), detail=_str(allow_blank=True),
                lien=_str(), quand=_snull()),
    total=_int())

_GUARDRAIL_COMMON = dict(
    weekly_change_pct_max=_int(), anomaly_window_hours=_int(),
    auto_rotate_creative=_bool(), auto_rebalance_within_band=_bool(),
    pacing_band_pct=_int(), exploration_floor_mad=_int(),
    exploration_floor_pct=_int(), health_creative_weight_ctr=_int(),
    health_creative_weight_freshness=_int(), health_ops_weight_cpl=_int(),
    health_ops_weight_delivery=_int())
GUARDRAIL_SINGLETON = _o(
    'AdsGuardrailSingleton', max_daily_budget_mad=_int(),
    max_monthly_budget_mad=s.IntegerField(allow_null=True),
    require_approval_above_mad=s.IntegerField(allow_null=True),
    ceiling_currency=_str(allow_blank=True), **_GUARDRAIL_COMMON)
GUARDRAIL_SINGLETON_REQUEST = _o(
    'AdsGuardrailSingletonRequest',
    max_daily_budget_mad=_int(required=False),
    max_monthly_budget_mad=s.IntegerField(required=False, allow_null=True),
    **{k: type(v)(required=False) for k, v in _GUARDRAIL_COMMON.items()})

# ── Dashboard / métriques ─────────────────────────────────────────────────────
_DASH_WINDOW = dict(spend=_str(), cpl=_snull(), frequency=_snull())
METRICS_DASHBOARD = _o(
    'AdsMetricsDashboard', cost_per_signature=_snull(), signatures=_int(),
    signatures_source=_str(), currency=_str(), **_DASH_WINDOW,
    previous=_o('AdsMetricsPrevious', optional=True, debut=_str(), fin=_str(),
                **_DASH_WINDOW))
METRICS_LEADS = _rows(
    'AdsMetricsLead', id=s.IntegerField(allow_null=True), nom=_str(allow_blank=True),
    etape=_str(allow_blank=True), url=_str(required=False),
    montant=_flt(required=False), source=_str(required=False))
METRICS_PACING = _o(
    'AdsMetricsPacing', enveloppe_mad=_flt(allow_null=True), depense_mad=_flt(),
    projection_mad=_flt(), jours_restants=_int(), etat=_str(),
    etat_display=_str(),
    lignes=_rows('AdsPacingLine', id=_str(), label=_str(), montant_mad=_flt()))
_SPARK = _rows('AdsSparkPoint', date=_str(), value=_flt())
DASHBOARD_V2 = _o(
    'AdsDashboardV2', window_days=_int(), since=_str(), until=_str(),
    conversations=_o('AdsDashboardV2Conv', total=_int(), sparkline=_SPARK),
    mer=_o('AdsDashboardV2Mer', spend=_str(), spend_currency=_str(),
           signed_ca_mad=_str(), signed_ca_currency=_str(),
           mer_ratio=s.JSONField(allow_null=True), odoo_configured=_bool(),
           spend_sparkline=_SPARK, signed_ca_sparkline=_SPARK, note=_str()))
REAL_LEADS = _o(
    'AdsRealLeads', by_ad=s.DictField(child=_int()),
    by_campaign=s.DictField(child=_int()), total=_int())

COST_PER_SIGNATURE_ODOO = _o(
    'AdsCostPerSignatureOdoo', configured=_bool(), total_spend=_str(),
    signatures=_int(), cost_per_signature=_snull(),
    signed_deals=s.ListField(child=s.DictField()),
    per_campaign=s.ListField(child=s.DictField()),
    attribution=_o('AdsOdooAttribution', attributed=_int(), unattributed=_int(),
                   note=_str(allow_blank=True)),
    odoo_error=_str(required=False))

ADS_COCKPIT = _rows(
    'AdsCockpitRow', id=_int(), meta_id=_str(), nom=_str(allow_blank=True),
    statut=_str(allow_blank=True), statut_display=_str(),
    adset_meta_id=_str(allow_blank=True), adset_nom=_str(allow_blank=True),
    learning_badge=_o('AdsCockpitLearning', status=_str(allow_blank=True),
                      label=_str(), tone=_str()),
    thumbnail_ref=_snull(), thumbnail_kind=_str(), depense_mad=_str(),
    conversations=_int(), nb_leads=_int(), cpl_mad=_snull(), cpl_source=_str(),
    impressions=s.IntegerField(allow_null=True),
    reach=s.IntegerField(allow_null=True), clics=s.IntegerField(allow_null=True),
    clics_lien=s.IntegerField(allow_null=True),
    resultats=s.IntegerField(allow_null=True), ctr=_flt(allow_null=True),
    cpc_mad=_snull(), cpm_mad=_snull(), hook_rate=_flt(allow_null=True),
    hold_rate=_flt(allow_null=True), signatures=_int(),
    cost_per_signature_mad=_snull(), leads_odoo=_int(),
    cpl_odoo=s.JSONField(allow_null=True), cpl_odoo_source=_str(),
    odoo_configured=_bool(), frequency=_snull(), fatigue=s.JSONField(),
    classement_qualite=_str(allow_blank=True),
    classement_engagement=_str(allow_blank=True),
    classement_conversion=_str(allow_blank=True),
    attribution_incrementale=s.DictField())

AD_FULL_STORY = _o(
    'AdsAdFullStory',
    ad=_o('AdsFullStoryAd', id=_int(), meta_id=_str(), nom=_str(allow_blank=True),
          statut=_str(allow_blank=True), statut_display=_str()),
    creatif=_o('AdsFullStoryCreative', null=True, video_id=_str(allow_blank=True),
               image_hash=_str(allow_blank=True), title=_str(allow_blank=True),
               body=_str(allow_blank=True), description=_str(allow_blank=True),
               cta_type=_str(allow_blank=True),
               instagram_permalink_url=_str(allow_blank=True),
               effective_object_story_id=_str(allow_blank=True)),
    metriques=s.DictField(allow_null=True),
    actions=_rows('AdsFullStoryAction', id=_int(), kind=_str(),
                  kind_display=_str(), reason_fr=_str(allow_blank=True),
                  status=_str(), status_display=_str(), auto=_bool(),
                  created_at=_str()),
    commentaires=_rows('AdsFullStoryComment', id=_int(),
                       from_name=_str(allow_blank=True),
                       message=_str(allow_blank=True), created_time=_snull(),
                       is_hidden=_bool(), hidden_verified=_bool(),
                       answered=_bool()),
    regles=_rows('AdsFullStoryRule', id=_int(), kind=_str(),
                 kind_display=_str(), severity=_str(),
                 message_fr=_str(allow_blank=True), resolved=_bool(),
                 rule_template_key=_snull(), rule_label=_snull(),
                 created_at=_str()),
    experiences=_rows('AdsFullStoryExperiment', id=_int(), label=_str(),
                      is_active=_bool(), experiment_id=s.IntegerField(allow_null=True),
                      experiment_nom=_str(allow_blank=True),
                      experiment_statut=_str(allow_blank=True)),
    breakdowns=s.ListField(child=s.DictField()))

AD_PREVIEWS = _o('AdsAdPreview', format=_str(), body=_str(allow_blank=True))
MEDIA_RESOLVE = _o('AdsMediaResolve', url=_str(allow_blank=True),
                   picture=_str(allow_blank=True), cached=_bool())

# ── Réconciliation / brief / simulation / backlog ─────────────────────────────
RECONCILIATION_LIST = _rows(
    'AdsReconciliationRow', id=_int(), campagne=_str(allow_blank=True),
    meta_mad=_int(), erp_mad=_int(), ecart_mad=_int(),
    ecart_pct=_flt(allow_null=True), statut=_str(), statut_display=_str(),
    lignes=s.ListField(child=s.DictField()))
RECONCILIATION_BACKFILL_REQUEST = _o(
    'AdsReconciliationBackfillRequest',
    alert_id=s.IntegerField(required=False, allow_null=True),
    campaign_meta_id=_str(required=False, allow_blank=True),
    date=s.DateField(required=False, allow_null=True))
RECONCILIATION_BACKFILL = _o(
    'AdsReconciliationBackfill', status=_str(), leads_processed=_int(),
    insights_refreshed=_int())
BRIEF_LATEST = _o(
    'AdsBriefLatest', periode=_str(allow_blank=True), resume=_str(allow_blank=True),
    items=_rows('AdsBriefItem', id=_str(), quoi=_str(allow_blank=True),
                pourquoi=_str(allow_blank=True), suggestion=_str(allow_blank=True),
                action_id=s.IntegerField(allow_null=True)))
SIMULATION_DETAIL = _o(
    'AdsSimulationDetail', id=_str(), nom=_str(), cree_le=_str(allow_blank=True),
    scenarios=_rows('AdsSimulationScenarioDetail', key=_str(), nom=_str(),
                    verdict=_str(), verdict_display=_str(), resume_fr=_str()),
    allocations=s.ListField(child=s.DictField()),
    decisions=s.ListField(child=s.DictField()))
BACKLOG_LIST = _rows(
    'AdsBacklogCampaign', id=_int(), campagne=_str(), runway_jours=_flt(),
    runway_cible=_flt(), diversite_hooks=s.JSONField(),
    lots=_rows(
        'AdsBacklogLot', id=_int(), nom=_str(), statut=_str(),
        statut_display=_str(), nb_hooks=_int(),
        assets=_rows('AdsBacklogLotAsset', id=_int(), designation=_str())))
BACKLOG_DROP_REQUEST = _o(
    'AdsBacklogDropRequest', file=s.FileField(),
    asset_type=_str(required=False))

# ── Signaux ───────────────────────────────────────────────────────────────────
_SIGNAL_SCORE = dict(score=_flt(), bande=_str(), bande_display=_str())
SIGNALS = _o(
    'AdsSignals', creatif=_o('AdsSignalCreatif', **_SIGNAL_SCORE),
    operations=_o('AdsSignalOperations', **_SIGNAL_SCORE),
    guardrails=_rows(
        'AdsSignalGuardrail', key=_str(), label=_str(),
        valeur=s.JSONField(allow_null=True), seuil=s.JSONField(allow_null=True),
        freine=_bool(), statut_display=_str(), raison=_str(allow_blank=True)),
    fenetre_jours=_int())
SIGNAL_COHORT = _rows(
    'AdsSignalCohortRow', id=_int(), fenetre=_str(),
    valeur=_flt(allow_null=True), maturite_display=_str(), mure=_bool(),
    maturation_jours=s.IntegerField(allow_null=True))

# ── Commentaires ──────────────────────────────────────────────────────────────
COMMENT_COUNTS = _o(
    'AdsCommentCounts', total=_int(), hidden=_int(), unanswered=_int(),
    par_objet=_rows('AdsCommentCountObject', object_meta_id=_str(allow_blank=True),
                    source=_str(), total=_int(), hidden=_int(), unanswered=_int()))
COMMENT_HIDE_REQUEST = _o('AdsCommentHideRequest', hidden=_bool(required=False))
COMMENT_MESSAGE_REQUEST = _o('AdsCommentMessageRequest', message=_str(allow_blank=True))
DCO_RECOMBINE = _o(
    'AdsDcoRecombinaison', action=s.DictField(), detail=_str(required=False))

# ── Instagram ─────────────────────────────────────────────────────────────────
IG_QUOTA = _o(
    'AdsInstagramQuota', used=s.IntegerField(allow_null=True),
    total=s.IntegerField(allow_null=True),
    remaining=s.IntegerField(allow_null=True))
IG_PUBLISH_REQUEST = _o(
    'AdsInstagramPublishRequest', media_type=_str(),
    image_url=_str(required=False, allow_blank=True, allow_null=True),
    video_url=_str(required=False, allow_blank=True, allow_null=True),
    caption=_str(required=False, allow_blank=True, allow_null=True),
    alt_text=_str(required=False, allow_blank=True, allow_null=True),
    scheduled_at=s.DateTimeField(required=False, allow_null=True))
IG_TOGGLE_REQUEST = _o('AdsInstagramToggleCommentsRequest',
                       enabled=_bool(required=False))

GEO_HOLDOUT = _o(
    'AdsGeoHoldoutReport', valide=_bool(), erreur_fr=_str(required=False),
    zone_tenue=s.ListField(child=_str(), required=False),
    periode_baseline=_o('AdsGeoPeriodeBaseline', optional=True, **_PERIODE_FIELD),
    periode_test=_o('AdsGeoPeriodeTest', optional=True, **_PERIODE_FIELD),
    zone_tenue_baseline=s.DictField(required=False),
    zone_tenue_test=s.DictField(required=False),
    zone_active_baseline=s.DictField(required=False),
    zone_active_test=s.DictField(required=False),
    delta_signatures_zone_tenue_pct=_flt(required=False, allow_null=True),
    delta_signatures_zone_active_pct=_flt(required=False, allow_null=True),
    fourchette_signatures_zone_tenue_test=s.ListField(
        child=_flt(), required=False),
    fourchette_signatures_zone_active_test=s.ListField(
        child=_flt(), required=False),
    confiance=_str(required=False), message_fr=_str(required=False))
