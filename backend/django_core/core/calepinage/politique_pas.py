# -*- coding: utf-8 -*-
"""AOF46 — la politique de PAS : ce qui unifie l'appel d'offres et la VILLA.

Le DP consomme ``pas_apres_rangee(kit, y0)`` et JAMAIS un scalaire ``allee``.
C'est la SEULE différence structurelle entre les deux métiers :

* **AO** — allée constante ; les tables dos-à-dos à 15° ne s'ombrent pas entre
  elles (chaque table a une face est et une face ouest), donc l'espacement est
  un choix de maintenance, pas de physique ;
* **VILLA** — pas variable ANTI-OMBRAGE : au solstice d'hiver, une rangée
  projette son ombre sur la suivante ; le pas se calcule
  (``profondeur projetée + longueur d'ombre + marge``), exactement comme le
  cerveau TypeScript du site (``roofPro2.ts``) ;
* **AFFLEURANT** — toiture en pente : les modules sont posés jointifs, il n'y a
  pas d'allée du tout.

Absorber la différence ici, au lieu de juxtaposer deux moteurs, donne
GRATUITEMENT à l'AO la capacité anti-ombrage le jour où une toiture plein sud
l'exige — et à la villa tout l'appareillage de preuve de l'AO.
"""

import math
from dataclasses import dataclass
from typing import Optional

from core.calepinage.types import PolitiquePas

__all__ = [
    "AlleeFixe", "AntiOmbrage", "Affleurant", "ELEVATION_DIMENSIONNEMENT_DEG",
    "DECLINAISON_SOLSTICE_DEG", "HEURE_SOLAIRE_DIMENSIONNEMENT",
    "ELEVATION_PLANCHER_DEG", "PASSAGE_CHEVRON_EW_M", "EW_OMBRE_PLEINE",
    "EW_EMPREINTE_RETRANCHEE", "POLITIQUES_EW", "position_solaire_solstice",
    "politique_par_defaut",
]

#: Élévation solaire de DIMENSIONNEMENT au solstice d'hiver (degrés).
#: Valeur de référence du cerveau TypeScript : elle n'est pas l'élévation
#: maximale de midi mais celle retenue pour garantir une plage utile autour du
#: midi solaire. Elle est PARAMÉTRABLE — jamais un littéral enfoui.
#:
#: PV65 : c'est une valeur de RÉFÉRENCE, pas une vérité de site — elle vaut le
#: Maroc « moyen ». Une ``AntiOmbrage`` qui reçoit sa ``latitude_deg`` calcule
#: l'élévation du LIEU (Agadir n'est pas Tanger) ; sans latitude, cette
#: constante s'applique, à l'identique de tout ce qui a déjà été publié.
ELEVATION_DIMENSIONNEMENT_DEG = 21.0

#: Déclinaison solaire au solstice d'hiver (hémisphère nord), en degrés.
DECLINAISON_SOLSTICE_DEG = -23.44

#: Heure SOLAIRE de dimensionnement : 10 h, le point le plus défavorable de la
#: fenêtre de travail 10 h - 14 h. Midi solaire donnerait une règle plus dense
#: — donc des rangées plus serrées, donc de l'ombre entre 10 h et midi.
HEURE_SOLAIRE_DIMENSIONNEMENT = 10.0

#: Garde-fou « soleil très bas » : sous 5°, la tangente explose et le pas de
#: rangée deviendrait absurde (une latitude polaire rendrait une toiture
#: infinie). Le cerveau TypeScript porte exactement le même plancher.
ELEVATION_PLANCHER_DEG = 5.0

#: CAL167 — passage de maintenance/aération entre deux chevrons EST-OUEST (m).
#: Porté du cerveau TypeScript du site, pas inventé ici :
#: ``estimatorBrainV2.ts``, constante ``EW_MAINTENANCE_GAP_M = 0.2``.
#: Ce n'est PAS un pas de rangée sud : entre deux chevrons dos-à-dos, ce qui
#: sépare les tables est un passage d'homme, pas une contrainte solaire.
PASSAGE_CHEVRON_EW_M = 0.20

#: Politique d'espacement entre CHEVRONS est-ouest — l'ancienne, par DÉFAUT :
#: l'ombre de faîte est comptée PLEINE, comme pour une rangée plein sud. Le
#: moteur est alors conservateur (il peut poser un chevron de moins, jamais un
#: de trop) : c'est la limite assumée que ``types.py`` documente sur
#: ``KIT_VILLA_EW``.
EW_OMBRE_PLEINE = "OMBRE_DE_FAITE_PLEINE"

