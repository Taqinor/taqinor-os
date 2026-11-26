# -*- coding: utf-8 -*-
"""LOT 6 (SCHEL-B1) — LE SCHÉMA ÉLECTRIQUE : un document, et son dessin en blocs.

Demande du fondateur (26/11/2026) : l'ancien schéma unifilaire du devis est
remplacé, sur la page client, dans l'annexe technique du PDF et sur la fiche
devis de l'ERP, par le « schéma électrique » du calepinage — une rangée colorée
par chaîne avec ses panneaux, le coffret côté panneaux, l'onduleur et ses
entrées, le coffret côté réseau, le compteur de production, le TGBT, le réseau —
et la BATTERIE quand la conception en porte une.

CE MODULE EST LA SEULE COMPOSITION DE CE DOCUMENT. Les trois écrans le lisent
tel quel (contrat ``apps/ventes/contract_samples/schema_electrique.json``) ;
aucun d'eux ne recompose chaînes, couleurs ou organes. Il est PUR (stdlib et
``core.electrique`` seulement, aucune application) et ne connaît aucun montant :
désignations, quantités, repères, calibres et sections, rien d'autre.

DEUX RÈGLES QUI NE SE NÉGOCIENT PAS.
* Toutes les clés d'un document sont TOUJOURS présentes (leçon PACT10). Une
  grandeur que personne n'a calculée ou qu'aucune fiche ne publie vaut ``None``
  — jamais un chiffre deviné, jamais un zéro de remplissage.
* Les organes sont ceux de ``core/electrique/schema.py::blocs_du_schema``, dans
  son ordre : le document ne retient rien que la planche détaillée ne retienne.

``rendre_schema_electrique_svg`` dessine ce document côté serveur pour
l'annexe PV46 du PDF (fr / en / ar) : mêmes bandes, mêmes cartes, mêmes
couleurs que l'écran du calepinage.
"""

import math
import re
from html import escape

from core.electrique.schema import (
    MENTION_A_CONFIRMER, MENTION_DECOUPLAGE, PALETTE_CHAINES, blocs_du_schema,
)
from core.electrique.types import fr

__all__ = [
    "VERSION_DOCUMENT", "SOURCE_CALEPINAGE", "SOURCE_CONCEPTION_DEVIS",
    "SOURCE_LIGNES_DEVIS", "SOURCES", "OPTION_SANS", "OPTION_AVEC", "OPTIONS",
    "ETAT_CALCULE", "ETAT_A_CALCULER", "ETAT_HORS_RESEAU", "CLES_DOCUMENT",
    "couleur_de_chaine", "chaines_colorees", "chaines_du_resultat", "troncons_du_resultat",
    "document_schema_electrique", "document_sans_repartition",
    "rendre_schema_electrique_svg",
]

#: Version du document servi (contrat ``schema_electrique.json``).
VERSION_DOCUMENT = 1

#: D'où viennent les chaînes dessinées (règle de source D-ACAL-131).
SOURCE_CALEPINAGE = "calepinage"
SOURCE_CONCEPTION_DEVIS = "conception_devis"
SOURCE_LIGNES_DEVIS = "lignes_devis"
SOURCES = (SOURCE_CALEPINAGE, SOURCE_CONCEPTION_DEVIS, SOURCE_LIGNES_DEVIS)

#: Les clés d'option — celles de ``option_totals`` de la page client.
OPTION_SANS = "sans_batterie"
OPTION_AVEC = "avec_batterie"
OPTIONS = (OPTION_SANS, OPTION_AVEC)

#: État du côté alternatif (``cote_reseau.etat``).
ETAT_CALCULE = "calcule"
ETAT_A_CALCULER = "a_calculer"
ETAT_HORS_RESEAU = "hors_reseau"
_ETATS = (ETAT_CALCULE, ETAT_A_CALCULER, ETAT_HORS_RESEAU)

#: Les clés d'un document, dans l'ordre du contrat — toujours toutes présentes.
CLES_DOCUMENT = (
    "version", "source", "option", "calibres_masques", "panneaux",
    "chaines_reparties", "chaines", "coffret_dc", "onduleurs", "batterie",
    "coffret_ac", "compteur_production", "tgbt", "etage_mt", "reseau",
    "cote_reseau", "liaisons", "terre",
)

#: Les organes de chaque coffret (clefs de ``Bloc``), dans l'ordre du moteur.
#: ``organe_dc`` (ACAL1551) : un organe côté continu retenu hors chaîne canonique
#: (``schema.organes_dc_hors_chaine``) — ``organe_dc#2``… pour les suivants.
_ORGANES_DC = ("fusibles", "parafoudre_dc", "sectionneur_dc", "organe_dc")
_ORGANES_AC = ("disjoncteur_ac", "parafoudre_ac", "ddr")
#: Les blocs de l'étage moyenne tension (``blocs_etage_mt``).
_BLOCS_MT = ("transformateur_mt", "cellule_mt", "decouplage_mt",
             "compteur_production_mt", "limiteur_injection")
#: Les familles de blocs reliées à la barrette de terre — la condition de
#: ``core/electrique/schema.py::_barrette_de_terre`` (``_A_LA_TERRE``).
_A_LA_TERRE = ("champ", "onduleur", "tgbt")


# ──────────────────────────────────────────────────────────── petites valeurs
def _positif(valeur):
    """Un nombre STRICTEMENT positif et fini — entier quand il l'est — sinon
    ``None`` : un zéro de fiche muette n'est jamais publié comme une valeur."""
    if isinstance(valeur, bool) or valeur is None:
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(nombre) or nombre <= 0:
        return None
    if abs(nombre - round(nombre)) < 1e-9:
        return int(round(nombre))
    return round(nombre, 2)


def _entier_positif(valeur):
    nombre = _positif(valeur)
    if nombre is None:
        return None
    return int(round(nombre))


def _texte(valeur):
    texte = str(valeur or "").strip()
    return texte or None


# ──────────────────────────────────────────────────────────────── chaînes
def couleur_de_chaine(numero):
    """S3 — LA couleur d'une chaîne, liée à son NUMÉRO (jamais à son rang d'apparition) : la chaîne 1 est
    toujours la première teinte de ``PALETTE_CHAINES``, la 2 la deuxième, etc. (modulo la palette). Source
    unique : la table d'affectation servie, son éditeur, le schéma, sa légende, le PDF et le plan de câblage
    la lisent ; un recâblage manuel qui change l'ordre des modules ne change plus aucune couleur."""
    return PALETTE_CHAINES[(int(numero) - 1) % len(PALETTE_CHAINES)]


