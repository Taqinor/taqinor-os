# -*- coding: utf-8 -*-
"""CALX159 — l'ombre qu'une rangée porte SUR LA SUIVANTE, enfin CHIFFRÉE.

CE QUE LE DÉPÔT SAVAIT DÉJÀ FAIRE, ET CE QU'IL NE SAVAIT PAS
-------------------------------------------------------------
``core/calepinage/politique_pas.py`` sait ESPACER les rangées pour qu'elles
ne s'ombrent pas : ``AntiOmbrage`` (``politique_pas.py:140-344``) calcule la
longueur d'ombre au solstice d'hiver et en fait le vide entre deux rangées,
à l'élévation de dimensionnement ``ELEVATION_DIMENSIONNEMENT_DEG`` (21°,
``politique_pas.py:45``). Cette élévation est un REPLI « Maroc moyen » et une
règle d'ESPACEMENT : elle ne dit rien de l'ombre RÉSIDUELLE, celle qui
subsiste toutes les heures où le soleil est plus bas que l'hypothèse de
dimensionnement. Aucune fonction du noyau ne rendait, jusqu'ici, une FRACTION
OMBRÉE à une heure donnée — et sans elle, la chaîne de pertes n'a aucune
étape « inter-rangées » à appliquer.

Ce module comble exactement ce trou, et rien de plus : il rend, pour une
géométrie de rangées et une position de soleil, la part de la table aval qui
est à l'ombre de la table amont. Il ne décide d'aucun espacement (c'est
``politique_pas``), n'ouvre aucune série météo (c'est l'étape,
``apps/calepinage/services/etapes/inter_rangees.py``) et ne porte AUCUN
coefficient (D-CALX 7).

LA GÉOMÉTRIE : UNE PROJECTION DANS LE PLAN DE PROFIL
------------------------------------------------------
Tout se joue dans le **plan de profil** : le plan VERTICAL perpendiculaire à
l'axe des rangées. Les rangées sont supposées LONGUES devant leur pas (le
problème est à deux dimensions ; les effets de bout de rangée ne sont pas
modélisés — voir « ce que ce module ne fait pas »).

Notations, toutes sorties de la géométrie du document :

* ``L`` = ``longueur_table_m``, le côté de la table DANS LA PENTE ;
* ``β`` = ``inclinaison_deg``, l'inclinaison de la table ;
* ``h = L·sin β`` la HAUTEUR de l'arête haute au-dessus du plan de pose, et
  ``d = L·cos β`` son EMPREINTE au sol. Ces deux grandeurs ne sont pas
  réécrites ici : elles sont demandées à ``AntiOmbrage.hauteur_module_m`` et
  ``AntiOmbrage.empreinte_pan_m``, les deux seules définitions du dépôt ;
* ``D`` = ``pas_m``, le pas de rangée (arête basse à arête basse), et
  ``g = D − d`` le JEU LIBRE entre l'empreinte d'une table et l'arête basse
  de la suivante — le ``gapM`` que ``apps/web/src/lib/shadingEngine.ts``
  (``rowSelfShading``, ``:646-670``) calcule déjà côté atelier.

La position du soleil n'entre PAS par son élévation brute mais par son
**angle de profil** ``α_p``, l'élévation vue dans le plan de profil :

    tan α_p = tan α / cos(γ_soleil − γ_plan)

(``α`` élévation, ``γ`` azimuts dans la convention PVGIS du dépôt : 0 = sud,
−90 = est, +90 = ouest ; c'est l'angle de profil des calculs d'ombrage de
Duffie & Beckman, *Solar Engineering of Thermal Processes*, déjà cité par
``core/calepinage/soleil.py`` pour l'angle d'incidence.) Ce facteur
``cos(γ_soleil − γ_plan)`` est EXACTEMENT le terme directionnel que
``AntiOmbrage.longueur_ombre_m`` applique quand la latitude du site lui est
transmise (``|cos γ|``, ``politique_pas.py:239``) : les deux calculs parlent
de la même ombre.

Un point de la table aval, à la distance ``x`` de son arête basse EN SUIVANT
LA PENTE, est à la hauteur ``x·sin β`` et à la distance horizontale
``g + x·cos β`` de l'arête haute amont. Il est à l'ombre tant que le rayon
rasant l'arête haute passe AU-DESSUS de lui :

    h − x·sin β  ≥  (g + x·cos β) · tan α_p

d'où la longueur ombrée, puis la fraction rendue :

    x_ombrée = (h − g·tan α_p) / (sin β + cos β · tan α_p)
    fraction = x_ombrée / L,  bornée à [0, 1]

Deux propriétés en découlent, et elles sont TESTÉES
(``core/tests/test_calepinage_ombre_rangees.py``) :

1. **la fraction DÉCROÎT quand le soleil monte** — la dérivée du numérateur
   par ``tan α_p`` vaut ``−(g·sin β + h·cos β)``, strictement négative dès
   que la table a du relief et que les rangées ne se chevauchent pas ;
1bis. **l'arête HAUTE n'est jamais ombrée par une rangée identique** — elle
   est à la même hauteur ``h`` que l'arête haute amont, et le rayon qui rase
   celle-ci ne peut pas passer au-dessus de celle-là. La fraction reste donc
   strictement inférieure à 1 pour tout pas positif, et ne tend vers 1 que
   lorsque le pas tend vers zéro. Le plafond de :func:`fraction_ombree` est
   une BORNE d'arithmétique, pas un cas de figure ;
2. **elle s'annule au-dessus de l'angle de profil CRITIQUE**
   ``α_p,crit = arctan(h / g)`` — c'est :func:`elevation_critique_deg`, et
   c'est le MÊME seuil que celui que ``AntiOmbrage`` vise en posant son pas :
   avec ``marge_m = 0``, ``pas_de_rangee_m`` rend ``d + h/tan(élévation de
   dimensionnement)``, donc ``g = h/tan(élévation)`` et ``arctan(h/g)`` est
   l'élévation de dimensionnement elle-même. Le dimensionnement et la mesure
   se rejoignent sans qu'aucune constante ne soit recopiée.

LES DEUX EXTENSIONS DEMANDÉES
-------------------------------
* **Châssis EST-OUEST (deux plans opposés).** Un chevron dos-à-dos porte un
  pan est et un pan ouest ; les chevrons se répètent le long de l'axe
  est-ouest. Pour le pan EST d'un chevron, l'obstacle est le FAÎTE du chevron
  voisin côté est : il est à la hauteur ``h`` et à la distance horizontale
  ``D − d`` de l'arête basse du pan — soit le même jeu ``g`` que pour une
  rangée plein sud, à condition que ``pas_m`` soit le pas de RÉPÉTITION des
  chevrons (arête basse d'un pan est à arête basse du pan est suivant, c'est
  ``AntiOmbrage.pas_de_rangee_m`` du kit dos-à-dos). La formule est donc
  inchangée : seule l'orientation du plan change.
  :func:`fraction_ombree_est_ouest` rend le couple (pan est, pan ouest) ;
  le pan que le soleil ne voit pas rend 0, parce qu'une face sans direct n'a
  pas d'ombre portée à retrancher — c'est l'angle d'incidence, pas
  l'inter-rangées, qui l'éteint.
* **Pose AU SOL.** Le plan de pose est ici le SOL (``poseSurfaces[]`` de
  genre ``sol``, ou une terrasse) : la géométrie est la même, à ceci près que
  le pas vient du moteur (``engine.rowPitchM``, CAL88) et non d'un toit. Rien
  à changer dans la formule — c'est le sens de « géométrie plane ». Une pose
  AFFLEURANTE sur toit en pente (``geometry.flush``) a une inclinaison nulle
  par rapport à son plan de pose : ``h = 0`` et la fraction vaut 0, par
  géométrie et non par défaut.

CE QUE CE MODULE NE FAIT PAS
------------------------------
* **Aucun lancer de rayons.** ``apps/web/src/lib/shadingEngine.ts`` en fait
  un (``isRowSelfShadedAt``, ``:622-638``) mais il rend un BOOLÉEN — ombré ou
  non — et jamais une fraction : il répond « à quelle heure de l'année une
  rangée commence-t-elle à en ombrer une autre ? », pas « combien perd-on ».
  Sa géométrie d'entrée est la même (``rowPitchM``, ``panelSlopeLenM``,
  ``tiltDeg``, ``gapM = pitch − slope·cos β``) et c'est ce qui rend les deux
  lectures comparables ; sa sortie ne l'est pas, et rien n'en est porté ici.
* **Aucun effet de bout de rangée**, aucune obstruction autre que la rangée
  amont, aucun diffus : la part diffuse reçue par une cellule ombrée est
  l'affaire de l'étape, qui n'applique cette fraction QU'À la composante
  directe.
* **Aucun électrique.** Une fraction de SURFACE ombrée n'est pas une perte de
  PUISSANCE : la dispersion I-V créée par l'ombre est un poste distinct de la
  chaîne (``mismatch_ombrage``). Ce module ne la préjuge pas.
"""

