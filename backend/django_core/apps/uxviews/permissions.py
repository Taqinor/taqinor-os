"""NTUX31 — permissions FINES par rôle sur les vues sauvegardées.

Avant ce module, partager une vue à l'équipe (NTUX1) n'était gardé QUE par le
réglage société ``UxParametres.permettre_vues_partagees_equipe`` (NTUX27, aucun
rôle) et ``definir-par-defaut-role`` (NTUX2) QUE par le palier grossier hérité
(``IsResponsableOrAdmin`` — ``CustomUser.is_responsable``). Ni l'un ni l'autre
n'était administrable au cas par cas dans la matrice de rôles.

Ces deux gardes fines s'ajoutent EN PLUS des gardes existantes (jamais à leur
place — même patron que ``apps/btp_chantier/permissions.py`` NTCON26) : un
compte HÉRITÉ sans rôle fin (``user.role_id`` vide) garde EXACTEMENT son accès
actuel, via le repli légacy de ``core.permissions._user_has_or_legacy`` ; un
rôle FIN doit désormais porter le code pour que la case correspondante puisse
être décochée dans l'éditeur de rôles sans toucher au code.

Nommage : le plan écrit les clés en pointé ; le registre du dépôt
(``roles.ALL_PERMISSIONS``) reste en souligné sans exception :

    ux.vue.partager_equipe     -> ux_vue_partager_equipe
    ux.vue.definir_defaut_role -> ux_vue_definir_defaut_role
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from core.permissions import _user_has_or_legacy

#: Codes fins NTUX31 — inscrits au catalogue ``roles.ALL_PERMISSIONS``.
PERM_PARTAGER_EQUIPE = 'ux_vue_partager_equipe'
PERM_DEFINIR_DEFAUT_ROLE = 'ux_vue_definir_defaut_role'


class _PermissionFineUx(BasePermission):
    """Base : exige ``code`` (repli légacy conservé via ``_user_has_or_legacy``)."""

    code: str | None = None
    message = 'Permission UX insuffisante pour cette action.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route interne.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, self.code)


class PeutPartagerVueEquipe(_PermissionFineUx):
    """``ux.vue.partager_equipe`` — partager une vue à l'équipe (NTUX1)."""

    code = PERM_PARTAGER_EQUIPE
    message = (
        "Permission « ux.vue.partager_equipe » requise pour partager une "
        "vue à l'équipe.")


class PeutDefinirVueDefautRole(_PermissionFineUx):
    """``ux.vue.definir_defaut_role`` — définir une vue par défaut de rôle (NTUX2)."""

    code = PERM_DEFINIR_DEFAUT_ROLE
    message = (
        "Permission « ux.vue.definir_defaut_role » requise pour définir une "
        "vue par défaut de rôle.")