def chaines_colorees(chaines):
    """Les chaînes servies : une entrée par chaîne, rangée par ``numero``.

    ``chaines`` : ``[{numero, nb_panneaux, onduleur, entree}, …]`` dans l'ordre
    de PREMIÈRE APPARITION (celui de la table d'affectation du calepinage, ou
    celui du moteur). ``couleur_index`` = (numéro − 1) modulo la palette ;
    ``couleur`` = ``couleur_de_chaine(numero)`` — la règle de
    ``apps/calepinage/services/chaines.py::_colorer``, liée au NUMÉRO.
    Deux entrées du même numéro s'additionnent ; une chaîne sans numéro ni
    panneau n'est pas une chaîne et n'est pas servie.
    """
    par_numero = {}
    for chaine in chaines or ():
        numero = _entier_positif((chaine or {}).get("numero"))
        nombre = _entier_positif((chaine or {}).get("nb_panneaux"))
        if numero is None or nombre is None:
            continue
        if numero in par_numero:
            par_numero[numero]["nb_panneaux"] += nombre
            continue
        index = (numero - 1) % len(PALETTE_CHAINES)
        par_numero[numero] = {
            "numero": numero,
            "couleur_index": index,
            "couleur": couleur_de_chaine(numero),
            "nb_panneaux": nombre,
            "onduleur": _entier_positif(chaine.get("onduleur")),
            "entree": _entier_positif(chaine.get("entree")),
        }
    return [par_numero[numero] for numero in sorted(par_numero)]


def chaines_du_resultat(resultat):
    """Les chaînes du MOTEUR (``ResultatElectrique.chaines``), dans son ordre.

    Le numéro est celui du repère (« CH7 » → 7) quand il en porte un, sinon le
    rang ; l'entrée est l'entrée MPPT ; ``onduleur`` reste ``None`` : la
    conception d'un devis ne rattache aucune chaîne à un exemplaire.
    """
    sortie = []
    for rang, chaine in enumerate(getattr(resultat, "chaines", ()) or (),
                                  start=1):
        chiffres = "".join(c for c in str(getattr(chaine, "repere", "") or "")
                           if c.isdigit())
        sortie.append({
            "numero": int(chiffres) if chiffres else rang,
            "nb_panneaux": getattr(chaine, "nb_modules", None),
            "onduleur": None,
            "entree": getattr(chaine, "mppt", None),
        })
    return tuple(sortie)


def troncons_du_resultat(resultat):
    """``({cote, section_mm2, longueur_m}, …)`` lus sur les câbles du moteur :
    ``W1`` est la liaison continue, ``W2`` (et ses branches ``W2.N``) la
    liaison alternative (``core/electrique/cables.py``)."""
    sortie = []
    for cable in getattr(resultat, "cables", ()) or ():
        repere = str(getattr(cable, "repere", "") or "")
        cote = "dc" if repere.startswith("W1") else (
            "ac" if repere.startswith("W2") else None)
        if cote is None:
            continue
        sortie.append({"cote": cote,
                       "section_mm2": getattr(cable, "section_mm2", None),
                       "longueur_m": getattr(cable, "longueur_m", None)})
    return tuple(sortie)


def _liaison(troncons, cote, masque):
    """Section commune à TOUS les tronçons du côté, sinon ``None`` ; longueur
    seulement quand le côté n'a qu'UN tronçon (aucune attribution devinée)."""
    du_cote = [t for t in troncons or () if (t or {}).get("cote") == cote]
    if masque or not du_cote:
        return {"section_mm2": None, "longueur_m": None}
    sections = {_positif(t.get("section_mm2")) for t in du_cote}
    section = next(iter(sections)) if len(sections) == 1 else None
    longueur = (_positif(du_cote[0].get("longueur_m")) if len(du_cote) == 1
                else None)
    return {"section_mm2": section, "longueur_m": longueur}


# ──────────────────────────────────────────────────────────────── organes
def _protections(resultat):
    return {getattr(p, "repere", ""): p
            for p in getattr(resultat, "protections", ()) or ()}


def _coffret(blocs, protections, clefs, masque, libelles):
    """``{organes: [...]}`` des organes RETENUS du coffret, ou ``None``."""
    organes = []
    for bloc in blocs:
        if bloc.clef.split("#", 1)[0] not in clefs:
            continue
        protection = protections.get(bloc.repere)
        organes.append({
            "clef": bloc.clef,
            "repere": _texte(bloc.repere),
            "titre": _texte(libelles.get(bloc.clef)) or bloc.titre,
            "calibre": (None if masque or protection is None
                        else _texte(getattr(protection, "calibre", ""))),
            "quantite": (_entier_positif(getattr(protection, "quantite", None))
                         if protection is not None else None),
        })
    return {"organes": organes} if organes else None


def _simple(blocs, clef, libelles):
    for bloc in blocs:
        if bloc.clef == clef:
            return {"titre": _texte(libelles.get(clef)) or bloc.titre,
                    "detail": _texte(bloc.sous_titre)}
    return None


def _detail_mt(bloc):
    if bloc.clef == "decouplage_mt":
        return "%s · %s" % (MENTION_A_CONFIRMER, MENTION_DECOUPLAGE)
    morceaux = [m.strip() for m in (bloc.sous_titre or "").split("\n")]
    return " · ".join(m for m in morceaux if m) or MENTION_A_CONFIRMER


def _etage_mt(blocs, libelles):
    return [{"clef": bloc.clef,
             "titre": _texte(libelles.get(bloc.clef)) or bloc.titre,
             "detail": _detail_mt(bloc)}
            for bloc in blocs if bloc.clef in _BLOCS_MT]


