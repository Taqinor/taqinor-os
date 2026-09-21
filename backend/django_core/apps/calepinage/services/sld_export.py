# -*- coding: utf-8 -*-
"""CALX235 — l'export DXF du SCHÉMA UNIFILAIRE (pas de la planche de toiture).

LE CONSTAT
----------
Le seul export DXF du dépôt est celui de la TOITURE (``services/export_dxf
.py``, calques ``TOITURE``/``OBSTACLES``/``MODULES``/``COTES``). Le schéma
unifilaire, lui, n'existait qu'en SVG inline : aucun bureau d'études ne
pouvait le reprendre dans son logiciel. Parité : HelioScope exporte son SLD
en DXF, PV*SOL exporte son schéma de chaînes en DXF.

Aucune dépendance nouvelle : ``ezdxf`` est déjà au dépôt
(``requirements.txt``), importée EN FONCTION-LOCAL comme dans
``export_dxf.py`` — la bibliothèque n'a aucune raison d'être chargée au
démarrage de Django pour une sortie qu'on demande rarement.

QUATRE CALQUES, ET RIEN D'AUTRE
--------------------------------
* ``SLD_BLOCS``    — un rectangle par organe DESSINÉ ;
* ``SLD_LIAISONS`` — une polyligne par liaison dessinée (chaîne série, puis
  les branches) ;
* ``SLD_TEXTES``   — le repère et la désignation de chaque organe ;
* ``SLD_TABLEAU``  — la nomenclature, telle que la planche la publie.

JAMAIS UNE SECONDE GÉOMÉTRIE
-----------------------------
Les blocs, leurs positions (édition CALX234 comprise) et les liaisons
viennent de ``services/sld.py::rendu_du_schema`` — le MÊME dessin que le
SVG. Ce module ne fait que le transposer : pixels de planche → millimètres,
et axe ``y`` retourné (un DXF compte vers le HAUT, un SVG vers le bas).

FICHE INCOMPLÈTE ⇒ AUCUN FICHIER
---------------------------------
Même discipline que le SVG : une conception dont une fiche est muette, ou
qui porte un bloquant, ne produit AUCUN fichier — et le refus NOMME le champ
en cause (règle fondateur « erreur → champ fautif »).

REPRODUCTIBLE, OCTET POUR OCTET
--------------------------------
Deux exports de la même conception doivent donner le MÊME fichier : sans
cela, un dossier déposé ne peut plus prouver que la pièce n'a pas bougé. La
bibliothèque pose pourtant, à chaque écriture, deux estampilles volatiles
(un GUID de version et l'horodatage de l'écrivain) ; elles sont FIGÉES ici.
Aucune donnée de dessin n'est touchée.
"""
from __future__ import annotations

import re

__all__ = [
    'CALQUE_BLOCS', 'CALQUE_LIAISONS', 'CALQUE_TEXTES', 'CALQUE_TABLEAU',
    'CALQUES', 'MM_PAR_PX', 'exporter_sld_dxf',
]

CALQUE_BLOCS = 'SLD_BLOCS'
CALQUE_LIAISONS = 'SLD_LIAISONS'
CALQUE_TEXTES = 'SLD_TEXTES'
CALQUE_TABLEAU = 'SLD_TABLEAU'

#: Les quatre calques, avec leur couleur d'INDEX AutoCAD (7 = noir/blanc
#: selon le fond, 5 = bleu, 3 = vert, 1 = rouge) — des index et non des RVB,
#: parce que c'est ce que tout lecteur DXF, même ancien, sait afficher
#: (même choix que ``services/export_dxf.py``).
CALQUES = (
    (CALQUE_BLOCS, 7),
    (CALQUE_LIAISONS, 5),
    (CALQUE_TEXTES, 3),
    (CALQUE_TABLEAU, 1),
)

#: Le moteur dessine en pixels CSS à 96 ppp (``core/electrique/schema.py``,
#: « A4 paysage 297 × 210 mm ») ; le DXF est déclaré en MILLIMÈTRES. Un DXF
#: sans unité s'ouvre en pouces chez la moitié des lecteurs, et la planche y
#: fait 39 fois sa taille.
MM_PAR_PX = 25.4 / 96.0

