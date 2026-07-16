"""Serializers du registre des assurances & sinistres d'entreprise (NTASS)."""
from rest_framework import serializers

from .models import Assureur, Courtier


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
