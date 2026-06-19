from rest_framework import serializers

from .models import EventType, Notification, NotificationPreference


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
