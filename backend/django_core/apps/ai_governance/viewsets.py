"""ViewSets du module « ai_governance » (Groupe NTAI).

``DocumentAiJobViewSet`` est en LECTURE SEULE : un job est produit par le
pipeline documentaire (dépôt GED), jamais créé par un client HTTP. Le SEUL
chemin d'écriture est l'action ``corriger/`` (NTAI18) — la revue humaine — et
elle n'écrit que dans la PROPOSITION, jamais dans un modèle métier.

Le scoping société vient de ``core.mixins.TenantMixin`` (``get_queryset``
filtré sur ``request.user.company``), donc le sweep générique d'isolation
multi-tenant couvre ce viewset automatiquement.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import IsAdminRole, IsAnyRole
from core.mixins import TenantMixin

from .models import (AiFeatureToggle, DocumentAiJob, LlmBudget,
                     PromptTemplate)
from .serializers import (AiFeatureToggleSerializer, DocumentAiJobSerializer,
                          LlmBudgetSerializer, PromptTemplateSerializer)
from .services import AiCopiloteUnavailable


class LlmBudgetViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTAI2 — CRUD du budget IA mensuel. ADMIN uniquement.

    Le scoping société vient de ``TenantMixin`` en lecture ; en écriture la
    société est FORCÉE depuis l'utilisateur (``perform_create``), jamais lue du
    corps de requête. Un seul budget par société (contrainte d'unicité) : une
    seconde création renvoie une erreur FR explicite plutôt qu'un 500.
    """

    queryset = LlmBudget.objects.all()
    serializer_class = LlmBudgetSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def perform_create(self, serializer):
        # La société vient TOUJOURS du serveur ; le doublon est refusé en 400
        # par le sérialiseur (``validate``), jamais par une 500 d'intégrité.
        serializer.save(company=self.request.user.company)

    @extend_schema(responses=inline_serializer('AiBudgetStatut', {
        'configure': drf_serializers.BooleanField(),
        'plafond_mad': drf_serializers.CharField(),
        'depense_mad': drf_serializers.CharField(),
        'pourcentage': drf_serializers.FloatField(),
        'depasse': drf_serializers.BooleanField(),
        'alerte': drf_serializers.BooleanField(),
        'periode': drf_serializers.CharField(),
    }))
    @action(detail=False, methods=['get'], url_path='statut')
    def statut(self, request):
        """``GET budgets/statut/`` — situation du mois COURANT.

        Renvoie ``configure: false`` quand aucun budget actif n'est défini :
        aucun pourcentage n'est affiché contre un plafond imaginaire.
        """
        from core.ai.usage import budget_status

        return Response(budget_status(request.user.company).as_dict())


class AiFeatureToggleViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTAI7 — CRUD des consentements IA. ADMIN uniquement.

    Couper une feature ici la rend inopérante POUR CETTE SOCIÉTÉ seulement ;
    l'absence de ligne vaut « actif » (le défaut n'est jamais un refus).
    """

    queryset = AiFeatureToggle.objects.all()
    serializer_class = AiFeatureToggleSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class PromptTemplateViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTAI5 — CRUD des surcharges de prompt. ADMIN uniquement.

    Chaque écriture FIGE une version immuable du corps : on peut toujours dire
    quel texte a produit un brouillon donné. La société est posée côté serveur.
    """

    queryset = PromptTemplate.objects.all()
    serializer_class = PromptTemplateSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return super().get_queryset().prefetch_related('versions')

    def perform_create(self, serializer):
        from .prompts import figer_version

        gabarit = serializer.save(company=self.request.user.company)
        figer_version(gabarit, user=self.request.user)

    def perform_update(self, serializer):
        from .prompts import figer_version

        gabarit = serializer.save()
        figer_version(gabarit, user=self.request.user)

    @extend_schema(responses=inline_serializer('AiPromptsEffectifs', {
        'cle': drf_serializers.CharField(),
        'corps': drf_serializers.CharField(),
        'origine': drf_serializers.CharField(),
        'placeholders': drf_serializers.JSONField(),
    }, many=True))
    @action(detail=False, methods=['get'], url_path='effective')
    def effective(self, request):
        """``GET prompt-templates/effective/`` — ce qui s'applique VRAIMENT.

        Pour chaque clé connue du code : le corps effectif et son origine
        (``code`` ou ``societe``). C'est la liste exhaustive de ce qu'une
        société peut surcharger.
        """
        from .prompts import prompts_effectifs

        return Response(prompts_effectifs(request.user.company))


class DocumentAiJobViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """NTAI17/NTAI18 — File des traitements IA de documents + revue humaine."""

    queryset = DocumentAiJob.objects.all()
    serializer_class = DocumentAiJobSerializer
    permission_classes = [IsAuthenticated, IsAnyRole]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('corrections')
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['post'], url_path='corriger')
    def corriger(self, request, pk=None):
        """``POST documents-ai-jobs/<id>/corriger/`` — valide/corrige les champs.

        Body ``{"corrections": [{"champ": "...", "valeur_corrigee": "..."}]}``.
        Enregistre l'écart CHAMP PAR CHAMP puis applique la valeur validée au
        résultat du job. N'écrit JAMAIS dans un modèle métier.
        """
        from .services import enregistrer_corrections

        job = self.get_object()
        corrections = request.data.get('corrections')
        if corrections is None and request.data.get('champ'):
            # Tolérance : un seul champ peut être envoyé à plat.
            corrections = [{
                'champ': request.data.get('champ'),
                'valeur_corrigee': request.data.get('valeur_corrigee'),
            }]
        try:
            resultat = enregistrer_corrections(
                job, corrections, user=request.user)
        except AiCopiloteUnavailable as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(resultat)

    @action(detail=False, methods=['get'], url_path='taux-correction')
    def taux_correction(self, request):
        """``GET documents-ai-jobs/taux-correction/`` — qualité par gabarit.

        Tableau ``[{schema, champs_revus, champs_corriges, taux_correction}]``
        scopé société : la précision MESURÉE de chaque schéma d'extraction.
        """
        from .services import taux_correction_par_schema

        return Response(taux_correction_par_schema(request.user.company))
