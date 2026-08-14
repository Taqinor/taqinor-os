# -*- coding: utf-8 -*-
"""PV37 — la NOMENCLATURE, re-alimentée par les calculs (jamais par des défauts).

La forme de sortie reprend celle de ``apps/ventes/solar_design.py::generate_boq``
— ``{items: [{categorie, designation, quantite, unite, spec}], summary, warnings}``
— pour qu'un adaptateur applicatif puisse la consommer sans se réécrire. Ce qui
change est la SOURCE des nombres : l'ancien bordereau annonçait « parafoudre DC
Type 2 » et « sectionneur-fusible DC par chaîne » sans avoir vérifié qu'ils
étaient exigés, et un « câble solaire DC 6 mm² » écrit en dur dans la
désignation. Ici, chaque ligne descend d'un organe RETENU par une règle (PV35)
ou d'un câble DIMENSIONNÉ (PV36) : si la liaison DC fait 8 m, il n'y a pas de
parafoudre dans le bordereau, et si le calcul demande du 10 mm², la ligne dit
10 mm².

QUANTITÉS et SPÉCIFICATIONS uniquement : **jamais un prix**. Le chiffrage reste
l'affaire du devis, hors du noyau.
"""

import math
from dataclasses import dataclass
from typing import Tuple

from core.electrique.types import LigneNomenclature, fr

__all__ = [
    "CATEGORIE_PAR_REPERE", "ResultatNomenclature", "nomenclature",
    "nomenclature_dict",
]

#: Catégorie de bordereau par préfixe de repère — mêmes intitulés que le
#: bordereau historique, pour qu'un consommateur existant s'y retrouve.
CATEGORIE_PAR_REPERE = (
    ("F", "Protection DC"),
    ("QDC", "Protection DC"),
    ("PDC", "Protection DC"),
    ("QBAT", "Protection batterie"),
    ("QAC", "Protection AC"),
    ("PAC", "Protection AC"),
    ("DDR", "Protection AC"),
    ("T", "Mise à la terre"),
)


@dataclass(frozen=True)
class ResultatNomenclature:
    lignes: Tuple[LigneNomenclature, ...] = ()
    alertes: Tuple[str, ...] = ()


def _categorie(repere):
    """Catégorie d'un repère — le préfixe le plus LONG gagne (QDC avant Q)."""
    meilleur = ""
    categorie = "Protection"
    for prefixe, valeur in CATEGORIE_PAR_REPERE:
        if repere.startswith(prefixe) and len(prefixe) > len(meilleur):
            meilleur, categorie = prefixe, valeur
    return categorie


