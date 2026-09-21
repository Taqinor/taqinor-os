"""Analyse d'un fichier DXF déposé — PVG1 (import DXF réel).

Complète l'écran ``ImportDxf.jsx`` (AOF81), livré AVANT l'endpoint : l'écran
proposait déjà de choisir un calque d'enveloppe et des calques d'obstacles,
mais aucune route ne parsait vraiment un DXF (``analyserDxf`` n'était passé
nulle part, l'écran restait dégradé). Ce module fait EXACTEMENT ce que
l'écran attend et rien de plus :

* les entités ``LWPOLYLINE``/``POLYLINE``/``LINE`` sont groupées par CALQUE
  (``layer``) — les autres types (texte, cotes, hachures…) ne proposent rien
  d'exploitable comme enveloppe ou obstacle, ils sont ignorés ;
* l'unité du fichier est lue depuis l'en-tête ``$INSUNITS`` et traduite dans
  le vocabulaire de l'écran (``m``/``cm``/``mm``/``pouce``/``pied``), ou
  ``'inconnu'`` si le fichier ne la déclare pas — jamais devinée ;
* AUCUNE écriture : ni ``PlanSource``, ni ``records.Attachment``. L'atelier ne
  fait que PROPOSER un mapping de calques ; c'est le choix de l'utilisateur
  (``ImportDxf.importer``) qui produit le contour, écrit ensuite par la voie
  existante (``ToituresPage`` → ``aoApi.toitures.update``).

Un fichier hostile ou corrompu ne doit JAMAIS produire un 500 : toute
exception d'``ezdxf`` (ou de simple décodage) est enveloppée dans
``DxfInvalide``, que la vue traduit en 400 motivé en français.
"""
from __future__ import annotations

import io

#: Garde-fou de taille (~5 Mo) — un DXF de toiture réel tient très large en
#: dessous ; au-delà, c'est soit un export non nettoyé, soit un fichier hostile.
TAILLE_MAX_OCTETS = 5 * 1024 * 1024

#: ``$INSUNITS`` (code de groupe 70, table DXF standard) → unité déjà connue
#: de l'écran (``ImportDxf.jsx`` ``UNITES``). Seules les valeurs que l'écran
#: sait déjà afficher sont mappées ; le reste retombe honnêtement sur
#: ``'inconnu'`` plutôt que d'être deviné.
_UNITES_INSUNITS = {
    1: 'pouce',
    2: 'pied',
    4: 'mm',
    5: 'cm',
    6: 'm',
}

#: Entités qui portent une géométrie EXPLOITABLE comme enveloppe ou obstacle.
#: Un calque de cotes, de texte ou de hachures n'en produit aucune — il
#: n'apparaît donc simplement pas dans le résultat.
_TYPES_RETENUS = {'LWPOLYLINE', 'POLYLINE', 'LINE'}

__all__ = ['DxfInvalide', 'TAILLE_MAX_OCTETS', 'analyser_dxf']


class DxfInvalide(ValueError):
    """Levée pour tout fichier illisible comme DXF — jamais un 500."""


def _unite_document(doc):
    try:
        code = int(doc.header.get('$INSUNITS', 0) or 0)
    except Exception:  # noqa: BLE001 — un en-tête bizarre ne doit rien casser
        return 'inconnu'
    return _UNITES_INSUNITS.get(code, 'inconnu')


def _sommets_entite(entite):
    """Sommets ``[x, y]`` d'une entité DXF — jamais le z (plan à plat)."""
    type_dxf = entite.dxftype()
    if type_dxf == 'LWPOLYLINE':
        return [[float(p[0]), float(p[1])] for p in entite.get_points('xy')]
    if type_dxf == 'POLYLINE':
        return [
            [float(v.dxf.location.x), float(v.dxf.location.y)]
            for v in entite.vertices
        ]
    if type_dxf == 'LINE':
        d = entite.dxf
        return [
            [float(d.start.x), float(d.start.y)],
            [float(d.end.x), float(d.end.y)],
        ]
    return []


def analyser_dxf(contenu: bytes) -> dict:
    """Parse un DXF EN MÉMOIRE → ``{'calques': [...], 'unite': ...}``.

    Chaque calque : ``{'nom', 'entites' (nombre), 'sommets'}`` — les sommets
    sont ceux de la PLUS GRANDE entité du calque (jamais un mélange de
    plusieurs polylignes, qui produirait un contour qui n'existe nulle part
    dans le fichier) ; c'est ce que ``ImportDxf.jsx`` affiche en aperçu et
    peut choisir comme enveloppe.

    Refuse (``DxfInvalide``) un fichier trop lourd ou illisible — jamais une
    exception ``ezdxf`` brute, jamais un 500.
    """
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise DxfInvalide(
            'Ce fichier dépasse 5 Mo : simplifiez-le (purge des calques '
            'inutiles) puis réessayez.')

    try:
        import ezdxf
    except ImportError as exc:  # pragma: no cover — toujours installé en prod
        raise DxfInvalide(
            "L'analyse DXF n'est pas disponible sur ce serveur (bibliothèque "
            'manquante).') from exc

    try:
        flux = io.StringIO(contenu.decode('utf-8', errors='replace'))
        doc = ezdxf.read(flux)
    except Exception as exc:  # noqa: BLE001 — fichier hostile : jamais un 500
        raise DxfInvalide(
            "Ce fichier n'a pas pu être lu comme un DXF (export corrompu ou "
            "incompatible). Vérifiez qu'il s'agit bien d'un export DXF, pas "
            'DWG.') from exc

    par_calque: dict[str, dict] = {}
    try:
        espace = doc.modelspace()
        for entite in espace:
            if entite.dxftype() not in _TYPES_RETENUS:
                continue
            nom_calque = entite.dxf.layer or '0'
            bucket = par_calque.setdefault(
                nom_calque, {'nom': nom_calque, 'entites': 0, 'sommets': []})
            bucket['entites'] += 1
            sommets = _sommets_entite(entite)
            if len(sommets) > len(bucket['sommets']):
                bucket['sommets'] = sommets
    except Exception as exc:  # noqa: BLE001 — un DXF structurellement valide
        # mais illisible en pratique (entité corrompue) reste un refus 400.
        raise DxfInvalide(
            "Ce fichier DXF n'a pas pu être parcouru jusqu'au bout — il est "
            'probablement corrompu.') from exc

    calques = sorted(par_calque.values(), key=lambda c: c['nom'])
    return {'calques': calques, 'unite': _unite_document(doc)}
