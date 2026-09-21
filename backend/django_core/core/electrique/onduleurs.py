# -*- coding: utf-8 -*-
"""PV34 — onduleurs : nombre, puissance AC, et la RÉCONCILIATION des deux ratios.

Le repo portait DEUX conventions de ratio, chacune juste dans son monde, jamais
réconciliées — c'est exactement le genre d'écart qui fait dire deux choses
différentes au même dossier :

* ``apps/ventes/solar_design.py`` publie **DC/AC** (puissance crête ÷ puissance
  AC) : borne usuelle 1,35, alerte au-delà de 1,50 — la convention des
  constructeurs d'onduleurs et des études de production ;
* ``core/calepinage/electrique.py`` publie **AC/DC** (puissance AC ÷ puissance
  crête) : fourchette 0,75-1,00 — la convention des CPS de marchés publics, qui
  imposent une puissance d'onduleur PLANCHER.

Ici, **UN SEUL calcul** produit les deux : ``ratio_dc_ac = kWc ÷ kW`` et
``ratio_ac_dc = kW ÷ kWc``, à partir du MÊME couple de puissances. Chacun sort
avec SES bornes attachées (``Ratio.fourchette_texte``), si bien qu'aucun lecteur
ne peut confondre « 1,35 » avec « 0,75 ». Les deux sont inverses l'un de l'autre
par construction : un test l'ARME (``valeur_dc_ac × valeur_ac_dc = 1``).
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from core.electrique.types import Ratio, fr

__all__ = [
    "BORNE_USUELLE_DC_AC", "SEUIL_ALERTE_DC_AC", "BORNES_RATIO_AC_DC",
    "CLE_BORNE_USUELLE_DC_AC", "CLE_SEUIL_ALERTE_DC_AC", "CLE_SEUIL_BAS_DC_AC",
    "CLES_RATIO_DC_AC", "SOURCE_CONVENTION_ATELIER",
    "BorneRatio", "BornesDcAc", "bornes_dc_ac",
    "EvaluationOnduleurs", "ratios", "nombre_onduleurs",
    "dimensionner_onduleurs",
]

#: Borne USUELLE du ratio DC/AC (convention ``apps/ventes/solar_design.MAX_DC_AC``)
#: — au-delà, l'onduleur est « petit » pour le champ (écrêtage aux heures pleines).
BORNE_USUELLE_DC_AC = 1.35

#: Seuil d'ALERTE du ratio DC/AC (même source) — surdimensionnement DC important.
SEUIL_ALERTE_DC_AC = 1.5

#: Fourchette du ratio AC/DC (convention ``core/calepinage/electrique.py``,
#: elle-même lue dans l'exigence du CPS quand le marché en impose une).
BORNES_RATIO_AC_DC = (0.75, 1.00)

#: CALX213 — les trois clés de réglage société (section « electrique_societe »,
#: registre CALX145) qui pilotent les bornes du ratio DC/AC. Le noyau ne LIT
#: aucune base : l'applicatif lui passe le dict des saisies, chacune de la
#: forme ``{valeur, source, reference}`` — la forme même du registre.
CLE_BORNE_USUELLE_DC_AC = "borne_usuelle_dc_ac"
CLE_SEUIL_ALERTE_DC_AC = "seuil_alerte_dc_ac"
CLE_SEUIL_BAS_DC_AC = "seuil_bas_dc_ac"
CLES_RATIO_DC_AC = (CLE_BORNE_USUELLE_DC_AC, CLE_SEUIL_ALERTE_DC_AC,
                    CLE_SEUIL_BAS_DC_AC)

#: Ce que VAUT une borne non saisie : les deux constantes historiques
#: s'appliquent À L'IDENTIQUE (décision D12 — un réglage neuf ne change pas le
#: comportement d'aujourd'hui), mais elles sont PUBLIÉES pour ce qu'elles sont.
#: Un chiffre d'atelier présenté comme une norme est un chiffre indéfendable.
SOURCE_CONVENTION_ATELIER = "convention atelier, non sourcée"


@dataclass(frozen=True)
class BorneRatio:
    """UNE borne du ratio DC/AC : sa clé, sa valeur, et d'OÙ elle vient.

    ``valeur is None`` veut dire « aucun contrôle » — jamais « zéro », jamais
    un repli. C'est le cas du seuil BAS tant que personne ne l'a saisi.
    """

    cle: str
    valeur: Optional[float]
    source: str = ""

    @property
    def controlee(self):
        return self.valeur is not None and self.valeur > 0


@dataclass(frozen=True)
class BornesDcAc:
    """Les TROIS paliers du ratio DC/AC, chacun avec sa source.

    OpenSolar publie les trois (trop bas = onduleur sous-utilisé, zone de
    prudence, zone où la garantie peut sauter) ; le noyau en fait trois bornes
    indépendantes, dont seule celle qui est renseignée prononce un verdict.
    """

    borne_usuelle: BorneRatio
    seuil_alerte: BorneRatio
    seuil_bas: BorneRatio


def _saisie(reglages, cle):
    """``(valeur, source)`` d'une saisie ``{valeur, source}``, sinon ``(None, '')``.

    Une valeur SANS source est traitée comme non saisie : c'est la règle du
    registre CALX145, et elle vaut aussi ici — une borne dont personne ne dit
    d'où elle sort ne peut pas fonder un refus.
    """
    saisie = (reglages or {}).get(cle)
    if not isinstance(saisie, dict):
        return (None, "")
    valeur = saisie.get("valeur")
    source = saisie.get("source") or ""
    if valeur is None or not source:
        return (None, "")
    try:
        return (float(valeur), str(source))
    except (TypeError, ValueError):
        return (None, "")


def bornes_dc_ac(reglages=None):
    """Les trois bornes du ratio DC/AC, saisies ou non (CALX213).

    Les deux bornes HAUTES retombent sur les constantes historiques quand rien
    n'est saisi — comportement d'aujourd'hui à l'identique (D12) — mais elles
    sortent alors avec la mention ``convention atelier, non sourcée``. La
    borne BASSE, elle, n'a pas de constante : non saisie, elle ne contrôle
    RIEN (``valeur is None``).
    """
    valeur, source = _saisie(reglages, CLE_BORNE_USUELLE_DC_AC)
    usuelle = BorneRatio(
        cle=CLE_BORNE_USUELLE_DC_AC,
        valeur=valeur if valeur is not None else BORNE_USUELLE_DC_AC,
        source=source or SOURCE_CONVENTION_ATELIER)
    valeur, source = _saisie(reglages, CLE_SEUIL_ALERTE_DC_AC)
    alerte = BorneRatio(
        cle=CLE_SEUIL_ALERTE_DC_AC,
        valeur=valeur if valeur is not None else SEUIL_ALERTE_DC_AC,
        source=source or SOURCE_CONVENTION_ATELIER)
    valeur, source = _saisie(reglages, CLE_SEUIL_BAS_DC_AC)
    bas = BorneRatio(cle=CLE_SEUIL_BAS_DC_AC, valeur=valeur, source=source)
    return BornesDcAc(borne_usuelle=usuelle, seuil_alerte=alerte,
                      seuil_bas=bas)


@dataclass(frozen=True)
class EvaluationOnduleurs:
    """Configuration d'onduleurs ÉVALUÉE — les deux ratios, les motifs nommés."""

    nombre: int
    ac_kw_unitaire: float
    puissance_dc_kwc: float
    ratio_dc_ac: Optional[Ratio] = None
    ratio_ac_dc: Optional[Ratio] = None
    plafond_kwc_par_onduleur: Optional[float] = None
    bloquants: Tuple[str, ...] = ()
    alertes: Tuple[str, ...] = ()
    #: CALX213 — les trois bornes du ratio DC/AC RÉELLEMENT employées, avec
    #: leur source. L'aval n'a plus à deviner si « 1,35 » vient d'un réglage
    #: société ou de la convention d'atelier du noyau.
    bornes: Optional[BornesDcAc] = None

    @property
    def puissance_ac_kw(self):
        return self.nombre * self.ac_kw_unitaire

    @property
    def dc_par_onduleur_kwc(self):
        return self.puissance_dc_kwc / self.nombre if self.nombre else 0.0