#: Hauteurs de texte, en millimètres — CONVERTIES des tailles de police que
#: la planche SVG emploie (12 px pour un titre de bloc, 9 px pour son détail,
#: 8 px pour une ligne de nomenclature), jamais choisies ici.
HAUTEUR_TITRE_MM = 12.0 * MM_PAR_PX
HAUTEUR_DETAIL_MM = 9.0 * MM_PAR_PX
HAUTEUR_TABLEAU_MM = 8.0 * MM_PAR_PX

#: Pas de ligne et retrait de colonne du tableau — convention de dessin, en
#: millimètres : un tableau ne porte aucune géométrie électrique, il n'a
#: donc rien à partager avec la planche que sa colonne d'accueil.
_PAS_LIGNE_MM = HAUTEUR_TABLEAU_MM * 2.0
_COLONNES_MM = (0.0, 18.0, 74.0, 103.0)

#: Les deux estampilles que la bibliothèque régénère À CHAQUE écriture.
#: Figées pour que deux exports de la même conception soient identiques.
_GUID_FIGE = '{00000000-0000-0000-0000-000000000000}'
_ECRIVAIN_FIGE = 'taqinor-sld'
_HORODATAGE_ECRIVAIN = re.compile(r'^\d+\.\d+\.\d+ @ \d{4}-\d{2}-\d{2}T')


def _mm(valeur):
    return float(valeur) * MM_PAR_PX


def _point(x, y, hauteur_px):
    """Pixels de planche (``y`` vers le bas) → millimètres (``y`` vers le
    haut)."""
    return (_mm(x), _mm(hauteur_px - y))


def _dessin_et_tableau(calepinage):
    """Le dessin d'aujourd'hui et sa nomenclature — ou un REFUS qui nomme.

    Raises:
        SldRefuse: la conception ne permet pas de dessiner (fiche muette,
            bloquant) — aucun fichier n'est produit, et le message est celui
            du service électrique, tel quel.
    """
    from core.electrique.schema import lignes_tableau

    from .electrique import (
        bloquants_nommes, conception_du_calepinage, parametres_societe,
    )
    from .norme import norme_applicable
    from .sld import (
        SldRefuse, cartouche_du_calepinage, edition_sld, gabarit_de_schema,
        rendu_du_schema,
    )

    conception, _materiel, _donnees, _document = conception_du_calepinage(
        calepinage)
    empechements = (list(getattr(conception, 'manquantes', ()) or ())
                    + list(bloquants_nommes(conception) or ()))
    if empechements:
        premier = empechements[0]
        champ = premier.split(' : ', 1)[0] if ' : ' in premier else 'schema'
        raise SldRefuse(
            "Le schéma unifilaire n'est pas exportable : %s Aucun fichier "
            "n'est produit — un DXF d'aspect officiel bâti sur une "
            "caractéristique devinée est un défaut invisible." % premier,
            champ=champ)

    gabarit = gabarit_de_schema(norme_applicable(
        parametres_societe(calepinage)))
    resultat = getattr(conception, 'resultat', None)
    dessin = rendu_du_schema(getattr(conception, 'entree', None), resultat,
                             edition=edition_sld(calepinage),
                             gabarit=gabarit,
                             cartouche=cartouche_du_calepinage(calepinage))
    return dessin, lignes_tableau(resultat, standard=gabarit['standard'])


