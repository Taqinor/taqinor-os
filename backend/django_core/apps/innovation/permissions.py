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
"""
from authentication.permissions import (
    IsAdminOrResponsableTier, IsAnyRole, IsResponsableOrAdmin,
)


class IdeasSeeAll(IsAdminOrResponsableTier):
    """``ideas_see_all`` — surfaces d'administration de la boîte à idées
    (tableau de bord, export .xlsx, actions en masse) : palier
    Directeur/Admin, jamais le palier limité (Utilisateur/Commercial)."""


class IdeasVote(IsAnyRole):
    """``ideas_vote`` — lire, proposer, voter : tout utilisateur interne
    connecté de la société, sans palier."""


class IdeasChangeStatus(IsResponsableOrAdmin):
    """``ideas_change_status`` — transitions de statut (examiner/retenir/
    réaliser/fermer) : palier Directeur/Responsable."""


class IdeasModerate(IsResponsableOrAdmin):
    """``ideas_moderate`` — modération de contenu (masquer une idée sans la
    supprimer) : palier Directeur/Responsable."""