def ratios(puissance_dc_kwc, puissance_ac_kw, bornes=None):
    """UN calcul, DEUX publications : ``(ratio_dc_ac, ratio_ac_dc)``.

    Les deux ``Ratio`` sortent du même couple de puissances et portent chacun
    SES bornes. Sans puissance AC connue (onduleur non renseigné), les deux
    valeurs sont ``None`` — un ratio inventé serait pire que pas de ratio.

    ``bornes`` (CALX213) — les trois paliers de ``bornes_dc_ac`` ; absent, les
    constantes historiques s'appliquent à l'identique. La borne BASSE saisie,
    quand elle existe, devient le ``borne_min`` publié du ratio DC/AC.
    """
    bornes = bornes if bornes is not None else bornes_dc_ac()
    dc = float(puissance_dc_kwc or 0.0)
    ac = float(puissance_ac_kw or 0.0)
    mini, maxi = BORNES_RATIO_AC_DC
    usuelle = bornes.borne_usuelle.valeur
    alerte = bornes.seuil_alerte.valeur
    bas = bornes.seuil_bas.valeur if bornes.seuil_bas.controlee else None

    if dc <= 0 or ac <= 0:
        return (
            Ratio(nom="DC/AC", valeur=None, borne_min=bas, borne_max=usuelle,
                  seuil_alerte=alerte, dans_bornes=True),
            Ratio(nom="AC/DC", valeur=None, borne_min=mini, borne_max=maxi,
                  dans_bornes=True),
        )

    valeur_dc_ac = dc / ac
    valeur_ac_dc = ac / dc
    dans_bornes = valeur_dc_ac <= usuelle + 1e-9
    if bas is not None:
        dans_bornes = dans_bornes and valeur_dc_ac >= bas - 1e-9
    return (
        Ratio(nom="DC/AC", valeur=valeur_dc_ac, borne_min=bas,
              borne_max=usuelle, seuil_alerte=alerte, dans_bornes=dans_bornes),
        Ratio(nom="AC/DC", valeur=valeur_ac_dc, borne_min=mini, borne_max=maxi,
              dans_bornes=(mini - 1e-9) <= valeur_ac_dc <= (maxi + 1e-9)),
    )


