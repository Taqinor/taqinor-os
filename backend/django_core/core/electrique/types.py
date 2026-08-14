# -*- coding: utf-8 -*-
"""PV33 — contrat de données GELÉ du moteur électrique : dataclasses IMMUABLES.

Pourquoi tout y est ``frozen`` (même raison que ``core.calepinage.types``) : une
étude électrique se recalcule des dizaines de fois par dossier (chaque
changement de calepinage rejoue la chaîne modules → chaînes → onduleurs →
protections → câbles). Si une spécification module ou une contrainte d'entrée
pouvait être MUTÉE en cours de route, deux calculs lancés dans le même processus
— deux tâches Celery, deux tests parallèles — se marcheraient dessus et le même
relevé rendrait deux calibres différents selon l'ordre d'exécution.

Conventions gravées ici :

* aucune collection mutable dans une dataclass : ``tuple`` partout, si bien
  qu'une ``EntreeElectrique`` est hachable et peut servir de clé de mémoïsation ;
* les tensions sont en VOLTS, les courants en AMPÈRES, les puissances module en
  WATTS-CRÊTE, les puissances onduleur en kW, les longueurs en MÈTRES, les
  températures en DEGRÉS CELSIUS — l'unité est dans le NOM de chaque champ ;
* AUCUN PRIX nulle part : le moteur ne manipule que des grandeurs électriques
  publiques et des quantités. Un prix qui entrerait ici ressortirait dans un
  schéma unifilaire remis au gestionnaire de réseau.
"""

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

__all__ = [
    "fr", "fr_v", "fr_a",
    "SpecModule", "SpecOnduleur", "GroupePan", "EntreeElectrique",
    "Chaine", "Protection", "Cable", "LigneNomenclature", "Ratio",
    "Conformite", "ResultatElectrique",
    "TEMPERATURE_STC_C", "TEMP_FROID_DEFAUT_C", "TEMP_CHAUD_DEFAUT_C",
    "REGIME_TT", "REGIME_TN", "REGIME_IT", "REGIMES_CONNUS",
]

# ------------------------------------------------------------------ constantes
#: Conditions STC : les Voc/Vmp/Isc/Imp d'une fiche module y sont donnés
#: (IEC 61215 — 1000 W/m², AM 1,5, température de cellule 25 °C).
TEMPERATURE_STC_C = 25.0

#: Température de cellule MINIMALE de dimensionnement (cas dimensionnant de la
#: borne HAUTE : le Voc monte quand il fait froid). −5 °C = hiver Maroc altitude.
TEMP_FROID_DEFAUT_C = -5.0

#: Température de cellule MAXIMALE de dimensionnement (cas dimensionnant de la
#: borne BASSE : le Vmp chute quand le module chauffe). 70 °C = module en été.
TEMP_CHAUD_DEFAUT_C = 70.0

#: Régimes de neutre (NF C 15-100 §312.2). Le TT est le régime des raccordements
#: BT au réseau de distribution public au Maroc comme en France.
REGIME_TT = "TT"
REGIME_TN = "TN"
REGIME_IT = "IT"
REGIMES_CONNUS = frozenset({REGIME_TT, REGIME_TN, REGIME_IT})


# ------------------------------------------------------------------ formatage
def fr(valeur, decimales=2):
    """Formatage FRANÇAIS d'un nombre : séparateur décimal virgule.

    Le moteur ne rédige jamais une phrase en dur : les motifs de refus, les
    alertes et la note de calcul sont GÉNÉRÉS à partir des nombres calculés.
    Ils doivent donc être lisibles en français (« 1,35 » et non « 1.35 »).
    """
    return ("%.*f" % (decimales, valeur)).replace(".", ",")


def fr_v(valeur, decimales=1):
    """« 812,5 V »."""
    return "%s V" % fr(valeur, decimales)


def fr_a(valeur, decimales=1):
    """« 13,8 A »."""
    return "%s A" % fr(valeur, decimales)