def _batterie(entree, batterie, unites, masque):
    """Le parc de stockage de l'option, ou ``None``.

    ``batterie`` ``None`` : lu sur l'entrée du moteur (``EntreeElectrique.
    batterie`` et ses grandeurs) ; un dict ``{designation, unites,
    capacite_kwh, tension_v}`` : résolu par l'appelant (fiche × unités) ; faux
    (``False`` / ``{}``) : l'option n'a pas de batterie. ``protection`` reste
    ``None`` : aucune protection batterie n'est calculée (décision fondateur du
    19/08/2026, ``core/electrique/protections.py`` § 9).
    """
    if batterie is None:
        if not getattr(entree, "batterie", False):
            return None
        batterie = {
            "designation": getattr(entree, "batterie_designation", ""),
            "unites": unites,
            "capacite_kwh": getattr(entree, "batterie_kwh", None),
            "tension_v": getattr(entree, "batterie_v_nominal", None),
        }
    if not batterie:
        return None
    return {
        "designation": _texte(batterie.get("designation")),
        "unites": _entier_positif(batterie.get("unites")),
        "capacite_kwh": _positif(batterie.get("capacite_kwh")),
        "tension_v": None if masque else _positif(batterie.get("tension_v")),
        "protection": None,
    }


def _cote_reseau(cote_reseau, etat_par_defaut):
    cote_reseau = cote_reseau if isinstance(cote_reseau, dict) else {}
    etat = cote_reseau.get("etat")
    if etat not in _ETATS:
        etat = etat_par_defaut
    if etat == ETAT_CALCULE and etat_par_defaut != ETAT_CALCULE:
        etat = ETAT_A_CALCULER      # « calculé » sans un seul bloc servi : non
    motif = _texte(cote_reseau.get("motif")) if etat == ETAT_A_CALCULER else None
    return {"etat": etat, "motif": motif}


# ─────────────────────────────────────────────────────────────── document
def _document(**cles):
    """Le document, clés DANS L'ORDRE du contrat ; une clé oubliée lève."""
    return {cle: cles[cle] for cle in CLES_DOCUMENT}


def _cote_alternatif(blocs, libelles, protections, masque, cote_reseau):
    """Les cinq clés du côté réseau + ``cote_reseau``, hors réseau appliqué."""
    coffret_ac = _coffret(blocs, protections, _ORGANES_AC, masque, libelles)
    cote = _cote_reseau(cote_reseau,
                        ETAT_CALCULE if coffret_ac else ETAT_A_CALCULER)
    hors_reseau = cote["etat"] == ETAT_HORS_RESEAU
    return {
        "coffret_ac": coffret_ac,
        "compteur_production": (None if hors_reseau else
                                _simple(blocs, "compteur_production", libelles)),
        "tgbt": _simple(blocs, "tgbt", libelles),
        "etage_mt": [] if hors_reseau else _etage_mt(blocs, libelles),
        "reseau": None if hors_reseau else _simple(blocs, "reseau", libelles),
        "cote_reseau": cote,
    }


def document_schema_electrique(entree, resultat, *, chaines=None,
                               option=OPTION_SANS,
                               source=SOURCE_CONCEPTION_DEVIS, standard=False,
                               cote_reseau=None, unites_batterie=None,
                               nombre_onduleurs=None, libelles=None,
                               troncons=None, batterie=None):
    """SCHEL-B1 — le document « schéma électrique » d'UNE conception.

    ``entree``/``resultat`` : l'entrée et le résultat du moteur (ou leurs
    reconstructions d'artefact, ``objets_moteur_depuis_contrat``). ``chaines``
    (``[{numero, nb_panneaux, onduleur, entree}]``, ordre d'apparition) :
    celles du calepinage quand la règle de source les retient ; ``None`` ⇒
    celles du moteur. ``standard`` (L-NIV) : calibres, sections, longueurs et
    tension de batterie à ``None``, mêmes organes. ``libelles`` : les titres
    ÉDITÉS (``{clef: titre}``, côté calepinage). ``troncons`` : ``[{cote,
    section_mm2, longueur_m}]`` — ``None`` ⇒ les câbles du moteur.
    ``unites_batterie`` / ``nombre_onduleurs`` : lus par l'appelant sur les
    lignes ou la conception — ``None`` quand personne ne les connaît.
    """
    libelles = libelles if isinstance(libelles, dict) else {}
    masque = bool(standard)
    blocs = blocs_du_schema(entree, resultat, standard=masque)
    protections = _protections(resultat)
    servies = chaines_colorees(chaines_du_resultat(resultat)
                               if chaines is None else chaines)
    if troncons is None:
        troncons = troncons_du_resultat(resultat)
    module = getattr(entree, "module", None)
    onduleur = getattr(entree, "onduleur", None)
    return _document(
        version=VERSION_DOCUMENT, source=source, option=option,
        calibres_masques=masque,
        panneaux={"nombre": _entier_positif(getattr(entree, "nb_modules", 0)),
                  "module": {
                      "designation": _texte(getattr(module, "designation", "")),
                      "puissance_wc": _positif(getattr(module, "pmax_wc", None))}},
        chaines_reparties=bool(servies), chaines=servies,
        coffret_dc=_coffret(blocs, protections, _ORGANES_DC, masque, libelles),
        onduleurs=[{"designation": _texte(getattr(onduleur, "designation", "")),
                    "puissance_kw": _positif(getattr(onduleur, "ac_kw", None)),
                    "nombre": _entier_positif(nombre_onduleurs),
                    "nb_entrees": _entier_positif(getattr(onduleur, "n_mppt",
                                                          None))}],
        batterie=_batterie(entree, batterie, unites_batterie, masque),
        liaisons={"dc": _liaison(troncons, "dc", masque),
                  "ac": _liaison(troncons, "ac", masque)},
        terre=any(b.clef.split("#", 1)[0] in _A_LA_TERRE for b in blocs),
        **_cote_alternatif(blocs, libelles, protections, masque, cote_reseau))


def document_sans_repartition(*, option, nb_panneaux, module_designation=None,
                              puissance_wc=None, onduleurs=(), batterie=None,
                              motif=None, standard=False):
    """Le champ SANS découpage (``source = lignes_devis``) : aucune conception
    ne répartit les panneaux de cette option. Ce que les lignes nomment
    (panneaux, onduleur, batterie) est servi ; chaînes, coffrets et côté réseau
    ne le sont pas — jamais une répartition inventée. ``None`` sans panneau."""
    nombre = _entier_positif(nb_panneaux)
    if nombre is None:
        return None
    return _document(
        version=VERSION_DOCUMENT, source=SOURCE_LIGNES_DEVIS, option=option,
        calibres_masques=bool(standard),
        panneaux={"nombre": nombre,
                  "module": {"designation": _texte(module_designation),
                             "puissance_wc": _positif(puissance_wc)}},
        chaines_reparties=False, chaines=[], coffret_dc=None,
        onduleurs=[{"designation": _texte(o.get("designation")),
                    "puissance_kw": _positif(o.get("puissance_kw")),
                    "nombre": _entier_positif(o.get("nombre")),
                    "nb_entrees": _entier_positif(o.get("nb_entrees"))}
                   for o in onduleurs or () if isinstance(o, dict)],
        batterie=_batterie(None, batterie or False, None, bool(standard)),
        coffret_ac=None, compteur_production=None, tgbt=None, etage_mt=[],
        reseau=None, cote_reseau={"etat": ETAT_A_CALCULER,
                                  "motif": _texte(motif)},
        liaisons={"dc": {"section_mm2": None, "longueur_m": None},
                  "ac": {"section_mm2": None, "longueur_m": None}},
        terre=False)


