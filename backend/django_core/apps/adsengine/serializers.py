"""Sérialiseurs du moteur publicitaire Meta Ads (Groupe ENG)."""
from decimal import Decimal

from rest_framework import serializers

from .models import (
    AdCampaignMirror, AdSetMirror, AnomalyEvent, ArmDailyStat, CommentMirror,
    CreativeAsset, CreativeBacklogItem, CreativeGenerationBatch,
    CreativePolicy, DecisionLog, EngineAction, EngineAlert, Experiment,
    ExperimentArm, FlightPhase, FlightPlan, GuardrailConfig,
    InsightBreakdown, InsightSnapshot, InstagramCommentMirror,
    InstagramMediaMirror, MetaConnection, PacingState,
    ReconciliationSnapshot, RulePolicy,
)


def _same_company(serializer, value):
    """ADSENG3 — Refuse une FK vers un objet d'une AUTRE société (isolation
    multi-tenant côté serializer, en plus du scoping du viewset). ``value`` est
    l'instance liée ; None passe (champ optionnel absent)."""
    if value is None:
        return value
    request = serializer.context.get('request')
    company = getattr(getattr(request, 'user', None), 'company', None)
    if company is not None and value.company_id != company.id:
        raise serializers.ValidationError("Référence d'une autre société.")
    return value


class MetaConnectionSerializer(serializers.ModelSerializer):
    """ENG2 — Connexion Meta d'une société.

    ``credentials`` est **write-only** (pattern ``MonitoringConfigSerializer``) :
    on peut l'écrire (POST/PATCH) mais un GET ne le renvoie JAMAIS. Le client ne
    voit que ``has_credentials`` (booléen de présence). ``company`` est absente
    des champs : elle est posée côté serveur (``perform_create``), jamais lue du
    corps de requête.
    """

    has_credentials = serializers.SerializerMethodField()

    class Meta:
        model = MetaConnection
        fields = [
            'id', 'enabled', 'ad_account_id', 'page_id', 'pixel_id',
            'currency', 'credentials', 'has_credentials',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'credentials': {'write_only': True, 'required': False},
        }
        # ``currency`` : renseignée par la synchro (nœud de compte Meta), jamais
        # par le client.
        read_only_fields = ['currency', 'created_at', 'updated_at']

    def get_has_credentials(self, obj):
        return bool(obj.credentials)


