"""CALX161 — ÉTAPE « salissure » : douze mois, jamais une moyenne.

LE CONSTAT
----------
``services/pertes.py`` déclare ``salissure`` comme le SEUL poste
``mensuel: True`` du catalogue, et ``moyenne_mensuelle`` réduit aussitôt les
douze valeurs à une moyenne annuelle avant de les sommer. La saisonnalité
saisie — un toit marocain se salit en été et se rince en novembre — est donc
perdue AVANT tout calcul.

CE QUE CETTE ÉTAPE FAIT
------------------------
Elle applique le facteur du MOIS de chaque heure à l'irradiance globale de
cette heure (et à ses composantes quand la réponse PVGIS les porte, pour que
``gi = gb + gd + gr`` reste vrai), et à la colonne d'énergie de la série. La
moyenne annuelle n'est plus une entrée de calcul : elle est une SORTIE,
publiée dans ``cascade[].entree.moyenne_pct``.

CE QUI LA FAIT SE TAIRE
------------------------
* Le réglage ``simulation.salissure_mensuelle_pct`` n'est pas saisi (ou l'est
  sans source) ⇒ étape OMISE en nommant la clé. Jamais un forfait : PVsyst
  écrit que la salissure dépend de la pluviométrie locale et ne propose
  aucune valeur universelle par défaut
  (https://www.pvsyst.com/help/project-design/array-and-system-losses/
  soiling-loss.html).
* Douze valeurs INCOMPLÈTES ⇒ étape OMISE en nommant les mois manquants.
  Aucun mois n'est comblé par la moyenne des autres : onze mois mesurés et un
  trou, ce n'est pas une année.
* Une VALEUR UNIQUE saisie reste admise et s'applique aux douze mois — en le
  DISANT (``entree.mode = 'annuelle'``). Aurora range salissure, neige et
  ombrage sous la même règle (« Shading, snow, and soiling losses can all be
  specified on an annual OR monthly basis. The default is annual. »,
  https://help.aurorasolar.com/hc/en-us/articles/220450107-System-Losses) ;
  chez nous la saisie annuelle est admise, jamais supposée.
* Les points de la série ne portent pas leur mois ⇒ étape OMISE en nommant la
  colonne : sans le mois, la saisonnalité ne peut pas être attribuée.

LA MACHINERIE EST PARTAGÉE
---------------------------
:func:`valeurs_mensuelles` est écrite ici pour être RÉEMPLOYÉE telle quelle
par l'étape ``neige`` (CALX148), qui se saisit exactement de la même façon :
douze valeurs mensuelles, ou une seule pour les douze.

Module PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.pertes import MOIS_LIBELLES
from apps.calepinage.services.pvgis_serie import COLONNES_COMPOSANTES

#: La clé de réglage société lue ici (registre CALX145).
CLE_REGLAGE = 'salissure_mensuelle_pct'

#: La colonne d'irradiance de plan à laquelle le facteur du mois s'applique.
COLONNE_IRRADIANCE = 'gi_w_m2'

#: Les deux modes de saisie admis, et leur nom publié.
MODE_MENSUEL = 'mensuelle'
MODE_ANNUEL = 'annuelle'

REFERENCE = (
    'PVsyst — Soiling loss : la salissure se saisit en facteurs de perte '
    'MENSUELS, très dépendants de la pluviométrie, sans valeur universelle '
    'par défaut (https://www.pvsyst.com/help/project-design/'
    'array-and-system-losses/soiling-loss.html) ; Aurora — System Losses : '
    '« Shading, snow, and soiling losses can all be specified on an annual '
    'OR monthly basis. The default is annual. » '
    '(https://help.aurorasolar.com/hc/en-us/articles/220450107-System-Losses)'
    '.')

LIBELLE = 'Salissure'

__all__ = ['CLE_REGLAGE', 'COLONNE_IRRADIANCE', 'MODE_MENSUEL',
           'MODE_ANNUEL', 'REFERENCE', 'LIBELLE', 'valeurs_mensuelles',
           'appliquer']


def valeurs_mensuelles(saisie, *, champ):
    """``(douze_valeurs, mode, motif)`` — douze mois, ou une seule valeur.

    La machinerie de saisie « douze valeurs mensuelles OU une valeur unique »,
    écrite une fois pour être réemployée par l'étape ``neige`` (CALX148).

    Args:
        saisie: la valeur saisie — un nombre (appliqué aux douze mois) ou une
            liste/tuple de douze nombres.
        champ: le nom du champ, pour que chaque refus le NOMME.

    Returns:
        ``(valeurs, mode, '')`` quand la saisie tient, où ``valeurs`` est
        toujours une liste de douze pourcentages ; ``(None, None, motif)``
        sinon, le motif étant le français à afficher — il nomme les mois
        manquants un par un, jamais un « saisie invalide » générique.
    """
    if isinstance(saisie, (list, tuple)):
        return _douze_valeurs(saisie, champ=champ)
    unique = _pourcentage(saisie)
    if unique is None:
        return None, None, (
            f'La saisie « {champ} » n\'est ni un pourcentage unique ni une '
            f'liste de douze valeurs mensuelles (reçu : {saisie!r}).')
    return [unique] * 12, MODE_ANNUEL, ''


def appliquer(serie, contexte):
    """``(serie, etape)`` — le facteur du MOIS de chaque heure, ou le silence."""
    contexte = contexte if isinstance(contexte, dict) else {}
    saisie = _etapes.reglage(contexte, CLE_REGLAGE)
    if not saisie:
        return serie, _etapes.etape_omise(
            LIBELLE,
            "Aucune salissure saisie pour cette société : la salissure "
            'dépend de la pluviométrie du site et ne se suppose pas. '
            "L'étape reste omise tant que les douze mois (ou une valeur "
            'unique assumée) ne sont pas renseignés.',
            champ=f'simulation.{CLE_REGLAGE}')

    valeurs, mode, motif = valeurs_mensuelles(
        saisie.get('valeur'), champ=f'simulation.{CLE_REGLAGE}')
    if valeurs is None:
        return serie, _etapes.etape_omise(
            LIBELLE, motif, champ=f'simulation.{CLE_REGLAGE}')

    mois_absents = _mois_absents(serie)
    if mois_absents:
        return serie, _etapes.etape_omise(
            LIBELLE,
            'La série horaire ne porte pas le mois de chacune de ses heures : '
            'la salissure du mois ne peut être attribuée à aucune heure.',
            champ='serie_horaire.mois')

    rendue = _appliquer_par_mois(serie, valeurs)
    entree = {
        'mode': mode,
        'valeurs_pct': list(valeurs),
        'mois': list(MOIS_LIBELLES),
        'moyenne_pct': round(sum(valeurs) / 12.0, 3),
        'source_du_reglage': saisie.get('source'),
        'reference_saisie': saisie.get('reference') or '',
        'colonnes_appliquees': _colonnes_touchees(serie),
    }
    return rendue, _etapes.etape_appliquee(
        LIBELLE, source=saisie.get('source'), entree=entree,
        reference=REFERENCE)


# ── la saisie, mois par mois ───────────────────────────────────────────

def _douze_valeurs(saisie, *, champ):
    """Douze valeurs exactement, toutes lisibles — ou le motif qui le dit."""
    if len(saisie) != 12:
        return None, None, (
            f'La saisie mensuelle « {champ} » attend 12 valeurs, une par mois '
            f'(reçu : {len(saisie)}). Une année incomplète se lirait comme '
            'une année complète.')
    valeurs, manquants, illisibles = [], [], []
    for rang, brut in enumerate(saisie):
        if brut is None or brut == '':
            manquants.append(MOIS_LIBELLES[rang])
            valeurs.append(None)
            continue
        nombre = _pourcentage(brut)
        if nombre is None:
            illisibles.append(MOIS_LIBELLES[rang])
            valeurs.append(None)
            continue
        valeurs.append(nombre)
    if manquants:
        return None, None, (
            'La saisie mensuelle de la salissure est incomplète : '
            f'{_liste(manquants)} sans valeur. Aucun mois n\'est comblé par '
            'la moyenne des autres.')
    if illisibles:
        return None, None, (
            'La saisie mensuelle de la salissure porte des valeurs '
            f'illisibles ou hors bornes : {_liste(illisibles)}. Un '
            'pourcentage se situe entre 0 et 100.')
    return valeurs, MODE_MENSUEL, ''


def _liste(mois):
    return ', '.join(f'« {nom} »' for nom in mois)


def _pourcentage(valeur):
    if isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre < 0 or nombre >= 100:
        return None
    return nombre


# ── l'application, heure par heure ─────────────────────────────────────

def _mois_absents(serie):
    """Y a-t-il une heure dont le mois n'est pas lisible ?"""
    for point in (serie or {}).get('points') or ():
        if not isinstance(point, dict):
            continue
        if _mois(point) is None:
            return True
    return False


