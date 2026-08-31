"""Profils PVGIS journaliers + productible mensuel — SOURCE UNIQUE des courbes.

Pourquoi ce module
------------------
La page proposition dessine deux courbes 24 h (production / consommation) par
saison. Avant ce module, la forme de production était une cloche SYNTHÉTIQUE
côté client et le « pic » affiché en kWh alors que c'est une PUISSANCE (kW).
Ici, le serveur devient propriétaire de la donnée : les formes horaires et le
productible mensuel viennent de PVGIS, jamais d'une courbe inventée.

Provenance des constantes (RÈGLE « zéro chiffre inventé »)
---------------------------------------------------------
Données relevées EN DIRECT sur PVGIS 5.3 (Commission européenne, JRC) — 13
villes le 21/08/2026, 19 villes de plus le 31/08/2026 (mêmes appels, mêmes
paramètres figés), soit 32 villes marocaines, avec EXACTEMENT ces deux appels
par ville :

* productible mensuel (``E_m``, kWh/kWc/mois) — ``PVcalc`` ::

    https://re.jrc.ec.europa.eu/api/v5_3/PVcalc?lat={lat}&lon={lon}
        &peakpower=1&loss=14&pvtechchoice=crystSi&outputformat=json
        &angle=30&aspect=0&mountingplace=free

* forme horaire du jour moyen du mois (``G(i)``, W/m²) — ``DRcalc``, mois
  1 / 4 / 7 ::

    https://re.jrc.ec.europa.eu/api/v5_3/DRcalc?lat={lat}&lon={lon}
        &month={1|4|7}&angle=30&aspect=0&global=1&outputformat=json

``COURBES_REFERENCE`` stocke la forme horaire NORMALISÉE (part de l'énergie
journalière par heure) et ``PRODUCTIBLE_MENSUEL_VILLE`` les 12 ``E_m`` par
ville — recopiés VERBATIM de ces réponses, jamais retouchés à la main.

Regroupement des 32 villes en 10 courbes de référence
-----------------------------------------------------
Les formes horaires de villes proches sont quasi identiques : on garde donc
UNE courbe par groupe, prise VERBATIM sur une ville d'ANCRAGE (jamais une
moyenne — une moyenne serait une courbe qui n'existe nulle part). Écart
maximal MESURÉ entre l'ancrage et les autres villes du groupe, sur les 3
saisons × 24 h (en points de fraction) :

===================  ===========  =========================================
groupe               ancrage      écart max mesuré
===================  ===========  =========================================
``casa_atlantique``  Casablanca   0.005 (El Jadida, janvier) ; ajouts du
                                  31/08 : Kénitra 0.0043, Bouznika 0.0021,
                                  Settat 0.0043
``tanger``           Tanger       ajouts : Taza 0.013, Al Hoceima 0.013,
                                  Larache 0.0071
``fes_oujda``        Fès          0.013 (Oujda) ; ajouts : Meknès 0.004,
                                  Nador 0.010, Errachidia 0.0051
``marrakech``        Marrakech    ajouts : Khouribga 0.005, Tiznit 0.0071,
                                  Taroudant 0.0069
``agadir``           Agadir       ajouts : Safi 0.012, Essaouira 0.008,
                                  Guelmim 0.005
``ouarzazate``       Ouarzazate   ajout : Ifrane 0.006
``sud_atlantique``   Laâyoune     0.015 (Dakhla, janvier)
``beni_mellal``      Béni Mellal  — (0.0192 vs tout groupe existant → sa
                                  propre courbe)
``tetouan_detroit``  Tétouan      — (0.0209 → sa propre courbe)
``tan_tan``          Tan-Tan      — (0.0152 → sa propre courbe)
===================  ===========  =========================================

Le productible ``E_m``, lui, reste PAR VILLE (32 jeux distincts) : c'est le
niveau d'énergie, il varie franchement d'une ville à l'autre (E_y de 1585,89
à Tétouan jusqu'à 1927,71 kWh/kWc/an à Dakhla).

Villes HORS table — gazetier + ancre la plus proche (fondateur, 31/08/2026)
---------------------------------------------------------------------------
Une ville marocaine absente de la table (« Bouznika » avant le 31/08 : le
devis automatique refusait, Rabat passait) n'est PLUS omise : le gazetier
GeoNames (``villes_maroc.py``, ~300 villes + orthographes, coordonnées
VERBATIM) donne sa position, et la chaîne sert alors les données PVGIS
RÉELLES de l'ancre de table LA PLUS PROCHE, la source NOMMANT l'ancre et la
distance (``pvgis_ville_proche:<ancre>~<km>km``). Ordre fondateur du
31/08/2026 — il amende la moitié « on omet » de Q6 pour les villes du
gazetier ; le reste de Q6 tient : jamais un chiffre inventé (la donnée servie
est la table PVGIS d'une vraie ville voisine, traçable), et un texte sans
aucune ville reconnue ni GPS reste ``None``.

Convention horaire — À LIRE AVANT DE CONSOMMER
-----------------------------------------------
PVGIS renvoie ses profils journaliers en **UTC**. Les formes stockées ici sont
donc en UTC, indice 0 = 00 h UTC. L'heure civile marocaine est **UTC+1 toute
l'année**, SAUF pendant le Ramadan où le pays repasse à **UTC+0**. Le décalage
est l'affaire du CONSOMMATEUR, pas du stockage : appeler
:func:`vers_heure_locale` pour obtenir la forme en heure civile marocaine
(UTC+1). Le cas Ramadan (UTC+0 = la forme brute, sans décalage) n'est PAS
modélisé ici — c'est une note d'affichage à porter côté page, pas un second
jeu de données.

Le module est PUR pour tout ce qui touche à la table de référence (aucun accès
DB, aucun I/O) ; seuls les chemins « live » font un appel réseau, avec le même
garde-fou que ``apps/parametres/pvgis.py`` (stdlib ``urllib``, timeout court,
repli silencieux) et le même cache SYSTÈME que PV73 (``core.cache`` avec
``company=None`` : la physique d'un point GPS n'appartient à aucun tenant).
"""
from __future__ import annotations

