"""ACAL454 — un fichier météo HORIZONTAL (EPW ou CSV) lu en une série nommée.

``services/meteo_fichier.py::lire_serie_meteo`` n'accepte que l'irradiance sur le
PLAN des modules (``gi_w_m2``) et refuse tout fichier horizontal. Ce lecteur est
l'autre porte : il lit un fichier qui part de l'HORIZONTAL (PVsyst part de
l'horizontal ; HelioScope charge un fichier météo par Condition Set) et rend la
série telle que le fichier la porte — il n'invente aucun plan : la transposition
reste l'affaire du moteur.

Deux formats :

* **EPW** — 8 lignes d'en-tête (la ligne 1 est ``LOCATION`` et porte le FUSEAU,
  en heures depuis UTC), puis une ligne par heure. Dictionnaire de données EPW :
  l'heure va de 1 à 24 et désigne la FIN de l'intervalle ; l'indice ``heure``
  rendu est donc ``heure EPW - 1``. Colonnes lues (rang 0) : 13 GHI, 14 DNI,
  15 DHI (Wh/m2, 9999 = manquant), 6 température sèche (99.9 = manquant),
  21 vitesse du vent (999 = manquant).
* **CSV** — colonnes nommées ``horodatage`` (ISO 8601 avec fuseau explicite, la
  règle de ``meteo_fichier``), ``ghi_w_m2``, ``dni_w_m2``, ``dhi_w_m2``, puis
  ``t2m_c`` et ``ws10m`` facultatives.

Une valeur de rayonnement manquante REFUSE le fichier en nommant ligne et
colonne ; température et vent manquants restent ``None`` (« non publié »).
Un fichier d'année type (mois de plusieurs années, chacun sur ses jours) est
vérifié mois par mois et publié ``mode: 'tmy'`` avec ``annees: []``, comme
``ClientPvgis.tmy``.

Une seule règle de fuseau et de calendrier : les lecteurs privés de
``meteo_fichier`` sont réemployés. ``pvlib.iotools`` n'est JAMAIS importé ici
(mémo ``docs/decisions/calx198-pvlib.md`` §2) : il sert de référence dans le test.
Lecture pure : rien n'est écrit, aucune route n'est touchée.
"""
from __future__ import annotations

import datetime

from .meteo_fichier import (
    COLONNE_HORODATAGE,
    LIGNES_MAX,
    MeteoFichierRefuse,
    _bloc_meteo_fichier,
    _cellule_numerique,
    _entete,
    _instant,
    _lignes_utiles,
    _octets,
    _texte,
    _verifier_calendrier,
)

__all__ = ['COLONNES_HORIZONTALES_REQUISES', 'lire_serie_horizontale']

#: Les trois colonnes de rayonnement du CSV horizontal, toutes obligatoires.
COLONNES_HORIZONTALES_REQUISES = ('ghi_w_m2', 'dni_w_m2', 'dhi_w_m2')

# Dictionnaire de données EPW — rang (à partir de 0) des colonnes lues.
_EPW_ENTETE_LIGNES = 8
_EPW_COLONNES = {
    'annee': 0, 'mois': 1, 'jour': 2, 'heure': 3,
    't2m_c': 6, 'ghi_w_m2': 13, 'dni_w_m2': 14, 'dhi_w_m2': 15,
    'ws10m': 21,
}
_EPW_MANQUANT = {'t2m_c': 99.9, 'ghi_w_m2': 9999.0, 'dni_w_m2': 9999.0,
                 'dhi_w_m2': 9999.0, 'ws10m': 999.0}


def _fuseau_epw(ligne1):
    """Le fuseau (heures) de la ligne LOCATION — ou un refus nommant la ligne 1."""
    cases = [case.strip() for case in ligne1.split(',')]
    if not cases or cases[0].upper() != 'LOCATION' or len(cases) < 9:
        raise MeteoFichierRefuse(
            'La ligne 1 du fichier EPW doit être « LOCATION » avec son fuseau '
            '(9e champ) : sans fuseau, une heure se décale en silence.',
            champ='LOCATION', ligne=1)
    try:
        return datetime.timezone(
            datetime.timedelta(hours=float(cases[8].replace(',', '.'))))
    except (ValueError, OverflowError):
        raise MeteoFichierRefuse(
            'Le fuseau de la ligne 1 (« {0} ») n\'est pas un nombre d\'heures '
            'depuis UTC.'.format(cases[8]), champ='LOCATION', ligne=1)


