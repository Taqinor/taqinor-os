"""COP-B — relais du copilote commercial (code neuf du service de l'assistant).

`sql_agent_service` reste le moteur LangChain et sa sécurité SQL ; ce module
porte ce qui entoure un tour : l'historique remis au modèle, ce qui suit une
confirmation (carte, mémoire du tour). Contrat :
`backend/django_core/apps/agent/contract_samples/assistant_reponse.json`.

Les imports de `sql_agent_service` sont locaux (il importe ce module).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.services import cartes as _cartes

logger = logging.getLogger(__name__)

#: Valeurs de `moteur` dans la réponse (contrat `assistant_reponse.json`).
MOTEUR_LANGCHAIN = "langchain"
MOTEUR_NATIF = "natif"

#: Messages d'historique remis au modèle LangChain (2 derniers échanges).
HISTORIQUE_MODELE = 4


def historique_langchain(brut: Optional[list]) -> list:
    """Historique Redis -> messages LangChain (2 derniers échanges seulement :
    d'anciens résultats ne doivent pas contaminer une nouvelle question ; tout
    l'historique reste dans Redis pour l'écran). Un message ancien sans
    `cartes` se relit tel quel."""
    from langchain_core.messages import AIMessage, HumanMessage

    messages = []
    for msg in (brut or [])[-HISTORIQUE_MODELE:]:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content") or ""))
        elif msg.get("role") == "agent":
            messages.append(AIMessage(content=msg.get("content") or ""))
    return messages


def carte_de_confirmation(resultat: dict) -> Optional[dict]:
    """Carte `resultat` d'une confirmation réussie (`/confirm`), par la
    fabrique unique des cartes. Les clés `libelle` / `carte` du résultat de
    `confirm_proposal` sont lues par `.get()` (absentes : carte générique)."""
    return _cartes.carte_depuis_sortie({
        "type": "result",
        "action_key": resultat.get("action_key") or "",
        "libelle": resultat.get("libelle") or "",
        "carte": resultat.get("carte"),
        "data": resultat.get("data"),
    })


def apres_confirmation(service, ctx, company_id: int, user_id: int,
                       resultat: dict) -> dict[str, Any]:
    """Après une confirmation RÉUSSIE : la carte du résultat, et l'action
    écrite dans l'historique (au tour suivant, le modèle sait qu'elle a eu
    lieu). Rend `{carte, suite}` ; `suite` vaut None sous le moteur LangChain."""
    carte = carte_de_confirmation(resultat)
    libelle = (carte or {}).get("libelle") or resultat.get("action_key") or ""
    service._ajouter_historique(user_id, [{
        "role": "agent",
        "content": f"Action confirmée par l'utilisateur et exécutée : {libelle}.",
        "cartes": [carte] if carte else [],
    }])
    return {"carte": carte, "suite": None}
