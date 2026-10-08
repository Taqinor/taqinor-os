"""ADEP42 - garde d'import optionnel des tests du service FastAPI.

Un test ne peut etre SAUTE que si une dependance TIERCE est absente
(``ModuleNotFoundError`` dont le nom n'est pas ``app``/``app.*``). Toute autre
erreur a l'import (ImportError d'un nom d'``app.*``, SyntaxError, etc.) doit
FAIRE ECHOUER le test : sinon une garde (ex. ``prix_achat``) peut etre sautee
en silence.

Usage, dans le bloc d'import de chaque fichier de test ::

    try:
        from app.services import sql_agent_service as svc
    except Exception as exc:
        svc = None
        _IMPORT_ERR = exc
        verifier_import_optionnel(exc)   # re-leve si ce n'est pas une dependance absente
"""


def dependance_tierce_absente(exc):
    """True ssi ``exc`` est l'absence d'un module tiers (hors ``app``)."""
    if not isinstance(exc, ModuleNotFoundError):
        return False
    nom = (exc.name or "").split(".")[0]
    return bool(nom) and nom != "app"


def verifier_import_optionnel(exc):
    """Re-leve ``exc`` sauf si c'est l'absence d'une dependance tierce."""
    if not dependance_tierce_absente(exc):
        raise exc
