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

    @staticmethod
    def _valider_code(value):
        """WIR11 — refuse un code de permission absent de `roles.ALL_PERMISSIONS`.

        Une règle SoD posée sur un code inexistant ne matcherait jamais (SoD
        silencieusement inerte) ; on la rejette à l'écriture (400 FR)."""
        # Import local du catalogue foundation (roles) — pas de couplage import.
        from apps.roles.models import ALL_PERMISSIONS
        if value not in set(ALL_PERMISSIONS):
            raise serializers.ValidationError(
                "Code de permission inconnu : « %s ». Il doit figurer dans le "
                "catalogue des permissions (roles.ALL_PERMISSIONS)." % value)
        return value

    def validate_permission_a(self, value):
        return self._valider_code(value)

    def validate_permission_b(self, value):
        return self._valider_code(value)
