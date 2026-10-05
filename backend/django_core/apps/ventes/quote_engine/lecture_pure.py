"""Lectures PURES partagées des moteurs de rendu (agricole, C&I) : un nombre
servi tel quel, jamais inventé. Un seul code — importé, jamais recopié."""
from __future__ import annotations


def nombre_ou_none(v):
    """Flottant lu tel quel, ou ``None`` (None, booléen, texte non numérique,
    NaN). Un booléen n'est pas un nombre."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def nombre_normalise(v):
    """Comme ``nombre_ou_none`` mais int si la valeur est un entier exact."""
    f = nombre_ou_none(v)
    if f is None:
        return None
    return int(f) if f == int(f) else f
