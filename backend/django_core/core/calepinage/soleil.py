# -*- coding: utf-8 -*-
"""CALX146 — la position du soleil HEURE PAR HEURE, dans le noyau pur.

Ce que le dépôt savait faire avant ce module
--------------------------------------------
``politique_pas.position_solaire_solstice`` (``politique_pas.py:92-120``) ne
calcule la position qu'AU SOLSTICE D'HIVER, à une heure solaire choisie, avec
une déclinaison figée à −23,44° : c'est tout ce qu'il faut pour ESPACER des
rangées, et rien de ce qu'il faut pour CHIFFRER une ombre. Sans position
horaire, ni l'horizon heure par heure (CALX156), ni l'auto-ombrage
inter-rangées (CALX159), ni l'IAM (CALX160) ne sont calculables.

Les formules et leur source
---------------------------
L'algorithme est celui du **NOAA Solar Calculator**, lui-même tiré de Jean
Meeus, *Astronomical Algorithms*, 2ᵉ édition, Willmann-Bell, 1998 (chapitres
7 « Julian Day », 22 « Nutation and the Obliquity of the Ecliptic » et 25
« Solar Coordinates »). Les grandeurs qu'il nomme, dans l'ordre où elles sont
calculées ici :

* **jour julien** ``JJ`` puis siècles juliens ``T = (JJ − 2 451 545) / 36 525``
  depuis l'époque J2000,0 (Meeus, ch. 7) ;
* **longitude moyenne géométrique** ``L₀`` et **anomalie moyenne** ``M`` du
  soleil, **excentricité** ``e`` de l'orbite terrestre (Meeus, ch. 25) ;
* **équation du centre** ``C``, d'où la longitude vraie ``L₀ + C`` puis la
  **longitude apparente** ``λ`` (corrigée de l'aberration et de la nutation
  en longitude) ;
* **obliquité de l'écliptique** ``ε`` (Meeus, ch. 22) ;
* **DÉCLINAISON** ``δ = arcsin(sin ε · sin λ)`` — l'angle du soleil au-dessus
  du plan équatorial, ce que ``position_solaire_solstice`` fige à −23,44° ;
* **ÉQUATION DU TEMPS** ``ET`` (en minutes), l'écart entre le midi solaire
  VRAI et le midi solaire moyen : ``ET = 4·(y·sin 2L₀ − 2e·sin M
  + 4ey·sin M·cos 2L₀ − ½y²·sin 4L₀ − 1,25e²·sin 2M)`` avec
  ``y = tan²(ε/2)`` — elle vaut jusqu'à ±16 min dans l'année, soit jusqu'à 4°
  d'angle horaire : l'ignorer est exactement l'erreur que ce module évite ;
* **heure solaire vraie**, **angle horaire** ``h``, puis la position :

      cos z = sin φ · sin δ + cos φ · cos δ · cos h      (zénith)
      cos A = (sin φ · cos z − sin δ) / (cos φ · sin z)  (azimut)

  ``A`` est compté DEPUIS LE SUD : négatif le matin (est), positif
  l'après-midi (ouest) — c'est la convention de PVGIS (``aspect`` : 0 = sud,
  −90 = est, +90 = ouest), celle des fixtures et celle des réglages société.
  **Attention** : ``position_solaire_solstice`` porte la convention INVERSE
  (son ``sin γ = −cos δ · sin h / cos α`` est positif le matin). Les deux
  fonctions s'accordent sur l'ÉLÉVATION ; elles ne doivent jamais être
  mélangées sur l'azimut. L'ancienne n'est pas touchée ici : elle décide de
  l'espacement des rangées déjà publiées.

Ce que ce module ne fait PAS
----------------------------
* **Aucune réfraction atmosphérique** : l'élévation rendue est GÉOMÉTRIQUE.
  La réfraction relève le soleil d'environ 0,1° à 10° de hauteur et de 0,5°
  à l'horizon — au-dessus du plancher d'élévation, c'est un ordre de grandeur
  sous l'écart d'arrondi horaire des séries météo.
* **Aucun fuseau horaire** : ``heure_utc`` est en UTC, toujours. La
  conversion vers l'heure légale appartient à l'appelant (CALX59) — le noyau
  n'a ni ``zoneinfo`` ni notion de pays.
* **Aucun plafond, aucun forfait** : sous ``ELEVATION_PLANCHER_DEG``, la
  position est rendue TELLE QUELLE avec ``sous_le_plancher = True``. C'est à
  l'appelant d'OMETTRE son poste en le nommant, jamais à ce module de
  fabriquer une valeur de remplacement.

Validation
----------
``apps/calepinage/tests/test_calx146_soleil.py`` confronte ce module à la
colonne ``H_sun`` des réponses PVGIS réelles enregistrées dans
``apps/calepinage/tests/fixtures_pvgis/`` et, quand ``pvlib`` est installé
(CALX198), à ``pvlib.solarposition.get_solarposition``.
"""

