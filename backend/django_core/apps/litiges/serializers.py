"""Sérialiseurs des Réclamations & litiges.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``created_by`` est posé côté serveur.
"""
from rest_framework import serializers

from .models import Reclamation


class ReclamationSerializer(serializers.ModelSerializer):
    type_reclamation_display = serializers.CharField(
        source='get_type_reclamation_display', read_only=True)
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Reclamation
        fields = [
            'id', 'reference', 'type_reclamation', 'type_reclamation_display',
            'gravite', 'gravite_display', 'objet', 'description',
            'source_type', 'source_id', 'montant_conteste', 'statut',
            'statut_display', 'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']
