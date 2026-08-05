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


# ── NTADM39 — permissions fines (RESSERREMENT au sein du palier admin) ──────
# Codes du registre (apps.roles.models.ALL_PERMISSIONS) — voir leur docstring
# de bloc pour le pourquoi du nommage underscore + `_voir`.
ADMINOPS_ENTITES_GERER = 'adminops_entites_gerer'
ADMINOPS_SANDBOX_CREER = 'adminops_sandbox_creer'
ADMINOPS_CONFIG_PACKAGE_EXPORTER = 'adminops_config_package_exporter'
ADMINOPS_CONFIG_PACKAGE_IMPORTER = 'adminops_config_package_importer'
ADMINOPS_LICENCES_VOIR = 'adminops_licences_voir'


def a_permission_fine(user, code):
    """NTADM39 — Vrai si `user` peut effectuer l'action gardée par `code`.

    Appelé APRÈS ``IsAdministrateur`` (le palier admin est déjà acquis) : ce
    contrôle RESSERRE encore l'accès. Rétrocompat explicite (bug-class #25 —
    jamais un ``get_permissions()`` qui écraserait silencieusement les
    ``permission_classes`` par @action ; ce contrôle est un appel EXPLICITE
    dans le corps de chaque action/vue) :
      * superuser Django → toujours vrai (jamais bloqué) ;
      * compte SANS Role fin (legacy, ``role_legacy`` seul) → toujours vrai
        (comportement actuel préservé, comme ``CustomUser._role_grants_write``) ;
      * rôle SYSTÈME (``est_systeme=True`` — Directeur/Administrateur/…) →
        toujours vrai (rétrocompat : ces rôles avaient déjà accès complet) ;
      * rôle CUSTOM (``est_systeme=False``) → vrai SEULEMENT si `code` figure
        dans ``role.permissions`` (403 sinon).
    """
    if getattr(user, 'is_superuser', False):
        return True
    role = getattr(user, 'role', None)
    if role is None:
        return True  # compte hérité sans Role fin : comportement actuel préservé
    if role.est_systeme:
        return True  # rétrocompat rôles système
    return code in (role.permissions or [])
