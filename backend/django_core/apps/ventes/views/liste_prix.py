"""XSAL1/XSAL2/XSAL3 — Listes de prix clients, règles de paliers, et
l'endpoint de résolution de prix.

Endpoints :
  GET/POST      /ventes/listes-prix/                  list/create
  GET/PUT/PATCH /ventes/listes-prix/{id}/              retrieve/update
  DELETE        /ventes/listes-prix/{id}/              destroy
  POST          /ventes/listes-prix/{id}/lignes/       ajouter/mettre à jour un prix
  POST          /ventes/listes-prix/{id}/regles/       ajouter une règle de palier
  GET           /ventes/prix-applicable/?produit=&client=&quantite=

Écriture réservée responsable/admin (une liste de prix révisée agit sur les
devis de tous les vendeurs) ; lecture ouverte à tout rôle authentifié de la
société. `prix_achat` n'est JAMAIS lu ni exposé ici."""
from decimal import Decimal, InvalidOperation

from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet  # ARC5
from ..models import ListePrix, LignePrixListe
from ..serializers import (
    ListePrixSerializer, LignePrixListeSerializer, RegleListePrixSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class ListePrixViewSet(CompanyScopedModelViewSet):
    # ARC5 — sweep TenantMixin : base transverse unique. get_queryset /
    # perform_create / get_permissions SURCHARGENT la base (scoping direct sur
    # `company`) : scoping et matrice 401/403/404 INCHANGÉS. `prix_achat` jamais
    # lu ni exposé ici (règle produit). L'@api_view `prix_applicable_view` reste
    # une fonction hors socle (non-ViewSet, hors baseline).
    queryset = ListePrix.objects.prefetch_related('lignes', 'regles').all()
    serializer_class = ListePrixSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            return qs.filter(company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        # Company toujours forcée côté serveur — jamais acceptée du body.
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def lignes(self, request, pk=None):
        """Crée ou met à jour (upsert par produit) le prix d'un produit dans
        cette liste."""
        liste = self.get_object()
        produit_id = request.data.get('produit')
        prix_unitaire = request.data.get('prix_unitaire')
        if not produit_id or prix_unitaire is None:
            raise ValidationError('produit et prix_unitaire sont requis.')
        try:
            prix_unitaire = Decimal(str(prix_unitaire))
        except InvalidOperation:
            raise ValidationError('prix_unitaire invalide.')

        ligne, _ = LignePrixListe.objects.update_or_create(
            liste=liste, produit_id=produit_id,
            defaults={'prix_unitaire': prix_unitaire},
        )
        return Response(
            LignePrixListeSerializer(ligne).data, status=200)

    @action(detail=True, methods=['post'])
    def regles(self, request, pk=None):
        """Ajoute une règle de prix/palier à cette liste (XSAL2)."""
        liste = self.get_object()
        serializer = RegleListePrixSerializer(data={
            **request.data, 'liste': liste.id,
        })
        serializer.is_valid(raise_exception=True)
        serializer.save(liste=liste)
        return Response(serializer.data, status=201)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def prix_applicable_view(request):
    """XSAL3 — GET /ventes/prix-applicable/?produit=&client=&quantite=

    Résout le prix effectif (XSAL1 liste + XSAL2 règles/paliers) pour un
    produit, un client optionnel et une quantité. Company-scoped : le produit
    et le client doivent appartenir à la société de l'utilisateur, sinon 404
    (jamais de fuite cross-tenant). Ne renvoie jamais `prix_achat`."""
    from apps.stock.models import Produit
    from apps.crm.models import Client
    from ..services import prix_applicable

    user = request.user
    company = getattr(user, 'company', None)
    if company is None and not user.is_superuser:
        raise PermissionDenied('Aucune société associée.')

    produit_id = request.query_params.get('produit')
    if not produit_id:
        raise ValidationError('Le paramètre produit est requis.')

    produit_qs = Produit.objects.all()
    if company is not None:
        produit_qs = produit_qs.filter(company=company)
    try:
        produit = produit_qs.get(pk=produit_id)
    except (Produit.DoesNotExist, ValueError):
        raise NotFound('Produit introuvable.')

    client = None
    client_id = request.query_params.get('client')
    if client_id:
        client_qs = Client.objects.all()
        if company is not None:
            client_qs = client_qs.filter(company=company)
        try:
            client = client_qs.get(pk=client_id)
        except (Client.DoesNotExist, ValueError):
            raise NotFound('Client introuvable.')

    quantite = request.query_params.get('quantite') or '1'
    try:
        quantite = Decimal(str(quantite))
    except InvalidOperation:
        raise ValidationError('quantite invalide.')

    resolved = prix_applicable(produit=produit, client=client, quantite=quantite)
    return Response({
        'produit': produit.id,
        'quantite': str(quantite),
        'prix': str(resolved['prix']),
        'source': resolved['source'],
        'liste_nom': resolved['liste_nom'],
    })