import math
from dataclasses import dataclass

from core.calepinage.politique_pas import AntiOmbrage

__all__ = [
    "CONVENTION_AZIMUT",
    "AZIMUT_PLAN_EST_DEG",
    "AZIMUT_PLAN_OUEST_DEG",
    "TableInclinee",
    "hauteur_table_m",
    "empreinte_table_m",
    "jeu_libre_m",
    "angle_profil_deg",
    "elevation_critique_deg",
    "fraction_ombree",
    "fraction_ombree_est_ouest",
]

#: La convention d'azimut de CE module, celle de PVGIS et de tout le reste de
#: la chaîne de pertes : 0 = sud, −90 = est, +90 = ouest. Elle est NOMMÉE
#: parce que ``politique_pas.position_solaire_solstice`` porte la convention
#: INVERSE sur son azimut (``soleil.py:44-48``) : les deux ne se mélangent
#: jamais.
CONVENTION_AZIMUT = "pvgis_sud_0_est_-90"

#: Les deux plans d'un châssis dos-à-dos, dans cette convention.
AZIMUT_PLAN_EST_DEG = -90.0
AZIMUT_PLAN_OUEST_DEG = 90.0

#: L'unique porteuse des deux helpers de géométrie de ``politique_pas``
#: (``hauteur_module_m`` et ``empreinte_pan_m`` ne lisent QUE le kit reçu,
#: jamais un réglage de la politique) : les rappeler ici évite d'écrire une
#: SECONDE fois ``L·sin β`` et ``L·cos β`` dans le dépôt.
_HELPERS_GEOMETRIE = AntiOmbrage()


