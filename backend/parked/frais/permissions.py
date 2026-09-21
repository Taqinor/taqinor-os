"""NTP2P36 — permission FINE sur la validation DIRECTION d'une note de frais.

``NoteFraisViewSet.valider`` (``apps.compta.views`` — le posting comptable de
FG135/136 reste dans ``compta`` par la frontière ODX15, cf.
``apps/compta/models.py``) n'était gardée QUE par le palier grossier
``compta_valider`` (YRBAC13), IDENTIQUE pour toute note — y compris une note
ESCALADÉE en direction (``NoteFrais.escalade_direction``, NTP2P11 : le montant
dépasse le seuil configuré). Ce module ajoute le code fin catalogué par
NTP2P36 (``roles.ALL_PERMISSIONS``), EN PLUS de ``compta_valider`` et
UNIQUEMENT pour une note escaladée — une note ordinaire reste validable par
tout porteur de ``compta_valider``, même patron que
``apps/btp_chantier/permissions.py`` (NTCON26).

Repli LÉGACY conservé via ``core.permissions._user_has_or_legacy`` : un compte
HÉRITÉ sans ``Role`` fin (palier Responsable/Admin) garde exactement son accès
actuel ; un rôle FIN doit désormais porter le code pour que la case
correspondante soit administrable dans l'éditeur de rôles.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from core.permissions import _user_has_or_legacy

#: Code fin NTP2P36 — inscrit au catalogue ``roles.ALL_PERMISSIONS``.
PERM_APPROUVER_NOTE_FRAIS_DIRECTION = 'approuver_note_frais_direction'


class PeutApprouverNoteFraisDirection(BasePermission):
    """``approuver_note_frais_direction`` — valide une note de frais
    escaladée en direction (NTP2P11)."""

    message = (
        "Permission « approuver_note_frais_direction » requise pour valider "
        "une note de frais escaladée en direction.")

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route interne.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, PERM_APPROUVER_NOTE_FRAIS_DIRECTION)
