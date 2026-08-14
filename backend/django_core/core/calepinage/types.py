# -*- coding: utf-8 -*-
"""AOF34 — contrat de données GELÉ du moteur : dataclasses IMMUABLES.

Pourquoi ce module existe et pourquoi tout y est ``frozen`` : le script
d'origine ``planche_05H`` reconfigurait le moteur en MUTANT les globales du
module (``C.MOD_L = 1.134``). Deux calculs lancés dans le même processus —
deux tâches Celery, deux tests parallèles — se marchent dessus, et le même
relevé peut rendre deux comptes différents selon l'ordre d'exécution. Ici,
TOUTE configuration passe par un ``Parametres`` immuable passé en ARGUMENT ;
aucun module du moteur ne porte d'état.

Second constat traité : les scripts de dépôt écrivaient leurs planches dans un
chemin OneDrive ABSOLU sans ``makedirs`` et plantaient sur toute autre machine.
Le moteur ne rend donc jamais un fichier : il rend des objets, et le rendu rend
des OCTETS que l'appelant écrit où il veut.

Conventions gravées ici :

* toutes les longueurs sont en MÈTRES ; le millimètre est l'unité de
  comparaison (``units.arrondi_mm``) ;
* aucune collection mutable dans une dataclass : ``tuple`` partout, si bien
  qu'un ``Parametres`` est hachable et peut servir de clé de mémoïsation ;
* l'axe d'une rangée n'est JAMAIS implicite (voir ``Axe`` et ``orientation``).
"""

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional, Tuple

from core.calepinage.units import TOL_LONGUEUR_M

__all__ = [
    "Axe", "OrientationModule", "Provenance", "TypeObstacle", "NatureZone",
    "ModePose", "MethodePreuve", "Confiance", "Kit", "Obstacle", "Zone",
    "Rives", "PolitiquePas", "Parametres", "Rangee", "Table", "Plan",
    "Preuve", "Marges", "Sensibilite", "Marche", "Recommandation", "Resultat",
    "KIT_AO_PORTRAIT", "KIT_AO_PAYSAGE", "KIT_VILLA_720",
    "remplacer",
]


# ==================================================================== énumérés
class Axe(Enum):
    """Axe cardinal d'une rangée ou d'un faîtage — jamais implicite."""

    NORD_SUD = "NORD_SUD"
    EST_OUEST = "EST_OUEST"

    @property
    def perpendiculaire(self):
        return Axe.EST_OUEST if self is Axe.NORD_SUD else Axe.NORD_SUD


class OrientationModule(Enum):
    """Pose du module DANS la table.

    * ``PORTRAIT`` — le grand côté monte la pente ; le pas le long de la rangée
      vaut le PETIT côté (1,134 sur le kit AO).
    * ``PAYSAGE`` — le grand côté est horizontal ; le pas le long de la rangée
      vaut le GRAND côté (2,382 sur le kit AO).
    """

    PORTRAIT = "PORTRAIT"
    PAYSAGE = "PAYSAGE"


class Provenance(Enum):
    """D'où vient la géométrie d'un obstacle — 6 valeurs, jamais un booléen.

    C'est la version moteur de l'``assert len(OBS) == 28`` du script d'origine :
    un plan ne devient engageable que si aucun objet du compte ne vient du PLAN
    ni d'une DEVINETTE. Sur l'aile L, les deux emprises jamais relevées
    (« GRECT » deviné, « PAN » venu du plan) valent 12 modules.
    """

    RELEVE = "RELEVE"
    RELEVE_DOUTEUX = "RELEVE_DOUTEUX"
    DECLARE_CLIENT = "DECLARE_CLIENT"
    PLAN = "PLAN"
    DEVINE = "DEVINE"
    ECARTE = "ECARTE"


class TypeObstacle(Enum):
    """13 types métier ; chacun porte un dégagement PAR DÉFAUT (``obstacles``)."""

    CAISSON_BETON = "CAISSON_BETON"
    CAGE_ESCALIER = "CAGE_ESCALIER"
    EDICULE = "EDICULE"
    SOUCHE = "SOUCHE"
    CLIMATISEUR = "CLIMATISEUR"
    LANTERNEAU = "LANTERNEAU"
    ACROTERE = "ACROTERE"
    JOINT_DILATATION = "JOINT_DILATATION"
    MURET = "MURET"
    ANTENNE = "ANTENNE"
    GARDE_CORPS = "GARDE_CORPS"
    EVACUATION_EU = "EVACUATION_EU"
    NATURE_INCONNUE = "NATURE_INCONNUE"


