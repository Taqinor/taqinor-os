"""apps.credit.views — peuplé tâche par tâche."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import LimiteCredit, ReglageCredit
from .serializers import LimiteCreditSerializer, ReglageCreditSerializer


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


class ReglageCreditView(APIView):
    """NTCRD3 — réglage crédit société (singleton get-or-default/PATCH).

    Lecture ouverte à tout authentifié ; écriture réservée Directeur/
    Administrateur (les réglages de hold impactent toute la société)."""
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT', 'POST'):
            return [IsResponsableOrAdmin()]
        return super().get_permissions()

    def get(self, request):
        reglage = ReglageCredit.get_or_default(request.user.company)
        return Response(ReglageCreditSerializer(reglage).data)

    def patch(self, request):
        reglage, _ = ReglageCredit.objects.get_or_create(
            company=request.user.company)
        serializer = ReglageCreditSerializer(
            reglage, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
