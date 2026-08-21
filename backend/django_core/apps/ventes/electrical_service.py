# -*- coding: utf-8 -*-
"""PV41 — la conception ÉLECTRIQUE d'un devis : de ses lignes au moteur.

Ce module est l'ADAPTATEUR entre le devis (des lignes, un calepinage, une fiche
produit) et le moteur PUR ``core.electrique`` (PV33-39, aucune base, aucun
Django). Il fait exactement trois choses :

1. **Résoudre les entrées** — la fiche du panneau et celle de l'onduleur sont
   lues EN CROSS-APP par le sélecteur ``apps.stock.selectors.specs_for_produit``
   (jamais par un import de ses modèles) ; les groupes de modules viennent des
   pans du calepinage (``roof_layout['_pans_geometry']``), et à défaut d'un seul
   groupe portant la cible lue dans les lignes (PV16). PV85 — l'entrée
   transporte aussi l'IDENTITÉ du matériel (module, onduleur, stockage) pour
   que le schéma NOMME les appareils ; seul un modèle CONFIRMÉ par le fondateur
   y est repris, un modèle « supposé » ne s'imprime jamais sur une pièce
   technique (cf. ``_designation_materiel``).
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
import logging

logger = logging.getLogger(__name__)

__all__ = ["build_electrical_design", "conception_electrique_stockee",
           "rendre_schema_du_devis", "fiches_manquantes_du_devis",
           "motifs_fiche_incomplete", "motifs_non_conformite_du_devis",
           "VARIABLES_MODULE_REQUISES", "VARIABLES_ONDULEUR_REQUISES",
           "DC_M_MINIMUM", "DC_M_PAR_DEFAUT", "AC_M_DEFAUT"]

#: Longueurs de liaison PAR DÉFAUT (m). DC — F2, décision fondateur
#: 19/08/2026 : chaque paire descendante (+ et −, une par entrée MPPT
#: réellement utilisée) parcourt un forfait de 30 m à l'aller — la longueur
#: ne dépend PLUS du nombre de chaînes (plusieurs chaînes en parallèle
#: convergent au coffret de chaînes avant la descente commune vers
#: l'onduleur) ; c'est le nombre de PAIRES qui suit les MPPT, pas la
#: longueur individuelle (``core.electrique.cables.dimensionner_cables``,
#: qui compte les conducteurs pour le métrage total du bordereau). AC
#: onduleur → tableau : 15 m. Les deux sont surchargeables (``dc_m``/``ac_m``).
DC_M_MINIMUM = 10.0
DC_M_PAR_DEFAUT = 30.0
AC_M_DEFAUT = 15.0

#: Clés d'override acceptées — toute autre clé est IGNORÉE (jamais une erreur :
#: un écran qui envoie un champ de trop ne doit pas casser une étude).
OVERRIDES_CONNUS = (
    "dc_m", "ac_m", "phases", "regime", "batterie", "zone_keraunique",
    "temp_froid_c", "temp_chaud_c", "longueur_chaine_forcee",
    "plafond_kwc_par_onduleur", "inclure_prise_terre",
)


# ── PVFCH (fondateur 20/08/2026) — « NEVER INVENT NUMBERS » ──────────────────
#
# CE QUI A CHANGÉ, ET POURQUOI. Ce module remplissait jusqu'ici les variables
# d'équipement absentes de la fiche avec les DÉFAUTS de marché de
# ``solar_design`` (module 450 Wc / 34 V / 41 V / −0,27 %/°C ; onduleur 2 MPPT,
# fenêtre 120-500 V, 600 V absolus, démarrage 90 V) et, à défaut, avec une
# REGEX sur le libellé de la ligne (« 10 kW », « triphasé »). Trois de ces
# nombres décidaient de grandeurs remises à un tiers :
#
#   * ``v_max_abs`` (600 V par défaut) est la borne dont le dépassement est
#     BLOQUANT — un onduleur réel en 1100 V se voyait refuser des chaînes
#     parfaitement admissibles, et un onduleur réel en 500 V se voyait valider
#     des chaînes qui l'auraient DÉTRUIT ;
#   * ``isc_a`` du module, quand la fiche ne le donnait pas, était FABRIQUÉ
#     (``Imp × 1,06``, Imp lui-même déduit de ``Pmax / Vmp``) — et c'est lui
#     qui fixe le calibre des fusibles de chaîne (``core.electrique.protections``)
#     et la section des câbles DC (``core.electrique.cables``) ;
#   * ``phases`` retombait en monophasé dès que le mot « triphasé » manquait au
#     libellé, divisant tout le courant AC par √3.
#
# LA RÈGLE EST DÉSORMAIS SANS EXCEPTION : une variable d'ÉQUIPEMENT vient de la
# FICHE TECHNIQUE (``stock.FicheTechnique`` via ``specs_for_produit``) ou le
# calcul REFUSE en DISANT quel champ manque. Aucun repli, aucune regex, aucune
# valeur déduite d'une autre.
#
# CE QUI RESTE, ET POURQUOI CE N'EST PAS LA MÊME CHOSE : les constantes
# d'INGÉNIERIE ne sont pas des données d'équipement et gardent leurs valeurs —
# le forfait de liaison DC/AC (30 m / 15 m, décision fondateur 19/08/2026), les
# températures de dimensionnement (−5 °C / 70 °C), le régime de neutre TT, et
# tout le corpus normatif du moteur (ampacités, calibres normalisés, chutes de
# tension admissibles, NF C 15-100 / UTE C 15-712-1). Elles ne décrivent aucun
# appareil : elles décrivent le SITE et la NORME.
#
# LES DEUX REPLIS DE FICHE CONSERVÉS sont des replis vers une AUTRE VALEUR DE
# LA MÊME FICHE, jamais vers un nombre inventé, et le moteur les documente
# déjà : ``v_demarrage_v`` → bas de plage MPPT, ``isc_max_mppt_a`` →
# ``i_max_mppt_a`` (repli PRUDENT, jamais plus permissif).

#: Variables d'ÉQUIPEMENT du MODULE que le calcul consomme réellement, avec
#: leur libellé français. Libellés alignés sur ceux du formulaire produit
#: (``ProduitForm.jsx``, section « Fiche technique ») : le fondateur doit lire
#: EXACTEMENT le nom du champ qu'il va remplir.
VARIABLES_MODULE_REQUISES = (
    ("pmax_wc", "puissance crête (Wc)"),
    ("voc_v", "tension circuit ouvert — Voc (V)"),
    ("vmp_v", "tension au point de puissance max — Vmp (V)"),
    ("isc_a", "courant court-circuit — Isc (A)"),
    ("imp_a", "courant au point de puissance max — Imp (A)"),
    ("temp_coeff_voc_pct_c", "coefficient de température Voc (%/°C)"),
    ("temp_coeff_pmax_pct_c", "coefficient de température Pmax (%/°C)"),
)

#: Variables d'ÉQUIPEMENT de l'ONDULEUR que le calcul consomme réellement.
#: Les libellés sont MOT POUR MOT ceux de ``CONTRAT_ONDULEUR``
#: (``apps/stock/selectors.py``) : le verrou du catalogue et celui-ci doivent
#: nommer la même variable de la même façon, sans quoi le fondateur cherche
#: deux champs différents pour un seul trou.
#:
#: N'y figurent PAS ``rendement_euro_pct`` (aucun calcul ne le consomme — il
#: est PUBLIÉ, et reste donc absent du schéma tant qu'une fiche ne le donne
#: pas), ``v_demarrage_v`` ni ``isc_max_mppt_a`` (leurs replis restent des
#: valeurs de la MÊME fiche, cf. le bandeau ci-dessus).
VARIABLES_ONDULEUR_REQUISES = (
    ("ac_kw", "puissance AC (kW)"),
    ("phases", "monophasé / triphasé"),
    ("n_mppt", "nombre d'entrées MPPT"),
    ("mppt_v_min", "plage MPPT — tension mini (V)"),
    ("mppt_v_max", "plage MPPT — tension maxi (V)"),
    ("v_max_abs", "tension DC maximale (V)"),
    ("i_max_mppt_a", "courant maxi par MPPT (A)"),
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


#: Marqueur posé par ``seed_catalogue`` sur la description d'un produit dont le
#: modèle constructeur a été TRANCHÉ par le fondateur. Son jumeau « Modèle
#: supposé : … — à confirmer fondateur » n'est délibérément PAS lu : un numéro
#: de modèle supposé imprimé sur un schéma remis au gestionnaire de réseau se
#: lirait comme une déclaration, alors que personne ne l'a vérifié.
MARQUEUR_MODELE_CONFIRME = 'Modèle confirmé fondateur :'


def _modele_confirme(produit):
    """Le modèle constructeur CONFIRMÉ d'un produit, ou ``""``."""
    description = getattr(produit, "description", "") or ""
    for ligne in description.splitlines():
        if ligne.startswith(MARQUEUR_MODELE_CONFIRME):
            return ligne[len(MARQUEUR_MODELE_CONFIRME):].strip()
    return ""