import json
import logging
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# ── Endpoints PVGIS (v5.3 — la version RELEVÉE le 21/08/2026, cf. docstring) ──
PVGIS_API_BASE = 'https://re.jrc.ec.europa.eu/api/v5_3'
PVGIS_DRCALC = PVGIS_API_BASE + '/DRcalc'
PVGIS_PVCALC = PVGIS_API_BASE + '/PVcalc'

# Timeout réseau COURT : on ne bloque JAMAIS l'affichage d'une proposition sur
# PVGIS (même politique que apps/parametres/pvgis.py).
PVGIS_TIMEOUT_S = 6

# Paramètres FIGÉS des appels live — identiques à ceux qui ont produit la table
# de référence, sinon « live » et « référence » ne seraient pas comparables.
PVGIS_ANGLE_DEG = 30      # inclinaison modules (°)
PVGIS_ASPECT_DEG = 0      # azimut : 0 = plein Sud (convention PVGIS = maison)
PVGIS_LOSS_PCT = 14       # pertes système PVGIS usuelles
PVGIS_PVTECH = 'crystSi'
PVGIS_MOUNTING = 'free'

# TTL du cache SYSTÈME (core.cache, company=None — comme PV73). Un profil
# DRcalc est une MOYENNE climatologique du jour moyen d'un mois : il ne bouge
# pas d'un jour à l'autre, d'où un TTL bien plus long que le productible
# ponctuel de PV73 (6 h) — 30 jours.
CACHE_TTL_S = 30 * 24 * 60 * 60

# Coupe-circuit : clé + durée du drapeau « PVGIS est en panne ». Posé au
# premier échec réseau, il évite d'infliger un timeout par appel restant à une
# page client (cf. :func:`_appel_pvgis`).
PANNE_CLE = 'pvgis:panne'
PANNE_TTL_S = 5 * 60

# ── Saisons ──────────────────────────────────────────────────────────────────
# Trois saisons, chacune ancrée sur le mois PVGIS effectivement relevé
# (jan / avr / juil) qui est aussi le CENTRE de son trimestre météorologique
# standard. Le découpage couvre les 12 mois exactement une fois :
#   hiver     = DJF                 (ancre janvier)
#   mi_saison = MAM + SON           (ancre avril — printemps ET automne)
#   ete       = JJA                 (ancre juillet)
SAISONS = ('hiver', 'mi_saison', 'ete')

# Saison → mois PVGIS réellement téléchargé pour la FORME horaire.
SAISON_MOIS_PVGIS = {'hiver': 1, 'mi_saison': 4, 'ete': 7}

# Saison → clé de la forme stockée dans COURBES_REFERENCE.
_SAISON_CLE_FORME = {'hiver': 'jan', 'mi_saison': 'avr', 'ete': 'juil'}

# Saison → numéros de mois (1-12) agrégés pour les MOYENNES journalières.
MOIS_PAR_SAISON = {
    'hiver': (12, 1, 2),
    'mi_saison': (3, 4, 5, 9, 10, 11),
    'ete': (6, 7, 8),
}

# Jours par mois (année non bissextile — la climatologie PVGIS est une moyenne
# pluriannuelle, le 29 février ne change rien à une moyenne journalière).
JOURS_PAR_MOIS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

# Décalage heure civile marocaine vs UTC (UTC+1 toute l'année depuis 2018 ;
# retour à UTC+0 pendant le Ramadan — NON modélisé, cf. docstring).
DECALAGE_MAROC_H = 1


