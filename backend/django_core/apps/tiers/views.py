"""Vues du répertoire ``Tiers`` (ARC17) — CRUD scopé société.

Le viewset filtre par ``request.user.company`` (``TenantMixin.get_queryset``)
et FORCE la société côté serveur à la création (``perform_create``) — jamais
lue du corps de requête. ``tiers`` étant une couche fondation, ce module
n'importe AUCUNE app de domaine.
"""
from rest_framework import filters, viewsets

from core.mixins import TenantMixin
from core.permissions import WriteScopedPermissionMixin

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
