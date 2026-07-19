"""Sérialiseurs du moteur publicitaire Meta Ads (Groupe ENG)."""
import datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import (
    AdCampaignMirror, AdMirror, AdSetMirror, Annotation, AnomalyEvent,
    ArmDailyStat,
    AssumptionNode, BrandKit, CommentMirror,
    CompetitorAdObservation, CompetitorPage, ConsentRecord, CreativeAsset,
    CreativeBacklogItem,
    CreativeGenerationBatch, CreativePolicy, DecisionLog, EngineAction,
    EngineAlert, Experiment, ExperimentArm, FactEntry, FactTable,
    FlightPhase, FlightPlan, ProposalTemplate,
    GuardrailConfig, InsightBreakdown, InsightSnapshot,
    InstagramCommentMirror, InstagramMediaMirror, MetaConnection,
    PacingState, ReconciliationSnapshot, RulePolicy,
)


def _extract_token_expiry(credentials):
    """PUB20 — Extrait au mieux l'expiration d'un token depuis les identifiants.

    Accepte ``expires_at`` (epoch secondes, comme le renvoie ``debug_token`` Meta)
    ou ``token_expires_at`` (ISO-8601). Renvoie un ``datetime`` aware ou ``None``
    (un System-User long-lived n'a souvent aucune expiration — c'est légitime)."""
    if not isinstance(credentials, dict):
        return None
    epoch = credentials.get('expires_at')
    if isinstance(epoch, (int, float)) and epoch > 0:
        return datetime.datetime.fromtimestamp(
            epoch, tz=datetime.timezone.utc)
    iso = credentials.get('token_expires_at')
    if isinstance(iso, str) and iso.strip():
        try:
            parsed = datetime.datetime.fromisoformat(iso.strip())
        except ValueError:
            return None
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, datetime.timezone.utc)
        return parsed
    return None


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
            # PUB20 — état santé du token (lecture seule) pour le bandeau
            # ConnectionScreen/Dashboard (front = lane console). `token_invalid`
            # est posé par les tâches de synchro sur une auth-error 190.
            'token_expires_at', 'token_invalid', 'token_invalid_at',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'credentials': {'write_only': True, 'required': False},
        }
        # ``currency`` : renseignée par la synchro (nœud de compte Meta), jamais
        # par le client. Les champs d'état PUB20 sont posés côté serveur (synchro).
        read_only_fields = [
            'currency', 'token_expires_at', 'token_invalid',
            'token_invalid_at', 'created_at', 'updated_at',
        ]

    def get_has_credentials(self, obj):
        return bool(obj.credentials)

    def _apply_token_state(self, instance, credentials):
        """PUB20 — À la (re)connexion, renseigne au mieux ``token_expires_at``
        si les identifiants portent une expiration (``expires_at`` epoch ou
        ``token_expires_at`` ISO), et lève tout état « token mort » précédent
        dès qu'un nouveau token est fourni (le client repart propre)."""
        creds = credentials or {}
        expiry = _extract_token_expiry(creds)
        changed = []
        if expiry is not None and instance.token_expires_at != expiry:
            instance.token_expires_at = expiry
            changed.append('token_expires_at')
        if creds.get('access_token') and (
                instance.token_invalid or instance.token_invalid_at):
            instance.token_invalid = False
            instance.token_invalid_at = None
            changed += ['token_invalid', 'token_invalid_at']
        if changed:
            instance.save(update_fields=changed)
        return instance

    def create(self, validated_data):
        credentials = validated_data.get('credentials')
        instance = super().create(validated_data)
        return self._apply_token_state(instance, credentials)

    def update(self, instance, validated_data):
        credentials = validated_data.get('credentials')
        instance = super().update(instance, validated_data)
        # Ne toucher l'état que si de nouveaux identifiants sont fournis.
        if 'credentials' in validated_data:
            self._apply_token_state(instance, credentials)
        return instance


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
            # SIG1 — poids fixes des deux scores de santé (créatif/opérations).
            'health_creative_weight_ctr', 'health_creative_weight_freshness',
            'health_ops_weight_cpl', 'health_ops_weight_delivery',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class AnnotationSerializer(serializers.ModelSerializer):
    """PUB49 — Annotation de courbe (note de décision épinglée à une date).

    ``company`` est absente des champs (posée côté serveur, jamais lue du corps).
    Le rendu en surimpression sur les courbes est côté front (lane console)."""

    class Meta:
        model = Annotation
        fields = ['id', 'date', 'texte', 'portee', 'created_at', 'updated_at']
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
    # PUB48 — lien profond FR vers l'entité concernée (approbation liée, écran
    # d'origine du gabarit, ou Règles & anomalies à défaut).
    link = serializers.SerializerMethodField()
    # PUB48 — snooze (reporté jusqu'à cette date) : stocké dans `detail`
    # (JSONField déjà existant, aucune migration) — exposé pour la cloche.
    snoozed_until = serializers.SerializerMethodField()

    class Meta:
        model = EngineAlert
        fields = [
            'id', 'alert_type', 'message', 'action', 'detail',
            'acknowledged', 'wa_links', 'link', 'snoozed_until',
            'created_at', 'updated_at',
            # ADSENG4 — sévérité + cooldown + escalade.
            'severity', 'entity_key', 'cooldown_hours', 'unresolved_cycles',
            'resolved',
        ]
        # ``wa_links``/``link``/``snoozed_until`` sont des champs déclarés
        # (SerializerMethodField, déjà read-only) — ils ne doivent PAS figurer
        # dans read_only_fields (DRF l'interdit). Ce viewset est de toute
        # façon GET-only (ENG13).
        read_only_fields = [
            'id', 'alert_type', 'message', 'action', 'detail',
            'acknowledged', 'created_at', 'updated_at',
            'severity', 'entity_key', 'cooldown_hours', 'unresolved_cycles',
            'resolved',
        ]

    def get_wa_links(self, obj):
        from .alerts import wa_links
        return wa_links(obj.message)

    def get_link(self, obj):
        from .alerts import deep_link_for_alert
        return deep_link_for_alert(obj)

    def get_snoozed_until(self, obj):
        return (obj.detail or {}).get('snoozed_until')


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
    # PUB75 — statut consentement (CNDP) : raison de blocage lisible (ou None).
    consent_block = serializers.SerializerMethodField()
    has_valid_consent = serializers.BooleanField(read_only=True)
    # PUB83 — avertissements NON BLOQUANTS de la check-list (ex. vignette manquante).
    checklist_warnings = serializers.SerializerMethodField()

    def validate_consent(self, value):
        return _same_company(self, value)

    class Meta:
        model = CreativeAsset
        fields = [
            'id', 'asset_type', 'file_key', 'source_lane', 'cost_cents',
            'policy_stamp', 'is_policy_passed', 'perf', 'parent',
            'preview_url', 'is_video',
            # PUB75 — consentement image/témoignage (CNDP).
            'depicts_real_client', 'consent', 'consent_scopes_required',
            'consent_block', 'has_valid_consent',
            # PUB76 — fraîcheur ; PUB77 — langue ; PUB83 — vignette choisie.
            'facts_version', 'expires_at', 'review_after', 'needs_review',
            'review_reason', 'language', 'thumbnail_key', 'checklist_warnings',
            # ADSENG5 — composants (accroche / texte / visuel / CTA).
            'hook_id', 'hook_text', 'primary_text', 'visual_asset_key', 'cta',
            'created_at', 'updated_at',
        ]
        # NB : ``is_policy_passed`` est déjà read-only (champ déclaré) — ne PAS
        # le remettre ici (DRF interdit un champ à la fois déclaré ET dans
        # read_only_fields).
        read_only_fields = [
            'file_key', 'policy_stamp', 'perf',
            # PUB76 — posés par le job de fraîcheur, jamais par le client.
            'facts_version', 'needs_review', 'review_reason',
            'created_at', 'updated_at',
        ]

    def get_checklist_warnings(self, obj):
        """PUB83 — Avertissements non bloquants de la check-list policy."""
        from .policy import asset_warnings
        return asset_warnings(obj)

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

    def get_consent_block(self, obj):
        """PUB75 — Raison de blocage consentement (CNDP) lisible, ou ``None``."""
        return obj.consent_block_reason()


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
            'approved_at', 'note',
            # AGEN1 — audit de génération ancrée (posé par le pipeline, jamais
            # par un client).
            'fact_table_version', 'claim_verdicts', 'template_quarantined',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'approved_by', 'approved_at', 'created_at', 'updated_at',
            'fact_table_version', 'claim_verdicts', 'template_quarantined',
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
        calcul entre ``depense_mad`` et ``nb_leads``).

        PUB40 — borné à ``context['debut']``/``context['fin']`` (dates ISO
        `datetime.date`, sélecteur de période de l'écran Campagnes) quand
        présents ; absents (défaut, y compris hors contexte de requête), la
        dépense reste cumulée sur TOUT l'historique — comportement inchangé."""
        cached = getattr(obj, '_ae_insights', None)
        if cached is None:
            from django.contrib.contenttypes.models import ContentType
            from django.db.models import Sum
            ct = ContentType.objects.get_for_model(AdCampaignMirror)
            qs = InsightSnapshot.objects.filter(
                company_id=obj.company_id, content_type=ct, object_id=obj.pk)
            debut = self.context.get('debut')
            fin = self.context.get('fin')
            if debut is not None:
                qs = qs.filter(date__gte=debut)
            if fin is not None:
                qs = qs.filter(date__lte=fin)
            cached = qs.aggregate(spend=Sum('spend'), results=Sum('results'))
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


def _spend_results_for(model, obj):
    """ADSDEEP60 — Agrégat (dépense, résultats) mémoïsé par instance depuis les
    ``InsightSnapshot`` rattachés à ``obj`` (FK générique). Factorisation
    partagée par les sérialiseurs de miroir (campagne/ad set/ad) — même
    formule que ``AdCampaignMirrorSerializer._insights``, sans dupliquer la
    requête pour les nouveaux niveaux de la hiérarchie."""
    cached = getattr(obj, '_ae_insights', None)
    if cached is None:
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Sum
        ct = ContentType.objects.get_for_model(model)
        cached = (InsightSnapshot.objects
                  .filter(company_id=obj.company_id, content_type=ct,
                          object_id=obj.pk)
                  .aggregate(spend=Sum('spend'), results=Sum('results')))
        obj._ae_insights = cached
    return cached


class AdSetMirrorSerializer(serializers.ModelSerializer):
    """ADSDEEP32/ADSDEEP60 — Miroir d'ad set (lecture seule) exposant la phase
    d'apprentissage pour le badge UI + (ADSDEEP60) statut FR, budget converti
    et dépense/résultats agrégés pour l'écran hiérarchique Campagnes→Ad
    sets→Ads. Le miroir reflète l'état Meta (jamais d'activation) ;
    company-scopé par le viewset."""

    learning_badge = serializers.SerializerMethodField()
    statut_display = serializers.SerializerMethodField()
    budget_quotidien_mad = serializers.SerializerMethodField()
    depense_mad = serializers.SerializerMethodField()
    nb_leads = serializers.SerializerMethodField()

    class Meta:
        model = AdSetMirror
        fields = [
            'id', 'meta_id', 'name', 'status', 'statut_display', 'campaign',
            'learning_status', 'last_sig_edit', 'learning_stage_info',
            'learning_badge', 'budget_quotidien_mad', 'depense_mad',
            'nb_leads', 'created_via_engine', 'created_at', 'updated_at',
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

    def get_statut_display(self, obj):
        return _META_STATUT_FR.get(obj.status, obj.status or '—')

    def get_budget_quotidien_mad(self, obj):
        if obj.budget is None:
            return None
        # Budget Meta en unités mineures (centimes) → MAD (unités majeures).
        return str((obj.budget / Decimal('100')).quantize(Decimal('0.01')))

    def get_depense_mad(self, obj):
        return str(_spend_results_for(AdSetMirror, obj)['spend'] or Decimal('0'))

    def get_nb_leads(self, obj):
        return int(_spend_results_for(AdSetMirror, obj)['results'] or 0)


class AdMirrorSerializer(serializers.ModelSerializer):
    """ADSDEEP60 — Miroir d'ad (lecture seule) pour le 3ᵉ niveau de la
    hiérarchie Campagnes→Ad sets→Ads : statut FR + dépense/résultats agrégés
    depuis les mêmes ``InsightSnapshot`` (ad-level, ADSDEEP2). Aucune
    activation ; company-scopé par le viewset appelant."""

    statut_display = serializers.SerializerMethodField()
    depense_mad = serializers.SerializerMethodField()
    nb_leads = serializers.SerializerMethodField()

    class Meta:
        model = AdMirror
        fields = [
            'id', 'meta_id', 'name', 'status', 'statut_display', 'adset',
            'depense_mad', 'nb_leads', 'hook_tag', 'angle_tag', 'format_tag',
            'created_via_engine', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_statut_display(self, obj):
        return _META_STATUT_FR.get(obj.status, obj.status or '—')

    def get_depense_mad(self, obj):
        return str(_spend_results_for(AdMirror, obj)['spend'] or Decimal('0'))

    def get_nb_leads(self, obj):
        return int(_spend_results_for(AdMirror, obj)['results'] or 0)


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

    # PUB44 — lien croisé vers la fiche « histoire complète » de l'ad (un
    # commentaire source=AD porte l'``effective_object_story_id`` du créatif
    # dans ``object_meta_id``, PAS le ``meta_id`` de l'ad — dossier
    # organic-posts §3). Résolu via ``context['story_to_ad']`` (map construite
    # UNE FOIS par ``CommentListView``, jamais une requête par ligne) ; ``None``
    # si le contexte n'est pas fourni ou si aucune ad ne correspond.
    ad_meta_id = serializers.SerializerMethodField()

    class Meta:
        model = CommentMirror
        fields = [
            'id', 'meta_id', 'object_meta_id', 'source', 'parent_meta_id',
            'message', 'from_name', 'from_id', 'created_time', 'like_count',
            'reply_count', 'is_hidden', 'hidden_verified', 'can_hide',
            'can_remove', 'answered', 'permalink', 'private_reply_sent_at',
            'fetched_at', 'created_at', 'updated_at', 'ad_meta_id',
        ]
        read_only_fields = fields

    def get_ad_meta_id(self, obj):
        if obj.source != CommentMirror.Source.AD:
            return None
        return self.context.get('story_to_ad', {}).get(obj.object_meta_id)


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


# ── ASG1 — Assumption Engine (arbre vivant de croyances testées) ──────────────
class AssumptionNodeSerializer(serializers.ModelSerializer):
    """ASG1 — Nœud de l'Assumption Engine (dd-assumption-engine §3.1).

    ``company`` est absente des champs (posée côté serveur). ``parent`` et
    ``invalidation_links`` sont contraints à la MÊME société
    (``_same_company``) — un DAG ne traverse jamais une frontière de tenant.
    ``demi_vie_semaines`` reçoit le défaut de sa classe (``HALF_LIFE_WEEKS``)
    quand absente ; une valeur fournie explicitement n'est jamais écrasée.
    """

    class Meta:
        model = AssumptionNode
        fields = [
            'id', 'classe', 'enonce_fr', 'enjeux_s', 'pertinence_r',
            'tags_saison', 'parent', 'invalidation_links',
            'alpha', 'beta', 'alpha0', 'beta0', 'demi_vie_semaines',
            'last_tested_at', 'statut', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_parent(self, value):
        return _same_company(self, value)

    def validate_invalidation_links(self, value):
        for node in value:
            _same_company(self, node)
        return value

    def validate(self, attrs):
        if attrs.get('demi_vie_semaines') is None:
            classe = attrs.get('classe') or getattr(
                self.instance, 'classe', None)
            if classe:
                attrs['demi_vie_semaines'] = (
                    AssumptionNode.HALF_LIFE_WEEKS.get(classe))
        return attrs


# ── AGEN1 — Table de faits versionnée (génération autonome ancrée) ────────────
class FactTableSerializer(serializers.ModelSerializer):
    """AGEN1 — Table de faits versionnée. ``version``/``statut`` sont EN
    LECTURE SEULE : la version est toujours calculée côté serveur
    (:meth:`FactTable.create_draft`, jamais un ``count()+1``) et le passage en
    'publiee' passe UNIQUEMENT par l'action ``publish`` — jamais un PATCH
    direct de statut (même discipline que ``CreativeGenerationBatch``)."""

    class Meta:
        model = FactTable
        fields = ['id', 'version', 'statut', 'created_at', 'updated_at']
        read_only_fields = ['version', 'statut', 'created_at', 'updated_at']

    def create(self, validated_data):
        return FactTable.create_draft(validated_data['company'])


class FactEntrySerializer(serializers.ModelSerializer):
    """AGEN1 — Une entrée de table de faits. ``table`` est contrainte à la
    MÊME société (``_same_company``)."""

    class Meta:
        model = FactEntry
        fields = [
            'id', 'table', 'cle', 'valeur', 'unite', 'source', 'verifie_le',
            # PUB85 — région optionnelle ('' = national ; ville = surcharge locale).
            'region',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_table(self, value):
        return _same_company(self, value)


class ConsentRecordSerializer(serializers.ModelSerializer):
    """PUB75 — Consentement image/témoignage (CNDP loi 09-08). ``company`` posée
    côté serveur ; ``revoked_at`` est en lecture seule (révoquer passe par
    l'action ``revoquer``, jamais un PATCH direct). ``scopes``/``is_active``
    exposent l'état pour l'UI de collecte simple."""

    scopes = serializers.ListField(
        child=serializers.CharField(), read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = ConsentRecord
        fields = [
            'id', 'client_id', 'client_nom', 'reference', 'canal',
            'portee_photo', 'portee_video', 'portee_temoignage', 'portee_geo',
            'date_consentement', 'expiration', 'revoked_at',
            'note', 'scopes', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['revoked_at', 'created_at', 'updated_at']

    def get_is_active(self, obj):
        return obj.is_active()


class CompetitorPageSerializer(serializers.ModelSerializer):
    """PUB70 — Page concurrente suivie. ``ad_library_url`` (lien profond WEB) est
    calculé côté serveur, en lecture seule (jamais un appel API, jamais un
    scraping). ``company`` posée côté serveur."""

    ad_library_url = serializers.SerializerMethodField()

    class Meta:
        model = CompetitorPage
        fields = [
            'id', 'name', 'page_id', 'country', 'website', 'note', 'active',
            'ad_library_url', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_ad_library_url(self, obj):
        return obj.ad_library_url()


class CompetitorAdObservationSerializer(serializers.ModelSerializer):
    """PUB70 — Observation manuelle (hook/angle reformulé, jamais copié verbatim).
    ``competitor_page`` contrainte à la MÊME société. ``company`` posée côté
    serveur."""

    competitor_name = serializers.CharField(
        source='competitor_page.name', read_only=True)

    class Meta:
        model = CompetitorAdObservation
        fields = [
            'id', 'competitor_page', 'competitor_name', 'observed_at',
            'hook_text', 'angle', 'format', 'source_url', 'note',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_competitor_page(self, value):
        return _same_company(self, value)


class ProposalTemplateSerializer(serializers.ModelSerializer):
    """PUB50 — Gabarit de proposition réutilisable. ``company`` posée côté
    serveur ; appliquer un gabarit ne fait que pré-remplir un composeur (aucune
    exécution automatique)."""

    class Meta:
        model = ProposalTemplate
        fields = [
            'id', 'name', 'kind', 'scope', 'payload', 'reason_fr', 'note',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Un nom de gabarit est requis.")
        return value.strip()


class BrandKitSerializer(serializers.ModelSerializer):
    """PUB83 — Kit de marque persistant (logo/couleurs/zones de sécurité/polices).
    ``company`` posée côté serveur ; consommé par le ``TemplatedAdapter`` au lieu
    d'un payload de marque ad hoc."""

    class Meta:
        model = BrandKit
        fields = [
            'id', 'name', 'logo_key', 'colors', 'safe_zones', 'fonts',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
