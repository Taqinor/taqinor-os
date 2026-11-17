"""Nombres : l'unique arrondi du moteur (regles.md §0)."""
import math

DEMI = 0.5  # « au plus proche, la demie vers le bas » (A2.3)


def arrondir(x):
    """`ceil(x - 0,5)` : au plus proche, la demie vers le bas (seul arrondi du moteur)."""
    return math.ceil(x - DEMI)
