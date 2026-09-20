"""CAL62 — importer un plan (DXF / PDF vectoriel) dans l'atelier de calepinage.

L'ANALYSEUR N'EST PAS RECODÉ
---------------------------
Il existe déjà, testé et en production : ``apps/ao/dxf.py`` ``analyser_dxf``
(ezdxf, 5 Mo max), exposé côté AO par ``POST /api/django/ao/toitures/dxf/
analyser/``. CAL62 lui ajoute une porte FINE — ``apps.ao.selectors.
analyser_plan_importe`` — et ce module l'APPELLE. Un second analyseur
donnerait, tôt ou tard, deux contours différents pour un même plan.

FRONTIÈRE
---------
On lit ``apps.ao`` par son SEUL ``selectors.py`` (import fonction-local) :
jamais ``apps.ao.models``, jamais ``apps.ao.views`` — contrats import-linter
``ao-models-decoupled`` / ``calepinage-models-decoupled``.

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

    Enveloppe le refus de l'analyseur AO (``dxf.DxfInvalide``) pour que
    l'appelant du module n'ait pas à connaître les exceptions d'une autre app.
    """

    def __init__(self, message, *, champ='fichier'):
        super().__init__(message)
        self.champ = champ


def analyser_plan(contenu, *, nom_fichier=''):
    """Analyse un plan déposé, par l'analyseur de l'AO — jamais un second.

    Args:
        contenu: les octets du fichier (DXF, ou PDF vectoriel).
        nom_fichier: indicatif (messages) — le format est déduit du contenu.

    Returns:
        ``{'format', 'unite', 'calques': [{'nom', 'entites', 'sommets'}]}`` —
        exactement la forme que sert déjà l'écran d'import DXF de l'AO.

    Raises:
        PlanIllisible: fichier vide, trop lourd, illisible, ou PDF SANS aucun
            tracé vectoriel (plan scanné) — la cause est nommée en français.
    """
    from apps.ao.selectors import analyser_plan_importe

    try:
        return analyser_plan_importe(contenu, nom_fichier=nom_fichier)
    except ValueError as refus:  # ``dxf.DxfInvalide`` est un ``ValueError``
        raise PlanIllisible(str(refus)) from refus


def contour_du_calque(analyse, nom_calque):
    """Le contour proposé par UN calque de l'analyse.

    Returns:
        ``[[x, y], …]`` dans l'unité du fichier.

    Raises:
        PlanIllisible: calque inconnu (le message liste les calques
            disponibles — un refus qui ne dit pas quoi choisir est inutile),
        ou calque sans tracé exploitable.
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

    sommets = calque.get('sommets') or []
    if len(sommets) < 2:
        raise PlanIllisible(
            f"Le calque « {nom_calque} » ne porte aucun tracé exploitable "
            "comme contour.", champ='calque')
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
