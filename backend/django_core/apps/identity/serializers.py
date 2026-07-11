"""Sérialiseurs de la fondation identité (NTSEC)."""
from rest_framework import serializers

from .models import IdentityProvider


class IdentityProviderSerializer(serializers.ModelSerializer):
    """Sérialise un ``IdentityProvider``.

    ``company`` n'est JAMAIS accepté depuis le corps (forcé côté serveur dans
    ``perform_create`` / filtrage du queryset). ``client_secret`` est
    write-only : jamais renvoyé dans une réponse.
    """

    class Meta:
        model = IdentityProvider
        fields = [
            'id', 'protocol', 'nom', 'actif',
            'metadata_url', 'metadata_xml', 'entity_id', 'sso_url', 'x509_cert',
            'client_id', 'client_secret', 'attribute_map',
            'auto_provision', 'default_role', 'enforce_sso',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            # Le secret client OIDC ne doit jamais ressortir dans une réponse.
            'client_secret': {'write_only': True},
        }

    def validate_attribute_map(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'La carte d\'attributs doit être un objet clé→valeur.')
        return value

    def validate_default_role(self, value):
        """``default_role`` doit appartenir à la société de l'appelant."""
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Ce rôle n'appartient pas à votre société.")
        return value
