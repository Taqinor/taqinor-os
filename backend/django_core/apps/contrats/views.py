"""Vues de la Gestion des contrats (scopées société, accès admin/responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; l'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``).

Niveaux de confidentialité (CONTRAT6)
--------------------------------------
La visibilité d'un ``Contrat`` est réglée par son champ ``confidentialite`` :

- ``PUBLIC``       : visible par tous les utilisateurs authentifiés de la société
                     qui ont accès au module (responsable + admin).
- ``INTERNE``      : même visibilité que PUBLIC au niveau du rôle — pas de
                     restriction supplémentaire au-dessus du filtre société.
- ``CONFIDENTIEL`` : visible uniquement par les Administrateurs.

Le filtre est appliqué dans ``ContratViewSet.get_queryset``.  Les filtres
``?confidentialite=`` permettent de restreindre la liste côté client.
"""
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors
from .models import Contrat, ContratLien, PartieContrat
from .serializers import (
    ContratLienSerializer,
    ContratSerializer,
    PartieContratSerializer,
)


class _ContratsBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ContratViewSet(_ContratsBaseViewSet):
    """Contrats de la société (CLM). Recherche par référence/objet.

    Visibilité par confidentialité : les contrats ``CONFIDENTIEL`` ne sont
    accessibles qu'aux Administrateurs. Les contrats ``PUBLIC``/``INTERNE``
    sont accessibles à tous les Responsables et Administrateurs de la société.
    Un filtre optionnel ``?confidentialite=<niveau>`` permet de restreindre
    la liste retournée.
    """
    queryset = Contrat.objects.all()
    serializer_class = ContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet']
    ordering_fields = ['date_debut', 'date_fin', 'montant', 'id', 'confidentialite']

    def get_queryset(self):
        """Queryset scopé société + filtre confidentialité.

        Les contrats ``CONFIDENTIEL`` sont exclus pour les non-Administrateurs.
        Un filtre optionnel ``?confidentialite=<valeur>`` restreint
        supplémentairement la liste.
        """
        qs = super().get_queryset()
        user = self.request.user
        # Exclure les contrats CONFIDENTIEL pour les non-Administrateurs.
        # Le rôle effectif est lu via la propriété ``effective_role`` du modèle
        # utilisateur (préférant le Role FK, fallback sur role_legacy).
        effective_role = getattr(user, 'effective_role', None) or getattr(
            user, 'role_legacy', 'normal')
        if effective_role != user.ROLE_ADMIN and not user.is_superuser:
            qs = qs.exclude(
                confidentialite=Contrat.NiveauConfidentialite.CONFIDENTIEL)
        # Filtre optionnel par niveau de confidentialité.
        niveau = self.request.query_params.get('confidentialite')
        if niveau:
            qs = qs.filter(confidentialite=niveau)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def liens(self, request, pk=None):
        """Liens du contrat ENRICHIS via les sélecteurs des apps cibles.

        Pour chaque lien : libellé frais quand l'app cible expose un sélecteur
        (``source='live'``), sinon le libellé stocké (``source='stored'``). La
        société est garantie par ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        return Response(selectors.liens_enrichis(contrat))


class PartieContratViewSet(_ContratsBaseViewSet):
    """Parties/signataires des contrats de la société.

    Société posée côté serveur (``TenantMixin.perform_create``) ; le contrat
    rattaché est validé même société par le sérialiseur. Filtrable par
    ``?contrat=<id>`` et recherchable par nom/email.
    """
    queryset = PartieContrat.objects.all()
    serializer_class = PartieContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email']
    ordering_fields = ['ordre', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        return qs


class ContratLienViewSet(_ContratsBaseViewSet):
    """Liens contrat → devis / lead / installation / maintenance (refs lâches).

    ``company`` est posée côté serveur (TenantMixin) ; le ``contrat`` reçu est
    validé même-société par le sérialiseur. Filtres optionnels ``?contrat=<id>``
    et ``?type_cible=<type>``.
    """
    queryset = ContratLien.objects.select_related('contrat').all()
    serializer_class = ContratLienSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        type_cible = self.request.query_params.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        return qs