# ════════════════════════════════════════════════════════════ LE DESSIN SVG
#: Libellés du dessin, par langue (fr, en, ar) — tuple de quadruplets : aucune
#: globale mutable. Le français est la langue de repli.
_LIBELLES = (
    ("bande_dc", "Côté panneaux · courant continu",
     "Panel side · direct current", "جهة الألواح · تيار مستمر"),
    ("bande_ac", "Côté réseau · courant alternatif",
     "Grid side · alternating current", "جهة الشبكة · تيار متناوب"),
    ("chaine", "Chaîne", "String", "سلسلة"),
    ("chaines", "chaînes", "strings", "سلاسل"),
    ("panneau", "panneau", "panel", "لوح"),
    ("panneaux", "panneaux", "panels", "ألواح"),
    ("entree", "entrée", "input", "مدخل"),
    ("entrees", "entrées", "inputs", "مداخل"),
    ("et", "et", "and", "و"),
    ("a", "à", "to", "إلى"),
    ("coffret_dc", "Coffret côté panneaux", "Panel-side box", "علبة جهة الألواح"),
    ("coffret_ac", "Coffret côté réseau", "Grid-side box", "علبة جهة الشبكة"),
    ("onduleur", "Onduleur", "Inverter", "العاكس"),
    ("conversion", "continu → alternatif", "DC → AC", "مستمر → متناوب"),
    ("batterie", "Batterie", "Battery", "البطارية"),
    ("unites", "unités", "units", "وحدات"),
    ("unite", "unité", "unit", "وحدة"),
    ("au_total", "au total", "in total", "في المجموع"),
    ("charge", "charge / décharge", "charge / discharge", "شحن / تفريغ"),
    ("compteur", "Compteur de production", "Production meter", "عداد الإنتاج"),
    ("tgbt", "TGBT", "Main LV board", "اللوحة العامة"),
    ("reseau", "Réseau du distributeur", "Distribution grid", "شبكة الموزع"),
    ("a_calculer", "à calculer", "to be sized", "قيد الحساب"),
    ("a_confirmer", "à confirmer", "to be confirmed", "يجب التأكيد"),
    ("etage_mt", "Étage moyenne tension", "Medium-voltage stage", "مرحلة الجهد المتوسط"),
    ("terre", "Liaison à la terre", "Earth connection", "الربط بالأرض"),
    ("terre_detail", "Terre : coffrets, onduleur et structure",
     "Earth: boxes, inverter and structure", "الأرضي: العلب والعاكس والهيكل"),
    ("legende_ac", "Côté réseau (courant alternatif)",
     "Grid side (alternating current)", "جهة الشبكة (تيار متناوب)"),
    ("legende_batterie", "Liaison batterie", "Battery link", "ربط البطارية"),
    ("legende_section", "Section du câble, puis sa longueur",
     "Cable cross-section, then its length", "مقطع الكابل ثم طوله"),
    ("champ", "Champ photovoltaïque", "PV array", "الحقل الشمسي"),
    ("non_reparti", "répartition en chaînes non calculée",
     "string layout not computed", "توزيع السلاسل غير محسوب"),
    ("fusibles", "Fusibles", "Fuses", "صمامات"),
    ("parafoudre", "Parafoudre", "Surge arrester", "مانعة الصواعق"),
    ("sectionneur", "Sectionneur", "Disconnector", "قاطع العزل"),
    ("disjoncteur", "Disjoncteur", "Circuit breaker", "قاطع التيار"),
    ("differentiel", "Différentiel", "Residual current device", "قاطع تفاضلي"),
)
_LANGUES = ("fr", "en", "ar")
#: Le nom (traduisible) de chaque organe de coffret.
_NOM_ORGANE = (("fusibles", "fusibles"), ("parafoudre_dc", "parafoudre"),
               ("sectionneur_dc", "sectionneur"), ("disjoncteur_ac", "disjoncteur"),
               ("parafoudre_ac", "parafoudre"), ("ddr", "differentiel"))

#: Convention de dessin (px CSS à 96 ppp) — géométrie, aucun seuil électrique.
_L_PLANCHE = 1040.0
_X_COFFRET_DC = 300.0
_L_COFFRET = 190.0
_X_ONDULEUR = 600.0
_L_ONDULEUR = 170.0
_X_BATTERIE = 830.0
_L_BATTERIE = 190.0
_H_BLOC_AC = 104.0
_ECART_AC = 26.0
_TRAIT = "#1f3a5f"
_SECONDAIRE = "#555555"
_FOND_DC = "#f4f8fc"
_FOND_AC = "#f7f4fb"
_CREUX = "#9aa5b1"


def _libelle(cle, langue):
    rang = _LANGUES.index(langue) if langue in _LANGUES else 0
    for entree in _LIBELLES:
        if entree[0] == cle:
            return entree[1 + rang] or entree[1]
    return cle


def _nombre_txt(valeur, langue, decimales=1):
    if isinstance(valeur, int):
        return str(valeur)
    if langue == "fr":
        return fr(valeur, decimales)
    return ("%.*f" % (decimales, float(valeur))).rstrip("0").rstrip(".")


def _t(x, y, texte, taille=10.0, poids="400", couleur=_TRAIT, ancre="start"):
    return ('<text x="%.1f" y="%.1f" font-size="%.1f" font-weight="%s" '
            'fill="%s" text-anchor="%s">%s</text>'
            % (x, y, taille, poids, couleur, ancre,
               escape(str(texte), quote=True)))


