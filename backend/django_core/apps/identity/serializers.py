"""Sérialiseurs de la fondation Identité & accès."""
from rest_framework import serializers

from .models import IpAllowRule, NetworkPolicy


class IpAllowRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = IpAllowRule
        fields = ['id', 'policy', 'cidr', 'label', 'created_at']
        read_only_fields = ['id', 'created_at']


class NetworkPolicySerializer(serializers.ModelSerializer):
    rules = IpAllowRuleSerializer(many=True, read_only=True)

    class Meta:
        model = NetworkPolicy
        fields = ['id', 'mode', 'applies_to', 'rules', 'created_at',
                  'updated_at']
        read_only_fields = ['id', 'rules', 'created_at', 'updated_at']
