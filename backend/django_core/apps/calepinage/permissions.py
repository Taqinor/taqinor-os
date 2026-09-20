"""Permissions du module Calepinage (``apps.calepinage``) — CAL6.

Deux codes DISJOINTS, déclarés dans ``apps.roles.models.ALL_PERMISSIONS`` :

* ``calepinage_voir``  — lecture d'un calepinage (GET/HEAD/OPTIONS) ;
* ``calepinage_gerer`` — écriture (création/édition/suppression, actions
  métier : enregistrer un layout, créer/retenir une variante, dupliquer).

Ce fichier est la SOURCE UNIQUE des codes du domaine (patron
``apps/ao/permissions.py``) : aucun littéral de permission ne vit dans un
viewset. Les viewsets les consomment en ``read_permission`` /
``write_permission`` (socle ``ScopedPermission``, cf. ``core.permissions``).

PALIER : celui de ``ventes``. Concevoir une toiture est un geste commercial
courant — les mêmes rôles qui voient/éditent un devis voient/éditent son
calepinage. AUCUNE permission ÉLEVÉE n'est touchée : ni ``prix_achat_voir``,
ni ``marge_voir``, ni ``roles_gerer``. Le module n'expose aucune donnée de
coût de revient, donc il n'a besoin d'aucun code élevé.
"""
from __future__ import annotations

#: Lecture d'un calepinage (source unique — jamais de littéral en viewset).
CAL_VOIR = 'calepinage_voir'

#: Écriture / actions métier sur un calepinage.
CAL_GERER = 'calepinage_gerer'

#: Les deux codes du domaine, pour les gardes et les tests.
CODES = (CAL_VOIR, CAL_GERER)


# ── CAL16 — les DEUX gardes DRF par action (jamais un littéral en viewset) ──
#
# Le cliquet ``core.tests.test_action_permissions`` refuse toute ``@action``
# neuve gardée seulement au niveau CLASSE : le module Calepinage est neuf, donc
# sa dette admise est ZÉRO et chaque action déclare sa garde. Ces deux classes
# sont ce que les actions déclarent — elles portent le CODE du domaine, pas un
# palier de rôle, pour qu'une action de lecture ne puisse jamais se retrouver
# gardée en écriture (ni l'inverse) par distraction.

from rest_framework.permissions import BasePermission  # noqa: E402

from core.permissions import _user_has_or_legacy  # noqa: E402


class _PermissionCalepinage(BasePermission):
    """Socle commun : compte INTERNE authentifié + un code de permission.

    Le refus des comptes PORTAIL (``portee != 'interne'``) reprend mot pour
    mot celui de ``core.permissions.ScopedPermission`` : un client du portail
    n'a aucune raison d'atteindre une route interne, même en lecture.
    """

    code = ''

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, self.code)


class PeutVoirCalepinage(_PermissionCalepinage):
    """Lecture d'un calepinage (``calepinage_voir``)."""

    code = CAL_VOIR


class PeutGererCalepinage(_PermissionCalepinage):
    """Écriture / action métier sur un calepinage (``calepinage_gerer``)."""

    code = CAL_GERER


class PeutLireOuEcrireCalepinage(_PermissionCalepinage):
    """CAL18 — la garde d'une ``@action`` qui sert GET **et** POST.

    Une action à deux méthodes ne peut pas déclarer une garde unique sans
    mentir d'un côté : gardée en lecture, elle laisserait écrire à un simple
    lecteur ; gardée en écriture, elle fermerait la lecture à qui a le droit
    de lire. Le code est donc choisi par la MÉTHODE, exactement comme
    ``ScopedPermission`` le fait au niveau de la classe.
    """

    def has_permission(self, request, view):
        from rest_framework.permissions import SAFE_METHODS

        garde = (PeutVoirCalepinage() if request.method in SAFE_METHODS
                 else PeutGererCalepinage())
        return garde.has_permission(request, view)
