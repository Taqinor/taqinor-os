"""Vues de l'app ESG (Groupe NTESG) — scopées société via
``core.viewsets.CompanyScopedModelViewSet`` (``TenantMixin``) : le queryset
filtre sur ``request.user.company`` et ``company`` est forcée côté serveur,
jamais lue du corps de requête.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixins import TenantMixin
from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet

from .models import CatalogueIndicateurESG, ObjectifESGTrajectoire, \
    PartiePrenanteESG, PeriodeReportingESG
from .serializers import (
    CatalogueIndicateurESGSerializer, ObjectifESGTrajectoireSerializer,
    PartiePrenanteESGSerializer, PeriodeReportingESGSerializer,
)


class PeriodeReportingESGViewSet(CompanyScopedModelViewSet):
    """Périodes de reporting ESG : CRUD + figeage (NTESG1) + rendus
    (NTESG4/5) + aperçu live des indicateurs agrégés (NTESG2/6)."""

    queryset = PeriodeReportingESG.objects.select_related(
        'figee_par', 'snapshot').all()
    serializer_class = PeriodeReportingESGSerializer

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def figer(self, request, pk=None):
        """Fige la période (NTESG1) : gèle son ``SnapshotESG``.

        Refuse (400) si la période est déjà figée/publiée — le figeage
        n'est jamais ré-exécutable (les chiffres gelés ne sont jamais
        recalculés)."""
        from . import services

        periode = self.get_object()
        try:
            services.figer_periode(periode, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(periode).data)

    @action(detail=False, methods=['get'],
            permission_classes=[ScopedPermission])
    def comparer(self, request):
        """Comparateur multi-période N vs N-1 (NTESG11) —
        ``?periode=X&reference=Y`` (les deux IDs scopés société)."""
        from .selectors import comparer_periodes

        periode_id = request.query_params.get('periode')
        reference_id = request.query_params.get('reference')
        if not periode_id or not reference_id:
            return Response(
                {'detail': "Paramètres 'periode' et 'reference' requis."},
                status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset()
        periode = queryset.filter(pk=periode_id).first()
        reference = queryset.filter(pk=reference_id).first()
        if periode is None or reference is None:
            return Response(
                {'detail': 'Période introuvable pour cette société.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(comparer_periodes(reference, periode))

    @action(detail=True, methods=['get'],
            permission_classes=[ScopedPermission])
    def indicateurs(self, request, pk=None):
        """Données ESG effectives de la période (NTESG2/6) — snapshot gelé
        si figée, aperçu LIVE (jamais persisté) si brouillon."""
        from .selectors import donnees_effectives_periode

        periode = self.get_object()
        return Response(donnees_effectives_periode(periode))

    @action(detail=True, methods=['get'], url_path='rapport-pdf',
            permission_classes=[ScopedPermission])
    def rapport_pdf(self, request, pk=None):
        """Rapport ESG GRI-lite PDF (NTESG4) — jamais ``/proposal``, aucune
        donnée commerciale/prix."""
        from .pdf import generer_rapport_esg_pdf

        periode = self.get_object()
        pdf_bytes = generer_rapport_esg_pdf(periode)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="rapport-esg-{periode.pk}.pdf"')
        return response

    @action(detail=True, methods=['get'],
            permission_classes=[ScopedPermission])
    def export(self, request, pk=None):
        """Export xlsx multi-feuilles (NTESG5) — ``?format=xlsx`` (seul
        format supporté aujourd'hui)."""
        from .esg_export import export_esg_periode_xlsx

        fmt = request.query_params.get('format', 'xlsx')
        if fmt != 'xlsx':
            return Response(
                {'detail': "Seul le format 'xlsx' est supporté."},
                status=status.HTTP_400_BAD_REQUEST)
        periode = self.get_object()
        return export_esg_periode_xlsx(periode)


class CatalogueIndicateurESGViewSet(
        TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Référentiel GRI-lite (NTESG3) — lecture seule côté API : seedé par
    ``python manage.py seed_catalogue_esg``, jamais édité en masse par
    l'utilisateur."""

    queryset = CatalogueIndicateurESG.objects.all()
    serializer_class = CatalogueIndicateurESGSerializer
    permission_classes = [ScopedPermission]

    @action(detail=False, methods=['get'],
            permission_classes=[ScopedPermission])
    def couverture(self, request):
        """% du catalogue effectivement renseigné par pilier (NTESG3)."""
        from .selectors import couverture_catalogue

        return Response(couverture_catalogue(request.user.company))


class ObjectifESGTrajectoireViewSet(CompanyScopedModelViewSet):
    """Objectifs de trajectoire ESG (NTESG7) — CRUD + comparaison théorique
    vs réalisé."""

    queryset = ObjectifESGTrajectoire.objects.all()
    serializer_class = ObjectifESGTrajectoireSerializer

    @action(detail=True, methods=['get'],
            permission_classes=[ScopedPermission])
    def trajectoire(self, request, pk=None):
        """Trajectoire linéaire théorique vs valeurs réelles par année
        (NTESG7)."""
        from .selectors import trajectoire_vs_realise

        objectif = self.get_object()
        return Response(trajectoire_vs_realise(objectif))


class PartiePrenanteESGViewSet(CompanyScopedModelViewSet):
    """Registre des parties prenantes ESG — matérialité simplifiée
    (NTESG12) : CRUD complet, la matrice 2x2 influence×intérêt se construit
    côté frontend à partir de la liste."""

    queryset = PartiePrenanteESG.objects.all()
    serializer_class = PartiePrenanteESGSerializer
