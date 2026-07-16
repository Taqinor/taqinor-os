from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
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


class ReceptionFournisseurViewSet(CompanyScopedModelViewSet):
    """G5 — Réceptions fournisseur (goods-in / entrée de marchandises).

    Numérotation sans trou (préfixe REC). La confirmation incrémente le stock
    via MouvementStock (ENTREE) pour chaque ligne reçue, avance les quantités
    reçues du BCF et son statut, et reste IDEMPOTENTE (une réception confirmée
    ne re-crée jamais de mouvement). Usage INTERNE."""
    queryset = ReceptionFournisseur.objects.select_related(
        'bon_commande', 'bon_commande__fournisseur', 'recu_par', 'created_by',
    ).prefetch_related('lignes__produit').all()
    serializer_class = ReceptionFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'bon_commande__reference',
        'bon_commande__fournisseur__nom', 'note',
    ]
    ordering_fields = ['date_creation', 'date_reception', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['scan_gs1', 'etiquettes']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['confirmer', 'annuler', 'facturer']:
            # « facturer » déclarait IsResponsableOrAdmin sur son décorateur
            # mais ce get_permissions l'écrasait vers IsAdminRole (le repli
            # par défaut) — bug préexistant attrapé par le test P2P YTEST6.
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        bon_id = self.request.query_params.get('bon_commande')
        if bon_id:
            qs = qs.filter(bon_commande_id=bon_id)
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
        create_with_reference(ReceptionFournisseur, 'REC', company, _save)

    @action(detail=False, methods=['get'], url_path='scan-gs1')
    def scan_gs1(self, request):
        """XSTK4 — décompose un code GS1-128/DataMatrix (query param
        ``code``) et résout le produit via le GTIN (= `Produit.code_barres`,
        XSTK3), scopé société. Renvoie ``{produit_id, numeros_serie,
        numero_lot, date_peremption}`` prêt à préremplir la ligne de
        réception (``LigneReceptionFournisseur``). GTIN inconnu → 404
        propre ; code sans AI '01' reconnu → 400 (code illisible)."""
        from ..gs1 import parse_gs1

        code = (request.query_params.get('code') or '').strip()
        if not code:
            return Response(
                {'detail': 'Code illisible.'},
                status=status.HTTP_400_BAD_REQUEST)

        parsed = parse_gs1(code)
        gtin = parsed.get('gtin')
        if not gtin:
            return Response(
                {'detail': 'Code illisible.'},
                status=status.HTTP_400_BAD_REQUEST)

        produit = Produit.objects.filter(
            company=request.user.company, code_barres=gtin).first()
        if produit is None:
            return Response(
                {'detail': 'Produit introuvable pour ce GTIN.'},
                status=status.HTTP_404_NOT_FOUND)

        serie = parsed.get('serie')
        return Response({
            'produit_id': produit.id,
            'produit_nom': produit.nom,
            'numeros_serie': [serie] if serie else None,
            'numero_lot': parsed.get('lot'),
            'date_peremption': (
                parsed['date_peremption'].isoformat()
                if parsed.get('date_peremption') else None),
        })

    @action(detail=True, methods=['get'], url_path='etiquettes')
    def etiquettes(self, request, pk=None):
        """ZSTK6 — planche d'étiquettes lot/série depuis les lignes de CETTE
        réception : une étiquette PAR série reçue (`numeros_serie`, jeton
        `SERIE:<produit>:<valeur>`) + une PAR lot renseigné (`numero_lot`,
        jeton `LOT:<produit>:<valeur>`). Réutilise le moteur N20
        (`labels.render_labels_html`) — jamais de prix affiché.

        Paramètres : ``symbology`` (qr défaut | code128), ``sortie`` (pdf
        défaut | html)."""
        from .. import labels
        from apps.ventes.utils.pdf import _html_to_pdf

        reception = self.get_object()
        symbology = request.query_params.get('symbology', 'qr')
        if symbology not in ('qr', 'code128'):
            symbology = 'qr'

        items = []
        for ligne in reception.lignes.select_related('produit').all():
            if ligne.produit_id is None:
                continue
            nom = ligne.produit.nom
            for serie in (ligne.numeros_serie or []):
                if not serie:
                    continue
                items.append({
                    'token': labels.serie_token(ligne.produit_id, serie),
                    'titre': nom,
                    'sous_titre': f'N° série {serie}',
                })
            if ligne.numero_lot:
                items.append({
                    'token': labels.lot_token(
                        ligne.produit_id, ligne.numero_lot),
                    'titre': nom,
                    'sous_titre': f'Lot {ligne.numero_lot}',
                })
        if not items:
            return Response(
                {'detail': 'Aucun n° de série/lot sur cette réception.'},
                status=status.HTTP_404_NOT_FOUND)

        html = labels.render_labels_html(items, symbology=symbology)
        if request.query_params.get('sortie') == 'html':
            return HttpResponse(html, content_type='text/html; charset=utf-8')
        pdf_bytes = _html_to_pdf(html)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="etiquettes-{reception.reference}.pdf"')
        return response

    @action(detail=True, methods=['post'], url_path='confirmer')
    def confirmer(self, request, pk=None):
        """Confirme la réception : incrémente le stock (ENTREE) pour chaque
        ligne reçue et avance le statut du BCF. Idempotent : une réception déjà
        confirmée ne re-crée jamais de mouvement."""
        from ..services import confirm_reception_fournisseur
        reception = self.get_object()
        try:
            confirm_reception_fournisseur(reception, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(reception).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """YSTCK6 — une réception CONFIRMÉE est annulée par CONTRE-PASSATION
        (mouvement de reversal référencé à l'original, jamais un blocage) via
        `annuler_reception_confirmee`. Une réception encore en brouillon
        garde le chemin historique (simple passage à ANNULE, rien à
        contre-passer)."""
        from ..services import annuler_reception_confirmee
        reception = self.get_object()
        if reception.statut == ReceptionFournisseur.Statut.CONFIRME:
            try:
                annuler_reception_confirmee(reception, request.user)
            except ValueError as exc:
                return Response({'detail': str(exc)},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response(self.get_serializer(reception).data)
        reception.statut = ReceptionFournisseur.Statut.ANNULE
        reception.save(update_fields=['statut'])
        return Response(self.get_serializer(reception).data)

    @action(detail=True, methods=['post'], url_path='facturer',
            permission_classes=[IsResponsableOrAdmin])
    def facturer(self, request, pk=None):
        """FG56 — Crée une FactureFournisseur à partir de cette réception
        confirmée. Calcule HT/TVA/TTC depuis les lignes BCF. INTERNE."""
        from ..services import facturer_reception
        reception = self.get_object()
        try:
            facture = facturer_reception(
                company=request.user.company,
                user=request.user,
                reception=reception)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            FactureFournisseurSerializer(
                facture, context={'request': request}).data,
            status=status.HTTP_201_CREATED)
