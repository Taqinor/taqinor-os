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
    PaiementFournisseur, CategorieFournisseur, ContactFournisseur,
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
    CategorieFournisseurSerializer,
    ContactFournisseurSerializer,
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


class FournisseurViewSet(CompanyScopedModelViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email', 'contact_personne']
    ordering = ['nom']
    # YAPIC2 — whitelist explicite (jamais '__all__').
    ordering_fields = ['nom', 'type', 'statut', 'email']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'performance':
            # XPUR7 — rapport de performance fournisseur (OTD…) : lecture, ouvert
            # à tout rôle porteur du droit de lecture stock (get_permissions
            # prime sur le permission_classes de l'@action, d'où ce cas explicite).
            return [HasPermissionOrLegacy('stock_voir')()]
        elif self.action in ('portail_tokens', 'revoquer_portail_token'):
            # XPUR22 — gestion des jetons portail fournisseur : écriture Stock,
            # ouverte à tout rôle porteur du droit `stock_modifier` (get_permissions
            # prime sur le permission_classes de l'@action, d'où ce cas explicite).
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        # L699 — annote les compteurs (produits liés + BCF associés) en lecture
        # pour la fiche/liste fournisseur, sans N+1.
        qs = super().get_queryset()
        if self.action in READ_ACTIONS:
            qs = qs.annotate(
                nb_produits_annot=Count('produits', distinct=True),
                nb_bons_commande_annot=Count('bons_commande', distinct=True),
            )
        # XPUR5 — filtre liste par catégorie fournisseur.
        categorie_id = self.request.query_params.get('categorie')
        if categorie_id:
            qs = qs.filter(categorie_id=categorie_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def create(self, request, *args, **kwargs):
        # XPUR5 — doublon ICE (warning non bloquant) ajouté à la réponse.
        response = super().create(request, *args, **kwargs)
        self._attach_ice_warning(response, request)
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        self._attach_ice_warning(response, request)
        return response

    def _attach_ice_warning(self, response, request):
        if response.status_code not in (200, 201):
            return
        try:
            from ..services import find_duplicate_ice
            ice = response.data.get('ice')
            if not ice:
                return
            dup = find_duplicate_ice(
                request.user.company, ice, exclude_id=response.data.get('id'))
            if dup is not None:
                response.data['ice_duplicate_warning'] = (
                    f"Attention : l'ICE {ice} est déjà utilisé par "
                    f'« {dup.nom} ».')
        except Exception:  # noqa: BLE001 — le warning ne casse jamais
            pass

    @action(detail=True, methods=['get'], url_path='performance',
            permission_classes=[HasPermissionOrLegacy('stock_voir')])
    def performance(self, request, *args, **kwargs):
        """FG59 — Scorecard performance fournisseur : délai moyen, taux de
        remplissage, taux de retour, dépenses totales, OTD (XPUR7).
        Lecture Stock. INTERNE."""
        from ..services import supplier_performance
        fournisseur = self.get_object()
        return Response(supplier_performance(request.user.company, fournisseur))

    @action(detail=True, methods=['get', 'post'], url_path='portail-tokens',
            permission_classes=[HasPermissionOrLegacy('stock_modifier')])
    def portail_tokens(self, request, *args, **kwargs):
        """XPUR22 — GET : liste les jetons portail de ce fournisseur (tous,
        y compris révoqués/expirés, pour audit). POST : génère un NOUVEAU
        jeton (l'URL publique est construite côté frontend depuis le
        token)."""
        from ..serializers import PortailFournisseurTokenSerializer
        fournisseur = self.get_object()
        if request.method.lower() == 'get':
            tokens = fournisseur.portail_tokens.order_by('-created_at')
            return Response(
                PortailFournisseurTokenSerializer(tokens, many=True).data)
        from ..services import generer_token_portail_fournisseur
        token_obj = generer_token_portail_fournisseur(
            request.user.company, fournisseur, request.user)
        return Response(
            PortailFournisseurTokenSerializer(token_obj).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'],
            url_path='portail-tokens/(?P<token_id>[^/.]+)/revoquer',
            permission_classes=[HasPermissionOrLegacy('stock_modifier')])
    def revoquer_portail_token(self, request, token_id=None, *args, **kwargs):
        """XPUR22 — révoque un jeton portail (le lien cesse immédiatement de
        fonctionner)."""
        from ..models import PortailFournisseurToken
        from ..serializers import PortailFournisseurTokenSerializer
        from ..services import revoquer_token_portail_fournisseur
        fournisseur = self.get_object()
        token_obj = PortailFournisseurToken.objects.filter(
            pk=token_id, fournisseur=fournisseur,
            company=request.user.company).first()
        if token_obj is None:
            return Response(
                {'detail': 'Jeton introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        revoquer_token_portail_fournisseur(token_obj)
        return Response(PortailFournisseurTokenSerializer(token_obj).data)


class ContactFournisseurViewSet(CompanyScopedModelViewSet):
    """XPUR5 — contacts secondaires d'un fournisseur (N par fournisseur)."""
    queryset = ContactFournisseur.objects.select_related('fournisseur').all()
    serializer_class = ContactFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['fournisseur_id', 'nom']
    # YAPIC2 — whitelist explicite (jamais '__all__').
    ordering_fields = ['fournisseur_id', 'nom', 'fonction']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [HasPermissionOrLegacy('stock_modifier')()]

    def get_queryset(self):
        qs = super().get_queryset()
        fournisseur_id = self.request.query_params.get('fournisseur')
        if fournisseur_id:
            qs = qs.filter(fournisseur_id=fournisseur_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class CategorieFournisseurViewSet(CompanyScopedModelViewSet):
    """XPUR5 — référentiel léger de catégories fournisseur (type Marque)."""
    queryset = CategorieFournisseur.objects.all()
    serializer_class = CategorieFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['nom']
    # YAPIC2 — whitelist explicite (jamais '__all__').
    ordering_fields = ['nom', 'archived']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [HasPermissionOrLegacy('stock_modifier')()]

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)
