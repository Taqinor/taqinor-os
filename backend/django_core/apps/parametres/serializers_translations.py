"""N94 — sérialiseur des surcharges de traduction (``TranslationOverride``)."""
from rest_framework import serializers

from .models_translations import TranslationOverride

VALID_LOCALES = {c for c, _ in TranslationOverride.Locale.choices}


class TranslationOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranslationOverride
        fields = [
            'id', 'locale', 'key', 'value', 'date_modification',
        ]
        # company posée côté serveur (TenantMixin) — jamais depuis le corps.
        read_only_fields = ['date_modification']

    def validate_locale(self, value):
        if value not in VALID_LOCALES:
            raise serializers.ValidationError('Langue inconnue (fr, en, ar).')
        return value

    def validate_key(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Clé i18n requise.')
        return value