#: Politique d'espacement entre CHEVRONS est-ouest — celle du site, en OPTION
#: EXPLICITE : un chevron en A absorbe sa PROPRE ombre de faîte tant qu'elle
#: reste dans l'empreinte de son pan ouest ; seul le RÉSIDU qui déborde, plus
#: le passage de maintenance, sépare deux chevrons. Elle exige la latitude du
#: site : l'ombre de faîte est-ouest a une DIRECTION (composante ``|sin γ|``),
#: et le noyau ne devine jamais un lieu.
EW_EMPREINTE_RETRANCHEE = "EMPREINTE_CHEVRON_RETRANCHEE"

#: Les deux seules valeurs acceptées — une politique inconnue est REFUSÉE en
#: nommant le champ, jamais repliée en silence sur le défaut.
POLITIQUES_EW = (EW_OMBRE_PLEINE, EW_EMPREINTE_RETRANCHEE)


def _borner(valeur, bas=-1.0, haut=1.0):
    """Ramène un sinus dans [-1, 1] : l'arrondi flottant sort du domaine."""
    return max(bas, min(haut, valeur))


def position_solaire_solstice(latitude_deg,
                              heure_solaire=HEURE_SOLAIRE_DIMENSIONNEMENT):
    """(élévation, azimut depuis le SUD) en degrés, au solstice d'hiver.

    Portage FIDÈLE du cerveau TypeScript du site (``estimatorBrainV2.ts``,
    ``sunPositionWinterSolstice``) : le site et l'ERP doivent espacer les
    rangées de la MÊME façon, sinon la même villa reçoit deux calepinages
    selon l'écran qui l'a produite.

        sin α = sin φ · sin δ + cos φ · cos δ · cos h
        sin γ = − cos δ · sin h / cos α

    avec φ la latitude, δ la déclinaison du solstice et h l'angle horaire
    (15° par heure depuis le midi solaire).
    """
    phi = math.radians(latitude_deg)
    delta = math.radians(DECLINAISON_SOLSTICE_DEG)
    angle_horaire = math.radians(15.0 * (heure_solaire - 12.0))
    sin_alpha = (math.sin(phi) * math.sin(delta)
                 + math.cos(phi) * math.cos(delta) * math.cos(angle_horaire))
    alpha = math.asin(_borner(sin_alpha))
    cos_alpha = math.cos(alpha)
    if abs(cos_alpha) < 1e-12:
        # Soleil au zénith : l'azimut n'est plus défini, l'ombre est nulle.
        return math.degrees(alpha), 0.0
    sin_gamma = -math.cos(delta) * math.sin(angle_horaire) / cos_alpha
    return math.degrees(alpha), math.degrees(math.asin(_borner(sin_gamma)))


@dataclass(frozen=True)
class AlleeFixe(PolitiquePas):
    """Allée CONSTANTE — la politique de l'appel d'offres."""

    allee_m: float = 0.60
    code: str = "ALLEE_FIXE"

    def __post_init__(self):
        if self.allee_m < 0:
            raise ValueError("allée négative")

    def pas_apres_rangee(self, kit, y0):
        return self.allee_m

    def allee_minimale(self):
        return self.allee_m


