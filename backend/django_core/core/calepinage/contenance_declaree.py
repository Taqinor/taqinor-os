# -*- coding: utf-8 -*-
"""CIQ113 — contenance ESTIMÉE d'une surface DÉCLARÉE, par le VRAI moteur.

Aujourd'hui rien ne borne la taille C&I par le toit : la contenance mesurée
n'existe que pour un calepinage dessiné, et le site public suppose une
constante surfacique non sourcée. Ici, AUCUNE constante surfacique : on
construit un RECTANGLE de l'aire déclarée (hypothèses PUBLIÉES : forme carrée
supposée, aucun obstacle), on lui applique le retrait de rive et l'allée des
réglages (``Parametres`` / ``Rives`` du moteur) et la politique du mode de
pose (CIQ112) — affleurante pour bac acier et toiture inclinée, anti-ombrage
pour toit plat lesté ou fixé, espacement inter-rangées calculé à la latitude
— puis on POSE avec ``core.calepinage.optimum.calculer``.

C'est un PLAFOND INDICATIF : il borne la taille automatique avec la raison
« limitée par la surface déclarée (estimation, à confirmer au calepinage /
visite) » et ne propose jamais une taille. Modes ``sol`` / ``ombriere`` :
aucune règle de pose n'est supposée (``None`` + motif). Dimensions du module
absentes (fiche) : ``None`` + motif.

Noyau PUR (garde ``calepinage-est-un-noyau-pur``) : stdlib + paquet seulement.
"""

import math

from core.calepinage.optimum import calculer
from core.calepinage.politique_pas import Affleurant, AntiOmbrage
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import Kit, OrientationModule, Parametres, Rives

__all__ = [
    "contenance_surface_declaree", "MODES_AFFLEURANTS", "MODES_ANTI_OMBRAGE",
    "RAISON_PLAFOND",
]

#: Modes de pose (vocabulaire ``core.product_roles.TYPES_POSE``).
MODES_AFFLEURANTS = ("bac_acier", "toiture_inclinee")
MODES_ANTI_OMBRAGE = ("toit_plat_leste", "toit_plat_fixe")
MODES_SANS_REGLE = ("sol", "ombriere")

#: La raison publiée quand ce plafond borne la taille automatique.
RAISON_PLAFOND = ("limitée par la surface déclarée (estimation, à confirmer "
                  "au calepinage/visite)")


def _resultat(nb, kwc, hypotheses, motif):
    return {"nb_modules": nb, "kwc": kwc, "hypotheses": hypotheses,
            "motif": motif}


def _nombre(valeur):
    try:
        x = float(valeur)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def contenance_surface_declaree(surface_m2, *, mode_pose, cotes_module_m,
                                inclinaison_deg, latitude_deg,
                                parametres=None, puissance_module_wc=None):
    """Nombre de modules qu'une surface DÉCLARÉE peut porter (estimation).

    ``cotes_module_m`` : ``(longueur, largeur)`` en mètres, lues sur la FICHE
    (``FicheTechnique.longueur_mm/largeur_mm`` ÷ 1000) — ``None`` si absentes.
    ``inclinaison_deg`` : inclinaison des modules (pente du toit en
    affleurant, des tables en anti-ombrage). ``parametres`` : un
    ``Parametres`` du moteur (rives + allée des réglages) ou ``None`` = les
    valeurs du moteur, publiées comme hypothèses. ``puissance_module_wc`` :
    pour rendre les kWc (sinon ``kwc`` vaut ``None``).

    Rend ``{nb_modules, kwc, hypotheses, motif}`` ; ``nb_modules`` ``None``
    ⇒ ``motif`` nommé. Ne lève jamais.
    """
    hypotheses = []
    mode = (mode_pose or "").strip()
    if mode in MODES_SANS_REGLE:
        return _resultat(None, None, hypotheses,
                         "contenance à établir au calepinage (sol / ombrière)")
    if mode not in MODES_AFFLEURANTS + MODES_ANTI_OMBRAGE:
        return _resultat(None, None, hypotheses,
                         "mode de pose non déclaré : contenance à établir au "
                         "calepinage")
    aire = _nombre(surface_m2)
    if aire is None or aire <= 0:
        return _resultat(None, None, hypotheses, "surface déclarée absente")
    cotes = None
    if cotes_module_m:
        try:
            cotes = tuple(_nombre(c) for c in cotes_module_m)
        except TypeError:
            cotes = None
    if not cotes or len(cotes) != 2 or any(c is None or c <= 0 for c in cotes):
        return _resultat(None, None, hypotheses,
                         "dimensions du module absentes de la fiche technique")
    inclinaison = _nombre(inclinaison_deg)
    if inclinaison is None or not (0.0 <= inclinaison < 90.0):
        return _resultat(None, None, hypotheses,
                         "inclinaison des modules non fournie")
    latitude = _nombre(latitude_deg)
    if mode in MODES_ANTI_OMBRAGE and latitude is None:
        return _resultat(None, None, hypotheses,
                         "latitude du site non fournie : espacement "
                         "anti-ombrage incalculable")

    rives = parametres.rives if parametres is not None else Rives()
    allee = parametres.allee_m if parametres is not None else None
    cote = math.sqrt(aire)
    hypotheses.extend([
        {"cle": "forme", "valeur": "carré de %.2f m de côté" % cote,
         "statut": "estimation",
         "source": "forme carrée supposée (surface déclarée sans plan)"},
        {"cle": "obstacles", "valeur": 0, "statut": "estimation",
         "source": "aucun obstacle supposé"},
        {"cle": "retrait_rive_m", "valeur": rives.laterale_m,
         "statut": "declare" if parametres is not None else "estimation",
         "source": "réglages de calepinage" if parametres is not None
         else "valeur du moteur de calepinage"},
    ])

    longueur, largeur = max(cotes), min(cotes)
    kit = Kit(code="CI_DECLAREE", libelle="Module de la fiche (estimation)",
              module_long_m=longueur, module_court_m=largeur,
              puissance_module_wc=_nombre(puissance_module_wc) or 1.0,
              inclinaison_deg=inclinaison,
              orientation=OrientationModule.PORTRAIT, modules_par_table=1)
    if mode in MODES_AFFLEURANTS:
        politique = Affleurant()
    else:
        politique = AntiOmbrage(latitude_deg=latitude)
    hypotheses.append({"cle": "politique", "valeur": politique.code,
                       "statut": "declare",
                       "source": "mode de pose déclaré « %s »" % mode})
    champs = {"kits": (kit,), "rives": rives}
    if allee is not None:
        champs["allee_m"] = allee
    reglages = Parametres(**champs)
    surface = SurfaceRectangle(repere="SURFACE_DECLAREE", longueur_m=cote,
                               largeur_m=cote, rives=rives)
    try:
        resultat = calculer(surface, reglages, politique=politique)
    except ValueError as erreur:
        return _resultat(None, None, hypotheses,
                         "contenance incalculable : %s" % erreur)
    nb = int(resultat.modules)
    wc = _nombre(puissance_module_wc)
    kwc = round(nb * wc / 1000.0, 3) if wc else None
    return _resultat(nb, kwc, hypotheses, None)
