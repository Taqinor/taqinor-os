"""Sérialiseurs du moteur publicitaire Meta Ads (Groupe ENG)."""
from rest_framework import serializers

from .models import (
    CreativeAsset, CreativePolicy, EngineAction, EngineAlert, GuardrailConfig,
    MetaConnection,
)


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
            'credentials', 'has_credentials', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'credentials': {'write_only': True, 'required': False},
        }
        read_only_fields = ['created_at', 'updated_at']

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
        ]
        # ``wa_links`` est un champ déclaré (SerializerMethodField, déjà
        # read-only) — il ne doit PAS figurer dans read_only_fields (DRF
        # l'interdit). Ce viewset est de toute façon GET-only (ENG13).
        read_only_fields = [
            'id', 'alert_type', 'message', 'action', 'detail',
            'acknowledged', 'created_at', 'updated_at',
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

    class Meta:
        model = CreativeAsset
        fields = [
            'id', 'asset_type', 'file_key', 'source_lane', 'cost_cents',
            'policy_stamp', 'is_policy_passed', 'perf', 'parent',
            'created_at', 'updated_at',
        ]
        # NB : ``is_policy_passed`` est déjà read-only (champ déclaré) — ne PAS
        # le remettre ici (DRF interdit un champ à la fois déclaré ET dans
        # read_only_fields).
        read_only_fields = [
            'file_key', 'policy_stamp', 'perf', 'created_at', 'updated_at',
        ]


class CreativePolicySerializer(serializers.ModelSerializer):
    """ENG16 — Policy créative d'une société. ``company`` posée côté serveur."""

    class Meta:
        model = CreativePolicy
        fields = [
            'id', 'forbidden_rules', 'allowed_rules',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
