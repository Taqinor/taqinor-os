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
        if self.action in ('van_stock_mon_stock', 'van_stock_signaler_manquant'):
            # NTFSM20 — écran mobile du TECHNICIEN : il lit le stock de SA
            # camionnette et y signale un manquant. Même piège que
            # `etiquettes_kanban` ci-dessus : `get_permissions` prime sur le
            # `permission_classes=[IsAnyRole]` posé sur l'@action, donc sans
            # ce cas explicite un technicien (rôle « normal ») recevait 403.
            # L'emplacement reste résolu CÔTÉ SERVEUR (jamais un id client),
            # donc ouvrir la garde n'ouvre pas la camionnette d'un collègue.
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        """NTWMS19 — filtre `?type_proprietaire=interne|chez_tiers|de_tiers`
        et `?tiers_nom=` (le filtrage est manuel : aucun backend de filtre
        DRF n'est installé sur ce projet, `filterset_fields` y serait un
        no-op silencieux)."""
        qs = super().get_queryset()
        params = self.request.query_params
        type_proprietaire = params.get('type_proprietaire')
        if type_proprietaire:
            qs = qs.filter(type_proprietaire=type_proprietaire)
        tiers_nom = params.get('tiers_nom')
        if tiers_nom:
            qs = qs.filter(tiers_nom__icontains=tiers_nom)
        return qs

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

    @action(detail=False, methods=['get'], url_path='van-stock/a-reapprovisionner',
            permission_classes=[IsAnyRole])
    def van_stock_a_reapprovisionner(self, request):
        """NTFSM19 — écarts van-stock (camionnette) sous seuil, avec la
        quantité suggérée à transférer depuis le dépôt principal."""
        from ..selectors import van_stock_a_reapprovisionner
        return Response(van_stock_a_reapprovisionner(request.user.company))

    @action(detail=False, methods=['post'], url_path='van-stock/creer-transfert',
            permission_classes=[IsResponsableOrAdmin])
    def van_stock_creer_transfert(self, request):
        """NTFSM19 — crée (ou renvoie, sans dupliquer) la demande de transfert
        dépôt principal → camionnette qui comble l'écart sous seuil pour
        {produit_id, emplacement_id}."""
        from ..selectors import van_stock_a_reapprovisionner
        from ..services_transfert_deux_temps import creer_demande_transfert

        company = request.user.company
        produit_id = request.data.get('produit_id')
        emplacement_id = request.data.get('emplacement_id')
        if not produit_id or not emplacement_id:
            return Response(
                {'detail': 'produit_id et emplacement_id requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        # Idempotence : une demande DÉJÀ en attente pour ce (produit,
        # camionnette) n'est jamais dupliquée.
        en_attente = [TransfertStock.Statut.DEMANDE, TransfertStock.Statut.EXPEDIE]
        existante = (TransfertStock.objects
                     .filter(company=company, produit_id=produit_id,
                             destination_id=emplacement_id,
                             statut__in=en_attente)
                     .order_by('-date')
                     .first())
        if existante is not None:
            return Response(TransfertStockSerializer(existante).data)

        ecarts = {
            (e['produit_id'], e['emplacement_id']): e
            for e in van_stock_a_reapprovisionner(company)
        }
        try:
            cle = (int(produit_id), int(emplacement_id))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'produit_id/emplacement_id invalides.'},
                status=status.HTTP_400_BAD_REQUEST)
        ecart = ecarts.get(cle)
        if ecart is None or not ecart.get('source_id'):
            return Response(
                {'detail': 'Aucun écart sous seuil pour ce produit sur '
                           'cette camionnette.'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            transfert = creer_demande_transfert(
                company=company, user=request.user, produit_id=produit_id,
                source_id=ecart['source_id'], destination_id=emplacement_id,
                quantite=ecart['qte_suggere_transfert'],
                note='Réappro van-stock automatique (NTFSM19)')
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TransfertStockSerializer(transfert).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='van-stock/mon-stock',
            permission_classes=[IsAnyRole])
    def van_stock_mon_stock(self, request):
        """NTFSM20 — stock de la CAMIONNETTE affectée au technicien connecté
        (jamais celui d'un collègue — l'emplacement est résolu côté serveur,
        jamais accepté depuis le client). Aucune camionnette affectée :
        réponse propre (emplacement null, produits vides)."""
        from ..models import StockEmplacement
        from ..selectors import emplacement_camionnette_technicien

        company = request.user.company
        emplacement = emplacement_camionnette_technicien(company, request.user)
        if emplacement is None:
            return Response({'emplacement': None, 'produits': []})

        lignes = (StockEmplacement.objects
                  .filter(company=company, emplacement=emplacement)
                  .select_related('produit')
                  .order_by('produit__nom'))
        produits = [{
            'produit_id': ligne.produit_id,
            'nom': ligne.produit.nom,
            'sku': ligne.produit.sku,
            'quantite': ligne.quantite,
            'seuil_min': ligne.seuil_min,
            'seuil_max': ligne.seuil_max,
        } for ligne in lignes]
        return Response({
            'emplacement': {'id': emplacement.id, 'nom': emplacement.nom},
            'produits': produits,
        })

    @action(detail=False, methods=['post'], url_path='van-stock/signaler-manquant',
            permission_classes=[IsAnyRole])
    def van_stock_signaler_manquant(self, request):
        """NTFSM20 — le technicien signale un produit manquant sur SA
        camionnette : crée une demande de transfert (NTFSM19) sans attendre
        le job de réappro automatique. Body {produit_id}. Jamais sur la
        camionnette d'un collègue (emplacement résolu côté serveur)."""
        from ..services_transfert_deux_temps import creer_demande_transfert
        from ..selectors import emplacement_camionnette_technicien

        company = request.user.company
        emplacement = emplacement_camionnette_technicien(company, request.user)
        if emplacement is None:
            return Response(
                {'detail': 'Aucune camionnette ne vous est affectée.'},
                status=status.HTTP_400_BAD_REQUEST)

        produit_id = request.data.get('produit_id')
        if not produit_id:
            return Response(
                {'detail': 'produit_id requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        principal = EmplacementStock.objects.filter(
            company=company, is_principal=True).first()
        if principal is None:
            return Response(
                {'detail': 'Aucun dépôt principal configuré.'},
                status=status.HTTP_400_BAD_REQUEST)

        en_attente = [TransfertStock.Statut.DEMANDE, TransfertStock.Statut.EXPEDIE]
        existante = (TransfertStock.objects
                     .filter(company=company, produit_id=produit_id,
                             destination=emplacement,
                             statut__in=en_attente)
                     .order_by('-date')
                     .first())
        if existante is not None:
            return Response(TransfertStockSerializer(existante).data)

        from ..models import StockEmplacement
        ligne = StockEmplacement.objects.filter(
            company=company, produit_id=produit_id,
            emplacement=emplacement).first()
        quantite = 1
        if ligne is not None and ligne.seuil_max:
            manque = ligne.seuil_max - ligne.quantite
            if manque > 0:
                quantite = manque
        elif ligne is not None and ligne.seuil_min:
            manque = ligne.seuil_min - ligne.quantite
            if manque > 0:
                quantite = manque

        try:
            transfert = creer_demande_transfert(
                company=company, user=request.user, produit_id=produit_id,
                source_id=principal.id, destination_id=emplacement.id,
                quantite=quantite,
                note='Signalé manquant par le technicien (NTFSM20)')
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TransfertStockSerializer(transfert).data,
            status=status.HTTP_201_CREATED)

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
