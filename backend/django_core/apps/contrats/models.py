"""Modèles de l'app « contrats » — PARQUÉE (MVP solaire, 20/09/2026).

Les modèles sont sortis de l'état Django par la migration ``solmvp_coquille``
(état seul, ``database_operations=[]``). Les TABLES et toutes leurs
lignes sont INTACTES en base — rien n'est perdu.

Ne rien remettre ici : le retour du module se fait par la recette de
``docs/parked-modules.md`` §5 (restauration depuis ``archive/full-erp-2026-09-20``).

TALON — ce qui suit n'est PAS du code métier : ce sont les 1
symbole(s) que des migrations GELÉES référencent encore dans ce
fichier, recopiés VERBATIM de l'original :
 ``_default_depot_contrepartie_token``.

Sans eux, ces migrations ne s'importent plus et le graphe ENTIER
casse (``AttributeError`` au chargement, visible seulement dans un
processus neuf). Aucun modèle Django ici : c'est la règle vérifiée
par ``core.parked.modeles_declares``. Au retour du module, ce talon
est REMPLACÉ par le models.py archivé (docs/parked-modules.md §5).
"""


import secrets


def _default_depot_contrepartie_token():
    """Jeton de dépôt long, imprévisible et URL-safe (pattern ``PartageGed``).

    Même générateur que ``ged.PartageGed`` / ``ventes.ShareLink``
    (``secrets.token_urlsafe(32)`` → ~43 caractères) : cryptographiquement
    fort, impossible à deviner ou à énumérer. C'est le SEUL secret qui
    authentifie un dépôt externe (la contrepartie n'a pas de compte ERP).
    """
    return secrets.token_urlsafe(32)
