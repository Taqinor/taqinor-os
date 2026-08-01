# -*- coding: utf-8 -*-
"""AOF51 — exceptions MÉTIER du moteur de calepinage.

Une exception du moteur porte toujours le REPÈRE fautif (« la table T14 de la
rangée y0=5,65 », « l'obstacle CAGE ») : un message générique oblige à
rejouer le calcul à la main pour savoir ce qui cloche, ce qui est exactement
ce que le dossier FRDISI a coûté en temps.
"""

__all__ = ["ErreurCalepinage", "CalepinageIncoherent"]


class ErreurCalepinage(Exception):
    """Base de toutes les erreurs métier du moteur."""


class CalepinageIncoherent(ErreurCalepinage):
    """Un plan a échoué à un garde-fou NOMMÉ — il ne peut pas être publié."""

    def __init__(self, controle, repere, message):
        self.controle = controle
        self.repere = repere
        self.message = message
        super().__init__("[%s] %s : %s" % (controle, repere or "(sans repère)",
                                           message))
