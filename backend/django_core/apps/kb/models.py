"""Modèles de l'app « kb » — PARQUÉE (MVP solaire, 20/09/2026).

Les modèles sont sortis de l'état Django par la migration ``solmvp_coquille``
(état seul, ``database_operations=[]``). Les TABLES et toutes leurs
lignes sont INTACTES en base — rien n'est perdu.

Ne rien remettre ici : le retour du module se fait par la recette de
``docs/parked-modules.md`` §5 (restauration depuis ``archive/full-erp-2026-09-20``).

TALON — ce qui suit n'est PAS du code métier : ce sont les 1
symbole(s) que des migrations GELÉES référencent encore dans ce
fichier, recopiés VERBATIM de l'original :
 ``_default_partage_token``.

Sans eux, ces migrations ne s'importent plus et le graphe ENTIER
casse (``AttributeError`` au chargement, visible seulement dans un
processus neuf). Aucun modèle Django ici : c'est la règle vérifiée
par ``core.parked.modeles_declares``. Au retour du module, ce talon
est REMPLACÉ par le models.py archivé (docs/parked-modules.md §5).
"""


import secrets


def _default_partage_token():
    """XKB19 — Jeton de partage public long, imprévisible et URL-safe.

    Réutilise EXACTEMENT le même générateur que ``ged.PartageGed.token``
    (``secrets.token_urlsafe``, 32 octets → ~43 caractères) : le jeton est le
    SEUL secret qui authentifie l'accès public à un article partagé.
    """
    return secrets.token_urlsafe(32)