def nombre_onduleurs(puissance_dc_kwc, plafond_kwc_par_onduleur=None):
    """Combien d'onduleurs pour tenir le plafond de puissance CRÊTE par appareil.

    Le plafond (« aucun onduleur au-dessus de N kWc ») est une règle de DOSSIER,
    pas une propriété de l'appareil : sur un marché public, c'est le CPS qui
    l'impose, et il REBOUCLE sur le calepinage (déporter des modules d'un pan à
    l'autre). Sans plafond, un seul onduleur.
    """
    dc = float(puissance_dc_kwc or 0.0)
    if plafond_kwc_par_onduleur is None or plafond_kwc_par_onduleur <= 0:
        return 1 if dc > 0 else 0
    if dc <= 0:
        return 0
    return max(1, int(math.ceil(dc / float(plafond_kwc_par_onduleur) - 1e-9)))


def dimensionner_onduleurs(entree, puissance_dc_kwc=None, reglages=None):
    """PV34 — nombre d'onduleurs, puissance AC totale, et les deux ratios bornés.

    Les alertes citent LA convention dont elles sortent : « ratio DC/AC 2,06
    au-dessus du seuil d'alerte 1,50 » et « ratio AC/DC 0,48 hors fourchette
    0,75-1,00 » disent la même chose de deux façons — les deux sont écrites,
    parce que deux lecteurs différents (le bureau d'études et l'acheteur public)
    ne lisent pas la même.

    CALX213 — deux bornes de FICHE, publiées par le catalogue depuis CALX60 et
    que personne ne lisait, deviennent des contrôles :

    * ``dc_max_kwc`` (puissance crête d'entrée maximale) — dépassement
      BLOQUANT : la configuration sort de la spécification constructeur, comme
      un Isc cumulé au-dessus de ``isc_max_mppt_a`` ;
    * ``s_max_kva`` (puissance apparente maximale) — dépassement ALERTE :
      l'appareil est bridé, rien ne casse. La comparaison se fait au point
      NOMINAL de la fiche (puissance active déclarée, cos φ = 1) : le noyau ne
      connaît aucun cos φ et n'en suppose donc aucun — c'est la comparaison la
      moins sévère possible, et le libellé le dit.

    Borne non publiée ⇒ AUCUN contrôle et aucun repli : refuser un dossier sur
    un nombre que le constructeur n'a pas écrit serait pire que se taire.

    ``reglages`` — les saisies société ``{clé: {valeur, source}}`` des trois
    paliers du ratio DC/AC (cf. ``bornes_dc_ac``). Absentes, les constantes
    historiques s'appliquent à l'identique.
    """
    onduleur = entree.onduleur
    dc = float(entree.puissance_kwc if puissance_dc_kwc is None
               else puissance_dc_kwc)
    plafond = entree.plafond_kwc_par_onduleur
    nombre = nombre_onduleurs(dc, plafond)
    ac_total = nombre * float(onduleur.ac_kw or 0.0)

    bornes = bornes_dc_ac(reglages)
    ratio_dc_ac, ratio_ac_dc = ratios(dc, ac_total, bornes)

    bloquants = []
    alertes = []
    if dc > 0 and (onduleur.ac_kw or 0.0) <= 0:
        alertes.append(
            "puissance AC de l'onduleur non renseignée — ratio DC/AC non "
            "calculable, à vérifier avant dépôt du dossier")

    borne_usuelle = bornes.borne_usuelle.valeur
    seuil_alerte = bornes.seuil_alerte.valeur
    valeur = ratio_dc_ac.valeur
    if valeur is not None:
        if valeur > seuil_alerte + 1e-9:
            alertes.append(
                "ratio DC/AC de %s au-dessus du seuil d'alerte %s — "
                "surdimensionnement DC important, écrêtage probable aux heures "
                "pleines" % (fr(valeur, 2), fr(seuil_alerte, 2)))
        elif valeur > borne_usuelle + 1e-9:
            alertes.append(
                "ratio DC/AC de %s au-dessus de la borne usuelle %s — "
                "écrêtage aux heures pleines" % (fr(valeur, 2),
                                                 fr(borne_usuelle, 2)))
        elif valeur < 1.0 - 1e-9:
            alertes.append(
                "ratio DC/AC de %s inférieur à 1,00 — onduleur surdimensionné "
                "par rapport au champ PV" % fr(valeur, 2))
        # Palier BAS — il n'existe QUE saisi : aucune constante ne le remplace.
        if bornes.seuil_bas.controlee \
                and valeur < bornes.seuil_bas.valeur - 1e-9:
            alertes.append(
                "onduleur sous-utilisé : ratio DC/AC de %s sous le seuil bas "
                "de %s (%s) — augmenter le champ PV ou prendre un onduleur de "
                "puissance inférieure"
                % (fr(valeur, 2), fr(bornes.seuil_bas.valeur, 2),
                   bornes.seuil_bas.source))

    bloquants.extend(_verdict_dc_max(onduleur, dc, nombre))
    alertes.extend(_verdict_s_max(onduleur))

    valeur_ac = ratio_ac_dc.valeur
    if valeur_ac is not None and not ratio_ac_dc.dans_bornes:
        mini, maxi = BORNES_RATIO_AC_DC
        alertes.append(
            "ratio AC/DC de %s hors fourchette %s-%s — %d onduleur(s) de %s kW "
            "pour %s kWc crête" % (fr(valeur_ac, 2), fr(mini, 2), fr(maxi, 2),
                                   nombre, fr(onduleur.ac_kw or 0.0, 0),
                                   fr(dc, 1)))

    if plafond and nombre:
        par_onduleur = dc / nombre
        if par_onduleur > float(plafond) + 1e-9:
            bloquants.append(
                "%s kWc par onduleur au-dessus du plafond de %s kWc — déport de "
                "modules nécessaire" % (fr(par_onduleur, 1), fr(plafond, 0)))

    return EvaluationOnduleurs(
        nombre=nombre,
        ac_kw_unitaire=float(onduleur.ac_kw or 0.0),
        puissance_dc_kwc=dc,
        ratio_dc_ac=ratio_dc_ac,
        ratio_ac_dc=ratio_ac_dc,
        plafond_kwc_par_onduleur=plafond,
        bloquants=tuple(bloquants),
        alertes=tuple(alertes),
        bornes=bornes,
    )


