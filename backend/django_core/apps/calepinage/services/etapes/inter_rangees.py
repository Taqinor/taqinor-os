# -*- coding: utf-8 -*-
"""CALX159 — étape « inter-rangées » : l'auto-ombrage des rangées, heure par heure.

CE QUE FAIT CETTE ÉTAPE
------------------------
Pour CHAQUE heure de la série, elle demande au noyau pur
(``core.calepinage.ombre_rangees.fraction_ombree``) quelle part de la table
aval est à l'ombre de la table amont, à la position du soleil de cette heure
(``core.calepinage.soleil.position_solaire``, CALX146), et elle retranche
cette part **de la seule composante DIRECTE** :

    facteur(h) = 1 − fraction_ombrée(h) × Gb(i)(h) / G(i)(h)

Une cellule ombrée reçoit encore le diffus et le réfléchi : c'est pourquoi
l'étape est OMISE quand PVGIS n'a pas rendu les composantes
(``pvgis_serie.MOTIF_COMPOSANTES_ABSENTES``, CALX152) — aucune répartition
n'est alors SUPPOSÉE.

CE QU'ELLE NE FAIT PAS
-----------------------
* **Aucun forfait, aucun coefficient** (D-CALX 7). Tout vient de la géométrie
  du document, de la position du soleil et des composantes de PVGIS. Une
  entrée absente OMET l'étape en nommant le champ à saisir.
* **Aucune perte électrique.** La fraction rendue est une part de SURFACE ;
  la dispersion I-V que l'ombre crée dans une chaîne est le poste
  ``mismatch_ombrage``, ailleurs dans ``ORDRE_ETAPES``. Rien n'est préjugé
  ici de ce poste.
* **Aucune exclusivité à gérer.** ``chaine_pertes.EXCLUSIVITES`` (D-CALX 16)
  écarte déjà cette étape quand l'accès solaire par module déclare couvrir
  l'ombre des rangées (``solarAccess.method.rangees``), exactement comme il
  écarte la matrice 12×24 quand ``solarAccess`` est présent : l'arbitrage
  appartient à l'ordonnanceur, jamais au module d'étape.

CE QUE L'ÉTAPE LIT, ET OÙ
--------------------------
Dans ``contexte`` (construit par ``services/simulation.py``, CALX5) :

* ``plans[]`` — un pan par entrée. Les champs de géométrie lus sont ceux de
  :data:`CHAMPS_GEOMETRIE` ; chacun est cherché d'abord sous son nom
  canonique de contexte, puis dans le sous-dict ``geometry`` (la forme brute
  de ``zones[].geometry`` du document ``roof_layout`` v2) et dans ``engine``
  (ce que le moteur a rendu pour une surface au sol, ``poseSurfaces[]``,
  CAL89 : c'est lui qui porte ``rowPitchM``).
* ``site.lat`` / ``site.lon`` — le point, pour la position du soleil.
* ``meteo.heure`` — la BASE horaire de la série et le décalage UTC appliqué
  (CALX143, renseignés par CALX59). PVGIS sert l'UTC par défaut et l'heure
  locale standard sous ``localtime=1`` : sans décalage publié, une série en
  heure locale ne peut pas être datée en UTC et l'étape s'OMET en nommant
  ``meteo.heure.decalage_minutes``. Dater le soleil à une heure fausse
  vaudrait jusqu'à 15° d'angle horaire par heure d'écart.

Un pan de MOINS DE DEUX RANGÉES n'a aucune rangée amont : sa fraction ombrée
vaut 0 pour toutes les heures. Ce 0 est CALCULÉ (il vient de
``nombre_rangees``), il n'est pas un défaut — et il explique pourquoi
``rowPitchM`` peut légitimement manquer sur un tel pan (le schéma v2 le dit :
« null quand le plan compte moins de deux rangées »).

PLUSIEURS PANS, UNE SEULE SÉRIE
---------------------------------
La chaîne s'applique à UNE série. Quand le contexte porte plusieurs pans, la
fraction horaire retenue est la moyenne des fractions de chaque pan,
PONDÉRÉE par sa puissance crête posée (``zones[].geometry.kwc``). Si un seul
pan manque de ``kwc``, aucune pondération n'est inventée : l'étape s'omet en
nommant le champ.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.calepinage.services import etapes
from apps.calepinage.services.pvgis_serie import MOTIF_COMPOSANTES_ABSENTES
from core.calepinage.ombre_rangees import (
    fraction_ombree, fraction_ombree_est_ouest)
from core.calepinage.soleil import position_solaire

__all__ = ['CHAMPS_GEOMETRIE', 'CHAMP_KWC', 'CHAMP_PAS', 'FAMILLE_EST_OUEST',
           'REFERENCE', 'SOURCE', 'appliquer']

#: Le nom de famille que le document donne à un châssis dos-à-dos
#: (``zones[].geometry.family``, schéma ``roof_layout`` v2).
FAMILLE_EST_OUEST = 'eastwest'

#: Les bases horaires que ``meteo.heure.base`` peut déclarer (CALX143).
BASE_UTC = 'utc'
BASE_LOCALE = 'locale_standard'

#: La géométrie lue sur chaque pan : ``(clé rendue, chemins essayés dans
#: l'ordre, nom du champ tel que l'écran doit le montrer)``. Les chemins vont
#: du nom canonique du contexte à la forme brute du document.
CHAMPS_GEOMETRIE = (
    ('inclinaison_deg',
     (('inclinaison_deg',), ('geometry', 'tiltDeg'), ('tiltDeg',)),
     'zones[].geometry.tiltDeg (inclinaison des tables)'),
    ('azimut_pvgis_deg',
     (('azimut_pvgis_deg',),),
     'plans[].azimut_pvgis_deg (azimut du plan, convention PVGIS)'),
    ('longueur_table_m',
     (('longueur_table_m',), ('geometry', 'panelSlopeLenM'),
      ('longueur_pente_m',)),
     'zones[].geometry.panelSlopeLenM (côté de table dans la pente)'),
)

#: Le pas de rangée : lu à part, parce qu'il est le SEUL champ qu'un pan à
#: rangée unique a le droit de ne pas porter.
CHEMINS_PAS = (('pas_rangee_m',), ('engine', 'rowPitchM'),
               ('geometry', 'rowPitchM'))
CHAMP_PAS = 'zones[].geometry.rowPitchM (pas entre rangées)'

#: Le nombre de rangées posées — il distingue « pan à rangée unique » de
#: « pas non renseigné ».
CHEMINS_RANGEES = (('nombre_rangees',), ('geometry', 'rowCount'),
                   ('engine', 'rowCount'))

#: La puissance crête posée du pan, seule pondération admise entre pans.
CHEMINS_KWC = (('kwc',), ('geometry', 'kwc'))
CHAMP_KWC = 'zones[].geometry.kwc (puissance crête posée du pan)'

#: La provenance publiée : la géométrie vient du document de calepinage, la
#: part directe de la réponse PVGIS.
SOURCE = 'layout+pvgis'

#: Ce que l'étape CITE — la relation employée et l'ordre de grandeur de
#: parité annoncé par le plan.
REFERENCE = (
    "Ombre de la rangée amont projetée dans le plan de profil : "
    "tan α_p = tan α / cos(γ_soleil − γ_plan), fraction ombrée "
    "(h − g·tan α_p) / (sin β + cos β·tan α_p) / L "
    "(core/calepinage/ombre_rangees.py). Ordre de grandeur de parité : "
    "PVsyst, « Backtracking strategy » — même avec backtracking les "
    "ombrages proches résiduels restent de l'ordre de 2 à 3 % "
    "(https://www.pvsyst.com/help/project-design/shadings/"
    "backtracking-strategy/index.html).")

#: L'hypothèse AJOUTÉE à la référence quand un châssis est-ouest ne dit pas
#: combien de modules regardent à l'est et combien à l'ouest.
HYPOTHESE_EST_OUEST = (
    " Châssis est-ouest sans face déclarée sur les modules "
    "(zones[].geometry.panels[].face) : les deux pans du chevron portent la "
    "même table, ils sont donc comptés à parts égales — l'hypothèse est "
    'ANNONCÉE, jamais silencieuse.')


def appliquer(serie, contexte):
    """``(serie, etape)`` — l'auto-ombrage inter-rangées, heure par heure."""
    contexte = contexte if isinstance(contexte, dict) else {}
    serie = serie if isinstance(serie, dict) else {}
    points = serie.get('points') or []

    geometries, champ = _geometries_des_plans(contexte)
    if champ:
        return serie, etapes.etape_omise('', _MOTIF_GEOMETRIE, champ=champ)
    if not points:
        return serie, etapes.etape_omise('', _MOTIF_SERIE_VIDE)
    if not _composantes_disponibles(serie, points):
        return serie, etapes.etape_omise('', MOTIF_COMPOSANTES_ABSENTES)

    site = contexte.get('site') or {}
    latitude = _nombre(site.get('lat'))
    longitude = _nombre(site.get('lon'))
    if latitude is None or longitude is None:
        return serie, etapes.etape_omise(
            '', _MOTIF_SITE,
            champ='site.lat / site.lon (point du calepinage)')

    decalages, champ = _decalages(contexte, len(points))
    if champ:
        return serie, etapes.etape_omise('', _MOTIF_HEURE, champ=champ)

    reference = REFERENCE
    if any(geometrie['hypothese_est_ouest'] for geometrie in geometries):
        reference += HYPOTHESE_EST_OUEST

    colonne = etapes.colonne_energie(serie)
    if colonne is None:
        # Aucune colonne d'énergie lisible : il n'y a rien à mettre à
        # l'échelle, et l'ordonnanceur publiera des null (jamais des 0).
        return serie, etapes.etape_appliquee(
            '', source=SOURCE, entree='zones[].geometry',
            reference=reference)

    suite = []
    for rang, point in enumerate(points):
        facteur = _facteur(point, geometries, latitude, longitude,
                           decalages[rang])
        valeur = point.get(colonne)
        if facteur >= 1.0 or valeur is None:
            suite.append(point)
            continue
        try:
            echelle = float(valeur) * facteur
        except (TypeError, ValueError):
            suite.append(point)
            continue
        copie = dict(point)
        copie[colonne] = echelle
        suite.append(copie)

    rendue = dict(serie)
    rendue['points'] = suite
    rendue['colonne_energie'] = colonne
    return rendue, etapes.etape_appliquee(
        '', source=SOURCE, entree='zones[].geometry', reference=reference)


