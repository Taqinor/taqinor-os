"""CAL62 — importer un plan (DXF / PDF vectoriel) dans l'atelier de calepinage.

L'ANALYSEUR N'EST PAS RECODÉ
---------------------------
Il existe, testé et en production : ``analyse_plan.analyser_plan_importe``
(ezdxf pour le DXF, PyMuPDF pour le PDF vectoriel, 5 Mo max), et ce module
l'APPELLE. Un second analyseur donnerait, tôt ou tard, deux contours
différents pour un même plan.

OÙ IL VIT (SOLMVP15)
--------------------
Il vivait chez le module d'appels d'offres, lu par son seul ``selectors.py``.
Ce module-là sort du produit : l'analyseur est rapatrié dans
``apps/calepinage/analyse_plan.py``, à la ligne près — même forme publiée,
mêmes refus, même unité jamais devinée.

CE QUE CE MODULE PRODUIT
------------------------
Un **contour** (liste de ``[x, y]`` dans l'unité DU FICHIER) et ses **cotes
hors-tout** dérivées de ce contour. Rien n'est converti en mètres ici : un DXF
qui ne déclare pas ``$INSUNITS`` et un PDF (points typographiques) rendent
``unite='inconnu'``, et c'est la calibration de l'atelier qui donne l'échelle.
Une conversion supposée produirait un plan faux qui a l'air juste.

AUCUNE ÉCRITURE : ces fonctions sont PURES (octets en entrée, dict en sortie).
"""
from __future__ import annotations


class PlanIllisible(ValueError):
    """Refus d'import, message FRANÇAIS nommant la cause, champ fautif nommé.

    Enveloppe le refus de l'analyseur (``analyse_plan.DxfInvalide``) pour que
    l'appelant n'ait pas à connaître les exceptions de l'analyseur.
    """

    def __init__(self, message, *, champ='fichier'):
        super().__init__(message)
        self.champ = champ


def analyser_plan(contenu, *, nom_fichier=''):
    """Analyse un plan déposé, par l'analyseur du module — jamais un second.

    Args:
        contenu: les octets du fichier (DXF, ou PDF vectoriel).
        nom_fichier: indicatif (messages) — le format est déduit du contenu.

    Returns:
        ``{'format', 'unite', 'calques': [{'nom', 'entites', 'sommets'}]}`` —
        exactement la forme que servait déjà l'écran d'import DXF.

    Raises:
        PlanIllisible: fichier vide, trop lourd, illisible, ou PDF SANS aucun
            tracé vectoriel (plan scanné) — la cause est nommée en français.
    """
    from ..analyse_plan import analyser_plan_importe

    try:
        return analyser_plan_importe(contenu, nom_fichier=nom_fichier)
    except ValueError as refus:  # ``DxfInvalide`` est un ``ValueError``
        raise PlanIllisible(str(refus)) from refus


def contour_du_calque(analyse, nom_calque, *, entite=None):
    """Le contour proposé par UN calque de l'analyse.

    Args:
        entite: rang (1, 2, …) de l'entité choisie dans
            ``calques[].entites_detail`` ; absent, l'entité FERMÉE de plus
            grande AIRE (``analyse_plan._entite_principale`` : le toit si
            choisi seul, sinon la parcelle).

    Returns:
        ``[[x, y], …]`` dans l'unité du fichier.

    Raises:
        PlanIllisible: calque inconnu (le message liste les calques
            disponibles — un refus qui ne dit pas quoi choisir est inutile),
            entité inexistante (champ ``entite``), tracé NON FERMÉ, ou moins
            de 3 sommets.
    """
    calques = (analyse or {}).get('calques') or []
    par_nom = {calque.get('nom'): calque for calque in calques}
    calque = par_nom.get(nom_calque)
    if calque is None:
        disponibles = ', '.join(sorted(nom for nom in par_nom if nom)) \
            or 'aucun'
        raise PlanIllisible(
            f"Le calque « {nom_calque} » n'existe pas dans ce plan "
            f'(calques disponibles : {disponibles}).', champ='calque')

    points = calque.get('entites_pts')
    if points is None:      # analyse « ancienne forme » : sommets seuls
        sommets = calque.get('sommets') or []
        points = [sommets] if sommets else []
        fermees = [True] if len(sommets) >= 3 else [False]
    else:
        fermees = calque.get('entites_fermees') or [True] * len(points)
    if not points:
        raise PlanIllisible(
            f"Le calque « {nom_calque} » ne porte aucun tracé exploitable "
            "comme contour.", champ='calque')

    if entite is not None:
        if (isinstance(entite, bool) or not isinstance(entite, int)
                or not 1 <= entite <= len(points)):
            raise PlanIllisible(
                f"L'entité {entite!r} n'existe pas dans le calque "
                f"« {nom_calque} » (entités disponibles : 1 à "
                f"{len(points)}).", champ='entite')
        rang = entite - 1
    else:
        from ..analyse_plan import _entite_principale

        entites = [{'fermee': fermees[i], 'aire': detail.get('aire') or 0.0}
                   for i, detail in enumerate(
                       calque.get('entites_detail')
                       or [{} for _ in points])]
        principale = _entite_principale(entites)
        rang = entites.index(principale) if principale is not None else None

    if rang is None or not fermees[rang]:
        segments = sum(max(1, len(pts) - 1) for pts in points) \
            if rang is None else max(1, len(points[rang]) - 1)
        mot = 'segment isolé' if segments == 1 else 'segments isolés'
        raise PlanIllisible(
            f"Le calque « {nom_calque} » ne porte aucun contour fermé : "
            f"tracé non fermé : {segments} {mot}. Fermez le tracé dans le "
            "dessin, ou choisissez un autre calque.", champ='calque')
    sommets = points[rang]
    if len(sommets) < 3:
        raise PlanIllisible(
            f"Le calque « {nom_calque} » : l'entité choisie n'a que "
            f"{len(sommets)} sommet(s) ; un contour demande au moins 3 "
            "sommets.", champ='calque')
    return [[float(x), float(y)] for x, y in sommets]


