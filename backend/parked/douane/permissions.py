"""NTLOG43 - permissions par role, module douane.

Reutilise le mecanisme PLATEFORME ``core.permissions.ScopedPermission``
(defaut de ``core.viewsets.CompanyScopedModelViewSet``) plutot qu'une classe
de role ad hoc - motif explicite de sa docstring : « Pour un controle
lecture!=ecriture, poser ``read_permission``/``write_permission`` ... plutot
qu'une classe de role ad hoc. » Un viewset pose juste
``write_permission = DOUANE_RESPONSABLE`` ; ``read_permission`` reste ``None``
(defaut) -> toute methode sure (GET) ne demande qu'un utilisateur authentifie
de la societe, ce qui couvre le role lecture-seule ``comptabilite`` sans
disposition supplementaire.

Codes de permission fine (reutilisent ``Role.permissions`` JSON, aucun
nouveau modele) - meme motif que ``apps/fpa/permissions.py`` /
``apps/entites/permissions.py`` :

  * ``douane_responsable``       - CRUD complet dossiers d'export (et, une
    fois NTLOG10/13 debloques, dossiers d'import + ``BaremeDouanier``).
  * ``douane_comptabilite_voir`` - marqueur du role lecture-seule
    (rapprochement comptable) assignable depuis l'UI de gestion des roles,
    une fois enregistre dans ``ALL_PERMISSIONS`` (hors perimetre, voir plus
    bas).

Note sur le suffixe ``_voir`` : ``core.permissions._user_has_or_legacy``
appelle ``has_erp_permission(code)`` DIRECTEMENT pour un compte porteur d'un
role fin (pas de repli ``is_responsable``) - donc l'enforcement ci-dessous ne
depend pas du suffixe. On le garde quand meme par convention repo (motif ERR4
sur ``CustomUser.is_responsable``, qui lui traite tout code SANS ce suffixe
comme accordant l'ecriture) : un futur code qui reutiliserait
``is_responsable``/``_role_grants_write`` pour ce role resterait donc
lecture-seule au lieu de basculer accidentellement en ecriture.

NB - enregistrer ces codes dans ``apps.roles.models.ALL_PERMISSIONS`` (pour
les rendre assignables depuis l'UI de gestion des roles) est HORS PERIMETRE
de cette lane SUPPLY (``apps/roles`` appartient a la plateforme) : reste a
faire par un run plateforme. L'ENFORCEMENT ecriture (``douane_responsable``)
est complet et independant des aujourd'hui, via ``ScopedPermission``.

Volet IMPORT (permissions sur ``dossiers-import/``, ``BaremeDouanier``
NTLOG13) NON implemente ici : NTLOG10 (GARDE 2026-07-18, WIR80) reste
BLOCKED (voir ``apps/douane/apps.py``) - seul le volet EXPORT existe
reellement dans cette app aujourd'hui."""

DOUANE_RESPONSABLE = 'douane_responsable'
DOUANE_COMPTABILITE_VOIR = 'douane_comptabilite_voir'
