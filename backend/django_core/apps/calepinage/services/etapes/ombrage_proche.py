# -*- coding: utf-8 -*-
"""CALX157 — étape « ombrage proche » : la matrice 12×24, HEURE PAR HEURE.

LE CONSTAT
----------
La matrice ``shading12x24`` est produite par l'atelier 3D
(``apps/web/src/scripts/roofPro11/prefill.ts``), décrite au contrat
(``contract_samples/roof_layout_v2.schema.json``, ``$defs/matrice12x24``) et
n'était lue QUE par le moteur de devis, qui la réduit à un seul pourcentage
annuel (``apps/ventes/etude.py::_weighted_shading_loss_pct``). Un
pourcentage annuel ne sait pas qu'une ombre de 8 h du matin en décembre ne
coûte pas ce qu'elle coûterait à midi en juin. ``apps/calepinage`` ne la
lisait nulle part.

CE QUE FAIT CETTE ÉTAPE
------------------------
Le facteur ``matrice[mois − 1][heure]`` de l'heure du point multiplie sa
composante DIRECTE ``gb_i_w_m2``. La convention est celle de l'atelier :
1 = plein soleil, 0 = entièrement masqué. Le DIFFUS et le RÉFLÉCHI ne sont
pas touchés — une cellule à l'ombre d'un obstacle proche voit encore le ciel.

Parité : HelioScope calcule et applique les ombres d'obstruction sur chaque
module, à chaque heure
(https://help-center.helioscope.com/hc/en-us/articles/7899937559443-Shade-Modeling).

L'INTRANSIGEANCE DU SÉRIALISEUR, CÔTÉ SERVEUR
-----------------------------------------------
``serializeShading`` refuse EN BLOC une matrice de mauvaise forme : mieux
vaut aucune ombre qu'une matrice à moitié fausse. La même règle vaut ici —
12 lignes de 24 facteurs dans [0, 1], sinon l'étape est OMISE en NOMMANT la
cellule (ou la forme) fautive. Rien n'est réparé, rien n'est complété.

Matrice absente ⇒ étape OMISE avec son motif : un facteur 1 supposé se
lirait « aucune ombre, vérifié » (D-CALX 7).

EXCLUSIVITÉ (D-CALX 16)
------------------------
Quand le document porte une lecture d'accès solaire MODULE PAR MODULE, c'est
elle qui s'applique (CALX158) et cette matrice est écartée : les deux
viennent du même moteur d'ombrage, et les cumuler compterait l'ombre deux
fois. L'ordonnanceur l'écarte déjà ; le module le refait pour qu'un appel
direct ne puisse pas contourner la règle.
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from apps.calepinage.services.pvgis_serie import MOTIF_COMPOSANTES_ABSENTES

#: Le nom du poste — celui de ``chaine_pertes.ORDRE_ETAPES``.
POSTE = 'ombrage_proche'

#: La forme EXACTE d'une matrice d'ombrage de l'atelier : 12 mois × 24 heures.
MOIS = 12
HEURES = 24

#: Les emplacements lus dans ``contexte['ombrage']``, dans cet ordre. Le
#: premier est le nom du document (``roof_layout`` v2) ; les deux autres sont
#: les formes francisées qu'un contexte peut porter.
CLES_MATRICE = ('shading12x24', 'matrice_12x24', 'matrice')

#: Le motif publié quand aucune matrice n'accompagne le document.
MOTIF_SANS_MATRICE = (
    "Le document ne porte aucune matrice d'ombrage 12×24 : l'ombrage proche "
    "n'est pas calculé. Un facteur 1 supposé se lirait « aucune ombre, "
    'vérifié ».')

#: Le motif publié quand l'accès solaire par module prend la main.
MOTIF_ACCES_MODULE = (
    "Le document porte une lecture d'accès solaire MODULE PAR MODULE : c'est "
    "elle qui s'applique, et la matrice 12×24 du même moteur d'ombrage est "
    "écartée pour ne pas compter l'ombre deux fois.")

#: La référence publiée dans ``cascade[].reference``.
REFERENCE = (
    "HelioScope — Shade Modeling : les ombres d'obstruction sont calculées "
    'et appliquées sur chaque module du champ, à chaque heure — '
    'https://help-center.helioscope.com/hc/en-us/articles/'
    '7899937559443-Shade-Modeling. Convention de la matrice : atelier 3D '
    'du constructeur 3D (roofPro11, serializeShading), 1 = plein soleil, 0 = masqué.')

__all__ = ['POSTE', 'MOIS', 'HEURES', 'CLES_MATRICE', 'MOTIF_SANS_MATRICE',
           'MOTIF_ACCES_MODULE', 'REFERENCE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — le direct dératé par la matrice de son heure.

    Fonction PURE : ni ``serie`` ni ses points ne sont modifiés sur place.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    libelle = _libelle()
    ombrage = contexte.get('ombrage') or {}

    if _acces_par_module(ombrage):
        return serie, etapes.etape_omise(libelle, MOTIF_ACCES_MODULE)

    brute = _matrice_brute(ombrage)
    if brute is None:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_MATRICE,
                                         champ='ombrage.shading12x24')
    matrice, refus = _lire_matrice(brute)
    if refus:
        return serie, etapes.etape_omise(libelle, refus,
                                         champ='ombrage.shading12x24')

    points = (serie or {}).get('points') or []
    if not points:
        return serie, etapes.etape_omise(
            libelle, 'La série horaire est vide : aucune matrice ne peut '
            'être appliquée heure par heure.', champ='serie.points')
    if any(point.get('gb_i_w_m2') is None for point in points):
        return serie, etapes.etape_omise(libelle, MOTIF_COMPOSANTES_ABSENTES)
    if _cellule_du_point(points[0]) is None:
        return serie, etapes.etape_omise(
            libelle, "Les points de la série ne portent ni mois ni heure "
            "lisibles : la case de la matrice ne peut pas leur être "
            'associée.', champ='serie.points[].heure')

    suite, ombrees = _derater(serie, points, matrice)
    facteurs = [facteur for ligne in matrice for facteur in ligne]
    return suite, etapes.etape_appliquee(
        libelle,
        source='document',
        reference=REFERENCE,
        entree={
            'matrice': f'{MOIS}×{HEURES}',
            'origine': 'atelier 3D (roofPro11, serializeShading)',
            'convention': '1 = plein soleil, 0 = entièrement masqué',
            'cases_ombrees': sum(1 for facteur in facteurs if facteur < 1.0),
            'facteur_minimal': round(min(facteurs), 6),
            'heures_ombrees': ombrees,
            'heures_lues': len(points),
            'composantes_touchees': 'gb_i_w_m2 seule (le diffus et le '
                                    'réfléchi ne sont pas masqués)',
        })


# ── les entrées, une par une ────────────────────────────────────────────

def _libelle():
    """Le libellé FRANÇAIS du poste, déclaré une seule fois (CALX148)."""
    from apps.calepinage.services.chaine_pertes import LIBELLES

    return LIBELLES[POSTE]


def _acces_par_module(ombrage):
    """Le document porte-t-il une lecture d'accès solaire par module ?"""
    acces = ombrage.get('solar_access') or ombrage.get('solarAccess') or {}
    return bool(acces) if isinstance(acces, dict) else False


