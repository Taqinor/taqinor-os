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
           "rafraichir_conception_electrique_devis",
           "rendre_schema_du_devis", "fiches_manquantes_du_devis",
           "motifs_fiche_incomplete", "motifs_non_conformite_du_devis",
           "groupes_protections", "objets_moteur_depuis_contrat",
           "artefact_a_rejouer", "FORMAT_CONTRAT",
           "VARIABLES_MODULE_REQUISES", "VARIABLES_ONDULEUR_REQUISES",
           "DC_M_MINIMUM", "DC_M_PAR_DEFAUT", "AC_M_DEFAUT"]

#: L-1V (24/08/2026) — VERSION DU FORMAT de l'artefact ``electrical_design``.
#: Elle entre dans l'empreinte des entrées : un devis dont l'étude a été rangée
#: sous un format antérieur voit donc son empreinte ne plus concorder, et le
#: PROCHAIN rafraîchissement la recalcule au format courant, sans migration de
#: données ni geste humain. À monter dès qu'une CLÉ est ajoutée au contrat.
FORMAT_CONTRAT = 2

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


def _blob_ligne(ligne):
    """Texte classifiable d'une ligne — désignation ET nom du produit lié.

    Même patron que ``quote_engine.builder._blob_item`` : une désignation
    éditée à la main ne casse pas silencieusement la classification.
    """
    produit = getattr(ligne, "produit", None)
    designation = ligne.designation or ""
    nom = getattr(produit, "nom", "") or ""
    return "%s %s" % (designation, nom)