def _document_dxf(dessin, lignes):
    """``rendu_du_schema(...)`` + sa nomenclature -> un document ``ezdxf``."""
    from core.electrique.schema import _BLOC_H, _BLOC_L, _MARGE, _TABLEAU_L

    import ezdxf
    from ezdxf import units

    hauteur = dessin['hauteur']
    document = ezdxf.new(setup=True)
    document.units = units.MM
    document.header['$INSUNITS'] = units.MM
    for nom, couleur in CALQUES:
        document.layers.add(name=nom, color=couleur)
    espace = document.modelspace()

    for bloc in dessin['blocs']:
        x, y = bloc['x'], bloc['y']
        coins = [_point(x, y + _BLOC_H, hauteur),
                 _point(x + _BLOC_L, y + _BLOC_H, hauteur),
                 _point(x + _BLOC_L, y, hauteur),
                 _point(x, y, hauteur)]
        espace.add_lwpolyline(coins, close=True,
                              dxfattribs={'layer': CALQUE_BLOCS})
        _texte(espace, bloc['titre'], _point(x + 6.0, y + 22.0, hauteur),
               HAUTEUR_TITRE_MM, CALQUE_TEXTES)
        if bloc['sous_titre']:
            _texte(espace, bloc['sous_titre'],
                   _point(x + 6.0, y + 38.0, hauteur), HAUTEUR_DETAIL_MM,
                   CALQUE_TEXTES)
        if bloc['repere']:
            _texte(espace, bloc['repere'], _point(x + 6.0, y - 4.0, hauteur),
                   HAUTEUR_DETAIL_MM, CALQUE_TEXTES)

    for liaison in dessin['liaisons']:
        depart, arrivee = liaison['points']
        espace.add_lwpolyline(
            [_point(depart[0], depart[1], hauteur),
             _point(arrivee[0], arrivee[1], hauteur)],
            dxfattribs={'layer': CALQUE_LIAISONS})

    origine_x = _mm(dessin['largeur'] - _MARGE - _TABLEAU_L)
    origine_y = _mm(hauteur - _MARGE)
    for rang, ligne in enumerate(lignes):
        y = origine_y - _PAS_LIGNE_MM * (rang + 1)
        for index, valeur in enumerate(ligne):
            if not valeur:
                continue
            _texte(espace, valeur, (origine_x + _COLONNES_MM[index], y),
                   HAUTEUR_TABLEAU_MM, CALQUE_TABLEAU)
    return document


def _texte(espace, contenu, position, hauteur, calque):
    espace.add_text(str(contenu), height=hauteur,
                    dxfattribs={'layer': calque}).set_placement(position)


def _fige_les_estampilles(texte):
    """Remplace les deux estampilles volatiles de l'écriture.

    ``$VERSIONGUID`` (valeur en code de groupe 2, deux lignes plus bas) et la
    signature « <version> @ <horodatage ISO> » que la bibliothèque dépose
    dans ses métadonnées. Rien d'autre n'est touché : ni une coordonnée, ni
    un texte du dessin.
    """
    lignes = texte.split('\n')
    for index, ligne in enumerate(lignes):
        depouillee = ligne.strip()
        if depouillee == '$VERSIONGUID' and index + 2 < len(lignes):
            lignes[index + 2] = _GUID_FIGE
        elif _HORODATAGE_ECRIVAIN.match(depouillee):
            lignes[index] = _ECRIVAIN_FIGE
    return '\n'.join(lignes)


def _octets_dxf(document):
    """Le DXF en OCTETS (utf-8) — aucun fichier n'est écrit sur le disque."""
    import io

    from ezdxf.document import CREATED_BY_EZDXF

    document.header['$FINGERPRINTGUID'] = _GUID_FIGE
    document.ezdxf_metadata()[CREATED_BY_EZDXF] = _ECRIVAIN_FIGE
    tampon = io.StringIO()
    document.write(tampon)
    return _fige_les_estampilles(tampon.getvalue()).encode('utf-8')


def exporter_sld_dxf(calepinage, *, dessin=None, lignes=None):
    """Le DXF du schéma unifilaire de CE calepinage, en octets.

    ``dessin``/``lignes`` court-circuitent le calcul de la conception : ils
    sont réservés aux APPELS INTERNES et aux tests, exactement comme
    ``materiel=`` sur ``conception_du_calepinage`` — aucune vue ne les
    expose, pour qu'un corps de requête ne puisse jamais fournir une
    géométrie de schéma inventée.

    Raises:
        SldRefuse: conception incomplète ou bloquée — AUCUN fichier.
    """
    if dessin is None or lignes is None:
        dessin, lignes = _dessin_et_tableau(calepinage)
    return _octets_dxf(_document_dxf(dessin, lignes))
