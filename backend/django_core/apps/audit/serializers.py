"""Sérialisation des entrées du Journal d'activité (lecture seule)."""
from zoneinfo import ZoneInfo

from rest_framework import serializers

from .models import AuditLog

CASABLANCA = ZoneInfo('Africa/Casablanca')


class AuditLogSerializer(serializers.ModelSerializer):
    utilisateur = serializers.SerializerMethodField()
    action_label = serializers.CharField(
        source='get_action_display', read_only=True)
    module = serializers.SerializerMethodField()
    model = serializers.SerializerMethodField()
    timestamp_local = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            'id', 'action', 'action_label', 'utilisateur', 'actor_username',
            'module', 'model', 'object_id', 'object_repr', 'detail',
            'timestamp', 'timestamp_local',
        )

    def get_utilisateur(self, obj):
        if obj.user_id:
            return obj.user.username
        return obj.actor_username or 'Système'

    def get_module(self, obj):
        return obj.content_type.app_label if obj.content_type_id else ''

    def get_model(self, obj):
        return obj.content_type.model if obj.content_type_id else ''

    def get_timestamp_local(self, obj):
        # Affichage Casablanca (la base stocke en UTC).
        if obj.timestamp is None:
            return None
        return obj.timestamp.astimezone(CASABLANCA).isoformat()
