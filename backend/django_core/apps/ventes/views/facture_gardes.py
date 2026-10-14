"""VNT98 — gardes partagées par plusieurs groupes d'actions de
``FactureViewSet`` (encaissement et rectificatifs), déplacées telles quelles
depuis ``views/facture.py``.
"""
from authentication.permissions import HasPermissionOrLegacy

#: ASEC29 / D-ASEC-1 — LA garde des gestes d'argent : le code ``encaisser``
#: (Administrateur, Directeur, Commercial et Commercial responsable par
#: défaut ; JAMAIS Commercial terrain, Technicien ni Admin RH). Aucune liste
#: de rôles codée ici : le code est la seule source (compte hérité sans rôle
#: fin = palier responsable, comme ``HasPermissionOrLegacy``).
PeutEncaisser = HasPermissionOrLegacy('encaisser')
