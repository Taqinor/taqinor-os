"""Vues FG325 — demande de transfert inter-emplacements (workflow).

``DemandeTransfertViewSet`` : CRUD des demandes ; référence anti-collision posée
serveur ; cycle ``approuver`` (→ approuvé, pose `approuve_par`/date) /
``refuser`` (→ refusé, `motif_refus`) / ``executer`` (→ exécuté, date). Lecture
tout rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
produit/source/destination validés tenant. Cross-app : ``stock`` en string-FK.
"""
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import DemandeTransfert
from ..serializers import DemandeTransfertSerializer

READ_ACTIONS = ['list', 'retrieve']


class DemandeTransfertViewSet(CompanyScopedModelViewSet):
    """FG325 — demandes de transfert. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `statut`, `produit`, `source`,
    `destination`."""
    queryset = DemandeTransfert.objects.select_related(
        'produit', 'source', 'destination', 'approuve_par', 'created_by').all()
    serializer_class = DemandeTransfertSerializer

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
        for field in ('produit', 'source', 'destination'):
            val = params.get(field)
            if val:
                qs = qs.filter(**{f'{field}_id': val})
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for field, label in (
                ('produit', 'Produit'), ('source', 'Emplacement source'),
                ('destination', 'Emplacement destination')):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != cid:
                raise ValidationError(
                    {field: f'{label} inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(DemandeTransfert, 'DTR', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        """FG325 — approuve la demande (demandé → approuvé)."""
        dt = self.get_object()
        if dt.statut != DemandeTransfert.Statut.DEMANDE:
            return Response(
                {'statut': 'Seule une demande au statut « demandé » '
                           'peut être approuvée.'},
                status=status.HTTP_409_CONFLICT)
        dt.statut = DemandeTransfert.Statut.APPROUVE
        dt.approuve_par = request.user
        dt.date_approbation = timezone.now()
        dt.save(update_fields=[
            'statut', 'approuve_par', 'date_approbation', 'date_modification'])
        return Response(self.get_serializer(dt).data)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """FG325 — refuse la demande (→ refusé). Body optionnel `motif_refus`."""
        dt = self.get_object()
        if dt.statut != DemandeTransfert.Statut.DEMANDE:
            return Response(
                {'statut': 'Seule une demande au statut « demandé » '
                           'peut être refusée.'},
                status=status.HTTP_409_CONFLICT)
        dt.statut = DemandeTransfert.Statut.REFUSE
        dt.motif_refus = request.data.get('motif_refus') or dt.motif_refus
        dt.save(update_fields=['statut', 'motif_refus', 'date_modification'])
        return Response(self.get_serializer(dt).data)

    @action(detail=True, methods=['post'])
    def executer(self, request, pk=None):
        """FG325/YSTCK2 — marque la demande exécutée (approuvé → exécuté) ET
        exécute RÉELLEMENT le mouvement via `stock.services.transfer_stock`
        (ventile source→destination, total inchangé). Une source insuffisante
        échoue en 409 (aucun changement de statut). IDEMPOTENTE : la garde de
        statut (seule une demande APPROUVÉE peut être exécutée) empêche tout
        second transfert."""
        from apps.stock.services import transfer_stock

        dt = self.get_object()
        if dt.statut != DemandeTransfert.Statut.APPROUVE:
            return Response(
                {'statut': 'Seule une demande approuvée peut être exécutée.'},
                status=status.HTTP_409_CONFLICT)
        try:
            transfer_stock(
                company=request.user.company, user=request.user,
                produit_id=dt.produit_id, source_id=dt.source_id,
                destination_id=dt.destination_id, quantite=dt.quantite,
                note=f'Demande de transfert {dt.reference}')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        dt.statut = DemandeTransfert.Statut.EXECUTE
        dt.date_execution = timezone.now()
        dt.save(update_fields=[
            'statut', 'date_execution', 'date_modification'])
        return Response(self.get_serializer(dt).data)
