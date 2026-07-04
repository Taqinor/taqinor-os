"""YSERV13 — endpoint `insights/integrite/` (contrôle d'intégrité inter-
documents, lecture seule, réservé responsable/admin)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

from .integrity import controle_integrite, total_anomalies


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def integrite_insight(request):
    """YSERV13 — ``GET reporting/insights/integrite/``.

    Exécute toutes les familles de contrôle pour la société de l'utilisateur
    et renvoie ``{familles: {clé: {label, ids}}, total_anomalies}``. Lecture
    seule : ne corrige RIEN."""
    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    if not user.company_id:
        return Response({'familles': {}, 'total_anomalies': 0})

    result = controle_integrite(user.company)
    return Response({
        'familles': result,
        'total_anomalies': total_anomalies(result),
    })
