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