@dataclass(frozen=True)
class AntiOmbrage(PolitiquePas):
    """Pas ANTI-OMBRAGE au solstice d'hiver — la politique de la villa.

    ``pas_apres_rangee`` rend le VIDE entre deux rangées ; le pas de rangée
    complet vaut ``emprise + pas_apres_rangee``, soit exactement
    ``profondeur projetée + longueur d'ombre + marge`` du calcul de référence.

    **PV65 — l'élévation peut venir du LIEU.** ``latitude_deg`` renseignée, le
    soleil de dimensionnement est calculé (déclinaison du solstice + angle
    horaire de 10 h) au lieu d'être lu dans une constante nationale : à Agadir
    (30,4°) le soleil monte plus haut qu'à Tanger (35,8°), l'ombre est plus
    courte et la toiture porte donc plus de rangées. Sans latitude, RIEN ne
    change : la constante historique s'applique et les comptes déjà publiés
    restent reproductibles au bit près.

    **CAL167 — UNE SEULE politique de pas, deux familles de pose.** La même
    classe gouverne désormais les rangées plein sud ET l'espacement entre
    chevrons est-ouest, au lieu de laisser la seconde à une limite muette :

    * ``politique_ew=EW_OMBRE_PLEINE`` (DÉFAUT) — l'ombre de faîte est comptée
      pleine, comme pour une rangée sud. Conservateur, historique, bit pour
      bit inchangé ;
    * ``politique_ew=EW_EMPREINTE_RETRANCHEE`` — la politique du site : le pan
      ouest du chevron absorbe sa propre ombre de faîte, seul le résidu plus
      un passage d'homme sépare deux chevrons. Elle EXIGE ``latitude_deg``.

    Le choix est NOMMÉ dans ``hypothese`` et l'écart entre les deux se lit sur
    ``ecart_a_l_ombre_pleine_m`` : un compte plus dense dit pourquoi il l'est.
    """

    elevation_deg: float = ELEVATION_DIMENSIONNEMENT_DEG
    marge_m: float = 0.05
    allee_minimale_m: float = 0.0
    #: Latitude du site (degrés, positif au nord). ``None`` = valeur nationale.
    latitude_deg: Optional[float] = None
    heure_solaire: float = HEURE_SOLAIRE_DIMENSIONNEMENT
    code: str = "ANTI_OMBRAGE"
    #: CAL167 — politique d'espacement entre CHEVRONS est-ouest (kits
    #: dos-à-dos). Le DÉFAUT reste l'ombre de faîte pleine : aucun calepinage
    #: déjà publié ne change tant que l'appelant ne choisit pas l'autre.
    politique_ew: str = EW_OMBRE_PLEINE
    #: Passage de maintenance entre deux chevrons — lu uniquement par
    #: ``EW_EMPREINTE_RETRANCHEE``.
    passage_chevron_m: float = PASSAGE_CHEVRON_EW_M

    def __post_init__(self):
        if not (0.0 < self.elevation_deg < 90.0):
            raise ValueError("élévation de dimensionnement hors bornes")
        if self.marge_m < 0:
            raise ValueError("marge négative")
        if self.latitude_deg is not None and not (-90.0 <= self.latitude_deg
                                                  <= 90.0):
            raise ValueError("latitude hors bornes (-90 à 90 degrés)")
        if not (0.0 <= self.heure_solaire <= 24.0):
            raise ValueError("heure solaire hors bornes (0 à 24)")
        if self.politique_ew not in POLITIQUES_EW:
            raise ValueError(
                "champ `politique_ew` : politique d'espacement est-ouest "
                "inconnue %r — attendu %s."
                % (self.politique_ew, " ou ".join(POLITIQUES_EW)))
        if (self.politique_ew == EW_EMPREINTE_RETRANCHEE
                and self.latitude_deg is None):
            raise ValueError(
                "champ `latitude_deg` : la politique est-ouest "
                "« empreinte du chevron retranchée » exige la LATITUDE du "
                "site. L'ombre de faîte entre chevrons a une DIRECTION "
                "est-ouest, que le noyau ne devine jamais : transmettez le "
                "point GPS du calepinage.")
        if self.passage_chevron_m < 0:
            raise ValueError("champ `passage_chevron_m` : passage négatif")

    def hauteur_module_m(self, kit):
        """Hauteur du haut du module au-dessus du plan (côté pente × sin)."""
        return kit.cote_dans_la_pente_m * math.sin(
            math.radians(kit.inclinaison_deg))

    def elevation_effective_deg(self):
        """L'élévation RETENUE : celle du lieu, ou la constante nationale."""
        if self.latitude_deg is None:
            return self.elevation_deg
        alpha, _azimut = position_solaire_solstice(self.latitude_deg,
                                                   self.heure_solaire)
        return max(ELEVATION_PLANCHER_DEG, alpha)

    def longueur_ombre_m(self, kit):
        """Ombre portée par UNE rangée à l'élévation de dimensionnement.

        Sans latitude, le calcul est celui d'avant PV65, à l'expression près :
        c'est ce qui garantit que les golden villa restent verts sans être
        régénérés. Avec latitude, l'ombre porte AUSSI la composante
        directionnelle ``|cos γ|`` du soleil — le même terme que le cerveau
        TypeScript (``shadeLengthM``), car à 10 h le soleil n'est pas au sud
        et une ombre projetée droit vers le nord surestimerait l'espacement.
        """
        hauteur = self.hauteur_module_m(kit)
        if self.latitude_deg is None:
            return hauteur / math.tan(math.radians(self.elevation_deg))
        _alpha, azimut = position_solaire_solstice(self.latitude_deg,
                                                   self.heure_solaire)
        direction = abs(math.cos(math.radians(azimut)))
        return max(0.0, hauteur * direction / math.tan(
            math.radians(self.elevation_effective_deg())))

    # ------------------------------------------------ CAL167 : chevron E-O
    def empreinte_pan_m(self, kit):
        """Empreinte au sol d'UN pan du chevron (``panelDepthM`` du site).

        Un chevron dos-à-dos en pose la moitié à l'est, l'autre à l'ouest :
        son emprise transversale vaut deux fois cette empreinte (plus le
        faîtage éventuel).
        """
        return kit.cote_dans_la_pente_m * math.cos(
            math.radians(kit.inclinaison_deg))

    def ombre_de_faite_ew_m(self, kit):
        """Ombre du faîte PROJETÉE SUR L'AXE EST-OUEST, à l'heure de design.

        Portage FIDÈLE de ``shadeLengthM(rise, lat, heure, eastWest=true)`` du
        cerveau TypeScript : les chevrons s'empilent vers l'est, donc ce qui
        les sépare est la composante ``|sin γ|`` de l'ombre — pas la
        composante nord-sud ``|cos γ|`` qui gouverne les rangées plein sud.
        """
        if self.latitude_deg is None:
            raise ValueError(
                "champ `latitude_deg` : l'ombre de faîte est-ouest exige la "
                "latitude du site (sa DIRECTION dépend du lieu).")
        _alpha, azimut = position_solaire_solstice(self.latitude_deg,
                                                   self.heure_solaire)
        direction = abs(math.sin(math.radians(azimut)))
        return max(0.0, self.hauteur_module_m(kit) * direction / math.tan(
            math.radians(self.elevation_effective_deg())))

    def pas_chevron_ew_m(self, kit):
        """VIDE entre deux chevrons : ombre RÉSIDUELLE + passage d'homme.

        ``max(0, ombre_de_faîte − empreinte d'un pan) + passage`` — identité
        pour identité avec ``interTentGap`` du site. Le pan ouest du chevron
        absorbe sa propre ombre de faîte tant qu'elle y tient ; ce qui déborde
        (souvent zéro aux inclinaisons est-ouest réalistes) est le SEUL terme
        solaire qui subsiste.
        """
        return (max(0.0, self.ombre_de_faite_ew_m(kit)
                    - self.empreinte_pan_m(kit))
                + self.passage_chevron_m)

    def empreinte_ew_active(self, kit):
        """La politique d'empreinte s'applique-t-elle à CE kit ?

        Uniquement si elle a été CHOISIE et si le kit est bien un chevron
        dos-à-dos : un module unique plein sud n'a pas de pan ouest pour
        absorber quoi que ce soit.
        """
        return (self.politique_ew == EW_EMPREINTE_RETRANCHEE
                and bool(getattr(kit, "dos_a_dos", False)))

    def ecart_a_l_ombre_pleine_m(self, kit):
        """Ce que l'empreinte du chevron LIBÈRE — l'écart, borné et expliqué.

        Positif = la nouvelle politique serre les chevrons ; négatif = elle
        les écarte. C'est la SEULE grandeur par laquelle les deux politiques
        diffèrent : même soleil, même solstice, même heure de design.
        """
        return ((self.longueur_ombre_m(kit) + self.marge_m)
                - self.pas_chevron_ew_m(kit))

    @property
    def hypothese(self):
        """Phrase GÉNÉRÉE qui NOMME l'hypothèse retenue — jamais un texte écrit
        à la main, et la même des deux côtés de l'écran (CAL86).
        """
        if self.latitude_deg is None:
            solaire = ("élévation de dimensionnement %.1f° (valeur nationale "
                       "— latitude du site non transmise)"
                       % self.elevation_deg)
        else:
            solaire = ("élévation de dimensionnement %.1f° calculée à la "
                       "latitude %.3f° à %.0f h solaire"
                       % (self.elevation_effective_deg(), self.latitude_deg,
                          self.heure_solaire))
        if self.politique_ew == EW_EMPREINTE_RETRANCHEE:
            ew = ("chevrons est-ouest : empreinte du pan retranchée de "
                  "l'ombre de faîte, passage de %.2f m" % self.passage_chevron_m)
        else:
            ew = "chevrons est-ouest : ombre de faîte PLEINE (conservateur)"
        return "%s ; %s" % (solaire, ew)

    # ------------------------------------------------------------- le pas
    def pas_de_rangee_m(self, kit):
        """Pas COMPLET de rangée (profondeur + ombre + marge) — publiable."""
        if self.empreinte_ew_active(kit):
            return kit.emprise_transversale_m + self.pas_chevron_ew_m(kit)
        return (kit.emprise_transversale_m + self.longueur_ombre_m(kit)
                + self.marge_m)

    def pas_apres_rangee(self, kit, y0):
        if self.empreinte_ew_active(kit):
            return max(self.allee_minimale_m, self.pas_chevron_ew_m(kit))
        return max(self.allee_minimale_m,
                   self.longueur_ombre_m(kit) + self.marge_m)

    def allee_minimale(self):
        return self.allee_minimale_m


@dataclass(frozen=True)
class Affleurant(PolitiquePas):
    """Pose JOINTIVE sur toiture en pente — aucune allée."""

    jeu_m: float = 0.0
    code: str = "AFFLEURANT"

    def __post_init__(self):
        if self.jeu_m < 0:
            raise ValueError("jeu négatif")

    def pas_apres_rangee(self, kit, y0):
        return self.jeu_m

    def allee_minimale(self):
        return self.jeu_m


def politique_par_defaut(parametres):
    """``AlleeFixe`` construite depuis les paramètres — la non-régression AO."""
    return AlleeFixe(allee_m=parametres.allee_m)
