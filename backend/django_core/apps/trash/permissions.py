"""NTUX31 — permissions FINES par rôle sur la corbeille transverse (NTUX7).

Avant ce module, `/parametres/corbeille` (liste + `{id}/restaurer/`) n'était
gardé QUE par le palier grossier hérité `IsAdminOrResponsableTier`
(`CustomUser.menu_tier` — Administrateur/Directeur OU un rôle « responsable »
système), non administrable au cas par cas dans la matrice de rôles.

Ces deux gardes fines s'ajoutent EN PLUS de `IsAdminOrResponsableTier` (jamais
à sa place — même patron que `apps/btp_chantier/permissions.py` NTCON26) : un
compte HÉRITÉ sans rôle fin garde EXACTEMENT son accès actuel via le repli
légacy de `core.permissions._user_has_or_legacy` ; un rôle FIN doit désormais
porter le code pour que la case correspondante puisse être décochée dans
l'éditeur de rôles sans toucher au code.

Nommage : le plan écrit les clés en pointé ; le registre du dépôt
(`roles.ALL_PERMISSIONS`) reste en souligné sans exception :

    ux.corbeille.consulter -> ux_corbeille_consulter
    ux.corbeille.restaurer -> ux_corbeille_restaurer
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from core.permissions import _user_has_or_legacy

#: Codes fins NTUX31 — inscrits au catalogue ``roles.ALL_PERMISSIONS``.
PERM_CONSULTER = 'ux_corbeille_consulter'
PERM_RESTAURER = 'ux_corbeille_restaurer'


class _PermissionFineCorbeille(BasePermission):
    """Base : exige ``code`` (repli légacy conservé via ``_user_has_or_legacy``)."""

    code: str | None = None
    message = 'Permission corbeille insuffisante pour cette action.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route interne.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, self.code)


class PeutConsulterCorbeille(_PermissionFineCorbeille):
    """``ux.corbeille.consulter`` — lister/lire la corbeille transverse."""

    code = PERM_CONSULTER
    message = (
        "Permission « ux.corbeille.consulter » requise pour consulter la "
        "corbeille.")


class PeutRestaurerCorbeille(_PermissionFineCorbeille):
    """``ux.corbeille.restaurer`` — restaurer un élément de la corbeille."""

    code = PERM_RESTAURER
    message = (
        "Permission « ux.corbeille.restaurer » requise pour restaurer un "
        "élément de la corbeille.")