class NatureZone(Enum):
    """4 natures de contour (``zones.py``)."""

    ENVELOPPE = "ENVELOPPE"
    INTERDITE = "INTERDITE"
    RESERVEE = "RESERVEE"
    PREFEREE = "PREFEREE"


class ModePose(Enum):
    """``PosePlan`` du plan de conception — comment les rangées sont posées.

    ``RANGEES_IMPOSEES_UTILISATEUR`` est le troisième mode (PV29) : le
    dessinateur FOURNIT ses rangées et le moteur se contente de les COMPTER
    puis de les situer face à l'optimum. Il ne s'agit pas d'une méthode de
    recherche de plus : la preuve rendue porte ``IMPOSE_UTILISATEUR``, donc
    ``optimal`` reste FAUX et l'écart au DP est publié — un plan imposé ne peut
    structurellement pas se réclamer d'un « optimum prouvé ».
    """

    RANGEES_EXPLICITES_DP = "rangees_explicites_dp"
    RANGEES_UNIFORMES_PHASE = "rangees_uniformes_phase"
    RANGEES_IMPOSEES_UTILISATEUR = "rangees_imposees_utilisateur"


#: Alias historique du plan : la tâche AOF34 nomme cet énuméré ``PosePlan``.
PosePlan = ModePose


class MethodePreuve(Enum):
    """Vocabulaire VERROUILLÉ de la preuve (risque commercial n°1).

    « Optimum prouvé » n'est accessible QUE sur une méthode exacte. Une
    heuristique ne rend que « meilleur plan trouvé + borne supérieure ».
    """

    DP_EXACT_1CM = "dp_exact_1cm"
    EXHAUSTIF_PAR_SEGMENT = "exhaustif_par_segment"
    HEURISTIQUE_BORNEE = "heuristique_bornee"
    IMPOSE_UTILISATEUR = "impose_utilisateur"

    @property
    def exacte(self):
        return self in (MethodePreuve.DP_EXACT_1CM,
                        MethodePreuve.EXHAUSTIF_PAR_SEGMENT)


class Confiance(Enum):
    HAUTE = "HAUTE"
    MOYENNE = "MOYENNE"
    BASSE = "BASSE"


# ======================================================================== kit
@dataclass(frozen=True)
class Kit:
    """Un type de table : géométrie DÉRIVÉE des modules, jamais saisie.

    Le kit AO est une table dos-à-dos de 2 modules 2,382 × 1,134 à 15° :
    en PORTRAIT elle fait 1,134 de pas et 4,70 d'emprise transversale, en
    PAYSAGE 2,382 de pas et 2,25 d'emprise. Ces deux chiffres sont RECALCULÉS
    ici (``2 × côté × cos(15°) + faîtage``) et non recopiés — c'est ce qui rend
    un kit villa à 1 module 2,384 × 1,303 à 13° exprimable sans code neuf.
    """

    code: str
    libelle: str
    module_long_m: float
    module_court_m: float
    puissance_module_wc: float
    inclinaison_deg: float
    orientation: OrientationModule
    modules_par_table: int = 2
    #: jeu de faîtage entre les deux plans de modules d'une table dos-à-dos.
    faitage_m: float = 0.0

    def __post_init__(self):
        if self.modules_par_table < 1:
            raise ValueError("une table porte au moins un module")
        if self.module_long_m <= 0 or self.module_court_m <= 0:
            raise ValueError("dimensions de module strictement positives")
        if self.module_long_m < self.module_court_m:
            raise ValueError("module_long_m doit être le GRAND côté")
        if not (0.0 <= self.inclinaison_deg < 90.0):
            raise ValueError("inclinaison hors bornes")

    # ---------------------------------------------------------- géométrie
    @property
    def cote_le_long_rangee_m(self):
        """Pas de pose LE LONG de la rangée (emprise d'une table sur l'axe)."""
        return (self.module_court_m if self.orientation is OrientationModule.PORTRAIT
                else self.module_long_m)

    @property
    def cote_dans_la_pente_m(self):
        """Côté du module qui monte la pente (projeté par l'inclinaison)."""
        return (self.module_long_m if self.orientation is OrientationModule.PORTRAIT
                else self.module_court_m)

    @property
    def emprise_transversale_m(self):
        """Largeur de la table perpendiculairement à la rangée.

        ``2 × côté_pente × cos(inclinaison) + faîtage`` pour une table
        dos-à-dos ; ``côté_pente × cos(inclinaison)`` pour un kit villa.
        """
        projete = self.cote_dans_la_pente_m * math.cos(math.radians(self.inclinaison_deg))
        return self.modules_par_table * projete + self.faitage_m

    @property
    def modules_par_pas(self):
        """Nombre de modules gagnés par pas de pose (2 pour une table dos-à-dos)."""
        return self.modules_par_table

    @property
    def puissance_table_wc(self):
        return self.modules_par_table * self.puissance_module_wc

    @property
    def axe_faitage(self):
        """Axe du FAÎTAGE d'une table dos-à-dos — voir ``orientation.py``.

        Une table dos-à-dos EST-OUEST (un module face est, l'autre face ouest)
        a forcément son faîtage NORD-SUD ; sa rangée court donc nord-sud. Le
        kit ne connaît pas les points cardinaux : c'est ``Parametres.axe_rangee``
        qui les porte, et ``orientation.verifier`` qui interdit la combinaison
        inconstructible.
        """
        return Axe.NORD_SUD if self.modules_par_table >= 2 else Axe.EST_OUEST

    @property
    def dos_a_dos(self):
        return self.modules_par_table >= 2