# --------------------------------------------------------------- spécifications
@dataclass(frozen=True)
class SpecModule:
    """Fiche électrique d'un module PV (valeurs STC de la fiche constructeur).

    ``temp_coeff_pmax_pct_c`` sert AUSSI de coefficient de dérive du Vmp : les
    fiches constructeur publient β(Voc) et γ(Pmax), rarement un coefficient Vmp
    propre, et pour le silicium cristallin γ(Pmax) en est la meilleure
    approximation disponible (c'est exactement la convention du calcul historique
    ``apps/ventes/solar_design.py``, qui nommait ce coefficient ``temp_coeff_vmp``).
    """

    vmp_v: float
    voc_v: float
    isc_a: float
    imp_a: float
    pmax_wc: float
    #: β(Voc) en %/°C, NÉGATIF — le Voc MONTE quand il fait froid.
    temp_coeff_voc_pct_c: float = -0.27
    #: γ(Pmax) en %/°C, NÉGATIF — sert de coefficient de dérive du Vmp.
    temp_coeff_pmax_pct_c: float = -0.35

    @property
    def temp_coeff_vmp_pct_c(self):
        """Coefficient de dérive du Vmp — cf. docstring de la classe."""
        return self.temp_coeff_pmax_pct_c

    def tension_voc_a(self, temperature_c):
        """Voc à une température de cellule donnée (dérive linéaire)."""
        return _tension_a_temperature(
            self.voc_v, self.temp_coeff_voc_pct_c, temperature_c)

    def tension_vmp_a(self, temperature_c):
        """Vmp à une température de cellule donnée (dérive linéaire)."""
        return _tension_a_temperature(
            self.vmp_v, self.temp_coeff_vmp_pct_c, temperature_c)


def _tension_a_temperature(v_stc, coeff_pct_par_c, temperature_c):
    """Tension à ``temperature_c`` depuis une tension STC (25 °C).

    ``coeff_pct_par_c`` est en %/°C (négatif) : à FROID (température < 25 °C)
    l'écart est négatif, le produit redevient positif, donc la tension MONTE.
    C'est le cas dimensionnant de la borne haute (sécurité matériel).
    """
    ecart = temperature_c - TEMPERATURE_STC_C
    return v_stc * (1.0 + (coeff_pct_par_c / 100.0) * ecart)


@dataclass(frozen=True)
class SpecOnduleur:
    """Fenêtre de fonctionnement d'un onduleur (fiche constructeur).

    ``v_max_abs`` est la tension DC MAXIMALE ABSOLUE : la dépasser détruit
    l'appareil, c'est la seule borne dont le franchissement est BLOQUANT et non
    une simple perte de production.
    """

    n_mppt: int
    mppt_v_min: float
    mppt_v_max: float
    v_max_abs: float
    i_max_mppt_a: float
    ac_kw: float
    #: 1 = monophasé 230 V, 3 = triphasé 400 V (NF C 15-100).
    phases: int = 1
    #: Rendement européen (%) — pondération EN 50530 des points de charge.
    rendement_euro_pct: float = 97.0
    #: Tension de DÉMARRAGE (V). À défaut, le bas de plage MPPT fait foi.
    v_demarrage_v: Optional[float] = None

    @property
    def tension_demarrage_v(self):
        """Tension de démarrage effective — repli sur le bas de plage MPPT."""
        if self.v_demarrage_v is None:
            return self.mppt_v_min
        return self.v_demarrage_v


@dataclass(frozen=True)
class GroupePan:
    """Un PAN de toiture : les modules d'une même orientation.

    Un pan n'est JAMAIS mélangé à un autre sur une même entrée MPPT : deux
    orientations différentes n'atteignent pas leur point de puissance maximale
    au même instant, et le MPPT commun suivrait le plus faible des deux toute
    la journée (perte permanente, invisible au bordereau).
    """

    label: str
    nb_modules: int
    azimut_deg: float
    inclinaison_deg: float