def _quantite_ligne(ligne):
    try:
        return float(getattr(ligne, "quantite", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _lignes_option_choisie(devis):
    """Les lignes d'UNE SEULE option — celle que la conception électrique lit.

    LANE CHOIX-AVEC (fondateur, 25/08/2026) : « pour toute question où l'on
    est obligé de choisir une seule config et ne peut pas montrer les deux,
    choisis l'option AVEC batterie. » Un schéma unifilaire ne représente
    qu'UN SEUL montage — contrairement au PDF « deux options » ou à la page
    publique, qui peuvent montrer les deux côte à côte. Avant ce correctif,
    ``_produit_de_famille``/``_batterie_du_devis`` lisaient TOUTES les lignes
    du devis sans distinction : sur un devis « deux options servables » (un
    onduleur RÉSEAU, un onduleur HYBRIDE et une batterie, tous trois en
    lignes NON optionnelles — le même état de données que l'artefact
    PV86/L-2OPT de ``quote_engine/builder.py``), ``_produit_de_famille``
    retournait le PREMIER onduleur rencontré par ordre d'insertion — sans
    savoir s'il s'agissait du réseau ou de l'hybride — pendant que
    ``_batterie_du_devis`` additionnait la batterie quelle que soit l'option
    à laquelle elle appartient. Résultat mesuré sur DEV-202608-0024 : un
    schéma unifilaire montrant l'onduleur RÉSEAU Huawei 15 kW avec la
    batterie Dyness 15,4 kWh accrochée dessus — un montage qui n'existe dans
    AUCUN document commercial.

    Même découpage par mots-clés que ``quote_engine.builder._repartir_options``
    (``LigneDevis.variante`` n'existe pas encore sur ce modèle — ``getattr``
    avec défaut ``''`` le lira automatiquement le jour où une autre lane
    l'ajoute, sans changer une ligne de ce code) : une ligne batterie ou
    onduleur hybride n'entre jamais dans le panier SANS, une ligne onduleur
    réseau n'entre jamais dans le panier AVEC ; les lignes neutres (panneaux,
    structure, câblage…) entrent dans LES DEUX paniers.

    CHOIX, dans cet ordre — jamais de mélange entre paniers :
      1. AVEC servable (un onduleur hybride ET une batterie, tous deux en
         lignes du panier AVEC) l'emporte TOUJOURS ;
      2. sinon SANS servable (un onduleur réseau en ligne du panier SANS) ;
      3. sinon repli neutre : TOUTES les lignes (devis mono-option classique
         ou données insuffisantes — PVFCH tranchera plus loin).
    Un devis mono-option (un seul onduleur, éventuellement une batterie) ne
    change JAMAIS de comportement : son unique équipement retombe dans un
    seul panier servable, identique octet pour octet à avant ce correctif.
    """
    from apps.ventes import solar_design as sd

    toutes = _lignes_du_devis(devis)
    sans, avec = [], []
    for ligne in toutes:
        variante = str(getattr(ligne, "variante", "") or "").strip().lower()
        blob = _blob_ligne(ligne)
        ok_sans = not sd.is_battery(blob) and not sd.is_hybrid_inverter(blob)
        ok_avec = not sd.is_reseau_inverter(blob)
        if variante == "sans":
            sans.append(ligne)
        elif variante == "avec":
            avec.append(ligne)
        else:
            if ok_sans:
                sans.append(ligne)
            if ok_avec:
                avec.append(ligne)

    def _presente(lignes, predicat):
        return any(predicat(_blob_ligne(ligne)) and _quantite_ligne(ligne) > 0
                   for ligne in lignes)

    avec_servable = (_presente(avec, sd.is_hybrid_inverter)
                     and _presente(avec, sd.is_battery))
    sans_servable = _presente(sans, sd.is_reseau_inverter)

    if avec_servable:
        return avec
    if sans_servable:
        return sans
    return toutes


def _produit_de_famille(devis, predicat):
    """``(produit, libellé)`` de la première ligne classée par ``predicat``.

    Classification par les mots-clés PARTAGÉS de ``solar_design`` (alignés sur
    ``quote_engine/builder.py``) : la désignation d'abord, le nom du produit
    ensuite — la même lecture que partout ailleurs dans l'app.

    Une ligne SANS produit lié compte quand même : son libellé porte souvent
    tout ce qu'on sait de l'onduleur (« 10 kW triphasé »), et l'ignorer ferait
    silencieusement retomber le calcul en monophasé. Une ligne AVEC fiche prime
    toutefois sur une ligne libre — la fiche est la meilleure source.

    LANE CHOIX-AVEC (fondateur, 25/08/2026) — les lignes parcourues sont
    celles de ``_lignes_option_choisie`` (option AVEC quand servable, sinon
    SANS, sinon toutes), jamais ``devis.lignes.all()`` brut : sur un devis
    « deux options » qui porte réseau + hybride + batterie en lignes, ceci
    évite de retourner le premier onduleur trouvé par ordre d'insertion
    plutôt que celui de l'option retenue (cf. sa docstring, DEV-202608-0024).
    """
    repli = (None, "")
    for ligne in _lignes_option_choisie(devis):
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

    RÉGIME ÉTABLI (lot4) — un parc de batteries compte souvent PLUSIEURS
    unités (packs) en parallèle sur le même bus DC : une ligne « Batterie
    stockage 10 kWh » avec ``quantite=3`` porte 30 kWh, pas 10. Avant ce
    correctif, seule la fiche de l'UNITÉ était lue (``kwh_nominal`` brut),
    quelle que soit la quantité commandée — un devis à 3 packs affichait le
    même « 10,0 kWh » qu'un devis à un seul, sur une pièce technique montrée
    au client. La capacité totale est désormais la somme, sur TOUTES les
    lignes batterie du devis, de ``kwh_nominal × quantite`` (même convention
    que ``quote_engine/builder._battery_kwh_from_items``, qui fait déjà ce
    calcul pour l'estimation d'économies). La tension nominale, elle, ne se
    somme pas : des packs en parallèle partagent la même tension de bus, donc
    celle de la PREMIÈRE ligne batterie identifiée fait foi.

    LANE CHOIX-AVEC (fondateur, 25/08/2026) — parcourt ``_lignes_option_choisie``
    (option AVEC quand servable, sinon SANS, sinon toutes), pas
    ``devis.lignes.all()`` brut : sur un devis « deux options » qui porte
    réseau + hybride + batterie en lignes, une batterie de l'option AVEC ne
    s'accroche plus à l'onduleur RÉSEAU de l'option SANS sur le schéma
    unifilaire (cf. la docstring de ``_lignes_option_choisie``,
    DEV-202608-0024).
    """
    from apps.ventes import solar_design as sd
    presente = False
    kwh_total = 0.0
    designation_ref = ""
    produit_ref = None
    v_nominal = 0.0
    for ligne in _lignes_option_choisie(devis):
        designation = ligne.designation or ""
        produit = getattr(ligne, "produit", None)
        nom = getattr(produit, "nom", "") or ""
        if not (sd.is_battery(designation) or sd.is_battery(nom)):
            continue
        specs = _specs_produit(produit)
        quantite = _flottant(getattr(ligne, "quantite", 1), 1.0) or 1.0
        kwh_total += _flottant(specs.get("kwh_nominal"), 0.0) * quantite
        if not presente:
            designation_ref = designation or nom
            produit_ref = produit
            v_nominal = _flottant(specs.get("v_nominal"), 0.0)
        presente = True
    if not presente:
        return (False, "", 0.0, 0.0)
    return (True,
            _designation_materiel(produit_ref, designation_ref,
                                  _texte_grandeur(kwh_total, "kWh", 1)),
            kwh_total,
            v_nominal)


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
        # L-1V — le FORMAT fait partie des entrées : sans lui, un artefact rangé
        # sous l'ancien format (sans ``materiel``, sans ``version_moteur``)
        # gardait une empreinte VALIDE et n'était donc jamais recalculé, alors
        # que le rendu du schéma a désormais besoin de ces clés.
        "format_contrat": FORMAT_CONTRAT,
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

    L-1V (24/08/2026) — **L'ARTEFACT SE SUFFIT À LUI-MÊME.** Le contrat portait
    jusqu'ici le RÉSULTAT du calcul mais pas ce qu'il fallait pour le REDESSINER :
    ni l'identité du matériel, ni le nombre de modules, ni les repères de câble,
    ni la version du moteur. Le schéma unifilaire rappelait donc ``concevoir()``
    sur les LIGNES COURANTES du devis à chaque rendu — un second calcul, qui
    pouvait dire autre chose que l'étude rangée (c'est exactement ce qui a fait
    diverger la planche et la fiche technique du client). Trois ajouts ferment
    la porte :

    * ``materiel``  — module, onduleur, parc de stockage, nombre de modules :
      tout ce que le CARTOUCHE et les BLOCS nomment. Rien d'inventé — chaque
      valeur vient de l'entrée, et une désignation inconnue reste vide ;
    * ``cote`` sur chaque protection, ``repere``/``nb_conducteurs`` sur chaque
      câble — l'identité des organes, pour que la répartition AC/DC soit une
      DÉCISION DU MOTEUR et non une lecture de libellé en aval ;
    * ``version_moteur``/``schema_version`` — l'estampille, sans laquelle deux
      artefacts identiques à l'œil peuvent sortir de deux moteurs différents
      (même discipline que ``core.calepinage.serialisation``).

    AUCUN de ces champs n'est un nombre nouveau : ce sont les entrées et les
    sorties DÉJÀ calculées, rangées au lieu d'être jetées.
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
            "cote": protection.cote,
        } for protection in resultat.protections],
        "cables": [{
            "repere": cable.repere,
            "liaison": cable.designation,
            "longueur_m": _arrondi(cable.longueur_m),
            "section_mm2": _arrondi(cable.section_mm2, 2),
            "chute_pct": _arrondi(cable.chute_tension_pct, 2),
            "nb_conducteurs": int(cable.nb_conducteurs or 0),
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
        "materiel": {
            "nb_modules": int(entree.nb_modules),
            "module": {
                "designation": entree.module.designation or "",
                "pmax_wc": _arrondi(entree.module.pmax_wc),
            },
            "onduleur": {
                "designation": entree.onduleur.designation or "",
                "ac_kw": _arrondi(entree.onduleur.ac_kw, 2),
                "n_mppt": int(entree.onduleur.n_mppt or 0),
                # Reste ``None`` tant qu'aucune fiche ne le donne : le schéma ne
                # publie un rendement que lorsqu'il en connaît un (cf. PVFCH).
                "rendement_euro_pct": _arrondi(
                    entree.onduleur.rendement_euro_pct)
                if entree.onduleur.rendement_euro_pct else None,
            },
            "batterie": {
                "presente": bool(entree.batterie),
                "designation": entree.batterie_designation or "",
                "kwh": _arrondi(entree.batterie_kwh),
                "v_nominal": _arrondi(entree.batterie_v_nominal),
            },
        },
        "version_moteur": resultat.version_moteur or "",
        "schema_version": int(resultat.schema_version or 0),
    }


# ── L-1V — RELIRE l'artefact : du contrat rangé aux objets du moteur ─────────

def groupes_protections(design):
    """Les organes de l'étude, PRÉ-ROUTÉS par côté — ``{dc, ac, commun}``.

    LE ROUTAGE EST UNE DÉCISION DU MOTEUR, pas une lecture de libellé. La page
    de proposition classait chaque organe en cherchant « dc », « gpv » ou
    « chaîne » dans SA DÉSIGNATION ; le jour où l'anticopie a fusionné les
    lignes du kit en un seul « Kit de fixation, câblage et protection complet »,
    le poste entier est parti du côté alternatif et le client a perdu, sur sa
    fiche technique, TOUS les organes continus que le schéma unifilaire de la
    même page continuait pourtant de dessiner.

    Un organe sans ``cote`` (artefact d'un format antérieur) est rangé en
    ``commun`` : il reste VISIBLE des deux côtés — jamais escamoté.
    """
    from core.electrique.types import COTE_AC, COTE_COMMUN, COTE_DC

    groupes = {COTE_DC: [], COTE_AC: [], COTE_COMMUN: []}
    for organe in (design or {}).get("protections") or []:
        if not isinstance(organe, dict):
            continue
        cote = organe.get("cote")
        groupes.setdefault(cote if cote in groupes else COTE_COMMUN,
                           []).append(organe)
    return groupes


def artefact_a_rejouer(design):
    """L'étude rangée doit-elle être RECALCULÉE avant d'être dessinée ?

    Deux cas, et deux seulement :

    * **format antérieur** — l'artefact ne porte pas ``materiel`` : il a été
      rangé avant L-1V et ne suffit pas à redessiner la planche ;
    * **MAJEUR du moteur qui a bougé** (``core.electrique.version.compatible``) —
      un MAJEUR signifie qu'un nombre publiable a changé à entrée identique.
      Dessiner l'ancien résultat avec le moteur d'aujourd'hui produirait un
      MÉLANGE des deux : on rejoue plutôt le calcul.

    Un artefact d'un MINEUR antérieur reste dessiné TEL QUEL : c'est la
    définition même du MINEUR (aucun nombre publié ne change).
    """
    from core.electrique.version import compatible

    if not isinstance(design, dict) or not design:
        return True
    if not isinstance(design.get("materiel"), dict) or not design["materiel"]:
        return True
    version = design.get("version_moteur") or ""
    try:
        return not compatible(version)
    except ValueError:
        return True


def objets_moteur_depuis_contrat(design):
    """``(entree, resultat)`` RECONSTRUITS depuis le contrat rangé — POUR LE RENDU.

    **CES OBJETS NE SONT PAS RECALCULABLES.** Ils portent exactement ce que le
    contrat conserve : les grandeurs que le DESSIN affiche. Les variables de
    fiche qui n'entrent que dans le CALCUL (Voc, Isc, fenêtre MPPT, tension
    maximale absolue…) n'y sont pas et valent ``0.0`` — les passer à
    ``concevoir()`` produirait un résultat faux. Ils ne servent qu'à
    ``core.electrique.schema.rendre_schema``, qui ne lit que des désignations,
    des quantités, des repères et des calibres.

    ``None`` quand le contrat ne porte pas de quoi dessiner (aucun module) :
    l'appelant rend alors ``None``, jamais une planche à moitié vraie.
    """
    from core.electrique.types import (
        Chaine, Conformite, Cable, EntreeElectrique, GroupePan, Protection,
        ResultatElectrique, SpecModule, SpecOnduleur)

    if not isinstance(design, dict) or not design:
        return None
    materiel = design.get("materiel") if isinstance(
        design.get("materiel"), dict) else {}
    module_src = materiel.get("module") or {}
    onduleur_src = materiel.get("onduleur") or {}
    batterie_src = materiel.get("batterie") or {}
    parametres = design.get("parametres") if isinstance(
        design.get("parametres"), dict) else {}

    nb_modules = _entier(materiel.get("nb_modules"), 0)
    if nb_modules <= 0:
        return None

    phases = _entier(parametres.get("phases"), 1)
    phases = 3 if phases == 3 else 1
    entree = EntreeElectrique(
        module=SpecModule(
            vmp_v=0.0, voc_v=0.0, isc_a=0.0, imp_a=0.0,
            pmax_wc=_flottant(module_src.get("pmax_wc"), 0.0),
            designation=str(module_src.get("designation") or ""),
        ),
        onduleur=SpecOnduleur(
            n_mppt=_entier(onduleur_src.get("n_mppt"), 0),
            mppt_v_min=0.0, mppt_v_max=0.0, v_max_abs=0.0, i_max_mppt_a=0.0,
            ac_kw=_flottant(onduleur_src.get("ac_kw"), 0.0),
            phases=phases,
            rendement_euro_pct=(
                _flottant(onduleur_src.get("rendement_euro_pct"), 0.0) or None),
            designation=str(onduleur_src.get("designation") or ""),
        ),
        groupes=(GroupePan(label="Toiture", nb_modules=nb_modules,
                           azimut_deg=0.0, inclinaison_deg=0.0),),
        dc_m=_flottant(parametres.get("dc_m"), 0.0),
        ac_m=_flottant(parametres.get("ac_m"), 0.0),
        phases=phases,
        regime=str(parametres.get("regime") or "TT"),
        batterie=bool(batterie_src.get("presente")),
        batterie_designation=str(batterie_src.get("designation") or ""),
        batterie_kwh=_flottant(batterie_src.get("kwh"), 0.0),
        batterie_v_nominal=_flottant(batterie_src.get("v_nominal"), 0.0),
    )

    chaines = tuple(Chaine(
        repere="", pan=str(c.get("pan") or ""),
        nb_modules=_entier(c.get("nb_modules"), 0),
        mppt=_entier(c.get("mppt"), 1),
        voc_froid_v=_flottant(c.get("voc_froid_v"), 0.0),
        vmp_froid_v=_flottant(c.get("vmp_froid_v"), 0.0),
        vmp_chaud_v=_flottant(c.get("vmp_chaud_v"), 0.0),
        vmp_stc_v=0.0, isc_a=0.0, imp_a=0.0, puissance_kwc=0.0,
    ) for c in (design.get("chaines") or []) if isinstance(c, dict))

    protections = tuple(Protection(
        repere=str(p.get("repere") or ""),
        designation=str(p.get("designation") or ""),
        calibre=str(p.get("calibre") or ""),
        quantite=_entier(p.get("quantite"), 0),
        regle_source="",
        cote=str(p.get("cote") or "commun"),
    ) for p in (design.get("protections") or []) if isinstance(p, dict))

    cables = tuple(Cable(
        repere=str(c.get("repere") or ""),
        designation=str(c.get("liaison") or ""),
        section_mm2=_flottant(c.get("section_mm2"), 0.0),
        longueur_m=_flottant(c.get("longueur_m"), 0.0),
        nb_conducteurs=_entier(c.get("nb_conducteurs"), 1) or 1,
        ib_a=0.0, in_a=None, iz_a=0.0,
        chute_tension_pct=_flottant(c.get("chute_pct"), 0.0),
        chute_cible_pct=0.0, chute_max_pct=0.0, conforme=True,
        critere_dimensionnant="", regle_source="",
    ) for c in (design.get("cables") or []) if isinstance(c, dict))

    conformite_src = design.get("conformite") if isinstance(
        design.get("conformite"), dict) else {}
    resultat = ResultatElectrique(
        chaines=chaines,
        conformite=Conformite(
            conforme=bool(conformite_src.get("conforme", True)),
            bloquants=tuple(conformite_src.get("bloquants") or ()),
            alertes=tuple(conformite_src.get("alertes") or ()),
        ),
        protections=protections,
        cables=cables,
        note=tuple(design.get("note") or ()),
        # Le cartouche imprime LA VERSION DE L'ARTEFACT, pas celle du moteur qui
        # tourne : c'est l'estampille du dossier remis, pas celle du jour.
        version_moteur=str(design.get("version_moteur") or ""),
        schema_version=_entier(design.get("schema_version"), 0),
    )
    return entree, resultat


# ── API publique ─────────────────────────────────────────────────────────────

def conception_electrique_stockee(devis):
    """La conception DÉJÀ calculée d'un devis, ou ``None``."""
    design = getattr(devis, "electrical_design", None)
    return design if isinstance(design, dict) and design else None


def _artefact_rejouable(devis):
    """L'étude rangée du devis, RECALCULÉE UNE FOIS si son format a vieilli.

    Rejeu ONE-SHOT, jamais un dégradé silencieux : un artefact d'un format
    antérieur (ou d'un MAJEUR de moteur périmé) est recalculé au premier rendu
    qui en a besoin, puis rangé — les rendus suivants relisent simplement. Sans
    ce rejeu, un devis d'avant L-1V perdrait son schéma jusqu'à sa prochaine
    modification de lignes. L'empreinte porte ``FORMAT_CONTRAT``, donc le calcul
    a réellement lieu (le raccourci d'idempotence ne se déclenche pas).

    Ne lève jamais : un rejeu impossible rend ``None`` et le schéma est
    simplement absent — jamais une planche mi-ancienne mi-nouvelle.
    """
    design = conception_electrique_stockee(devis)
    if design is None:
        return None
    if not artefact_a_rejouer(design):
        return design
    try:
        # L'empreinte porte le FORMAT (donc un artefact écrit par du code
        # antérieur ne concorde plus), mais un artefact devenu illisible pour
        # une AUTRE raison — MAJEUR périmé — garderait une empreinte valide et
        # le raccourci d'idempotence rendrait l'ancien contrat tel quel. On
        # invalide donc explicitement : « ceci n'est pas utilisable, recalcule ».
        devis.electrical_design_hash = None
        rejoue = build_electrical_design(devis)
    except Exception:  # noqa: BLE001
        logger.warning(
            "L-1V : rejeu de la conception électrique impossible sur %s",
            getattr(devis, "reference", "?"), exc_info=True)
        return None
    if artefact_a_rejouer(rejoue):
        # Le rejeu n'a rien produit de dessinable (fiche redevenue incomplète —
        # ``build_electrical_design`` rend alors un contrat de REFUS non
        # persisté). Dégradé propre : pas de schéma.
        return None
    return rejoue


def rendre_schema_du_devis(devis, *, standard=False):
    """PV81/PVSLD — le schéma unifilaire d'un devis, en SVG, ou ``None``.

    **UNE SEULE VÉRITÉ.** Le schéma a longtemps existé en deux exemplaires qui
    se contredisaient : la page web du client rendait celui du moteur
    ``core.electrique`` (organes réels, protections, repères), pendant que
    l'annexe du PDF dessinait une esquisse à cinq blocs fixes qui ignorait la
    conception — et affichait donc autre chose que la nomenclature imprimée
    juste dessous. Les deux appelants passent maintenant ICI.

    **L-1V (fondateur 24/08/2026) — LA CONCEPTION STOCKÉE EST LA SOURCE, PLUS
    SEULEMENT LE PORTAIL.** Jusqu'ici, l'artefact ne servait que de laissez-
    passer : sa présence autorisait le dessin, mais le dessin lui-même était
    RECALCULÉ depuis les lignes COURANTES du devis (``construire_entree`` +
    ``concevoir``). Deux surfaces de la même page lisaient donc deux vérités —
    la planche parlait des lignes d'aujourd'hui, la fiche technique de l'étude
    rangée hier — et rien ne pouvait le signaler. Le contrat porte désormais
    tout ce que le dessin réclame (``materiel``, repères de câble, estampille),
    et le SVG se reconstruit à partir de LUI
    (``objets_moteur_depuis_contrat``) : le schéma ne peut plus montrer un
    organe absent de l'étude, ni en taire un qu'elle porte.

    ``standard`` — niveau de partage « standard » : désignations, quantités et
    repères, jamais un calibre ni une section (L-NIV). La dégradation est faite
    par le moteur de rendu lui-même, plus par un filtre appliqué au SVG fini
    (qui laissait les calibres dans les sous-titres des blocs).

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
    design = _artefact_rejouable(devis)
    if design is None:
        return None
    # PVFCH (fondateur 20/08/2026) — un schéma unifilaire est une pièce
    # technique remise au gestionnaire de réseau : il ne se dessine JAMAIS avec
    # une tension maximale, une fenêtre MPPT ou un Isc inventés. Fiche
    # incomplète ⇒ pas de schéma, comme un devis sans calepinage. Ce portail
    # lit les fiches COURANTES : c'est un REFUS, jamais une source de dessin —
    # il peut faire disparaître la planche, jamais en changer un trait.
    if fiches_manquantes_du_devis(devis):
        return None
    from core.electrique.schema import rendre_schema

    # DEV-202608-0016 — CONFORMITÉ : le verdict lu est celui de L'ÉTUDE RANGÉE
    # (``motifs_non_conformite_du_devis`` lit la même source), plus celui d'un
    # calcul refait à la volée. Même omission que PVFCH (``None``, jamais une
    # erreur, jamais une esquisse de repli), mais le motif est JOURNALISÉ : un
    # schéma qui disparaît sans laisser de trace est indébuggable.
    bloquants = ((design.get("conformite") or {}).get("bloquants")
                 if isinstance(design.get("conformite"), dict) else None)
    if bloquants:
        logger.warning(
            "DEV-202608-0016 : schéma unifilaire NON rendu pour le devis %s — "
            "%s", getattr(devis, "pk", None),
            MOTIF_NON_CONFORME % bloquants[0])
        return None

    objets = objets_moteur_depuis_contrat(design)
    if objets is None:
        return None
    entree, resultat = objets

    date_creation = getattr(devis, "date_creation", None)
    cartouche = {
        "client": getattr(getattr(devis, "client", None), "nom", "") or "",
        "reference": getattr(devis, "reference", "") or "",
        "date": date_creation.strftime("%d/%m/%Y") if date_creation else "",
    }
    return rendre_schema(entree, resultat, cartouche=cartouche,
                         standard=standard)


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


def rafraichir_conception_electrique_devis(devis):
    """L-SLD (24/08/2026) — pose l'étude électrique À L'ENREGISTREMENT du devis.

    LE TROU QUE CECI BOUCHE. ``build_electrical_design`` n'avait qu'UN SEUL
    appelant en production : l'action ``conception-electrique`` du devis,
    c'est-à-dire l'OUVERTURE de l'onglet par un vendeur. Un devis créé par
    l'écran générateur (``POST /devis/atomic/``) et jamais ouvert dans cet
    onglet n'avait donc AUCUNE ``electrical_design`` — et comme la conception
    stockée est le PORTAIL unique du schéma unifilaire
    (``rendre_schema_du_devis``), la page client (même au niveau « confiance »)
    et l'annexe technique du PDF étaient muettes sur un devis pourtant complet.
    Même esprit et même place que ``services.rafraichir_etude_horaire_devis`` /
    ``rafraichir_dimensionnement_devis`` : le chemin d'enregistrement pose ce
    que les écrans lisent, au lieu d'attendre un geste humain.

    LES TROIS PORTAILS SONT CEUX DU SCHÉMA, mot pour mot — on ne range une
    étude automatiquement que si elle est DESSINABLE : des modules à répartir
    (``entree.groupes``), des fiches techniques COMPLÈTES (PVFCH), et une
    conformité SANS bloquant (DEV-202608-0016). Sinon on ne persiste RIEN et
    ``Devis.electrical_design`` reste ``None`` — dégradé propre, jamais une
    étude vide : l'annexe technique du PDF se déclenche sur la seule EXISTENCE
    d'une conception (``quote_engine/builder``), et un devis de pompage, un
    devis à micro-onduleurs non modélisés ou une fiche muette imprimeraient
    sinon une annexe sans nomenclature. Le vendeur, lui, garde le diagnostic
    complet : l'onglet ``conception-electrique`` calcule toujours à la demande
    et DIT ce qui manque.

    Zéro chiffre inventé : tout vient des lignes du devis et des deux fiches
    (le moteur ``core.electrique`` est pur et ignore jusqu'à l'existence d'un
    montant). Ne lève JAMAIS, ne touche ni statut, ni ligne, ni prix
    (règle #4) — un devis correctement enregistré n'est jamais annulé par une
    étude. Rend le contrat rangé, ou ``None``.
    """
    try:
        entree = construire_entree(devis)
        if not entree.groupes:
            return None
        if fiches_manquantes_du_devis(devis):
            return None
        from core.electrique import concevoir
        resultat = concevoir(entree)
        if resultat.conformite.bloquants:
            logger.info(
                "L-SLD : conception électrique NON rangée pour le devis %s — "
                "%s", getattr(devis, "reference", "?"),
                MOTIF_NON_CONFORME % resultat.conformite.bloquants[0])
            return None
        return build_electrical_design(devis)
    except Exception:  # noqa: BLE001 — une étude ratée n'empêche jamais un
        # enregistrement de devis/lignes (même contrat que les rafraîchisseurs
        # de ``services.py``).
        logger.warning(
            "rafraichir_conception_electrique_devis indisponible sur %s",
            getattr(devis, "reference", "?"), exc_info=True)
        return None
