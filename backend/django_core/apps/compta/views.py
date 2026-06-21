"""Vues de la Comptabilité générale (toutes scopées société, admin-gated).

La compta est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``).
Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; aucun prix d'achat ni marge n'apparaît ici.
"""
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors, services
from .models import (
    CompteComptable, CompteTresorerie, EcritureComptable, ExerciceComptable,
    Journal, PeriodeComptable, PlanComptable,
)
from .serializers import (
    CompteComptableSerializer, CompteTresorerieSerializer,
    EcritureComptableSerializer, ExerciceComptableSerializer,
    JournalSerializer, PeriodeComptableSerializer, PlanComptableSerializer,
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


# ── FG115 — Périodes comptables verrouillables ─────────────────────────────

class PeriodeComptableViewSet(_ComptaBaseViewSet):
    """Périodes comptables (FG115) : clôture/réouverture (verrouillage).

    Actions ``cloturer`` / ``rouvrir`` figent ou libèrent la période ; une fois
    verrouillée, les écritures & factures de l'intervalle deviennent immuables.
    """
    queryset = PeriodeComptable.objects.select_related('exercice').all()
    serializer_class = PeriodeComptableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin']

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        periode = self.get_object()
        services.cloturer_periode(periode, user=request.user)
        return Response(self.get_serializer(periode).data)

    @action(detail=True, methods=['post'])
    def rouvrir(self, request, pk=None):
        periode = self.get_object()
        try:
            services.rouvrir_periode(periode)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(periode).data)


# ── FG116 / FG117 — Exercices comptables (clôture, OD, à-nouveaux) ──────────

class ExerciceComptableViewSet(_ComptaBaseViewSet):
    """Exercices comptables (FG117) : clôture, réouverture, report d'à-nouveaux.

    Porte aussi l'action ``ecriture-od`` (FG116) : saisie d'une écriture de
    régularisation manuelle (sans document source), refusée si la période est
    verrouillée.
    """
    queryset = ExerciceComptable.objects.prefetch_related('periodes').all()
    serializer_class = ExerciceComptableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin']

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        exercice = self.get_object()
        services.cloturer_exercice(exercice, user=request.user)
        return Response(self.get_serializer(exercice).data)

    @action(detail=True, methods=['post'])
    def rouvrir(self, request, pk=None):
        exercice = self.get_object()
        services.rouvrir_exercice(exercice)
        return Response(self.get_serializer(exercice).data)

    @action(detail=True, methods=['post'], url_path='reporter-a-nouveaux')
    def reporter_a_nouveaux(self, request, pk=None):
        """Reporte les soldes de bilan de CET exercice dans ``exercice_cible``.

        Corps : ``{"exercice_cible": <id>}``. L'exercice source (celui de l'URL)
        doit être clôturé ; le report est idempotent.
        """
        exercice_clos = self.get_object()
        cible_id = request.data.get('exercice_cible')
        cible = ExerciceComptable.objects.filter(
            company=request.user.company, id=cible_id).first()
        if cible is None:
            return Response(
                {'detail': 'Exercice cible inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ecriture = services.reporter_a_nouveaux(
                exercice_clos, cible, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'exercice': self.get_serializer(cible).data,
            'ecriture_id': ecriture.id if ecriture else None,
        })

    @action(detail=False, methods=['post'], url_path='ecriture-od')
    def ecriture_od(self, request):
        """Crée une écriture de régularisation manuelle (OD) — FG116.

        Corps : ``{date_ecriture, libelle, reference?, lignes:[{compte, debit,
        credit, libelle?}]}``. Σ débit = Σ crédit exigé ; refusée si la période
        est verrouillée.
        """
        company = request.user.company
        data = request.data
        lignes_in = data.get('lignes') or []
        lignes = []
        for lig in lignes_in:
            compte = CompteComptable.objects.filter(
                company=company, id=lig.get('compte')).first()
            if compte is None:
                return Response(
                    {'detail': 'Compte inconnu.'},
                    status=status.HTTP_400_BAD_REQUEST)
            lignes.append({
                'compte': compte,
                'debit': lig.get('debit') or 0,
                'credit': lig.get('credit') or 0,
                'libelle': lig.get('libelle', '') or '',
            })
        try:
            ecriture = services.creer_ecriture_od(
                company, data.get('date_ecriture'),
                data.get('libelle', '') or 'Régularisation', lignes,
                reference=data.get('reference', '') or '',
                created_by=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages[0] if exc.messages else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            EcritureComptableSerializer(ecriture).data,
            status=status.HTTP_201_CREATED)