def cotes_hors_tout(contour):
    """Cotes DÉRIVÉES du contour : ``{'largeur', 'hauteur', 'sommets'}``.

    Hors-tout = l'encombrement rectangulaire du tracé, dans l'unité du
    fichier. Rien n'est ajouté à ce que le plan contient : sans contour, tout
    vaut ``None`` — jamais un ``0`` qui se lirait comme une mesure.
    """
    points = [(float(x), float(y)) for x, y in (contour or [])]
    if len(points) < 2:
        return {'largeur': None, 'hauteur': None, 'sommets': len(points)}
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return {
        'largeur': round(max(xs) - min(xs), 4),
        'hauteur': round(max(ys) - min(ys), 4),
        'sommets': len(points),
    }


class CalageIllisible(ValueError):
    """ACAL69 — calage refusé, le CHAMP fautif nommé (calage ou pin)."""

    def __init__(self, message, *, champ='calage'):
        super().__init__(message)
        self.champ = champ


def _nombre_fini(valeur, libelle):
    import math

    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise CalageIllisible(f"Calage illisible : « {libelle} » doit être "
                              "un nombre.")
    if not math.isfinite(float(valeur)):
        raise CalageIllisible(f"Calage illisible : « {libelle} » doit être "
                              "un nombre fini.")
    return float(valeur)


def lire_calage(brut):
    """Valide le corps ``calage`` (dict, ou JSON en texte : multipart).

    Returns:
        ``(point_a, point_b, distance_m, rotation_deg)``.

    Raises:
        CalageIllisible: forme, nombre, distance <= 0 ou A = B (échelle
            indéterminée) — jamais une échelle devinée.
    """
    import json

    if isinstance(brut, str):
        try:
            brut = json.loads(brut)
        except ValueError as exc:
            raise CalageIllisible(
                "Calage illisible : le champ « calage » n'est pas un JSON "
                "valide.") from exc
    if not isinstance(brut, dict):
        raise CalageIllisible(
            "Calage illisible : {pointA, pointB, distanceM, rotationDeg} "
            "est attendu.")
    points = []
    for cle in ('pointA', 'pointB'):
        point = brut.get(cle)
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise CalageIllisible(f"Calage illisible : « {cle} » doit être "
                                  "un point [x, y].")
        points.append((_nombre_fini(point[0], cle),
                       _nombre_fini(point[1], cle)))
    distance = _nombre_fini(brut.get('distanceM'), 'distanceM')
    if distance <= 0:
        raise CalageIllisible("Calage refusé : la distance réelle entre les "
                              "deux points doit être positive.")
    rotation = brut.get('rotationDeg')
    rotation = 0.0 if rotation is None else _nombre_fini(rotation,
                                                         'rotationDeg')
    ab = ((points[1][0] - points[0][0]) ** 2
          + (points[1][1] - points[0][1]) ** 2) ** 0.5
    if ab == 0:
        raise CalageIllisible("Calage refusé : les deux points sont "
                              "confondus, l'échelle serait indéterminée.")
    return points[0], points[1], distance, rotation


def contour_lnglat(contour, calage, pin):
    """ACAL69 — le contour du plan, calé, posé en ``[lng, lat]`` sur l'épingle.

    Échelle = ``distanceM / |AB|`` (la calibration, jamais une estimation) ;
    rotation ``rotationDeg`` en degrés, sens trigonométrique (anti-horaire,
    Y vers le nord) autour de A ; le CENTRE de l'emprise du contour calé est
    ensuite posé sur l'épingle, par ``zones.deprojeteur_local`` — l'inverse du
    repère local unique du module (le même que CAL237).

    Args:
        contour: ``[[x, y], …]`` dans l'unité du fichier.
        calage: ``(point_a, point_b, distance_m, rotation_deg)``
            (``lire_calage``).
        pin: ``{'lat', 'lng'}``.

    Raises:
        CalageIllisible: ``pin`` (sans épingle exploitable) ou contour vide.
    """
    import math

    from .zones import deprojeteur_local

    if (not isinstance(pin, dict) or pin.get('lat') is None
            or pin.get('lng') is None):
        raise CalageIllisible(
            "Ce calepinage n'a pas d'épingle : posez-la sur la carte avant "
            "de caler le plan.", champ='pin')
    if not contour:
        raise CalageIllisible("Aucun contour à caler : choisissez un calque.",
                              champ='calque')
    (ax, ay), (bx, by), distance_m, rotation = calage
    echelle = distance_m / math.hypot(bx - ax, by - ay)
    cos_r = math.cos(math.radians(rotation))
    sin_r = math.sin(math.radians(rotation))
    locaux = []
    for x, y in contour:
        dx, dy = (x - ax) * echelle, (y - ay) * echelle
        locaux.append((dx * cos_r - dy * sin_r, dx * sin_r + dy * cos_r))
    xs = [p[0] for p in locaux]
    ys = [p[1] for p in locaux]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    deprojeter = deprojeteur_local((float(pin['lng']), float(pin['lat'])))
    sortie = []
    for x, y in locaux:
        lng, lat = deprojeter((x - cx, y - cy))
        sortie.append([round(lng, 9), round(lat, 9)])
    return sortie