import math
from dataclasses import dataclass

from core.calepinage.exceptions import EntreeInvalide
from core.calepinage.politique_pas import ELEVATION_PLANCHER_DEG

__all__ = [
    "PositionSolaire",
    "position_solaire",
    "JOUR_JULIEN_J2000",
    "JOURS_PAR_SIECLE_JULIEN",
    "DEGRES_PAR_MINUTE_HORAIRE",
]

#: Jour julien de l'époque J2000,0 (1ᵉʳ janvier 2000 à 12 h TT) — Meeus ch. 7.
JOUR_JULIEN_J2000 = 2451545.0

#: Longueur du siècle julien, en jours — Meeus ch. 7.
JOURS_PAR_SIECLE_JULIEN = 36525.0

#: La Terre tourne de 360° en 1 440 min : 0,25° par minute de temps. Sert à
#: convertir l'heure solaire vraie en angle horaire ET la longitude en minutes
#: (4 min par degré, l'inverse de cette constante).
DEGRES_PAR_MINUTE_HORAIRE = 0.25


def _borner(valeur, bas=-1.0, haut=1.0):
    """Ramène un sinus/cosinus dans [-1, 1] : l'arrondi flottant en sort."""
    return max(bas, min(haut, valeur))


def _jour_julien(annee, mois, jour, heure_utc):
    """Jour julien du calendrier grégorien (Meeus, ch. 7, formule 7.1)."""
    if mois <= 2:
        annee -= 1
        mois += 12
    siecle = annee // 100
    gregorien = 2 - siecle + siecle // 4
    entier = (math.floor(365.25 * (annee + 4716))
              + math.floor(30.6001 * (mois + 1))
              + jour + gregorien - 1524.5)
    return entier + heure_utc / 24.0


