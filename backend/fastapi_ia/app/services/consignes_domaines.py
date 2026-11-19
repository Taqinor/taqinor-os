"""Copilote vague 2 (FND4) — consignes de l'ERP PAR DOMAINE.

Le bloc fixe des consignes est plein (999 mots sur 1 000) : une règle propre à
un domaine voyage AVEC le chargement de ce domaine. Quand ``outils_charger``
charge un domaine dont le texte n'est pas vide, le relais pose, dans le MÊME
message utilisateur et APRÈS les ``tool_result`` (jamais dedans : l'essai clé
réelle FND0 a prouvé qu'un texte mêlé aux ``tool_reference`` est un 400), un
bloc texte borné par :data:`DEBUT` / :data:`FIN`. Il vit dans la conversation
gardée (ajout seul, jamais réécrit : la pensée préservée reste valide).

Rempli par la lane TXT (vague 2B) ; budget tenu par
``tests/test_prompt_copilote.py`` : 120 mots par domaine, 900 au total, aucun
prénom, aucun pourcentage, aucune date, aucune clé d'outil hors de son domaine
ou du noyau.
"""
from __future__ import annotations

#: ``{domaine: texte}`` — domaine = une valeur de
#: ``chargeur_outils.DOMAINES``. Vide tant que la lane TXT ne l'a pas rempli.
CONSIGNES: dict[str, str] = {}

DEBUT = "[Consignes de l'ERP pour le domaine %s]"
FIN = "[Fin des consignes du domaine %s]"


def bloc_consignes(domaine: str) -> list[dict]:
    """``[]`` (domaine sans consigne) ou UN bloc texte borné."""
    texte = (CONSIGNES.get(domaine) or "").strip()
    if not texte:
        return []
    return [{"type": "text", "text": "\n".join((DEBUT % domaine, texte, FIN % domaine))}]
