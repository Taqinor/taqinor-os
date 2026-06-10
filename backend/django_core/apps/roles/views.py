from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminRole
from .models import Role, ALL_PERMISSIONS
from .serializers import RoleSerializer


class RoleViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Gestion des rôles d'une entreprise.
    Seul l'admin peut créer/modifier/supprimer des rôles.
    Les rôles système (est_systeme=True) ne peuvent pas être supprimés.
    """
    queryset = Role.objects.select_related('company').all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return super().get_queryset().prefetch_related('users')

    def perform_destroy(self, instance):
        if instance.est_systeme:
            raise PermissionDenied(
                "Les rôles système ne peuvent pas être supprimés."
            )
        if instance.users.exists():
            raise PermissionDenied(
                "Ce rôle est assigné à des utilisateurs. "
                "Réassignez-les avant de supprimer ce rôle."
            )
        instance.delete()

    @action(detail=False, methods=['get'], url_path='permissions-disponibles')
    def permissions_disponibles(self, request):
        """Retourne la liste de toutes les permissions disponibles."""
        return Response({'permissions': ALL_PERMISSIONS})
