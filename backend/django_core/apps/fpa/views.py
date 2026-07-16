from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixins import TenantMixin

from .models import CycleBudgetaire, Departement, LigneBudgetDepartement
from .serializers import (
    CycleBudgetaireSerializer, DepartementSerializer,
    LigneBudgetDepartementSerializer,
)


class DepartementViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA1 — CRUD des départements FP&A, scopé société."""

    queryset = Departement.objects.select_related('responsable', 'parent').all()
    serializer_class = DepartementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom']
    ordering_fields = ['nom', 'code']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai'))
        return qs

    def _to_node(self, dept, by_parent):
        enfants = by_parent.get(dept.pk, [])
        return {
            **DepartementSerializer(dept).data,
            'enfants': [self._to_node(e, by_parent) for e in enfants],
        }

    def list(self, request, *args, **kwargs):
        if request.query_params.get('tree') == '1':
            qs = list(self.filter_queryset(self.get_queryset()))
            by_parent = {}
            for d in qs:
                by_parent.setdefault(d.parent_id, []).append(d)
            racines = by_parent.get(None, [])
            return Response([self._to_node(d, by_parent) for d in racines])
        return super().list(request, *args, **kwargs)


class CycleBudgetaireViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA2 — Cycles budgétaires : machine d'états gardée (brouillon →
    ouvert_saisie → en_validation → clos), transitions illégales refusées
    (400)."""

    queryset = CycleBudgetaire.objects.all()
    serializer_class = CycleBudgetaireSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['date_debut', 'nom']

    @action(detail=True, methods=['post'], url_path='ouvrir-saisie')
    def ouvrir_saisie(self, request, pk=None):
        cycle = self.get_object()
        if cycle.statut != CycleBudgetaire.Statut.BROUILLON:
            return Response(
                {'detail': "Seul un cycle « brouillon » peut être ouvert à la saisie."},
                status=status.HTTP_400_BAD_REQUEST)
        cycle.statut = CycleBudgetaire.Statut.OUVERT_SAISIE
        cycle.save(update_fields=['statut'])
        return Response(CycleBudgetaireSerializer(cycle).data)

    @action(detail=True, methods=['post'], url_path='clore')
    def clore(self, request, pk=None):
        cycle = self.get_object()
        if cycle.statut not in (
                CycleBudgetaire.Statut.OUVERT_SAISIE,
                CycleBudgetaire.Statut.EN_VALIDATION):
            return Response(
                {'detail': "Un cycle brouillon ou déjà clos ne peut pas être clôturé."},
                status=status.HTTP_400_BAD_REQUEST)
        cycle.statut = CycleBudgetaire.Statut.CLOS
        cycle.save(update_fields=['statut'])
        return Response(CycleBudgetaireSerializer(cycle).data)


class LigneBudgetDepartementViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA3 — Lignes de budget départemental (saisie mensuelle par
    catégorie). NTFPA6 — un cycle clos refuse toute écriture (400, via le
    ``ValidationError`` levé par ``LigneBudgetDepartement.save()``)."""

    queryset = LigneBudgetDepartement.objects.select_related(
        'cycle', 'departement').all()
    serializer_class = LigneBudgetDepartementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['mois', 'categorie']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if cycle_id := params.get('cycle'):
            qs = qs.filter(cycle_id=cycle_id)
        if departement_id := params.get('departement'):
            qs = qs.filter(departement_id=departement_id)
        if categorie := params.get('categorie'):
            qs = qs.filter(categorie=categorie)
        return qs
