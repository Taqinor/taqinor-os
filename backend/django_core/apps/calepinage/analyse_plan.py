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
import math
import re

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

__all__ = ['DxfInvalide', 'TAILLE_MAX_OCTETS', 'TOL_FUSION_M',
           'analyser_dxf']

#: ACAL212 — tolérance de rapprochement des extrémités de segments, en
#: MÈTRES (convertie dans l'unité du fichier quand elle est déclarée).
TOL_FUSION_M = 0.01

#: Fins de ligne d'un DXF (CRLF des exports CAD, CR des anciens Mac).
CRLF, CR, LF = chr(13) + chr(10), chr(13), chr(10)

#: Unités du fichier par mètre (``_UNITES_INSUNITS`` ci-dessous).
_FACTEUR_UNITE = {'m': 1.0, 'cm': 100.0, 'mm': 1000.0, 'pouce': 39.3701,
                  'pied': 3.28084}

#: Pas angulaire maximal d'un arc discrétisé (10°).
_PAS_ARC_RAD = math.radians(10.0)


class DxfInvalide(ValueError):
    """Levée pour tout fichier illisible comme DXF — jamais un 500."""


def _unite_document(doc):
    try:
        code = int(doc.header.get('$INSUNITS', 0) or 0)
    except Exception:  # noqa: BLE001 — un en-tête bizarre ne doit rien casser
        return 'inconnu'
    return _UNITES_INSUNITS.get(code, 'inconnu')


def _tolerance(unite):
    """``TOL_FUSION_M`` dans l'unité DU FICHIER (mètres si inconnue)."""
    return TOL_FUSION_M * _FACTEUR_UNITE.get(unite, 1.0)


def _arc_discretise(p1, p2, bulge):
    """Points INTERMÉDIAIRES de l'arc de ``p1`` à ``p2`` porté par ``bulge``.

    ``bulge = tan(θ/4)`` (θ = angle balayé, signé : positif = anti-horaire).
    Un arc aplati en corde fausserait l'aire et l'emprise : il est discrétisé
    par pas de 10° au plus.
    """
    if not bulge:
        return []
    theta = 4.0 * math.atan(bulge)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    corde = math.hypot(dx, dy)
    if corde == 0:
        return []
    rayon = corde / (2.0 * math.sin(abs(theta) / 2.0))
    milieu = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
    # Le centre est à gauche de la corde pour un arc anti-horaire, à droite
    # sinon, à la distance signée r·cos(|θ|/2) (négative au-delà de 180°).
    decalage = math.copysign(rayon * math.cos(abs(theta) / 2.0), bulge)
    centre = (milieu[0] + decalage * (-dy / corde),
              milieu[1] + decalage * (dx / corde))
    depart = math.atan2(p1[1] - centre[1], p1[0] - centre[0])
    pas = max(2, int(math.ceil(abs(theta) / _PAS_ARC_RAD)))
    return [[centre[0] + rayon * math.cos(depart + theta * k / pas),
             centre[1] + rayon * math.sin(depart + theta * k / pas)]
            for k in range(1, pas)]


def _points_avec_arcs(points, ferme):
    """``[(x, y, bulge), …]`` → sommets ``[x, y]``, arcs discrétisés."""
    sortie = []
    total = len(points)
    for rang, (x, y, bulge) in enumerate(points):
        sortie.append([float(x), float(y)])
        if bulge and (rang < total - 1 or ferme):
            suivant = points[(rang + 1) % total]
            sortie.extend(_arc_discretise(
                (x, y), (suivant[0], suivant[1]), float(bulge)))
    return sortie


def _polyligne(entite):
    """``(sommets, fermee)`` d'une LWPOLYLINE / POLYLINE — jamais le z."""
    if entite.dxftype() == 'LWPOLYLINE':
        points = [(p[0], p[1], p[2]) for p in entite.get_points('xyb')]
        ferme = bool(entite.closed)
    else:
        points = [(v.dxf.location.x, v.dxf.location.y,
                   v.dxf.get('bulge', 0.0) or 0.0)
                  for v in entite.vertices]
        ferme = bool(entite.is_closed)
    return _points_avec_arcs(points, ferme), ferme


