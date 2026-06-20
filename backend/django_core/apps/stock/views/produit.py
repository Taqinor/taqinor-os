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


class ProduitViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Produit.objects.select_related(
        'categorie', 'fournisseur'
    ).all()
    serializer_class = ProduitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'sku', 'description', 'categorie__nom']
    ordering_fields = [
        'nom', 'quantite_stock', 'prix_vente', 'date_creation'
    ]
    ordering = ['nom']

    def get_permissions(self):
        # Écritures Stock : permission ERP granulaire (rôles fins type
        # « Commerciale » = lecture seule) avec comportement historique
        # pour les comptes hérités sans rôle fin.
        if self.action in READ_ACTIONS + ['export_xlsx']:
            return [IsAnyRole()]
        elif self.action == 'create':
            return [HasPermissionOrLegacy('stock_creer')()]
        elif self.action in WRITE_ACTIONS + ['bulk']:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action in ('destroy', 'force_delete'):
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('show_archived') == 'true':
            return qs.annotate(
                nb_mouvements=Count('mouvements'),
                premiere_date_mouvement=Min('mouvements__date'),
                derniere_date_mouvement=Max('mouvements__date'),
            )
        if self.action in ('force_delete', 'unarchive'):
            return qs  # archived products must be visible for these actions
        return qs.filter(is_archived=False)

    def destroy(self, request, *args, **kwargs):
        produit = self.get_object()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            nb = produit.mouvements.count()
            produit.is_archived = True
            produit.save(update_fields=['is_archived'])
            return Response(
                {
                    'archived': True,
                    'detail': (
                        f'Ce produit a été archivé car il possède {nb} '
                        f'mouvement(s) de stock. L\'historique est conservé.'
                    ),
                    'nb_mouvements': nb,
                },
                status=status.HTTP_200_OK,
            )

    @action(detail=False, methods=['post'], url_path='bulk',
            permission_classes=[HasPermissionOrLegacy('stock_modifier')])
    def bulk(self, request):
        """Édition en masse d'une sélection de produits (prix %/fixe, garantie,
        catégorie, marque). Le prix d'achat n'est jamais modifié."""
        from ..services import BULK_ACTIONS, apply_product_bulk
        op = request.data.get('action')
        ids = request.data.get('ids') or []
        if op not in BULK_ACTIONS:
            return Response({'detail': 'Action en masse inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Sélectionnez au moins un produit.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            result = apply_product_bulk(
                company=request.user.company, user=request.user,
                ids=ids, op=op, params=request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=False, methods=['post'], url_path='inventaire',
            permission_classes=[IsAdminRole])
    def inventaire(self, request):
        """N16 — inventaire physique : pose un comptage par produit et publie
        l'écart en ajustement de stock (audité). Réservé admin.

        Corps : {"motif": <str>, "lignes": [{"produit": <id>,
                 "quantite_comptee": <int>}]}.
        """
        from ..services import apply_inventory_count
        lignes = request.data.get('lignes') or []
        if not isinstance(lignes, list) or not lignes:
            return Response({'detail': 'Aucune ligne de comptage fournie.'},
                            status=status.HTTP_400_BAD_REQUEST)
        result = apply_inventory_count(
            company=request.user.company, user=request.user,
            motif=request.data.get('motif'), lignes=lignes)
        return Response(result)

    @action(detail=False, methods=['post'], url_path='export-xlsx',
            permission_classes=[IsAnyRole])
    def export_xlsx(self, request):
        """Exporte une sélection de produits en .xlsx (prix d'achat exclu)."""
        from ..services import export_products_xlsx
        ids = request.data.get('ids') or []
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Sélectionnez au moins un produit.'},
                            status=status.HTTP_400_BAD_REQUEST)
        produits = (Produit.objects.filter(company=request.user.company, id__in=ids)
                    .select_related('categorie').order_by('nom'))
        return export_products_xlsx(produits)

    @action(detail=False, methods=['get'], url_path='valorisation',
            permission_classes=[IsAdminRole])
    def valorisation(self, request):
        """N18 — valorisation du stock par emplacement au coût moyen d'achat.
        INTERNE (admin) — les prix d'achat ne sont jamais client-facing."""
        from ..services import stock_valuation_by_location
        return Response(stock_valuation_by_location(request.user.company))

    @action(detail=False, methods=['get'], url_path='valorisation-xlsx',
            permission_classes=[IsAdminRole])
    def valorisation_xlsx(self, request):
        """Export Excel de la valorisation du stock (admin/INTERNE) —
        les prix d'achat/coûts ne sont jamais client-facing."""
        from ..services import export_valorisation_xlsx
        return export_valorisation_xlsx(request.user.company)

    @action(detail=True, methods=['get'], url_path='prix-fournisseurs',
            permission_classes=[IsAnyRole])
    def prix_fournisseurs(self, request, *args, **kwargs):
        """N17 — liste de prix multi-fournisseurs de ce produit (INTERNE),
        triée du moins cher au plus cher."""
        produit = self.get_object()
        qs = produit.prix_fournisseurs.select_related('fournisseur').order_by(
            'prix_achat')
        return Response(PrixFournisseurSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='emplacements',
            permission_classes=[IsAnyRole])
    def emplacements(self, request, *args, **kwargs):
        """N15 — ventilation du stock de ce produit par emplacement (le dépôt
        principal détient le reste = total − somme des autres)."""
        from ..services import stock_breakdown
        produit = self.get_object()
        return Response(stock_breakdown(produit))

    @action(detail=False, methods=['get'], url_path='etiquettes',
            permission_classes=[IsAnyRole])
    def etiquettes(self, request):
        """N20 — Étiquettes imprimables (QR/CODE128) pour une sélection de SKU.

        Encode un jeton stable `PRODUIT:<id>` + un texte LISIBLE (nom + SKU).
        Le jeton scanné est résolu par `resolve` (lecture seule). On n'imprime
        JAMAIS de prix d'achat / marge — uniquement nom + SKU + jeton.

        Paramètres :
          - ``ids`` : liste d'identifiants (répétée ou séparée par virgules) ;
          - ``symbology`` : ``qr`` (défaut) | ``code128`` ;
          - ``sortie`` : ``html`` (aperçu) | ``pdf`` (défaut). On utilise
            ``sortie`` et non ``format`` (réservé par DRF).
        """
        from .. import labels
        from apps.ventes.utils.pdf import _html_to_pdf

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
        items = [{
            'token': labels.produit_token(p.id),
            'titre': p.nom,
            'sous_titre': p.sku or '',
        } for p in produits]
        if not items:
            return Response({'detail': 'Aucun produit correspondant.'},
                            status=status.HTTP_404_NOT_FOUND)

        html = labels.render_labels_html(items, symbology=symbology)
        if request.query_params.get('sortie') == 'html':
            return HttpResponse(html, content_type='text/html; charset=utf-8')
        pdf_bytes = _html_to_pdf(html)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            'inline; filename="etiquettes-produits.pdf"')
        return response

    @action(detail=False, methods=['get'], url_path='resolve',
            permission_classes=[IsAnyRole])
    def resolve(self, request):
        """N20 — Résout un code scanné (`PRODUIT:<id>` / `SYSTEME:<id>`) vers
        l'enregistrement correspondant, STRICTEMENT scopé à la société.

        Lecture seule : ne modifie JAMAIS d'installation (import paresseux,
        aucune écriture). Renvoie ``{type, id, label, route}`` pour que le
        front navigue vers la bonne fiche, ou 404 si le code est inconnu /
        hors société."""
        from .. import labels

        code = (request.query_params.get('code') or '').strip()
        if not code or ':' not in code:
            return Response(
                {'detail': 'Code illisible.'},
                status=status.HTTP_400_BAD_REQUEST)
        prefix, _, raw_id = code.partition(':')
        prefix = prefix.strip().upper()
        raw_id = raw_id.strip()
        if not raw_id.isdigit():
            return Response(
                {'detail': 'Code illisible.'},
                status=status.HTTP_400_BAD_REQUEST)
        obj_id = int(raw_id)

        if prefix == labels.PRODUIT_PREFIX:
            produit = (Produit.objects
                       .filter(company=request.user.company, id=obj_id)
                       .first())
            if produit is None:
                return Response(
                    {'detail': 'Produit introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            return Response({
                'type': 'produit',
                'id': produit.id,
                'label': produit.nom,
                'sku': produit.sku or '',
                'route': '/stock',
            })

        if prefix == labels.SYSTEME_PREFIX:
            # Import paresseux : résolution en LECTURE SEULE, jamais d'écriture.
            from apps.installations.selectors import installation_scoped
            inst = installation_scoped(request.user.company, obj_id)
            if inst is None:
                return Response(
                    {'detail': 'Système installé introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            client_nom = getattr(inst.client, 'nom', '') if inst.client_id \
                else ''
            return Response({
                'type': 'systeme',
                'id': inst.id,
                'label': inst.reference,
                'client': client_nom,
                'statut': inst.statut,
                'route': '/chantiers',
            })

        if prefix == labels.INTERVENTION_PREFIX:
            # F23 — résolution LECTURE SEULE vers une intervention (sortie
            # chantier), scopée société. Import paresseux, aucune écriture.
            from apps.installations.selectors import intervention_scoped
            itv = intervention_scoped(request.user.company, obj_id)
            if itv is None:
                return Response(
                    {'detail': 'Intervention introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            inst = itv.installation
            client_nom = (getattr(inst.client, 'nom', '')
                          if inst and inst.client_id else '')
            return Response({
                'type': 'intervention',
                'id': itv.id,
                'label': itv.get_type_intervention_display(),
                'chantier': inst.reference if inst else '',
                'client': client_nom,
                'statut': itv.statut,
                'route': '/interventions',
            })

        return Response(
            {'detail': 'Type de code inconnu.'},
            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='unarchive')
    def unarchive(self, request, *args, **kwargs):
        produit = self.get_object()
        if not produit.is_archived:
            return Response(
                {'detail': 'Ce produit n\'est pas archivé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        produit.is_archived = False
        produit.save(update_fields=['is_archived'])
        serializer = self.get_serializer(produit)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'], url_path='force-delete')
    def force_delete(self, request, *args, **kwargs):
        produit = self.get_object()
        if not produit.is_archived:
            return Response(
                {
                    'detail': (
                        'Seuls les produits archivés peuvent être '
                        'supprimés définitivement.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        nb = produit.mouvements.count()
        produit.mouvements.all().delete()
        produit.delete()
        return Response(
            {
                'detail': (
                    f'Produit et {nb} mouvement(s) supprimé(s) définitivement.'
                )
            },
            status=status.HTTP_200_OK,
        )
