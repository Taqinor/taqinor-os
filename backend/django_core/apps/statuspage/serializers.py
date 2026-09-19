"""NTOBS1/NTOBS2 — sérialiseurs de la page de statut publique.

Aucun champ interne (id de société, détail des sondes ``core.health``) n'est
exposé — R1 (garde « forme déclarée réelle ») : chaque champ est nommé
explicitement, jamais un simple ``OpenApiTypes.OBJECT`` opaque côté OpenAPI.
"""
from rest_framework import serializers

from .models import (
    ComponentStatus, ComponentStatusLog, IncidentPublic, IncidentUpdate,
    UptimeDayBucket,
)


class ComponentStatusPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentStatus
        fields = ['nom', 'region', 'statut', 'derniere_verification']


class IncidentUpdatePublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentUpdate
        fields = ['statut', 'message', 'horodatage']


class IncidentPublicSerializer(serializers.ModelSerializer):
    updates = IncidentUpdatePublicSerializer(many=True, read_only=True)
    composants = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field='nom')
    # NTOBS2 — le contenu du post-mortem n'apparaît que s'il est PUBLIÉ
    # (jamais un brouillon interne exposé publiquement).
    postmortem_markdown = serializers.SerializerMethodField()
    # NTOBS23 — horodatages dans le fuseau d'affichage du VIEWER quand connu
    # (page publique le plus souvent anonyme : ``company=None`` -> fuseau par
    # défaut ``core.tz_display.DEFAULT_TIMEZONE``, jamais une exception).
    debute_le_local = serializers.SerializerMethodField()
    resolu_le_local = serializers.SerializerMethodField()

    class Meta:
        model = IncidentPublic
        fields = [
            'id', 'titre', 'severite', 'statut', 'region', 'composants',
            'debute_le', 'resolu_le', 'updates',
            'postmortem_markdown', 'postmortem_publie_le',
            'debute_le_local', 'resolu_le_local',
        ]

    def get_postmortem_markdown(self, obj) -> str:
        if obj.postmortem_publie_le:
            return obj.postmortem_markdown
        return ''

    def _viewer_company(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        company = getattr(user, 'company', None)
        return company or obj.company

    def get_debute_le_local(self, obj) -> str:
        from core.tz_display import to_company_tz
        return to_company_tz(obj.debute_le, self._viewer_company(obj)).isoformat()

    def get_resolu_le_local(self, obj):
        from core.tz_display import to_company_tz
        local = to_company_tz(obj.resolu_le, self._viewer_company(obj))
        return local.isoformat() if local is not None else None


class UptimeDayBucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = UptimeDayBucket
        fields = ['composant', 'date', 'statut_pire_du_jour', 'pct_disponible_jour']


class ComponentStatusLogSerializer(serializers.ModelSerializer):
    """NTOBS33 — historique brut des changements de statut (admin interne)."""

    class Meta:
        model = ComponentStatusLog
        fields = [
            'id', 'composant', 'region', 'ancien_statut', 'nouveau_statut',
            'created_at',
        ]
