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


class RechercheGlobaleRequeteSerializer(serializers.Serializer):
    """NTAI25 — corps de ``POST /api/django/ai/recherche-globale/``.

    Déclaré pour que la vue soit une ``GenericAPIView`` avec une forme
    RÉSOLVABLE : sans lui, drf-spectacular tombe en « unable to guess
    serializer » et la vue ajouterait de la dette au cliquet R2
    (`check_openapi_shapes`), qui ne peut que décroître.
    """

    question = serializers.CharField(allow_blank=True, required=False)
