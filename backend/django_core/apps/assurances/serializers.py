"""Serializers du registre des assurances & sinistres d'entreprise (NTASS)."""
from rest_framework import serializers

from .models import (
    ActifCouvert, AttestationAssurance, Assureur, Courtier, DeclarationSinistre,
    EcheancePrime, ExigenceAssuranceMarche, GarantiePolice,
    IndemnisationSinistre, PoliceActivity, PoliceAssurance, SinistreActivity,
)
from .selectors import resoudre_libelle_actif


class AssureurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assureur
        fields = [
            'id', 'company', 'raison_sociale', 'ice', 'telephone', 'email',
            'adresse', 'actif',
        ]
        read_only_fields = ['id', 'company']


class CourtierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Courtier
        fields = [
            'id', 'company', 'raison_sociale', 'numero_agrement', 'telephone',
            'email', 'actif',
        ]
        read_only_fields = ['id', 'company']


class PoliceAssuranceSerializer(serializers.ModelSerializer):
    assureur_nom = serializers.CharField(
        source='assureur.raison_sociale', read_only=True)
    courtier_nom = serializers.CharField(
        source='courtier.raison_sociale', read_only=True, default='')
    type_police_display = serializers.CharField(
        source='get_type_police_display', read_only=True)
    # NTASS22 — libellé de l'employé couvert (police homme-clé), résolu à la
    # volée via rh.selectors (null si rh absent / employé introuvable).
    employe_couvert_libelle = serializers.SerializerMethodField()

    class Meta:
        model = PoliceAssurance
        fields = [
            'id', 'company', 'assureur', 'assureur_nom', 'courtier',
            'courtier_nom', 'numero_police', 'type_police',
            'type_police_display', 'libelle', 'date_effet', 'date_echeance',
            'tacite_reconduction', 'prime_annuelle_ht', 'statut',
            'document_police', 'notes', 'police_precedente', 'employe_ref',
            'employe_couvert_libelle', 'cyber_clauses', 'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']

    def get_employe_couvert_libelle(self, obj):
        from .selectors import libelle_employe_couvert
        return libelle_employe_couvert(obj.company, obj.employe_ref)

    def validate_assureur(self, value):
        request = self.context.get('request')
        if request and value.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "L'assureur doit appartenir à la même société.")
        return value

    def validate_courtier(self, value):
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError(
                'Le courtier doit appartenir à la même société.')
        return value


class PoliceActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.CharField(
        source='user.get_full_name', read_only=True, default='')

    class Meta:
        model = PoliceActivity
        fields = [
            'id', 'police', 'kind', 'champ', 'champ_label',
            'ancienne_valeur', 'nouvelle_valeur', 'description',
            'user', 'user_nom', 'created_at',
        ]
        read_only_fields = fields


class GarantiePoliceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GarantiePolice
        fields = [
            'id', 'company', 'police', 'libelle_garantie',
            'plafond_indemnisation', 'franchise_montant',
            'franchise_pourcentage', 'notes',
        ]
        read_only_fields = ['id', 'company']

    def validate_police(self, value):
        request = self.context.get('request')
        if request and value.company_id != request.user.company_id:
            raise serializers.ValidationError(
                'La police doit appartenir à la même société.')
        return value


