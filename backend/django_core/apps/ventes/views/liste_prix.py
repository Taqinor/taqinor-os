"""XSAL1 — Listes de prix clients (détail / revendeur / export).

Endpoints :
  GET/POST      /ventes/listes-prix/                  list/create
  GET/PUT/PATCH /ventes/listes-prix/{id}/              retrieve/update
  DELETE        /ventes/listes-prix/{id}/              destroy
  POST          /ventes/listes-prix/{id}/lignes/       ajouter/mettre à jour un prix

Écriture réservée responsable/admin (une liste de prix révisée agit sur les
devis de tous les vendeurs) ; lecture ouverte à tout rôle authentifié de la
société. `prix_achat` n'est JAMAIS lu ni exposé ici."""
from decimal import Decimal, InvalidOperation

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from ..models import ListePrix, LignePrixListe
from ..serializers import ListePrixSerializer, LignePrixListeSerializer

READ_ACTIONS = ['list', 'retrieve']


class ListePrixViewSet(viewsets.ModelViewSet):
    queryset = ListePrix.objects.prefetch_related('lignes').all()
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