def _elements_solaires(siecles):
    """``(déclinaison_deg, équation_du_temps_min)`` pour ``T`` siècles juliens.

    Meeus ch. 25 (coordonnées du soleil) et ch. 22 (obliquité) ; c'est le
    cœur de la feuille de calcul NOAA. Les coefficients sont ceux, publiés,
    des séries de Meeus — aucun n'est ajusté ici.
    """
    # Longitude moyenne géométrique et anomalie moyenne du soleil (degrés).
    long_moyenne = (280.46646 + siecles * (36000.76983
                                           + siecles * 0.0003032)) % 360.0
    anomalie = 357.52911 + siecles * (35999.05029 - 0.0001537 * siecles)
    # Excentricité de l'orbite terrestre (sans dimension).
    excentricite = 0.016708634 - siecles * (0.000042037
                                            + 0.0000001267 * siecles)
    anomalie_rad = math.radians(anomalie)
    # Équation du centre : l'écart entre orbite réelle (ellipse) et moyenne.
    centre = (math.sin(anomalie_rad) * (1.914602 - siecles * (0.004817 + siecles * 0.000014))
              + math.sin(2 * anomalie_rad) * (0.019993 - 0.000101 * siecles)
              + math.sin(3 * anomalie_rad) * 0.000289)
    longitude_vraie = long_moyenne + centre
    # Nutation en longitude + aberration -> longitude APPARENTE.
    noeud = math.radians(125.04 - 1934.136 * siecles)
    longitude_apparente = longitude_vraie - 0.00569 - 0.00478 * math.sin(noeud)
    # Obliquité moyenne de l'écliptique, puis sa correction de nutation.
    obliquite_moyenne = 23.0 + (26.0 + (21.448 - siecles * (46.815 + siecles * (
        0.00059 - siecles * 0.001813))) / 60.0) / 60.0
    obliquite = obliquite_moyenne + 0.00256 * math.cos(noeud)
    obliquite_rad = math.radians(obliquite)
    declinaison = math.degrees(math.asin(_borner(
        math.sin(obliquite_rad) * math.sin(math.radians(longitude_apparente)))))
    # Équation du temps, en MINUTES de temps.
    y = math.tan(obliquite_rad / 2.0) ** 2
    long_rad = math.radians(long_moyenne)
    equation_du_temps = 4.0 * math.degrees(
        y * math.sin(2 * long_rad)
        - 2 * excentricite * math.sin(anomalie_rad)
        + 4 * excentricite * y * math.sin(anomalie_rad) * math.cos(2 * long_rad)
        - 0.5 * y * y * math.sin(4 * long_rad)
        - 1.25 * excentricite * excentricite * math.sin(2 * anomalie_rad))
    return declinaison, equation_du_temps


@dataclass(frozen=True)
class PositionSolaire:
    """Le soleil à un INSTANT et en un LIEU — tout en degrés, sauf mention.

    Immuable (le noyau n'a aucune globale mutable) et sans aucune dépendance :
    c'est le type que consomment les étapes horaires de la chaîne de pertes.
    """

    #: Hauteur GÉOMÉTRIQUE du soleil au-dessus de l'horizon (négative la nuit).
    elevation_deg: float
    #: Distance angulaire au zénith : toujours ``90 − elevation_deg``.
    zenith_deg: float
    #: Azimut compté DEPUIS LE SUD, convention PVGIS : 0 = sud, −90 = est,
    #: +90 = ouest, ±180 = nord. Négatif le matin, positif l'après-midi.
    azimut_depuis_sud_deg: float
    #: Déclinaison du soleil à cet instant (l'entrée du modèle, pas un réglage).
    declinaison_deg: float
    #: Équation du temps, en minutes de temps (midi vrai − midi moyen).
    equation_du_temps_min: float
    #: Angle horaire : 0 au midi solaire vrai, −15°/h avant, +15°/h après.
    angle_horaire_deg: float
    #: Heure solaire VRAIE du lieu, en heures dans [0, 24[.
    heure_solaire_vraie_h: float
    #: ``True`` sous ``ELEVATION_PLANCHER_DEG`` (5°, ``politique_pas.py:58``) :
    #: l'appelant OMET alors son poste en le nommant — ce module n'invente
    #: aucune valeur de remplacement et ne tronque rien.
    sous_le_plancher: bool

    def angle_incidence_deg(self, inclinaison_deg, azimut_plan_deg):
        """Angle entre le rayon direct et la NORMALE d'un plan incliné.

        ``inclinaison_deg`` = pente du plan (0 = horizontal, 90 = vertical) ;
        ``azimut_plan_deg`` = orientation du plan dans la MÊME convention que
        ``azimut_depuis_sud_deg`` (0 = sud, −90 = est, +90 = ouest).

            cos θ = cos z · cos β + sin z · sin β · cos(γ_soleil − γ_plan)

        (Duffie & Beckman, *Solar Engineering of Thermal Processes*, éq. 1.6.3,
        écrite ici avec l'angle zénithal.) Le résultat dépasse 90° quand le
        soleil est DERRIÈRE le plan : c'est une information, pas une erreur —
        l'appelant décide (pas de direct sur la face avant).
        """
        zenith = math.radians(self.zenith_deg)
        pente = math.radians(inclinaison_deg)
        ecart = math.radians(self.azimut_depuis_sud_deg - azimut_plan_deg)
        cos_theta = (math.cos(zenith) * math.cos(pente)
                     + math.sin(zenith) * math.sin(pente) * math.cos(ecart))
        return math.degrees(math.acos(_borner(cos_theta)))


