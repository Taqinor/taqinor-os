"""Permissions granulaires du module Innovation (NTIDE22).

Quatre gardes NOMMÉES, une par action métier de la boîte à idées, chacune un
alias explicite au-dessus d'un palier générique déjà éprouvé
(``authentication.permissions``, foundation app — import autorisé hors
frontière cross-app). Documenter l'intention à l'endroit où la garde est
DÉCLARÉE (ici) plutôt qu'au point d'utilisation (``views.py``) — même
comportement qu'avant NTIDE22, nommage explicite en plus :

    * ``IdeasSeeAll``       — ``ideas_see_all``, palier Directeur/Admin par
                              défaut (tableau de bord, export, actions en
                              masse — surfaces d'administration de la boîte
                              à idées).
    * ``IdeasVote``         — ``ideas_vote``, tout utilisateur interne connecté
                              (lecture/proposition/vote — alias de
                              ``IsAnyRole``, aucune restriction de palier).
    * ``IdeasChangeStatus`` — ``ideas_change_status``, palier
                              Directeur/Responsable (transitions NTIDE5 :
                              examiner/retenir/réaliser/fermer).
    * ``IdeasModerate``     — ``ideas_moderate``, palier Directeur (masquer
                              une idée sans la supprimer, NTIDE19).
    * ``IdeasAggregateRead`` — ``ideas_agrege_voir``, NTIDE49 : le rôle
                              « Viewer » (permission ERP fine
                              ``ideas_agrege_voir``, ``Role.permissions``)
                              lit les tableaux de bord/résumés AGRÉGÉS
                              (idées/campagnes/feedback) — jamais le détail,
                              jamais de vote/proposition (cf. ``IdeasVote``
                              ci-dessous, qui l'exclut explicitement).
"""
from rest_framework.permissions import BasePermission

from authentication.permissions import (
    IsAdminOrResponsableTier, IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)

# NTIDE49 — permission ERP fine portée par un rôle « Viewer » (lecture seule
# agrégée, jamais le détail, jamais de vote/proposition). Un rôle qui la
# porte n'est PAS pour autant promu au palier Directeur/Admin/Responsable —
# suffixe ``_voir`` (cf. ``CustomUser._role_grants_write``) : un rôle qui ne
# porte QUE cette permission reste « lecture seule » au sens du palier
# hérité (``is_responsable``/``is_admin_role`` restent False).
IDEAS_AGGREGATE_PERMISSION = 'ideas_agrege_voir'


def _est_viewer_agrege(user):
    """True si ``user`` porte la permission fine ``ideas_agrege_voir`` SANS
    bénéficier par ailleurs du palier Directeur/Admin/Responsable
    (``IsAdminOrResponsableTier``) — c'est la définition opérationnelle du
    rôle « Viewer » de ce module (NTIDE49) : un Directeur/Responsable qui
    porterait aussi ce code (redondant) reste géré par son palier normal,
    jamais restreint par cette fonction."""
    role = getattr(user, 'role', None)
    if not role or IDEAS_AGGREGATE_PERMISSION not in (role.permissions or []):
        return False
    return not (
        getattr(user, 'is_admin_role', False)
        or getattr(user, 'is_responsable', False))


class IdeasSeeAll(IsAdminOrResponsableTier):
    """``ideas_see_all`` — surfaces d'administration de la boîte à idées
    (tableau de bord, export .xlsx, actions en masse) : palier
    Directeur/Admin, jamais le palier limité (Utilisateur/Commercial)."""


class IdeasVote(IsAnyRole):
    """``ideas_vote`` — lire, proposer, voter : tout utilisateur interne
    connecté de la société, sans palier — SAUF le rôle « Viewer » (NTIDE49,
    ``ideas_agrege_voir``) : lecture seule agrégée, jamais le détail, jamais
    de vote/proposition (cf. ``IdeasAggregateRead``)."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return not _est_viewer_agrege(request.user)


class IdeasChangeStatus(IsResponsableOrAdmin):
    """``ideas_change_status`` — transitions de statut (examiner/retenir/
    réaliser/fermer) : palier Directeur/Responsable."""


class IdeasModerate(IsResponsableOrAdmin):
    """``ideas_moderate`` — modération de contenu (masquer une idée sans la
    supprimer) : palier Directeur/Responsable."""


class FeedbackModerate(IsAdminRole):
    """``feedback_moderate`` — modération du feedback produit (NTIDE47,
    masquer sans supprimer) : palier Directeur/Administrateur STRICT
    (``IsAdminRole``, ``user.is_admin_role``) — contrairement à
    ``IdeasModerate`` sur les idées, jamais le palier Responsable ici."""


class IdeasAggregateRead(BasePermission):
    """``ideas_agrege_voir`` — NTIDE49 : lecture des agrégats (tableaux de
    bord idées/campagnes, résumé feedback) : palier Directeur/Admin/
    Responsable (``IdeasSeeAll``, comportement inchangé) OU rôle « Viewer »
    (permission ERP fine ``ideas_agrege_voir`` SANS palier — cf.
    ``_est_viewer_agrege``). Jamais le détail (listes/fiches individuelles
    restent gardées par ``IdeasSeeAll``/``IdeasVote``, qui excluent déjà ce
    rôle)."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return bool(
            IdeasSeeAll().has_permission(request, view)
            or _est_viewer_agrege(user))