#: Kit AO — table dos-à-dos 2 × 625 Wc, modules 2,382 × 1,134 à 15°, PORTRAIT :
#: pas 1,134 le long de la rangée, emprise transversale 4,70.
KIT_AO_PORTRAIT = Kit(
    code="AO_PORTRAIT",
    libelle="Table dos-à-dos 2 modules 625 Wc — portrait (1,134 × 4,70)",
    module_long_m=2.382,
    module_court_m=1.134,
    puissance_module_wc=625.0,
    inclinaison_deg=15.0,
    orientation=OrientationModule.PORTRAIT,
    modules_par_table=2,
    faitage_m=0.098,
)

#: Kit AO — même table posée en PAYSAGE : pas 2,382, emprise transversale 2,25.
KIT_AO_PAYSAGE = Kit(
    code="AO_PAYSAGE",
    libelle="Table dos-à-dos 2 modules 625 Wc — paysage (2,382 × 2,25)",
    module_long_m=2.382,
    module_court_m=1.134,
    puissance_module_wc=625.0,
    inclinaison_deg=15.0,
    orientation=OrientationModule.PAYSAGE,
    modules_par_table=2,
    faitage_m=0.059,
)

#: Kit VILLA — UN module 720 Wc 2,384 × 1,303 à 13° (le calepinage villa n'est
#: pas un autre moteur : c'est ce kit-ci plus une politique de pas anti-ombrage).
KIT_VILLA_720 = Kit(
    code="VILLA_720",
    libelle="Module unique 720 Wc 2,384 × 1,303 à 13° (villa)",
    module_long_m=2.384,
    module_court_m=1.303,
    puissance_module_wc=720.0,
    inclinaison_deg=13.0,
    orientation=OrientationModule.PORTRAIT,
    modules_par_table=1,
    faitage_m=0.0,
)


# ================================================================== obstacles
@dataclass(frozen=True)
class Obstacle:
    """Rectangle bloquant, dans le repère (axe de rangée, axe transversal).

    ``x`` court LE LONG de la rangée, ``y`` en travers. ``degagement_m`` vaut
    ``None`` tant que ``obstacles.degagement_effectif`` ne l'a pas dérivé de
    (type, provenance) : le moteur ne devine jamais un dégagement en silence.
    """

    repere: str
    x0: float
    x1: float
    y0: float
    y1: float
    type_obstacle: TypeObstacle = TypeObstacle.NATURE_INCONNUE
    provenance: Provenance = Provenance.RELEVE
    degagement_m: Optional[float] = None
    hauteur_m: Optional[float] = None
    #: règle qui a produit le dégagement retenu (tracé, jamais reconstitué).
    regle_appliquee: str = ""

    def __post_init__(self):
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("obstacle %s : bornes inversées" % self.repere)

    @property
    def largeur_m(self):
        return self.x1 - self.x0

    @property
    def profondeur_m(self):
        return self.y1 - self.y0

    @property
    def ecarte(self):
        return self.provenance is Provenance.ECARTE


# ====================================================================== zones
@dataclass(frozen=True)
class Zone:
    """Contour polygonal NOMMÉ (``zones.py`` en donne la sémantique)."""

    repere: str
    nature: NatureZone
    sommets: Tuple[Tuple[float, float], ...]
    hauteur_m: Optional[float] = None
    retrait_m: float = 0.0

    def __post_init__(self):
        if len(self.sommets) < 3:
            raise ValueError("zone %s : au moins 3 sommets" % self.repere)


