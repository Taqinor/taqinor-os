"""NTMOB1 — point de synchro hors-ligne UNIQUE (tous modules) + journal.

``POST /offlinesync/operations/batch/`` reçoit le lot accumulé par l'outbox du
terminal pendant une coupure réseau et l'applique de façon IDEMPOTENTE (rejouer
la même clé est un no-op). ``GET /offlinesync/operations/`` expose le journal
(lecture seule) : ce qui attend, ce qui a été appliqué, ce qui a été refusé et
pourquoi — aucune opération ne disparaît en silence (VX119).

``POST /offlinesync/operations/<id>/resoudre/`` (NTMOB2) est la SEULE écriture
du journal : elle exécute l'arbitrage humain d'un conflit (garder ma version /
celle du serveur / fusionner). Rien n'est jamais écrasé en silence.

Multi-tenant : la société vient de ``request.user.company``, JAMAIS du corps ;
un champ « company » envoyé par le navigateur est ignoré.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.mixins import TenantMixin

from . import services
from rest_framework.generics import GenericAPIView

from .models import OfflineOperation
from .serializers import (
    OfflineOperationSerializer, ResolutionConflitSerializer)


class OfflineSyncBatchView(GenericAPIView):
    """Rejeu idempotent d'un lot multi-module.

    Corps : ``{"ops": [{client_op_id, op_type, payload, queued_at?}, …]}``.
    Réponse : ``{applied, replayed, errors, results}``. Sûr à rejouer en
    entier : une clé déjà appliquée renvoie son résultat mémorisé sans
    ré-appliquer l'effet."""

    permission_classes = [IsResponsableOrAdmin]
    # Forme DÉCLARÉE (pas devinée) : sans cela drf-spectacular tombe en
    # « unable to guess serializer » et publie un schéma muet.
    serializer_class = OfflineOperationSerializer

    def get_queryset(self):
        return OfflineOperation.objects.filter(
            company=self.request.user.company)

    def post(self, request):
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': "Aucune société sur l'utilisateur."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            resume = services.apply_batch(company, request.user,
                                          request.data.get('ops'))
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(resume, status=status.HTTP_200_OK)


class OfflineOperationViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Journal des opérations hors-ligne de la société (lecture seule)."""

    queryset = OfflineOperation.objects.select_related('user').all()
    serializer_class = OfflineOperationSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        module = self.request.query_params.get('module')
        if module:
            qs = qs.filter(module=module)
        return qs

    @action(detail=True, methods=['post'], url_path='resoudre',
            permission_classes=[IsResponsableOrAdmin],
            serializer_class=ResolutionConflitSerializer)
    def resoudre(self, request, pk=None):
        """NTMOB2 — arbitrage EXPLICITE d'un conflit de synchronisation.

        Corps : ``{"choix": "mienne"|"serveur"|"fusion", "payload": {…}}``
        (``payload`` uniquement — et obligatoirement — pour une fusion).

        Le journal reste en lecture seule : c'est la SEULE écriture, elle ne
        fait qu'exécuter une décision humaine, et l'objet est repris par
        ``get_object()`` — donc borné à la société de l'appelant."""
        operation = self.get_object()
        entree = ResolutionConflitSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        try:
            resultat = services.resoudre_conflit(
                request.user.company, request.user, operation,
                entree.validated_data['choix'],
                entree.validated_data.get('payload'))
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        operation.refresh_from_db()
        return Response(
            {'resultat': resultat,
             'operation': OfflineOperationSerializer(operation).data},
            status=status.HTTP_200_OK)
