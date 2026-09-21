from rest_framework import serializers

from .models import (
    AttestationTenant, BeneficiaireEffectif, EcheanceFiscale, ObligationFiscale,
    VeilleReglementaire,
)


class ObligationFiscaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObligationFiscale
        fields = [
            'id', 'type_obligation', 'libelle', 'periodicite',
            'regle_echeance', 'actif', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']


class EcheanceFiscaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcheanceFiscale
        fields = [
            'id', 'obligation', 'periode_debut', 'periode_fin', 'date_limite',
            'statut', 'declaration_type', 'declaration_id',
            'rappel_envoye_le', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation', 'rappel_envoye_le']


class AttestationTenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttestationTenant
        fields = [
            'id', 'type_attestation', 'numero', 'date_emission',
            'date_expiration', 'fichier_key', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']


class BeneficiaireEffectifSerializer(serializers.ModelSerializer):
    class Meta:
        model = BeneficiaireEffectif
        fields = [
            'id', 'nom', 'cin_passeport', 'nationalite',
            'pourcentage_detention', 'type_controle', 'date_declaration',
            'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']


class VeilleReglementaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = VeilleReglementaire
        fields = [
            'id', 'domaine', 'titre', 'resume', 'date_effet', 'source_url',
            'statut', 'parametre_cible', 'impact_traite', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']
