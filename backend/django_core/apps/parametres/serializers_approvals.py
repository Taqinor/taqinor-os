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

    def validate(self, attrs):
        # Unicité (company, action_type) validée ici → 400 propre plutôt qu'une
        # IntegrityError 500 au save. company est dérivée du serveur (TenantMixin).
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        action_type = attrs.get(
            'action_type', getattr(self.instance, 'action_type', None))
        if company is not None and action_type is not None:
            qs = ApprovalPolicy.objects.filter(
                company=company, action_type=action_type)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'action_type':
                        'Une politique existe déjà pour cette action.'})
        return attrs