def _boite(x, y, largeur, h, creux=False, fond="#ffffff"):
    trait = ' stroke-dasharray="4 3"' if creux else ""
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" '
            'fill="%s" stroke="%s" stroke-width="1.2"%s/>'
            % (x, y, largeur, h, fond, _CREUX if creux else _TRAIT, trait))


def _ligne(x1, y1, x2, y2, couleur=_TRAIT, largeur=2.0, tirets=""):
    style = ' stroke-dasharray="%s"' % tirets if tirets else ""
    return ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
            'stroke-width="%.1f"%s/>' % (x1, y1, x2, y2, couleur, largeur, style))


def _pointe(x, y, vers_la_droite=True, couleur=_TRAIT):
    d = -7.0 if vers_la_droite else 7.0
    return ('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1f Z" fill="%s"/>'
            % (x, y, x + d, y - 4.0, x + d, y + 4.0, couleur))


def _texte_entrees(nombre, langue):
    if nombre == 1:
        plage = "1"
    elif nombre == 2:
        plage = "1 %s 2" % _libelle("et", langue)
    else:
        plage = "1 %s %d" % (_libelle("a", langue), nombre)
    return "%d %s : %s" % (nombre, _libelle("entrees" if nombre > 1 else "entree",
                                            langue), plage)


def _rangees(doc, langue):
    """SVG des rangées de chaînes (ou du champ sans découpage) + ``(svg,
    ordonnées des fils, bas)``."""
    chaines = doc.get("chaines") or []
    wc = ((doc.get("panneaux") or {}).get("module") or {}).get("puissance_wc")
    morceaux, fils = [], []
    if not chaines:
        nombre = (doc.get("panneaux") or {}).get("nombre") or 0
        morceaux.append(_boite(16.0, 44.0, 200.0, 70.0))
        morceaux.append(_t(26.0, 64.0, _libelle("champ", langue), 11.0, "700"))
        texte = "%d %s" % (nombre, _libelle("panneaux", langue))
        if wc:
            texte += " · %s Wc" % _nombre_txt(wc, langue)
        morceaux.append(_t(26.0, 82.0, texte, 10.0))
        morceaux.append(_t(26.0, 100.0, _libelle("non_reparti", langue), 9.0,
                           couleur=_SECONDAIRE))
        return "".join(morceaux), [(None, 79.0)], 124.0
    chaines, reste = _chaines_visibles(doc)
    lignes = len(chaines) + (1 if reste else 0)
    pas = 92.0 if lignes <= 2 else 60.0
    if reste:
        y = 44.0 + len(chaines) * pas
        morceaux.append(_t(16.0, y + 11.0, _texte_reste(reste, langue), 10.5, "700"))
        for k, couleur in enumerate(reste["couleurs"]):
            morceaux.append('<rect x="%.1f" y="%.1f" width="18" height="12" fill="%s"/>'
                            % (16.0 + k * 22.0, y + 16.0, couleur))
        fils.append(({"couleur": _TRAIT, "entree": None}, y + 22.0))
    for rang, chaine in enumerate(chaines):
        y = 44.0 + rang * pas
        nombre = chaine["nb_panneaux"]
        mot = _libelle("panneaux" if nombre > 1 else "panneau", langue)
        morceaux.append(_t(16.0, y + 11.0, "%s %d · %d %s" % (
            _libelle("chaine", langue), chaine["numero"], nombre, mot), 10.5, "700"))
        h = 22.0 if pas > 50 else 12.0
        ecart = 2.0 if nombre > 8 else 4.0
        largeur = max(2.0, min(18.0, (190.0 - ecart * (nombre - 1)) / nombre))
        for k in range(nombre):
            morceaux.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                            'fill="%s"/>' % (16.0 + k * (largeur + ecart), y + 16.0,
                                             largeur, h, chaine["couleur"]))
        if wc and pas > 50:
            morceaux.append(_t(16.0, y + h + 30.0, "%d × %s Wc" % (
                nombre, _nombre_txt(wc, langue)), 9.0, couleur=_SECONDAIRE))
        fils.insert(rang, (chaine, y + 16.0 + h / 2.0))
    return "".join(morceaux), fils, 44.0 + lignes * pas


#: SCHEL-B4 — rangées de chaînes DESSINÉES au plus : au-delà, les premières
#: chaînes puis UNE ligne de suite qui porte les vrais totaux des autres — la
#: planche reste bornée sur sa page d'annexe, aucune chaîne n'est perdue
#: (le document, lui, les porte toutes). Convention de mise en page.
_RANGEES_MAX = 4


def _chaines_visibles(doc):
    """``(chaînes dessinées, reste)`` — ``reste`` ``{nombre, nb_panneaux,
    couleurs}`` des chaînes résumées sur la ligne de suite, ou ``None``."""
    chaines = list(doc.get("chaines") or [])
    if len(chaines) <= _RANGEES_MAX:
        return chaines, None
    visibles, autres = chaines[:_RANGEES_MAX - 1], chaines[_RANGEES_MAX - 1:]
    return visibles, {"nombre": len(autres),
                      "nb_panneaux": sum(c["nb_panneaux"] for c in autres),
                      "couleurs": [c["couleur"] for c in autres][:len(PALETTE_CHAINES)]}


def _texte_reste(reste, langue):
    """« + 27 chaînes · 324 panneaux » — les vrais totaux des chaînes résumées."""
    return "+ %d %s · %d %s" % (reste["nombre"], _libelle("chaines", langue),
                                reste["nb_panneaux"], _libelle("panneaux", langue))


def _carte_coffret(x, y, h, titre, organes, langue, creux=False, largeur=_L_COFFRET):
    morceaux = [_boite(x, y, largeur, h, creux=creux)]
    morceaux.append(_t(x + 10.0, y + 18.0, titre, 10.5, "700",
                       _CREUX if creux else _TRAIT))
    if creux:
        morceaux.append(_t(x + 10.0, y + 36.0, _libelle("a_calculer", langue),
                           9.0, couleur=_CREUX))
    for rang, organe in enumerate(organes or ()):
        oy = y + 38.0 + rang * 30.0
        nom = dict(_NOM_ORGANE).get(organe.get("clef"), "")
        titre_organe = (organe.get("titre") if langue == "fr"
                        else _libelle(nom, langue)) or _libelle(nom, langue)
        quantite = organe.get("quantite")
        if quantite and quantite > 1:
            titre_organe = "%d × %s" % (quantite, titre_organe)
        morceaux.append('<g data-repere="%s">' % escape(organe.get("repere") or "",
                                                        quote=True))
        morceaux.append(_t(x + 10.0, oy, titre_organe, 9.5, "700"))
        if organe.get("calibre"):
            morceaux.append(_t(x + 10.0, oy + 12.0, organe["calibre"], 8.5,
                               couleur=_SECONDAIRE))
        morceaux.append("</g>")
    return "".join(morceaux)