class GuardrailConfigSerializer(serializers.ModelSerializer):
    """ENG3 — Garde-fous publicitaires d'une société.

    ``company`` est absente des champs (posée côté serveur). L'activation d'une
    campagne n'est volontairement AUCUN champ ici (interdite au niveau service).
    """

    class Meta:
        model = GuardrailConfig
        fields = [
            'id', 'daily_budget_ceiling_mad', 'weekly_change_pct_max',
            'anomaly_window_hours',
            # ENG8 — toggles de capacités (auto-apply par capacité).
            'auto_rotate_creative', 'auto_rebalance_within_band',
            # ADSENG4 — trésorerie : enveloppe mensuelle + pacing + exploration.
            'monthly_budget_ceiling_mad', 'pacing_band_pct',
            'exploration_floor_mad', 'exploration_floor_pct',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class EngineActionSerializer(serializers.ModelSerializer):
    """ENG7 — Action du moteur (propose→approuve→applique).

    Le POST (propose) n'accepte que ``kind`` / ``payload`` / ``reason_fr`` —
    ``reason_fr`` est OBLIGATOIRE (une phrase). ``status`` naît toujours
    ``proposee`` côté serveur ; ``auto``/``approved_by``/``applied_at``/
    ``result``/``error`` sont tous en lecture seule (posés par les services, jamais
    par le client). Une action ne s'approuve/rejette/applique QUE via ses actions
    dédiées, jamais par un PATCH direct de ``status``.
    """

    class Meta:
        model = EngineAction
        fields = [
            'id', 'kind', 'payload', 'reason_fr', 'status', 'auto',
            'approved_by', 'applied_at', 'result', 'error',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'auto', 'approved_by', 'applied_at', 'result', 'error',
            'created_at', 'updated_at',
        ]

    def validate_reason_fr(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Une raison en une phrase (français) est obligatoire.")
        return value.strip()


class EngineAlertSerializer(serializers.ModelSerializer):
    """ENG13 — Alerte moteur (lecture seule côté API).

    Rendue avec des deep-links ``wa.me`` (un par destinataire configuré) — mais
    l'ENVOI réel reste gated (BSP). Aucun secret exposé.
    """

    wa_links = serializers.SerializerMethodField()

    class Meta:
        model = EngineAlert
        fields = [
            'id', 'alert_type', 'message', 'action', 'detail',
            'acknowledged', 'wa_links', 'created_at', 'updated_at',
            # ADSENG4 — sévérité + cooldown + escalade.
            'severity', 'entity_key', 'cooldown_hours', 'unresolved_cycles',
            'resolved',
        ]
        # ``wa_links`` est un champ déclaré (SerializerMethodField, déjà
        # read-only) — il ne doit PAS figurer dans read_only_fields (DRF
        # l'interdit). Ce viewset est de toute façon GET-only (ENG13).
        read_only_fields = [
            'id', 'alert_type', 'message', 'action', 'detail',
            'acknowledged', 'created_at', 'updated_at',
            'severity', 'entity_key', 'cooldown_hours', 'unresolved_cycles',
            'resolved',
        ]

    def get_wa_links(self, obj):
        from .alerts import wa_links
        return wa_links(obj.message)


class CreativeAssetSerializer(serializers.ModelSerializer):
    """ENG15 — Asset créatif. ``file_key`` (posé par l'upload/la fabrique),
    ``policy_stamp`` (posé par la check-list ENG16) et ``perf`` sont en lecture
    seule : le client ne les écrit jamais directement. ``company`` posée côté
    serveur. ``is_policy_passed`` expose l'état de validation."""

    is_policy_passed = serializers.BooleanField(read_only=True)
    # ADSDEEP15 — URL présignée MinIO depuis ``file_key`` (patron
    # ``records.storage``) : sans elle, la créathèque n'affiche aucune preview
    # (l'écran attend ``preview_url || file_url``). ``is_video`` pilote le rendu
    # ``<video>`` pour un reel/explainer.
    preview_url = serializers.SerializerMethodField()
    is_video = serializers.SerializerMethodField()

    class Meta:
        model = CreativeAsset
        fields = [
            'id', 'asset_type', 'file_key', 'source_lane', 'cost_cents',
            'policy_stamp', 'is_policy_passed', 'perf', 'parent',
            'preview_url', 'is_video',
            # ADSENG5 — composants (accroche / texte / visuel / CTA).
            'hook_id', 'hook_text', 'primary_text', 'visual_asset_key', 'cta',
            'created_at', 'updated_at',
        ]
        # NB : ``is_policy_passed`` est déjà read-only (champ déclaré) — ne PAS
        # le remettre ici (DRF interdit un champ à la fois déclaré ET dans
        # read_only_fields).
        read_only_fields = [
            'file_key', 'policy_stamp', 'perf', 'created_at', 'updated_at',
        ]

    def get_preview_url(self, obj):
        """ADSDEEP15 — URL présignée MinIO depuis ``file_key`` (None si vide/
        stockage indisponible). Jamais un secret : c'est une URL de lecture
        temporaire signée, patron ``records.storage.presign_attachment``."""
        if not obj.file_key:
            return None
        from apps.records.storage import presign_attachment
        return presign_attachment(obj.file_key)

    def get_is_video(self, obj):
        """Un reel / explainer se rend en ``<video>`` (les statiques en ``<img>``)."""
        return obj.asset_type in (
            CreativeAsset.AssetType.REEL, CreativeAsset.AssetType.EXPLAINER)


class CreativePolicySerializer(serializers.ModelSerializer):
    """ENG16 — Policy créative d'une société. ``company`` posée côté serveur."""

    class Meta:
        model = CreativePolicy
        fields = [
            'id', 'forbidden_rules', 'allowed_rules',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ExperimentSerializer(serializers.ModelSerializer):
    """ADSENG3 — Expérience (test A/B/n). ``company`` posée côté serveur ;
    campagne/ad set cibles validés dans la même société."""

    class Meta:
        model = Experiment
        fields = [
            'id', 'name', 'tested_variable', 'status', 'campaign', 'adset',
            'start_date', 'end_date', 'notes',
            # ADSDEEP34 — lien vers l'étude A/B native Meta (posé par le
            # service, jamais par le client — read-only).
            'meta_study_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['meta_study_id', 'created_at', 'updated_at']

    def validate_campaign(self, value):
        return _same_company(self, value)

    def validate_adset(self, value):
        return _same_company(self, value)


class ExperimentArmSerializer(serializers.ModelSerializer):
    """ADSENG3 — Bras d'expérience. ``company`` posée côté serveur ;
    expérience/asset validés dans la même société."""

    class Meta:
        model = ExperimentArm
        fields = [
            'id', 'experiment', 'creative_asset', 'label', 'ad_id',
            'hook_id', 'visual_id', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_experiment(self, value):
        return _same_company(self, value)

    def validate_creative_asset(self, value):
        return _same_company(self, value)


class ArmDailyStatSerializer(serializers.ModelSerializer):
    """ADSENG3 — Stat quotidienne d'un bras. ``company`` posée côté serveur ;
    bras validé dans la même société."""

    class Meta:
        model = ArmDailyStat
        fields = [
            'id', 'arm', 'date', 'impressions', 'clicks', 'conversations',
            'spend', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_arm(self, value):
        return _same_company(self, value)


class DecisionLogSerializer(serializers.ModelSerializer):
    """ADSENG3 — Journal de décision (lecture seule côté API : écrit par la
    science P1, jamais par un client)."""

    class Meta:
        model = DecisionLog
        fields = [
            'id', 'experiment', 'inputs', 'posteriors', 'allocations',
            'summary_fr', 'action', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'experiment', 'inputs', 'posteriors', 'allocations',
            'summary_fr', 'action', 'created_at', 'updated_at',
        ]


class RulePolicySerializer(serializers.ModelSerializer):
    """ADSENG4 — Règle de garde-fou (le fondateur configure). ``company`` +
    ``created_by`` posés côté serveur ; ``last_*`` écrits par le moteur.
    Invariant DUR : ``mode='auto'`` interdit tant que ``dry_run`` est vrai."""

    class Meta:
        model = RulePolicy
        fields = [
            'id', 'template_key', 'enabled', 'mode', 'dry_run', 'conditions',
            'params', 'cadence_hours', 'cooldown_hours', 'last_evaluated_at',
            'last_result', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'last_evaluated_at', 'last_result', 'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        # État final = valeurs entrantes fondues sur l'instance existante.
        mode = attrs.get(
            'mode', getattr(self.instance, 'mode', RulePolicy.Mode.PROPOSE))
        dry_run = attrs.get(
            'dry_run', getattr(self.instance, 'dry_run', True))
        if mode == RulePolicy.Mode.AUTO and dry_run:
            raise serializers.ValidationError(
                "Le mode automatique est interdit en simulation (dry-run) : "
                "désactivez d'abord la simulation.")
        return attrs


class AnomalyEventSerializer(serializers.ModelSerializer):
    """ADSENG4 — Anomalie détectée (lecture seule : écrite par le gardien)."""

    class Meta:
        model = AnomalyEvent
        fields = [
            'id', 'kind', 'entity_type', 'entity_meta_id', 'severity',
            'message_fr', 'detail', 'resolved', 'rule_policy', 'alert',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'kind', 'entity_type', 'entity_meta_id', 'severity',
            'message_fr', 'detail', 'resolved', 'rule_policy', 'alert',
            'created_at', 'updated_at',
        ]


class PacingStateSerializer(serializers.ModelSerializer):
    """ADSENG4 — État de pacing mensuel (lecture seule : calculé par le
    moteur de trésorerie)."""

    class Meta:
        model = PacingState
        fields = [
            'id', 'period_start', 'monthly_budget_ceiling_mad',
            'spend_to_date', 'expected_spend_to_date', 'forecast_spend',
            'pacing_ratio', 'state', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'period_start', 'monthly_budget_ceiling_mad',
            'spend_to_date', 'expected_spend_to_date', 'forecast_spend',
            'pacing_ratio', 'state', 'created_at', 'updated_at',
        ]


class CreativeGenerationBatchSerializer(serializers.ModelSerializer):
    """ADSENG5 — Lot de génération créative. ``company`` posée côté serveur ;
    l'approbation (statut/approved_by/at) passe par les actions dédiées."""

    class Meta:
        model = CreativeGenerationBatch
        fields = [
            'id', 'source_hook_asset', 'visual_ids', 'status', 'approved_by',
            'approved_at', 'note', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'approved_by', 'approved_at', 'created_at', 'updated_at',
        ]

    def validate_source_hook_asset(self, value):
        return _same_company(self, value)


class CreativeBacklogItemSerializer(serializers.ModelSerializer):
    """ADSENG5 — Item de backlog créatif. FK validées dans la même société."""

    class Meta:
        model = CreativeBacklogItem
        fields = [
            'id', 'asset', 'batch', 'target_campaign', 'source',
            'earliest_date', 'seasonal_tag', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_asset(self, value):
        return _same_company(self, value)

    def validate_batch(self, value):
        return _same_company(self, value)

    def validate_target_campaign(self, value):
        return _same_company(self, value)


class FlightPlanSerializer(serializers.ModelSerializer):
    """ADSENG5 — Plan de vol. ``company`` posée côté serveur."""

    class Meta:
        model = FlightPlan
        fields = [
            'id', 'name', 'objective', 'status', 'start_date', 'end_date',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class FlightPhaseSerializer(serializers.ModelSerializer):
    """ADSENG5 — Phase de vol. Bornes de base : 2-4 bras, 1-8 semaines."""

    class Meta:
        model = FlightPhase
        fields = [
            'id', 'plan', 'order', 'name', 'tested_variable',
            'launch_template', 'budget_mad', 'start_date', 'end_date',
            'num_arms', 'week_span', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_plan(self, value):
        return _same_company(self, value)

    def validate_num_arms(self, value):
        if not (2 <= value <= 4):
            raise serializers.ValidationError(
                "Une phase teste entre 2 et 4 bras.")
        return value

    def validate_week_span(self, value):
        if not (1 <= value <= 8):
            raise serializers.ValidationError(
                "La durée d'une phase est de 1 à 8 semaines.")
        return value


class ReconciliationSnapshotSerializer(serializers.ModelSerializer):
    """ADSENG5 — Instantané de réconciliation (lecture seule : calculé par le
    moteur ; les deux chiffres Meta/ERP sont montrés côte à côte)."""

    class Meta:
        model = ReconciliationSnapshot
        fields = [
            'id', 'date', 'campaign', 'meta_leads', 'erp_leads', 'meta_spend',
            'delta_leads', 'status', 'detail', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'date', 'campaign', 'meta_leads', 'erp_leads', 'meta_spend',
            'delta_leads', 'status', 'detail', 'created_at', 'updated_at',
        ]


# ── ADSENGINT2 — Miroir de campagne pour la console (ENG24) ───────────────────
# Statut Meta FR pour l'affichage (le miroir rapporte la réalité Meta ; le
# service n'active jamais rien — invariant PAUSED intact).
_META_STATUT_FR = {
    'ACTIVE': 'Active',
    'PAUSED': 'En pause',
    'ARCHIVED': 'Archivée',
    'DELETED': 'Supprimée',
    'CAMPAIGN_PAUSED': 'Campagne en pause',
    'ADSET_PAUSED': "Ad set en pause",
}


class AdCampaignMirrorSerializer(serializers.ModelSerializer):
    """ADSENGINT2 — Miroir de campagne (lecture seule) pour l'écran Campagnes.

    Reflète le statut Meta tel quel (jamais d'activation), convertit le budget
    (unités mineures Meta → MAD) et agrège la dépense cumulée + le nombre de
    résultats depuis les ``InsightSnapshot`` rattachés (une seule source). Aucun
    secret ; company-scopé par le viewset."""

    statut = serializers.CharField(source='status', read_only=True)
    statut_display = serializers.SerializerMethodField()
    objectif = serializers.CharField(source='objective', read_only=True)
    budget_quotidien_mad = serializers.SerializerMethodField()
    depense_mad = serializers.SerializerMethodField()
    nb_leads = serializers.SerializerMethodField()

    class Meta:
        model = AdCampaignMirror
        fields = [
            'id', 'meta_id', 'name', 'statut', 'statut_display', 'objectif',
            'budget_quotidien_mad', 'depense_mad', 'nb_leads',
            'created_via_engine', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def _insights(self, obj):
        """Agrégat (dépense, résultats) mémoïsé par instance (évite un double
        calcul entre ``depense_mad`` et ``nb_leads``)."""
        cached = getattr(obj, '_ae_insights', None)
        if cached is None:
            from django.contrib.contenttypes.models import ContentType
            from django.db.models import Sum
            ct = ContentType.objects.get_for_model(AdCampaignMirror)
            cached = (InsightSnapshot.objects
                      .filter(company_id=obj.company_id, content_type=ct,
                              object_id=obj.pk)
                      .aggregate(spend=Sum('spend'), results=Sum('results')))
            obj._ae_insights = cached
        return cached

    def get_statut_display(self, obj):
        return _META_STATUT_FR.get(obj.status, obj.status or '—')

    def get_budget_quotidien_mad(self, obj):
        if obj.budget is None:
            return None
        # Budget Meta en unités mineures (centimes) → MAD (unités majeures).
        return str((obj.budget / Decimal('100')).quantize(Decimal('0.01')))

    def get_depense_mad(self, obj):
        return str(self._insights(obj)['spend'] or Decimal('0'))

    def get_nb_leads(self, obj):
        return int(self._insights(obj)['results'] or 0)


# ── ADSDEEP32 — Badge de phase d'apprentissage par ad set ─────────────────────
# Libellé + tonalité par statut d'apprentissage (le rendu frontend — badge dans
# ApprovalsScreen — est la tâche SÉPARÉE ADSDEEP35 ; ici on n'expose que la
# donnée). '' (inconnu) → un badge neutre, jamais d'erreur.
_LEARNING_BADGE = {
    'LEARNING': {'label': 'En apprentissage', 'tone': 'info'},
    'SUCCESS': {'label': 'Optimisé', 'tone': 'success'},
    'FAIL': {'label': 'Apprentissage limité', 'tone': 'danger'},
}


class AdSetMirrorSerializer(serializers.ModelSerializer):
    """ADSDEEP32 — Miroir d'ad set (lecture seule) exposant la phase
    d'apprentissage pour le badge UI. Le miroir reflète l'état Meta (jamais
    d'activation) ; company-scopé par le viewset."""

    learning_badge = serializers.SerializerMethodField()

    class Meta:
        model = AdSetMirror
        fields = [
            'id', 'meta_id', 'name', 'status', 'campaign',
            'learning_status', 'last_sig_edit', 'learning_stage_info',
            'learning_badge', 'created_via_engine',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_learning_badge(self, obj):
        """Badge {status, label, tone, is_learning, last_sig_edit} pour l'UI."""
        meta = _LEARNING_BADGE.get(
            obj.learning_status, {'label': 'Inconnu', 'tone': 'neutral'})
        return {
            'status': obj.learning_status or '',
            'label': meta['label'],
            'tone': meta['tone'],
            'is_learning': obj.is_learning,
            'last_sig_edit': (obj.last_sig_edit.isoformat()
                              if obj.last_sig_edit else None),
        }


class InsightBreakdownSerializer(serializers.ModelSerializer):
    """ADSDEEP9 — Ligne de ventilation (démo/placement/région/horaire) exposée à
    l'écran « Audience & diffusion ». Lecture seule ; aucun secret."""

    dimension_display = serializers.CharField(
        source='get_dimension_display', read_only=True)

    class Meta:
        model = InsightBreakdown
        fields = [
            'id', 'date', 'dimension', 'dimension_display', 'key',
            'spend', 'impressions', 'clicks', 'results', 'conversations',
        ]
        read_only_fields = fields


# ── ADSDEEP53/54 — Boîte de réception des commentaires ────────────────────────
class CommentMirrorSerializer(serializers.ModelSerializer):
    """ADSDEEP53 — Miroir de commentaire (lecture seule côté API : peuplé par la
    synchro, jamais écrit par le client — toute action passe par la proposition
    ``EngineAction`` via les vues dédiées, jamais un PATCH direct)."""

    class Meta:
        model = CommentMirror
        fields = [
            'id', 'meta_id', 'object_meta_id', 'source', 'parent_meta_id',
            'message', 'from_name', 'from_id', 'created_time', 'like_count',
            'reply_count', 'is_hidden', 'hidden_verified', 'can_hide',
            'can_remove', 'answered', 'permalink', 'private_reply_sent_at',
            'fetched_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


# ── ADSDEEP55/56 — Instagram (compte Business relié) ──────────────────────────
class InstagramMediaMirrorSerializer(serializers.ModelSerializer):
    """ADSDEEP55 — Miroir de média Instagram (lecture seule côté API). La
    ``caption`` est immuable après publication — jamais éditable ici (le SEUL
    champ écrivable, ``comment_enabled``, passe par la proposition dédiée)."""

    class Meta:
        model = InstagramMediaMirror
        fields = [
            'id', 'meta_id', 'caption', 'media_type', 'media_url',
            'permalink', 'like_count', 'comments_count', 'view_count',
            'comment_enabled', 'timestamp', 'fetched_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class InstagramCommentMirrorSerializer(serializers.ModelSerializer):
    """ADSDEEP55 — Miroir de commentaire Instagram (lecture seule côté API) ;
    toute action (masquer/répondre/supprimer) passe par la proposition
    ``EngineAction`` via les vues dédiées, jamais un PATCH direct."""

    class Meta:
        model = InstagramCommentMirror
        fields = [
            'id', 'meta_id', 'media_meta_id', 'parent_meta_id', 'message',
            'from_username', 'like_count', 'hidden', 'answered', 'timestamp',
            'fetched_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
