"""CIQ625 — le RÉSULTAT d'une recette est CALCULÉ, jamais saisi.

Avant : ``resultat`` était écrit tel quel par le client
(``installations/serializers_commissioning.py``) et ``passe`` en dépendait :
``isolement_ok=false`` + ``resultat='conforme'`` ouvrait le gate « Mise en
service » et le pack de remise affichait le certificat comme présent.

La règle (une seule, ici) :

* un essai explicitement FAUX ⇒ ``non_conforme`` ;
* tous les essais VRAIS ⇒ ``conforme`` ;
* sinon (au moins un essai non renseigné, aucun faux) ⇒ ``en_cours``.

Seul choix HUMAIN : « conforme avec réserves » (``reserves``), admis SEULEMENT
quand tous les essais sont vrais (:func:`resultat_avec_choix`). Fonctions
PURES : stdlib seule, aucun ``apps.*``.
"""
from __future__ import annotations

EN_COURS = 'en_cours'
CONFORME = 'conforme'
RESERVES = 'reserves'
NON_CONFORME = 'non_conforme'

#: Refus FR d'un « conforme avec réserves » demandé alors qu'un essai n'est
#: pas vrai.
MESSAGE_RESERVES_REFUSEES = (
    "« Conforme avec réserves » n'est possible que si TOUS les essais sont "
    "conformes : un essai est non conforme ou non renseigné.")


class ReservesRefusees(ValueError):
    """« Conforme avec réserves » demandé alors qu'un essai n'est pas vrai."""


def resultat_recette(essais):
    """Le résultat DÉRIVÉ des essais (itérable de ``True``/``False``/
    ``None``) : un faux ⇒ ``non_conforme`` ; tous vrais ⇒ ``conforme`` ;
    sinon ``en_cours``. Une liste VIDE n'a rien prouvé : ``en_cours``."""
    essais = list(essais)
    if any(e is False for e in essais):
        return NON_CONFORME
    if essais and all(e is True for e in essais):
        return CONFORME
    return EN_COURS


def resultat_avec_choix(essais, choix=None):
    """Le résultat FINAL : :func:`resultat_recette`, sauf le seul choix
    humain admis — ``reserves`` quand tous les essais sont vrais.

    ``choix`` = ce que l'utilisateur demande (``None`` = rien). Tout autre
    choix que ``reserves`` est IGNORÉ (le résultat est calculé). ``reserves``
    alors qu'un essai n'est pas vrai ⇒ :class:`ReservesRefusees`."""
    calcule = resultat_recette(essais)
    if choix == RESERVES:
        if calcule != CONFORME:
            raise ReservesRefusees(MESSAGE_RESERVES_REFUSEES)
        return RESERVES
    return calcule
