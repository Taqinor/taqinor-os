"""apps.credit.views — squelette (NTCRD1).

NTCRD1 n'a encore aucun modèle : ``ping`` sert uniquement à vérifier que
l'app est bien montée (200 propre) sans dépendre d'une table. Les ViewSets
réels (LimiteCreditViewSet…) arrivent à partir de NTCRD2.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ping(request):
    """NTCRD1 — vérifie que l'app ``credit`` est montée et répond."""
    return Response({'app': 'credit', 'status': 'ok'})