# ── les motifs d'omission, chacun nommant ce qui manque ─────────────────

_MOTIF_GEOMETRIE = (
    "L'auto-ombrage entre rangées se calcule sur la GÉOMÉTRIE des rangées "
    'posées (pas, inclinaison, côté de table dans la pente) : elle est '
    "incomplète dans le document, et aucune ombre n'est supposée à sa "
    'place.')

_MOTIF_SERIE_VIDE = (
    "La série horaire ne porte aucun point : il n'y a aucune heure à "
    "laquelle projeter l'ombre d'une rangée sur la suivante.")

_MOTIF_SITE = (
    "Le point du site n'est pas connu : sans latitude ni longitude, la "
    "position du soleil n'est pas calculable, donc aucune ombre n'est "
    'projetée.')

_MOTIF_HEURE = (
    "L'heure de la série n'est pas datable en UTC : PVGIS sert l'UTC par "
    "défaut et l'heure LOCALE STANDARD sous « localtime=1 », et la base "
    'horaire ou le décalage réellement appliqué manque ici. Dater le soleil '
    "à une heure fausse vaudrait jusqu'à 15° d'angle horaire par heure "
    "d'écart — aucune ombre n'est projetée tant que le champ manque.")


# ── la géométrie des pans ───────────────────────────────────────────────

