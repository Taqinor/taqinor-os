"""Vues FG311 — RFQ multi-fournisseurs & comparatif d'offres.

``RFQViewSet`` : CRUD des demandes de prix + cycle de vie
(``envoyer`` / ``cloturer``) + action ``retenir`` qui sélectionne UNE offre
(les autres sont automatiquement dé-sélectionnées). ``RFQOffreViewSet`` : CRUD
des réponses fournisseur. Lecture tout rôle, écriture responsable/admin.
Multi-tenant via ``TenantMixin`` : référence/société/created_by posés côté
serveur ; les FK liées sont validées tenant. Cross-app : ``stock.Fournisseur``
en string-FK.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from apps.ventes.utils.references import create_with_reference

from ..models import RFQ, RFQOffre
from ..serializers import RFQSerializer, RFQOffreSerializer

READ_ACTIONS = ['list', 'retrieve']


class RFQViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG311 — RFQ. Lecture tout rôle, écriture responsable/admin. Référence
    anti-collision + société + `created_by` posés serveur ; `demande` validée
    tenant. Filtrable par `statut`, `demande`. Cycle de vie + `retenir`."""
    queryset = RFQ.objects.select_related(
        'demande', 'created_by').prefetch_related('offres').all()
    serializer_class = RFQSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        demande = params.get('demande')
        if demande:
            qs = qs.filter(demande_id=demande)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        demande = serializer.validated_data.get('demande')
        if demande is not None and getattr(
                demande, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'demande': 'Demande inconnue pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(RFQ, 'RFQ', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def envoyer(self, request, pk=None):
        """FG311 — marque la RFQ comme envoyée (brouillon → envoyée)."""
        rfq = self.get_object()
        if rfq.statut not in (RFQ.Statut.BROUILLON, RFQ.Statut.ENVOYEE):
            return Response(
                {'detail': "Seule une RFQ brouillon peut être envoyée."},
                status=status.HTTP_400_BAD_REQUEST)
        rfq.statut = RFQ.Statut.ENVOYEE
        rfq.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(rfq).data)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """FG311 — clôt la RFQ (le choix est fait)."""
        rfq = self.get_object()
        rfq.statut = RFQ.Statut.CLOTUREE
        rfq.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(rfq).data)

    @action(detail=True, methods=['post'])
    def retenir(self, request, pk=None):
        """FG311 — retient UNE offre de la RFQ (les autres sont dé-sélectionnées).
        Corps : `offre` (id). L'offre doit appartenir à cette RFQ."""
        rfq = self.get_object()
        offre_id = request.data.get('offre')
        if not offre_id:
            return Response(
                {'offre': 'Paramètre `offre` requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        offre = rfq.offres.filter(id=offre_id).first()
        if offre is None:
            return Response(
                {'offre': "Cette offre n'appartient pas à la RFQ."},
                status=status.HTTP_400_BAD_REQUEST)
        rfq.offres.exclude(id=offre.id).update(retenue=False)
        offre.retenue = True
        offre.save(update_fields=['retenue', 'date_modification'])
        return Response(self.get_serializer(rfq).data)


class RFQOffreViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG311 — réponses fournisseur à une RFQ. La RFQ parente est validée tenant.
    Filtrable par `rfq`. Lecture tout rôle, écriture responsable/admin."""
    queryset = RFQOffre.objects.select_related('rfq', 'fournisseur').all()
    serializer_class = RFQOffreSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        rfq = self.request.query_params.get('rfq')
        if rfq:
            qs = qs.filter(rfq_id=rfq)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        rfq = serializer.validated_data.get('rfq')
        if rfq is not None and getattr(rfq, 'company_id', None) != cid:
            raise ValidationError({'rfq': 'RFQ inconnue pour cette société.'})
        fournisseur = serializer.validated_data.get('fournisseur')
        if fournisseur is not None and getattr(
                fournisseur, 'company_id', None) != cid:
            raise ValidationError(
                {'fournisseur': 'Fournisseur inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)
