"""Sérialiseurs de la gouvernance des accès (NTSEC19/20)."""
import re

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.roles.permissions_registre import ALL_PERMISSIONS
from core.mixins import SameCompanyFKSerializerMixin

from .models import AccessReviewCampaign, AccessReviewItem, SodRule


@extend_schema_field({
    'type': 'string',
    'pattern': '^(?:%s)$' % '|'.join(re.escape(c) for c in ALL_PERMISSIONS)})
class PermissionCodeField(serializers.CharField):
    """Code de permission du catalogue ``roles.ALL_PERMISSIONS`` (ENF10 :
    le schéma déclare l'énum que ``_valider_code`` impose côté serveur)."""


class AccessReviewItemSerializer(SameCompanyFKSerializerMixin,
                                 serializers.ModelSerializer):
    # ENF17 — campagne / compte d'une AUTRE société = id absent (400).
    same_company_fields = ('campagne', 'user')

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
    permission_a = PermissionCodeField(max_length=100)
    permission_b = PermissionCodeField(max_length=100)

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
        from apps.roles.permissions_registre import ALL_PERMISSIONS
        if value not in set(ALL_PERMISSIONS):
            raise serializers.ValidationError(
                "Code de permission inconnu : « %s ». Il doit figurer dans le "
                "catalogue des permissions (roles.ALL_PERMISSIONS)." % value)
        return value

    def validate_permission_a(self, value):
        return self._valider_code(value)

    def validate_permission_b(self, value):
        return self._valider_code(value)