# ── Table de référence : 7 courbes horaires (parts de l'énergie du jour) ──────
# Chaque liste = 24 valeurs, indice 0 = 00 h UTC, recopiées VERBATIM de la
# réponse DRcalc de la ville d'ancrage (G(i) horaire / somme du jour).
COURBES_REFERENCE = {
    'casa_atlantique': {
        'ancrage': 'Casablanca',
        'lat': 33.573, 'lon': -7.59,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.027, 0.072, 0.111, 0.140, 0.151, 0.147, 0.136, 0.111,
            0.076, 0.028, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.001, 0.019,
            0.048, 0.077, 0.103, 0.124, 0.136, 0.135, 0.124, 0.104,
            0.074, 0.042, 0.012, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.005, 0.020,
            0.046, 0.075, 0.101, 0.122, 0.133, 0.132, 0.122, 0.103,
            0.075, 0.045, 0.018, 0.004, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    'tanger': {
        'ancrage': 'Tanger',
        'lat': 35.777, 'lon': -5.804,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.032, 0.079, 0.116, 0.142, 0.153, 0.149, 0.133, 0.109,
            0.071, 0.015, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.002, 0.023,
            0.053, 0.081, 0.105, 0.123, 0.131, 0.134, 0.123, 0.103,
            0.074, 0.040, 0.010, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.006, 0.024,
            0.052, 0.079, 0.103, 0.121, 0.130, 0.129, 0.118, 0.099,
            0.074, 0.044, 0.017, 0.003, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    'fes_oujda': {
        'ancrage': 'Fès',
        'lat': 34.033, 'lon': -5.0,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.039, 0.081, 0.118, 0.143, 0.155, 0.148, 0.130, 0.104,
            0.067, 0.016, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.002, 0.025,
            0.056, 0.085, 0.111, 0.131, 0.136, 0.133, 0.117, 0.095,
            0.066, 0.035, 0.008, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.007, 0.026,
            0.054, 0.083, 0.107, 0.126, 0.133, 0.130, 0.117, 0.095,
            0.068, 0.039, 0.014, 0.002, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    'marrakech': {
        'ancrage': 'Marrakech',
        'lat': 31.63, 'lon': -8.01,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.031, 0.072, 0.110, 0.134, 0.148, 0.147, 0.136, 0.110,
            0.078, 0.034, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.018,
            0.048, 0.079, 0.106, 0.128, 0.136, 0.136, 0.123, 0.102,
            0.072, 0.041, 0.012, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.004, 0.020,
            0.048, 0.078, 0.104, 0.124, 0.135, 0.133, 0.120, 0.099,
            0.072, 0.043, 0.017, 0.003, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    'agadir': {
        'ancrage': 'Agadir',
        'lat': 30.428, 'lon': -9.598,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.024, 0.069, 0.108, 0.133, 0.149, 0.145, 0.137, 0.113,
            0.082, 0.040, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.014,
            0.042, 0.072, 0.100, 0.122, 0.134, 0.139, 0.129, 0.108,
            0.079, 0.046, 0.015, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.002, 0.016,
            0.038, 0.064, 0.093, 0.120, 0.135, 0.138, 0.129, 0.109,
            0.081, 0.050, 0.021, 0.004, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    'ouarzazate': {
        'ancrage': 'Ouarzazate',
        'lat': 30.92, 'lon': -6.91,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.037, 0.078, 0.114, 0.135, 0.149, 0.145, 0.133, 0.108,
            0.075, 0.026, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.001, 0.020,
            0.052, 0.085, 0.111, 0.131, 0.137, 0.133, 0.118, 0.096,
            0.068, 0.038, 0.010, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.004, 0.022,
            0.053, 0.085, 0.111, 0.131, 0.137, 0.130, 0.113, 0.091,
            0.066, 0.039, 0.015, 0.002, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    'sud_atlantique': {
        'ancrage': 'Laâyoune',
        'lat': 27.15, 'lon': -13.2,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.012, 0.058, 0.100, 0.127, 0.147, 0.148, 0.142, 0.121,
            0.091, 0.051, 0.003, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.007,
            0.035, 0.066, 0.095, 0.120, 0.135, 0.138, 0.131, 0.112,
            0.085, 0.053, 0.021, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.010,
            0.032, 0.060, 0.090, 0.116, 0.133, 0.137, 0.130, 0.113,
            0.088, 0.057, 0.026, 0.006, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    # ── 3 groupes ajoutés le 31/08/2026 (villes dont l'écart max mesuré vs
    # tous les groupes existants dépassait 0.015 — elles portent donc leur
    # PROPRE courbe VERBATIM, jamais rattachées de force ni moyennées).
    'beni_mellal': {
        'ancrage': 'Béni Mellal',
        'lat': 32.337, 'lon': -6.350,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.006, 0.082, 0.119, 0.144, 0.154, 0.149, 0.135, 0.109,
            0.075, 0.027, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.001, 0.022,
            0.054, 0.084, 0.109, 0.126, 0.133, 0.132, 0.120, 0.099,
            0.070, 0.038, 0.010, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.005, 0.023,
            0.053, 0.083, 0.109, 0.128, 0.135, 0.130, 0.116, 0.093,
            0.067, 0.039, 0.015, 0.002, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    'tetouan_detroit': {
        'ancrage': 'Tétouan',
        'lat': 35.578, 'lon': -5.368,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.034, 0.084, 0.121, 0.146, 0.161, 0.155, 0.140, 0.110,
            0.046, 0.003, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.002, 0.025,
            0.055, 0.085, 0.109, 0.127, 0.133, 0.130, 0.118, 0.099,
            0.072, 0.040, 0.007, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.006, 0.025,
            0.051, 0.079, 0.104, 0.122, 0.131, 0.128, 0.118, 0.099,
            0.073, 0.044, 0.016, 0.003, 0.000, 0.000, 0.000, 0.000,
        ],
    },
    'tan_tan': {
        'ancrage': 'Tan-Tan',
        'lat': 28.438, 'lon': -11.103,
        'jan': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
            0.011, 0.063, 0.104, 0.130, 0.150, 0.150, 0.141, 0.120,
            0.087, 0.044, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'avr': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.011,
            0.037, 0.066, 0.096, 0.120, 0.136, 0.140, 0.131, 0.113,
            0.083, 0.049, 0.017, 0.000, 0.000, 0.000, 0.000, 0.000,
        ],
        'juil': [
            0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.001, 0.014,
            0.033, 0.052, 0.075, 0.108, 0.133, 0.144, 0.140, 0.121,
            0.092, 0.057, 0.025, 0.005, 0.000, 0.000, 0.000, 0.000,
        ],
    },
}

# ── Table de référence : productible mensuel PAR VILLE (kWh/kWc/mois) ─────────
# ``e_m`` = 12 valeurs janvier→décembre, VERBATIM de PVcalc (peakpower=1).
# ``e_y`` = total annuel PVGIS de la même réponse (contrôle de cohérence).
# ``courbe`` = groupe de COURBES_REFERENCE qui porte la forme horaire.
# Les clés sont déjà normalisées (minuscules, sans accent) — cf. _normaliser.
PRODUCTIBLE_MENSUEL_VILLE = {
    'casablanca': {
        'courbe': 'casa_atlantique',
        'lat': 33.573, 'lon': -7.59,
        'e_y': 1719.14,
        'e_m': [
            123.73, 121.81, 147.07, 153.96, 158.90, 155.03,
            165.63, 164.69, 149.73, 140.26, 118.39, 119.96,
        ],
    },
    'bouskoura': {
        'courbe': 'casa_atlantique',
        'lat': 33.449, 'lon': -7.657,
        'e_y': 1713.88,
        'e_m': [
            123.17, 120.89, 145.73, 150.75, 157.68, 155.71,
            168.57, 166.81, 148.50, 138.74, 117.20, 120.14,
        ],
    },
    'mohammedia': {
        'courbe': 'casa_atlantique',
        'lat': 33.686, 'lon': -7.383,
        'e_y': 1706.76,
        'e_m': [
            121.63, 120.78, 145.14, 151.94, 157.94, 155.08,
            166.02, 165.12, 149.49, 138.99, 116.82, 117.80,
        ],
    },
    'el jadida': {
        'courbe': 'casa_atlantique',
        'lat': 33.231, 'lon': -8.5,
        'e_y': 1756.21,
        'e_m': [
            125.65, 124.74, 152.51, 160.38, 163.48, 157.97,
            166.47, 165.62, 153.45, 142.37, 120.82, 122.74,
        ],
    },
    'rabat': {
        'courbe': 'casa_atlantique',
        'lat': 34.021, 'lon': -6.841,
        'e_y': 1702.78,
        'e_m': [
            118.71, 120.17, 145.25, 153.44, 159.69, 156.86,
            166.45, 165.43, 150.25, 137.93, 114.59, 114.00,
        ],
    },
    'fes': {
        'courbe': 'fes_oujda',
        'lat': 34.033, 'lon': -5.0,
        'e_y': 1682.84,
        'e_m': [
            123.96, 122.96, 143.62, 144.76, 152.30, 152.68,
            160.68, 159.53, 146.03, 137.70, 117.02, 121.61,
        ],
    },
    'marrakech': {
        'courbe': 'marrakech',
        'lat': 31.63, 'lon': -8.01,
        'e_y': 1749.09,
        'e_m': [
            140.13, 132.38, 154.07, 153.52, 152.89, 149.63,
            154.83, 153.95, 146.07, 143.22, 130.26, 138.13,
        ],
    },
    'agadir': {
        'courbe': 'agadir',
        'lat': 30.428, 'lon': -9.598,
        'e_y': 1831.53,
        'e_m': [
            148.84, 142.28, 167.29, 165.34, 162.41, 152.98,
            157.16, 156.05, 150.83, 150.35, 137.47, 140.53,
        ],
    },
    'tanger': {
        'courbe': 'tanger',
        'lat': 35.777, 'lon': -5.804,
        'e_y': 1660.57,
        'e_m': [
            110.24, 111.25, 137.57, 147.26, 161.18, 161.35,
            171.97, 167.76, 148.68, 133.08, 106.10, 104.13,
        ],
    },
    'oujda': {
        'courbe': 'fes_oujda',
        'lat': 34.681, 'lon': -1.908,
        'e_y': 1703.24,
        'e_m': [
            126.27, 124.40, 144.21, 147.34, 155.22, 156.25,
            161.36, 160.96, 145.22, 140.54, 119.36, 122.10,
        ],
    },
    'ouarzazate': {
        'courbe': 'ouarzazate',
        'lat': 30.92, 'lon': -6.91,
        'e_y': 1879.73,
        'e_m': [
            158.22, 150.26, 175.25, 171.01, 165.86, 155.70,
            152.63, 151.61, 150.28, 153.37, 145.12, 150.40,
        ],
    },
    'laayoune': {
        'courbe': 'sud_atlantique',
        'lat': 27.15, 'lon': -13.2,
        'e_y': 1909.10,
        'e_m': [
            151.75, 147.84, 176.72, 171.81, 167.29, 157.75,
            163.60, 164.75, 158.37, 156.10, 145.34, 147.79,
        ],
    },
    'dakhla': {
        'courbe': 'sud_atlantique',
        'lat': 23.70, 'lon': -15.94,
        'e_y': 1927.71,
        'e_m': [
            161.54, 158.32, 181.74, 170.49, 165.49, 153.62,
            156.45, 156.49, 154.48, 161.48, 154.06, 153.56,
        ],
    },
    # ── 19 villes ajoutées le 31/08/2026 — PVGIS v5_3, MÊMES appels figés que
    # les 13 d'origine (PVcalc peakpower=1, loss=14, crystSi, angle=30,
    # aspect=0, mountingplace=free), valeurs recopiées VERBATIM. Le groupe
    # ``courbe`` de chacune est celui qui MINIMISE l'écart mesuré (3 saisons ×
    # 24 h) vs sa forme DRcalc réelle — écarts consignés dans le docstring.
    'kenitra': {
        'courbe': 'casa_atlantique',
        'lat': 34.261, 'lon': -6.580,
        'e_y': 1680.56,
        'e_m': [
            115.09, 116.62, 143.50, 152.37, 158.50, 156.66,
            166.95, 165.19, 148.09, 135.10, 111.72, 110.76,
        ],
    },
    'bouznika': {
        'courbe': 'casa_atlantique',
        'lat': 33.789, 'lon': -7.160,
        'e_y': 1705.27,
        'e_m': [
            121.29, 120.99, 145.43, 151.61, 157.69, 155.16,
            166.08, 164.89, 149.94, 138.87, 115.95, 117.36,
        ],
    },
    'settat': {
        'courbe': 'casa_atlantique',
        'lat': 33.001, 'lon': -7.617,
        'e_y': 1733.84,
        'e_m': [
            127.99, 122.92, 147.09, 151.65, 156.96, 157.56,
            167.82, 166.75, 149.74, 140.54, 120.27, 124.56,
        ],
    },
    'khouribga': {
        'courbe': 'marrakech',
        'lat': 32.881, 'lon': -6.906,
        'e_y': 1755.86,
        'e_m': [
            133.33, 128.43, 151.68, 154.03, 157.30, 157.63,
            163.42, 163.33, 150.50, 142.99, 123.96, 129.26,
        ],
    },
    'beni mellal': {
        'courbe': 'beni_mellal',
        'lat': 32.337, 'lon': -6.350,
        'e_y': 1657.02,
        'e_m': [
            126.46, 122.16, 142.28, 142.20, 145.16, 147.55,
            154.02, 152.16, 141.79, 136.67, 119.83, 126.74,
        ],
    },
    'meknes': {
        'courbe': 'fes_oujda',
        'lat': 33.894, 'lon': -5.547,
        'e_y': 1676.80,
        'e_m': [
            123.37, 121.24, 142.14, 143.61, 151.70, 152.31,
            161.96, 160.66, 145.69, 137.86, 115.97, 120.30,
        ],
    },
    'taza': {
        'courbe': 'tanger',
        'lat': 34.210, 'lon': -4.010,
        'e_y': 1727.68,
        'e_m': [
            129.61, 126.67, 151.38, 151.83, 159.74, 158.46,
            160.33, 158.78, 148.05, 141.02, 120.23, 121.59,
        ],
    },
    'nador': {
        'courbe': 'fes_oujda',
        'lat': 35.168, 'lon': -2.934,
        'e_y': 1609.23,
        'e_m': [
            116.06, 115.11, 135.44, 137.72, 148.15, 152.77,
            156.76, 155.19, 137.84, 131.35, 111.10, 111.73,
        ],
    },
    'al hoceima': {
        'courbe': 'tanger',
        'lat': 35.252, 'lon': -3.937,
        'e_y': 1647.57,
        'e_m': [
            118.63, 117.18, 141.31, 143.81, 154.33, 157.81,
            163.19, 156.32, 140.89, 130.72, 111.83, 111.55,
        ],
    },
    'tetouan': {
        'courbe': 'tetouan_detroit',
        'lat': 35.578, 'lon': -5.368,
        'e_y': 1585.89,
        'e_m': [
            111.83, 104.24, 130.39, 134.49, 150.73, 158.22,
            165.95, 155.64, 137.91, 127.28, 105.62, 103.60,
        ],
    },
    'larache': {
        'courbe': 'tanger',
        'lat': 35.193, 'lon': -6.156,
        'e_y': 1662.88,
        'e_m': [
            111.32, 114.05, 140.03, 151.37, 159.85, 158.68,
            167.63, 164.82, 148.52, 134.18, 107.43, 105.01,
        ],
    },
    'safi': {
        'courbe': 'agadir',
        'lat': 32.299, 'lon': -9.237,
        'e_y': 1818.59,
        'e_m': [
            133.49, 131.23, 158.66, 163.95, 166.29, 160.76,
            171.07, 169.88, 157.37, 147.12, 128.50, 130.28,
        ],
    },
    'essaouira': {
        'courbe': 'agadir',
        'lat': 31.512, 'lon': -9.770,
        'e_y': 1843.78,
        'e_m': [
            140.21, 136.34, 163.35, 166.48, 166.93, 161.08,
            168.54, 167.33, 157.98, 148.71, 132.23, 134.61,
        ],
    },
    'guelmim': {
        'courbe': 'agadir',
        'lat': 28.987, 'lon': -10.057,
        'e_y': 1871.24,
        'e_m': [
            154.13, 146.25, 173.46, 168.14, 162.34, 151.41,
            154.92, 155.75, 155.04, 155.65, 144.22, 149.93,
        ],
    },
    'tan tan': {
        'courbe': 'tan_tan',
        'lat': 28.438, 'lon': -11.103,
        'e_y': 1777.90,
        'e_m': [
            146.04, 141.36, 169.26, 159.52, 151.32, 135.52,
            139.44, 146.94, 150.14, 151.64, 142.04, 144.68,
        ],
    },
    'tiznit': {
        'courbe': 'marrakech',
        'lat': 29.697, 'lon': -9.732,
        'e_y': 1855.96,
        'e_m': [
            149.81, 143.73, 168.65, 166.19, 161.33, 151.01,
            160.41, 161.33, 154.70, 153.45, 141.26, 144.10,
        ],
    },
    'taroudant': {
        'courbe': 'marrakech',
        'lat': 30.470, 'lon': -8.877,
        'e_y': 1789.85,
        'e_m': [
            149.55, 139.05, 162.65, 159.12, 156.12, 146.63,
            152.46, 151.94, 146.55, 146.74, 137.28, 141.76,
        ],
    },
    'errachidia': {
        'courbe': 'fes_oujda',
        'lat': 31.931, 'lon': -4.427,
        'e_y': 1867.19,
        'e_m': [
            152.57, 148.64, 171.01, 168.87, 164.77, 157.33,
            157.75, 157.79, 149.51, 151.72, 141.29, 145.93,
        ],
    },
    'ifrane': {
        'courbe': 'ouarzazate',
        'lat': 33.527, 'lon': -5.110,
        'e_y': 1689.28,
        'e_m': [
            122.62, 120.82, 143.34, 148.14, 152.47, 154.85,
            158.20, 156.76, 147.19, 140.62, 118.66, 125.62,
        ],
    },
}

# Orthographes courantes → clé de PRODUCTIBLE_MENSUEL_VILLE. On n'ajoute ICI
# que des ÉCRITURES du MÊME lieu (translittérations, tirets, article) — jamais
# une ville voisine « rattachée » à une autre : pour ``cle_ville``, une ville
# hors table reste INCONNUE. (Depuis le 31/08/2026, la résolution DOUCE des
# villes hors table — gazetier + ancre la plus proche, source nommée — vit
# plus bas dans la chaîne, cf. docstring du module ; ce mapping-ci reste
# réservé aux écritures du même lieu.)
_ORTHOGRAPHES = {
    'eljadida': 'el jadida',
    'el-jadida': 'el jadida',
    'fez': 'fes',
    'oudjda': 'oujda',
    'ouarzazat': 'ouarzazate',
    'warzazate': 'ouarzazate',
    'layoune': 'laayoune',
    'el aaiun': 'laayoune',
    'ad dakhla': 'dakhla',
    'addakhla': 'dakhla',
    'tangier': 'tanger',
    'marrakesh': 'marrakech',
    'boskoura': 'bouskoura',
}


def _normaliser(valeur) -> str:
    """Minuscule, sans accent, tirets/apostrophes → espace, espaces compactés.

    « Laâyoune », « LAAYOUNE » et «  laayoune  » donnent la même clé ;
    « Tan-Tan » et « Tan Tan » aussi (même règle que ``villes_maroc``).
    """
    txt = str(valeur or '').strip().lower()
    if not txt:
        return ''
    txt = txt.replace('-', ' ').replace("'", ' ').replace('’', ' ')
    txt = unicodedata.normalize('NFKD', txt)
    txt = ''.join(c for c in txt if not unicodedata.combining(c))
    return ' '.join(txt.split())


def cle_ville(ville):
    """Clé de table pour ``ville``, ou ``None`` si la ville est INCONNUE.

    Aucune approximation : une ville absente de la table renvoie ``None`` et
    l'appelant OMET la donnée (Q6), il n'invente pas une ville voisine.

    L-QA1 (24/08/2026) FIX2 — repli TOLÉRANT quand la correspondance exacte
    échoue. Le tunnel web range du texte LIBRE dans ``Lead.ville`` (cas réel :
    « Hay Riad, Rabat »), et l'égalité stricte échouait alors avec « ni GPS,
    ni ville reconnue » alors que « Rabat » figure bel et bien dans la table.
    Le repli cherche un nom de ville CONNU comme MOT ENTIER dans le texte
    (:func:`_cle_ville_tolerante`) — jamais une ville hors table devinée, Q6
    tient toujours : un texte sans aucune ville connue reste ``None``.
    """
    key = _normaliser(ville)
    if not key:
        return None
    alias = _ORTHOGRAPHES.get(key, key)
    if alias in PRODUCTIBLE_MENSUEL_VILLE:
        return alias
    return _cle_ville_tolerante(key)


def _cle_ville_tolerante(texte_normalise):
    """Cherche un nom de ville CONNU (table + orthographes) comme séquence de
    MOTS ENTIERS dans ``texte_normalise`` (déjà passé par :func:`_normaliser`),
    virgules traitées comme des séparateurs — ``None`` si aucune ville connue
    n'apparaît. Les candidats multi-mots (« el jadida ») sont essayés AVANT
    les mono-mots pour ne jamais laisser un mot isolé chevaucher un nom
    composé."""
    mots = texte_normalise.replace(',', ' ').split()
    if not mots:
        return None
    candidats = set(PRODUCTIBLE_MENSUEL_VILLE) | set(_ORTHOGRAPHES)
    for candidat in sorted(candidats, key=lambda c: -len(c.split())):
        mots_candidat = candidat.split()
        n = len(mots_candidat)
        for i in range(len(mots) - n + 1):
            if mots[i:i + n] == mots_candidat:
                return _ORTHOGRAPHES.get(candidat, candidat)
    return None


def ville_connue(ville) -> bool:
    """``True`` si la ville figure dans la table PVGIS de référence."""
    return cle_ville(ville) is not None


# ── Gazetier + ancre la plus proche (ordre fondateur du 31/08/2026) ──────────

def _coordonnees_gazetier(ville):
    """``(lat, lon)`` du gazetier GeoNames pour ``ville``, ou ``None``.

    Import paresseux : le gazetier est un module GÉNÉRÉ (~300 villes) ; son
    absence ou une erreur d'import ne casse jamais la chaîne — on retombe
    simplement sur l'omission historique.
    """
    try:
        from apps.parametres.villes_maroc import coordonnees_ville
    except Exception:  # noqa: BLE001 — gazetier indisponible → chaîne inchangée
        return None
    try:
        return coordonnees_ville(ville)
    except Exception:  # noqa: BLE001 — un texte illisible n'est pas une panne
        logger.warning('gazetier villes_maroc illisible', exc_info=True)
        return None


def _distance_km(lat1, lon1, lat2, lon2):
    """Distance grand-cercle (haversine), en kilomètres."""
    import math
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def ancre_la_plus_proche(lat, lon):
    """``(clé, km)`` de la ville de la table la plus proche du point donné.

    Sert la résolution « ville hors table » : la donnée rendue est alors la
    table PVGIS RÉELLE de cette ancre, jamais une interpolation. Départage
    déterministe (distance, puis clé alphabétique).
    """
    meilleure = min(
        PRODUCTIBLE_MENSUEL_VILLE.items(),
        key=lambda kv: (_distance_km(lat, lon, kv[1]['lat'], kv[1]['lon']),
                        kv[0]))
    cle, entree = meilleure
    return cle, _distance_km(lat, lon, entree['lat'], entree['lon'])


def _normaliser_forme(valeurs):
    """Ramène 24 valeurs positives à une somme de 1,0 (ou ``None`` si vide).

    Les fractions stockées sont arrondies à 3 décimales : leur somme vaut
    0,998 à 1,002 selon la ville. On renormalise pour que la forme servie
    somme EXACTEMENT à 1 — le total journalier reste donc le ``kwh_jour``
    réel, jamais 0,2 % à côté.
    """
    try:
        vals = [max(0.0, float(v)) for v in valeurs]
    except (TypeError, ValueError):
        return None
    if len(vals) != 24:
        return None
    total = sum(vals)
    if total <= 0:
        return None
    return [round(v / total, 5) for v in vals]


def vers_heure_locale(forme_utc, decalage_h=DECALAGE_MAROC_H):
    """Décale une forme 24 h UTC vers l'heure civile marocaine (UTC+1).

    ``forme_locale[h] = forme_utc[(h - decalage) % 24]`` : le pic de janvier,
    à 12 h UTC dans la donnée PVGIS, s'affiche bien à 13 h locale.

    NOTE RAMADAN (affichage, non modélisé) : pendant le Ramadan le Maroc
    repasse à UTC+0 — la courbe est alors la forme BRUTE (``decalage_h=0``),
    décalée d'une heure vers la gauche par rapport au reste de l'année.
    """
    if not forme_utc or len(forme_utc) != 24:
        return None
    try:
        dec = int(decalage_h) % 24
    except (TypeError, ValueError):
        dec = 0
    return [forme_utc[(h - dec) % 24] for h in range(24)]


def moyenne_journaliere_saison(valeurs_mensuelles, saison):
    """Moyenne JOURNALIÈRE d'une série mensuelle sur les mois d'une saison.

    ``valeurs_mensuelles`` = 12 totaux MENSUELS (même unité, janvier→décembre) :
    productible kWh/kWc/mois, ou consommation kWh/mois du client. On divise
    chaque mois par SON nombre de jours PUIS on moyenne — jamais
    ``moyenne(mois) / moyenne(jours)``, qui pondère mal les mois courts.

    Renvoie ``None`` si la série est absente, incomplète ou entièrement nulle
    (on OMET plutôt que d'afficher un zéro qui ressemblerait à une mesure).
    """
    if saison not in MOIS_PAR_SAISON:
        return None
    if not valeurs_mensuelles or len(valeurs_mensuelles) != 12:
        return None
    quotidiens = []
    for mois in MOIS_PAR_SAISON[saison]:
        try:
            total_mois = float(valeurs_mensuelles[mois - 1])
        except (TypeError, ValueError, IndexError):
            return None
        quotidiens.append(total_mois / JOURS_PAR_MOIS[mois - 1])
    if not quotidiens or not any(v > 0 for v in quotidiens):
        return None
    return sum(quotidiens) / len(quotidiens)


# ── Accès réseau PVGIS (live) ────────────────────────────────────────────────

def _cache_lire(cle):
    """Lecture du cache SYSTÈME (``core.cache``, company=None) — best-effort."""
    try:
        from core import cache as tenant_cache
        return tenant_cache.get(None, cle)
    except Exception:  # noqa: BLE001 — pas de Django/cache dispo → pas de cache
        return None


def _cache_ecrire(cle, valeur, ttl=None):
    """Écriture du cache SYSTÈME — best-effort, jamais bloquante."""
    try:
        from core import cache as tenant_cache
        tenant_cache.set(None, cle, valeur,
                         CACHE_TTL_S if ttl is None else ttl)
    except Exception:  # noqa: BLE001 — cache indisponible → on s'en passe
        logger.debug('cache pvgis_profils indisponible pour %s', cle)


def _appel_pvgis(url):
    """GET JSON PVGIS avec timeout court ; ``None`` sur toute anomalie.

    Aucune exception réseau ne remonte : une proposition doit s'afficher même
    hors-ligne (la chaîne de résolution retombe alors sur la table de
    référence, puis sur l'omission).

    COUPE-CIRCUIT : une page proposition peut demander jusqu'à 4 profils (3
    saisons + le productible). PVGIS injoignable, c'est 4 × ``PVGIS_TIMEOUT_S``
    ajoutés au temps de réponse d'une page CLIENT. Le premier échec pose donc
    un drapeau de panne partagé (cache système, :data:`PANNE_TTL_S`) : les
    appels suivants renoncent IMMÉDIATEMENT et la chaîne retombe sur la table
    de référence. Le drapeau expire tout seul.
    """
    if _cache_lire(PANNE_CLE):
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'taqinor-os'})
        with urllib.request.urlopen(req, timeout=PVGIS_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            ValueError, OSError) as exc:
        logger.info('PVGIS indisponible (%s)', type(exc).__name__)
        _cache_ecrire(PANNE_CLE, True, PANNE_TTL_S)
        return None


def _url_drcalc(lat, lon, mois):
    params = {
        'lat': lat, 'lon': lon, 'month': mois,
        'angle': PVGIS_ANGLE_DEG, 'aspect': PVGIS_ASPECT_DEG,
        'global': 1, 'outputformat': 'json',
    }
    return PVGIS_DRCALC + '?' + urllib.parse.urlencode(params)


def _url_pvcalc(lat, lon):
    params = {
        'lat': lat, 'lon': lon, 'peakpower': 1, 'loss': PVGIS_LOSS_PCT,
        'pvtechchoice': PVGIS_PVTECH, 'outputformat': 'json',
        'angle': PVGIS_ANGLE_DEG, 'aspect': PVGIS_ASPECT_DEG,
        'mountingplace': PVGIS_MOUNTING,
    }
    return PVGIS_PVCALC + '?' + urllib.parse.urlencode(params)


def _forme_depuis_drcalc(payload):
    """Extrait la forme 24 h normalisée d'une réponse ``DRcalc``.

    Structure attendue : ``outputs.daily_profile`` = 24 entrées ``{'time':
    'HH:MM', 'G(i)': W/m²}`` en UTC. Toute structure inattendue → ``None``.
    """
    try:
        profil = (payload or {}).get('outputs', {}).get('daily_profile')
    except AttributeError:
        return None
    if not isinstance(profil, list) or len(profil) != 24:
        return None
    heures = [0.0] * 24
    for entree in profil:
        if not isinstance(entree, dict):
            return None
        try:
            heure = int(str(entree.get('time', '')).split(':')[0])
            gi = float(entree.get('G(i)', 0.0))
        except (TypeError, ValueError, IndexError):
            return None
        if not 0 <= heure <= 23:
            return None
        heures[heure] = max(0.0, gi)
    return _normaliser_forme(heures)


def _mensuel_depuis_pvcalc(payload):
    """Extrait les 12 ``E_m`` (kWh/kWc/mois) d'une réponse ``PVcalc``."""
    try:
        mois = (payload or {}).get('outputs', {}).get('monthly', {}).get('fixed')
    except AttributeError:
        return None
    if not isinstance(mois, list) or len(mois) != 12:
        return None
    valeurs = []
    for entree in mois:
        if not isinstance(entree, dict):
            return None
        try:
            valeurs.append(round(float(entree['E_m']), 2))
        except (TypeError, ValueError, KeyError):
            return None
    if not any(v > 0 for v in valeurs):
        return None
    return valeurs


def _coordonnees(lat, lon):
    """Couple (lat, lon) flottant plausible, ou ``None``."""
    try:
        latf, lonf = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= latf <= 90.0) or not (-180.0 <= lonf <= 180.0):
        return None
    if latf == 0.0 and lonf == 0.0:  # « île nulle » = coordonnée non renseignée
        return None
    return latf, lonf


def profil_horaire_live(lat, lon, mois):
    """Forme 24 h UTC au point GPS via ``DRcalc``, ou ``None``. Cache 30 j.

    Clé de cache SYSTÈME (jamais scopée société — la physique d'un point GPS
    n'appartient à aucun tenant, même convention que PV73) :
    ``pvgis:drprofil:{lat:.3f}:{lon:.3f}:{mois}``, coordonnées arrondies à
    3 décimales (~100 m) pour que deux devis du même toit partagent l'entrée.
    """
    coords = _coordonnees(lat, lon)
    if coords is None or mois not in (1, 4, 7):
        return None
    latf, lonf = coords
    cle = 'pvgis:drprofil:%.3f:%.3f:%d' % (latf, lonf, mois)

    en_cache = _cache_lire(cle)
    if en_cache is not None:
        return en_cache or None

    forme = _forme_depuis_drcalc(_appel_pvgis(_url_drcalc(latf, lonf, mois)))
    if forme is not None:
        _cache_ecrire(cle, forme)
    return forme


def productible_mensuel_live(lat, lon):
    """12 ``E_m`` (kWh/kWc/mois) au point GPS via ``PVcalc``, ou ``None``.

    Mêmes paramètres FIGÉS que la table de référence (angle 30, aspect 0,
    loss 14, crystSi) — sans quoi « live » et « référence » ne seraient pas
    comparables. Cache SYSTÈME 30 j, clé ``pvgis:emens:{lat}:{lon}``.
    """
    coords = _coordonnees(lat, lon)
    if coords is None:
        return None
    latf, lonf = coords
    cle = 'pvgis:emens:%.3f:%.3f' % (latf, lonf)

    en_cache = _cache_lire(cle)
    if en_cache is not None:
        return en_cache or None

    valeurs = _mensuel_depuis_pvcalc(_appel_pvgis(_url_pvcalc(latf, lonf)))
    if valeurs is not None:
        _cache_ecrire(cle, valeurs)
    return valeurs


# ── API publique : chaîne de résolution ──────────────────────────────────────

def profil_production_journalier(*, saison, lat=None, lon=None, ville=None):
    """Forme 24 h UTC de la production + libellé de source, ou ``None``.

    Chaîne de résolution (dans cet ordre) :

    a. ``lat``/``lon`` fournis → PVGIS **live** (``DRcalc``) au point EXACT,
       mois 1/4/7 selon la saison → source ``'pvgis_live'``.
    b. pas de coordonnées (ou live indisponible) et ``ville`` RECONNUE parmi
       les 32 villes de la table → courbe de référence de son groupe →
       source ``'pvgis_ville:<ancrage>'``.
    c. ville HORS table mais au GAZETIER (ou coordonnées dont le live est
       indisponible) → courbe du groupe de l'ANCRE de table la plus proche →
       source ``'pvgis_ville_proche:<ancrage>'`` (fondateur, 31/08/2026 :
       une vraie courbe d'une vraie ville voisine, nommée — jamais une
       cloche synthétique).
    d. ni coordonnées exploitables ni ville reconnue nulle part → ``None``.
       La page OMET la courbe et garde son affichage actuel.

    La forme renvoyée est en **UTC** (indice 0 = 00 h UTC) et somme à 1,0 :
    c'est au consommateur d'appeler :func:`vers_heure_locale`.
    """
    if saison not in _SAISON_CLE_FORME:
        return None

    coords = _coordonnees(lat, lon)
    if coords is not None:
        forme = profil_horaire_live(
            coords[0], coords[1], SAISON_MOIS_PVGIS[saison])
        if forme:
            return forme, 'pvgis_live'

    cle = cle_ville(ville)
    if cle:
        groupe = PRODUCTIBLE_MENSUEL_VILLE[cle]['courbe']
        courbe = COURBES_REFERENCE[groupe]
        forme = _normaliser_forme(courbe[_SAISON_CLE_FORME[saison]])
        if forme:
            return forme, 'pvgis_ville:%s' % _normaliser(courbe['ancrage'])

    if coords is None:
        coords = _coordonnees_gazetier(ville)
    if coords is not None:
        cle_ancre, _km = ancre_la_plus_proche(coords[0], coords[1])
        groupe = PRODUCTIBLE_MENSUEL_VILLE[cle_ancre]['courbe']
        courbe = COURBES_REFERENCE[groupe]
        forme = _normaliser_forme(courbe[_SAISON_CLE_FORME[saison]])
        if forme:
            return (forme,
                    'pvgis_ville_proche:%s' % _normaliser(courbe['ancrage']))

    return None


def productible_mensuel(ville=None, lat=None, lon=None):
    """12 productibles mensuels (kWh/kWc/mois) + source, ou ``None``.

    Même chaîne que :func:`profil_production_journalier` : live au point GPS,
    sinon table de la ville reconnue, sinon ancre de table LA PLUS PROCHE du
    point connu (GPS dont le live est indisponible, ou position gazetier de la
    ville — fondateur, 31/08/2026), sinon ``None`` (on omet). La source de
    l'ancre nomme la ville ET la distance : ``pvgis_ville_proche:<cle>~<km>km``.
    """
    coords = _coordonnees(lat, lon)
    if coords is not None:
        valeurs = productible_mensuel_live(coords[0], coords[1])
        if valeurs:
            # Copie : l'appelant ne peut pas muter l'entrée de cache.
            return list(valeurs), 'pvgis_live'

    cle = cle_ville(ville)
    if cle:
        entree = PRODUCTIBLE_MENSUEL_VILLE[cle]
        return list(entree['e_m']), 'pvgis_ville:%s' % cle

    if coords is None:
        coords = _coordonnees_gazetier(ville)
    if coords is not None:
        cle_ancre, km = ancre_la_plus_proche(coords[0], coords[1])
        entree = PRODUCTIBLE_MENSUEL_VILLE[cle_ancre]
        return (list(entree['e_m']),
                'pvgis_ville_proche:%s~%dkm' % (cle_ancre, round(km)))

    return None
