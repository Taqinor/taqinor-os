"""N91/F21 — endpoint de SYNCHRO de la capture terrain hors-ligne.

`POST /installations/sync/` reçoit le LOT d'opérations accumulées par l'outbox
du terminal pendant une coupure réseau et les applique de façon IDEMPOTENTE
(rejouer la même clé est un no-op, last-write-wins sur les conflits).

Multi-tenant : la société est posée côté serveur depuis ``request.user.company``
— JAMAIS lue du corps. Un éventuel champ « company » du corps est ignoré.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsResponsableOrAdmin

from .. import field_sync


class FieldSyncView(APIView):
    """Synchro idempotente d'un lot de capture terrain.

    Corps : {"ops": [ {client_op_id, op_type, payload}, ... ]}.
    Réponse : {applied, replayed, errors, results}. Sûr à rejouer en entier."""
    permission_classes = [IsResponsableOrAdmin]
    parser_classes = [JSONParser]

    @extend_schema(
        request=inline_serializer('FieldSyncRequete', fields={
            'ops': serializers.ListField(
                child=serializers.DictField(),
                help_text='Lot {client_op_id, op_type, payload}.'),
        }),
        responses={200: inline_serializer('FieldSyncResultat', fields={
            'applied': serializers.IntegerField(),
            'replayed': serializers.IntegerField(),
            'errors': serializers.IntegerField(),
            'results': serializers.ListField(child=serializers.DictField()),
        })})
    def post(self, request):
        company = request.user.company
        if company is None:
            return Response(
                {'detail': "Aucune société sur l'utilisateur."},
                status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(request.data, dict):
            return Response({'detail': 'Corps JSON objet attendu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ops = request.data.get('ops')
        try:
            summary = field_sync.apply_batch(company, request.user, ops)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(summary, status=status.HTTP_200_OK)
