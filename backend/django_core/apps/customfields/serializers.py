from rest_framework import serializers

from .models import (
    CustomFieldDefinition, HiddenStandardField,
    TYPE_CHOICE, FIELD_TYPE_KEYS, MODULE_KEYS,
)
from .services import derive_field_key


class _CurrentCompanyDefault:
    """Société du user courant, injectée CÔTÉ SERVEUR (jamais lue du corps)."""
    requires_context = True

    def __call__(self, serializer_field):
        return serializer_field.context['request'].user.company


class CustomFieldDefinitionSerializer(serializers.ModelSerializer):
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    # field_key est dérivé côté serveur ; jamais accepté du corps.
    field_key = serializers.SlugField(read_only=True)

    class Meta:
        model = CustomFieldDefinition
        fields = [
            'id', 'company', 'module', 'field_key', 'label', 'field_type',
            'choices', 'required', 'order', 'show_in_list', 'show_in_filter',
            'active', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_module(self, value):
        if value not in MODULE_KEYS:
            raise serializers.ValidationError('Module non supporté.')
        return value

    def validate_field_type(self, value):
        if value not in FIELD_TYPE_KEYS:
            raise serializers.ValidationError('Type de champ non supporté.')
        return value

    def validate(self, attrs):
        field_type = attrs.get('field_type', getattr(self.instance, 'field_type', None))
        choices = attrs.get('choices', getattr(self.instance, 'choices', None))
        if field_type == TYPE_CHOICE:
            if not isinstance(choices, list) or not [c for c in choices if str(c).strip()]:
                raise serializers.ValidationError(
                    {'choices': 'Une liste de choix non vide est requise.'})
            # Normalise : chaînes non vides, sans doublon, ordre préservé.
            seen, clean = set(), []
            for c in choices:
                s = str(c).strip()
                if s and s not in seen:
                    seen.add(s)
                    clean.append(s)
            attrs['choices'] = clean
        else:
            attrs['choices'] = []
        return attrs

    def create(self, validated_data):
        company = validated_data['company']
        module = validated_data['module']
        validated_data['field_key'] = derive_field_key(
            validated_data['label'], company, module)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Le module et la clé restent stables après création (évite d'orphaner
        # les valeurs déjà saisies). On ignore tout module entrant divergent.
        validated_data.pop('module', None)
        return super().update(instance, validated_data)


class HiddenStandardFieldSerializer(serializers.ModelSerializer):
    company = serializers.HiddenField(default=_CurrentCompanyDefault())

    class Meta:
        model = HiddenStandardField
        fields = ['id', 'company', 'module', 'field_key', 'date_creation']
        read_only_fields = ['date_creation']

    def validate_module(self, value):
        if value not in MODULE_KEYS:
            raise serializers.ValidationError('Module non supporté.')
        return value
