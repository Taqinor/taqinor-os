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