@dataclass(frozen=True)
class Rives:
    """Les 4 rives NOMMÉES — jamais un paramètre ``rive`` unique.

    Le seul bug de cohérence documenté du moteur historique venait d'un
    ``end_rive`` dont le défaut divergeait entre ``count_band`` (0,5) et
    ``fill_band`` (0,0) : compté ≠ dessiné. Nommer les quatre tue la classe.
    """

    laterale_m: float = 0.35
    extremite_m: float = 0.35
    acrotere_m: float = 0.0
    joint_m: float = 0.0

    def __post_init__(self):
        for nom in ("laterale_m", "extremite_m", "acrotere_m", "joint_m"):
            if getattr(self, nom) < 0:
                raise ValueError("rive %s négative" % nom)

    @property
    def laterale_totale_m(self):
        """Retrait effectif en bord LATÉRAL (rive + acrotère)."""
        return self.laterale_m + self.acrotere_m

    @property
    def extremite_totale_m(self):
        """Retrait effectif en bout de rangée (rive d'extrémité + joint)."""
        return self.extremite_m + self.joint_m


# ============================================================ politique de pas
class PolitiquePas:
    """Contrat de la politique d'espacement entre rangées.

    Le DP consomme ``pas_apres_rangee(kit, y0)`` et JAMAIS un scalaire
    ``allee`` : c'est la seule différence structurelle entre le calepinage AO
    (allée constante, tables 15° dos-à-dos qui ne s'ombrent pas) et le
    calepinage villa (pas variable anti-ombrage). Les implémentations vivent
    dans ``politique_pas.py``.
    """

    code = "abstraite"

    def pas_apres_rangee(self, kit, y0):
        raise NotImplementedError

    def allee_minimale(self):
        raise NotImplementedError


# ================================================================= paramètres
@dataclass(frozen=True)
class Parametres:
    """TOUTE la configuration du moteur, immuable et hachable."""

    kits: Tuple[Kit, ...]
    rives: Rives = field(default_factory=Rives)
    axe_rangee: Axe = Axe.NORD_SUD
    mode_pose: ModePose = ModePose.RANGEES_EXPLICITES_DP
    allee_m: float = 0.60
    degagement_defaut_m: float = 0.30
    degagement_nature_inconnue_m: float = 0.50
    pas_recherche_m: float = 0.01
    engagement_modules: Optional[int] = None
    plafond_kwc: Optional[float] = None
    marge_troncon_min_m: float = 0.02
    marge_bande_min_m: float = 0.04
    #: Plan IMPOSÉ (PV29) : ``((y0, code_kit), …)``, lu par le seul mode
    #: ``RANGEES_IMPOSEES_UTILISATEUR``. Le code de kit — et non l'objet ``Kit``
    #: — parce que ce champ traverse le JSON : les kits y sont déjà décrits une
    #: fois, les redécrire ici ferait deux vérités pour la même table.
    rangees_imposees: Optional[Tuple[Tuple[float, str], ...]] = None
    #: pour l'aléatoire éventuel (départage) — le moteur reste déterministe.
    graine: int = 0

    def __post_init__(self):
        if not self.kits:
            raise ValueError("au moins un kit est requis")
        if self.allee_m < 0:
            raise ValueError("allée négative")
        if self.pas_recherche_m <= 0:
            raise ValueError("pas de recherche strictement positif")
        codes = [k.code for k in self.kits]
        if len(set(codes)) != len(codes):
            raise ValueError("deux kits portent le même code")

    def kit(self, code):
        for k in self.kits:
            if k.code == code:
                return k
        raise KeyError("kit inconnu : %s" % code)

    @property
    def multi_kits(self):
        return len(self.kits) > 1


def remplacer(objet, **champs):
    """``dataclasses.replace`` exposé sous un nom français (immuabilité)."""
    return replace(objet, **champs)


# =================================================================== résultats
@dataclass(frozen=True)
class Rangee:
    """Une rangée posée : position transversale + kit + tronçons occupés."""

    y0: float
    kit_code: str
    emprise_m: float
    troncons: Tuple[Tuple[float, float], ...] = ()
    modules: int = 0
    surface_repere: str = ""

    @property
    def y1(self):
        return self.y0 + self.emprise_m


@dataclass(frozen=True)
class Table:
    """Une table POSÉE (chemin de code B) — géométrie, jamais un total."""

    x0: float
    x1: float
    y0: float
    y1: float
    kit_code: str
    surface_repere: str = ""
    #: polygone effectif (arc : rectangle rigide au repère tangent local).
    polygone: Tuple[Tuple[float, float], ...] = ()
    pas_m: float = 0.0

    @property
    def modules(self):
        return None  # une table ne compte JAMAIS — c'est le rôle du moteur


