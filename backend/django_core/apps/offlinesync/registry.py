"""NTMOB1 — registre des handlers de rejeu (un par `op_type`).

Le moteur hors-ligne ne connaît AUCUN modèle métier : il route chaque opération
vers un handler enregistré par `op_type`. Un handler :

    def handler(company, user, payload) -> dict

  * reçoit la société posée SERVEUR (jamais lue du corps) et l'utilisateur
    acteur ;
  * résout sa cible via le `selectors.py` de l'app visée (borné société) et
    écrit via son `services.py` — JAMAIS en important ses `models`/`views`
    (règle de frontière cross-app) ;
  * lève ``OfflineOpError`` (message FR prêt à afficher) sur une erreur
    applicative attendue : l'op est refusée proprement, le lot CONTINUE ;
  * renvoie un dict JSON-sérialisable, mémorisé et renvoyé tel quel au rejeu.

Un handler DOIT être écrit « last-write-wins » (il POSE un état, jamais un
incrément) : deux terminaux qui se reconnectent dans le désordre convergent.
"""


class OfflineOpError(Exception):
    """Erreur applicative d'une opération (cible inconnue, corps invalide…).

    N'interrompt PAS le lot : l'op est journalisée `rejetee` avec son message et
    reste rejouable après correction — elle ne disparaît jamais en silence."""


# op_type → (module, handler)
_HANDLERS = {}
# NTMOB2 — op_type → resolveur(company, payload) -> objet cible | None.
# FACULTATIF et séparé du registre principal : ``get()`` garde son contrat de
# paire, et un op_type sans resolveur se comporte exactement comme sous NTMOB1
# (aucune garde de version, aucun conflit possible).
_RESOLVEURS = {}


def register(op_type, module, handler, resolveur=None):
    """Enregistre (ou remplace) le handler d'un `op_type`.

    `module` doit être une valeur de ``OfflineOperation.Module`` — la validation
    est faite à l'enregistrement pour qu'un module inconnu explose au démarrage,
    jamais au milieu d'un lot de synchro.

    `resolveur` (NTMOB2, facultatif) est la fonction qui retrouve
    l'ENREGISTREMENT CIBLE de l'op — ``resolveur(company, payload)`` — pour que
    le moteur puisse comparer sa version serveur à celle que le terminal avait
    lue. Il ne doit RIEN écrire ; il peut renvoyer ``None`` (cible inconnue :
    c'est le handler qui refusera, avec son propre message)."""
    from .models import OfflineOperation

    valides = {c for c, _ in OfflineOperation.Module.choices}
    if module not in valides:
        raise ValueError(
            f'Module inconnu « {module} » pour l’op « {op_type} » '
            f'(attendus : {", ".join(sorted(valides))}).')
    if not callable(handler):
        raise ValueError(f'Handler non appelable pour l’op « {op_type} ».')
    if resolveur is not None and not callable(resolveur):
        raise ValueError(f'Resolveur non appelable pour l’op « {op_type} ».')
    _HANDLERS[op_type] = (module, handler)
    if resolveur is None:
        _RESOLVEURS.pop(op_type, None)
    else:
        _RESOLVEURS[op_type] = resolveur
    return handler


def get(op_type):
    """Renvoie ``(module, handler)`` ou ``None`` si l'op_type est inconnu."""
    return _HANDLERS.get(op_type)


def resolveur(op_type):
    """NTMOB2 — resolveur de cible de cet op_type, ou ``None`` (pas de garde)."""
    return _RESOLVEURS.get(op_type)


def registered_op_types():
    """Liste triée des `op_type` connus (introspection / écran de diagnostic)."""
    return sorted(_HANDLERS)


def modules_actifs():
    """Modules ayant au moins un handler enregistré."""
    return sorted({module for module, _ in _HANDLERS.values()})
