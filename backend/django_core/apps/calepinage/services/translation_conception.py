"""ACAL117 (D-ACAL-15) — translater une conception sur un autre repère.

Un MODÈLE emporte ses réglages et son implantation RELATIVE : appliqué à un
lead repéré ailleurs (Marrakech au lieu de Casablanca), TOUTE la géométrie du
document ``roof_layout`` v2 est décalée du MÊME vecteur et l'épingle devient
exactement celle du lead cible.

UNE SEULE translation dans le module : celle du « Recentrer » (D-ACAL-13,
``services/repere.py::_translater_document`` — projection métrique locale,
formes et surfaces conservées, chemins de coordonnées listés par
``CHEMINS_TRANSLATES``). Cette fonction l'APPELLE, elle n'en écrit pas une
seconde. Fonction PURE : rien n'est écrit en base.
"""
from __future__ import annotations

import copy

__all__ = ['translater_conception']


def translater_conception(roof_layout, vers_pin):
    """Une COPIE de ``roof_layout`` dont toute position est décalée du
    vecteur (épingle du document → ``vers_pin``), ``pin`` = ``vers_pin``.

    Args:
        roof_layout: le document v2 (``None`` accepté : rend ``None``).
        vers_pin: ``{lat, lng}`` du repère cible.

    Sans épingle source, aucun vecteur n'est connu : seule l'épingle est posée
    (aucune position n'est devinée).
    """
    from .repere import _point, _translater_document

    if not isinstance(roof_layout, dict):
        return None
    cible = _point(vers_pin)
    if cible is None:
        return copy.deepcopy(roof_layout)
    source = _point(roof_layout.get('pin'))
    if source is None or (abs(source['lat'] - cible['lat']) < 1e-9
                          and abs(source['lng'] - cible['lng']) < 1e-9):
        # Aucun vecteur connu, ou vecteur nul : rien ne bouge.
        copie = copy.deepcopy(roof_layout)
    else:
        copie = _translater_document(roof_layout, source, cible)
    copie['pin'] = {'lat': cible['lat'], 'lng': cible['lng']}
    return copie