def _aire(sommets):
    """Aire (formule des lacets) — dans l'unité DU FICHIER, au carré."""
    total = 0.0
    for rang, (x1, y1) in enumerate(sommets):
        x2, y2 = sommets[(rang + 1) % len(sommets)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _entite(sommets, fermee, tolerance):
    """Une entité candidate : sommets, fermeture, aire, emprise.

    Un tracé dont le dernier point retombe sur le premier (à la tolérance
    près) est FERMÉ, et son point de bouclage n'est pas compté deux fois.
    """
    points = [[float(x), float(y)] for x, y in sommets]
    if (len(points) > 2 and math.hypot(points[0][0] - points[-1][0],
                                       points[0][1] - points[-1][1])
            <= tolerance):
        points.pop()
        fermee = True
    abscisses = [p[0] for p in points]
    ordonnees = [p[1] for p in points]
    return {
        'sommets': points,
        'fermee': bool(fermee),
        'aire': round(_aire(points), 6) if fermee and len(points) >= 3
        else 0.0,
        'emprise': {
            'largeur': round(max(abscisses) - min(abscisses), 6)
            if points else 0.0,
            'hauteur': round(max(ordonnees) - min(ordonnees), 6)
            if points else 0.0,
        },
    }


def _fusionner_segments(segments, tolerance):
    """Chaîne des segments LINE bout à bout (à ``tolerance``) en entités.

    Un cycle devient une entité FERMÉE ; une chaîne qui ne se referme pas
    reste ouverte. Les extrémités sont rapprochées par une grille (pas de
    comparaison de toutes les paires : un export de 20 000 segments reste
    instantané).
    """
    tolerance = tolerance if tolerance > 0 else 1e-9
    grille, noeuds = {}, []

    def noeud(point):
        cx = int(math.floor(point[0] / tolerance))
        cy = int(math.floor(point[1] / tolerance))
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for rang in grille.get((gx, gy), ()):
                    autre = noeuds[rang]
                    if math.hypot(autre[0] - point[0],
                                  autre[1] - point[1]) <= tolerance:
                        return rang
        noeuds.append(point)
        grille.setdefault((cx, cy), []).append(len(noeuds) - 1)
        return len(noeuds) - 1

    aretes = []
    for debut, fin in segments:
        a, b = noeud(debut), noeud(fin)
        if a != b:
            aretes.append((a, b))
    adjacence = {}
    for rang, (a, b) in enumerate(aretes):
        adjacence.setdefault(a, []).append(rang)
        adjacence.setdefault(b, []).append(rang)

    utilisees = set()
    departs = ([n for n in sorted(adjacence) if len(adjacence[n]) % 2 == 1]
               + sorted(adjacence))
    entites = []
    for depart in departs:
        while any(rang not in utilisees for rang in adjacence[depart]):
            chemin, courant = [depart], depart
            while True:
                suite = next((rang for rang in adjacence[courant]
                              if rang not in utilisees), None)
                if suite is None:
                    break
                utilisees.add(suite)
                a, b = aretes[suite]
                courant = b if a == courant else a
                chemin.append(courant)
            ferme = len(chemin) >= 4 and chemin[0] == chemin[-1]
            if ferme:
                chemin.pop()
            entites.append(_entite([noeuds[n] for n in chemin], ferme,
                                   tolerance))
    return entites


def _entite_principale(entites):
    """LE critère de choix du contour par défaut — un seul pour DXF et PDF.

    L'entité FERMÉE de plus grande AIRE (le toit, quand il est dessiné
    seul ; sinon la parcelle) — jamais celle qui a le plus de sommets : un
    contour de parcelle finement découpé n'est pas le toit. ``None`` quand
    aucune entité n'est fermée.
    """
    fermees = [entite for entite in entites if entite['fermee']]
    if not fermees:
        return None
    return max(fermees, key=lambda entite: entite['aire'])


def _calque(nom, entites):
    """Le calque publié : détail des entités + sommets de la principale.

    ``sommets`` : ceux de l'entité principale ; à défaut (aucune fermée),
    ceux de l'entité la plus riche — le calque reste VISIBLE dans le menu
    (compte de sommets), c'est le choix du contour qui le refuse.
    """
    principale = _entite_principale(entites)
    if principale is None and entites:
        principale = max(entites, key=lambda e: len(e['sommets']))
    return {
        'nom': nom,
        'entites': len(entites),
        'sommets': principale['sommets'] if principale else [],
        'entites_detail': [
            {'rang': rang, 'sommets': len(entite['sommets']),
             'aire': entite['aire'], 'emprise': entite['emprise'],
             'fermee': entite['fermee']}
            for rang, entite in enumerate(entites, start=1)],
        # Les sommets de CHAQUE entité (même ordre que ``entites_detail``) :
        # ``contour_du_calque`` y choisit par rang ; la vue ne les publie pas.
        'entites_pts': [entite['sommets'] for entite in entites],
        'entites_fermees': [entite['fermee'] for entite in entites],
    }


def _decoder_dxf(contenu):
    """Le texte d'un DXF (fins de ligne normalisées), BON encodage.

    Les fins de ligne CRLF des exports CAD sont ramenées à LF : sans cela
    ``ezdxf`` ne lit AUCUNE entité d'un flux texte CRLF.
    """
    texte = _decoder_octets(contenu)
    return texte.replace(CRLF, LF).replace(CR, LF)


def _decoder_octets(contenu):
    """Les octets d'un DXF décodés avec le BON encodage.

    UTF-8 d'abord (DXF R2007+ et ASCII pur) ; à défaut, la page de code que
    le fichier DÉCLARE (``$DWGCODEPAGE``, ``ANSI_1252`` → cp1252), à défaut
    cp1252. Jamais ``errors='replace'`` : un « â » remplacé par « � » fait
    deux calques « Bâtiment » et « Bétiment » homonymes.
    """
    try:
        return contenu.decode('utf-8')
    except UnicodeDecodeError:
        pass
    encodage = 'cp1252'
    trouve = re.search(rb'\$DWGCODEPAGE\s*\r?\n\s*3\s*\r?\n\s*([^\r\n]+)',
                       contenu[:200000])
    if trouve:
        from ezdxf.tools.codepage import toencoding

        encodage = toencoding(
            trouve.group(1).decode('ascii', 'ignore').strip())
    try:
        return contenu.decode(encodage)
    except (UnicodeDecodeError, LookupError):
        return contenu.decode('cp1252', errors='replace')


def analyser_dxf(contenu: bytes) -> dict:
    """Parse un DXF EN MÉMOIRE → ``{'calques': [...], 'unite': ...}``.

    Chaque calque : ``{'nom', 'entites' (nombre), 'sommets',
    'entites_detail'}``.
    Les entités sont les POLYLIGNES (arcs à ``bulge`` discrétisés) et les
    chaînes de segments LINE rapprochés bout à bout : un toit dessiné en
    quatre LINE est UN contour fermé. ``sommets`` est celui de l'entité
    FERMÉE de plus grande aire (``_entite_principale``) — jamais un mélange
    de plusieurs entités, qui produirait un contour qui n'existe nulle part
    dans le fichier ; ``entites_detail`` liste rang, sommets, aire, emprise
    et fermeture de chacune, pour que l'écran propose le choix.

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
        flux = io.StringIO(_decoder_dxf(contenu))
        doc = ezdxf.read(flux)
    except Exception as exc:  # noqa: BLE001 — fichier hostile : jamais un 500
        raise DxfInvalide(
            "Ce fichier n'a pas pu être lu comme un DXF (export corrompu ou "
            "incompatible). Vérifiez qu'il s'agit bien d'un export DXF, pas "
            'DWG.') from exc

    unite = _unite_document(doc)
    tolerance = _tolerance(unite)
    polylignes: dict[str, list] = {}
    segments: dict[str, list] = {}
    try:
        espace = doc.modelspace()
        for entite in espace:
            type_dxf = entite.dxftype()
            if type_dxf not in _TYPES_RETENUS:
                continue
            nom_calque = entite.dxf.layer or '0'
            polylignes.setdefault(nom_calque, [])
            segments.setdefault(nom_calque, [])
            if type_dxf == 'LINE':
                d = entite.dxf
                segments[nom_calque].append(
                    ((float(d.start.x), float(d.start.y)),
                     (float(d.end.x), float(d.end.y))))
            else:
                sommets, ferme = _polyligne(entite)
                if sommets:
                    polylignes[nom_calque].append(
                        _entite(sommets, ferme, tolerance))
    except Exception as exc:  # noqa: BLE001 — un DXF structurellement valide
        # mais illisible en pratique (entité corrompue) reste un refus 400.
        raise DxfInvalide(
            "Ce fichier DXF n'a pas pu être parcouru jusqu'au bout — il est "
            'probablement corrompu.') from exc

    calques = [
        _calque(nom, polylignes[nom]
                + _fusionner_segments(segments[nom], tolerance))
        for nom in sorted(polylignes)]
    return {'calques': calques, 'unite': unite}


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
            entites = _entites_des_traces(traces)
            if entites:
                calques.append(_calque(f'Page {numero + 1}', entites))
    finally:
        document.close()

    if not calques:
        raise DxfInvalide(
            'Ce PDF ne contient aucun tracé vectoriel : c\'est un plan '
            'SCANNÉ (une image). Réimportez-le en DXF, ou en PDF vectoriel '
            'exporté depuis le logiciel de dessin.')

    return {'format': 'pdf', 'unite': 'inconnu', 'calques': calques}


def _entites_des_traces(traces):
    """Les entités d'une page PDF : segments chaînés + rectangles.

    MÊME règle de choix que le DXF (``_entite_principale``) : les segments
    ``l`` sont chaînés bout à bout, les rectangles (``re``) et quadrilatères
    (``qu``) sont des entités fermées. Les courbes (``c``) sont IGNORÉES :
    approcher une Bézier par ses points de contrôle produirait un contour qui
    n'est pas celui du plan.
    """
    segments, entites = [], []
    for trace in traces or []:
        for item in trace.get('items') or []:
            if not item:
                continue
            operateur = item[0]
            if operateur == 'l' and len(item) >= 3:
                segments.append(((float(item[1].x), float(item[1].y)),
                                 (float(item[2].x), float(item[2].y))))
            elif operateur == 're' and len(item) >= 2:
                rect = item[1]
                entites.append(_entite(
                    [[rect.x0, rect.y0], [rect.x1, rect.y0],
                     [rect.x1, rect.y1], [rect.x0, rect.y1]], True,
                    TOL_FUSION_M))
            elif operateur == 'qu' and len(item) >= 2:
                quad = item[1]
                entites.append(_entite(
                    [[p.x, p.y] for p in (quad.ul, quad.ur,
                                          quad.lr, quad.ll)], True,
                    TOL_FUSION_M))
    return entites + _fusionner_segments(segments, TOL_FUSION_M)
