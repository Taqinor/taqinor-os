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
