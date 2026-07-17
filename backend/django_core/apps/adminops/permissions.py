"""Permission « Administrateur only » pour apps.adminops (même pattern que
apps/entites/permissions.py et apps/fpa/permissions.py — code fin lisible via
has_erp_permission, enregistrement UI dans apps.roles = NTADM39, hors périmètre)."""
from rest_framework.permissions import BasePermission

ADMINOPS_ADMINISTRER = 'adminops_administrer'


class IsAdministrateur(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        if getattr(user, 'is_admin_role', False):
            return True
        try:
            return bool(user.has_erp_permission(ADMINOPS_ADMINISTRER))
        except Exception:
            return False


class IsTaqinorSupportOuAdministrateur(BasePermission):
    """NTADM23/24 — réservé staff Taqinor (`is_taqinor_support`, NTADM22 hors
    périmètre = pas encore de champ dédié) OU l'Administrateur du tenant
    lui-même. Repli : superuser Django = staff Taqinor de facto."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        if getattr(user, 'is_taqinor_support', False):
            return True
        return getattr(user, 'is_admin_role', False)
