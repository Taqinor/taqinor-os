from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminOrResponsableTier
from apps.parametres.models import SettingsAuditLog
from .models import Role, ALL_PERMISSIONS
from .serializers import RoleSerializer


class RoleViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Gestion des rôles d'une entreprise.
    Administrateur et Responsable (promu) peuvent créer/modifier/supprimer des
    rôles ; le palier limité reste bloqué.
    Les rôles système (est_systeme=True) ne peuvent pas être supprimés.
    Chaque création/modification/suppression écrit une ligne au Journal d'audit
    des paramètres (section='roles').
    """
    queryset = Role.objects.select_related('company').all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        return super().get_queryset().prefetch_related('users')

    def _audit(self, field, label, old, new):
        """Écrit une ligne d'audit company-scopée pour le rôle agissant."""
        user = self.request.user
        SettingsAuditLog.log_change(
            company=getattr(user, 'company', None), user=user,
            section='roles', field=field, field_label=label, old=old, new=new,
        )

    def perform_create(self, serializer):
        # TenantMixin force la société côté serveur (jamais depuis la requête).
        instance = serializer.save(company=self.request.user.company)
        self._audit(
            field=f'role:{instance.nom}',
            label='Rôle créé',
            old=None,
            new=f"{instance.nom} ({len(instance.permissions or [])} permissions)",
        )

    def perform_update(self, serializer):
        old_nom = serializer.instance.nom
        old_perms = sorted(serializer.instance.permissions or [])
        instance = serializer.save(company=self.request.user.company)
        new_perms = sorted(instance.permissions or [])
        if old_perms != new_perms or old_nom != instance.nom:
            self._audit(
                field=f'role:{instance.nom}',
                label='Rôle modifié',
                old=f"{old_nom} ({len(old_perms)} permissions)",
                new=f"{instance.nom} ({len(new_perms)} permissions)",
            )

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
        nom = instance.nom
        perms_count = len(instance.permissions or [])
        instance.delete()
        self._audit(
            field=f'role:{nom}',
            label='Rôle supprimé',
            old=f"{nom} ({perms_count} permissions)",
            new=None,
        )

    @action(detail=False, methods=['get'], url_path='permissions-disponibles')
    def permissions_disponibles(self, request):
        """Retourne la liste de toutes les permissions disponibles."""
        return Response({'permissions': ALL_PERMISSIONS})
