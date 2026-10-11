from django.utils import timezone
from rest_framework import serializers

from .models import (
    AbonnementMonitoring, CertificatCarbone, CleaningEvent, MonitoringConfig,
    MonitoringSettings, ProductionReading, ProductionWarranty,
    SlaDisponibilite,
)
from .providers import available_providers


class MonitoringConfigSerializer(serializers.ModelSerializer):
    provider_label = serializers.SerializerMethodField()
    is_auto = serializers.BooleanField(read_only=True)
    # has_credentials expose seulement la PRÉSENCE d'identifiants (jamais leur
    # contenu côté client) ; `credentials` est write-only.
    has_credentials = serializers.SerializerMethodField()
    # ASAV71 — colonne chiffrée (sous-classe de TextField) : champ JSON
    # déclaré explicitement, write-only, jamais relu par l'API.
    credentials = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = MonitoringConfig
        fields = [
            'id', 'installation', 'provider', 'provider_label', 'enabled',
            'credentials', 'has_credentials', 'expected_annual_kwh',
            'is_auto', 'last_sync', 'date_modification',
        ]
        # `company` posée côté serveur ; identifiants jamais relus du serveur.
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

    def validate_period_days(self, value):
        # ASAV66 — un relevé couvre au moins un jour.
        if value is None or value < 1:
            raise serializers.ValidationError(
                'La période doit couvrir au moins 1 jour.')
        return value

    def validate(self, attrs):
        """ASAV66 — pas de relevé dans le futur, et un seul relevé par
        (système, date, période), TOUTES sources (un double clic ou une saisie
        après import CSV ne compte plus la production deux fois)."""
        attrs = super().validate(attrs)
        instance = self.instance
        jour = attrs.get('date', getattr(instance, 'date', None))
        periode = attrs.get(
            'period_days', getattr(instance, 'period_days', None))
        installation = attrs.get(
            'installation', getattr(instance, 'installation', None))
        if jour is not None and jour > timezone.localdate():
            raise serializers.ValidationError(
                {'date': 'La date du relevé ne peut pas être dans le futur.'})
        if jour is not None and periode is not None and installation:
            doublons = ProductionReading.objects.filter(
                installation=installation, date=jour, period_days=periode)
            if instance is not None:
                doublons = doublons.exclude(pk=instance.pk)
            if doublons.exists():
                raise serializers.ValidationError(
                    {'date': 'Relevé déjà saisi pour cette période.'})
        return attrs


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


class AbonnementMonitoringSerializer(serializers.ModelSerializer):
    """ASAV100 — abonnement de supervision. ``client_id`` est résolu côté
    serveur depuis le système (lecture seule) ; statut, motif et échéance ne
    bougent que par les services (création, résiliation)."""
    periodicite_display = serializers.CharField(
        source='get_periodicite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    installation_id = serializers.IntegerField(min_value=1)
    # Aucun chiffre inventé : le montant est obligatoire à la saisie.
    montant = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=True)

    class Meta:
        model = AbonnementMonitoring
        fields = [
            'id', 'client_id', 'installation_id', 'periodicite',
            'periodicite_display', 'montant', 'statut', 'statut_display',
            'date_debut', 'prochaine_echeance', 'motif_resiliation',
            'date_creation',
        ]
        read_only_fields = [
            'client_id', 'statut', 'prochaine_echeance', 'motif_resiliation',
            'date_creation',
        ]


class SlaDisponibiliteSerializer(serializers.ModelSerializer):
    """ASAV101 — SLA de disponibilité d'un système. Le taux garanti est SAISI
    (aucun défaut, CIQ644) ; la compensation par jour vient de la saisie
    (0 = aucune compensation chiffrée). ``company`` posée côté serveur."""

    class Meta:
        model = SlaDisponibilite
        fields = [
            'id', 'installation', 'disponibilite_garantie_pct',
            'compensation_mad_par_jour_indispo', 'note', 'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {'disponibilite_garantie_pct': {
            'required': True, 'allow_null': False}}

    def validate_installation(self, value):
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Système inconnu.')
        return value

    def validate_disponibilite_garantie_pct(self, value):
        if value is None or value <= 0 or value > 100:
            raise serializers.ValidationError('Saisir le taux garanti.')
        return value

    def validate_compensation_mad_par_jour_indispo(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Compensation invalide.')
        return value


class CertificatCarboneSerializer(serializers.ModelSerializer):
    """ASAV102 — certificat du registre carbone. Entrée : la cible
    (``installation_id`` OU ``client_id``) et la période ; ``tco2_evitees`` et
    ``reference`` sont posées par le serveur (calcul mesuré, numérotation
    race-safe). ``fichier_key`` (clé de stockage interne) n'est jamais servi."""
    installation_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True)
    client_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True)

    class Meta:
        model = CertificatCarbone
        fields = [
            'id', 'installation_id', 'client_id', 'periode_debut',
            'periode_fin', 'tco2_evitees', 'reference', 'created_at',
        ]
        read_only_fields = ['tco2_evitees', 'reference', 'created_at']
