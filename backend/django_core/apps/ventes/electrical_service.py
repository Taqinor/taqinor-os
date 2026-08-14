# -*- coding: utf-8 -*-
"""PV41 — la conception ÉLECTRIQUE d'un devis : de ses lignes au moteur.

Ce module est l'ADAPTATEUR entre le devis (des lignes, un calepinage, une fiche
produit) et le moteur PUR ``core.electrique`` (PV33-39, aucune base, aucun
Django). Il fait exactement trois choses :

1. **Résoudre les entrées** — la fiche du panneau et celle de l'onduleur sont
   lues EN CROSS-APP par le sélecteur ``apps.stock.selectors.specs_for_produit``
   (jamais par un import de ses modèles) ; les groupes de modules viennent des
   pans du calepinage (``roof_layout['_pans_geometry']``), et à défaut d'un seul
   groupe portant la cible lue dans les lignes (PV16).
2. **Appeler ``core.electrique.concevoir()``** une seule fois, et projeter son
   ``ResultatElectrique`` sur le CONTRAT PARTAGÉ
   ``apps/ventes/contract_samples/conception_electrique.json`` — clé pour clé,
   toutes les clés TOUJOURS présentes (une liste vide vaut ``[]``), pour qu'un
   écran ne puisse jamais ``.map()`` sur ``undefined``.
3. **Persister le résultat AVEC L'EMPREINTE DE SES ENTRÉES.** Deux appels aux
   mêmes entrées produisent la même empreinte, donc AUCUNE écriture au second
   (patron d'idempotence QJ17) : recalculer un écran ne réécrit pas la base.

CE QU'IL NE FAIT JAMAIS : toucher un statut de devis, une ligne, un prix. Le
moteur ne connaît aucun montant — la conception électrique est une pièce
technique, et ``Produit.prix_achat`` n'y entre sous aucune forme (règle du
dépôt). Le PDF client reste l'affaire exclusive de ``/proposal`` (règle #4).
"""
import hashlib
import json

__all__ = ["build_electrical_design", "conception_electrique_stockee",
           "DC_M_MINIMUM", "DC_M_PAR_CHAINE", "AC_M_DEFAUT"]

#: Longueurs de liaison PAR DÉFAUT (m), reprises du bordereau historique
#: (``solar_design.generate_boq``) pour que les deux chiffrages s'accordent :
#: la liaison DC est estimée à 20 m par chaîne, avec un plancher de 10 m ; la
#: liaison AC onduleur → tableau à 15 m. Les deux sont surchargeables.
DC_M_MINIMUM = 10.0
DC_M_PAR_CHAINE = 20.0
AC_M_DEFAUT = 15.0

#: Clés d'override acceptées — toute autre clé est IGNORÉE (jamais une erreur :
#: un écran qui envoie un champ de trop ne doit pas casser une étude).
OVERRIDES_CONNUS = (
    "dc_m", "ac_m", "phases", "regime", "batterie", "zone_keraunique",
    "temp_froid_c", "temp_chaud_c", "longueur_chaine_forcee",
    "plafond_kwc_par_onduleur",
)


# ── Résolution des entrées ───────────────────────────────────────────────────

def _specs_produit(produit):
    """Fiche normalisée d'un produit — lecture CROSS-APP par le sélecteur."""
    if produit is None:
        return {}
    from apps.stock.selectors import specs_for_produit
    return specs_for_produit(produit) or {}


def _flottant(valeur, defaut):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return defaut
    return nombre


def _entier(valeur, defaut):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return defaut


def _lignes_du_devis(devis):
    try:
        return list(devis.lignes.all())
    except Exception:      # pragma: no cover - devis non persisté
        return []


