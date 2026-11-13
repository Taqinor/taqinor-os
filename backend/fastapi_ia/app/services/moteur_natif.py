"""COP5 — moteur NATIF de l'assistant (boucle d'outils sur l'API Messages d'Anthropic).

INTERFACE FIGÉE (contrat entre le relais et le moteur) — ce module ne connaît
NI le catalogue d'actions, NI Django, NI l'utilisateur : le relais
(``sql_agent_service``) lui remet des outils déjà prêts (schéma + fonction
d'exécution qui alimente SON collecteur de cartes), le prompt système et le
texte de la question (en-tête de tour compris). Le moteur ne fait qu'une
chose : tenir la conversation avec le modèle.

  * ``executer``  — un tour : question -> appels d'outils -> réponse finale.
  * ``reprendre`` — après une confirmation : le relais remet le résultat de
    l'ERP (déjà mis sous enveloppe « non fiable ») et le modèle CONTINUE la
    tâche là où il s'était arrêté.
  * ``effacer``   — oublie une conversation.

La conversation (blocs d'outils compris) est gardée par le moteur sous la clé
``conversation`` fournie par le relais (« société:utilisateur »), 48 h au plus.

Éteint par défaut : le relais ne l'appelle que si ``ASSISTANT_MOTEUR=natif``
ET que le copilote est allumé pour le compte.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

#: Valeurs de ``arret`` dans le retour de :func:`executer` / :func:`reprendre`.
ARRET_FIN = "fin"          # le modèle a terminé son tour
ARRET_LIMITE = "limite"    # nombre maximal d'itérations ou de tokens atteint
ARRET_REFUS = "refus"      # le modèle a refusé (stop_reason « refusal »)
ARRET_ERREUR = "erreur"    # erreur du fournisseur après les reprises prévues


class MoteurIndisponible(RuntimeError):
    """Le moteur natif ne peut pas servir ce tour (clé absente, SDK absent,
    fournisseur en panne franche) : le relais retombe sur le moteur LangChain."""


@dataclass(frozen=True)
class OutilNatif:
    """Un outil remis au modèle.

    ``executer`` reçoit les arguments déjà décodés (dict) et rend le TEXTE
    remis au modèle (résultat, proposition en attente de confirmation, ou
    refus expliqué). Il ne lève pas pour un refus métier ; s'il lève quand
    même, le moteur rend au modèle un message d'erreur court et continue.
    """

    nom: str                       # ^[a-zA-Z0-9_-]{1,64}$
    description: str
    schema: dict                   # JSON Schema de type « object »
    executer: Callable[[dict], str]


def executer(*, question: str, systeme: list[dict], outils: list[OutilNatif],
             conversation: str, modele: str, effort: str = "low",
             max_tokens: int = 4096, max_iterations: int = 10) -> dict[str, Any]:
    """Un tour complet. Rend ``{"answer": str, "outils_appeles": [nom, ...],
    "tokens": {"input", "output", "cache_read", "cache_write"},
    "arret": ARRET_*, "modele": str}``.

    ``systeme`` : blocs ``{"type": "text", "text": ...}`` dans un ordre STABLE
    (le moteur pose lui-même les points de cache). ``question`` : le texte de
    l'utilisateur précédé de l'en-tête de tour (``prompt_copilote.entete_tour``).
    Lève :class:`MoteurIndisponible` si le tour ne peut pas être servi du tout.
    """
    raise MoteurIndisponible("Moteur natif non construit.")


def reprendre(*, conversation: str, message: str, systeme: list[dict],
              outils: list[OutilNatif], modele: str, effort: str = "low",
              max_tokens: int = 4096,
              max_iterations: int = 10) -> Optional[dict[str, Any]]:
    """Après une confirmation : ajoute ``message`` (résultat de l'ERP sous
    enveloppe, rédigé par le relais) à la conversation et laisse le modèle
    continuer. Même retour qu':func:`executer`, ou ``None`` s'il n'y a aucune
    conversation à reprendre (expirée, effacée, autre moteur)."""
    return None


def effacer(conversation: str) -> None:
    """Oublie la conversation (bouton « Effacer » de l'écran)."""
    return None