def _carte_onduleur(doc, y, h, langue):
    onduleur = (doc.get("onduleurs") or [{}])[0] or {}
    x = _X_ONDULEUR
    morceaux = [_boite(x, y, _L_ONDULEUR, h, fond="#eef7f1"),
                _t(x + 10.0, y + 20.0, _libelle("onduleur", langue), 11.0, "700")]
    lignes = []
    if onduleur.get("puissance_kw"):
        lignes.append("%s kW" % _nombre_txt(onduleur["puissance_kw"], langue))
    if onduleur.get("nombre") and onduleur["nombre"] > 1:
        lignes.append("%d ×" % onduleur["nombre"])
    if onduleur.get("designation"):
        lignes.extend(_couper(_designation_affichee(onduleur["designation"]), 24, 3))
    if onduleur.get("nb_entrees"):
        lignes.append(_texte_entrees(onduleur["nb_entrees"], langue))
    for rang, ligne in enumerate(lignes):
        morceaux.append(_t(x + 10.0, y + 38.0 + rang * 15.0, ligne, 9.5))
    morceaux.append(_t(x + _L_ONDULEUR / 2.0, y + h - 12.0,
                       _libelle("conversion", langue), 9.0, "700", _SECONDAIRE,
                       "middle"))
    return "".join(morceaux)


def _carte_batterie(batterie, y, langue):
    x = _X_BATTERIE
    morceaux = [_boite(x, y, _L_BATTERIE, 104.0, fond="#fff3f5"),
                _t(x + 10.0, y + 20.0, _libelle("batterie", langue), 11.0, "700")]
    lignes = []
    if batterie.get("designation"):
        lignes.extend(_couper(_designation_affichee(batterie["designation"]), 30, 2))
    if batterie.get("unites"):
        lignes.append("%d %s" % (batterie["unites"], _libelle(
            "unites" if batterie["unites"] > 1 else "unite", langue)))
    if batterie.get("capacite_kwh"):
        lignes.append("%s kWh %s" % (_nombre_txt(batterie["capacite_kwh"], langue),
                                     _libelle("au_total", langue)))
    if batterie.get("tension_v"):
        lignes.append("%s V" % _nombre_txt(batterie["tension_v"], langue))
    for rang, ligne in enumerate(lignes):
        morceaux.append(_t(x + 10.0, y + 38.0 + rang * 15.0, ligne, 9.5))
    # La liaison NEUTRE à double flèche : le courant batterie va dans les
    # deux sens (charge et décharge).
    ly = y + 52.0
    x1, x2 = _X_ONDULEUR + _L_ONDULEUR, x
    morceaux.append(_ligne(x1 + 7.0, ly, x2 - 7.0, ly, largeur=1.6))
    morceaux.append(_pointe(x1, ly, vers_la_droite=False))
    morceaux.append(_pointe(x2, ly))
    # L'étiquette de la liaison ne franchit jamais une boîte : l'espace entre onduleur et batterie ne fait que
    # `_X_BATTERIE - _X_ONDULEUR - _L_ONDULEUR` px ; « charge / décharge » (≈ 75 px) y déborderait, elle se pose donc
    # sur deux lignes (« charge / » puis « décharge »), chacune plus étroite que l'écart.
    libelle = _libelle("charge", langue)
    lignes = ([libelle.split(" / ")[0] + " /", libelle.split(" / ", 1)[1]]
              if " / " in libelle else [libelle])
    for rang, ligne in enumerate(lignes):
        morceaux.append(_t((x1 + x2) / 2.0, ly - 6.0 - (len(lignes) - 1 - rang) * 9.0,
                           ligne, 8.0, couleur=_SECONDAIRE, ancre="middle"))
    return "".join(morceaux)


def _section_txt(liaison, langue):
    morceaux = []
    if (liaison or {}).get("section_mm2"):
        morceaux.append("%s mm²" % _nombre_txt(liaison["section_mm2"], langue))
    if (liaison or {}).get("longueur_m"):
        morceaux.append("%s m" % _nombre_txt(liaison["longueur_m"], langue, 0))
    return " · ".join(morceaux)


def _fils_dc(doc, fils, coffret_bas, langue):
    """Un fil par chaîne, à SA couleur : rangée → coffret → entrée onduleur."""
    morceaux = []
    section = _section_txt((doc.get("liaisons") or {}).get("dc"), langue)
    avec_coffret = coffret_bas is not None
    for rang, (chaine, y) in enumerate(fils):
        couleur = chaine["couleur"] if chaine else _TRAIT
        ye = 70.0 + rang * 18.0
        if avec_coffret:
            morceaux.append(_ligne(218.0, y, _X_COFFRET_DC, y, couleur))
            depart = _X_COFFRET_DC + _L_COFFRET
            morceaux.append(_ligne(depart, ye, _X_ONDULEUR - 7.0, ye, couleur))
        else:
            xm = 250.0 + rang * 10.0
            morceaux.append(_ligne(218.0, y, xm, y, couleur))
            morceaux.append(_ligne(xm, y, xm, ye, couleur))
            depart = xm
            morceaux.append(_ligne(xm, ye, _X_ONDULEUR - 7.0, ye, couleur))
        morceaux.append(_pointe(_X_ONDULEUR, ye, couleur=couleur))
        etiquette = [m for m in (
            "%s %d" % (_libelle("entree", langue), chaine["entree"])
            if chaine and chaine.get("entree") else "", section) if m]
        if etiquette:
            morceaux.append(_t(depart + 8.0, ye - 4.0, " · ".join(etiquette), 8.0,
                               couleur=_SECONDAIRE))
    return "".join(morceaux)