def _valeur(plan, chemins):
    """La première valeur trouvée parmi ``chemins``, ou ``None``."""
    for chemin in chemins:
        courant = plan
        for cle in chemin:
            if not isinstance(courant, dict):
                courant = None
                break
            courant = courant.get(cle)
        nombre = _nombre(courant)
        if nombre is not None:
            return nombre
    return None


def _texte(plan, chemins):
    """Le premier texte trouvé parmi ``chemins``, ou ``''``."""
    for chemin in chemins:
        courant = plan
        for cle in chemin:
            if not isinstance(courant, dict):
                courant = None
                break
            courant = courant.get(cle)
        if isinstance(courant, str) and courant.strip():
            return courant.strip()
    return ''


def _nombre(valeur):
    """Un flottant fini, ou ``None`` — un booléen n'est jamais un nombre."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre in (float('inf'), float('-inf')):
        return None
    return nombre


def _parts_est_ouest(plan):
    """``(part est, part ouest, hypothèse ?)`` d'un châssis dos-à-dos.

    Les faces réellement posées (``geometry.panels[].face``, schéma v2) font
    foi ; à défaut, les deux pans d'un chevron portent la même table et sont
    comptés à parts égales — l'hypothèse est alors ANNONCÉE.
    """
    geometrie = plan.get('geometry') if isinstance(plan, dict) else None
    panneaux = (geometrie or {}).get('panels') if isinstance(
        geometrie, dict) else None
    est = ouest = 0
    for panneau in panneaux or ():
        face = (panneau or {}).get('face') if isinstance(panneau, dict) else None
        if face == 'E':
            est += 1
        elif face == 'W':
            ouest += 1
    total = est + ouest
    if total:
        return est / total, ouest / total, False
    return 0.5, 0.5, True


def _geometries_des_plans(contexte):
    """``(liste de géométries, champ manquant)`` — jamais les deux remplis."""
    plans = [plan for plan in (contexte.get('plans') or ())
             if isinstance(plan, dict)]
    if not plans:
        return [], 'zones[].geometry (aucun pan exploitable)'

    geometries = []
    poids_manquant = False
    for plan in plans:
        lues = {}
        for cle, chemins, champ in CHAMPS_GEOMETRIE:
            valeur = _valeur(plan, chemins)
            if valeur is None:
                return [], champ
            lues[cle] = valeur

        rangees = _valeur(plan, CHEMINS_RANGEES)
        pas = _valeur(plan, CHEMINS_PAS)
        if pas is None:
            if rangees is None or rangees >= 2:
                return [], CHAMP_PAS
            # Moins de deux rangées : aucune rangée amont, donc aucune ombre
            # portée — et le pas n'existe pas, il n'est pas « manquant ».
            pas = 0.0
        lues['pas_rangee_m'] = pas
        lues['rangee_unique'] = rangees is not None and rangees < 2
        lues['est_ouest'] = (
            _texte(plan, (('famille',), ('geometry', 'family')))
            == FAMILLE_EST_OUEST)
        part_est, part_ouest, hypothese = _parts_est_ouest(plan)
        lues['part_est'] = part_est
        lues['part_ouest'] = part_ouest
        lues['hypothese_est_ouest'] = lues['est_ouest'] and hypothese
        poids = _valeur(plan, CHEMINS_KWC)
        if poids is None or poids <= 0.0:
            poids_manquant = True
        lues['poids'] = poids
        geometries.append(lues)

    if len(geometries) == 1:
        geometries[0]['poids'] = 1.0
        return geometries, ''
    if poids_manquant:
        return [], CHAMP_KWC
    total = sum(geometrie['poids'] for geometrie in geometries)
    for geometrie in geometries:
        geometrie['poids'] = geometrie['poids'] / total
    return geometries, ''


# ── la série : composantes, heure, facteur horaire ──────────────────────

def _composantes_disponibles(serie, points):
    """Le direct est-il séparé du diffus sur TOUS les points (CALX152) ?"""
    if serie.get('composantes_disponibles') is False:
        return False
    colonnes = serie.get('colonnes')
    if isinstance(colonnes, (list, tuple)) and 'gb_i_w_m2' not in colonnes:
        return False
    for point in points:
        if not isinstance(point, dict):
            return False
        if _nombre(point.get('gb_i_w_m2')) is None:
            return False
        if _nombre(point.get('gi_w_m2')) is None:
            return False
    return True


def _decalages(contexte, nombre_points):
    """``(décalages UTC en minutes, champ manquant)`` — jamais les deux."""
    heure = (contexte.get('meteo') or {}).get('heure') or {}
    base = str(heure.get('base') or '').strip().lower()
    if not base or base == BASE_UTC:
        # PVGIS sert l'UTC quand « localtime » n'est pas demandé : c'est son
        # défaut documenté, pas une hypothèse de notre part.
        return [0.0] * nombre_points, ''
    if base != BASE_LOCALE:
        return [], 'meteo.heure.base (base horaire de la série)'

    brut = heure.get('decalage_minutes')
    unique = _nombre(brut)
    if unique is not None:
        return [unique] * nombre_points, ''
    if isinstance(brut, (list, tuple)) and brut:
        valeurs = [_nombre(valeur) for valeur in brut]
        if None not in valeurs:
            if len(valeurs) == 1:
                return [valeurs[0]] * nombre_points, ''
            if len(valeurs) == nombre_points:
                return valeurs, ''
    return [], 'meteo.heure.decalage_minutes (décalage UTC appliqué)'


def _position(point, latitude, longitude, decalage_minutes):
    """La position du soleil à l'instant du point, ou ``None``."""
    annee = point.get('annee')
    mois = point.get('mois')
    jour = point.get('jour')
    heure = _nombre(point.get('heure'))
    if heure is None:
        return None
    try:
        moment = (datetime(int(annee), int(mois), int(jour),
                           tzinfo=timezone.utc)
                  + timedelta(hours=heure, minutes=-float(decalage_minutes)))
        return position_solaire(
            latitude, longitude, annee=moment.year, mois=moment.month,
            jour=moment.day,
            heure_utc=(moment.hour + moment.minute / 60.0
                       + moment.second / 3600.0))
    except (TypeError, ValueError):
        # Horodatage illisible : la série ressort intacte sur cette heure.
        # Aucune ombre n'est SUPPOSÉE faute de savoir quand on est.
        return None