def _borner(valeur, bas=0.0, haut=1.0):
    """Ramène une fraction dans ses bornes : l'arrondi flottant en sort."""
    return max(bas, min(haut, valeur))


def _ecart_azimut_deg(azimut_soleil_deg, azimut_plan_deg):
    """L'écart d'azimut soleil − plan, ramené dans ]−180, 180]."""
    ecart = (float(azimut_soleil_deg) - float(azimut_plan_deg) + 180.0) % 360.0
    return ecart - 180.0


@dataclass(frozen=True)
class TableInclinee:
    """Une TABLE de rangée réduite à ce dont l'ombre dépend.

    Les deux attributs portent les noms que ``core.calepinage.types.Kit``
    emploie, ce qui permet de passer cet objet AUX MÉTHODES de
    ``politique_pas.AntiOmbrage`` sans adaptateur : c'est ce qui garantit
    qu'il n'existe qu'UNE définition de la hauteur et de l'empreinte d'une
    table dans le noyau.
    """

    #: Côté de la table dans le sens de la pente (m).
    cote_dans_la_pente_m: float
    #: Inclinaison de la table (degrés).
    inclinaison_deg: float

    @property
    def hauteur_m(self):
        """Hauteur de l'arête HAUTE au-dessus du plan de pose (m)."""
        return _HELPERS_GEOMETRIE.hauteur_module_m(self)

    @property
    def emprise_transversale_m(self):
        """Empreinte au sol de la table (m) — ``politique_pas`` la lit sous
        ce nom pour composer un pas de rangée publiable."""
        return _HELPERS_GEOMETRIE.empreinte_pan_m(self)


