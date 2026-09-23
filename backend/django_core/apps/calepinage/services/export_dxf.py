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

CALX310 — le calque ``CHAINES``, SOUS UN PARAMÈTRE EXPLICITE
============================================================
``document_dxf(geometrie, chaines=…)`` ajoute un cinquième calque, ``CHAINES`` :
un objet par module AFFECTÉ, teint de la couleur de sa chaîne (celle du plan de
câblage et de l'écran), et un texte ``C<n>`` (``C<n>*`` en affectation
manuelle). Sans le paramètre, le fichier est EXACTEMENT celui de CAL178 — les
quatre calques et rien d'autre. Un module non affecté n'entre PAS sur ce
calque : il reste sur ``MODULES``, jamais teinté d'une chaîne voisine.

CALX314 — le calque ``PROVENANCE`` (non imprimable)
===================================================
``document_dxf(geometrie, provenance=…)`` pose UN bloc de texte (MTEXT) sur un
calque ``PROVENANCE`` marqué NON IMPRIMABLE : le fichier dit d'où il vient
(base de rayonnement, version du moteur, empreintes) sans charger le tirage.
Les lignes sont celles de ``provenance_document.lignes_de_provenance`` — la
fonction PARTAGÉE avec le classeur XLSX et l'export JSON. ``exporter_dxf`` la
passe toujours ; sans le paramètre, ``document_dxf`` reste celui de CAL178.
"""
from __future__ import annotations

__all__ = [
    'CALQUE_TOITURE', 'CALQUE_OBSTACLES', 'CALQUE_MODULES', 'CALQUE_COTES',
    'CALQUES', 'document_dxf', 'octets_dxf', 'exporter_dxf',
    # CALX310
    'CALQUE_CHAINES',
    # CALX314
    'CALQUE_PROVENANCE',
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

#: CALX310 — le calque du câblage, déclaré SEULEMENT sur demande explicite
#: (``chaines=``), avec sa couleur d'index (6 = magenta) ; chaque objet y
#: porte en plus la couleur VRAIE de sa chaîne.
CALQUE_CHAINES = 'CHAINES'
COULEUR_CALQUE_CHAINES = 6

#: Hauteur du texte des cotes, en mètres (l'unité du dessin).
HAUTEUR_TEXTE_M = 0.25

#: Hauteur du repère de chaîne ``C<n>`` posé sur chaque module (m).
HAUTEUR_REPERE_CHAINE_M = 0.2

#: CALX314 — le calque de provenance, NON IMPRIMABLE (8 = gris d'index).
CALQUE_PROVENANCE = 'PROVENANCE'
COULEUR_CALQUE_PROVENANCE = 8


def _rectangle(centre, longueur, largeur):
    """Les 4 coins d'un rectangle centré, dans le plan du dessin."""
    demi_l, demi_c = longueur / 2.0, largeur / 2.0
    x, y = centre
    return [(x - demi_l, y - demi_c), (x + demi_l, y - demi_c),
            (x + demi_l, y + demi_c), (x - demi_l, y + demi_c)]


