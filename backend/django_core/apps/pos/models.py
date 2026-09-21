"""Modèles de l'app « pos » — PARQUÉE (MVP solaire, 20/09/2026).

Les modèles sont sortis de l'état Django par la migration ``solmvp_coquille``
(état seul, ``database_operations=[]``). Les TABLES et toutes leurs
lignes sont INTACTES en base — rien n'est perdu.

Ne rien remettre ici : le retour du module se fait par la recette de
``docs/parked-modules.md`` §5 (restauration depuis ``archive/full-erp-2026-09-20``).

TALON — ce qui suit n'est PAS du code métier : ce sont les 3
symbole(s) que des migrations GELÉES référencent encore dans ce
fichier, recopiés VERBATIM de l'original :
 ``_default_share_expiry``, ``_default_share_token``, ``default_code_retrait``.

Sans eux, ces migrations ne s'importent plus et le graphe ENTIER
casse (``AttributeError`` au chargement, visible seulement dans un
processus neuf). Aucun modèle Django ici : c'est la règle vérifiée
par ``core.parked.modeles_declares``. Au retour du module, ce talon
est REMPLACÉ par le models.py archivé (docs/parked-modules.md §5).
"""


from django.utils import timezone


def default_code_retrait():
    import secrets
    return secrets.token_hex(3).upper()


def _default_share_token():
    import secrets
    return secrets.token_urlsafe(32)


def _default_share_expiry():
    from datetime import timedelta
    return timezone.now() + timedelta(days=30)