def nomenclature(entree, resultat_chaines=None, resultat_protections=None,
                 resultat_cables=None):
    """PV37 — les lignes de bordereau déduites des calculs amont."""
    lignes = []
    alertes = []
    chaines = resultat_chaines.chaines if resultat_chaines else ()
    nb_chaines = len(chaines)
    nb_modules = entree.nb_modules

    def ajouter(categorie, designation, quantite, unite, spec=""):
        lignes.append(LigneNomenclature(
            categorie=categorie, designation=designation,
            quantite=quantite, unite=unite, spec=spec))

    if nb_modules <= 0:
        return ResultatNomenclature(
            alertes=("aucun module — pas de nomenclature à générer",))

    # ── Câblage, aux sections RÉELLEMENT calculées ───────────────────────────
    cables = resultat_cables.cables if resultat_cables else ()
    for cable in cables:
        categorie = "Câblage DC" if cable.repere == "W1" else "Câblage AC"
        ajouter(categorie,
                "%s %s mm²" % (cable.designation, fr(cable.section_mm2, 1)),
                round(cable.longueur_m * cable.nb_conducteurs, 1), "m",
                "chute de tension %s %% (cible %s %%), Iz %s A, critère "
                "dimensionnant : %s"
                % (fr(cable.chute_tension_pct, 2), fr(cable.chute_cible_pct, 1),
                   fr(cable.iz_a, 0), cable.critere_dimensionnant))

    # ── Protections, une ligne par organe RETENU par une règle ───────────────
    protections = (resultat_protections.protections
                   if resultat_protections else ())
    for protection in protections:
        ajouter(_categorie(protection.repere),
                "%s — %s" % (protection.repere, protection.designation),
                protection.quantite, "u",
                "%s ; %s" % (protection.calibre, protection.regle_source))

    # ── Coffrets — leur nombre suit le nombre de chaînes à raccorder ─────────
    if nb_chaines:
        ajouter("Coffret", "Coffret de chaînes DC (string box)",
                1 if nb_chaines <= 2 else 2, "u",
                "IP65, presse-étoupes, embase parafoudre, %d chaîne(s) à "
                "raccorder" % nb_chaines)
    if resultat_protections is not None and resultat_protections.calibre_ac_a:
        ajouter("Coffret", "Coffret de protection AC", 1, "u",
                "IP65, prêt à raccorder au tableau, disjoncteur %s A"
                % fr(resultat_protections.calibre_ac_a, 0))

    # ── Mise à la terre — le conducteur, en plus des organes ci-dessus ───────
    longueur_terre = round(float(entree.dc_m or 0.0) * 0.6
                           + float(entree.ac_m or 0.0), 1)
    if longueur_terre > 0:
        ajouter("Mise à la terre", "Câble de terre cuivre nu 25 mm²",
                longueur_terre, "m",
                "liaison équipotentielle structure + masses (NF C 15-100 §542)")

    # ── Structure ────────────────────────────────────────────────────────────
    ajouter("Structure", "Rail de fixation aluminium", nb_modules * 2, "u",
            "rail anodisé, longueur ajustée au module")
    ajouter("Structure", "Pince de fixation (milieu + extrémité)",
            nb_modules * 2 + 4, "u", "inox A2, milieu et extrémité")
    ajouter("Structure", "Crochet / patte de fixation toiture",
            max(4, int(math.ceil(nb_modules * 0.6))), "u",
            "selon couverture (tuile / bac acier)")

    # ── Stockage ─────────────────────────────────────────────────────────────
    if entree.batterie:
        ajouter("Batterie", "Câble batterie DC 25 mm²", 6.0, "m",
                "section forte intensité, cosses serties")

    if resultat_chaines is not None and resultat_chaines.reste_total:
        alertes.append(
            "%d module(s) hors chaîne comptés au bordereau (réserve d'appoint) "
            "— la structure les inclut, l'électricité non"
            % resultat_chaines.reste_total)
    if resultat_cables is not None:
        alertes.extend(resultat_cables.alertes)

    return ResultatNomenclature(lignes=tuple(lignes), alertes=tuple(alertes))


def nomenclature_dict(entree, resultat_chaines=None, resultat_protections=None,
                      resultat_cables=None, resultat_nomenclature=None):
    """Même contenu, dans la FORME du bordereau historique (``generate_boq``).

    ``{items: [...], summary: {...}, warnings: [...]}`` — les clés de résumé
    reprennent celles de ``generate_boq`` (``kwc``, ``n_panels``, ``strings``,
    ``phases``, ``ac_breaker_amp``, ``ac_cable_section_mm2``, ``n_lignes``) pour
    qu'un adaptateur applicatif branche l'un sur l'autre sans traduction.
    """
    resultat = resultat_nomenclature or nomenclature(
        entree, resultat_chaines, resultat_protections, resultat_cables)
    section_ac = None
    for cable in (resultat_cables.cables if resultat_cables else ()):
        if cable.repere == "W2":
            section_ac = cable.section_mm2
    return {
        "items": [{
            "categorie": ligne.categorie,
            "designation": ligne.designation,
            "quantite": ligne.quantite,
            "unite": ligne.unite,
            "spec": ligne.spec,
        } for ligne in resultat.lignes],
        "summary": {
            "kwc": round(entree.puissance_kwc, 3),
            "n_panels": entree.nb_modules,
            "strings": (resultat_chaines.nb_chaines if resultat_chaines else 0),
            "phases": 3 if int(entree.phases or 1) == 3 else 1,
            "ac_breaker_amp": (resultat_protections.calibre_ac_a
                               if resultat_protections else None),
            "ac_cable_section_mm2": section_ac,
            "n_lignes": len(resultat.lignes),
        },
        "warnings": list(resultat.alertes),
    }
