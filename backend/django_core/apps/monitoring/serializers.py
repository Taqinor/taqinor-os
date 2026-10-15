from django.utils import timezone
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from apps.records.champs_stricts import (
    ChampsStrictsBornesMixin, ChampsStrictsLitterauxMixin, DecimalLitteral,
)

from core.champs_stricts import DecimalStricte, IdInconnu404Mixin
from core.serializers import CompanyScopedRelationsMixin
from core.conflit_etat import ConflitEtat
from core.unicite import UniciteEn409Mixin

from .models import (
    AbonnementMonitoring, CertificatCarbone, CleaningEvent, MonitoringConfig,
    MonitoringSettings, ProductionReading, ProductionWarranty,
    SlaDisponibilite,
)
from .providers import available_providers


class MonitoringConfigSerializer(IdInconnu404Mixin, UniciteEn409Mixin, CompanyScopedRelationsMixin,
                                 ChampsStrictsBornesMixin,
                                 serializers.ModelSerializer):
    provider_label = serializers.SerializerMethodField()
    is_auto = serializers.BooleanField(read_only=True)
    # has_credentials expose seulement la PRÉSENCE d'identifiants (jamais leur
    # contenu côté client) ; `credentials` est write-only.
    has_credentials = serializers.SerializerMethodField()
    # ASAV71 — colonne chiffrée (sous-classe de TextField) : champ déclaré
    # explicitement, write-only, jamais relu par l'API. ERR-ENF11-FUZZ-MONITORING
    # — un OBJET (le connecteur lit un dict) : ``null`` ou une liste, publiés
    # valides par un JSON libre, étaient refusés (« Ce champ ne peut être nul »).
    credentials = serializers.DictField(write_only=True, required=False)
    # ENF11 (nocturne 15/10) — « » vaut « non renseigné » : le schéma le publie
    # (anyOf motif | chaîne vide), le champ l'applique (DecimalStricte nullable).
    expected_annual_kwh = DecimalStricte(max_digits=12, decimal_places=2, allow_null=True, required=False)

    class Meta:
        model = MonitoringConfig
        fields = [
            'id', 'installation', 'provider', 'provider_label', 'enabled',
            'credentials', 'has_credentials', 'expected_annual_kwh',
            'is_auto', 'last_sync', 'date_modification',
        ]
        # `company` posée côté serveur ; identifiants jamais relus du serveur.
        read_only_fields = ['last_sync', 'date_modification']

    def get_provider_label(self, obj) -> str:  # ENF11 — type au schéma
        return dict(available_providers()).get(obj.provider, obj.provider)

    # CI #993 — booléen publié (SerializerMethodField sans type = chaîne :
    # `false` servi était « hors schéma » sur configs/ et configs/{id}/).
    @extend_schema_field(serializers.BooleanField())
    def get_has_credentials(self, obj):
        return bool(obj.credentials)

    def validate_installation(self, value):
        request = self.context.get('request')
        if request is not None and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Système inconnu.')
        return value


#: ERR-ENF11-FUZZ-MONITORING — énergie relevée : décimal >= 0, 10 chiffres
#: entiers et 2 décimales au plus (``validate_energy_kwh``, colonne
#: ``numeric(12,2)``) ; le motif générique publiait aussi le signe ``-``.
MOTIF_ENERGIE_KWH = r'^[0-9]{1,10}(?:\.[0-9]{1,2})?$'


@extend_schema_field({'type': 'string', 'format': 'decimal',
                      'pattern': MOTIF_ENERGIE_KWH})
class _EnergieKwh(DecimalLitteral):
    """Énergie relevée (kWh) : chaîne décimale positive ou nulle (un nombre
    JSON est refusé, comme le schéma le dit)."""


class ProductionReadingSerializer(IdInconnu404Mixin, CompanyScopedRelationsMixin, ChampsStrictsBornesMixin,
                                  serializers.ModelSerializer):
    source_display = serializers.CharField(
        source='get_source_display', read_only=True)
    energy_kwh = _EnergieKwh(max_digits=12, decimal_places=2)

    class Meta:
        model = ProductionReading
        fields = [
            'id', 'installation', 'date', 'period_days', 'energy_kwh',
            'source', 'source_display', 'external_id', 'note', 'date_creation',
        ]
        # `company`, `created_by`, `source`='manual' et `external_id` posés
        # côté serveur pour la saisie manuelle — jamais lus du corps.
        read_only_fields = ['source', 'external_id', 'date_creation']
        # Un relevé couvre au moins un jour (``validate_period_days``) : la
        # borne est PUBLIÉE (le schéma annonçait 0).
        extra_kwargs = {'period_days': {'min_value': 1}}

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
        # ERR-ENF11-FUZZ-MONITORING — deux refus qui dépendent de l'HORLOGE et
        # des relevés DÉJÀ saisis (le schéma ne peut les dire) : 409.
        if jour is not None and jour > timezone.localdate():
            raise ConflitEtat(
                {'date': ['La date du relevé ne peut pas être dans le futur.']})
        if jour is not None and periode is not None and installation:
            doublons = ProductionReading.objects.filter(
                installation=installation, date=jour, period_days=periode)
            if instance is not None:
                doublons = doublons.exclude(pk=instance.pk)
            if doublons.exists():
                raise ConflitEtat(
                    {'date': ['Relevé déjà saisi pour cette période.']})
        return attrs


