"""L-ECO — LE MOIS DE RAMADAN, CÔTÉ MOTEUR (fenêtre CALCULÉE par date).

Jusqu'ici le Ramadan n'existait QUE côté page :

* ``apps/web/src/lib/dayProfiles.ts`` porte la table des plages, le calcul
  solaire NOAA et la fenêtre imsak/iftar ;
* le serveur, lui, se contentait de le DIRE dans
  ``courbes_journalieres.NOTE_HORAIRE`` sans jamais l'intégrer dans les
  économies.

Or c'est le MOTEUR qui chiffre l'argent : une consommation décalée d'une heure
pendant un mois entier ne croise pas la même production. Ce module porte donc
en Python EXACTEMENT ce que la page calcule déjà, avec les MÊMES valeurs et les
MÊMES sources citées — aucun chiffre nouveau n'est introduit ici.

CE QUI EST RECOPIÉ VERBATIM DE ``dayProfiles.ts`` (avec sa provenance) :
  * :data:`RAMADAN_PLAGES` — les plages grégoriennes 2025→2033 ;
  * :data:`FAJR_AVANT_LEVER_MIN` — l'approximation de l'imsak ;
  * :func:`heures_soleil` — l'algorithme NOAA du lever/coucher ;
  * :data:`DEFAUT_LAT` / :data:`DEFAUT_LON` — le repli Casablanca.

CE QUI EST PROPRE AU MOTEUR, ET POURQUOI :
  * :func:`part_ramadan_par_mois` — le moteur travaille sur des JOURS TYPES
    mensuels ; il lui faut donc savoir quelle PART de chaque mois tombe dans le
    Ramadan. C'est de l'arithmétique de calendrier sur la table ci-dessus, pas
    une hypothèse de comportement.

CE QUE CE MODULE MODÉLISE — ET CE QU'IL NE MODÉLISE PLUS (20/09/2026)
--------------------------------------------------------------------
Il modélise les **HABITUDES** du mois : on ne consomme pas aux mêmes heures
quand on jeûne (suhoor avant l'aube, rupture au coucher du soleil, veille plus
tardive). C'est du MÉTIER, et le décret n'y change rien : ces heures sortent du
calcul solaire NOAA au point GPS du chantier, à la date réelle du mois.

Il ne modélise PLUS un décalage d'**HORLOGE**. Jusqu'au 19/09/2026, le Maroc
vivait à UTC+1 et repassait à UTC+0 pendant le Ramadan : ce module portait donc
deux constantes (``RAMADAN_FUSEAU_UTC`` = 0 et
``DECALAGE_FUSEAU_VERS_CIVIL_H`` = +1 h) pour ramener un iftar lu sur
« l'horloge du Ramadan » vers le repère civil ordinaire du moteur. Le décret
n° 2.26.530 relatif à l'heure légale (Bulletin officiel n° 7521 du 29/06/2026),
qui abroge le décret 2.18.855 de 2018, a supprimé CETTE bascule : depuis le
20/09/2026 il n'y a plus qu'une seule horloge, UTC+0 toute l'année. Les deux
constantes sont donc retirées, et le lever/coucher est calculé DIRECTEMENT dans
le décalage civil du jour de référence — lu dans la base de fuseaux par
``apps.parametres.pvgis_profils.decalage_maroc_h``, jamais écrit ici. La
fenêtre sort ainsi du même repère que la production PVGIS, par construction et
quelle que soit la loi en vigueur à la date calculée.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from apps.parametres.pvgis_profils import JOURS_PAR_MOIS, decalage_maroc_h

# ── Table des plages, recopiée VERBATIM de dayProfiles.RAMADAN_RANGES ────────
# « Plages grégoriennes du mois de Ramadan, 2025 → 2033 (hégire 1446 → 1455).
#   Ce sont des ESTIMATIONS ASTRONOMIQUES publiées, relevées le 21/08/2026 sur
#   aladhan.com (`aladhan.com/ramadan-calendar/<année>` et le calendrier
#   hijri-grégorien 9/1455) et recoupées avec sajda.com : le Maroc confirme le
#   premier jour par OBSERVATION LUNAIRE (annonce du ministère des Habous la
#   veille), donc chaque borne peut bouger de ±1 jour. »
#
# Cette incertitude de ±1 jour est SANS EFFET sur une économie mensuelle : elle
# déplace au plus un trentième de la pondération d'un mois.
RAMADAN_PLAGES = (
    {'hijri': 1446, 'debut': date(2025, 3, 1), 'fin': date(2025, 3, 29)},
    {'hijri': 1447, 'debut': date(2026, 2, 18), 'fin': date(2026, 3, 19)},
    {'hijri': 1448, 'debut': date(2027, 2, 8), 'fin': date(2027, 3, 8)},
    {'hijri': 1449, 'debut': date(2028, 1, 28), 'fin': date(2028, 2, 25)},
    {'hijri': 1450, 'debut': date(2029, 1, 16), 'fin': date(2029, 2, 13)},
    {'hijri': 1451, 'debut': date(2030, 1, 5), 'fin': date(2030, 2, 3)},
    {'hijri': 1452, 'debut': date(2030, 12, 26), 'fin': date(2031, 1, 23)},
    {'hijri': 1453, 'debut': date(2031, 12, 15), 'fin': date(2032, 1, 13)},
    {'hijri': 1454, 'debut': date(2032, 12, 4), 'fin': date(2033, 1, 1)},
    {'hijri': 1455, 'debut': date(2033, 11, 23), 'fin': date(2033, 12, 22)},
)

#: Approximation assumée de l'imsak : lever du soleil MOINS 80 minutes. « Le
#: fajr vrai est l'aube astronomique (dépression solaire de 18° pour la
#: convention de la Ligue islamique mondiale, 19° pour d'autres) ; l'écart
#: lever↔aube varie de ~70 à ~95 min sous nos latitudes selon la saison. On
#: retient 80 min, valeur médiane, et on l'ÉTIQUETTE. »
FAJR_AVANT_LEVER_MIN = 80

#: Repli quand le chantier n'a ni GPS ni ville reconnue — Casablanca.
DEFAUT_LAT = 33.57
DEFAUT_LON = -7.59

_DEG = math.pi / 180.0


def _mod360(x):
    return ((x % 360.0) + 360.0) % 360.0


def _jour_julien_midi(annee, mois, jour):
    """Jour julien à 12 h TU du jour civil donné (algorithme grégorien standard)."""
    y, m = annee, mois
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + jour + b - 1524.5 + 0.5)


def heures_soleil(jour, lat, lon, decalage_h):
    """``(lever_min, coucher_min)`` en minutes depuis minuit, ou ``None``.

    Algorithme NOAA (« NOAA Solar Calculator », gml.noaa.gov/grad/solcalc/), la
    même chaîne équation-du-temps + déclinaison que la feuille de référence.
    Zénith 90,833° = centre du disque + réfraction atmosphérique moyenne,
    convention NOAA du lever/coucher. C'est de l'ASTRONOMIE, pas une mesure :
    reproductible, sans réseau, précis à la minute près sous nos latitudes.
    ``lon`` est positif vers l'EST (le Maroc est donc négatif). Nuit/jour
    polaire (jamais au Maroc) ⇒ ``None``.

    Port fidèle de ``dayProfiles.sunTimes``.
    """
    try:
        lat = float(lat)
        lon = float(lon)
        decalage_h = float(decalage_h)
    except (TypeError, ValueError):
        return None
    if not isinstance(jour, date):
        return None

    jd = _jour_julien_midi(jour.year, jour.month, jour.day)
    t = (jd - 2451545.0) / 36525.0

    l0 = _mod360(280.46646 + t * (36000.76983 + t * 0.0003032))
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = (math.sin(m * _DEG) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * m * _DEG) * (0.019993 - 0.000101 * t)
         + math.sin(3 * m * _DEG) * 0.000289)
    long_vraie = l0 + c
    omega = 125.04 - 1934.136 * t
    lambda_ = long_vraie - 0.00569 - 0.00478 * math.sin(omega * _DEG)
    secondes = 21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))
    eps0 = 23 + (26 + secondes / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(omega * _DEG)
    decl = math.asin(math.sin(eps * _DEG) * math.sin(lambda_ * _DEG)) / _DEG

    y_tan = math.tan((eps * _DEG) / 2.0) ** 2
    eq_temps = (4.0 * (
        y_tan * math.sin(2 * l0 * _DEG)
        - 2 * e * math.sin(m * _DEG)
        + 4 * e * y_tan * math.sin(m * _DEG) * math.cos(2 * l0 * _DEG)
        - 0.5 * y_tan * y_tan * math.sin(4 * l0 * _DEG)
        - 1.25 * e * e * math.sin(2 * m * _DEG)
    )) / _DEG

    zenith = 90.833
    denom = math.cos(lat * _DEG) * math.cos(decl * _DEG)
    if denom == 0:
        return None
    cos_h = (math.cos(zenith * _DEG) / denom
             - math.tan(lat * _DEG) * math.tan(decl * _DEG))
    if cos_h > 1 or cos_h < -1:
        return None
    angle_horaire = math.acos(cos_h) / _DEG

    midi_solaire_min = 720.0 - 4.0 * lon - eq_temps + decalage_h * 60.0
    return (midi_solaire_min - 4.0 * angle_horaire,
            midi_solaire_min + 4.0 * angle_horaire)


def plage_ramadan_pour(jour):
    """``(plage, dedans)`` — celle qui CONTIENT ``jour``, sinon la PROCHAINE.

    Au-delà de la table (après 2033) ⇒ ``None`` : on préfère ne rien affirmer.
    Même règle que ``dayProfiles.ramadanRangeFor``.
    """
    if not isinstance(jour, date):
        return None
    for plage in RAMADAN_PLAGES:
        if plage['debut'] <= jour <= plage['fin']:
            return plage, True
        if jour < plage['debut']:
            return plage, False
    return None


def fenetre_ramadan(jour, lat=None, lon=None):
    """Fenêtre du Ramadan DANS LE REPÈRE DU MOTEUR (l'heure civile marocaine).

    Renvoie ``{'imsak_h', 'iftar_h', 'jour_reference', 'hijri', 'dedans'}`` en
    heures décimales, ou ``None`` hors table / calcul impossible.

    * IFTAR = coucher du soleil NOAA, exact (c'est la définition) ;
    * IMSAK = lever du soleil moins :data:`FAJR_AVANT_LEVER_MIN`, approximation
      assumée et étiquetée ;
    * les deux sont calculés DIRECTEMENT dans le décalage civil du jour de
      référence (``decalage_maroc_h``), donc dans le même repère que les formes
      de production PVGIS — aucune conversion d'horloge en plus. Il n'y a plus
      d'« horloge du Ramadan » distincte depuis le 20/09/2026 (décret
      n° 2.26.530) ; voir l'en-tête du module.

    Jour de référence : le jour même s'il tombe dans le Ramadan, sinon le jour
    MÉDIAN de la plage (représentatif du mois plutôt qu'une borne extrême) —
    même choix que ``dayProfiles.ramadanWindow``.
    """
    trouve = plage_ramadan_pour(jour)
    if trouve is None:
        return None
    plage, dedans = trouve
    if dedans:
        reference = jour
    else:
        milieu = (plage['fin'] - plage['debut']).days // 2
        reference = plage['debut'] + timedelta(days=milieu)

    lat_eff = DEFAUT_LAT if lat is None else lat
    lon_eff = DEFAUT_LON if lon is None else lon
    try:
        lat_eff = float(lat_eff)
        lon_eff = float(lon_eff)
    except (TypeError, ValueError):
        lat_eff, lon_eff = DEFAUT_LAT, DEFAUT_LON
    if not (math.isfinite(lat_eff) and math.isfinite(lon_eff)):
        lat_eff, lon_eff = DEFAUT_LAT, DEFAUT_LON

    soleil = heures_soleil(reference, lat_eff, lon_eff,
                           decalage_maroc_h(reference))
    if soleil is None:
        return None
    lever_min, coucher_min = soleil
    return {
        'imsak_h': (lever_min - FAJR_AVANT_LEVER_MIN) / 60.0,
        'iftar_h': coucher_min / 60.0,
        'jour_reference': reference.isoformat(),
        'hijri': plage['hijri'],
        'dedans': dedans,
    }


def part_ramadan_par_mois(jour):
    """12 parts (index 0 = janvier) du mois passées en Ramadan, ou ``None``.

    Le moteur ne connaît que des JOURS TYPES mensuels : la journée type d'un
    mois à moitié en Ramadan est la moyenne pondérée d'une journée de jeûne et
    d'une journée ordinaire. Cette fonction rend ce poids-là, et rien d'autre.

    La plage retenue est celle de :func:`plage_ramadan_pour` (celle qui
    contient ``jour``, sinon la prochaine à venir) : le devis chiffre le
    Ramadan que le client va VIVRE, pas un Ramadan moyen. Le mois recule
    d'environ 11 jours par an, il peut donc chevaucher deux mois grégoriens —
    d'où douze parts et non un mois unique.

    Le dénominateur est :data:`JOURS_PAR_MOIS` (année non bissextile), la MÊME
    convention que le reste du moteur : deux découpages différents feraient
    diverger la part et le nombre de jours qui la valorise.
    """
    trouve = plage_ramadan_pour(jour)
    if trouve is None:
        return None
    plage, _dedans = trouve
    parts = [0.0] * 12
    courant = plage['debut']
    while courant <= plage['fin']:
        index = courant.month - 1
        parts[index] += 1.0
        courant += timedelta(days=1)
    for index in range(12):
        jours = JOURS_PAR_MOIS[index]
        parts[index] = min(1.0, parts[index] / jours) if jours else 0.0
    return parts