def _produit_de_famille(devis, predicat):
    """``(produit, libellé)`` de la première ligne classée par ``predicat``.

    Classification par les mots-clés PARTAGÉS de ``solar_design`` (alignés sur
    ``quote_engine/builder.py``) : la désignation d'abord, le nom du produit
    ensuite — la même lecture que partout ailleurs dans l'app.

    Une ligne SANS produit lié compte quand même : son libellé porte souvent
    tout ce qu'on sait de l'onduleur (« 10 kW triphasé »), et l'ignorer ferait
    silencieusement retomber le calcul en monophasé. Une ligne AVEC fiche prime
    toutefois sur une ligne libre — la fiche est la meilleure source.
    """
    repli = (None, "")
    for ligne in _lignes_du_devis(devis):
        produit = getattr(ligne, "produit", None)
        designation = ligne.designation or ""
        nom = getattr(produit, "nom", "") or ""
        if not predicat(designation, nom):
            continue
        libelle = designation or nom
        if produit is not None:
            return produit, libelle
        if not repli[1]:
            repli = (None, libelle)
    return repli


def spec_module_du_devis(devis):
    """``SpecModule`` du panneau du devis — fiche produit, sinon défauts sûrs.

    Les défauts sont ceux de ``solar_design.DEFAULT_MODULE`` (silicium
    cristallin de marché), à l'exception d'``isc_a``/``imp_a`` que l'historique
    n'avait pas : ils sont estimés depuis Pmax et Vmp/Voc quand la fiche ne les
    donne pas, faute de quoi le calibre des fusibles de chaîne serait nul.
    """
    from apps.ventes import solar_design as sd
    from core.electrique.types import SpecModule

    produit, libelle = _produit_de_famille(
        devis, lambda designation, nom: sd.is_panel(designation, nom))
    specs = _specs_produit(produit)

    pmax = _flottant(specs.get("pmax_wc"), 0.0)
    if pmax <= 0:
        pmax = float(sd.parse_watt(libelle)
                     or sd.DEFAULT_MODULE["puissance_w"])
    vmp = _flottant(specs.get("vmp_v"), float(sd.DEFAULT_MODULE["vmp"]))
    voc = _flottant(specs.get("voc_v"), float(sd.DEFAULT_MODULE["voc"]))
    # Isc/Imp : la fiche fait foi ; sinon on les déduit de la puissance (Imp =
    # Pmax / Vmp) avec la marge usuelle Isc ≈ 1,06 × Imp des fiches silicium.
    imp = _flottant(specs.get("imp_a"), 0.0)
    if imp <= 0:
        imp = (pmax / vmp) if vmp > 0 else 0.0
    isc = _flottant(specs.get("isc_a"), 0.0)
    if isc <= 0:
        isc = imp * 1.06
    return SpecModule(
        vmp_v=vmp,
        voc_v=voc,
        isc_a=isc,
        imp_a=imp,
        pmax_wc=pmax,
        temp_coeff_voc_pct_c=_flottant(
            specs.get("temp_coeff_voc_pct_c"),
            float(sd.DEFAULT_MODULE["temp_coeff_voc"])),
        temp_coeff_pmax_pct_c=_flottant(
            specs.get("temp_coeff_pmax_pct_c"),
            float(sd.DEFAULT_MODULE["temp_coeff_vmp"])),
    )