@dataclass(frozen=True)
class EntreeElectrique:
    """ENTRÉE COMPLÈTE du moteur — tout ce dont le calcul a besoin, rien de plus.

    Aucun modèle Django, aucun devis, aucun prix : l'adaptateur applicatif
    (``apps.ventes`` / ``apps.ao``) construit cette structure et lit le
    ``ResultatElectrique``. C'est ce qui rend le moteur testable sans base.
    """

    module: SpecModule
    onduleur: SpecOnduleur
    #: Un groupe par PAN — jamais deux orientations dans un même groupe.
    groupes: Tuple[GroupePan, ...] = ()
    #: Longueur de la liaison DC (m) — champ → onduleur, aller simple.
    dc_m: float = 0.0
    #: Longueur de la liaison AC (m) — onduleur → tableau, aller simple.
    ac_m: float = 0.0
    #: 1 = monophasé 230 V, 3 = triphasé 400 V.
    phases: int = 1
    #: Régime de neutre (NF C 15-100) — TT par défaut (raccordement BT public).
    regime: str = REGIME_TT
    batterie: bool = False
    temp_froid_c: float = TEMP_FROID_DEFAUT_C
    temp_chaud_c: float = TEMP_CHAUD_DEFAUT_C
    # ── contraintes optionnelles ──────────────────────────────────────────────
    #: Plafond de puissance CRÊTE raccordable sur UN onduleur (règle de dossier).
    plafond_kwc_par_onduleur: Optional[float] = None
    #: Longueur de chaîne IMPOSÉE — acceptée seulement si la physique l'admet.
    longueur_chaine_forcee: Optional[int] = None
    #: Site en zone KÉRAUNIQUE (densité de foudroiement élevée) — impose le
    #: parafoudre quelle que soit la longueur de liaison (UTE C 15-712-1 §7 :
    #: le critère de longueur critique dépend de la densité d'arcs Ng).
    zone_keraunique: bool = False

    @property
    def nb_modules(self):
        return sum(g.nb_modules for g in self.groupes)

    @property
    def puissance_kwc(self):
        return self.nb_modules * self.module.pmax_wc / 1000.0

    @property
    def tension_reseau_v(self):
        """230 V en monophasé, 400 V en triphasé (réseau BT)."""
        return 400.0 if int(self.phases or 1) == 3 else 230.0

    @property
    def facteur_phases(self):
        """√3 en triphasé, 1 en monophasé — facteur de la formule de courant."""
        return math.sqrt(3.0) if int(self.phases or 1) == 3 else 1.0


# ------------------------------------------------------------------- résultats
@dataclass(frozen=True)
class Chaine:
    """Une chaîne série calculée, RATTACHÉE à son pan et à son entrée MPPT."""

    repere: str
    pan: str
    nb_modules: int
    mppt: int
    voc_froid_v: float
    vmp_froid_v: float
    vmp_chaud_v: float
    vmp_stc_v: float
    isc_a: float
    imp_a: float
    puissance_kwc: float


@dataclass(frozen=True)
class Protection:
    """Un organe de protection EXIGÉ par une règle, qui reste CITÉE.

    ``regle_source`` n'est pas décoratif : un bureau de contrôle demande sur
    quelle règle repose un calibre, et une protection sans source est une
    protection que personne ne sait défendre.
    """

    repere: str
    designation: str
    calibre: str
    quantite: int
    regle_source: str


@dataclass(frozen=True)
class Cable:
    """Un câble dimensionné : section RETENUE + les deux critères qui l'imposent.

    Les deux critères sont publiés côte à côte (échauffement ``iz_a`` et chute
    de tension ``chute_tension_pct``) parce que c'est le PLUS CONTRAIGNANT des
    deux qui a choisi la section — le lecteur doit voir lequel.
    """

    repere: str
    designation: str
    section_mm2: float
    longueur_m: float
    nb_conducteurs: int
    ib_a: float
    in_a: Optional[float]
    iz_a: float
    chute_tension_pct: float
    chute_cible_pct: float
    chute_max_pct: float
    conforme: bool
    critere_dimensionnant: str
    regle_source: str


