"""Vues de la Comptabilité générale (toutes scopées société, admin-gated).

La compta est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``).
Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; aucun prix d'achat ni marge n'apparaît ici.
"""
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors, services
from .models import (
    CompteComptable, CompteTresorerie, EcritureComptable, Journal,
    PlanComptable,
)
from .serializers import (
    CompteComptableSerializer, CompteTresorerieSerializer,
    EcritureComptableSerializer, JournalSerializer, PlanComptableSerializer,
)


class _ComptaBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class PlanComptableViewSet(_ComptaBaseViewSet):
    """Plan(s) comptable(s) de la société (FG107). Action ``seed`` pour amorcer
    le plan CGNC + les journaux standards (idempotent)."""
    queryset = PlanComptable.objects.all()
    serializer_class = PlanComptableSerializer

    @action(detail=False, methods=['post'])
    def seed(self, request):
        company = request.user.company
        plan = services.seed_plan_comptable(company)
        services.seed_journaux(company)
        return Response(PlanComptableSerializer(plan).data)


class CompteComptableViewSet(_ComptaBaseViewSet):
    """Comptes du plan comptable (FG107). Recherche par numéro/intitulé."""
    queryset = CompteComptable.objects.select_related('plan').all()
    serializer_class = CompteComptableSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero', 'intitule']
    ordering_fields = ['numero', 'classe']

    def get_queryset(self):
        qs = super().get_queryset()
        classe = self.request.query_params.get('classe')
        if classe:
            qs = qs.filter(classe=classe)
        return qs


class JournalViewSet(_ComptaBaseViewSet):
    """Journaux comptables (FG108)."""
    queryset = Journal.objects.select_related('compte_contrepartie').all()
    serializer_class = JournalSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['code']


class EcritureComptableViewSet(_ComptaBaseViewSet):
    """Écritures en partie double (FG108). Filtrable par journal/période."""
    queryset = EcritureComptable.objects.select_related('journal').prefetch_related(
        'lignes__compte').all()
    serializer_class = EcritureComptableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_ecriture', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        journal = params.get('journal')
        if journal:
            qs = qs.filter(journal_id=journal)
        date_debut = params.get('date_debut')
        if date_debut:
            qs = qs.filter(date_ecriture__gte=date_debut)
        date_fin = params.get('date_fin')
        if date_fin:
            qs = qs.filter(date_ecriture__lte=date_fin)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class CompteTresorerieViewSet(_ComptaBaseViewSet):
    """Référentiel des comptes bancaires & caisses (FG121)."""
    queryset = CompteTresorerie.objects.select_related('compte_comptable').all()
    serializer_class = CompteTresorerieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['type_compte', 'libelle']

    @action(detail=True, methods=['get'])
    def solde(self, request, pk=None):
        """Solde courant du compte de trésorerie (solde initial + GL)."""
        treso = self.get_object()
        from decimal import Decimal
        mouvements = selectors.solde_compte(
            request.user.company, treso.compte_comptable)
        total = Decimal(treso.solde_initial) + mouvements
        return Response({
            'solde_initial': treso.solde_initial,
            'mouvements': mouvements,
            'solde': total,
        })


class EtatsComptablesViewSet(viewsets.ViewSet):
    """États de synthèse en LECTURE SEULE (FG110-114) : grand livre, balance,
    CPC, bilan. Admin/Responsable uniquement, scopés société côté selector."""
    permission_classes = [IsResponsableOrAdmin]

    def _periode(self, request):
        params = request.query_params
        return {
            'date_debut': params.get('date_debut') or None,
            'date_fin': params.get('date_fin') or None,
            'validees_seulement': params.get('validees') == '1',
        }

    @action(detail=False, methods=['get'])
    def grand_livre(self, request):
        company = request.user.company
        periode = self._periode(request)
        compte = None
        numero = request.query_params.get('compte')
        if numero:
            compte = CompteComptable.objects.filter(
                company=company, numero=numero).first()
        data = selectors.grand_livre(company, compte=compte, **periode)
        return Response(data)

    @action(detail=False, methods=['get'])
    def balance(self, request):
        data = selectors.balance_generale(
            request.user.company, **self._periode(request))
        return Response(data)

    @action(detail=False, methods=['get'])
    def cpc(self, request):
        data = selectors.cpc(request.user.company, **self._periode(request))
        return Response(data)

    @action(detail=False, methods=['get'])
    def bilan(self, request):
        periode = self._periode(request)
        data = selectors.bilan(
            request.user.company, date_fin=periode['date_fin'],
            validees_seulement=periode['validees_seulement'])
        return Response(data)
