"""Analyse d'un plan déposé (DXF ou PDF vectoriel) — l'analyseur DU MODULE.

SOLMVP15 — l'analyseur vivait chez le module d'appels d'offres (``apps/ao/dxf.py``
+ sa porte fine ``analyser_plan_importe``) et ``services/import_plan.py``
l'appelait. AO sort du produit : l'analyseur est RAPATRIÉ ici, à la ligne près
(mêmes seuils, mêmes unités, mêmes refus français, même forme publiée). Aucune
capacité de l'atelier ne change : le même DXF et le même PDF rendent le même
contour qu'avant.

IL N'Y A TOUJOURS QU'UN SEUL ANALYSEUR pour le module — celui-ci. La règle
d'origine tient : un second analyseur donnerait, tôt ou tard, deux contours
différents pour un même plan.

AUCUNE ÉCRITURE, AUCUN MODÈLE : octets en entrée, dict en sortie. ``unite``
n'est JAMAIS devinée (le DXF la déclare, un PDF n'a que des points
typographiques) — c'est la calibration de l'atelier qui donne l'échelle.
"""

import io

#: Garde-fou de taille (~5 Mo) — un DXF de toiture réel tient très large en
__all__ = [
    'TAILLE_MAX_OCTETS', 'DxfInvalide', 'analyser_dxf',
    'analyser_plan_importe',
]

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


# ── CAL62 — la PORTE : un plan déposé, quel que soit son format ─────────────
#
# Elle ne recode rien : elle AIGUILLE selon le format RÉEL du fichier (on
# regarde le CONTENU, jamais l'extension — un « .dxf » renommé depuis un PDF
# est un cas réel d'atelier) et délègue.

#: Signature d'en-tête d'un PDF — on regarde le CONTENU.
_ENTETE_PDF = b'%PDF-'


def analyser_plan_importe(contenu, *, nom_fichier=''):
    """CAL62 — analyse un plan déposé (DXF ou PDF VECTORIEL) EN MÉMOIRE.

    Rend la MÊME forme que ``analyser_dxf`` ci-dessus, plus ``format`` :

        ``{'format': 'dxf'|'pdf', 'unite': …, 'calques': [{'nom', 'entites',
        'sommets'}]}``

    Une seule forme pour les deux formats : l'atelier choisit un « calque »
    d'enveloppe de la même façon, qu'il vienne d'un DXF ou d'un PDF.

    **``unite`` n'est JAMAIS devinée.** Le DXF la déclare (``$INSUNITS``) ou
    vaut ``'inconnu'`` ; un PDF n'a que des points typographiques, donc
    ``'inconnu'`` — c'est la calibration de l'atelier qui donne l'échelle,
    jamais une conversion supposée ici.

    Args:
        contenu: les octets du fichier déposé.
        nom_fichier: purement INDICATIF (messages) — le format est déduit du
            contenu.

    Raises:
        DxfInvalide: fichier vide, trop lourd, illisible, ou PDF sans
            aucun tracé vectoriel — message FRANÇAIS nommant la cause.
    """
    if not contenu:
        raise DxfInvalide(
            'Le fichier déposé est vide : aucun plan à analyser.')
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise DxfInvalide(
            'Ce fichier dépasse 5 Mo : simplifiez-le (purge des calques '
            'inutiles) puis réessayez.')

    if contenu[:len(_ENTETE_PDF)] == _ENTETE_PDF:
        return _analyser_pdf_vectoriel(contenu, nom_fichier=nom_fichier)

    resultat = dict(analyser_dxf(contenu))
    resultat['format'] = 'dxf'
    return resultat


def _analyser_pdf_vectoriel(contenu, *, nom_fichier=''):
    """Tracés vectoriels d'un PDF → la forme « calques » de l'analyseur DXF.

    PyMuPDF est DÉJÀ en production et DÉJÀ utilisé par le dépôt
    (rasterisation des PDF déposés, métadonnées de la fabrique) :
    aucune dépendance n'est ajoutée, et ce n'est pas une seconde plomberie
    PDF — c'est la même.

    Un plan SCANNÉ ne contient aucun tracé : il est REFUSÉ en nommant la
    cause. Le rasteriser pour en deviner un contour produirait une géométrie
    inventée ; l'atelier a déjà la voie honnête pour ce cas (calibration
    manuelle sur image, ``ingestion_service``).
    """
    try:
        import fitz  # PyMuPDF — déjà en production, jamais une seconde plomberie
    except ImportError as erreur:  # pragma: no cover — dépendance présente
        raise DxfInvalide(
            "La bibliothèque de lecture PDF (PyMuPDF) n'est pas installée "
            'sur ce serveur : ce plan ne peut pas être analysé.') from erreur

    try:
        document = fitz.open(stream=contenu, filetype='pdf')
    except Exception as erreur:  # noqa: BLE001 — fichier hostile : jamais un 500
        raise DxfInvalide(
            "Ce fichier n'a pas pu être lu comme un PDF (export corrompu ou "
            'protégé par mot de passe).') from erreur

    calques = []
    try:
        for numero in range(document.page_count):
            page = document.load_page(numero)
            try:
                traces = page.get_drawings()
            except Exception:  # noqa: BLE001 — page corrompue : pas un 500
                traces = []
            sommets, entites = _sommets_des_traces(traces)
            if entites:
                calques.append({'nom': f'Page {numero + 1}',
                                'entites': entites,
                                'sommets': sommets})
    finally:
        document.close()

    if not calques:
        raise DxfInvalide(
            'Ce PDF ne contient aucun tracé vectoriel : c\'est un plan '
            'SCANNÉ (une image). Réimportez-le en DXF, ou en PDF vectoriel '
            'exporté depuis le logiciel de dessin.')

    return {'format': 'pdf', 'unite': 'inconnu', 'calques': calques}


def _sommets_des_traces(traces):
    """``(sommets de la PLUS GRANDE polyligne, nombre de tracés)``.

    MÊME règle que l'analyseur DXF ci-dessus : on propose les sommets de la plus grande
    entité, jamais un mélange de plusieurs tracés — un contour composite
    n'existerait nulle part dans le fichier.
    """
    meilleure = []
    entites = 0
    for trace in traces or []:
        for item in trace.get('items') or []:
            points = _points_de_l_item(item)
            if not points:
                continue
            entites += 1
            if len(points) > len(meilleure):
                meilleure = points
    return meilleure, entites


def _points_de_l_item(item):
    """Points ``[x, y]`` d'un item de dessin PyMuPDF (ligne, rectangle).

    Les courbes (``'c'``) sont IGNORÉES : approcher une Bézier par ses points
    de contrôle produirait un contour qui n'est pas celui du plan.
    """
    if not item:
        return []
    operateur = item[0]
    if operateur == 'l' and len(item) >= 3:
        return [[float(item[1].x), float(item[1].y)],
                [float(item[2].x), float(item[2].y)]]
    if operateur == 're' and len(item) >= 2:
        rect = item[1]
        return [[float(rect.x0), float(rect.y0)],
                [float(rect.x1), float(rect.y0)],
                [float(rect.x1), float(rect.y1)],
                [float(rect.x0), float(rect.y1)]]
