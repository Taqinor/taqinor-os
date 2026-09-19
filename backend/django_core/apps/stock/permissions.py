"""NTP2P36 — permission FINE sur la validation d'un dossier fournisseur.

``DossierOnboardingFournisseurViewSet.valider_dossier`` (NTP2P7, action
``valider-dossier``) n'était gardée QUE par le palier grossier hérité
(``IsResponsableOrAdmin``) : tout compte Responsable/Admin pouvait valider ou
rejeter un dossier d'entrée en relation fournisseur. Ce module ajoute le code
fin catalogué par NTP2P36 (``roles.ALL_PERMISSIONS``), EN PLUS de
``IsResponsableOrAdmin`` — jamais à sa place, même patron que
``apps/btp_chantier/permissions.py`` (NTCON26) et
``apps/installations/permissions.py`` (NTP2P36).

Repli LÉGACY conservé via ``core.permissions._user_has_or_legacy`` : un compte
HÉRITÉ sans ``Role`` fin (palier Responsable/Admin via ``role_legacy``) garde
exactement son accès actuel ; un rôle FIN doit désormais porter le code pour
que la case correspondante soit administrable dans l'éditeur de rôles.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from core.permissions import _user_has_or_legacy

#: Code fin NTP2P36 — inscrit au catalogue ``roles.ALL_PERMISSIONS``.
PERM_VALIDER_DOSSIER_FOURNISSEUR = 'valider_dossier_fournisseur'


class PeutValiderDossierFournisseur(BasePermission):
    """``valider_dossier_fournisseur`` — valide/rejette un dossier
    d'onboarding fournisseur en attente (NTP2P7, action ``valider-dossier``)."""

    message = (
        "Permission « valider_dossier_fournisseur » requise pour valider un "
        "dossier fournisseur.")

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route interne.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, PERM_VALIDER_DOSSIER_FOURNISSEUR)