def _valeur_epw(cases, nom, rang):
    """Une cellule EPW : nombre, ``None`` (temp./vent manquants) ou refus."""
    brut = cases[_EPW_COLONNES[nom]] if _EPW_COLONNES[nom] < len(cases) else ''
    valeur = _cellule_numerique(
        brut, colonne=nom, ligne=rang, obligatoire=nom in COLONNES_HORIZONTALES_REQUISES)
    if valeur is not None and valeur == _EPW_MANQUANT[nom]:
        if nom in COLONNES_HORIZONTALES_REQUISES:
            raise MeteoFichierRefuse(
                'La colonne « {0} » porte le code « manquant » EPW ({1:g}) à la '
                'ligne {2} : une heure sans rayonnement laisserait un trou dans '
                'la série.'.format(nom, valeur, rang), champ=nom, ligne=rang)
        return None
    return valeur


def _points_epw(lignes, fuseau):
    points, moments = [], []
    for rang, ligne in lignes:
        if rang <= _EPW_ENTETE_LIGNES:
            continue
        cases = ligne.split(',')
        try:
            annee, mois, jour, heure = (int(float(cases[_EPW_COLONNES[cle]]))
                                        for cle in ('annee', 'mois', 'jour', 'heure'))
            moment = datetime.datetime(annee, mois, jour, tzinfo=fuseau) \
                + datetime.timedelta(hours=heure - 1)
        except (ValueError, IndexError, OverflowError):
            raise MeteoFichierRefuse(
                'La ligne {0} du fichier EPW n\'a pas une date et une heure '
                'lisibles (colonnes année, mois, jour, heure).'.format(rang),
                champ=COLONNE_HORODATAGE, ligne=rang)
        point = {'annee': moment.year, 'mois': moment.month, 'jour': moment.day,
                 'heure': heure - 1}
        for nom in ('ghi_w_m2', 'dni_w_m2', 'dhi_w_m2', 't2m_c', 'ws10m'):
            point[nom] = _valeur_epw(cases, nom, rang)
        points.append(point)
        moments.append((rang, moment))
    return points, moments


def _points_csv(lignes, rang_entete, separateur, titres):
    # ACAL456 — le global SEUL (ni dni ni dhi) est admis : les composantes sont
    # alors déduites plus tard (``decomposition.py``) ; une seule des deux
    # colonnes reste refusée.
    seul = 'ghi_w_m2' in titres and not {'dni_w_m2', 'dhi_w_m2'} & set(titres)
    for colonne in COLONNES_HORIZONTALES_REQUISES:
        if colonne not in titres and not (seul and colonne != 'ghi_w_m2'):
            raise MeteoFichierRefuse(
                'Aucune colonne « {0} » dans ce fichier horizontal : donnez '
                'dni_w_m2 ET dhi_w_m2, ou ni l\'un ni l\'autre (le global seul '
                'est décomposé par le modèle saisi) — aucune composante n\'est '
                'supposée à sa place.'.format(colonne),
                champ=colonne, ligne=rang_entete)
    points, moments = [], []
    for rang, ligne in lignes:
        if rang <= rang_entete:
            continue
        cases = ligne.split(separateur)
        lue = {titre: (cases[i] if i < len(cases) else '')
               for i, titre in enumerate(titres)}
        moment = _instant(lue.get(COLONNE_HORODATAGE), ligne=rang)
        point = {'annee': moment.year, 'mois': moment.month, 'jour': moment.day,
                 'heure': moment.hour}
        for nom in COLONNES_HORIZONTALES_REQUISES:
            if seul and nom != 'ghi_w_m2':
                point[nom] = None
                continue
            point[nom] = _cellule_numerique(lue.get(nom), colonne=nom,
                                            ligne=rang, obligatoire=True)
        for nom in ('t2m_c', 'ws10m'):
            point[nom] = (_cellule_numerique(lue.get(nom), colonne=nom, ligne=rang)
                          if nom in titres else None)
        points.append(point)
        moments.append((rang, moment))
    return points, moments


