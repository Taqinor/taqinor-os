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


class EmplacementStockViewSet(CompanyScopedModelViewSet):
    """N15 — emplacements de stock (dépôt principal + camionnette amorcés au
    premier accès). Lecture tout rôle, écriture admin. Le principal ne peut être
    ni supprimé ni archivé ; un emplacement détenant du stock ne peut pas être
    supprimé (transférez d'abord)."""
    queryset = EmplacementStock.objects.all()
    serializer_class = EmplacementStockSerializer
    ordering = ['-is_principal', 'ordre', 'nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['etiquettes_kanban']:
            # XSTK20 — impression de cartes kanban : lecture seule, même
            # garde que les autres impressions d'étiquettes N20
            # (`get_permissions` prime sur le `permission_classes` de
            # l'@action, d'où ce cas explicite — sinon repli IsAdminRole).
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        from ..services import ensure_emplacements
        if request.user.company_id:
            ensure_emplacements(request.user.company)
        return super().list(request, *args, **kwargs)

    def _holds_stock(self, emplacement):
        return emplacement.stocks.filter(quantite__gt=0).exists()

    def destroy(self, request, *args, **kwargs):
        emp = self.get_object()
        if emp.is_principal:
            return Response(
                {'detail': 'Le dépôt principal ne peut pas être supprimé.'},
                status=status.HTTP_400_BAD_REQUEST)
        if self._holds_stock(emp):
            return Response(
                {'detail': 'Cet emplacement détient du stock — transférez-le '
                           'avant de le supprimer.'},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='suggestions-reappro',
            permission_classes=[IsAdminRole])
    def suggestions_reappro(self, request):
        """FG62 — Emplacements non-principaux dont le stock est sous seuil_min,
        avec suggestion de transfert depuis le dépôt principal. Admin-only."""
        from ..services import suggestions_reappro_emplacement
        return Response(suggestions_reappro_emplacement(request.user.company))

    @action(detail=True, methods=['get'], url_path='etiquettes-kanban')
    def etiquettes_kanban(self, request, *args, **kwargs):
        """XSTK20 — Cartes kanban deux-bacs pour CET emplacement : une carte
        par produit sélectionné (`?ids=<produit_id>,...`), jeton
        `KANBAN:<produit>:<emplacement>` (réutilise le moteur d'étiquettes
        N20). Affiche le seuil_max (FG62) = quantité de recomplètement, si
        défini. Lecture seule ; jamais de prix d'achat/marge."""
        from ..models import StockEmplacement
        from .. import labels
        from apps.ventes.utils.pdf import _html_to_pdf

        emplacement = self.get_object()
        ids = request.query_params.getlist('ids')
        if len(ids) == 1 and ',' in ids[0]:
            ids = ids[0].split(',')
        ids = [i for i in (str(x).strip() for x in ids) if i.isdigit()]
        if not ids:
            return Response({'detail': 'Sélectionnez au moins un produit.'},
                            status=status.HTTP_400_BAD_REQUEST)

        symbology = request.query_params.get('symbology', 'qr')
        if symbology not in ('qr', 'code128'):
            symbology = 'qr'

        produits = (Produit.objects
                    .filter(company=request.user.company, id__in=ids)
                    .order_by('nom'))
        seuils = {
            se.produit_id: se.seuil_max
            for se in StockEmplacement.objects.filter(
                company=request.user.company, emplacement=emplacement,
                produit_id__in=[p.id for p in produits])
        }
        items = []
        for p in produits:
            seuil_max = seuils.get(p.id)
            sous_titre = emplacement.nom
            if seuil_max:
                sous_titre = f'{emplacement.nom} — recompl. {seuil_max}'
            items.append({
                'token': labels.kanban_token(p.id, emplacement.id),
                'titre': p.nom,
                'sous_titre': sous_titre,
            })
        if not items:
            return Response({'detail': 'Aucun produit correspondant.'},
                            status=status.HTTP_404_NOT_FOUND)

        html = labels.render_labels_html(items, symbology=symbology)
        if request.query_params.get('sortie') == 'html':
            return HttpResponse(html, content_type='text/html; charset=utf-8')
        pdf_bytes = _html_to_pdf(html)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            'inline; filename="cartes-kanban.pdf"')
        return response
