from rest_framework import serializers

from .models import AutomationApproval, AutomationRule, AutomationRun


class AutomationRuleSerializer(serializers.ModelSerializer):
    trigger_type_display = serializers.CharField(
        source='get_trigger_type_display', read_only=True)
    action_type_display = serializers.CharField(
        source='get_action_type_display', read_only=True)

    class Meta:
        model = AutomationRule
        # `company` posée côté serveur (TenantMixin) — jamais lue du corps.
        fields = [
            'id', 'nom', 'enabled',
            'trigger_type', 'trigger_type_display', 'trigger_config',
            'action_type', 'action_type_display', 'action_config',
            'requires_approval', 'approval_threshold', 'ordre',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


class AutomationRunSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    rule_nom = serializers.CharField(
        source='rule.nom', read_only=True, default=None)

    class Meta:
        model = AutomationRun
        fields = [
            'id', 'rule', 'rule_nom', 'target_model', 'target_id',
            'status', 'status_display', 'message', 'timestamp',
        ]
        read_only_fields = fields


class AutomationApprovalSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    rule_nom = serializers.CharField(
        source='rule.nom', read_only=True, default=None)
    requested_by_nom = serializers.CharField(
        source='requested_by.username', read_only=True, default=None)
    decided_by_nom = serializers.CharField(
        source='decided_by.username', read_only=True, default=None)

    class Meta:
        model = AutomationApproval
        fields = [
            'id', 'rule', 'rule_nom', 'target_model', 'target_id',
            'description', 'context', 'status', 'status_display',
            'requested_by', 'requested_by_nom',
            'decided_by', 'decided_by_nom', 'decided_at', 'date_creation',
        ]
        read_only_fields = fields