class DeclarationSinistreSerializer(serializers.ModelSerializer):
    numero_dossier = serializers.CharField(source='reference', read_only=True)
    type_sinistre_display = serializers.CharField(
        source='get_type_sinistre_display', read_only=True)
    # NTASS15 — libellé du risque ERM lié, résolu à la volée (null tant que
    # le futur module NTGRC n'existe pas).
    risque_libelle = serializers.SerializerMethodField()

    class Meta:
        model = DeclarationSinistre
        fields = [
            'id', 'company', 'police', 'numero_dossier', 'date_survenance',
            'date_declaration', 'nature_sinistre', 'type_sinistre',
            'type_sinistre_display', 'montant_estime_degats', 'statut',
            'description', 'flotte_sinistre_id', 'risque_ref', 'risque_libelle',
            'dossier_contentieux_ref', 'conteste', 'created_at',
        ]
        read_only_fields = [
            'id', 'company', 'numero_dossier', 'date_declaration',
            'dossier_contentieux_ref', 'conteste', 'created_at',
        ]

    def get_risque_libelle(self, obj):
        from .selectors import libelle_risque
        return libelle_risque(obj.risque_ref)

    def validate_police(self, value):
        request = self.context.get('request')
        if request and value.company_id != request.user.company_id:
            raise serializers.ValidationError(
                'La police doit appartenir à la même société.')
        return value


class SinistreActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.CharField(
        source='user.get_full_name', read_only=True, default='')

    class Meta:
        model = SinistreActivity
        fields = [
            'id', 'declaration', 'kind', 'champ', 'champ_label',
            'ancienne_valeur', 'nouvelle_valeur', 'description',
            'user', 'user_nom', 'created_at',
        ]
        read_only_fields = fields


class IndemnisationSinistreSerializer(serializers.ModelSerializer):
    reste_a_charge = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = IndemnisationSinistre
        fields = [
            'id', 'company', 'declaration', 'montant_reclame',
            'franchise_appliquee', 'montant_indemnise', 'reste_a_charge',
            'date_versement', 'ecriture_ref', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ActifCouvertSerializer(serializers.ModelSerializer):
    """NTASS7 — ``actif_libelle`` accepté en écriture (snapshot posé à
    l'ajout) ; en LECTURE, la représentation le remplace par le libellé
    RÉSOLU à la volée quand un selector propriétaire (``flotte`` pour
    VEHICULE) le connaît, sinon le snapshot reste affiché tel quel."""

    class Meta:
        model = ActifCouvert
        fields = [
            'id', 'company', 'police', 'type_actif', 'actif_ref',
            'actif_libelle', 'date_ajout',
        ]
        read_only_fields = ['id', 'company', 'date_ajout']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        resolu = resoudre_libelle_actif(
            instance.company, instance.type_actif, instance.actif_ref)
        if resolu:
            data['actif_libelle'] = resolu
        return data

    def validate_police(self, value):
        request = self.context.get('request')
        if request and value.company_id != request.user.company_id:
            raise serializers.ValidationError(
                'La police doit appartenir à la même société.')
        return value


class EcheancePrimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcheancePrime
        fields = [
            'id', 'company', 'police', 'date_echeance_paiement', 'montant',
            'periodicite', 'statut', 'ecriture_ref',
        ]
        read_only_fields = ['id', 'company', 'ecriture_ref']

    def validate_police(self, value):
        request = self.context.get('request')
        if request and value.company_id != request.user.company_id:
            raise serializers.ValidationError(
                'La police doit appartenir à la même société.')
        return value


class AttestationAssuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttestationAssurance
        fields = [
            'id', 'company', 'police', 'document', 'date_emission',
            'date_validite', 'emise_pour', 'statut', 'created_at',
        ]
        read_only_fields = ['id', 'company', 'created_at']

    def validate_police(self, value):
        request = self.context.get('request')
        if request and value.company_id != request.user.company_id:
            raise serializers.ValidationError(
                'La police doit appartenir à la même société.')
        return value


class ExigenceAssuranceMarcheSerializer(serializers.ModelSerializer):
    type_police_requis_display = serializers.CharField(
        source='get_type_police_requis_display', read_only=True)

    class Meta:
        model = ExigenceAssuranceMarche
        fields = [
            'id', 'company', 'marche_ref', 'type_police_requis',
            'type_police_requis_display', 'montant_couverture_minimum',
            'statut_verification', 'created_at',
        ]
        read_only_fields = [
            'id', 'company', 'statut_verification', 'created_at',
        ]
