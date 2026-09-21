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

from core.electrique.types import LigneNomenclature, fr, fr_a

__all__ = [
    "CATEGORIE_PAR_REPERE", "MOTIF_STRUCTURE_NON_SOURCEE",
    "ResultatNomenclature", "nomenclature", "nomenclature_dict",
]

# ═══════════════════════════════════════════════════════════════════════════
# CALX246 — RATTACHER CHAQUE LIGNE À UNE RÉFÉRENCE DU CATALOGUE
# ═══════════════════════════════════════════════════════════════════════════
#
# Le bordereau sortait des désignations EN CLAIR (« Coffret de chaînes DC
# (string box) », « Rail de fixation aluminium ») sans aucun identifiant
# produit : personne ne pouvait commander depuis cette liste, et
# ``apps.stock.selectors.specs_for_produit`` — déjà employé par le module
# électrique — ne servait jamais à rattacher une ligne à un article.
#
# LE NOYAU NE CONNAÎT AUCUN CATALOGUE. Il reçoit une table ``references``
# DÉJÀ RÉSOLUE par l'applicatif (qui seul peut lire le stock, borné société)
# et se contente de poser l'identifiant sur la bonne ligne. La CLEF de
# rattachement est le REPÈRE de l'organe ou du câble (« QAC1 », « W1 ») quand
# il en a un, et sa CATÉGORIE sinon (« Structure », « Coffret ») : le repère
# est plus précis, il passe donc en premier.
#
# SANS CORRESPONDANCE, LES DEUX CHAMPS VALENT ``None`` et la ligne est publiée
# exactement comme avant — jamais un article deviné (D-CALX 7).


def _reference_de_ligne(references, repere, categorie):
    """``(produit_id, reference)`` — le REPÈRE prime sur la CATÉGORIE."""
    if not references:
        return (None, None)
    for clef in (repere, categorie):
        if not clef:
            continue
        entree = references.get(clef)
        if isinstance(entree, dict):
            return (entree.get("produit_id"), entree.get("reference"))
    return (None, None)


#: CALX247 — le motif publié quand AUCUNE règle de bordereau de structure
#: n'a été saisie par la société (décision fondateur 21/09/2026, registre
#: ``services/parametres_cles.py::CLES_ELECTRIQUE_SOCIETE`` — clé
#: ``regle_bom_structure``) : les trois lignes de fixation sont OMISES plutôt
#: que devinées par un ratio écrit en dur.
MOTIF_STRUCTURE_NON_SOURCEE = (
    "quantités de fixation non sourcées : renseignez la règle de bordereau "
    "de votre système de pose")

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
    ("ARM", "Coffret AC/DC"),
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


def _lignes_structure(nb_modules, regle_bom_structure, references=None):
    """CALX247 — 0 ou 3 lignes de fixation, SOURCÉES, jamais devinées.

    ``regle_bom_structure`` est le réglage société ``{rails_par_module,
    pinces_par_module, pinces_supplement, crochets_par_module,
    crochets_minimum, source}`` (registre ``CLES_ELECTRIQUE_SOCIETE``, clé
    ``regle_bom_structure``) : AUCUN de ces cinq nombres n'est écrit ici, ils
    sont LUS sur la règle saisie — seule ``source`` (le texte de provenance)
    conditionne la publication : sans elle, aucune quantité n'est publiée,
    même si des nombres sont par ailleurs présents dans l'objet.

    Rend ``(lignes, motif)`` — ``lignes`` vide et ``motif`` non vide quand la
    règle manque ou qu'un champ n'est pas lisible.
    """
    if not isinstance(regle_bom_structure, dict):
        return (), MOTIF_STRUCTURE_NON_SOURCEE
    source = (regle_bom_structure.get("source") or "").strip()
    if not source:
        return (), MOTIF_STRUCTURE_NON_SOURCEE
    champs = ("rails_par_module", "pinces_par_module", "pinces_supplement",
              "crochets_par_module", "crochets_minimum")
    valeurs = {}
    for champ in champs:
        try:
            valeurs[champ] = float(regle_bom_structure.get(champ))
        except (TypeError, ValueError):
            return (), (
                "quantités de fixation non sourcées : le champ « %s » de la "
                "règle de bordereau de votre système de pose n'est pas un "
                "nombre" % champ)
    rails = nb_modules * valeurs["rails_par_module"]
    pinces = nb_modules * valeurs["pinces_par_module"] + valeurs["pinces_supplement"]
    crochets = max(valeurs["crochets_minimum"],
                   math.ceil(nb_modules * valeurs["crochets_par_module"]))
    # CALX246 — les trois lignes de fixation n'ont pas de repère d'organe :
    # elles se rattachent par leur CATÉGORIE (« Structure »).
    produit_id, reference = _reference_de_ligne(references, "", "Structure")
    return (
        LigneNomenclature(
            categorie="Structure", designation="Rail de fixation aluminium",
            quantite=rails, unite="u",
            spec="rail anodisé, longueur ajustée au module ; règle de "
                 "bordereau société : %s" % source,
            produit_id=produit_id, reference=reference),
        LigneNomenclature(
            categorie="Structure",
            designation="Pince de fixation (milieu + extrémité)",
            quantite=pinces, unite="u",
            spec="inox A2, milieu et extrémité ; règle de bordereau "
                 "société : %s" % source,
            produit_id=produit_id, reference=reference),
        LigneNomenclature(
            categorie="Structure",
            designation="Crochet / patte de fixation toiture",
            quantite=crochets, unite="u",
            spec="selon couverture (tuile / bac acier) ; règle de "
                 "bordereau société : %s" % source,
            produit_id=produit_id, reference=reference),
    ), ""