def spec_onduleur_du_devis(devis):
    """``SpecOnduleur`` de l'onduleur du devis — fiche produit, sinon défauts.

    Retourne aussi le nombre de PHASES déduit : la fiche d'abord, sinon le
    libellé (« triphasé » / « tri » / « 400 V ») — un onduleur triphasé mal
    déclaré ferait chuter le courant AC d'un facteur √3 dans tout le calcul.
    """
    from apps.ventes import solar_design as sd
    from core.electrique.types import SpecOnduleur

    produit, libelle = _produit_de_famille(
        devis, lambda designation, nom: sd.is_any_inverter(designation)
        or sd.is_any_inverter(nom))
    specs = _specs_produit(produit)
    defauts = sd.DEFAULT_INVERTER_WINDOW

    ac_kw = _flottant(specs.get("ac_kw"), 0.0)
    if ac_kw <= 0:
        ac_kw = _flottant(sd.parse_kw(libelle), 0.0)

    phases = _entier(specs.get("phases"), 0)
    if phases not in (1, 3):
        blob = (libelle or "").lower()
        phases = 3 if ("triphas" in blob or "tétrapolaire" in blob) else 1

    # Le courant d'entrée MPPT admissible n'a pas de défaut défendable : à
    # défaut de fiche, on le laisse à 0 et le moteur SAUTE le verdict de
    # courant plutôt que d'inventer une limite (il ne dira rien de faux).
    onduleur = SpecOnduleur(
        n_mppt=max(1, _entier(specs.get("n_mppt"), int(defauts["n_mppt"]))),
        mppt_v_min=_flottant(specs.get("mppt_v_min"),
                             float(defauts["v_mppt_min"])),
        mppt_v_max=_flottant(specs.get("mppt_v_max"),
                             float(defauts["v_mppt_max"])),
        v_max_abs=_flottant(specs.get("v_max_abs"), float(defauts["v_max"])),
        i_max_mppt_a=_flottant(specs.get("i_max_mppt_a"), 0.0),
        ac_kw=ac_kw,
        phases=phases,
        v_demarrage_v=float(defauts["v_min"]),
    )
    return onduleur, phases


def groupes_du_devis(devis):
    """``GroupePan`` du calepinage — un par PAN, sinon UN groupe pour la cible.

    Les pans viennent de ``roof_layout['_pans_geometry']`` (QJ21) : c'est la
    seule source qui connaît l'orientation RÉELLE de chaque pan, et deux
    orientations ne partagent jamais une entrée MPPT (le moteur le refuse).
    Sans calepinage, on retombe sur un unique groupe portant le nombre de
    panneaux lu dans les LIGNES du devis (PV16) — le devis fait foi.
    """
    from core.electrique.types import GroupePan

    layout = devis.roof_layout if isinstance(devis.roof_layout, dict) else {}
    pans = layout.get("_pans_geometry") or []
    groupes = []
    if isinstance(pans, list):
        for index, pan in enumerate(pans, start=1):
            if not isinstance(pan, dict):
                continue
            nb_modules = _entier(pan.get("nb_panneaux"), 0)
            if nb_modules <= 0:
                continue
            groupes.append(GroupePan(
                label=str(pan.get("label") or "Pan %d" % index),
                nb_modules=nb_modules,
                azimut_deg=_flottant(pan.get("azimut_deg"), 0.0),
                inclinaison_deg=_flottant(pan.get("inclinaison_deg"), 0.0),
            ))
    if groupes:
        return tuple(groupes)

    from apps.ventes.services import cible_depuis_lignes
    cible = cible_depuis_lignes(devis) or {}
    panneaux = _entier(cible.get("panneaux"), 0)
    if panneaux <= 0:
        return ()
    return (GroupePan(label="Toiture", nb_modules=panneaux,
                      azimut_deg=0.0, inclinaison_deg=0.0),)


def _batterie_du_devis(devis):
    from apps.ventes import solar_design as sd
    for ligne in _lignes_du_devis(devis):
        designation = ligne.designation or ""
        nom = getattr(getattr(ligne, "produit", None), "nom", "") or ""
        if sd.is_battery(designation) or sd.is_battery(nom):
            return True
    return False