def _blocs_ac(doc, langue):
    """Les blocs du côté réseau, de l'onduleur vers le réseau : ``[(clef,
    titre, detail, organes, creux)]``."""
    cote = (doc.get("cote_reseau") or {}).get("etat")
    if cote == ETAT_HORS_RESEAU and not doc.get("coffret_ac"):
        return []
    if cote == ETAT_A_CALCULER and not doc.get("coffret_ac"):
        return [("coffret_ac", _libelle("coffret_ac", langue), "", (), True),
                ("compteur", _libelle("compteur", langue), "", (), True),
                ("reseau", _libelle("reseau", langue), "", (), True)]
    blocs = []
    if doc.get("coffret_ac"):
        blocs.append(("coffret_ac", _libelle("coffret_ac", langue), "",
                      doc["coffret_ac"].get("organes") or (), False))
    if doc.get("compteur_production"):
        blocs.append(("compteur", _libelle("compteur", langue), "", (), False))
    if doc.get("tgbt"):
        blocs.append(("tgbt", _libelle("tgbt", langue),
                      doc["tgbt"].get("detail") or "", (), False))
    etage = [b.get("titre") or "" for b in doc.get("etage_mt") or ()]
    if etage:
        # UN bloc pour tout l'étage MT : ses organes nommés, chacun « à confirmer »
        # (cinq blocs étroits ne tiendraient pas entre la marge et l'onduleur).
        blocs.append(("etage_mt", _libelle("etage_mt", langue),
                      "%s : %s" % (_libelle("a_confirmer", langue), ", ".join(etage)),
                      (), False))
    if doc.get("reseau"):
        blocs.append(("reseau", _libelle("reseau", langue),
                      doc["reseau"].get("titre") or "", (), False))
    return blocs


#: Les unités qu'un nombre ne quitte jamais en fin de ligne (« 400 V », « 20 kA », « 1,5 kV »).
_UNITES = r"kWh|kWc|kW|kVA|kV|kA|Wc|Wh|Ah|mA|mm²|mm2|m²|Hz|°C|V|A|W|m|%"
_NOMBRE_UNITE = re.compile(r"(\d(?:[\d.,]*\d)?)[ \t]+((?:%s)(?![\w²]))" % _UNITES)
_BLANCS = re.compile(r"[ \t\r\n]+")
_INSECABLE = "\u00a0"


def _mots(texte):
    """Les mots d'un texte, une valeur et son unité formant UN seul mot (espace insécable)."""
    joint = _NOMBRE_UNITE.sub("\\1" + _INSECABLE + "\\2", str(texte or ""))
    return [mot for mot in _BLANCS.split(joint.strip()) if mot]


def _designation_affichee(designation):
    """La désignation SANS marque répétée : « Deye Onduleur hybride Deye 20kW » (marque + nom du
    catalogue, qui contient déjà la marque) s'écrit « Onduleur hybride Deye 20kW ». Affichage seul :
    la désignation servie et ses empreintes ne bougent pas."""
    mots = str(designation or "").split()
    if len(mots) > 2 and len(mots[0]) >= 3 and mots[0].casefold() in (
            m.casefold() for m in mots[1:]):
        mots = mots[1:]
    return " ".join(mots)


def _couper(texte, largeur, lignes):
    """Mots entiers sur ``lignes`` lignes d'au plus ``largeur`` signes. Une valeur ne quitte jamais son
    unité ; trop long, le texte finit par « … » posé à une FRONTIÈRE de mot (jamais au milieu d'un mot) —
    un texte, jamais un chiffre."""
    sortie = []
    morceaux = []
    for mot in _mots(texte):
        # Un mot seul plus long que la ligne (code de modèle) est coupé à la largeur de la ligne.
        while largeur > 0 and len(mot) > largeur:
            morceaux.append(mot[:largeur])
            mot = mot[largeur:]
        morceaux.append(mot)
    for mot in morceaux:
        if sortie and len(sortie[-1]) + 1 + len(mot) <= largeur:
            sortie[-1] += " " + mot
        else:
            sortie.append(mot)
    if len(sortie) > lignes:
        sortie = sortie[:lignes]
        derniers = sortie[-1].split(" ")
        while len(derniers) > 1 and len(" ".join(derniers)) + 1 > largeur:
            derniers.pop()
        sortie[-1] = " ".join(derniers) + "…"
    return [ligne.replace(_INSECABLE, " ") for ligne in sortie]


def _largeurs_ac(blocs):
    """La largeur de chaque bloc AC : tous tiennent entre la marge et
    l'onduleur, le coffret (qui liste ses organes) au plus large."""
    disponible = _X_ONDULEUR - 16.0 - _ECART_AC * len(blocs)
    if blocs[0][3] and len(blocs) > 1:
        premier = min(_L_COFFRET, disponible * 0.4)
        autres = min(_L_COFFRET, (disponible - premier) / (len(blocs) - 1))
        return [premier] + [autres] * (len(blocs) - 1)
    return [min(_L_COFFRET, disponible / len(blocs))] * len(blocs)


def _cote_ac_svg(doc, y_ac, langue):
    """La bande alternative : blocs posés de l'onduleur vers la gauche."""
    blocs = _blocs_ac(doc, langue)
    if not blocs:
        return ""
    y = y_ac + 44.0
    lien = y + _H_BLOC_AC / 2.0
    morceaux, curseur = [], _X_ONDULEUR
    section = _section_txt((doc.get("liaisons") or {}).get("ac"), langue)
    for rang, (largeur, (_clef, titre, detail, organes, creux)) in enumerate(
            zip(_largeurs_ac(blocs), blocs)):
        x = curseur - _ECART_AC - largeur
        trait = "4 3" if creux else ""
        morceaux.append(_ligne(x + largeur + 7.0, lien, curseur, lien,
                               _CREUX if creux else _TRAIT, 1.8, trait))
        morceaux.append(_pointe(x + largeur, lien, vers_la_droite=False,
                                couleur=_CREUX if creux else _TRAIT))
        if rang == 0 and section and not creux:
            morceaux.append(_t(x + largeur + 4.0, lien - 6.0, section, 8.0,
                               couleur=_SECONDAIRE))
        if organes:
            morceaux.append(_carte_coffret(x, y, _H_BLOC_AC, titre, organes, langue,
                                           largeur=largeur))
        else:
            caracteres = max(6, int((largeur - 12.0) / 5.6))
            morceaux.append(_boite(x, y, largeur, _H_BLOC_AC, creux=creux))
            texte = _couper(titre, caracteres, 2)
            for k, ligne in enumerate(texte):
                morceaux.append(_t(x + 6.0, y + 18.0 + k * 12.0, ligne, 9.5, "700",
                                   _CREUX if creux else _TRAIT))
            dessous = _couper(_libelle("a_calculer", langue) if creux else detail,
                              caracteres + 2, 3)
            for k, ligne in enumerate(dessous):
                morceaux.append(_t(x + 6.0, y + 22.0 + len(texte) * 12.0 + k * 11.0,
                                   ligne, 8.5, couleur=_CREUX if creux else _SECONDAIRE))
        curseur = x
    return "".join(morceaux)


