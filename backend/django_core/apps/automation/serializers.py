from rest_framework import serializers

from .models import (
    ApprovalRequest, ApprovalRequestType, AutomationApproval, AutomationRule,
    AutomationRun,
)


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


class ApprovalRequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRequestType
        # `company` posée côté serveur (TenantMixin) — jamais lue du corps.
        fields = [
            'id', 'nom', 'description', 'enabled',
            'champs_requis', 'champs_optionnels', 'palier_approbateur',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


class ApprovalRequestSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    request_type_nom = serializers.CharField(
        source='request_type.nom', read_only=True, default=None)
    demandeur_nom = serializers.CharField(
        source='demandeur.username', read_only=True, default=None)
    decided_by_nom = serializers.CharField(
        source='decided_by.username', read_only=True, default=None)

    class Meta:
        model = ApprovalRequest
        fields = [
            'id', 'request_type', 'request_type_nom', 'demandeur',
            'demandeur_nom', 'payload', 'status', 'status_display',
            'decided_by', 'decided_by_nom', 'decided_at', 'decision_note',
            'date_creation',
        ]
        # `company` + `demandeur` posés côté serveur ; le statut/décision ne
        # se change QUE via les actions dédiées (approve/reject), jamais par
        # un PATCH direct du champ.
        read_only_fields = [
            'id', 'request_type_nom', 'demandeur', 'demandeur_nom', 'status',
            'status_display', 'decided_by', 'decided_by_nom', 'decided_at',
            'decision_note', 'date_creation',
        ]