def _part_directe(point):
    """``Gb(i) / G(i)`` de l'heure, borné à [0, 1]."""
    directe = _nombre(point.get('gb_i_w_m2'))
    globale = _nombre(point.get('gi_w_m2'))
    if directe is None or globale is None or globale <= 0.0:
        return 0.0
    return max(0.0, min(1.0, directe / globale))


def _fraction_du_plan(geometrie, position):
    """La fraction ombrée d'UN pan à cette position de soleil."""
    if geometrie['rangee_unique']:
        # Un pan d'une seule rangée n'a pas de rangée amont : 0 CALCULÉ.
        return 0.0
    if geometrie['est_ouest']:
        est, ouest = fraction_ombree_est_ouest(
            geometrie['pas_rangee_m'], geometrie['longueur_table_m'],
            geometrie['inclinaison_deg'], position.elevation_deg,
            position.azimut_depuis_sud_deg)
        return geometrie['part_est'] * est + geometrie['part_ouest'] * ouest
    return fraction_ombree(
        geometrie['pas_rangee_m'], geometrie['longueur_table_m'],
        geometrie['inclinaison_deg'], geometrie['azimut_pvgis_deg'],
        position.elevation_deg, position.azimut_depuis_sud_deg)


def _facteur(point, geometries, latitude, longitude, decalage_minutes):
    """``1 − fraction ombrée × part directe`` pour cette heure."""
    part = _part_directe(point)
    if part <= 0.0:
        return 1.0
    position = _position(point, latitude, longitude, decalage_minutes)
    if position is None or position.elevation_deg <= 0.0:
        return 1.0
    fraction = sum(geometrie['poids'] * _fraction_du_plan(geometrie, position)
                   for geometrie in geometries)
    if fraction <= 0.0:
        return 1.0
    return max(0.0, 1.0 - fraction * part)