def _matrice_brute(ombrage):
    """La matrice telle que le contexte la porte, ou ``None``."""
    for cle in CLES_MATRICE:
        valeur = ombrage.get(cle)
        if valeur is not None:
            return valeur
    return None


def _lire_matrice(brute):
    """``(matrice, refus)`` — la matrice lue, ou le refus qui la NOMME.

    Refus EN BLOC : une seule case illisible et rien n'est appliqué. La
    matrice à moitié juste est précisément ce que ``serializeShading``
    refuse d'émettre.
    """
    if not isinstance(brute, (list, tuple)):
        return None, (
            "La matrice d'ombrage n'est pas une liste de lignes (reçu : "
            f'{type(brute).__name__}) : elle est refusée en bloc.')
    if len(brute) != MOIS:
        return None, (
            f"La matrice d'ombrage porte {len(brute)} ligne(s) au lieu des "
            f'{MOIS} mois attendus : elle est refusée en bloc plutôt que '
            'complétée.')
    lues = []
    for rang, ligne in enumerate(brute):
        if not isinstance(ligne, (list, tuple)):
            return None, (
                f"La ligne n°{rang + 1} de la matrice d'ombrage (mois "
                f"{rang + 1}) n'est pas une liste d'heures (reçu : "
                f'{type(ligne).__name__}).')
        if len(ligne) != HEURES:
            return None, (
                f"La ligne n°{rang + 1} de la matrice d'ombrage (mois "
                f'{rang + 1}) porte {len(ligne)} heure(s) au lieu de '
                f'{HEURES}.')
        facteurs = []
        for heure, valeur in enumerate(ligne):
            facteur = _nombre(valeur)
            if facteur is None or not 0.0 <= facteur <= 1.0:
                return None, (
                    f"La case [mois {rang + 1}, heure {heure}] de la matrice "
                    f"d'ombrage n'est pas un facteur de 0 à 1 (reçu : "
                    f'{valeur!r}).')
            facteurs.append(facteur)
        lues.append(facteurs)
    return lues, ''


