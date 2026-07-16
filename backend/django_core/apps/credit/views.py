"""apps.credit.views — peuplé tâche par tâche."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import LimiteCredit
from .serializers import LimiteCreditSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ping(request):
    """NTCRD1 — vérifie que l'app ``credit`` est montée et répond."""
    return Response({'app': 'credit', 'status': 'ok'})


class LimiteCreditViewSet(CompanyScopedModelViewSet):
    """NTCRD2 — CRUD limite de crédit par client, company-scopé."""
    queryset = LimiteCredit.objects.select_related('client', 'cree_par').all()
    serializer_class = LimiteCreditSerializer

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, cree_par=self.request.user)