def _legende(doc, y, langue):
    """Une ligne par chaîne, puis le côté réseau, la batterie, la terre et la
    section — chacune SEULEMENT quand le dessin la porte."""
    visibles, reste = _chaines_visibles(doc)
    items = [("chaine", c["couleur"], "%s %d%s" % (
        _libelle("chaine", langue), c["numero"],
        (" · %s %d" % (_libelle("entree", langue), c["entree"]))
        if c.get("entree") else "")) for c in visibles]
    if reste:
        items.append(("chaine", _TRAIT, _texte_reste(reste, langue)))
    if doc.get("coffret_ac"):
        items.append(("plein", _TRAIT, _libelle("legende_ac", langue)))
    if doc.get("batterie"):
        items.append(("plein", _TRAIT, _libelle("legende_batterie", langue)))
    if doc.get("terre"):
        items.append(("terre", _TRAIT, _libelle("terre", langue)))
    liaisons = doc.get("liaisons") or {}
    if any((liaisons.get(c) or {}).get("section_mm2") for c in ("dc", "ac")):
        items.append(("texte", _SECONDAIRE, _libelle("legende_section", langue)))
    morceaux = []
    for rang, (nature, couleur, texte) in enumerate(items):
        x = 16.0 + (rang % 4) * 252.0
        yy = y + (rang // 4) * 16.0
        if nature == "texte":
            morceaux.append(_t(x, yy + 3.0, "mm²", 8.0, "700", couleur))
        else:
            morceaux.append(_ligne(x, yy, x + 20.0, yy, couleur, 2.0,
                                   "4 3" if nature == "terre" else ""))
        morceaux.append(_t(x + 26.0, yy + 3.0, texte, 8.5))
    return "".join(morceaux), y + ((len(items) + 3) // 4) * 16.0


def _geometrie(doc, langue):
    """Rangées, coffret DC et hauteur de la bande continue."""
    rangees_svg, fils, bas_rangees = _rangees(doc, langue)
    organes_dc = (doc.get("coffret_dc") or {}).get("organes") or ()
    coffret_h = max(bas_rangees - 44.0, 44.0 + len(organes_dc) * 30.0,
                    40.0 + len(fils) * 18.0) if doc.get("coffret_dc") else None
    bas_batterie = 44.0 + 104.0 if doc.get("batterie") else 0.0
    h_dc = max(bas_rangees, 44.0 + (coffret_h or 0.0), bas_batterie,
               70.0 + len(fils) * 18.0) + 20.0
    return rangees_svg, fils, coffret_h, h_dc


def rendre_schema_electrique_svg(doc, langue="fr", largeur_px=None):
    """SCHEL-B4 — le dessin en blocs du document, en SVG (texte), ou ``""``.

    Même dessin que l'écran du calepinage : bande « Côté panneaux · courant
    continu » (une rangée colorée par chaîne, coffret côté panneaux, entrées
    de l'onduleur, carte BATTERIE reliée à l'onduleur par une liaison neutre à
    double flèche), bande « Côté réseau · courant alternatif » (coffret côté
    réseau, compteur, TGBT, étage MT, réseau ; en creux quand le côté réseau
    est à calculer, rien hors réseau), terre et légende. Ne lit que le
    document : aucune valeur n'est recomposée ici. ``largeur_px`` : largeur
    affichée (le ``viewBox`` ne change pas).
    """
    if not isinstance(doc, dict) or not doc.get("onduleurs"):
        return ""
    langue = langue if langue in _LANGUES else "fr"
    rangees_svg, fils, coffret_h, h_dc = _geometrie(doc, langue)
    y_ac = h_dc + 16.0
    bas_ac = y_ac + 44.0 + _H_BLOC_AC
    y_terre = bas_ac + 30.0
    legende_svg, bas = _legende(doc, y_terre + (30.0 if doc.get("terre") else 0.0),
                                langue)
    hauteur = bas + 16.0
    morceaux = [
        '<rect x="0" y="0" width="%.1f" height="%.1f" fill="%s"/>'
        % (_L_PLANCHE, h_dc, _FOND_DC),
        '<rect x="0" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
        % (y_ac, _L_PLANCHE, bas_ac + 16.0 - y_ac, _FOND_AC),
        _t(16.0, 24.0, _libelle("bande_dc", langue), 11.5, "700"),
        _t(16.0, y_ac + 24.0, _libelle("bande_ac", langue), 11.5, "700"),
        rangees_svg,
    ]
    if coffret_h is not None:
        morceaux.append(_carte_coffret(_X_COFFRET_DC, 44.0, coffret_h,
                                       _libelle("coffret_dc", langue),
                                       doc["coffret_dc"].get("organes"), langue))
    morceaux.append(_fils_dc(doc, fils, coffret_h, langue))
    morceaux.append(_carte_onduleur(doc, 44.0, bas_ac - 44.0, langue))
    if doc.get("batterie"):
        morceaux.append(_carte_batterie(doc["batterie"], 44.0, langue))
    morceaux.append(_cote_ac_svg(doc, y_ac, langue))
    if doc.get("terre"):
        morceaux.append(_ligne(16.0, y_terre, _X_ONDULEUR + _L_ONDULEUR, y_terre,
                               _TRAIT, 1.2, "4 3"))
        morceaux.append(_t(16.0, y_terre - 6.0, _libelle("terre_detail", langue),
                           8.5, couleur=_SECONDAIRE))
    morceaux.append(legende_svg)
    largeur = float(largeur_px) if largeur_px else _L_PLANCHE
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f" '
            'width="%.0f" height="%.0f" font-family="Helvetica, Arial, '
            'sans-serif" data-schema="electrique">%s</svg>'
            % (_L_PLANCHE, hauteur, largeur, hauteur * largeur / _L_PLANCHE,
               "".join(morceaux)))
