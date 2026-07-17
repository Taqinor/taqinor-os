"""apps.credit.views — peuplé tâche par tâche."""
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import DerogationCredit, LimiteCredit, ReglageCredit
from .serializers import (
    DerogationCreditSerializer, LimiteCreditSerializer, ReglageCreditSerializer,
)


class IsDirecteurOrAdmin(BasePermission):
    """NTCRD9 — décision de dérogation réservée Directeur/Administrateur.

    Passe pour un superuser, le palier admin (``is_admin_role``), ou un rôle
    fin nommé « Directeur »/« Administrateur ». Un Commercial (même avec des
    permissions d'écriture) est REFUSÉ — c'est une garde de restriction, pas
    de compatibilité."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(u, 'is_superuser', False) or getattr(u, 'is_admin_role', False):
            return True
        role = getattr(u, 'role', None)
        return bool(role and role.nom in ('Directeur', 'Administrateur'))


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


class DerogationCreditViewSet(CompanyScopedModelViewSet):
    """NTCRD9 — dérogations crédit : tout authentifié peut DEMANDER
    (``create``) ; seul Directeur/Administrateur peut approuver/rejeter."""
    queryset = DerogationCredit.objects.select_related(
        'client', 'demandeur', 'approuvee_par', 'devis').all()
    serializer_class = DerogationCreditSerializer

    def get_permissions(self):
        if self.action in ('approuver', 'rejeter'):
            return [IsDirecteurOrAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, demandeur=self.request.user)

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        from .services import approuver_derogation
        derogation = self.get_object()
        approuver_derogation(derogation, request.user)
        return Response(self.get_serializer(derogation).data)

    @action(detail=True, methods=['post'])
    def rejeter(self, request, pk=None):
        from .services import rejeter_derogation
        derogation = self.get_object()
        rejeter_derogation(derogation, request.user)
        return Response(
            self.get_serializer(derogation).data, status=status.HTTP_200_OK)