def _designation_materiel(produit, libelle, grandeur=""):
    """Comment NOMMER un appareil sur une pièce technique, du sûr au flou.

    Trois sources, dans cet ordre : le modèle CONFIRMÉ par le fondateur (le
    seul numéro de modèle qu'on ait le droit d'imprimer), sinon la marque
    accompagnée de la grandeur certaine (« Deye 10 kW », « Canadien Solar
    710 Wc »), sinon le libellé de la ligne du devis. Vide quand on ne sait
    rien : le schéma retombe alors sur son intitulé générique plutôt que
    d'afficher une identité fabriquée.
    """
    modele = _modele_confirme(produit)
    if modele:
        return modele
    marque = (getattr(produit, "marque", "") or "").strip()
    if marque:
        return ("%s %s" % (marque, grandeur)).strip() if grandeur else marque
    return (libelle or "").strip()


def _texte_grandeur(valeur, unite, decimales=0):
    """« 710 Wc » / « 10 kW » — vide si la grandeur n'est pas connue."""
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return ""
    if nombre <= 0:
        return ""
    return ("%.*f" % (decimales, nombre)).replace(".", ",") + " " + unite


def specs_module_du_devis(devis):
    """``(specs, produit, libellé)`` du panneau du devis — fiche BRUTE, sans
    aucun repli. ``specs`` est le dict de ``specs_for_produit`` : une variable
    non saisie y est simplement ABSENTE (jamais rendue à ``None``)."""
    from apps.ventes import solar_design as sd

    produit, libelle = _produit_de_famille(
        devis, lambda designation, nom: sd.is_panel(designation, nom))
    return _specs_produit(produit), produit, libelle


