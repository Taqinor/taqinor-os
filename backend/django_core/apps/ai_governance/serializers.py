"""Serializers du module « ai_governance » (Groupe NTAI)."""
from rest_framework import serializers

from .models import DocumentAiJob, ExtractionCorrection


class ExtractionCorrectionSerializer(serializers.ModelSerializer):
    """Écart journalisé entre la valeur proposée et la valeur retenue."""

    modifie = serializers.BooleanField(
        source='est_une_correction', read_only=True)

    class Meta:
        model = ExtractionCorrection
        fields = ['id', 'job', 'champ', 'valeur_ia', 'valeur_corrigee',
                  'modifie', 'corrige_par', 'corrige_le']
        read_only_fields = fields


class DocumentAiJobSerializer(serializers.ModelSerializer):
    """Job de traitement documentaire — LECTURE SEULE.

    Un job est créé par le pipeline (dépôt GED), jamais par un client HTTP :
    tous les champs sont en lecture seule. La revue humaine passe par l'action
    ``corriger/`` (NTAI18), qui est le seul chemin d'écriture.
    """

    corrections = ExtractionCorrectionSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentAiJob
        fields = ['id', 'document', 'categorie', 'schema', 'statut',
                  'resultat_json', 'confiance', 'message', 'traite_le',
                  'corrections', 'created_at', 'updated_at']
        read_only_fields = fields
