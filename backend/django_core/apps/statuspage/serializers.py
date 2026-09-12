"""NTOBS1/NTOBS2 — sérialiseurs de la page de statut publique.

Aucun champ interne (id de société, détail des sondes ``core.health``) n'est
exposé — R1 (garde « forme déclarée réelle ») : chaque champ est nommé
explicitement, jamais un simple ``OpenApiTypes.OBJECT`` opaque côté OpenAPI.
"""
from rest_framework import serializers

from .models import ComponentStatus, IncidentPublic, IncidentUpdate, UptimeDayBucket


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

    class Meta:
        model = IncidentPublic
        fields = [
            'id', 'titre', 'severite', 'statut', 'region', 'composants',
            'debute_le', 'resolu_le', 'updates',
            'postmortem_markdown', 'postmortem_publie_le',
        ]

    def get_postmortem_markdown(self, obj) -> str:
        if obj.postmortem_publie_le:
            return obj.postmortem_markdown
        return ''


class UptimeDayBucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = UptimeDayBucket
        fields = ['composant', 'date', 'statut_pire_du_jour', 'pct_disponible_jour']