@dataclass(frozen=True)
class LigneNomenclature:
    """Une ligne de bordereau : QUANTITÉ et SPÉCIFICATION, JAMAIS un prix."""

    categorie: str
    designation: str
    quantite: float
    unite: str
    spec: str = ""


@dataclass(frozen=True)
class Ratio:
    """Un ratio PUBLIÉ AVEC SES BORNES — un nombre nu ne se relit pas.

    Le moteur publie DEUX ratios inverses l'un de l'autre car les deux
    conventions coexistent dans le dossier : DC/AC (convention onduleuriste,
    borne usuelle 1,35, alerte au-delà de 1,5) et AC/DC (convention CPS des
    marchés publics, fourchette 0,75-1,00). Ils sortent du MÊME calcul.
    """

    nom: str
    valeur: Optional[float]
    borne_min: Optional[float] = None
    borne_max: Optional[float] = None
    seuil_alerte: Optional[float] = None
    dans_bornes: bool = True

    @property
    def texte(self):
        if self.valeur is None:
            return "—"
        return fr(self.valeur, 2)

    @property
    def fourchette_texte(self):
        """« fourchette 0,75-1,00 » / « borne usuelle 1,35, alerte au-delà de 1,50 »."""
        morceaux = []
        if self.borne_min is not None and self.borne_max is not None:
            morceaux.append("fourchette %s-%s"
                            % (fr(self.borne_min, 2), fr(self.borne_max, 2)))
        elif self.borne_max is not None:
            morceaux.append("borne usuelle %s" % fr(self.borne_max, 2))
        elif self.borne_min is not None:
            morceaux.append("borne basse %s" % fr(self.borne_min, 2))
        if self.seuil_alerte is not None:
            morceaux.append("alerte au-delà de %s" % fr(self.seuil_alerte, 2))
        return ", ".join(morceaux)


@dataclass(frozen=True)
class Conformite:
    """Verdict de conformité — un BLOQUANT arrête le dossier, une ALERTE non.

    La distinction est la raison d'être de cette structure : dépasser la tension
    maximale absolue d'un onduleur détruit du matériel (bloquant), un ratio DC/AC
    un peu haut coûte quelques kWh d'écrêtage (alerte).
    """

    conforme: bool = True
    bloquants: Tuple[str, ...] = ()
    alertes: Tuple[str, ...] = ()

    @property
    def bloquant(self):
        return bool(self.bloquants)

    @property
    def alerte(self):
        """Le message affiché en tête : le premier bloquant, sinon la 1re alerte."""
        if self.bloquants:
            return self.bloquants[0]
        if self.alertes:
            return self.alertes[0]
        return ""


@dataclass(frozen=True)
class ResultatElectrique:
    """SORTIE COMPLÈTE du moteur — tout ce qu'un dossier technique consomme."""

    chaines: Tuple[Chaine, ...] = ()
    conformite: Conformite = field(default_factory=Conformite)
    ratio_dc_ac: Optional[Ratio] = None
    ratio_ac_dc: Optional[Ratio] = None
    protections: Tuple[Protection, ...] = ()
    cables: Tuple[Cable, ...] = ()
    bom: Tuple[LigneNomenclature, ...] = ()
    note: Tuple[str, ...] = ()
    #: Projection PRÊTE À AFFICHER pour les tiroirs de l'écran (PV38).
    #: NB : ``default_factory`` obligatoire — Python 3.11 (la CI) refuse un
    #: ``MappingProxyType`` comme défaut direct de dataclass (3.12+ l'accepte,
    #: d'où le vert local trompeur).
    tiroirs: Mapping = field(default_factory=lambda: MappingProxyType({}))
    version_moteur: str = ""
    schema_version: int = 0

    @property
    def puissance_kwc(self):
        return sum(c.puissance_kwc for c in self.chaines)

    @property
    def nb_chaines(self):
        return len(self.chaines)