def _verdict_dc_max(onduleur, puissance_dc_kwc, nombre):
    """Puissance crête raccordée PAR ONDULEUR contre ``dc_max_kwc`` (BLOQUANT).

    Le plafond est une propriété de L'APPAREIL : c'est donc la puissance crête
    raccordée sur UN onduleur qu'il borne, pas celle de la centrale entière.
    Borne non publiée ⇒ liste vide.
    """
    borne = onduleur.dc_max_kwc
    if borne is None or borne <= 0 or not nombre or puissance_dc_kwc <= 0:
        return []
    par_onduleur = puissance_dc_kwc / nombre
    if par_onduleur <= float(borne) + 1e-9:
        return []
    return [
        "%s kWc crête raccordés sur l'onduleur « %s » > %s kWc, puissance "
        "d'entrée maximale de sa fiche constructeur — configuration HORS "
        "SPÉCIFICATION, réduire le champ raccordé sur cet appareil ou ajouter "
        "un onduleur"
        % (fr(par_onduleur, 2), onduleur.designation or "onduleur",
           fr(float(borne), 2))]


def _verdict_s_max(onduleur):
    """Puissance apparente injectée contre ``s_max_kva`` (ALERTE : bridage).

    La comparaison se fait au point NOMINAL publié par la fiche (puissance
    active ``ac_kw``, cos φ = 1) : aucun cos φ n'est supposé, et c'est la
    comparaison la moins sévère — si elle sort déjà, l'appareil est bridé quel
    que soit le facteur de puissance réel. Borne non publiée ⇒ liste vide.
    """
    borne = onduleur.s_max_kva
    active = float(onduleur.ac_kw or 0.0)
    if borne is None or borne <= 0 or active <= 0:
        return []
    if active <= float(borne) + 1e-9:
        return []
    return [
        "onduleur « %s » BRIDÉ : puissance apparente maximale de fiche %s kVA "
        "inférieure à sa puissance active nominale %s kW (comparaison à "
        "cos φ = 1, aucun facteur de puissance n'étant supposé) — l'injection "
        "plafonnera à %s kVA, en tenir compte au bilan de production"
        % (onduleur.designation or "onduleur", fr(float(borne), 2),
           fr(active, 2), fr(float(borne), 2))]
