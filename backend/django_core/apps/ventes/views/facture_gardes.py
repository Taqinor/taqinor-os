"""Gardes PARTAGÉES des vues facture (VNT98) : ``PeutEncaisser`` sert les
gestes d'encaissement (``views/facture_encaissement.py``) ET
``creer_avoir`` (rectificatifs) — un module à part, jamais un ré-export."""

from authentication.permissions import HasPermissionOrLegacy


#: ASEC29 / D-ASEC-1 — LA garde des gestes d'argent : le code ``encaisser``
#: (Administrateur, Directeur, Commercial et Commercial responsable par
#: défaut ; JAMAIS Commercial terrain, Technicien ni Admin RH). Aucune liste
#: de rôles codée ici : le code est la seule source (compte hérité sans rôle
#: fin = palier responsable, comme ``HasPermissionOrLegacy``).
PeutEncaisser = HasPermissionOrLegacy('encaisser')
