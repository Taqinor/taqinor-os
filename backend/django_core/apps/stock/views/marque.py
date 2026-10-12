from django.db import transaction
from rest_framework.parsers import JSONParser
from rest_framework import status
from rest_framework.response import Response
from core.viewsets import CompanyScopedModelViewSet
from ..models import Produit, Marque
from ..serializers import MarqueSerializer
from authentication.permissions import IsAnyRole, IsAdminRole

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


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


class MarqueViewSet(CompanyScopedModelViewSet):
    """Marques produit gérées (Paramètres → Stock). Lecture tout rôle, écriture
    admin. Une marque utilisée par des produits ne peut pas être supprimée."""
    queryset = Marque.objects.all()
    serializer_class = MarqueSerializer

    parser_classes = [JSONParser]

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

    def perform_update(self, serializer):
        """ASTK97 — renommer une marque propage le nouveau libellé à
        ``Produit.marque`` des produits de la société qui portaient l'ancien
        (une transaction ; chaque produit est sauvé individuellement pour que
        son journal enregistre le changement)."""
        ancien = serializer.instance.nom
        with transaction.atomic():
            super().perform_update(serializer)
            nouveau = serializer.instance.nom
            if nouveau != ancien:
                produits = Produit.objects.filter(
                    company=serializer.instance.company, marque=ancien)
                for produit in produits:
                    produit.marque = nouveau
                    produit.save(update_fields=['marque'])
