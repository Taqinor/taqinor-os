"""Serializers du registre des assurances & sinistres d'entreprise (NTASS)."""
from rest_framework import serializers

from .models import Assureur, Courtier, PoliceAssurance


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

    class Meta:
        model = PoliceAssurance
        fields = [
            'id', 'company', 'assureur', 'assureur_nom', 'courtier',
            'courtier_nom', 'numero_police', 'type_police',
            'type_police_display', 'libelle', 'date_effet', 'date_echeance',
            'tacite_reconduction', 'prime_annuelle_ht', 'statut',
            'document_police', 'notes', 'police_precedente',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']

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
