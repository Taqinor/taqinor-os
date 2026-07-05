from rest_framework import serializers

from .models import (
    CleaningEvent, MonitoringConfig, MonitoringSettings, ProductionReading,
    ProductionWarranty,
)
from .providers import available_providers

# ODX16 — ré-export TRANSITOIRE du serializer d'``AbonnementMonitoring`` qui vit
# encore dans ``apps.compta.serializers`` (interleavé avec les serializers
# comptables, adossé à la logique de facturation compta/ventes). Ce ré-export
# donne à la nouvelle route ``/api/django/monitoring/abonnements-monitoring/`` un
# point d'entrée stable ; ODX22 re-logera le corps ici.
from apps.compta.serializers import (  # noqa: E402,F401
    AbonnementMonitoringSerializer,
)


class MonitoringConfigSerializer(serializers.ModelSerializer):
    provider_label = serializers.SerializerMethodField()
    is_auto = serializers.BooleanField(read_only=True)
    # has_credentials expose seulement la PRÉSENCE d'identifiants (jamais leur
    # contenu côté client) ; `credentials` est write-only.
    has_credentials = serializers.SerializerMethodField()

    class Meta:
        model = MonitoringConfig
        fields = [
            'id', 'installation', 'provider', 'provider_label', 'enabled',
            'credentials', 'has_credentials', 'expected_annual_kwh',
            'is_auto', 'last_sync', 'date_modification',
        ]
        # `company` posée côté serveur ; identifiants jamais relus du serveur.
        extra_kwargs = {'credentials': {'write_only': True, 'required': False}}
        read_only_fields = ['last_sync', 'date_modification']

    def get_provider_label(self, obj):
        return dict(available_providers()).get(obj.provider, obj.provider)

    def get_has_credentials(self, obj):
        return bool(obj.credentials)

    def validate_installation(self, value):
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Système inconnu.')
        return value


class ProductionReadingSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(
        source='get_source_display', read_only=True)

    class Meta:
        model = ProductionReading
        fields = [
            'id', 'installation', 'date', 'period_days', 'energy_kwh',
            'source', 'source_display', 'external_id', 'note', 'date_creation',
        ]
        # `company`, `created_by`, `source`='manual' et `external_id` posés
        # côté serveur pour la saisie manuelle — jamais lus du corps.
        read_only_fields = ['source', 'external_id', 'date_creation']

    def validate_installation(self, value):
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Système inconnu.')
        return value

    def validate_energy_kwh(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError('Énergie invalide.')
        return value


class CleaningEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CleaningEvent
        fields = [
            'id', 'installation', 'date', 'note', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_installation(self, value):
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Système inconnu.')
        return value


class ProductionWarrantySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionWarranty
        fields = [
            'id', 'installation', 'guaranteed_year1_kwh',
            'degradation_pct_per_year', 'start_year',
            'compensation_mad_per_kwh', 'tolerance_pct', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_installation(self, value):
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Système inconnu.')
        return value


class MonitoringSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringSettings
        fields = [
            'id', 'underperf_threshold_pct', 'auto_create_ticket',
            'date_modification',
        ]
        read_only_fields = ['date_modification']