def hauteur_table_m(longueur_table_m, inclinaison_deg):
    """``L·sin β`` — la hauteur de l'arête haute, en mètres."""
    return TableInclinee(float(longueur_table_m),
                         float(inclinaison_deg)).hauteur_m


def empreinte_table_m(longueur_table_m, inclinaison_deg):
    """``L·cos β`` — l'empreinte au sol de la table, en mètres."""
    return TableInclinee(float(longueur_table_m),
                         float(inclinaison_deg)).emprise_transversale_m


def jeu_libre_m(pas_m, longueur_table_m, inclinaison_deg):
    """``g = D − d`` : le vide entre deux tables, en mètres.

    Négatif quand les rangées se chevauchent — c'est une information, pas une
    erreur : la fraction ombrée sature alors à 1 toute la journée.
    """
    return float(pas_m) - empreinte_table_m(longueur_table_m, inclinaison_deg)


def _tangente_profil(elevation_deg, azimut_soleil_deg, azimut_plan_deg):
    """``tan α_p``, ou ``None`` quand la face avant ne voit pas le soleil."""
    elevation = float(elevation_deg)
    if elevation <= 0.0 or elevation >= 90.0:
        # Sous l'horizon : rien à ombrer. Au zénith exact : le plan de profil
        # n'a plus de direction, et aucune ombre ne porte au-delà de
        # l'empreinte.
        return None
    ecart = _ecart_azimut_deg(azimut_soleil_deg, azimut_plan_deg)
    if abs(ecart) >= 90.0:
        # Soleil DERRIÈRE le plan : la face avant ne reçoit aucun direct, il
        # n'y a donc aucun direct à retrancher.
        return None
    cosinus = math.cos(math.radians(ecart))
    if cosinus <= 0.0:
        return None
    return math.tan(math.radians(elevation)) / cosinus


def angle_profil_deg(elevation_deg, azimut_soleil_deg, azimut_plan_deg):
    """L'ANGLE DE PROFIL ``α_p`` en degrés, ou ``None``.

    C'est l'élévation du soleil VUE DANS LE PLAN DE PROFIL (le plan vertical
    perpendiculaire aux rangées) : ``tan α_p = tan α / cos(γ_soleil −
    γ_plan)``. ``None`` signifie « aucun direct sur la face avant » (soleil
    sous l'horizon, rasant, ou derrière le plan) — jamais 0°, qui se lirait
    « soleil à l'horizon, ombre infinie ».
    """
    tangente = _tangente_profil(elevation_deg, azimut_soleil_deg,
                                azimut_plan_deg)
    if tangente is None:
        return None
    return math.degrees(math.atan(tangente))


def elevation_critique_deg(pas_m, longueur_table_m, inclinaison_deg):
    """L'angle de profil de NON-OMBRAGE ``arctan(h / g)``, en degrés.

    Au-dessus de cet angle, :func:`fraction_ombree` vaut exactement 0 : c'est
    le seuil que ``politique_pas.AntiOmbrage`` VISE en fixant son pas (avec
    ``marge_m = 0``, l'angle rendu ici est son élévation de dimensionnement).
    Rendu par ``atan2`` : des rangées jointives ou chevauchantes (``g ≤ 0``)
    donnent un angle ``≥ 90°``, c'est-à-dire « ombrées à toute heure », et
    une table sans relief (``h ≤ 0``) donne 0°, c'est-à-dire « jamais
    ombrée ».
    """
    hauteur = hauteur_table_m(longueur_table_m, inclinaison_deg)
    if hauteur <= 0.0:
        return 0.0
    return math.degrees(math.atan2(
        hauteur, jeu_libre_m(pas_m, longueur_table_m, inclinaison_deg)))


