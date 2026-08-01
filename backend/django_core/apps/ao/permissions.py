"""Permissions du module Appels d'offres (``apps.ao``) — AOF2.

Trois codes DISJOINTS déclarés dans ``apps.roles.models.ALL_PERMISSIONS`` :

* ``ao_voir``  — lecture d'un dossier d'appel d'offres ;
* ``ao_gerer`` — écriture (création/édition/suppression, actions métier) ;
* ``ao_rentabilite_voir`` — voir l'ÉCONOMIE d'un AO (coût de revient, marge,
  bénéfice). ÉLEVÉE (``ELEVATED_PERMISSIONS``) : un non-administrateur ne peut
  jamais l'octroyer, et elle n'est mappée sur AUCUN rôle
  Responsable/Commercial/Technicien/Utilisateur — seuls Directeur et
  Administrateur la portent, par héritage d'``ALL_PERMISSIONS``.

Les deux premiers sont consommés en ``read_permission``/``write_permission``
par le socle de viewsets AO (``ScopedPermission``, cf. ``core.permissions``).
Le troisième garde des ENDPOINTS SÉPARÉS (économie/rentabilité) via la classe
``CanViewAoRentabilite`` ci-dessous, calquée sur ``audit.views``
``CanViewActivityLog``.

Règle produit gravée : ``prix_achat``, coût de revient, marge et bénéfice ne
sortent JAMAIS dans un rendu remis au maître d'ouvrage. Cette permission garde
la surface INTERNE ; elle n'autorise aucune sortie client.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

#: Codes de permission du domaine AO (source unique — jamais de littéral
#: dupliqué dans un viewset).
AO_VOIR = 'ao_voir'
AO_GERER = 'ao_gerer'
AO_RENTABILITE_VOIR = 'ao_rentabilite_voir'


class CanViewAoRentabilite(BasePermission):
    """Permission « ao_rentabilite_voir » (Directeur/Administrateur seulement).

    AUCUN repli historique (contrairement à ``ScopedPermission``) : un compte
    SANS rôle fin n'a PAS accès à l'économie d'un AO. C'est délibéré — le repli
    légacy ``is_responsable`` rouvrirait exactement la fuite de marge que AOF2
    ferme (tout le palier Responsable voyait l'AO entier). Superuser toujours
    autorisé, comme partout ailleurs dans le dépôt.
    """
    message = "Accès à l'économie de l'appel d'offres non autorisé."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        if not getattr(user, 'role_id', None):
            return False
        return user.has_erp_permission(AO_RENTABILITE_VOIR)