def spec_module_du_devis(devis):
    """``SpecModule`` du panneau du devis — LA FICHE, ou rien.

    PVFCH (fondateur 20/08/2026) : plus AUCUN repli. Une variable absente de la
    fiche vaut ``0.0`` ici et fait REFUSER le calcul en amont
    (``fiches_manquantes_du_devis``) — elle n'est jamais remplacée par un
    défaut de marché, par une regex sur le libellé de la ligne, ni déduite
    d'une autre variable. Un ``0.0`` qui atteindrait le moteur serait un bug de
    l'appelant, pas une valeur de repli.
    """
    from core.electrique.types import SpecModule

    specs, produit, libelle = specs_module_du_devis(devis)
    pmax = _flottant(specs.get("pmax_wc"), 0.0)
    return SpecModule(
        vmp_v=_flottant(specs.get("vmp_v"), 0.0),
        voc_v=_flottant(specs.get("voc_v"), 0.0),
        isc_a=_flottant(specs.get("isc_a"), 0.0),
        imp_a=_flottant(specs.get("imp_a"), 0.0),
        pmax_wc=pmax,
        temp_coeff_voc_pct_c=_flottant(
            specs.get("temp_coeff_voc_pct_c"), 0.0),
        temp_coeff_pmax_pct_c=_flottant(
            specs.get("temp_coeff_pmax_pct_c"), 0.0),
        designation=_designation_materiel(
            produit, libelle, _texte_grandeur(pmax, "Wc")),
    )