def construire_entree(devis, overrides=None):
    """``EntreeElectrique`` complète d'un devis (+ les overrides appliqués).

    Les longueurs de liaison par défaut dépendent du NOMBRE DE CHAÎNES, qu'on
    ne connaît qu'après un premier passage : on conçoit donc les chaînes une
    fois à vide pour le compter, puis on ferme l'entrée. Le passage est pur et
    sans effet de bord — c'est du calcul, pas une écriture.
    """
    import dataclasses

    from core.electrique.chaines import concevoir_chaines
    from core.electrique.types import (
        EntreeElectrique, REGIME_TT, REGIMES_CONNUS,
        TEMP_CHAUD_DEFAUT_C, TEMP_FROID_DEFAUT_C)

    reglages = {clef: valeur for clef, valeur in (overrides or {}).items()
                if clef in OVERRIDES_CONNUS}

    module = spec_module_du_devis(devis)
    onduleur, phases_fiche = spec_onduleur_du_devis(devis)
    groupes = groupes_du_devis(devis)

    phases = _entier(reglages.get("phases"), phases_fiche)
    phases = 3 if phases == 3 else 1
    regime = str(reglages.get("regime") or REGIME_TT).upper()
    if regime not in REGIMES_CONNUS:
        regime = REGIME_TT

    longueur_forcee = reglages.get("longueur_chaine_forcee")
    longueur_forcee = (_entier(longueur_forcee, 0) or None
                       if longueur_forcee is not None else None)
    plafond = reglages.get("plafond_kwc_par_onduleur")
    plafond = (_flottant(plafond, 0.0) or None) if plafond is not None else None

    entree = EntreeElectrique(
        module=module,
        onduleur=onduleur,
        groupes=groupes,
        dc_m=0.0,
        ac_m=_flottant(reglages.get("ac_m"), AC_M_DEFAUT),
        phases=phases,
        regime=regime,
        batterie=(bool(reglages["batterie"]) if "batterie" in reglages
                  else _batterie_du_devis(devis)),
        temp_froid_c=_flottant(reglages.get("temp_froid_c"),
                               TEMP_FROID_DEFAUT_C),
        temp_chaud_c=_flottant(reglages.get("temp_chaud_c"),
                               TEMP_CHAUD_DEFAUT_C),
        plafond_kwc_par_onduleur=plafond,
        longueur_chaine_forcee=longueur_forcee,
        zone_keraunique=bool(reglages.get("zone_keraunique")),
    )

    if "dc_m" in reglages:
        dc_m = _flottant(reglages.get("dc_m"), DC_M_MINIMUM)
    else:
        nb_chaines = concevoir_chaines(entree).nb_chaines
        dc_m = max(DC_M_MINIMUM, nb_chaines * DC_M_PAR_CHAINE)
    return dataclasses.replace(entree, dc_m=dc_m)


# ── Empreinte des ENTRÉES (idempotence QJ17) ─────────────────────────────────