@dataclass(frozen=True)
class Preuve:
    """Vocabulaire VERROUILLÉ (voir ``MethodePreuve``)."""

    methode: MethodePreuve
    pas_recherche_m: float
    compte_retenu: int
    compte_optimal: Optional[int] = None
    borne_superieure: Optional[int] = None
    nb_plans_optimaux: Optional[int] = None

    @property
    def optimal(self):
        """« Optimum prouvé » — INACCESSIBLE sur une méthode non exacte."""
        return bool(self.methode.exacte
                    and self.compte_optimal is not None
                    and self.compte_retenu == self.compte_optimal)

    @property
    def libelle(self):
        """Phrase GÉNÉRÉE — jamais un texte commercial écrit à la main."""
        if self.optimal:
            return "optimum prouvé (%d modules)" % self.compte_retenu
        borne = self.borne_superieure if self.borne_superieure is not None \
            else self.compte_optimal
        if borne is None:
            return "meilleur plan trouvé (%d modules)" % self.compte_retenu
        return ("meilleur plan trouvé (%d modules) — borne supérieure %d"
                % (self.compte_retenu, borne))


@dataclass(frozen=True)
class Marges:
    """Marges de robustesse PUBLIÉES EN CENTIMÈTRES (``robustesse.py``)."""

    troncon_min_m: float
    bande_min_m: float
    rangee_critique: str = ""
    obstacle_critique: str = ""

    @property
    def troncon_min_cm(self):
        return self.troncon_min_m * 100.0

    @property
    def bande_min_cm(self):
        return self.bande_min_m * 100.0


@dataclass(frozen=True)
class Sensibilite:
    """Une variante DÉFAVORABLE recalculée par le MÊME moteur."""

    code: str
    libelle: str
    modules: int
    delta: int
    tenu: bool = True


@dataclass(frozen=True)
class Marche:
    """Une marche de l'échelle de décomposition (``echelle.py``)."""

    code: str
    libelle: str
    modules: int
    delta: int
    attendu: Optional[int] = None


@dataclass(frozen=True)
class Recommandation:
    """Proposition APPLIQUABLE — le gain est RECALCULÉ, jamais estimé."""

    code: str
    titre: str
    gain_modules: int
    gain_kwc: float
    cout_qualitatif: str
    confiance: Confiance
    patch_entree: Tuple[Tuple[str, str], ...] = ()
    question_a_poser: str = ""


@dataclass(frozen=True)
class Plan:
    """Le plan de pose retenu — rangées + tables, sans aucun total dupliqué."""

    surface_repere: str
    rangees: Tuple[Rangee, ...] = ()
    tables: Tuple[Table, ...] = ()
    kit_codes: Tuple[str, ...] = ()

    @property
    def modules(self):
        return sum(r.modules for r in self.rangees)


@dataclass(frozen=True)
class Resultat:
    """Sortie complète d'un calepinage — tout est CALCULÉ, rien n'est recopié."""

    plan: Plan
    modules: int
    kwc: float
    preuve: Preuve
    marges: Optional[Marges] = None
    parametres: Optional[Parametres] = None
    sensibilites: Tuple[Sensibilite, ...] = ()
    recommandations: Tuple[Recommandation, ...] = ()
    regles_obstacles: Tuple[Tuple[str, str], ...] = ()
    engageable: bool = True
    motifs_non_engageable: Tuple[str, ...] = ()
    hash_entree: str = ""
    version_moteur: str = ""

    @property
    def plancher_sensibilites(self):
        """Le PLANCHER publié : le pire compte de la batterie défavorable."""
        if not self.sensibilites:
            return self.modules
        return min([self.modules] + [s.modules for s in self.sensibilites])

    def verdict(self, engagement=None):
        """Phrase GÉNÉRÉE (jamais rédigée) : engagement tenu / tenu sauf …."""
        cible = engagement
        if cible is None and self.parametres is not None:
            cible = self.parametres.engagement_modules
        if cible is None:
            return "aucun engagement déclaré"
        manquants = tuple(s.code for s in self.sensibilites if s.modules < cible)
        if self.plancher_sensibilites >= cible:
            return "engagement tenu partout (%d ≥ %d)" % (
                self.plancher_sensibilites, cible)
        if not manquants:
            return "engagement NON tenu (%d < %d)" % (self.modules, cible)
        return "engagement tenu sauf %s (plancher %d < %d)" % (
            ", ".join(manquants), self.plancher_sensibilites, cible)


def egaux(a, b, tolerance=TOL_LONGUEUR_M):
    """Égalité de longueurs à la tolérance NOMMÉE — évite les ``1e-9`` épars."""
    return abs(a - b) <= tolerance