def document_dxf(geometrie, *, chaines=None, provenance=None):
    """``geometrie_de_planche(...)`` -> un document ``ezdxf`` prêt à écrire.

    L'import d'``ezdxf`` est FONCTION-LOCAL : la bibliothèque n'a aucune raison
    d'être chargée au démarrage de Django pour une sortie qu'on demande
    rarement.

    CALX310 — ``chaines`` (les ``modules`` de
    ``services.documents.plan_cablage.plan_de_cablage`` : ``{module, centre,
    chaine, couleur, manuel}``) ajoute le calque ``CHAINES``. ``None`` (le
    défaut) : aucun calque de plus.

    CALX314 — ``provenance`` (les lignes ``(libellé, valeur)`` de
    ``provenance_document.lignes_de_provenance``) ajoute le calque
    ``PROVENANCE``, non imprimable. ``None`` (le défaut) : aucun calque de plus.
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
    if chaines is not None:
        _calque_chaines(document, espace, chaines, module_m)
    if provenance is not None:
        _calque_provenance(document, espace, provenance,
                           geometrie.get('etendue'))
    return document


def _calque_provenance(document, espace, lignes, etendue):
    """CALX314 — UN bloc de texte, sous le dessin, sur un calque NON imprimé.

    Chaque ligne est « libellé : valeur » (``provenance_document
    .texte_de_ligne``) ; le bloc est posé sous les cotes d'encombrement pour
    ne recouvrir aucun objet du plan.
    """
    from .provenance_document import texte_de_ligne

    calque = document.layers.add(name=CALQUE_PROVENANCE,
                                 color=COULEUR_CALQUE_PROVENANCE)
    calque.dxf.plot = 0  # non imprimable : il documente, il ne se tire pas
    if etendue:
        x0, y0, x1, y1 = etendue
        decalage = max((x1 - x0), (y1 - y0)) * 0.04 + 0.5
        position = (x0, y0 - decalage * 3.0)
    else:
        position = (0.0, 0.0)
    texte = '\n'.join(texte_de_ligne(ligne) for ligne in lignes)
    espace.add_mtext(texte, dxfattribs={
        'layer': CALQUE_PROVENANCE, 'char_height': HAUTEUR_TEXTE_M,
    }).set_location(position)


def _calque_chaines(document, espace, chaines, module_m):
    """CALX310 — un objet TEINT et un repère ``C<n>`` par module AFFECTÉ.

    Rien n'est recalculé : la chaîne et sa couleur viennent du plan de câblage,
    qui les a LUES dans l'affectation publiée.
    """
    from ezdxf import colors

    from .documents.plan_cablage import rgb_de

    document.layers.add(name=CALQUE_CHAINES, color=COULEUR_CALQUE_CHAINES)
    for module in chaines:
        if not isinstance(module, dict) or module.get('chaine') is None:
            continue
        attributs = {'layer': CALQUE_CHAINES}
        if module.get('couleur'):
            attributs['true_color'] = colors.rgb2int(
                rgb_de(module['couleur']))
        centre = module['centre']
        if module_m is None:
            espace.add_point((centre[0], centre[1]), dxfattribs=attributs)
        else:
            espace.add_lwpolyline(
                _rectangle(centre, module_m[0], module_m[1]), close=True,
                dxfattribs=attributs)
        repere = 'C%s%s' % (module['chaine'], '*' if module.get('manuel')
                            else '')
        espace.add_text(repere, height=HAUTEUR_REPERE_CHAINE_M,
                        dxfattribs=dict(attributs)).set_placement(
                            (centre[0], centre[1]))


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


def octets_dxf(geometrie, *, chaines=None, provenance=None):
    """Le DXF en OCTETS (utf-8) — aucun fichier n'est écrit sur le disque.

    ``chaines`` : voir ``document_dxf`` (CALX310, calque ``CHAINES``) ;
    ``provenance`` : voir ``document_dxf`` (CALX314, calque ``PROVENANCE``).
    """
    import io

    tampon = io.StringIO()
    document_dxf(geometrie, chaines=chaines,
                 provenance=provenance).write(tampon)
    return tampon.getvalue().encode('utf-8')


def exporter_dxf(calepinage):
    """Le DXF d'un ``Calepinage``. Lève ``PlancheRefusee`` sans conception.

    La géométrie est celle de la planche : le DXF et le PDF ne peuvent pas
    diverger, parce qu'il n'y a qu'une seule projection. CALX314 — le calque
    ``PROVENANCE`` (non imprimable) porte les lignes de la fonction PARTAGÉE
    ``provenance_document.lignes_de_provenance``.
    """
    from .planche import geometrie_de_planche
    from .provenance_document import lignes_de_provenance

    return octets_dxf(
        geometrie_de_planche(getattr(calepinage, 'roof_layout', None)),
        provenance=lignes_de_provenance(calepinage))
