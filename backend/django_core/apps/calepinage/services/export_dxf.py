"""CAL178 — l'export DXF du calepinage (ÉCRITURE).

Le constat
==========
``ezdxf`` est déjà une dépendance du dépôt, mais elle n'y sert qu'en LECTURE
(``apps/ao/dxf.py`` : ``ezdxf.read``). Aucun code de PRODUCTION n'écrivait de
DXF — ``ezdxf.new`` n'apparaissait que dans une fixture de test. Un bureau
d'études qui demandait le plan repartait donc avec un PDF qu'il ne pouvait pas
réutiliser. Parité : HelioScope exporte son schéma en DXF.

Aucune dépendance nouvelle n'est ajoutée : c'est la MÊME bibliothèque, dans
l'autre sens.

Ce que le fichier contient
==========================
Quatre calques NOMMÉS, et rien d'autre :

* ``TOITURE``   — le contour relevé et les pans ;
* ``OBSTACLES`` — les obstacles relevés, chacun à sa position et à son emprise ;
* ``MODULES``   — un objet par module POSÉ (rectangle quand l'emprise du module
  est SOURCÉE, sinon un point : on ne dessine jamais un rectangle de taille
  plausible, il se lirait comme une emprise mesurée) ;
* ``COTES``     — les cotes d'encombrement, MESURÉES sur la géométrie projetée.

Unités : le MÈTRE (``$INSUNITS``), parce que c'est l'unité de la géométrie
stockée. Un DXF sans unité déclarée s'ouvre en pouces chez la moitié des
lecteurs, et le plan y fait alors 39 fois sa taille.

La géométrie est celle de la planche (``services.planche.geometrie_de_planche``)
— la MÊME projection, donc le DXF et le PDF ne peuvent pas diverger.
"""
from __future__ import annotations

__all__ = [
    'CALQUE_TOITURE', 'CALQUE_OBSTACLES', 'CALQUE_MODULES', 'CALQUE_COTES',
    'CALQUES', 'document_dxf', 'octets_dxf', 'exporter_dxf',
]

CALQUE_TOITURE = 'TOITURE'
CALQUE_OBSTACLES = 'OBSTACLES'
CALQUE_MODULES = 'MODULES'
CALQUE_COTES = 'COTES'

#: Les quatre calques, avec leur couleur d'index AutoCAD (7 = noir/blanc selon
#: le fond, 1 = rouge, 3 = vert, 5 = bleu). Des couleurs d'INDEX et non des
#: RVB : c'est ce que tout lecteur DXF, même ancien, sait afficher.
CALQUES = (
    (CALQUE_TOITURE, 7),
    (CALQUE_OBSTACLES, 1),
    (CALQUE_MODULES, 3),
    (CALQUE_COTES, 5),
)

#: Hauteur du texte des cotes, en mètres (l'unité du dessin).
HAUTEUR_TEXTE_M = 0.25


def _rectangle(centre, longueur, largeur):
    """Les 4 coins d'un rectangle centré, dans le plan du dessin."""
    demi_l, demi_c = longueur / 2.0, largeur / 2.0
    x, y = centre
    return [(x - demi_l, y - demi_c), (x + demi_l, y - demi_c),
            (x + demi_l, y + demi_c), (x - demi_l, y + demi_c)]


