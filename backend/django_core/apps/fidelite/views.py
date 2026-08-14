"""Vues du module « fidelite » (NTRET9) — configuration du programme +
consultation des comptes/mouvements de points.
"""
from django.db import IntegrityError
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet

from .models import CompteFidelite, PalierFidelite, ProgrammeFidelite
from .serializers import (
    CompteFideliteSerializer, MouvementFideliteSerializer,
    PalierFideliteSerializer, ProgrammeFideliteSerializer,
)


class ProgrammeFideliteViewSet(CompanyScopedModelViewSet):
    """Configuration du programme de fidélité (Directeur/Admin habituellement,
    grain de rôle laissé au défaut ``ScopedPermission`` de la base — aucun
    rôle dédié n'est demandé par NTRET9).

    Un seul programme ACTIF par société : la contrainte d'unicité partielle
    du modèle est traduite ici en 400 explicite plutôt qu'un 500 générique.
    """

    queryset = ProgrammeFidelite.objects.all()
    serializer_class = ProgrammeFideliteSerializer

    def perform_create(self, serializer):
        try:
            super().perform_create(serializer)
        except IntegrityError:
            raise ValidationError(
                {'actif': "Un programme actif existe déjà pour cette société."})

    def perform_update(self, serializer):
        try:
            super().perform_update(serializer)
        except IntegrityError:
            raise ValidationError(
                {'actif': "Un programme actif existe déjà pour cette société."})


class PalierFideliteViewSet(CompanyScopedModelViewSet):
    """Paliers de fidélité (NTRET10) — filtrable par ``?programme=<id>``."""

    queryset = PalierFidelite.objects.select_related('programme').all()
    serializer_class = PalierFideliteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        programme_id = self.request.query_params.get('programme')
        if programme_id:
            qs = qs.filter(programme_id=programme_id)
        return qs


class CompteFideliteViewSet(CompanyScopedModelViewSet):
    """Lecture seule (NTRET9) : un compte naît du crédit de points
    (``services.crediter_points_pour_vente``), jamais d'une création API
    directe — filtrable par ``?client=<id>`` (fiche client)."""

    queryset = CompteFidelite.objects.select_related(
        'client', 'palier_actuel').all()
    serializer_class = CompteFideliteSerializer
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        client_id = self.request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    # YRBAC4 — garde DÉCLARÉE par l'action. Lecture d'un historique de points
    # sur un viewset DÉJÀ lecture seule (``http_method_names`` sans écriture) et
    # company-scopé : ``ScopedPermission`` (GET → ``read_permission`` None)
    # exprime le tier réel « authentifié INTERNE de la société », identique au
    # défaut de classe — explicite et vérifiable, sans changement de
    # comportement. Le vendeur au comptoir doit pouvoir consulter le solde d'un
    # client sans être responsable. Aucun ``get_permissions`` ici ni dans les
    # bases → la déclaration n'est pas neutralisée.
    @action(detail=True, methods=['get'], url_path='mouvements',
            permission_classes=[ScopedPermission])
    def mouvements(self, request, pk=None):
        """Historique des mouvements de points du compte (plus récent d'abord)."""
        compte = self.get_object()
        qs = compte.mouvements.all()[:200]
        return Response(MouvementFideliteSerializer(qs, many=True).data)
