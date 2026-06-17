"""N31 — endpoint d'audit de la numérotation séquentielle (lecture seule).

Réservé à l'admin : signale les numéros manquants (trous laissés par une
suppression) et d'éventuels doublons, par type de pièce. Ne renumérote rien.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminRole
from .utils.numbering_audit import audit_company


@api_view(['GET'])
@permission_classes([IsAdminRole])
def numerotation_audit(request):
    """GET → rapport des trous/doublons de numérotation pour la société."""
    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    if not user.company_id:
        return Response({'detail': 'Aucune société.'}, status=400)
    return Response(audit_company(user.company))
