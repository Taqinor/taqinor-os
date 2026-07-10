"""Vues du répertoire ``Tiers`` (ARC17) — CRUD scopé société.

Le viewset filtre par ``request.user.company`` (``TenantMixin.get_queryset``)
et FORCE la société côté serveur à la création (``perform_create``) — jamais
lue du corps de requête. ``tiers`` étant une couche fondation, ce module
n'importe AUCUNE app de domaine.
"""
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAdminRole
from core.mixins import TenantMixin
from core.permissions import WriteScopedPermissionMixin

from . import selectors
from .models import Tiers
from .serializers import TiersSerializer


class TiersViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """CRUD du répertoire des tiers (parties prenantes), scopé société.

    Lecture/écriture : tout utilisateur authentifié de la société (répertoire
    de fondation, aucune permission fine dédiée pour l'instant — le repli
    légacy reste géré par ``ScopedPermission``). L'isolation multi-société est
    garantie par ``TenantMixin`` (queryset filtré + société forcée à la
    création).
    """
    queryset = Tiers.objects.all()
    serializer_class = TiersSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'nom', 'prenom', 'raison_sociale', 'email', 'telephone',
        'ice', 'rc', 'identifiant_fiscal', 'cin',
    ]
    ordering_fields = ['nom', 'prenom', 'date_creation']
    ordering = ['nom', 'prenom']
    # Répertoire de fondation : aucune permission fine dédiée — authentifié
    # + scopé société suffit (le repli légacy reste géré par ScopedPermission).
    read_permission = None
    write_permission = None

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminRole])
    def doublons(self, request):
        """ARC20 — Rapport LECTURE SEULE des doublons inter-référentiels de la
        société de l'utilisateur : le même ICE/email porté par plusieurs fiches
        ``Tiers`` (ex. un acteur à la fois Fournisseur et Partenaire). Réservé
        aux administrateurs. AUCUNE fusion, aucune écriture. Company-scopé
        (jamais les tiers d'une autre société). Renvoie ``{count, clusters}``."""
        clusters = selectors.find_duplicates(request.user.company)
        return Response({'count': len(clusters), 'clusters': clusters})
