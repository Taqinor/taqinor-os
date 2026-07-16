"""Vues FG312 — paliers d'approbation de BCF par seuil (workflow par montant).

``SeuilApprobationBCFViewSet`` : configuration du seuil par société (réservé
Administrateur — c'est une règle de gouvernance). ``ApprobationBCFViewSet`` :
lecture des approbations + action ``approuver`` qui APPLIQUE le palier requis
selon le montant d'achat du BCF :
  * montant ≤ seuil → un Responsable (ou Admin) peut approuver ;
  * montant > seuil → SEUL un Administrateur peut approuver.

Multi-tenant via ``TenantMixin`` : société + approbateur posés côté serveur ; le
BCF est validé tenant. Cross-app : ``stock.BonCommandeFournisseur`` lu via
sélecteur (string-FK, aucun import du modèle stock).
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import (
    IsAnyRole, IsResponsableOrAdmin, IsAdminRole,
)
from core.viewsets import CompanyScopedModelViewSet

from ..models import SeuilApprobationBCF, ApprobationBCF
from ..models_approbation_bcf import PALIER_ADMIN, PALIER_RESPONSABLE
from ..serializers import (
    SeuilApprobationBCFSerializer, ApprobationBCFSerializer,
)
from .. import selectors

READ_ACTIONS = ['list', 'retrieve']


class SeuilApprobationBCFViewSet(CompanyScopedModelViewSet):
    """FG312 — seuil d'approbation BCF par société. Lecture responsable/admin,
    écriture Administrateur seulement (règle de gouvernance). Société posée
    serveur."""
    queryset = SeuilApprobationBCF.objects.all()
    serializer_class = SeuilApprobationBCFSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]


class ApprobationBCFViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """FG312 — approbations de BCF (lecture) + action `approuver`. Lecture tout
    rôle ; l'approbation applique le palier requis par le montant. Société +
    approbateur posés serveur ; BCF validé tenant. Filtrable par `bcf`."""
    queryset = ApprobationBCF.objects.select_related(
        'bcf', 'approuve_par').all()
    serializer_class = ApprobationBCFSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        qs = super().get_queryset()
        bcf = self.request.query_params.get('bcf')
        if bcf:
            qs = qs.filter(bcf_id=bcf)
        return qs

    @action(detail=False, methods=['post'])
    def approuver(self, request):
        """FG312 — approuve un BCF en appliquant le palier requis selon son
        montant d'achat. Corps : `bcf` (id), `note` (optionnelle). Refuse si
        l'utilisateur n'a pas le palier requis (admin obligatoire au-dessus du
        seuil). Idempotent si déjà approuvé au bon palier."""
        company = request.user.company
        bcf_id = request.data.get('bcf')
        if not bcf_id:
            return Response(
                {'bcf': 'Paramètre `bcf` requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        # Le BCF doit appartenir à la société (lu via sélecteur, string-FK).
        from django.apps import apps as django_apps
        bcf_model = django_apps.get_model('achats', 'BonCommandeFournisseur')
        bcf = bcf_model.objects.filter(id=bcf_id, company=company).first()
        if bcf is None:
            return Response(
                {'bcf': 'Bon de commande inconnu pour cette société.'},
                status=status.HTTP_404_NOT_FOUND)

        montant = selectors.bcf_montant_achat(company, bcf_id)
        palier = selectors.palier_requis_bcf(company, montant)

        user = request.user
        if palier == PALIER_ADMIN and not user.is_admin_role:
            return Response(
                {'detail': "Ce montant dépasse le seuil : seul un "
                           "Administrateur peut approuver ce BCF."},
                status=status.HTTP_403_FORBIDDEN)
        if palier == PALIER_RESPONSABLE and not user.is_responsable:
            return Response(
                {'detail': "Approbation réservée aux Responsables/"
                           "Administrateurs."},
                status=status.HTTP_403_FORBIDDEN)

        approbation, _ = ApprobationBCF.objects.update_or_create(
            company=company, bcf=bcf,
            defaults={
                'palier': palier,
                'montant_approuve': montant,
                'approuve_par': user,
                'note': (request.data.get('note') or '').strip() or None,
            })
        return Response(
            self.get_serializer(approbation).data,
            status=status.HTTP_200_OK)
