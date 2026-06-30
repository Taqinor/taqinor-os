"""FG25 — sérialiseur des politiques d'approbation (ApprovalPolicy)."""
from rest_framework import serializers

from .models_approvals import ApprovalPolicy


class ApprovalPolicySerializer(serializers.ModelSerializer):
    action_type_label = serializers.CharField(
        source='get_action_type_display', read_only=True)
    approver_tier_label = serializers.CharField(
        source='get_approver_tier_display', read_only=True)

    class Meta:
        model = ApprovalPolicy
        fields = [
            'id', 'action_type', 'action_type_label', 'seuil',
            'approver_tier', 'approver_tier_label', 'enabled', 'note',
            'date_creation', 'date_modification',
        ]
        # company posée côté serveur (TenantMixin) — jamais depuis le corps.
        read_only_fields = ['date_creation', 'date_modification']

    def validate_seuil(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le seuil ne peut pas être négatif.')
        return value
