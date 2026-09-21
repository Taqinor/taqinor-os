"""Sérialiseurs du vertical Agriculture.

``company`` est TOUJOURS en lecture seule (posé côté serveur par le
viewset, jamais lu du corps de requête — CLAUDE.md multi-tenant). Toute
relation vers un autre objet scopé société de cette app (exploitation,
parcelle, campagne, intrant, équipe) est vérifiée appartenir à la MÊME
société que l'appelant — sinon un id d'une autre société laisserait fuir de
la donnée cross-tenant via une relation."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F
from rest_framework import serializers

from .models import (
    CampagneCulturale, EquipeSaisonniere, EtapeCampagne, Exploitation,
    IntrantAgricole, LotRecolte, MaterielAgricole, Parcelle, PointageAgricole,
    PointIrrigation, RelevePointIrrigation, UtilisationMateriel,
    check_dar_guard,
)


def _company(serializer):
    request = serializer.context.get('request')
    user = getattr(request, 'user', None)
    return getattr(user, 'company', None)


def _check_same_company(serializer, obj, field_label):
    if obj is None:
        return
    company = _company(serializer)
    if company is not None and obj.company_id != company.id:
        raise serializers.ValidationError(
            {field_label: f"{field_label} introuvable pour votre société."})


class ExploitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exploitation
        fields = [
            'id', 'company', 'nom', 'adresse', 'superficie_totale_ha',
            'responsable_id', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']


class ParcelleSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = Parcelle
        fields = [
            'id', 'company', 'exploitation', 'nom', 'code', 'superficie_ha',
            'geometrie_gps', 'culture_principale', 'type_sol', 'statut',
            'statut_display', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def validate_exploitation(self, value):
        _check_same_company(self, value, 'exploitation')
        return value


class CampagneCulturaleSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = CampagneCulturale
        fields = [
            'id', 'company', 'parcelle', 'culture', 'variete', 'date_semis',
            'date_recolte_prevue', 'date_recolte_reelle', 'statut',
            'statut_display', 'rendement_prevu_qtl_ha', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def validate_parcelle(self, value):
        _check_same_company(self, value, 'parcelle')
        return value

    def validate(self, attrs):
        statut = attrs.get('statut', getattr(self.instance, 'statut', None))
        parcelle = attrs.get('parcelle', getattr(self.instance, 'parcelle', None))
        if statut == CampagneCulturale.Statut.EN_COURS and parcelle is not None:
            qs = CampagneCulturale.objects.filter(
                parcelle=parcelle, statut=CampagneCulturale.Statut.EN_COURS)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'statut': (
                        "Cette parcelle a déjà une campagne 'en_cours' — "
                        'clôturez-la ou récoltez-la avant d’en démarrer une '
                        'nouvelle.'),
                })
        return attrs


class EtapeCampagneSerializer(serializers.ModelSerializer):
    type_etape_display = serializers.CharField(
        source='get_type_etape_display', read_only=True)

    class Meta:
        model = EtapeCampagne
        fields = [
            'id', 'company', 'campagne', 'type_etape', 'type_etape_display',
            'date', 'description', 'cout_mad', 'intrant', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def validate_campagne(self, value):
        _check_same_company(self, value, 'campagne')
        return value

    def validate_intrant(self, value):
        _check_same_company(self, value, 'intrant')
        return value

    def validate(self, attrs):
        type_etape = attrs.get('type_etape', getattr(self.instance, 'type_etape', None))
        date = attrs.get('date', getattr(self.instance, 'date', None))
        intrant = attrs.get('intrant', getattr(self.instance, 'intrant', None))
        campagne = attrs.get('campagne', getattr(self.instance, 'campagne', None))
        if campagne is not None:
            try:
                check_dar_guard(
                    type_etape=type_etape, date=date, intrant=intrant,
                    campagne=campagne)
            except DjangoValidationError as exc:
                message = exc.messages[0] if exc.messages else str(exc)
                raise serializers.ValidationError({'date': message})
        return attrs


class IntrantAgricoleSerializer(serializers.ModelSerializer):
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    produit_nom = serializers.SerializerMethodField()

    class Meta:
        model = IntrantAgricole
        fields = [
            'id', 'company', 'produit_id', 'produit_nom', 'categorie',
            'categorie_display', 'dose_reference_par_ha',
            'delai_avant_recolte_jours', 'matiere_active', 'numero_amm',
            'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def get_produit_nom(self, obj):
        from apps.stock.selectors import get_produit_scoped
        company = _company(self)
        produit = get_produit_scoped(company, obj.produit_id) if company else None
        return produit.nom if produit else None

    def validate_produit_id(self, value):
        # NTAGR5 — le produit stock doit exister et appartenir à la même
        # société. Lu EXCLUSIVEMENT via apps.stock.selectors (jamais un
        # import de apps.stock.models).
        from apps.stock.selectors import get_produit_scoped
        company = _company(self)
        if company is not None and get_produit_scoped(company, value) is None:
            raise serializers.ValidationError(
                'Aucun produit stock avec cet id pour votre société.')
        return value


class EquipeSaisonniereSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipeSaisonniere
        fields = ['id', 'company', 'nom', 'chef_equipe_id', 'date_creation']
        read_only_fields = ['id', 'company', 'date_creation']


class PointageAgricoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointageAgricole
        fields = [
            'id', 'company', 'equipe', 'travailleur_nom', 'campagne',
            'parcelle', 'date', 'tache', 'nombre_journees',
            'taux_journalier_mad', 'employe_id', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def validate_equipe(self, value):
        _check_same_company(self, value, 'equipe')
        return value

    def validate_campagne(self, value):
        _check_same_company(self, value, 'campagne')
        return value

    def validate_parcelle(self, value):
        _check_same_company(self, value, 'parcelle')
        return value

    def validate(self, attrs):
        equipe = attrs.get('equipe', getattr(self.instance, 'equipe', None))
        travailleur_nom = attrs.get(
            'travailleur_nom', getattr(self.instance, 'travailleur_nom', ''))
        if not equipe and not travailleur_nom:
            raise serializers.ValidationError(
                'Renseignez une équipe ou un nom de travailleur libre.')
        return attrs


class MaterielAgricoleSerializer(serializers.ModelSerializer):
    type_materiel_display = serializers.CharField(
        source='get_type_materiel_display', read_only=True)

    class Meta:
        model = MaterielAgricole
        fields = [
            'id', 'company', 'nom', 'type_materiel', 'type_materiel_display',
            'numero_serie', 'heures_moteur', 'parcelle_affectee',
            'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def validate_parcelle_affectee(self, value):
        _check_same_company(self, value, 'parcelle_affectee')
        return value


class UtilisationMaterielSerializer(serializers.ModelSerializer):
    class Meta:
        model = UtilisationMateriel
        fields = [
            'id', 'company', 'materiel', 'campagne', 'date',
            'heures_utilisees', 'cout_carburant_mad', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def validate_materiel(self, value):
        _check_same_company(self, value, 'materiel')
        return value

    def validate_campagne(self, value):
        _check_same_company(self, value, 'campagne')
        return value

    def create(self, validated_data):
        # NTAGR11 — chaque utilisation incrémente ATOMIQUEMENT (F()) les
        # heures moteur cumulées du matériel — jamais une lecture-puis-
        # écriture qui perdrait des mises à jour concurrentes.
        utilisation = super().create(validated_data)
        MaterielAgricole.objects.filter(pk=utilisation.materiel_id).update(
            heures_moteur=F('heures_moteur') + utilisation.heures_utilisees)
        utilisation.materiel.refresh_from_db(fields=['heures_moteur'])
        return utilisation


class PointIrrigationSerializer(serializers.ModelSerializer):
    type_source_display = serializers.CharField(
        source='get_type_source_display', read_only=True)

    class Meta:
        model = PointIrrigation
        fields = [
            'id', 'company', 'parcelle', 'type_source', 'type_source_display',
            'installation_id', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def validate_parcelle(self, value):
        _check_same_company(self, value, 'parcelle')
        return value

    def validate_installation_id(self, value):
        # NTAGR13 — l'installation (pompage solaire) doit exister et
        # appartenir à la même société. Lue EXCLUSIVEMENT via
        # apps.installations.selectors (jamais un import de modèle).
        if value is None:
            return value
        from apps.installations.selectors import installation_scoped
        company = _company(self)
        if company is not None and installation_scoped(company, value) is None:
            raise serializers.ValidationError(
                'Aucune installation avec cet id pour votre société.')
        return value


class RelevePointIrrigationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelevePointIrrigation
        fields = [
            'id', 'company', 'point', 'date', 'volume_m3',
            'cout_energie_mad', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def validate_point(self, value):
        _check_same_company(self, value, 'point')
        return value


class LotRecolteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LotRecolte
        fields = [
            'id', 'company', 'campagne', 'date_recolte', 'quantite_qtl',
            'calibre', 'qualite', 'numero_lot', 'stock_lot_id',
            'date_creation',
        ]
        read_only_fields = ['id', 'company', 'numero_lot', 'date_creation']

    def validate_campagne(self, value):
        _check_same_company(self, value, 'campagne')
        return value

    def create(self, validated_data):
        # NTAGR15 — numérotation race-safe via core.numbering, jamais un
        # ModelSerializer.create() nu (qui laisserait numero_lot vide).
        # ``company`` est déjà dans ``validated_data`` : le viewset l'injecte
        # via ``serializer.save(company=...)`` (TenantMixin.perform_create).
        from .services import creer_lot_recolte

        return creer_lot_recolte(**validated_data)
