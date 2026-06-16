"""Mixin de sérialiseur pour exposer/valider le JSONField `custom_fields` d'un
modèle cible (crm.Lead / crm.Client / stock.Produit) selon les définitions de
champs personnalisés de la société.

Usage :
    class LeadSerializer(CustomFieldsSerializerMixin, ModelSerializer):
        custom_fields_module = 'lead'
        ...
"""
from rest_framework import serializers

from .services import validate_custom_fields, read_custom_fields


class CustomFieldsSerializerMixin:
    # À surcharger : 'lead' | 'client' | 'produit'.
    custom_fields_module = None

    def _cf_company(self):
        request = self.context.get('request')
        return getattr(getattr(request, 'user', None), 'company', None)

    def validate_custom_fields(self, value):
        """Valide les valeurs entrantes contre les définitions actives.

        Lève une erreur DRF (mappée par champ) si type/obligatoire/choix
        invalide. Le PATCH partiel ne fusionne que les clés fournies.
        """
        company = self._cf_company()
        module = self.custom_fields_module
        if company is None or module is None:
            return value or {}
        existing = {}
        if self.instance is not None:
            existing = getattr(self.instance, 'custom_fields', None) or {}
        partial = bool(getattr(self, 'partial', False))
        try:
            return validate_custom_fields(
                company, module, value, existing=existing, partial=partial)
        except ValueError as exc:
            detail = exc.args[0] if exc.args else str(exc)
            raise serializers.ValidationError(detail)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        company = self._cf_company()
        module = self.custom_fields_module
        if company is not None and module is not None:
            data['custom_fields'] = read_custom_fields(
                company, module, getattr(instance, 'custom_fields', None))
        return data