def specs_onduleur_du_devis(devis):
    """``(specs, produit, libellé)`` de l'onduleur du devis — fiche BRUTE."""
    from apps.ventes import solar_design as sd

    produit, libelle = _produit_de_famille(
        devis, lambda designation, nom: sd.is_any_inverter(designation)
        or sd.is_any_inverter(nom))
    return _specs_produit(produit), produit, libelle


def spec_onduleur_du_devis(devis):
    """``SpecOnduleur`` de l'onduleur du devis — LA FICHE, ou rien.

    Retourne aussi le nombre de PHASES : PVFCH (fondateur 20/08/2026) — il se
    lit sur la fiche (``FicheTechnique.ond_phases``) et NULLE PART ailleurs. La
    regex historique sur le libellé (« triphasé » / « tétrapolaire ») est
    SUPPRIMÉE : un onduleur dont la ligne omettait le mot repassait en
    monophasé sans le dire, divisant tout le courant AC par √3. Sans fiche,
    ``phases`` vaut 0 et le calcul refuse — il ne devine plus.
    """
    from core.electrique.types import SpecOnduleur

    specs, produit, libelle = specs_onduleur_du_devis(devis)
    ac_kw = _flottant(specs.get("ac_kw"), 0.0)
    phases = _entier(specs.get("phases"), 0)
    if phases not in (1, 3):
        phases = 0

    onduleur = SpecOnduleur(
        n_mppt=_entier(specs.get("n_mppt"), 0),
        mppt_v_min=_flottant(specs.get("mppt_v_min"), 0.0),
        mppt_v_max=_flottant(specs.get("mppt_v_max"), 0.0),
        v_max_abs=_flottant(specs.get("v_max_abs"), 0.0),
        i_max_mppt_a=_flottant(specs.get("i_max_mppt_a"), 0.0),
        ac_kw=ac_kw,
        phases=phases,
        # PVOND-H (2026-08-19) — la fiche fait foi quand elle la donne
        # (``FicheTechnique.ond_v_demarrage_v``) ; à défaut, le repli reste une
        # valeur de la MÊME fiche (bas de plage MPPT, cf. ``SpecOnduleur``),
        # jamais un nombre inventé.
        v_demarrage_v=(_flottant(specs.get("v_demarrage_v"), 0.0) or None),
        # Le rendement n'a PAS de défaut : il reste None tant qu'une fiche ne
        # le donne pas (il serait sinon publié comme une caractéristique
        # vérifiée de l'appareil sur une pièce technique).
        rendement_euro_pct=(_flottant(specs.get("rendement_euro_pct"), 0.0)
                            or None),
        # PVOND-H — même garde que le rendement : PAS de défaut inventé, une
        # borne matérielle plus permissive que ce qu'une fiche garantit serait
        # dangereuse. ``None`` tant qu'aucune fiche ne la donne ; le moteur
        # (``SpecOnduleur.courant_isc_max_a``) retombe alors sur
        # ``i_max_mppt_a``, exactement le repli déjà documenté côté moteur.
        isc_max_mppt_a=(_flottant(specs.get("isc_max_mppt_a"), 0.0) or None),
        designation=_designation_materiel(
            produit, libelle, _texte_grandeur(ac_kw, "kW", 1)),
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
    """``(présente, désignation, kWh, tension)`` du parc de stockage du devis.

    Seul le booléen pilote les règles (il l'a toujours fait) ; les trois
    autres valeurs servent UNIQUEMENT à nommer le matériel sur le schéma, et
    restent vides quand la fiche ne les donne pas.
    """
    from apps.ventes import solar_design as sd
    for ligne in _lignes_du_devis(devis):
        designation = ligne.designation or ""
        produit = getattr(ligne, "produit", None)
        nom = getattr(produit, "nom", "") or ""
        if not (sd.is_battery(designation) or sd.is_battery(nom)):
            continue
        specs = _specs_produit(produit)
        kwh = _flottant(specs.get("kwh_nominal"), 0.0)
        return (True,
                _designation_materiel(produit, designation or nom,
                                      _texte_grandeur(kwh, "kWh", 1)),
                kwh,
                _flottant(specs.get("v_nominal"), 0.0))
    return (False, "", 0.0, 0.0)


# ── PVFCH — le VERROU DE COMPLÉTUDE de l'étude électrique ────────────────────

def fiches_manquantes_du_devis(devis):
    """``[(matériel, libellé), …]`` — les variables d'équipement ABSENTES.

    Même patron que le verrou du catalogue
    (``stock.selectors.onduleur_specs_manquantes``, qui grise un onduleur non
    chiffrable) : on ne calcule pas ce qu'on ne sait pas, et on DIT quel champ
    manque. Liste vide = toutes les variables consommées par le calcul sont sur
    la fiche.

    Un devis SANS panneau et SANS onduleur ne rend RIEN : il n'a pas une fiche
    incomplète, il n'a pas encore de matériel. C'est le cas « aucun module à
    répartir », que le moteur sait déjà dire lui-même.
    """
    manquantes = []
    specs_module, produit_module, libelle_module = specs_module_du_devis(devis)
    if produit_module is not None or libelle_module:
        for cle, libelle in VARIABLES_MODULE_REQUISES:
            if not _flottant(specs_module.get(cle), 0.0):
                manquantes.append(("Panneau", libelle))

    specs_ond, produit_ond, libelle_ond = specs_onduleur_du_devis(devis)
    if produit_ond is not None or libelle_ond:
        for cle, libelle in VARIABLES_ONDULEUR_REQUISES:
            if not _flottant(specs_ond.get(cle), 0.0):
                manquantes.append(("Onduleur", libelle))
    return manquantes


#: Forme GÉNITIVE de chaque matériel — « du panneau », « de l'onduleur ».
#: L'élision n'est pas un détail : un bandeau qui écrit « du onduleur » se lit
#: comme une phrase de machine, pas comme un message à un lecteur.
_GENITIF_MATERIEL = {"Panneau": "du panneau", "Onduleur": "de l'onduleur"}


def motifs_fiche_incomplete(devis):
    """Les motifs de REFUS, en français, prêts à afficher — ``[]`` si complet.

    Un motif par variable manquante : le fondateur doit lire le NOM EXACT du
    champ à remplir et l'écran où le remplir, pas « données insuffisantes ».
    """
    return ["« %s » non renseigné(e) sur la fiche technique %s — "
            "complétez la fiche technique du produit (Stock → Catalogue)."
            % (libelle, _GENITIF_MATERIEL.get(materiel, "du matériel"))
            for materiel, libelle in fiches_manquantes_du_devis(devis)]


#: Préfixe des motifs de refus ÉLECTRIQUE — le pendant, pour la conformité, du
#: « non renseigné(e) sur la fiche technique » de PVFCH. Deux refus voisins mais
#: distincts : PVFCH dit « je ne SAIS pas » (fiche muette), celui-ci dit « je
#: sais, et c'est NON » (deux chiffres de fiche qui ne vont pas ensemble).
MOTIF_NON_CONFORME = "Configuration électrique non conforme : %s"


def motifs_non_conformite_du_devis(devis):
    """Les motifs de refus ÉLECTRIQUE de l'étude STOCKÉE — ``[]`` si conforme.

    DEV-202608-0016 — le schéma unifilaire d'un devis dont l'étude porte un
    BLOQUANT (Isc cumulé au-dessus de la borne d'entrée MPPT publiée, Voc à
    froid au-dessus de la tension maximale absolue, fenêtre de tension vide)
    n'est plus dessiné : une pièce technique qui montre proprement un montage
    que la fiche constructeur n'autorise pas est pire qu'une pièce absente.

    Symétrique de ``motifs_fiche_incomplete`` : même forme (liste de phrases
    françaises prêtes à afficher), même portail (la conception STOCKÉE, seule
    vérité de ``rendre_schema_du_devis``), et AUCUN chiffre ajouté — les
    ampères et les volts cités viennent du moteur, qui les tient lui-même des
    deux fiches. Ne lève jamais.
    """
    conception = conception_electrique_stockee(devis)
    if not conception:
        return []
    conformite = conception.get("conformite")
    if not isinstance(conformite, dict):
        return []
    return [MOTIF_NON_CONFORME % bloquant
            for bloquant in (conformite.get("bloquants") or [])]


def construire_entree(devis, overrides=None):
    """``EntreeElectrique`` complète d'un devis (+ les overrides appliqués).

    La longueur DC par défaut est un FORFAIT (30 m par paire descendante,
    F2 — décision fondateur 19/08/2026) : elle ne dépend plus du nombre de
    chaînes du devis, seulement d'un éventuel override explicite. C'est
    ``core.electrique.cables`` qui compte les PAIRES (une par MPPT réellement
    utilisée) pour le métrage total du bordereau, pas ce module.
    """
    import dataclasses

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

    (batterie_presente, batterie_designation, batterie_kwh,
     batterie_v) = _batterie_du_devis(devis)

    entree = EntreeElectrique(
        module=module,
        onduleur=onduleur,
        groupes=groupes,
        dc_m=0.0,
        ac_m=_flottant(reglages.get("ac_m"), AC_M_DEFAUT),
        phases=phases,
        regime=regime,
        batterie=(bool(reglages["batterie"]) if "batterie" in reglages
                  else batterie_presente),
        batterie_designation=batterie_designation,
        batterie_kwh=batterie_kwh,
        batterie_v_nominal=batterie_v,
        temp_froid_c=_flottant(reglages.get("temp_froid_c"),
                               TEMP_FROID_DEFAUT_C),
        temp_chaud_c=_flottant(reglages.get("temp_chaud_c"),
                               TEMP_CHAUD_DEFAUT_C),
        plafond_kwc_par_onduleur=plafond,
        longueur_chaine_forcee=longueur_forcee,
        zone_keraunique=bool(reglages.get("zone_keraunique")),
        inclure_prise_terre=bool(reglages.get("inclure_prise_terre")),
    )

    if "dc_m" in reglages:
        dc_m = _flottant(reglages.get("dc_m"), DC_M_MINIMUM)
    else:
        dc_m = DC_M_PAR_DEFAUT
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
        "inclure_prise_terre": entree.inclure_prise_terre,
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


def rendre_schema_du_devis(devis):
    """PV81/PVSLD — le schéma unifilaire d'un devis, en SVG, ou ``None``.

    **UNE SEULE VÉRITÉ.** Le schéma a longtemps existé en deux exemplaires qui
    se contredisaient : la page web du client rendait celui du moteur
    ``core.electrique`` (organes réels, protections, repères), pendant que
    l'annexe du PDF dessinait une esquisse à cinq blocs fixes qui ignorait la
    conception — et affichait donc autre chose que la nomenclature imprimée
    juste dessous. Les deux appelants passent maintenant ICI.

    LA CONCEPTION STOCKÉE EST LE PORTAIL : sans ``Devis.electrical_design``
    (PV41), on rend ``None`` — jamais une esquisse fabriquée à la volée. Le SVG
    lui-même est re-RENDU depuis les mêmes entrées (le calcul est pur et
    idempotent par empreinte), parce que le rendu demande les objets du moteur,
    que le contrat stocké ne conserve pas.

    Lecture PURE : aucun statut, aucune ligne, aucun prix (règle #4 ; le moteur
    ignore jusqu'à l'existence d'un montant). Jamais bloquant — une étude
    illisible rend ``None``, pas une erreur.

    TROIS PORTAILS, et un dessin ne sort que s'ils s'ouvrent tous les trois :
    l'étude existe (PV41), les fiches sont complètes (PVFCH), et la conception
    est CONFORME (DEV-202608-0016). Le troisième est le plus récent : 25
    panneaux Canadian Solar 710 Wc (Isc 18,59 A) posés par l'outil 3D sur un
    Deye 5 kW mono dont chaque entrée MPPT admet 17 A se dessinaient sans
    broncher — « MPPT 1 · 3 chaînes », soit trois fois la limite de l'entrée,
    sur un schéma d'aspect officiel destiné au gestionnaire de réseau. Un
    montage que la fiche constructeur n'autorise pas ne se DESSINE pas : le
    motif est journalisé et lisible sur l'étude (``conformite.bloquants``,
    ``motifs_non_conformite_du_devis``), le dessin, lui, n'existe pas.
    """
    if conception_electrique_stockee(devis) is None:
        return None
    # PVFCH (fondateur 20/08/2026) — un schéma unifilaire est une pièce
    # technique remise au gestionnaire de réseau : il ne se dessine JAMAIS avec
    # une tension maximale, une fenêtre MPPT ou un Isc inventés. Fiche
    # incomplète ⇒ pas de schéma, comme un devis sans calepinage.
    if fiches_manquantes_du_devis(devis):
        return None
    from core.electrique import concevoir
    from core.electrique.schema import rendre_schema

    entree = construire_entree(devis)
    if not entree.groupes:
        return None

    resultat = concevoir(entree)
    # DEV-202608-0016 — CONFORMITÉ : le rendu lit enfin le verdict qu'il
    # ignorait. Même omission que PVFCH (``None``, jamais une erreur, jamais
    # une esquisse de repli), mais le motif est JOURNALISÉ : un schéma qui
    # disparaît sans laisser de trace est indébuggable.
    if resultat.conformite.bloquants:
        logger.warning(
            "DEV-202608-0016 : schéma unifilaire NON rendu pour le devis %s — "
            "%s", getattr(devis, "pk", None),
            MOTIF_NON_CONFORME % resultat.conformite.bloquants[0])
        return None

    date_creation = getattr(devis, "date_creation", None)
    cartouche = {
        "client": getattr(getattr(devis, "client", None), "nom", "") or "",
        "reference": getattr(devis, "reference", "") or "",
        "date": date_creation.strftime("%d/%m/%Y") if date_creation else "",
    }
    return rendre_schema(entree, resultat, cartouche=cartouche)


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
    from core.electrique.types import Conformite, ResultatElectrique

    entree = construire_entree(devis, overrides)
    empreinte = empreinte_entree(devis, entree)

    stockee = conception_electrique_stockee(devis)
    if stockee is not None \
            and getattr(devis, "electrical_design_hash", None) == empreinte:
        return stockee

    # PVFCH (fondateur 20/08/2026) — FICHE INCOMPLÈTE : on rend le contrat
    # COMPLET EN FORME (toutes les clés, listes vides) mais VIDE DE NOMBRES, et
    # on DIT dans ``bloquants`` quel champ manque. L'écran affiche déjà cette
    # liste telle quelle (``ConceptionElectrique.jsx``) et rend « Aucune chaîne
    # calculée » : il dégrade sans rien inventer, sans une ligne de front.
    #
    # ON NE PERSISTE RIEN dans ce cas, et c'est le point important : un refus
    # n'est PAS une étude. ``Devis.electrical_design`` reste ``None``, donc
    # l'annexe technique du PDF (déclenchée par la seule EXISTENCE d'une étude)
    # ne sort pas, le schéma public reste absent, et le repli historique à cinq
    # blocs du builder n'est jamais réveillé pour couvrir un trou de fiche.
    # Sans cela, un devis sans fiche aurait imprimé une esquisse d'aspect
    # officiel au-dessus d'une nomenclature VIDE.
    motifs = motifs_fiche_incomplete(devis)
    if motifs:
        return projeter_contrat(entree, ResultatElectrique(
            conformite=Conformite(conforme=False, bloquants=tuple(motifs)),
            note=("Étude non calculée : une pièce technique ne se dessine pas "
                  "avec des valeurs supposées. Complétez la fiche technique "
                  "du matériel, puis relancez le calcul.",)))

    design = projeter_contrat(entree, concevoir(entree))
    devis.electrical_design = design
    devis.electrical_design_hash = empreinte
    if devis.pk:
        devis.save(update_fields=["electrical_design",
                                  "electrical_design_hash"])
    return design
