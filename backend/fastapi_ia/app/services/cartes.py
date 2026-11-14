"""COP1 — cartes de la réponse de l'assistant (contrat ``assistant_reponse.json``).

Une seule fabrique, lue par les DEUX moteurs (LangChain et natif) : la liste
ORDONNÉE de toutes les sorties structurées d'un tour. Avant elle, l'endpoint ne
remontait que la DERNIÈRE proposition et le DERNIER résultat, et aplatissait le
corps de l'action à la racine de ``result`` pendant que l'écran lisait
``result.data`` : aucune carte d'action interne ne s'affichait.

Entrée : le collecteur partagé d'un tour, alimenté par
``action_tools.run_catalogue_action`` — des dicts ``{"type": "proposal", …}`` et
``{"type": "result", …}`` (les entrées ``erreur`` et ``signalement`` ne sont pas
des cartes). Sortie : des cartes ``proposition`` / ``resultat`` au format du
contrat. Module PUR : aucun réseau, aucun Redis, aucune dépendance LLM.
"""
from __future__ import annotations

from typing import Any, Optional

#: Durée de vie par défaut d'une proposition (secondes) quand la sortie ne la
#: porte pas — même valeur que ``ACTION_PROPOSAL_TTL`` par défaut.
EXPIRATION_DEFAUT_S = 300


def _donnees(data: Any) -> dict:
    """``donnees`` est TOUJOURS un objet : une liste rendue par l'endpoint
    devient ``{"lignes": [...]}``, une valeur nue ``{"valeur": …}``."""
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"lignes": data}
    if data is None:
        return {}
    return {"valeur": data}


def carte_depuis_sortie(sortie: dict) -> Optional[dict]:
    """Une sortie du collecteur -> sa carte, ou None si ce n'en est pas une."""
    genre = sortie.get("type")
    if genre == "proposal":
        return {
            "type": "proposition",
            "action_key": sortie.get("action_key") or "",
            "libelle": sortie.get("libelle") or "",
            "apercu": sortie.get("human_preview") or "",
            "confirm_token": sortie.get("confirm_token"),
            "expire_dans_s": int(sortie.get("expire_dans_s")
                                 or EXPIRATION_DEFAUT_S),
        }
    if genre == "result":
        return {
            "type": "resultat",
            "action_key": sortie.get("action_key") or "",
            "libelle": sortie.get("libelle") or "",
            "carte": sortie.get("carte"),
            "donnees": _donnees(sortie.get("data")),
        }
    return None


def construire_cartes(action_outputs: Optional[list]) -> list[dict]:
    """Toutes les cartes du tour, dans l'ordre où les outils ont répondu."""
    cartes = []
    for sortie in action_outputs or []:
        if not isinstance(sortie, dict):
            continue
        carte = carte_depuis_sortie(sortie)
        if carte is not None:
            cartes.append(carte)
    return cartes
