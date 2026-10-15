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


class CalqueInconnu(PlanIllisible):
    """Le calque demandé n'existe pas dans CE fichier : 404 nommant ``calque``
    (l'existence d'un calque est un fait du fichier déposé, que le schéma ne
    peut pas porter)."""


class EntiteInconnue(PlanIllisible):
    """Le rang d'entité demandé dépasse ceux du calque : 404 nommant
    ``entite``."""


class CalqueInexploitable(PlanIllisible):
    """Le calque existe mais ne porte aucun contour fermé exploitable (tracé
    non fermé, moins de 3 sommets) : refus qui dépend du CONTENU du fichier,
    409 nommant ``calque``."""


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
        raise CalqueInconnu(
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
        raise CalqueInexploitable(
            f"Le calque « {nom_calque} » ne porte aucun tracé exploitable "
            "comme contour.", champ='calque')

    if entite is not None:
        if (isinstance(entite, bool) or not isinstance(entite, int)
                or not 1 <= entite <= len(points)):
            raise EntiteInconnue(
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
        raise CalqueInexploitable(
            f"Le calque « {nom_calque} » ne porte aucun contour fermé : "
            f"tracé non fermé : {segments} {mot}. Fermez le tracé dans le "
            "dessin, ou choisissez un autre calque.", champ='calque')
    sommets = points[rang]
    if len(sommets) < 3:
        raise CalqueInexploitable(
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
    """ACAL69 — calage refusé, le CHAMP fautif nommé (calage ou pin).

    Une FORME fautive (JSON illisible, point, nombre hors bornes) est un 400 :
    le schéma publié (``serializers.CalageSerializer``) la dit."""

    def __init__(self, message, *, champ='calage'):
        super().__init__(message)
        self.champ = champ


class CalageEnConflit(CalageIllisible):
    """Calage de forme CONFORME mais inexploitable avec CE plan / CE calepinage
    (points confondus, aucun calque choisi, pas d'épingle, échelle hors des
    nombres représentables) : le schéma ne peut pas le dire, 409."""


#: Bornes de SAISIE du calage — ni une mesure ni une norme : elles écartent les
#: débordements flottants de l'échelle (distance / |AB|) et sont les MÊMES au
#: schéma publié (``serializers.CalageSerializer``) et à la lecture ci-dessous
#: (un seul prédicat). Coordonnées d'un point du plan, dans l'unité du fichier.
COORDONNEE_CALAGE_MAX = 1e7

#: Distance réelle saisie entre A et B, en mètres : au plus dix mille
#: kilomètres, strictement positive (plancher d'un micromètre).
DISTANCE_CALAGE_MIN_M = 1e-6
DISTANCE_CALAGE_MAX_M = 1e7

#: Rotation saisie, en degrés : dix mille degrés au plus, dans les deux sens.
ROTATION_CALAGE_MAX_DEG = 1e4


def _premier_refus(erreurs, chemin='calage'):
    """Le premier refus d'un sérialiseur, en français, avec son chemin."""
    if isinstance(erreurs, dict):
        for cle, sous in erreurs.items():
            return _premier_refus(sous, f'{chemin}.{cle}')
    if isinstance(erreurs, (list, tuple)) and erreurs:
        return _premier_refus(erreurs[0], chemin)
    return f'Calage illisible : « {chemin} » : {erreurs}'


def lire_calage(brut):
    """Valide le corps ``calage`` (dict, ou JSON en texte : multipart).

    UN seul prédicat de forme : ``serializers.CalageSerializer`` — celui que
    le schéma OpenAPI publie.

    Returns:
        ``(point_a, point_b, distance_m, rotation_deg)``.

    Raises:
        CalageIllisible: forme, nombre ou borne (400).
        CalageEnConflit: A = B, échelle indéterminée (409) — jamais une échelle
            devinée.
    """
    import json

    from ..serializers import CalageSerializer

    if isinstance(brut, str):
        try:
            brut = json.loads(brut)
        except ValueError as exc:
            raise CalageIllisible(
                "Calage illisible : le champ « calage » n'est pas un JSON "
                "valide.") from exc
    champs = CalageSerializer(data=brut)
    if not champs.is_valid():
        raise CalageIllisible(_premier_refus(champs.errors))
    valides = champs.validated_data
    point_a = (valides['pointA'][0], valides['pointA'][1])
    point_b = (valides['pointB'][0], valides['pointB'][1])
    rotation = valides.get('rotationDeg')
    rotation = 0.0 if rotation is None else rotation
    ab = ((point_b[0] - point_a[0]) ** 2
          + (point_b[1] - point_a[1]) ** 2) ** 0.5
    if ab == 0:
        raise CalageEnConflit("Calage refusé : les deux points sont "
                              "confondus, l'échelle serait indéterminée.")
    return point_a, point_b, valides['distanceM'], rotation


def _epingle_exploitable(pin):
    """``(lat, lng)`` flottants d'une épingle dans les bornes GPS, ou ``None``."""
    import math

    if not isinstance(pin, dict):
        return None
    try:
        lat, lng = float(pin.get('lat')), float(pin.get('lng'))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)
            and -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    return lat, lng


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
        CalageEnConflit: ``pin`` (sans épingle exploitable), contour vide, ou
            échelle dont le résultat sort des nombres représentables.
    """
    import math

    from .zones import deprojeteur_local

    position = _epingle_exploitable(pin)
    if position is None:
        raise CalageEnConflit(
            "Ce calepinage n'a pas d'épingle : posez-la sur la carte avant "
            "de caler le plan.", champ='pin')
    if not contour:
        raise CalageEnConflit("Aucun contour à caler : choisissez un calque.",
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
    deprojeter = deprojeteur_local((position[1], position[0]))
    sortie = []
    for x, y in locaux:
        lng, lat = deprojeter((x - cx, y - cy))
        sortie.append([round(lng, 9), round(lat, 9)])
    if not all(math.isfinite(valeur) for point in sortie for valeur in point):
        raise CalageEnConflit(
            "Calage inexploitable : l'échelle (distance réelle / distance A-B) "
            "sort des nombres représentables pour ce plan — éloignez A et B.")
    return sortie
