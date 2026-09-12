"""Serializers du module « ai_governance » (Groupe NTAI)."""
from rest_framework import serializers

from .models import DocumentAiJob, ExtractionCorrection, LlmBudget


class LlmBudgetSerializer(serializers.ModelSerializer):
    """NTAI2 — Budget IA mensuel d'une société.

    ``company`` n'est PAS un champ : elle est forcée côté serveur dans
    ``perform_create`` (jamais lue du corps de requête). ``alerte_periode`` est
    en lecture seule — c'est la mémoire de l'alerte, pas un réglage.
    """

    class Meta:
        model = LlmBudget
        fields = ['id', 'montant_mensuel_mad', 'seuil_alerte_pct', 'actif',
                  'alerte_periode', 'created_at', 'updated_at']
        read_only_fields = ['id', 'alerte_periode', 'created_at', 'updated_at']

    def validate_seuil_alerte_pct(self, valeur):
        if valeur is not None and not (1 <= int(valeur) <= 100):
            raise serializers.ValidationError(
                "Le seuil d'alerte doit être compris entre 1 et 100 %.")
        return valeur

    def validate_montant_mensuel_mad(self, valeur):
        if valeur is not None and valeur <= 0:
            raise serializers.ValidationError(
                'Le plafond mensuel doit être strictement positif.')
        return valeur

    def validate(self, attrs):
        """Refuse un SECOND budget en 400 explicite (jamais une 500).

        La contrainte d'unicité protège la base ; cette validation protège
        l'UTILISATEUR, qui doit lire « il en existe déjà un » plutôt qu'une
        erreur serveur."""
        attrs = super().validate(attrs)
        if self.instance is None:
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None and LlmBudget.objects.filter(
                    company=company).exists():
                raise serializers.ValidationError({
                    'detail': 'Un budget IA existe déjà pour cette société — '
                              "modifiez-le au lieu d'en créer un second."})
        return attrs


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


class UsageRequeteSerializer(serializers.Serializer):
    """NTAI1 — paramètres de ``GET /api/django/ai-governance/usage/``.

    Déclaré pour que la vue soit une ``GenericAPIView`` à forme RÉSOLVABLE :
    sans lui, drf-spectacular tombe en « unable to guess serializer » et la vue
    ajouterait de la dette au cliquet R2 (`check_openapi_shapes`), qui ne peut
    que décroître.
    """

    since = serializers.DateField(required=False)
    feature = serializers.CharField(required=False, allow_blank=True)


class RechercheGlobaleRequeteSerializer(serializers.Serializer):
    """NTAI25 — corps de ``POST /api/django/ai/recherche-globale/``.

    Déclaré pour que la vue soit une ``GenericAPIView`` avec une forme
    RÉSOLVABLE : sans lui, drf-spectacular tombe en « unable to guess
    serializer » et la vue ajouterait de la dette au cliquet R2
    (`check_openapi_shapes`), qui ne peut que décroître.
    """

    question = serializers.CharField(allow_blank=True, required=False)
