"""Sérialiseurs de la fondation Identité & accès."""
import ipaddress

from rest_framework import serializers

from .models import IdentityProvider, IpAllowRule, NetworkPolicy, TrustedDevice


class IpAllowRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = IpAllowRule
        fields = ['id', 'policy', 'cidr', 'label', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_cidr(self, value):
        # Valider ICI (DRF → 400) et non seulement dans ``IpAllowRule.clean()``
        # (django ValidationError au save → 500). Normalise aussi la saisie.
        cidr = (value or '').strip()
        try:
            ipaddress.ip_network(cidr, strict=False)
        except (ValueError, AttributeError):
            raise serializers.ValidationError(
                'Plage CIDR invalide (ex. 10.0.0.0/8).')
        return cidr


class NetworkPolicySerializer(serializers.ModelSerializer):
    rules = IpAllowRuleSerializer(many=True, read_only=True)

    class Meta:
        model = NetworkPolicy
        fields = ['id', 'mode', 'applies_to', 'rules', 'created_at',
                  'updated_at']
        read_only_fields = ['id', 'rules', 'created_at', 'updated_at']


class TrustedDeviceSerializer(serializers.ModelSerializer):
    """NTSEC14 — lecture seule : liste des appareils de confiance de l'utilisateur
    (jamais l'empreinte complète, qui vaut un jeton de contournement MFA)."""

    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = TrustedDevice
        fields = ['id', 'label', 'approuve_le', 'expire_le', 'revoque_le',
                  'is_active']
        read_only_fields = fields


class IdentityProviderSerializer(serializers.ModelSerializer):
    """CRUD d'un IdP SSO (NTSEC1). ``company`` forcée côté serveur."""

    class Meta:
        model = IdentityProvider
        fields = [
            'id', 'protocol', 'nom', 'actif', 'metadata_url', 'metadata_xml',
            'entity_id', 'sso_url', 'x509_cert', 'attribute_map',
            'auto_provision', 'default_role_id', 'enforce_sso',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_attribute_map(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Le mapping d\'attributs doit être un objet JSON.')
        return value