def fraction_ombree(pas_m, longueur_table_m, inclinaison_deg,
                    azimut_plan_deg, elevation_deg, azimut_soleil_deg):
    """La part de la table AVAL à l'ombre de la table AMONT, dans [0, 1].

    Args:
        pas_m: pas de rangée ``D`` (m), arête basse à arête basse.
        longueur_table_m: côté ``L`` de la table dans la pente (m).
        inclinaison_deg: inclinaison ``β`` de la table (degrés).
        azimut_plan_deg: azimut du plan, convention :data:`CONVENTION_AZIMUT`.
        elevation_deg: élévation du soleil (degrés).
        azimut_soleil_deg: azimut du soleil, même convention que le plan —
            c'est ``PositionSolaire.azimut_depuis_sud_deg`` (CALX146).

    Returns:
        float dans [0, 1] — 0 quand rien n'est ombré (soleil au-dessus de
        :func:`elevation_critique_deg`, table sans relief, ou soleil derrière
        le plan). La valeur 1 est la BORNE arithmétique : pour un pas positif
        et une rangée amont identique, elle n'est jamais atteinte (cf. le
        module).

    La fraction est une part de SURFACE, jamais une perte de puissance
    (cf. le module). Elle n'est bornée que par la géométrie : aucun plancher,
    aucun plafond métier n'est appliqué.
    """
    longueur = float(longueur_table_m)
    if longueur <= 0.0:
        return 0.0
    table = TableInclinee(longueur, float(inclinaison_deg))
    hauteur = table.hauteur_m
    if hauteur <= 0.0:
        # Table posée à plat sur son plan (pose affleurante) : pas de relief,
        # donc pas d'ombre portée d'une rangée sur l'autre.
        return 0.0
    tangente = _tangente_profil(elevation_deg, azimut_soleil_deg,
                                azimut_plan_deg)
    if tangente is None or tangente <= 0.0:
        return 0.0
    pente = math.radians(float(inclinaison_deg))
    denominateur = math.sin(pente) + tangente * math.cos(pente)
    if denominateur <= 0.0:
        return 0.0
    jeu = float(pas_m) - table.emprise_transversale_m
    return _borner((hauteur - jeu * tangente) / denominateur / longueur)


def fraction_ombree_est_ouest(pas_m, longueur_table_m, inclinaison_deg,
                              elevation_deg, azimut_soleil_deg,
                              azimut_plan_est_deg=AZIMUT_PLAN_EST_DEG):
    """``(fraction pan EST, fraction pan OUEST)`` d'un châssis dos-à-dos.

    ``pas_m`` est le pas de RÉPÉTITION des chevrons (arête basse d'un pan est
    à arête basse du pan est suivant) : l'obstacle d'un pan est le FAÎTE du
    chevron voisin, qui se trouve à ``pas_m − L·cos β`` de son arête basse —
    le même jeu ``g`` que pour une rangée plein sud (cf. le module). Le pan
    que le soleil ne voit pas rend 0.
    """
    est = fraction_ombree(pas_m, longueur_table_m, inclinaison_deg,
                          float(azimut_plan_est_deg), elevation_deg,
                          azimut_soleil_deg)
    ouest = fraction_ombree(pas_m, longueur_table_m, inclinaison_deg,
                            float(azimut_plan_est_deg) + 180.0, elevation_deg,
                            azimut_soleil_deg)
    return est, ouest
