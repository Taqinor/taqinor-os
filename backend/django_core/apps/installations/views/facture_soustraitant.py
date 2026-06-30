"""Vues FG306 — factures & règlements des sous-traitants chantier (AP dédiée).

``FactureSousTraitantViewSet`` : CRUD des factures entrantes émises par un
sous-traitant (FG304), rattachables à un ordre de travaux (FG305) et/ou un
chantier, plus les actions de cycle de vie (``a_payer`` / ``annuler``).
``PaiementSousTraitantViewSet`` : CRUD des règlements imputés sur une facture ;
le statut de la facture se reflète automatiquement (à payer → partielle → payée)
au fil des paiements.

Lecture responsable/admin, écriture responsable/admin — ces montants sont
INTERNES (compte à payer) et ne doivent jamais fuir vers un rôle client-facing
ni un document client. Multi-tenant via ``TenantMixin`` : le queryset est filtré
sur la société de l'utilisateur ; la société et ``created_by`` sont posés côté
serveur (jamais lus du corps). Les FK liées sont validées tenant (même société).
"""
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from ..models import FactureSousTraitant, PaiementSousTraitant
from ..serializers import (
    FactureSousTraitantSerializer, PaiementSousTraitantSerializer,
)


def _check_tenant(serializer, company, field):
    """Tenant safety : l'objet lié doit appartenir à la société du user."""
    cid = getattr(company, 'id', None)
    obj = serializer.validated_data.get(field)
    if obj is not None and getattr(obj, 'company_id', None) != cid:
        raise ValidationError({field: 'Objet inconnu pour cette société.'})


def _refresh_statut(facture):
    """Reflète l'état de paiement sur le statut de la facture (jamais sur une
    facture brouillon ou annulée). À payer → partielle → payée."""
    if facture.statut in (FactureSousTraitant.Statut.BROUILLON,
                          FactureSousTraitant.Statut.ANNULEE):
        return
    paye = facture.total_paye
    ttc = facture.montant_ttc or Decimal('0')
    if paye <= 0:
        nouveau = FactureSousTraitant.Statut.A_PAYER
    elif paye < ttc:
        nouveau = FactureSousTraitant.Statut.PARTIELLE
    else:
        nouveau = FactureSousTraitant.Statut.PAYEE
    if nouveau != facture.statut:
        facture.statut = nouveau
        facture.save(update_fields=['statut', 'date_modification'])


class FactureSousTraitantViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG306 — factures entrantes sous-traitant (compte à payer). Lecture &
    écriture responsable/admin (montants INTERNES). Société + `created_by` posés
    serveur ; `sous_traitant`/`ordre`/`chantier` validés tenant. Filtrable par
    `sous_traitant`, `statut`, `ordre`, `chantier`. Cycle de vie via les actions
    `a_payer`/`annuler`."""
    queryset = FactureSousTraitant.objects.select_related(
        'sous_traitant', 'ordre', 'chantier', 'created_by'
    ).prefetch_related('paiements').all()
    serializer_class = FactureSousTraitantSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for key, col in (('sous_traitant', 'sous_traitant_id'),
                         ('statut', 'statut'),
                         ('ordre', 'ordre_id'),
                         ('chantier', 'chantier_id')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'sous_traitant')
        _check_tenant(serializer, company, 'ordre')
        _check_tenant(serializer, company, 'chantier')
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'sous_traitant')
        _check_tenant(serializer, company, 'ordre')
        _check_tenant(serializer, company, 'chantier')
        serializer.save(company=company)

    @action(detail=True, methods=['post'])
    def a_payer(self, request, pk=None):
        """FG306 — passe la facture en « à payer » (brouillon → à payer), puis
        reflète l'état réel des paiements."""
        facture = self.get_object()
        if facture.statut == FactureSousTraitant.Statut.ANNULEE:
            return Response(
                {'detail': "Une facture annulée ne peut pas passer à payer."},
                status=status.HTTP_400_BAD_REQUEST)
        facture.statut = FactureSousTraitant.Statut.A_PAYER
        if facture.date_facture is None:
            facture.date_facture = timezone.now().date()
        facture.save(update_fields=['statut', 'date_facture',
                                    'date_modification'])
        _refresh_statut(facture)
        return Response(self.get_serializer(facture).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """FG306 — annule la facture (refusée si elle porte déjà un paiement)."""
        facture = self.get_object()
        if facture.total_paye > 0:
            return Response(
                {'detail': "Une facture déjà réglée ne peut pas être annulée."},
                status=status.HTTP_400_BAD_REQUEST)
        facture.statut = FactureSousTraitant.Statut.ANNULEE
        facture.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(facture).data)


class PaiementSousTraitantViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG306 — règlements imputés sur une facture sous-traitant. Lecture &
    écriture responsable/admin (montants INTERNES). Société + `created_by` posés
    serveur ; la facture ciblée est validée tenant. Le statut de la facture est
    rafraîchi à chaque création/suppression de paiement. Filtrable par
    `facture`."""
    queryset = PaiementSousTraitant.objects.select_related(
        'facture', 'created_by').all()
    serializer_class = PaiementSousTraitantSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        facture = self.request.query_params.get('facture')
        if facture:
            qs = qs.filter(facture_id=facture)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'facture')
        facture = serializer.validated_data.get('facture')
        # On ne paie pas une facture annulée.
        if facture is not None and (
                facture.statut == FactureSousTraitant.Statut.ANNULEE):
            raise ValidationError(
                {'facture': "Impossible de régler une facture annulée."})
        # On n'imputera jamais plus que le reste à payer.
        if facture is not None:
            montant = serializer.validated_data.get('montant') or Decimal('0')
            try:
                montant = Decimal(str(montant))
            except (InvalidOperation, ValueError):
                montant = Decimal('0')
            if montant > facture.reste_a_payer:
                raise ValidationError(
                    {'montant': "Le paiement dépasse le reste à payer."})
        paiement = serializer.save(
            company=company, created_by=self.request.user)
        _refresh_statut(paiement.facture)

    def perform_destroy(self, instance):
        facture = instance.facture
        instance.delete()
        _refresh_statut(facture)
