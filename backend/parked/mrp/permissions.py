"""Permissions DRF de l'app `mrp` (NTMFG33) — matrice de rôle Technicien /
Responsable / Admin.

Alignée sur `authentication.CustomUser.menu_tier` (le PALIER de rôle FAISANT
AUTORITÉ, N103) plutôt que sur `authentication.permissions.IsResponsableOrAdmin`
(basé sur `is_responsable`, qui passe dès qu'un rôle porte NE SERAIT-CE
QU'UNE permission d'écriture — même une permission MRP-terminal isolée). Un
Technicien outillé pour le terminal atelier (NTMFG8) ne doit JAMAIS passer à
tort les gardes Responsable/Admin de ce module (`analyse-couts/`,
`parametres/`) simplement parce qu'il détient une permission d'écriture MES —
`menu_tier` ne dérive QUE du signal de permission faisant autorité
(`roles_gerer`/`users_voir`) ou du nom système du rôle, jamais d'une
permission métier isolée.

Trois paliers (cf. `frontend/src/features/mrp/module.config.jsx`,
`ROLES`/`ROLES_ADMIN` — même matrice côté nav) :

* **Technicien** (`menu_tier == 'normal'`) — lecture OF + terminal atelier
  (démarrer/pauser/reprendre/terminer SES opérations, NTMFG8), AUCUN accès au
  coût standard (NTMFG11) ni aux paramètres du module (NTMFG29).
* **Responsable production** (`menu_tier == 'responsable'`) — tout Technicien
  + création/planification OF (NTMFG3), Gantt (NTMFG7), validation ECO
  (NTMFG15), coût standard (NTMFG11) — comme la nav frontend existante.
* **Admin** (`menu_tier == 'admin'`) — tout + `ParametresMRP` (NTMFG29).

Le superuser passe toujours (même convention que `authentication.permissions`).
"""
from rest_framework.permissions import BasePermission


def _menu_tier(user):
    return getattr(user, 'menu_tier', None)


class EstTechnicienResponsableOuAdmin(BasePermission):
    """Palier Technicien et au-dessus — terminal atelier MES (NTMFG8) : le
    palier limité EST le Technicien dans ce module (pas de rôle fin dédié
    dans le vocabulaire existant, cf. commentaire de
    `features/mrp/module.config.jsx`)."""

    message = 'Action réservée à un compte interne (Technicien, Responsable ou Admin).'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        return _menu_tier(user) in ('normal', 'responsable', 'admin')


class EstResponsableOuAdminMRP(BasePermission):
    """Palier Responsable production et au-dessus — planification OF
    (NTMFG3), Gantt (NTMFG7), ECO (NTMFG15), coût standard (NTMFG11),
    tableau de bord (NTMFG22). Un Technicien (palier `normal`) est REFUSÉ
    même s'il détient par ailleurs une permission d'écriture fine."""

    message = 'Action réservée à un Responsable production ou un Admin.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        return _menu_tier(user) in ('responsable', 'admin')


class EstAdminMRP(BasePermission):
    """Palier Admin UNIQUEMENT — `ParametresMRP` (NTMFG29). Un Responsable
    « peut planifier mais pas modifier les paramètres société »."""

    message = 'Action réservée à un Admin.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        return _menu_tier(user) == 'admin'
