from rest_framework import serializers

from .models import (
    EventType, Holiday, Notification, NotificationPreference,
    NotificationRoutingRule, WorkingHoursConfig,
)


class NotificationSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(
        source='get_event_type_display', read_only=True)

    class Meta:
        model = Notification
        # company + recipient posés côté serveur — jamais lus du corps.
        fields = [
            'id', 'event_type', 'event_label', 'title', 'body', 'link',
            'read', 'read_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'event_type', 'event_label', 'title', 'body', 'link',
            'read_at', 'created_at',
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(
        source='get_event_type_display', read_only=True)

    class Meta:
        model = NotificationPreference
        # company + user posés côté serveur — jamais lus du corps.
        fields = ['id', 'event_type', 'event_label', 'in_app', 'whatsapp', 'email']
        read_only_fields = ['id', 'event_label']

    def validate_event_type(self, value):
        if value not in EventType.values:
            raise serializers.ValidationError("Type d'événement inconnu.")
        return value


class NotificationRoutingRuleSerializer(serializers.ModelSerializer):
    """FG4 — Serializer des règles de routage (admin seulement)."""
    event_label = serializers.CharField(
        source='get_event_type_display', read_only=True)
    target_role_label = serializers.CharField(
        source='get_target_role_display', read_only=True)

    class Meta:
        model = NotificationRoutingRule
        # company posée côté serveur (TenantMixin + perform_create).
        fields = [
            'id', 'event_type', 'event_label',
            'target_role', 'target_role_label', 'target_user',
            'enabled', 'created_at',
        ]
        read_only_fields = ['id', 'event_label', 'target_role_label', 'created_at']

    def validate(self, data):
        if not data.get('target_role') and not data.get('target_user'):
            raise serializers.ValidationError(
                'Une règle de routage doit cibler soit un rôle, soit un utilisateur.')
        return data


class WorkingHoursConfigSerializer(serializers.ModelSerializer):
    """FG5 — Sérializer de la configuration des jours ouvrés (singleton société)."""

    class Meta:
        model = WorkingHoursConfig
        # company posée côté serveur — jamais acceptée du corps.
        fields = ['id', 'working_days', 'hours_per_day', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class HolidaySerializer(serializers.ModelSerializer):
    """FG5 — Sérializer des jours fériés."""

    class Meta:
        model = Holiday
        # company posée côté serveur — jamais acceptée du corps.
        fields = ['id', 'date', 'nom', 'recurrent_annuel', 'created_at']
        read_only_fields = ['id', 'created_at']