def _mode_et_calendrier(moments):
    """``'tmy'`` si les mois viennent d'années différentes, sinon ``None``.

    Le calendrier d'abord continu ; à défaut, vérifié MOIS PAR MOIS et admis
    seulement pour une année type (chaque mois une fois, années différentes).
    """
    try:
        _verifier_calendrier(moments)
        return None
    except MeteoFichierRefuse as refus:
        par_mois = {}
        for ligne, moment in moments:
            par_mois.setdefault((moment.year, moment.month), []).append(
                (ligne, moment))
        mois = [cle[1] for cle in par_mois]
        annees = {cle[0] for cle in par_mois}
        if len(mois) != len(set(mois)) or len(annees) < 2:
            raise refus
        for groupe in par_mois.values():
            _verifier_calendrier(groupe)
        return 'tmy'


def lire_serie_horizontale(fichier, *, format, fournisseur='', nom_fichier='',
                           obtenue_le=None):
    """La série HORIZONTALE d'un fichier EPW ou CSV, nommée et sourcée.

    Returns:
        dict — ``service`` (``'fichier'``), ``plan_des_donnees``
        (``'horizontal'``), ``points`` (``annee, mois, jour, heure, ghi_w_m2,
        dni_w_m2, dhi_w_m2, t2m_c, ws10m``), ``mode``, ``annees`` et ``meteo``
        (``composantes_origine``). ACAL456 : un CSV au global seul rend
        ``dni_w_m2``/``dhi_w_m2`` à ``None`` et ``a_decomposer: True``.

    Raises:
        MeteoFichierRefuse: format inconnu, fuseau absent (ligne 1), valeur de
            rayonnement manquante ou colonne absente (ligne et colonne nommées),
            calendrier troué, en doublon ou désordonné.
    """
    if format not in ('epw', 'csv'):
        raise MeteoFichierRefuse(
            'Format météo inconnu « {0} » : attendu « epw » ou « csv ».'.format(
                format), champ='format')
    contenu = _octets(fichier)
    lignes = _lignes_utiles(_texte(contenu))
    if format == 'epw':
        if not lignes or lignes[0][0] != 1:
            raise MeteoFichierRefuse(
                'La ligne 1 du fichier EPW est absente ou vide (LOCATION et '
                'fuseau attendus).', champ='LOCATION', ligne=1)
        points, moments = _points_epw(lignes, _fuseau_epw(lignes[0][1]))
    else:
        separateur, titres, rang_entete = _entete(lignes)
        points, moments = _points_csv(lignes, rang_entete, separateur, titres)
    if not points:
        raise MeteoFichierRefuse(
            'Ce fichier ne porte aucune heure de mesure à lire.', champ='fichier')
    if len(points) > LIGNES_MAX:
        raise MeteoFichierRefuse(
            'Ce fichier porte {0} lignes de mesure, au-delà des {1} admises.'
            .format(len(points), LIGNES_MAX), champ='fichier')
    mode = _mode_et_calendrier(moments)
    annees = [] if mode == 'tmy' else sorted({p['annee'] for p in points})
    decalages = sorted({int(m.utcoffset().total_seconds() // 60)
                        for _, m in moments})
    horodatage = obtenue_le or datetime.datetime.now(
        datetime.timezone.utc).replace(microsecond=0).isoformat()
    meteo = _bloc_meteo_fichier(
        fournisseur=fournisseur, nom_fichier=nom_fichier, contenu=contenu,
        lignes_lues=len(points), annees=annees, decalages=decalages,
        obtenue_le=horodatage)
    meteo['mode'] = mode
    a_decomposer = points[0]['dni_w_m2'] is None
    meteo['composantes_origine'] = 'deduites' if a_decomposer else 'mesurees'
    return {'service': 'fichier', 'plan_des_donnees': 'horizontal',
            'points': points, 'mode': mode, 'annees': annees, 'meteo': meteo,
            'a_decomposer': a_decomposer, 'url': None, 'depuis_cache': False}
