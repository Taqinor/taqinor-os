"""Sérialiseurs du module Gestion de flotte.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par le
``TenantMixin`` (``perform_create``). Aucune valeur de société du corps de requête
n'est jamais acceptée (multi-tenant). Les FK reçus sont validés comme appartenant
à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import Vehicule


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class VehiculeSerializer(serializers.ModelSerializer):
    type_vehicule_display = serializers.CharField(
        source='get_type_vehicule_display', read_only=True)
    energie_display = serializers.CharField(
        source='get_energie_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Vehicule
        fields = [
            'id', 'immatriculation', 'marque', 'modele', 'type_vehicule',
            'type_vehicule_display', 'energie', 'energie_display',
            'kilometrage', 'valeur_acquisition', 'date_mise_circulation',
            'statut', 'statut_display', 'conducteur', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_conducteur(self, value):
        return _meme_societe(self, value, 'Conducteur')