def _mois(point):
    valeur = point.get('mois')
    if isinstance(valeur, bool):
        return None
    try:
        mois = int(valeur)
    except (TypeError, ValueError):
        return None
    return mois if 1 <= mois <= 12 else None


def _colonnes_touchees(serie):
    """Les colonnes que le facteur du mois multiplie réellement."""
    colonnes = []
    energie = _etapes.colonne_energie(serie)
    if energie is not None:
        colonnes.append(energie)
    points = (serie or {}).get('points') or []
    premier = points[0] if points and isinstance(points[0], dict) else {}
    for nom in (COLONNE_IRRADIANCE,) + COLONNES_COMPOSANTES:
        if nom in premier and nom not in colonnes:
            colonnes.append(nom)
    return colonnes


def _appliquer_par_mois(serie, valeurs):
    """Une COPIE de la série, chaque heure à son propre facteur de mois."""
    colonnes = _colonnes_touchees(serie)
    facteurs = [1.0 - valeur / 100.0 for valeur in valeurs]
    rendus = []
    for point in (serie or {}).get('points') or ():
        if not isinstance(point, dict):
            rendus.append(point)
            continue
        mois = _mois(point)
        copie = dict(point)
        facteur = facteurs[mois - 1]
        for nom in colonnes:
            brut = copie.get(nom)
            if brut is None or isinstance(brut, bool):
                continue
            try:
                copie[nom] = float(brut) * facteur
            except (TypeError, ValueError):
                continue
        rendus.append(copie)
    rendue = dict(serie)
    rendue['points'] = rendus
    energie = _etapes.colonne_energie(serie)
    if energie is not None:
        rendue['colonne_energie'] = energie
    return rendue
