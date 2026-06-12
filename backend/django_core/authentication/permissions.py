from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Admin role or superuser only."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin_role
        )


class IsResponsableOrAdmin(BasePermission):
    """Responsable or admin role."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_responsable
        )


class IsAnyRole(BasePermission):
    """Any authenticated user."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


def HasPermissionOrLegacy(code):
    """Permission ERP granulaire quand l'utilisateur porte un rôle fin ;
    comportement historique (responsable/admin) pour les comptes hérités
    sans rôle. C'est ce qui rend possible un rôle « lecture seule Stock »
    sans rien changer pour demo_admin / demo_resp.
    """
    class _HasPermissionOrLegacy(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            if not (user and user.is_authenticated):
                return False
            if user.is_superuser:
                return True
            if getattr(user, 'role', None):
                return user.has_erp_permission(code)
            return user.is_responsable
    _HasPermissionOrLegacy.__name__ = f'HasPermissionOrLegacy_{code}'
    return _HasPermissionOrLegacy


def HasPermission(code):
    """
    Permission factory. Returns a DRF permission class that checks
    whether the user has a specific ERP permission code.

    Usage:
        permission_classes = [HasPermission('stock_voir')]
    """
    class _HasPermission(BasePermission):
        def has_permission(self, request, view):
            return bool(
                request.user
                and request.user.is_authenticated
                and request.user.has_erp_permission(code)
            )
    _HasPermission.__name__ = f'HasPermission_{code}'
    return _HasPermission
