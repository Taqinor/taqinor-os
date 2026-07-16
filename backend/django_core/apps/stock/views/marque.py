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
