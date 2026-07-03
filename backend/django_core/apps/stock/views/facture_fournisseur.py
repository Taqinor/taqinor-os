from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from authentication.mixins import TenantMixin  # noqa: F401
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import (  # noqa: F401
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, ReceptionFournisseur, FactureFournisseur,
    PaiementFournisseur,
)
from ..serializers import (  # noqa: F401
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
    EmplacementStockSerializer,
    TransfertStockSerializer,
    PrixFournisseurSerializer,
    RetourFournisseurSerializer,
    ReceptionFournisseurSerializer,
    FactureFournisseurSerializer,
    PaiementFournisseurSerializer,
    EcheanceFactureFournisseurSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class FactureFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """G5 — Factures fournisseur / comptes à payer (AP).

    Numérotation sans trou (préfixe FF). Le solde dû = TTC − Σ paiements ; le
    statut de règlement est recalculé à chaque paiement. L'action `paiements`
    liste/ajoute les règlements ; `comptes-a-payer` liste les factures non
    soldées. Usage INTERNE (montants d'achat jamais client-facing)."""
    queryset = FactureFournisseur.objects.select_related(
        'fournisseur', 'bon_commande', 'created_by',
    ).prefetch_related('lignes__produit', 'paiements').all()
    serializer_class = FactureFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'ref_fournisseur', 'fournisseur__nom', 'note',
    ]
    ordering_fields = [
        'date_creation', 'date_facture', 'date_echeance', 'statut',
        'reference', 'montant_ttc',
    ]
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['comptes_a_payer']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['paiements', 'echeancier']:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        fournisseur_id = self.request.query_params.get('fournisseur')
        if fournisseur_id:
            qs = qs.filter(fournisseur_id=fournisseur_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(FactureFournisseur, 'FF', company, _save)

    @action(detail=False, methods=['get'], url_path='comptes-a-payer')
    def comptes_a_payer(self, request):
        """Liste des factures fournisseur NON soldées (à payer ou
        partiellement payées), triées par échéance puis date. INTERNE."""
        from decimal import Decimal
        qs = self.filter_queryset(self.get_queryset()).exclude(
            statut=FactureFournisseur.Statut.PAYEE).order_by(
            'date_echeance', '-date_creation')
        data = self.get_serializer(qs, many=True).data
        total_du = sum((Decimal(f['solde_du']) for f in data), Decimal('0'))
        return Response({'results': data, 'total_du': str(total_du)})

    @action(detail=True, methods=['get'], url_path='pdf',
            permission_classes=[IsResponsableOrAdmin])
    def pdf(self, request, pk=None):
        """FG55 — PDF facture fournisseur (INTERNE — montre les prix d'achat).
        Jamais un document client."""
        from ..services import generate_facture_fournisseur_pdf
        facture = self.get_object()
        pdf_bytes = generate_facture_fournisseur_pdf(facture)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{facture.reference}.pdf"')
        return response

    @action(detail=True, methods=['get', 'post'], url_path='paiements')
    def paiements(self, request, pk=None):
        """GET : liste des paiements de la facture. POST : enregistre un
        paiement (montant/date/mode), recalcule le statut + le solde dû."""
        facture = self.get_object()
        if request.method.lower() == 'get':
            qs = facture.paiements.select_related('created_by').all()
            return Response(
                PaiementFournisseurSerializer(qs, many=True).data)
        # POST — enregistre un paiement, company posée serveur.
        serializer = PaiementFournisseurSerializer(
            data={**request.data, 'facture': facture.id},
            context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save(
                company=request.user.company, created_by=request.user)
            from ..services import recompute_facture_fournisseur_statut
            facture.refresh_from_db()
            recompute_facture_fournisseur_statut(facture)
        return Response(self.get_serializer(facture).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='echeancier')
    def echeancier(self, request, pk=None):
        """XPUR6 — GET : liste les tranches d'échéancier de la facture.
        POST : crée l'échéancier multi-tranches (corps : ``{"tranches": [
        {"pourcentage": 30, "date_echeance": "2026-08-01"}, ...]}``). Chaque
        tranche sans ``montant`` explicite est dérivée du TTC × pourcentage."""
        facture = self.get_object()
        if request.method.lower() == 'get':
            qs = facture.echeances.all()
            return Response(
                EcheanceFactureFournisseurSerializer(qs, many=True).data)
        tranches = request.data.get('tranches') or []
        if not isinstance(tranches, list) or not tranches:
            return Response(
                {'detail': 'Au moins une tranche est requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        for t in tranches:
            if not t.get('date_echeance'):
                return Response(
                    {'detail': 'Chaque tranche doit porter une date '
                               "d'échéance."},
                    status=status.HTTP_400_BAD_REQUEST)
        from ..services import creer_echeancier_facture_fournisseur
        created = creer_echeancier_facture_fournisseur(
            request.user.company, facture, tranches)
        return Response(
            EcheanceFactureFournisseurSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED)
