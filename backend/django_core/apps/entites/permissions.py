"""Permission « Administrateur only » pour apps.entites (NTADM1).

Même pattern documenté que ``apps/fpa/permissions.py`` : le code fin
``entites_administrer`` est LISIBLE via ``user.has_erp_permission`` mais son
enregistrement dans ``apps.roles.models.ALL_PERMISSIONS`` (pour être
assignable depuis l'UI de gestion des rôles) est HORS PÉRIMÈTRE de cette
session (``apps/roles`` appartient à la plateforme, NTADM39 non construit
ici) — le repli de palier ``is_admin_role`` garantit l'enforcement dès
aujourd'hui, indépendamment de ce futur enregistrement.
"""
from rest_framework.permissions import BasePermission

ENTITES_ADMINISTRER = 'entites_administrer'


class IsAdministrateur(BasePermission):
    """Superuser, palier admin (``is_admin_role``), ou porteur explicite du
    code fin ``entites_administrer``."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        if getattr(user, 'is_admin_role', False):
            return True
        try:
            return bool(user.has_erp_permission(ENTITES_ADMINISTRER))
        except Exception:
            return False
