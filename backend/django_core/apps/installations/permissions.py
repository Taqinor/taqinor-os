"""NTP2P36 — permission FINE sur la décision d'une étape d'approbation d'achat.

``DemandeAchatViewSet.approuver_etape`` (NTP2P2, action ``approuver-etape``)
n'était gardée QUE par le palier grossier hérité (``IsResponsableOrAdmin``) :
tout compte Responsable/Admin pouvait décider une étape du plan d'approbation,
même sans siéger dans le circuit de validation achats. Ce module ajoute le
code fin catalogué par NTP2P36 (``roles.ALL_PERMISSIONS``), EN PLUS de
``IsResponsableOrAdmin`` — jamais à sa place, même patron que
``apps/btp_chantier/permissions.py`` (NTCON26) et ``apps/uxviews/permissions.py``
(NTUX31).

Repli LÉGACY conservé via ``core.permissions._user_has_or_legacy`` : un compte
HÉRITÉ sans ``Role`` fin (palier Responsable/Admin via ``role_legacy``) garde
exactement son accès actuel ; un rôle FIN doit désormais porter le code pour
que la case correspondante soit administrable dans l'éditeur de rôles.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from core.permissions import _user_has_or_legacy

#: Code fin NTP2P36 — inscrit au catalogue ``roles.ALL_PERMISSIONS``.
PERM_APPROUVER_DEMANDE_ACHAT = 'approuver_demande_achat'


class PeutApprouverDemandeAchat(BasePermission):
    """``approuver_demande_achat`` — décider une étape du plan d'approbation
    d'une demande d'achat (NTP2P2, action ``approuver-etape``)."""

    message = (
        "Permission « approuver_demande_achat » requise pour décider une "
        "étape d'approbation d'achat.")

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route interne.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, PERM_APPROUVER_DEMANDE_ACHAT)
