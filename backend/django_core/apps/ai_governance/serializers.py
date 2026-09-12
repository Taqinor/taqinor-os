"""Serializers du module « ai_governance » (Groupe NTAI)."""
from rest_framework import serializers

from .models import (AiFeatureToggle, DocumentAiJob, ExtractionCorrection,
                     LlmBudget, PromptTemplate, PromptTemplateVersion)


class AiFeatureToggleSerializer(serializers.ModelSerializer):
    """NTAI7 — Consentement IA d'une société pour une feature.

    ``company`` n'est pas un champ : elle est forcée dans ``perform_create``.
    L'absence de ligne vaut « actif » — créer une ligne à ``actif: true`` est
    donc un no-op explicite, et c'est voulu (l'écran montre l'état choisi).
    """

    class Meta:
        model = AiFeatureToggle
        fields = ['id', 'feature_key', 'actif', 'motif', 'created_at',
                  'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_feature_key(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError(
                'La clé de la fonction est obligatoire.')
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        doublon = AiFeatureToggle.objects.filter(
            company=company, feature_key=valeur)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if company is not None and doublon.exists():
            raise serializers.ValidationError(
                'Cette fonction a déjà un réglage — modifiez-le.')
        return valeur


class PromptTemplateVersionSerializer(serializers.ModelSerializer):
    """Version FIGÉE d'un gabarit — lecture seule (aucune route d'écriture)."""

    class Meta:
        model = PromptTemplateVersion
        fields = ['id', 'numero', 'corps', 'cree_par', 'cree_le']
        read_only_fields = fields


class PromptTemplateSerializer(serializers.ModelSerializer):
    """NTAI5 — Surcharge société du prompt d'une feature.

    ``company`` n'est pas un champ : elle est forcée dans ``perform_create``.
    ``placeholders`` expose les ``{{champ}}`` déclarés, pour que l'écran de
    paramétrage montre ce que le texte attend."""

    versions = PromptTemplateVersionSerializer(many=True, read_only=True)
    placeholders = serializers.SerializerMethodField()

    class Meta:
        model = PromptTemplate
        fields = ['id', 'cle', 'label', 'corps', 'capability', 'actif',
                  'placeholders', 'versions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'placeholders', 'versions', 'created_at',
                            'updated_at']

    def get_placeholders(self, obj):
        from core.ai.prompts import placeholders

        return placeholders(obj.corps)

    def validate_cle(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError('La clé est obligatoire.')
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        doublon = PromptTemplate.objects.filter(company=company, cle=valeur)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if company is not None and doublon.exists():
            raise serializers.ValidationError(
                'Cette clé est déjà surchargée pour votre société.')
        return valeur


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


class FicheCibleSerializer(serializers.Serializer):
    """NTAI8/NTAI9 — corps de ``resume-fiche/`` et ``prochaines-actions/``.

    La société n'est JAMAIS dans le corps : elle vient de l'utilisateur
    authentifié et borne la résolution de la cible côté serveur.
    """

    content_type = serializers.CharField()
    object_id = serializers.CharField()


class CapacitesRequeteSerializer(serializers.Serializer):
    """NTAI6 — requête (vide) de ``GET ai-governance/capabilities/``.

    Déclaré pour que la vue soit une ``GenericAPIView`` à forme résolvable :
    sans lui, drf-spectacular tombe en « unable to guess serializer » et la vue
    ajouterait de la dette au cliquet R2 (`check_openapi_shapes`).
    """


class RechercheGlobaleRequeteSerializer(serializers.Serializer):
    """NTAI25 — corps de ``POST /api/django/ai/recherche-globale/``.

    Déclaré pour que la vue soit une ``GenericAPIView`` avec une forme
    RÉSOLVABLE : sans lui, drf-spectacular tombe en « unable to guess
    serializer » et la vue ajouterait de la dette au cliquet R2
    (`check_openapi_shapes`), qui ne peut que décroître.
    """

    question = serializers.CharField(allow_blank=True, required=False)
