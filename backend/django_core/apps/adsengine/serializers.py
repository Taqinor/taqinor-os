"""Sérialiseurs du moteur publicitaire Meta Ads (Groupe ENG)."""
from rest_framework import serializers

from .models import GuardrailConfig, MetaConnection


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
            'anomaly_window_hours', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