# ── le dératage, heure par heure ────────────────────────────────────────

def _derater(serie, points, matrice):
    """Une COPIE de la série dératée, et le nombre d'heures ombrées."""
    suite = []
    ombrees = 0
    for point in points:
        cellule = _cellule_du_point(point)
        if cellule is None:
            suite.append(point)
            continue
        mois, heure = cellule
        facteur = matrice[mois - 1][heure]
        directe = _nombre(point.get('gb_i_w_m2')) or 0.0
        if facteur < 1.0 and directe > 0.0:
            ombrees += 1
        copie = dict(point)
        copie['gb_i_w_m2'] = directe * facteur
        _reporter(point, copie)
        suite.append(copie)
    rendue = dict(serie)
    rendue['points'] = suite
    return rendue, ombrees


def _cellule_du_point(point):
    """``(mois, heure)`` du point, ou ``None`` s'ils sont illisibles."""
    mois = _entier(point.get('mois'))
    heure = _entier(point.get('heure'))
    if mois is None or heure is None:
        return None
    if not 1 <= mois <= MOIS or not 0 <= heure < HEURES:
        return None
    return mois, heure


def _reporter(avant, apres):
    """Recompose ``gi_w_m2`` et met l'énergie à l'échelle du même rapport.

    ``G(i)`` est la SOMME des trois composantes sous ``components=1``
    (vérifié sur les réponses PVGIS réelles par
    ``tests/test_calx152_composantes.py``). Une colonne de puissance déjà
    présente suit le MÊME rapport, heure par heure.
    """
    diffuse = _nombre(avant.get('gd_i_w_m2')) or 0.0
    reflechie = _nombre(avant.get('gr_i_w_m2')) or 0.0
    globale_avant = _nombre(avant.get('gi_w_m2'))
    globale_apres = apres['gb_i_w_m2'] + diffuse + reflechie
    apres['gi_w_m2'] = globale_apres
    if not globale_avant:
        return
    rapport = globale_apres / globale_avant
    for colonne in etapes.ORDRE_COLONNES_ENERGIE:
        valeur = _nombre(avant.get(colonne))
        if valeur is not None:
            apres[colonne] = valeur * rapport


def _nombre(valeur):
    """Un flottant lisible, ou ``None`` — jamais une valeur de remplacement."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre


def _entier(valeur):
    """Un entier lisible, ou ``None``."""
    nombre = _nombre(valeur)
    return None if nombre is None else int(nombre)
