"""Modèles de l'app « btp_chantier » — PARQUÉE (MVP solaire, 20/09/2026).

Les modèles sont sortis de l'état Django par la migration ``solmvp_coquille``
(état seul, ``database_operations=[]``). Les TABLES et toutes leurs
lignes sont INTACTES en base — rien n'est perdu.

Ne rien remettre ici : le retour du module se fait par la recette de
``docs/parked-modules.md`` §5 (restauration depuis ``archive/full-erp-2026-09-20``).

TALON — ce qui suit n'est PAS du code métier : ce sont les 2
symbole(s) que des migrations GELÉES référencent encore dans ce
fichier, recopiés VERBATIM de l'original :
 ``_default_btp_token``, ``lots_types_defaut``.

Sans eux, ces migrations ne s'importent plus et le graphe ENTIER
casse (``AttributeError`` au chargement, visible seulement dans un
processus neuf). Aucun modèle Django ici : c'est la règle vérifiée
par ``core.parked.modeles_declares``. Au retour du module, ce talon
est REMPLACÉ par le models.py archivé (docs/parked-modules.md §5).
"""


import secrets


def _default_btp_token():
    """Jeton public long/imprévisible (NTCON8/NTCON12) — réplique le motif
    ``ged.PartageGed``/``ventes.ShareLink`` (``secrets.token_urlsafe``, 32
    octets) SANS importer ces apps : ``btp_chantier`` génère son propre jeton
    local, résolu par lookup (jamais un JWT/token signé)."""
    return secrets.token_urlsafe(32)


LOTS_TYPES_DEFAUT = [
    'Gros-œuvre', 'Électricité', 'Plomberie', 'CVC', 'Finitions',
]


def lots_types_defaut():
    """Défaut CALLABLE du champ JSON (jamais une liste mutable partagée)."""
    return list(LOTS_TYPES_DEFAUT)
