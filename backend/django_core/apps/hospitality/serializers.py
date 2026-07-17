"""Sérialiseurs du module Hôtellerie & restauration.

``company`` n'est JAMAIS exposée en écriture : posée côté serveur par le
``TenantMixin`` (``perform_create``/``perform_update``).
"""
from rest_framework import serializers

from .models import (
    Chambre, FicheClient, Folio, LigneFolio, PlanTarifaire, Reservation,
    TacheMenage, TypeChambre,
)


def _company(serializer):
    request = serializer.context.get('request')
    user = getattr(request, 'user', None)
    return getattr(user, 'company', None)


def _check_same_company(serializer, obj, field_label):
    """Refuse une FK pointant vers une ligne d'une AUTRE société — sans quoi le
    queryset non scopé de DRF laisserait un id étranger référencer/écrire de la
    donnée cross-tenant (même garde que ``apps.agriculture``)."""
    if obj is None:
        return
    company = _company(serializer)
    if company is not None and obj.company_id != company.id:
        raise serializers.ValidationError(
            {field_label: f"{field_label} introuvable pour votre société."})


class TypeChambreSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeChambre
        fields = ['id', 'libelle', 'capacite_max', 'description']


class ChambreSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_chambre_libelle = serializers.CharField(
        source='type_chambre.libelle', read_only=True)

    class Meta:
        model = Chambre
        fields = [
            'id', 'type_chambre', 'type_chambre_libelle', 'numero', 'nom',
            'etage', 'statut', 'statut_display', 'vue',
        ]
        # NTHOT1 — une chambre créée sans statut explicite obtient LIBRE par
        # défaut (valeur du modèle) ; le statut évolue ensuite via les
        # actions du cycle de vie (check-in/check-out/housekeeping).
        extra_kwargs = {'statut': {'required': False}}


class PlanTarifaireSerializer(serializers.ModelSerializer):
    canal_display = serializers.CharField(
        source='get_canal_display', read_only=True)

    class Meta:
        model = PlanTarifaire
        fields = [
            'id', 'type_chambre', 'canal', 'canal_display', 'date_debut',
            'date_fin', 'prix_nuit_ht', 'min_nuits',
        ]

    def validate_type_chambre(self, value):
        _check_same_company(self, value, 'type_chambre')
        return value

    def validate(self, attrs):
        date_debut = attrs.get(
            'date_debut', getattr(self.instance, 'date_debut', None))
        date_fin = attrs.get(
            'date_fin', getattr(self.instance, 'date_fin', None))
        if date_debut and date_fin and date_fin < date_debut:
            raise serializers.ValidationError(
                {'date_fin': 'La date de fin doit être postérieure à la date de début.'})
        return attrs


class ReservationSerializer(serializers.ModelSerializer):
    """Création/édition de réservation.

    ``company``/``statut``/``prix_nuit_snapshot`` sont posés côté serveur
    (jamais lus du corps) : le statut suit le cycle de vie (check-in/check-out/
    annulation), le prix est figé via ``services.prix_applicable`` à la
    création. La validation de chevauchement (``services.check_reservation_
    overlap``) est appliquée par le viewset (``services.creer_reservation``),
    pas ici, pour renvoyer un message métier clair plutôt qu'une erreur de
    champ générique.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    origine_display = serializers.CharField(
        source='get_origine_display', read_only=True)
    # ``client_id`` en écriture (résolution côté service) ; ``client`` reste
    # exposé en LECTURE seule (le FK effectivement retenu après résolution).
    client_id = serializers.IntegerField(
        required=False, allow_null=True, write_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id', 'chambre', 'type_chambre', 'origine', 'origine_display',
            'date_arrivee', 'date_depart', 'nb_adultes', 'nb_enfants',
            'client', 'client_id', 'client_nom', 'client_telephone',
            'statut', 'statut_display', 'prix_nuit_snapshot', 'date_creation',
        ]
        read_only_fields = [
            'client', 'statut', 'prix_nuit_snapshot', 'date_creation']

    def validate_chambre(self, value):
        _check_same_company(self, value, 'chambre')
        return value

    def validate_type_chambre(self, value):
        _check_same_company(self, value, 'type_chambre')
        return value


class FicheClientSerializer(serializers.ModelSerializer):
    type_piece_display = serializers.CharField(
        source='get_type_piece_display', read_only=True)

    class Meta:
        model = FicheClient
        fields = [
            'id', 'reservation', 'nom_complet', 'nationalite', 'type_piece',
            'type_piece_display', 'numero_piece', 'date_naissance',
            'date_creation',
        ]
        read_only_fields = ['reservation', 'date_creation']


class LigneFolioSerializer(serializers.ModelSerializer):
    origine_display = serializers.CharField(
        source='get_origine_display', read_only=True)

    class Meta:
        model = LigneFolio
        fields = [
            'id', 'origine', 'origine_display', 'description', 'montant_ht',
            'tva', 'source_type', 'source_id', 'date_creation',
        ]


class FolioSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    lignes = LigneFolioSerializer(many=True, read_only=True)
    total_ht = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Folio
        fields = [
            'id', 'reservation', 'statut', 'statut_display', 'facture_id',
            'lignes', 'total_ht', 'date_creation', 'date_cloture',
        ]
        read_only_fields = fields


class TacheMenageSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_tache_display = serializers.CharField(
        source='get_type_tache_display', read_only=True)
    chambre_numero = serializers.CharField(
        source='chambre.numero', read_only=True)

    class Meta:
        model = TacheMenage
        fields = [
            'id', 'chambre', 'chambre_numero', 'type_tache',
            'type_tache_display', 'assignee', 'statut', 'statut_display',
            'date_creation', 'date_completion',
        ]
        read_only_fields = ['statut', 'date_creation', 'date_completion']

    def validate_chambre(self, value):
        _check_same_company(self, value, 'chambre')
        return value
