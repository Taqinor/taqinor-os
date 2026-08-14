"""ViewSets du module « ai_governance » (Groupe NTAI).

``DocumentAiJobViewSet`` est en LECTURE SEULE : un job est produit par le
pipeline documentaire (dépôt GED), jamais créé par un client HTTP. Le SEUL
chemin d'écriture est l'action ``corriger/`` (NTAI18) — la revue humaine — et
elle n'écrit que dans la PROPOSITION, jamais dans un modèle métier.

Le scoping société vient de ``core.mixins.TenantMixin`` (``get_queryset``
filtré sur ``request.user.company``), donc le sweep générique d'isolation
multi-tenant couvre ce viewset automatiquement.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.mixins import TenantMixin

from .models import DocumentAiJob
from .serializers import DocumentAiJobSerializer
from .services import AiCopiloteUnavailable


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
