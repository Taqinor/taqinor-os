from django.db import transaction
from django.db.models import ProtectedError, Count, Min, Max
from django.http import HttpResponse
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from apps.ventes.utils.references import create_with_reference
from .models import (
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur,
)
from .serializers import (
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
)
from authentication.permissions import (
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


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
        from .services import BULK_ACTIONS, apply_product_bulk
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
        from .services import apply_inventory_count
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
        from .services import export_products_xlsx
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
        from .services import stock_valuation_by_location
        return Response(stock_valuation_by_location(request.user.company))

    @action(detail=False, methods=['get'], url_path='valorisation-xlsx',
            permission_classes=[IsAdminRole])
    def valorisation_xlsx(self, request):
        """Export Excel de la valorisation du stock (admin/INTERNE) —
        les prix d'achat/coûts ne sont jamais client-facing."""
        from .services import export_valorisation_xlsx
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
        from .services import stock_breakdown
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
        from . import labels
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
        from . import labels

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
            from apps.installations.models import Installation
            inst = (Installation.objects
                    .filter(company=request.user.company, id=obj_id)
                    .select_related('client')
                    .first())
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
            from apps.installations.models import Intervention
            itv = (Intervention.objects
                   .filter(company=request.user.company, id=obj_id)
                   .select_related('installation', 'installation__client')
                   .first())
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


def seed_marques(company):
    """Amorce le référentiel Marque depuis les marques déjà saisies sur les
    produits (idempotent, additif). N'écrase rien."""
    if company is None:
        return
    existing = set(Marque.objects.filter(company=company)
                   .values_list('nom', flat=True))
    used = (Produit.objects.filter(company=company)
            .exclude(marque__isnull=True).exclude(marque='')
            .values_list('marque', flat=True).distinct())
    for nom in used:
        if nom not in existing:
            Marque.objects.get_or_create(company=company, nom=nom)


class MarqueViewSet(TenantMixin, viewsets.ModelViewSet):
    """Marques produit gérées (Paramètres → Stock). Lecture tout rôle, écriture
    admin. Une marque utilisée par des produits ne peut pas être supprimée."""
    queryset = Marque.objects.all()
    serializer_class = MarqueSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        if request.user.company_id:
            seed_marques(request.user.company)
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        marque = self.get_object()
        if Produit.objects.filter(company=marque.company, marque=marque.nom).exists():
            return Response(
                {'detail': "Cette marque est utilisée par des produits — "
                           "archivez-la plutôt."},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)


class CategorieViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


class FournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email', 'contact_personne']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


class MouvementStockViewSet(viewsets.ModelViewSet):
    queryset = MouvementStock.objects.select_related(
        'produit', 'created_by'
    ).all()
    serializer_class = MouvementStockSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['produit__nom', 'reference', 'note']
    ordering_fields = ['date', 'type_mouvement', 'quantite']
    ordering = ['-date']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'create':
            return [HasPermissionOrLegacy('stock_mouvement')()]
        else:
            return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            # Direct company filter + produit__company belt-and-braces guard
            # against cross-tenant produit references slipping in.
            return qs.filter(company=user.company, produit__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        produit = serializer.validated_data['produit']
        user = self.request.user
        # Reject cross-tenant produit references before touching stock.
        if user.company_id and produit.company_id != user.company_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Produit hors de votre entreprise.")
        produit.refresh_from_db()
        qte = serializer.validated_data['quantite']
        type_mv = serializer.validated_data['type_mouvement']
        qte_avant = produit.quantite_stock
        if type_mv == MouvementStock.TypeMouvement.ENTREE:
            qte_apres = qte_avant + qte
        elif type_mv == MouvementStock.TypeMouvement.SORTIE:
            qte_apres = qte_avant - qte
        else:
            qte_apres = qte
        serializer.save(
            created_by=user,
            company=produit.company,
            quantite_avant=qte_avant,
            quantite_apres=qte_apres,
        )
        produit.quantite_stock = qte_apres
        produit.save(update_fields=['quantite_stock'])


class PrixFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """N17 — prix d'achat multi-fournisseurs par SKU (INTERNE). Lecture tout
    rôle, écriture stock_modifier. `company` posé serveur ; produit/fournisseur
    doivent appartenir à la société."""
    queryset = PrixFournisseur.objects.select_related(
        'produit', 'fournisseur').all()
    serializer_class = PrixFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['prix_achat', 'date_dernier_achat']
    ordering = ['prix_achat']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [HasPermissionOrLegacy('stock_modifier')()]

    def get_queryset(self):
        qs = super().get_queryset()
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        return qs

    def _check_company(self, serializer):
        company = self.request.user.company
        produit = serializer.validated_data.get('produit')
        fournisseur = serializer.validated_data.get('fournisseur')
        from rest_framework.exceptions import ValidationError
        if produit is not None and produit.company_id != getattr(
                company, 'id', None):
            raise ValidationError({'produit': 'Produit hors de votre entreprise.'})
        if fournisseur is not None and fournisseur.company_id != getattr(
                company, 'id', None):
            raise ValidationError(
                {'fournisseur': 'Fournisseur hors de votre entreprise.'})

    def perform_create(self, serializer):
        self._check_company(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_company(serializer)
        serializer.save(company=self.request.user.company)


class EmplacementStockViewSet(TenantMixin, viewsets.ModelViewSet):
    """N15 — emplacements de stock (dépôt principal + camionnette amorcés au
    premier accès). Lecture tout rôle, écriture admin. Le principal ne peut être
    ni supprimé ni archivé ; un emplacement détenant du stock ne peut pas être
    supprimé (transférez d'abord)."""
    queryset = EmplacementStock.objects.all()
    serializer_class = EmplacementStockSerializer
    ordering = ['-is_principal', 'ordre', 'nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        from .services import ensure_emplacements
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


class TransfertStockViewSet(TenantMixin, viewsets.ModelViewSet):
    """N15 — transferts de stock entre emplacements (le « transfer record »).

    Lecture seule + création. La création passe par le service `transfer_stock`
    (validation + atomicité), jamais par un save direct. Le total
    `Produit.quantite_stock` n'est jamais modifié par un transfert."""
    queryset = TransfertStock.objects.select_related(
        'produit', 'source', 'destination', 'created_by').all()
    serializer_class = TransfertStockSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['produit__nom', 'note']
    ordering_fields = ['date', 'quantite']
    ordering = ['-date']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action == 'create':
            return [HasPermissionOrLegacy('stock_mouvement')()]
        return [IsAdminRole()]

    def create(self, request, *args, **kwargs):
        from .services import transfer_stock
        try:
            transfert = transfer_stock(
                company=request.user.company, user=request.user,
                produit_id=request.data.get('produit'),
                source_id=request.data.get('source'),
                destination_id=request.data.get('destination'),
                quantite=request.data.get('quantite'),
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(transfert).data,
                        status=status.HTTP_201_CREATED)


class RetourFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """N19 — retours fournisseur (articles défectueux / erronés). Numérotation
    sans trou (préfixe RF). La validation DÉCRÉMENTE le stock via MouvementStock
    (SORTIE). Usage INTERNE."""
    queryset = RetourFournisseur.objects.select_related(
        'fournisseur', 'bon_commande', 'created_by',
    ).prefetch_related('lignes__produit').all()
    serializer_class = RetourFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'fournisseur__nom', 'motif']
    ordering_fields = ['date_creation', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['valider', 'annuler']:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(RetourFournisseur, 'RF', company, _save)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide le retour : décrémente le stock (SORTIE) pour chaque ligne.
        Idempotent : un retour déjà validé/annulé ne re-décrémente jamais."""
        from .services import apply_retour_fournisseur
        retour = self.get_object()
        try:
            apply_retour_fournisseur(retour, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(retour).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        retour = self.get_object()
        if retour.statut == RetourFournisseur.Statut.VALIDE:
            return Response(
                {'detail': 'Un retour validé ne peut pas être annulé '
                           '(le stock a déjà été décrémenté).'},
                status=status.HTTP_400_BAD_REQUEST)
        retour.statut = RetourFournisseur.Statut.ANNULE
        retour.save(update_fields=['statut'])
        return Response(self.get_serializer(retour).data)


class BonCommandeFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """Bons de commande fournisseur (achats). Distinct du BC CLIENT de ventes.

    - référence numérotée sans trou (préfixe BCF) via references.py ;
    - réceptions partielles : l'action `recevoir` incrémente le stock via
      MouvementStock (ENTREE) pour les quantités reçues uniquement ;
    - les prix d'ACHAT restent internes (jamais sur un document client).
    """
    queryset = BonCommandeFournisseur.objects.select_related(
        'fournisseur', 'created_by',
    ).prefetch_related('lignes__produit').all()
    serializer_class = BonCommandeFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'fournisseur__nom', 'note']
    ordering_fields = ['date_creation', 'date_commande', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'envoyer', 'recevoir', 'annuler', 'generer_pdf',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(
            BonCommandeFournisseur, 'BCF', company, _save)

    @action(detail=True, methods=['post'], url_path='envoyer')
    def envoyer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommandeFournisseur.Statut.BROUILLON:
            return Response(
                {'detail': 'Seul un BCF en brouillon peut être envoyé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.ENVOYE
        bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        bc = self.get_object()
        if bc.statut == BonCommandeFournisseur.Statut.RECU:
            return Response(
                {'detail': 'Un BCF entièrement reçu ne peut pas être annulé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommandeFournisseur.Statut.ANNULE
        bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['post'], url_path='recevoir')
    def recevoir(self, request, pk=None):
        """Réception (totale ou partielle) — incrémente le stock par ENTREE.

        Corps : {"receptions": [{"ligne": <id>, "quantite": <int>}, ...]}.
        Idempotent/sûr : on ne reçoit jamais plus que le reste dû ; le stock
        n'augmente que des quantités effectivement reçues.
        """
        bc = self.get_object()
        if bc.statut in (
            BonCommandeFournisseur.Statut.BROUILLON,
            BonCommandeFournisseur.Statut.ANNULE,
            BonCommandeFournisseur.Statut.RECU,
        ):
            return Response(
                {'detail': (
                    'Seul un BCF envoyé (non encore entièrement reçu) '
                    'peut recevoir des quantités.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receptions = request.data.get('receptions') or []
        if not isinstance(receptions, list) or not receptions:
            return Response(
                {'detail': 'Aucune réception fournie.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Index par id de ligne (scopé à ce BC uniquement).
        lignes = {ligne.id: ligne for ligne in bc.lignes.select_related(
            'produit')}
        plan = []
        for rec in receptions:
            try:
                ligne_id = int(rec.get('ligne'))
                qte = int(rec.get('quantite'))
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'Réception invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ligne = lignes.get(ligne_id)
            if ligne is None:
                return Response(
                    {'detail': f'Ligne {ligne_id} introuvable sur ce BCF.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if qte <= 0:
                continue
            # Plafonnement au reste dû — jamais plus que commandé (idempotence).
            qte = min(qte, ligne.quantite_restante)
            if qte > 0:
                plan.append((ligne, qte))

        if not plan:
            return Response(
                {'detail': 'Rien à recevoir (quantités déjà reçues).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        from .services import record_purchase_price
        today = timezone.now().date()
        with transaction.atomic():
            for ligne, qte in plan:
                produit = ligne.produit
                produit.refresh_from_db()
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant + qte
                MouvementStock.objects.create(
                    company=bc.company,
                    produit=produit,
                    type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                    quantite=qte,
                    quantite_avant=qte_avant,
                    quantite_apres=qte_apres,
                    reference=bc.reference,
                    note=f'Réception BCF {bc.reference}',
                    created_by=request.user,
                )
                produit.quantite_stock = qte_apres
                produit.save(update_fields=['quantite_stock'])
                ligne.quantite_recue += qte
                ligne.save(update_fields=['quantite_recue'])
                # N17 — mémorise le prix d'achat (interne) chez ce fournisseur.
                record_purchase_price(
                    company=bc.company, produit=produit,
                    fournisseur=bc.fournisseur,
                    prix_achat=ligne.prix_achat_unitaire, date=today)
            bc.refresh_from_db()
            if bc.est_entierement_recu:
                bc.statut = BonCommandeFournisseur.Statut.RECU
                bc.save(update_fields=['statut'])
        return Response(self.get_serializer(bc).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def generer_pdf(self, request, pk=None):
        """PDF fournisseur (INTERNE — montre les prix d'achat). Jamais un
        document client."""
        from .utils.pdf_fournisseur import generate_bcf_pdf
        bc = self.get_object()
        pdf_bytes = generate_bcf_pdf(bc)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{bc.reference}.pdf"')
        return response
