"""NTMOB1 — sérialiseurs du journal hors-ligne (lecture seule)."""
from rest_framework import serializers

from .models import OfflineOperation


class OfflineOperationSerializer(serializers.ModelSerializer):
    """Journal en LECTURE SEULE : une opération n'est jamais créée par ce
    sérialiseur — elle naît du lot de synchro, société posée serveur."""

    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    module_libelle = serializers.CharField(
        source='get_module_display', read_only=True)

    class Meta:
        model = OfflineOperation
        fields = [
            'id', 'module', 'module_libelle', 'op_type', 'client_op_id',
            'statut', 'statut_libelle', 'payload', 'resultat', 'erreur',
            'date_creation', 'date_traitement', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
