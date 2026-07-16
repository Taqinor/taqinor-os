"""Serializers de GESTION (écran Paramètres) pour clés API & webhooks (N89).

Authentifiés par session/JWT normaux, palier admin. La clé en clair et le
secret webhook ne sont JAMAIS renvoyés en lecture — uniquement une fois, à la
création, par les vues dédiées.
"""
from rest_framework import serializers

from core.models import ApiUsagePlan

from .constants import ALL_SCOPES, ALL_EVENTS, SCOPE_CHOICES, EVENT_CHOICES
from .models import ApiKey, ServiceAccount, Webhook, WebhookDelivery
from .validators import UnsafeWebhookURL, validate_webhook_target_url


class ApiKeySerializer(serializers.ModelSerializer):
    """Représentation en lecture d'une clé (jamais le secret)."""
    created_by_nom = serializers.SerializerMethodField()

    class Meta:
        model = ApiKey
        fields = [
            'id', 'label', 'prefix', 'scopes', 'enabled', 'api_version',
            'created_by', 'created_by_nom', 'created_at', 'last_used_at',
        ]
        read_only_fields = fields

    def get_created_by_nom(self, obj):
        u = obj.created_by
        if not u:
            return ''
        return (u.get_full_name() or u.username or u.email or '').strip()


class ApiKeyCreateSerializer(serializers.Serializer):
    """Entrée de création : libellé + scopes. Renvoie la clé en clair UNE fois."""
    label = serializers.CharField(max_length=120)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=ALL_SCOPES),
        allow_empty=True, default=list)

    def validate_label(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Le libellé est obligatoire.')
        return value


class WebhookSerializer(serializers.ModelSerializer):
    """Représentation en lecture d'un webhook (jamais le secret en clair)."""

    class Meta:
        model = Webhook
        fields = [
            'id', 'label', 'target_url', 'events', 'enabled',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_events(self, value):
        unknown = [e for e in value if e not in ALL_EVENTS]
        if unknown:
            raise serializers.ValidationError(
                f'Évènements inconnus : {", ".join(unknown)}.')
        return value

    def validate_target_url(self, value):
        # ERR46 — refuse https + bloque les hôtes internes (anti-SSRF).
        try:
            return validate_webhook_target_url(value)
        except UnsafeWebhookURL as exc:
            raise serializers.ValidationError(str(exc))


def scope_catalogue():
    """Catalogue scopes/évènements pour peupler l'écran Paramètres."""
    return {
        'scopes': [{'code': c, 'label': lbl} for c, lbl in SCOPE_CHOICES],
        'events': [{'code': c, 'label': lbl} for c, lbl in EVENT_CHOICES],
    }


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = [
            'id', 'webhook', 'event', 'payload', 'status', 'response_status',
            'error', 'created_at',
        ]
        read_only_fields = fields


class ApiUsagePlanSerializer(serializers.ModelSerializer):
    """NTAPI7 — plan d'API nommé de la société (gratuit/pro/entreprise).

    ``company`` n'est JAMAIS acceptée en écriture : la vue la force depuis
    ``request.user.company`` (jamais du corps de requête)."""

    class Meta:
        model = ApiUsagePlan
        fields = [
            'id', 'code', 'quota_par_minute', 'quota_par_jour',
            'quota_par_mois', 'quota_burst', 'retention_livraisons_jours',
            'nb_webhooks_max', 'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ServiceAccountSerializer(serializers.ModelSerializer):
    """NTSEC24 — compte de service (jeton renvoyé UNE fois à la création)."""

    class Meta:
        model = ServiceAccount
        fields = [
            'id', 'nom', 'scopes', 'prefix', 'actif', 'expire_le',
            'last_used_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'prefix', 'last_used_at', 'created_at']