def position_solaire(latitude_deg, longitude_deg, *,
                     annee, mois, jour, heure_utc):
    """Position du soleil à ``heure_utc`` (UTC, heures décimales) — cf. module.

    ``latitude_deg`` positive au nord, ``longitude_deg`` positive à l'EST de
    Greenwich (Casablanca = −7,6). ``heure_utc`` accepte les fractions : une
    série PVGIS horodatée à ``HH:09`` se lit ``HH + 9/60``, et c'est bien ce
    qu'il faut faire — arrondir à l'heure ronde coûte jusqu'à 2,3° d'élévation
    (mesuré sur la fixture de Casablanca).

    Lève ``EntreeInvalide`` — en français, en nommant le champ — sur une date
    ou une coordonnée hors domaine : le noyau REFUSE, il ne replie pas.
    """
    if not -90.0 <= latitude_deg <= 90.0:
        raise EntreeInvalide(
            "latitude hors domaine : %r (attendu entre −90 et 90)" % (latitude_deg,))
    if not -180.0 <= longitude_deg <= 180.0:
        raise EntreeInvalide(
            "longitude hors domaine : %r (attendu entre −180 et 180)" % (longitude_deg,))
    if not 1 <= int(mois) <= 12:
        raise EntreeInvalide("mois hors domaine : %r (attendu 1 à 12)" % (mois,))
    if not 1 <= int(jour) <= 31:
        raise EntreeInvalide("jour hors domaine : %r (attendu 1 à 31)" % (jour,))
    if not 0.0 <= float(heure_utc) < 24.0:
        raise EntreeInvalide(
            "heure_utc hors domaine : %r (attendu [0, 24[ en UTC)" % (heure_utc,))

    heure_utc = float(heure_utc)
    siecles = ((_jour_julien(int(annee), int(mois), int(jour), heure_utc)
                - JOUR_JULIEN_J2000) / JOURS_PAR_SIECLE_JULIEN)
    declinaison, equation_du_temps = _elements_solaires(siecles)

    # Heure solaire vraie : l'heure UTC, corrigée de la longitude (4 min par
    # degré vers l'est) et de l'équation du temps.
    minutes_solaires = (heure_utc * 60.0
                        + equation_du_temps
                        + longitude_deg / DEGRES_PAR_MINUTE_HORAIRE) % 1440.0
    angle_horaire = minutes_solaires * DEGRES_PAR_MINUTE_HORAIRE - 180.0

    phi = math.radians(latitude_deg)
    delta = math.radians(declinaison)
    h = math.radians(angle_horaire)
    cos_zenith = _borner(math.sin(phi) * math.sin(delta)
                         + math.cos(phi) * math.cos(delta) * math.cos(h))
    zenith = math.degrees(math.acos(cos_zenith))
    elevation = 90.0 - zenith

    denominateur = math.cos(phi) * math.sin(math.radians(zenith))
    if abs(denominateur) < 1e-12:
        # Soleil au zénith exact, ou observateur au pôle : l'azimut n'est plus
        # défini. On rend 0 (sud) plutôt qu'une valeur tirée d'un arrondi.
        azimut = 0.0
    else:
        ecart = math.degrees(math.acos(_borner(
            (math.sin(phi) * cos_zenith - math.sin(delta)) / denominateur)))
        azimut = ecart if angle_horaire > 0.0 else -ecart

    return PositionSolaire(
        elevation_deg=elevation,
        zenith_deg=zenith,
        azimut_depuis_sud_deg=azimut,
        declinaison_deg=declinaison,
        equation_du_temps_min=equation_du_temps,
        angle_horaire_deg=angle_horaire,
        heure_solaire_vraie_h=minutes_solaires / 60.0,
        sous_le_plancher=elevation < ELEVATION_PLANCHER_DEG,
    )