def empreinte_entree(devis, entree):
    """SHA-256 des entrées du calcul — même empreinte ⇒ aucune réécriture.

    Ce qui entre : l'empreinte du calepinage (``layout_hash``), les deux fiches
    (module et onduleur), la composition en pans, les longueurs de liaison, les
    phases, le régime de neutre et les contraintes optionnelles. Ce qui n'entre
    PAS : rien de monétaire, rien d'horodaté — deux calculs identiques à des
    dates différentes doivent donner la MÊME empreinte.
    """
    import dataclasses

    charge = {
        "layout_hash": getattr(devis, "layout_hash", None) or "",
        "module": dataclasses.asdict(entree.module),
        "onduleur": dataclasses.asdict(entree.onduleur),
        "groupes": [dataclasses.asdict(g) for g in entree.groupes],
        "dc_m": entree.dc_m,
        "ac_m": entree.ac_m,
        "phases": entree.phases,
        "regime": entree.regime,
        "batterie": entree.batterie,
        "temp_froid_c": entree.temp_froid_c,
        "temp_chaud_c": entree.temp_chaud_c,
        "plafond_kwc_par_onduleur": entree.plafond_kwc_par_onduleur,
        "longueur_chaine_forcee": entree.longueur_chaine_forcee,
        "zone_keraunique": entree.zone_keraunique,
    }
    brut = json.dumps(charge, sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


# ── Projection sur le CONTRAT PARTAGÉ ────────────────────────────────────────

def _arrondi(valeur, decimales=1):
    try:
        return round(float(valeur), decimales)
    except (TypeError, ValueError):
        return None


def _chaine_conforme(chaine, onduleur):
    """Verdict PAR CHAÎNE, lu sur les quatre mêmes bornes que le moteur."""
    plancher = max(onduleur.mppt_v_min, onduleur.tension_demarrage_v)
    return bool(
        chaine.voc_froid_v <= onduleur.v_max_abs
        and chaine.vmp_froid_v <= onduleur.mppt_v_max
        and chaine.vmp_chaud_v >= plancher)


def projeter_contrat(entree, resultat):
    """``ResultatElectrique`` → le dict du contrat, clé pour clé.

    Toutes les clés sont TOUJOURS présentes (liste vide plutôt qu'absente) :
    c'est la garantie qui empêche un écran de ``.map()`` sur ``undefined``.
    """
    index_par_pan = {}
    for groupe in entree.groupes:
        if groupe.label not in index_par_pan:
            index_par_pan[groupe.label] = len(index_par_pan) + 1

    chaines = [{
        "pan": index_par_pan.get(chaine.pan, 1),
        "mppt": chaine.mppt,
        "nb_modules": chaine.nb_modules,
        "vmp_froid_v": _arrondi(chaine.vmp_froid_v),
        "voc_froid_v": _arrondi(chaine.voc_froid_v),
        "vmp_chaud_v": _arrondi(chaine.vmp_chaud_v),
        "conforme": _chaine_conforme(chaine, entree.onduleur),
    } for chaine in resultat.chaines]

    return {
        "chaines": chaines,
        "conformite": {
            "conforme": bool(resultat.conformite.conforme),
            "bloquants": list(resultat.conformite.bloquants),
            "alertes": list(resultat.conformite.alertes),
        },
        "ratio_dc_ac": (_arrondi(resultat.ratio_dc_ac.valeur, 3)
                        if resultat.ratio_dc_ac else None),
        "ratio_ac_dc": (_arrondi(resultat.ratio_ac_dc.valeur, 3)
                        if resultat.ratio_ac_dc else None),
        "protections": [{
            "repere": protection.repere,
            "designation": protection.designation,
            "calibre": protection.calibre,
            "quantite": protection.quantite,
        } for protection in resultat.protections],
        "cables": [{
            "liaison": cable.designation,
            "longueur_m": _arrondi(cable.longueur_m),
            "section_mm2": _arrondi(cable.section_mm2, 2),
            "chute_pct": _arrondi(cable.chute_tension_pct, 2),
        } for cable in resultat.cables],
        "bom": [{
            "designation": ligne.designation,
            "quantite": ligne.quantite,
            "spec": ligne.spec,
        } for ligne in resultat.bom],
        "note": list(resultat.note),
        "parametres": {
            "dc_m": _arrondi(entree.dc_m),
            "ac_m": _arrondi(entree.ac_m),
            "phases": entree.phases,
            "regime": entree.regime,
        },
    }


# ── API publique ─────────────────────────────────────────────────────────────

def conception_electrique_stockee(devis):
    """La conception DÉJÀ calculée d'un devis, ou ``None``."""
    design = getattr(devis, "electrical_design", None)
    return design if isinstance(design, dict) and design else None


def build_electrical_design(devis, *, overrides=None):
    """PV41 — conçoit (ou re-conçoit) l'étude électrique d'un devis et la range.

    Retourne TOUJOURS le dict du contrat partagé
    ``contract_samples/conception_electrique.json``. Écrit ``electrical_design``
    et ``electrical_design_hash`` sur le devis — et RIEN d'autre : ni statut, ni
    ligne, ni prix (règle #4 ; le moteur ignore jusqu'à l'existence d'un
    montant). Deux appels aux mêmes entrées ⇒ même empreinte ⇒ aucune écriture
    au second (idempotence QJ17).
    """
    from core.electrique import concevoir

    entree = construire_entree(devis, overrides)
    empreinte = empreinte_entree(devis, entree)

    stockee = conception_electrique_stockee(devis)
    if stockee is not None \
            and getattr(devis, "electrical_design_hash", None) == empreinte:
        return stockee

    design = projeter_contrat(entree, concevoir(entree))
    devis.electrical_design = design
    devis.electrical_design_hash = empreinte
    if devis.pk:
        devis.save(update_fields=["electrical_design",
                                  "electrical_design_hash"])
    return design