class CleaningEventSerializer(IdInconnu404Mixin, CompanyScopedRelationsMixin, ChampsStrictsBornesMixin,
                              serializers.ModelSerializer):
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


class ProductionWarrantySerializer(IdInconnu404Mixin, UniciteEn409Mixin, CompanyScopedRelationsMixin,
                                   ChampsStrictsLitterauxMixin,
                                   serializers.ModelSerializer):
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


#: ERR-ENF11-FUZZ-MONITORING — la forme que ``DecimalLitteral`` accepte
#: (``-?[0-9]+(.[0-9]+)?``), bornée par le champ (5 chiffres dont 2
#: décimales). Le motif générique publiait aussi ``-.3`` / ``12.``, refusés
#: en 400 (« conforme refusée », PUT settings/{id} du 13/10/2026).
MOTIF_SEUIL_POURCENT = r'^-?0*[0-9]{1,3}(\.[0-9]{1,2})?$'


@extend_schema_field({'type': 'string', 'format': 'decimal',
                      'pattern': MOTIF_SEUIL_POURCENT})
class _SeuilPourcentLitteral(DecimalLitteral):
    """``DecimalLitteral`` dont le motif publié est celui qu'il accepte."""


# ENF11 — `list` renvoie UN objet (singleton société), pas un tableau : sans
# `many=False` drf-spectacular l'enveloppait en tableau (réponse hors schéma).
@extend_schema_serializer(many=False)
class MonitoringSettingsSerializer(ChampsStrictsLitterauxMixin,
                                   serializers.ModelSerializer):
    underperf_threshold_pct = _SeuilPourcentLitteral(
        max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = MonitoringSettings
        fields = [
            'id', 'underperf_threshold_pct', 'auto_create_ticket',
            'date_modification',
        ]
        read_only_fields = ['date_modification']


#: CI #997 fuzz — les décimaux dont le serveur refuse la valeur NULLE ou hors
#: borne la publient dans leur motif (forme littérale ``DecimalLitteral``) :
#: montant d'abonnement STRICTEMENT positif (12 chiffres, 2 décimales), taux de
#: disponibilité garanti dans ]0 ; 100], compensation par jour ≥ 0.
MOTIF_MONTANT_POSITIF = (
    r'^(?:0*[1-9][0-9]{0,9}(?:\.[0-9]{1,2})?|0+\.(?:[1-9][0-9]?|0[1-9]))$')
MOTIF_TAUX_GARANTI = (
    r'^(?:0*[1-9][0-9]?(?:\.[0-9]{1,2})?|0*100(?:\.0{1,2})?'
    r'|0+\.(?:[1-9][0-9]?|0[1-9]))$')
MOTIF_COMPENSATION = r'^[0-9]{1,8}(?:\.[0-9]{1,2})?$'


@extend_schema_field({'type': 'string', 'format': 'decimal',
                      'pattern': MOTIF_MONTANT_POSITIF})
class _MontantPositifLitteral(DecimalLitteral):
    """Montant par période : chaîne décimale > 0."""


@extend_schema_field({'type': 'string', 'format': 'decimal',
                      'pattern': MOTIF_TAUX_GARANTI})
class _TauxGarantiLitteral(DecimalLitteral):
    """Taux de disponibilité garanti : chaîne décimale dans ]0 ; 100]."""


@extend_schema_field({'type': 'string', 'format': 'decimal',
                      'pattern': MOTIF_COMPENSATION})
class _CompensationLitterale(DecimalLitteral):
    """Compensation par jour d'indisponibilité : chaîne décimale ≥ 0."""


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
    montant = _MontantPositifLitteral(
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

    def validate_montant(self, value):
        # La règle est AUSSI publiée dans le motif du champ (corps conforme).
        if value <= 0:
            raise serializers.ValidationError('Saisir le montant par période.')
        return value


class SlaDisponibiliteSerializer(IdInconnu404Mixin, UniciteEn409Mixin, CompanyScopedRelationsMixin,
                                 ChampsStrictsBornesMixin,
                                 serializers.ModelSerializer):
    """ASAV101 — SLA de disponibilité d'un système. Le taux garanti est SAISI
    (aucun défaut, CIQ644) ; la compensation par jour vient de la saisie
    (0 = aucune compensation chiffrée). ``company`` posée côté serveur."""
    disponibilite_garantie_pct = _TauxGarantiLitteral(
        max_digits=5, decimal_places=2)
    compensation_mad_par_jour_indispo = _CompensationLitterale(
        max_digits=10, decimal_places=2, required=False)

    class Meta:
        model = SlaDisponibilite
        fields = [
            'id', 'installation', 'disponibilite_garantie_pct',
            'compensation_mad_par_jour_indispo', 'note', 'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

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
