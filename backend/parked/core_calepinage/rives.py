# -*- coding: utf-8 -*-
"""AOF36 — les 4 rives NOMMÉES, jamais un paramètre ``rive`` unique.

Constat historique, et c'est LE bug de cohérence documenté du moteur d'origine :
``count_band`` prenait ``end_rive=0.5`` par défaut et ``fill_band`` prenait
``end_rive=0.0``. Le compte ANNONCÉ et le compte DESSINÉ divergeaient donc dès
que l'appelant oubliait l'argument — sur un livrable remis à un maître
d'ouvrage. Nommer les quatre rives et n'exposer AUCUN défaut implicite tue la
classe entière de bugs :

* ``rive_laterale``  — retrait au bord LATÉRAL (perpendiculaire aux rangées) ;
* ``rive_extremite`` — retrait en BOUT de rangée (l'ancien ``end_rive``) ;
* ``rive_acrotere``  — retrait supplémentaire imposé par un acrotère ;
* ``rive_joint``     — retrait imposé par un joint de dilatation / un muret.
"""

from core.calepinage.types import Rives

__all__ = [
    "NOMS_DE_RIVE", "retrait_lateral", "retrait_extremite",
    "bornes_laterales", "bornes_extremite", "verifier_rives",
]

#: Les quatre noms, dans l'ordre de lecture d'une planche.
NOMS_DE_RIVE = (
    "rive_laterale", "rive_extremite", "rive_acrotere", "rive_joint",
)


def retrait_lateral(rives):
    """Retrait effectif en bord LATÉRAL : rive latérale + acrotère."""
    return rives.laterale_totale_m


def retrait_extremite(rives):
    """Retrait effectif en BOUT de rangée : rive d'extrémité + joint."""
    return rives.extremite_totale_m


def bornes_laterales(ymin, ymax, rives):
    """Bande transversale utile après application des rives latérales."""
    r = retrait_lateral(rives)
    return (ymin + r, ymax - r)


def bornes_extremite(xmin, xmax, rives):
    """Tronçon utile d'une rangée après application des rives d'extrémité."""
    r = retrait_extremite(rives)
    return (xmin + r, xmax - r)


def verifier_rives(rangees, ymin, ymax, rives, tolerance=1e-9):
    """Motifs NOMMÉS pour toute rangée qui déborde d'une rive (jamais un booléen)."""
    motifs = []
    y_bas, y_haut = bornes_laterales(ymin, ymax, rives)
    for r in rangees:
        if r.y0 < y_bas - tolerance:
            motifs.append("rive_laterale (bas) non tenue par la rangée y0=%.3f "
                          "(minimum %.3f)" % (r.y0, y_bas))
        if r.y1 > y_haut + tolerance:
            motifs.append("rive_laterale (haut) non tenue par la rangée y0=%.3f "
                          "(maximum %.3f)" % (r.y0, y_haut))
    return tuple(motifs)


def rives_par_defaut_ao():
    """Rives du dossier FRDISI : 0,35 latérale et 0,35 d'extrémité."""
    return Rives(laterale_m=0.35, extremite_m=0.35)
