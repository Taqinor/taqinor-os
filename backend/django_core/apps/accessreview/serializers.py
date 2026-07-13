"""Sérialiseurs de la gouvernance des accès (NTSEC19/20)."""
from rest_framework import serializers

from .models import AccessReviewCampaign, AccessReviewItem, SodRule


class AccessReviewItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessReviewItem
        fields = [
            'id', 'campagne', 'user', 'role_snapshot', 'reviewer',
            'decision', 'commentaire', 'decided_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'role_snapshot', 'reviewer', 'decided_at', 'created_at']


class AccessReviewCampaignSerializer(serializers.ModelSerializer):
    items = AccessReviewItemSerializer(many=True, read_only=True)

    class Meta:
        model = AccessReviewCampaign
        fields = [
            'id', 'nom', 'perimetre', 'perimetre_ref', 'date_debut',
            'date_fin', 'statut', 'items', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'items', 'created_at', 'updated_at']


class SodRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SodRule
        fields = [
            'id', 'permission_a', 'permission_b', 'severite', 'libelle',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
