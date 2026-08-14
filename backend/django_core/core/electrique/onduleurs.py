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

    @property
    def puissance_ac_kw(self):
        return self.nombre * self.ac_kw_unitaire

    @property
    def dc_par_onduleur_kwc(self):
        return self.puissance_dc_kwc / self.nombre if self.nombre else 0.0


def ratios(puissance_dc_kwc, puissance_ac_kw):
    """UN calcul, DEUX publications : ``(ratio_dc_ac, ratio_ac_dc)``.

    Les deux ``Ratio`` sortent du même couple de puissances et portent chacun
    SES bornes. Sans puissance AC connue (onduleur non renseigné), les deux
    valeurs sont ``None`` — un ratio inventé serait pire que pas de ratio.
    """
    dc = float(puissance_dc_kwc or 0.0)
    ac = float(puissance_ac_kw or 0.0)
    mini, maxi = BORNES_RATIO_AC_DC

    if dc <= 0 or ac <= 0:
        return (
            Ratio(nom="DC/AC", valeur=None, borne_max=BORNE_USUELLE_DC_AC,
                  seuil_alerte=SEUIL_ALERTE_DC_AC, dans_bornes=True),
            Ratio(nom="AC/DC", valeur=None, borne_min=mini, borne_max=maxi,
                  dans_bornes=True),
        )

    valeur_dc_ac = dc / ac
    valeur_ac_dc = ac / dc
    return (
        Ratio(nom="DC/AC", valeur=valeur_dc_ac,
              borne_max=BORNE_USUELLE_DC_AC, seuil_alerte=SEUIL_ALERTE_DC_AC,
              dans_bornes=valeur_dc_ac <= BORNE_USUELLE_DC_AC + 1e-9),
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


def dimensionner_onduleurs(entree, puissance_dc_kwc=None):
    """PV34 — nombre d'onduleurs, puissance AC totale, et les deux ratios bornés.

    Les alertes citent LA convention dont elles sortent : « ratio DC/AC 2,06
    au-dessus du seuil d'alerte 1,50 » et « ratio AC/DC 0,48 hors fourchette
    0,75-1,00 » disent la même chose de deux façons — les deux sont écrites,
    parce que deux lecteurs différents (le bureau d'études et l'acheteur public)
    ne lisent pas la même.
    """
    onduleur = entree.onduleur
    dc = float(entree.puissance_kwc if puissance_dc_kwc is None
               else puissance_dc_kwc)
    plafond = entree.plafond_kwc_par_onduleur
    nombre = nombre_onduleurs(dc, plafond)
    ac_total = nombre * float(onduleur.ac_kw or 0.0)

    ratio_dc_ac, ratio_ac_dc = ratios(dc, ac_total)

    bloquants = []
    alertes = []
    if dc > 0 and (onduleur.ac_kw or 0.0) <= 0:
        alertes.append(
            "puissance AC de l'onduleur non renseignée — ratio DC/AC non "
            "calculable, à vérifier avant dépôt du dossier")

    valeur = ratio_dc_ac.valeur
    if valeur is not None:
        if valeur > SEUIL_ALERTE_DC_AC + 1e-9:
            alertes.append(
                "ratio DC/AC de %s au-dessus du seuil d'alerte %s — "
                "surdimensionnement DC important, écrêtage probable aux heures "
                "pleines" % (fr(valeur, 2), fr(SEUIL_ALERTE_DC_AC, 2)))
        elif valeur > BORNE_USUELLE_DC_AC + 1e-9:
            alertes.append(
                "ratio DC/AC de %s au-dessus de la borne usuelle %s — "
                "écrêtage aux heures pleines" % (fr(valeur, 2),
                                                 fr(BORNE_USUELLE_DC_AC, 2)))
        elif valeur < 1.0 - 1e-9:
            alertes.append(
                "ratio DC/AC de %s inférieur à 1,00 — onduleur surdimensionné "
                "par rapport au champ PV" % fr(valeur, 2))

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
    )