def nomenclature(entree, resultat_chaines=None, resultat_protections=None,
                 resultat_cables=None, resultat_coffrets_dc=None,
                 resultat_coffret_ac=None, regle_bom_structure=None,
                 references=None):
    """PV37 — les lignes de bordereau déduites des calculs amont.

    ``references`` (CALX246) — table ``{repère ou catégorie: {produit_id,
    reference}}`` DÉJÀ RÉSOLUE par l'applicatif contre le catalogue de la
    société. Absente, chaque ligne sort avec ``produit_id``/``reference`` à
    ``None``, exactement comme avant.
    """
    lignes = []
    alertes = []
    nb_modules = entree.nb_modules

    def ajouter(categorie, designation, quantite, unite, spec="", repere=""):
        produit_id, reference = _reference_de_ligne(references, repere,
                                                    categorie)
        lignes.append(LigneNomenclature(
            categorie=categorie, designation=designation,
            quantite=quantite, unite=unite, spec=spec,
            produit_id=produit_id, reference=reference))

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
                   fr(cable.iz_a, 0), cable.critere_dimensionnant),
                repere=cable.repere)

    # ── Protections, une ligne par organe RETENU par une règle ───────────────
    protections = (resultat_protections.protections
                   if resultat_protections else ())
    for protection in protections:
        ajouter(_categorie(protection.repere),
                "%s — %s" % (protection.repere, protection.designation),
                protection.quantite, "u",
                "%s ; %s" % (protection.calibre, protection.regle_source),
                repere=protection.repere)

    # ── Coffrets DC — CALX230 : leur nombre suit les coffrets RÉELLEMENT
    # posés dans le plan (``electrical.equipements[]``), jamais un comptage
    # deviné à partir du nombre de chaînes. ``resultat_coffrets_dc`` est le
    # résultat de ``apps.calepinage.services.coffrets.coffrets_dc`` — un
    # coffret par organe posé, chacun avec ses entrées réellement raccordées.
    # ``resultat_coffrets_dc is None`` (intégration pas encore câblée) :
    # comportement d'aujourd'hui préservé SANS alerte.
    if resultat_coffrets_dc is not None and resultat_coffrets_dc.coffrets:
        for coffret in resultat_coffrets_dc.coffrets:
            if coffret.capacite_entrees:
                capacite_texte = ("%d entrée(s) disponible(s)"
                                  % coffret.capacite_entrees)
            else:
                capacite_texte = "capacité non publiée"
            # CALX231 — un coffret dont l'Isc cumulé dépasse son propre Isc
            # regroupe des enfants : la ligne le dit, avec le cumul.
            regroupement = ""
            if coffret.isc_cumule_a != coffret.isc_propre_a:
                nb_enfants = sum(
                    1 for autre in resultat_coffrets_dc.coffrets
                    if autre.parent_id == coffret.id)
                regroupement = (
                    "; regroupe %d coffret(s) enfant(s), Isc cumulé %s"
                    % (nb_enfants, fr_a(coffret.isc_cumule_a)))
            ajouter("Coffret",
                    "Coffret de chaînes DC (string box) — %s" % coffret.label,
                    1, "u",
                    "IP65, presse-étoupes, embase parafoudre, %d chaîne(s) "
                    "raccordée(s) sur %s%s"
                    % (len(coffret.chaines), capacite_texte, regroupement),
                    repere=coffret.id)
        alertes.extend(resultat_coffrets_dc.refus)
        alertes.extend(resultat_coffrets_dc.omissions)
    elif resultat_coffrets_dc is not None:
        # ``coffrets_dc`` a tourné (equipements[] connu, éventuellement vide)
        # et n'a rien pu retenir : son propre motif est publié — jamais un
        # second motif inventé ici.
        alertes.extend(resultat_coffrets_dc.refus)
        alertes.extend(resultat_coffrets_dc.omissions)

    # ── Coffret AC — CALX232 : dimensionné par ses départs réels quand
    # ``resultat_coffret_ac`` (apps.calepinage.services.coffrets.coffret_ac)
    # est fourni ; comportement d'aujourd'hui préservé tant qu'il ne l'est
    # pas, pour qu'un appelant qui n'a pas encore câblé CALX232 ne voie rien
    # changer.
    if resultat_coffret_ac is not None:
        if resultat_coffret_ac.departs:
            tete_texte = (" — calibre de tête %s"
                          % fr_a(resultat_coffret_ac.calibre_tete_a, 0)
                          if resultat_coffret_ac.calibre_tete_a else "")
            ajouter("Coffret",
                    "Coffret de protection AC — %d départ(s)%s"
                    % (resultat_coffret_ac.departs, tete_texte), 1, "u",
                    "IP65, prêt à raccorder au tableau, %d organe(s) AC ; %s"
                    % (resultat_coffret_ac.organes,
                       resultat_coffret_ac.regle_source),
                    repere="ARM1")
        alertes.extend(resultat_coffret_ac.omissions)
    elif resultat_protections is not None and resultat_protections.calibre_ac_a:
        ajouter("Coffret", "Coffret de protection AC", 1, "u",
                "IP65, prêt à raccorder au tableau, disjoncteur %s A"
                % fr(resultat_protections.calibre_ac_a, 0), repere="ARM1")

    # ── Mise à la terre — le conducteur, en plus des organes ci-dessus ───────
    longueur_terre = round(float(entree.dc_m or 0.0) * 0.6
                           + float(entree.ac_m or 0.0), 1)
    if longueur_terre > 0:
        ajouter("Mise à la terre", "Câble de terre cuivre nu 25 mm²",
                longueur_terre, "m",
                "liaison équipotentielle structure + masses (NF C 15-100 §542)")

    # ── Structure — CALX247 : conditionnée à une règle de bordereau SOCIÉTÉ
    # portant sa source ; sans elle, OMISE en le disant (décision fondateur
    # 21/09/2026, la structure sort du bordereau électrique quand personne
    # ne l'a sourcée).
    lignes_structure, motif_structure = _lignes_structure(
        nb_modules, regle_bom_structure, references)
    lignes.extend(lignes_structure)
    if motif_structure:
        alertes.append(motif_structure)

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
                      resultat_cables=None, resultat_nomenclature=None,
                      resultat_coffrets_dc=None, resultat_coffret_ac=None,
                      regle_bom_structure=None, references=None):
    """Même contenu, dans la FORME du bordereau historique (``generate_boq``).

    ``{items: [...], summary: {...}, warnings: [...]}`` — les clés de résumé
    reprennent celles de ``generate_boq`` (``kwc``, ``n_panels``, ``strings``,
    ``phases``, ``ac_breaker_amp``, ``ac_cable_section_mm2``, ``n_lignes``) pour
    qu'un adaptateur applicatif branche l'un sur l'autre sans traduction.
    """
    resultat = resultat_nomenclature or nomenclature(
        entree, resultat_chaines, resultat_protections, resultat_cables,
        resultat_coffrets_dc, resultat_coffret_ac, regle_bom_structure,
        references)
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
            # CALX246 — les deux champs de RÉFÉRENCE restent HORS de cette
            # forme : elle existe pour être la forme de ``generate_boq``, mot
            # pour mot (PV83, garde épinglée par
            # ``core/tests/test_electrique_nomenclature.py``). Un consommateur
            # qui veut les références lit ``ResultatNomenclature.lignes``.
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