def document_dxf(geometrie):
    """``geometrie_de_planche(...)`` -> un document ``ezdxf`` prêt à écrire.

    L'import d'``ezdxf`` est FONCTION-LOCAL : la bibliothèque n'a aucune raison
    d'être chargée au démarrage de Django pour une sortie qu'on demande
    rarement.
    """
    import ezdxf
    from ezdxf import units

    document = ezdxf.new(setup=True)
    # L'unité du DESSIN est celle de la géométrie stockée : le mètre. Sans
    # cette déclaration, la moitié des lecteurs ouvre le fichier en pouces.
    document.units = units.M
    document.header['$INSUNITS'] = units.M
    for nom, couleur in CALQUES:
        document.layers.add(name=nom, color=couleur)
    espace = document.modelspace()

    contour = geometrie.get('contour') or ()
    if len(contour) >= 3:
        espace.add_lwpolyline(contour, close=True,
                              dxfattribs={'layer': CALQUE_TOITURE})
    for pan in geometrie.get('pans') or ():
        if len(pan['points']) >= 3:
            espace.add_lwpolyline(pan['points'], close=True,
                                  dxfattribs={'layer': CALQUE_TOITURE})
    for zone in geometrie.get('zones_interdites') or ():
        if len(zone['points']) >= 3:
            espace.add_lwpolyline(zone['points'], close=True,
                                  dxfattribs={'layer': CALQUE_OBSTACLES})

    for obstacle in geometrie.get('obstacles') or ():
        coins = [(obstacle['x'], obstacle['y']),
                 (obstacle['x'] + obstacle['largeur'], obstacle['y']),
                 (obstacle['x'] + obstacle['largeur'],
                  obstacle['y'] + obstacle['hauteur']),
                 (obstacle['x'], obstacle['y'] + obstacle['hauteur'])]
        espace.add_lwpolyline(coins, close=True,
                              dxfattribs={'layer': CALQUE_OBSTACLES})

    # UN objet par module POSÉ — c'est le compte que le calque doit porter.
    module_m = geometrie.get('module_m')
    for pan in geometrie.get('pans') or ():
        for centre in pan['modules']:
            if module_m is None:
                espace.add_point(
                    (centre[0], centre[1]),
                    dxfattribs={'layer': CALQUE_MODULES})
            else:
                espace.add_lwpolyline(
                    _rectangle(centre, module_m[0], module_m[1]), close=True,
                    dxfattribs={'layer': CALQUE_MODULES})

    _coter(espace, geometrie.get('etendue'))
    return document


def _coter(espace, etendue):
    """Les cotes d'encombrement : une ligne et son texte, en MÈTRES.

    Des lignes cotées plutôt que des entités ``DIMENSION`` : une DIMENSION doit
    être RENDUE par le lecteur avec un style, et un style absent la fait
    disparaître chez certains. Une ligne et un texte s'affichent partout.
    """
    from apps.calepinage.services.planche import texte_de_longueur

    if not etendue:
        return
    x0, y0, x1, y1 = etendue
    decalage = max((x1 - x0), (y1 - y0)) * 0.04 + 0.5
    attributs = {'layer': CALQUE_COTES}

    espace.add_line((x0, y0 - decalage), (x1, y0 - decalage),
                    dxfattribs=attributs)
    espace.add_text(
        texte_de_longueur(x1 - x0), height=HAUTEUR_TEXTE_M,
        dxfattribs=attributs).set_placement(
            ((x0 + x1) / 2.0, y0 - decalage * 1.6))

    espace.add_line((x0 - decalage, y0), (x0 - decalage, y1),
                    dxfattribs=attributs)
    espace.add_text(
        texte_de_longueur(y1 - y0), height=HAUTEUR_TEXTE_M,
        dxfattribs=attributs).set_placement(
            (x0 - decalage * 1.6, (y0 + y1) / 2.0))


def octets_dxf(geometrie):
    """Le DXF en OCTETS (utf-8) — aucun fichier n'est écrit sur le disque."""
    import io

    tampon = io.StringIO()
    document_dxf(geometrie).write(tampon)
    return tampon.getvalue().encode('utf-8')


def exporter_dxf(calepinage):
    """Le DXF d'un ``Calepinage``. Lève ``PlancheRefusee`` sans conception.

    La géométrie est celle de la planche : le DXF et le PDF ne peuvent pas
    diverger, parce qu'il n'y a qu'une seule projection.
    """
    from .planche import geometrie_de_planche

    return octets_dxf(
        geometrie_de_planche(getattr(calepinage, 'roof_layout', None)))
