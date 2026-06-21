"""Sérialiseurs du module Gestion de flotte.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par le
``TenantMixin`` (``perform_create``). Aucune valeur de société du corps de requête
n'est jamais acceptée (multi-tenant).
"""
from rest_framework import serializers

from .models import Vehicule


class VehiculeSerializer(serializers.ModelSerializer):
    energie_display = serializers.CharField(
        source='get_energie_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Vehicule
        fields = [
            'id', 'immatriculation', 'marque', 'modele', 'energie',
            'energie_display', 'kilometrage', 'valeur', 'statut',
            'statut_display', 'date_creation',
        ]
        read_only_fields = ['date_creation']
