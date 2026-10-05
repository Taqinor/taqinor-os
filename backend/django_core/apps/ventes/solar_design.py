"""FG246 / FG247 / FG249 / … / FG257 — Calculs d'ingénierie solaire (conception électrique).

Module PUR (aucune écriture base, aucun effet de bord) regroupant trois
calculateurs réutilisés par l'écran de devis et, à terme, le pont toiture 3D :

* ``string_design`` (FG246) — répartit N panneaux sur les entrées MPPT d'un
  onduleur, vérifie Vmp/Voc des chaînes à FROID contre la fenêtre de tension
  onduleur, et rapporte le ratio DC/AC.
* ``match_inverter`` (FG247) — propose l'onduleur compatible du catalogue pour
  une configuration panneaux donnée, en gardant les mots-clés de classification
  ALIGNÉS sur ``quote_engine/builder.py`` (réseau/injection, hybride, batterie,
  panneau).
* ``optimize_orientation`` (FG249) — balaie inclinaison/azimut autour du site
  via l'intégration PVGIS EXISTANTE (``apps.parametres.pvgis``) pour retourner
  l'orientation optimale ; repli gracieux hors-ligne (la fonction PVGIS retombe
  déjà sur l'hypothèse manuelle, jamais d'exception réseau).

CONTRAINTES :
* Les onduleurs/panneaux du catalogue (``stock.Produit``) portent DÉSORMAIS une
  fiche électrique normalisée (``stock.FicheTechnique``, PV5/PVOND-H) lue par le
  pont PV10 ci-dessous — tensions, courants, fenêtre MPPT, puissance AC. Ce qui
  reste par défaut ne l'est que pour un produit dont la fiche est ABSENTE ou
  INCOMPLÈTE : on applique alors des paramètres de tension par défaut SENSÉS
  (silicium cristallin), on extrait du nom ce qui est extractible (puissance W,
  kW onduleur), et les COURANTS restent à 0 — le noyau saute alors ses verdicts
  de courant plutôt que d'en inventer un.
* Aucun prix d'achat / marge n'apparaît jamais dans une sortie — ce module ne
  manipule que des grandeurs électriques publiques.
* Aucune dépendance pip nouvelle ; PVGIS via le client stdlib existant.
"""
from __future__ import annotations

import math
import re

# STKCAT22 — LA table de reconnaissance « panneau » (mot à frontière de mot,
# « module » + qualifiant PV, marque + wattage) vit dans la couche de FONDATION
# ``core`` : elle est lue AUSSI par ``apps.stock`` (seeder : catégorie ET
# prédicat fiscal de TVA), qui n'a pas le droit d'importer ``apps.ventes``.
# Import de tête SÛR : ``core.product_roles`` est du Python pur — ni Django, ni
# modèle, ni réglage — donc il ne peut pas créer de cycle de chargement, ce que
# l'en-tête de ce module exige.
from core.product_roles import (
    PANNEAU_MARQUES,
    PANNEAU_MODULE_QUALIFIERS,
    WATT_RE as _CORE_WATT_RE,
    est_panneau,
)

# SPL259 — helpers d'hypothèse, d'omission et de série : module FEUILLE
# ``solar_base`` (stdlib seule), importés ici POUR USAGE par les calculateurs.
from apps.ventes.solar_base import (
    _coerce_series,
    _hypothese,
    _omission,
    _omissions_temperatures,
    _source_defaut,
    _taux_ou_none,
)

# SPL260 — le bloc tarifs/finance vit dans ``solar_finance`` ; seul
# ``compare_scenarios`` (plus bas) s'en sert ici, POUR USAGE.
from apps.ventes.solar_finance import tariff_escalation_projection

# ── Paramètres électriques par défaut (module silicium cristallin) ────────────
# Valeurs marché conservatrices pour un panneau PV mono/poly courant. Tout est
# surchargeable par l'appelant via le dict ``module``.
#
# * ``vmp`` / ``voc`` aux conditions STC (25 °C) — référence d'un panneau ~60–72
#   cellules. À défaut de fiche produit, on s'appuie sur ces valeurs et le
#   coefficient de température pour borner la fenêtre.
# * ``temp_coeff_voc`` : coefficient de température du Voc (%/°C), négatif :
#   le Voc MONTE quand il fait FROID (cas dimensionnant pour la borne haute).
DEFAULT_MODULE = {
    "vmp": 34.0,           # tension au point de puissance max (V), STC
    "voc": 41.0,           # tension circuit ouvert (V), STC
    "temp_coeff_voc": -0.27,   # %/°C (négatif)
    "temp_coeff_vmp": -0.35,   # %/°C (négatif) — Vmp chute plus vite
    "puissance_w": 450,    # puissance crête (W) — repli si non lisible du nom
    # PVCOMPAT — COURANTS du module. Défaut 0 VOULU : un courant n'a pas de
    # « valeur de marché » défendable (il varie du simple au double d'un module
    # à l'autre) et le noyau SAUTE ses verdicts de courant quand il vaut 0.
    # Sans fiche, on ne rend donc AUCUN verdict de courant plutôt qu'un verdict
    # inventé — c'est exactement le comportement d'avant ce lot.
    "isc_a": 0.0,          # courant de court-circuit (A), STC
    "imp_a": 0.0,          # courant au point de puissance max (A), STC
}

# Fenêtre onduleur par défaut (onduleur string résidentiel/commercial typique).
# Surchargeable via ``inverter``.
DEFAULT_INVERTER_WINDOW = {
    "v_min": 90.0,       # tension de démarrage / minimale DC (V)
    "v_max": 600.0,      # tension DC max absolue (V) — ne JAMAIS dépasser
    "v_mppt_min": 120.0,  # bas de la plage MPPT (V)
    "v_mppt_max": 500.0,  # haut de la plage MPPT (V)
    "n_mppt": 2,         # nombre d'entrées MPPT
    "ac_kw": None,       # puissance AC nominale (kW) — pour le ratio DC/AC
    # PVCOMPAT — COURANTS admissibles par entrée MPPT. Même raison que côté
    # module : 0 signifie « la fiche ne le dit pas », et le noyau se tait plutôt
    # que de fabriquer une contrainte. ``isc_max_mppt_a=None`` fait retomber le
    # noyau sur ``i_max_mppt_a`` (repli PRUDENT documenté dans SpecOnduleur).
    "i_max_mppt_a": 0.0,     # courant d'entrée admissible par MPPT (A)
    "isc_max_mppt_a": None,  # Isc admissible par MPPT (A) — borne MATÉRIELLE
}

# Conditions de température de référence pour le calcul à froid / à chaud.
STC_TEMP_C = 25.0          # conditions standard (Voc/Vmp donnés à 25 °C)
# CALX286 — ces deux températures n'ont AUCUNE source (ni station, ni fiche,
# ni site) : ``string_design`` / ``verdicts_chaines`` / ``match_inverter`` ne
# les appliquent PLUS d'office. Sans températures fournies, la fenêtre de
# tension est OMISE (``omissions`` + grandeurs ``None``). Les appelants
# historiques (``apps/ventes/compatibilites.py``) les passent EXPLICITEMENT
# pour ne rien changer en production (D12).
DEFAULT_COLD_TEMP_C = -5.0   # température cellule mini de dimensionnement (hiver Maroc montagne)
DEFAULT_HOT_TEMP_C = 70.0    # température cellule maxi (été, module chaud)


# Ratio DC/AC maximal toléré pour considérer un onduleur « assez gros ».
MAX_DC_AC = 1.35

# STKCAT22 — UNE SEULE expression pour « un wattage lisible » : celle de
# ``core.product_roles``. C'était la MÊME regex écrite deux fois (ici pour LIRE
# la puissance, là-bas pour RECONNAÎTRE un panneau à sa marque + son wattage) —
# deux copies qui n'avaient aucune raison de pouvoir diverger.
_WATT_RE = _CORE_WATT_RE
_KW_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:kw|kva)\b", re.IGNORECASE)
_KWH_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kwh\b", re.IGNORECASE)


def parse_watt(text: str):
    """Puissance panneau (W) lue dans un nom/désignation, sinon None."""
    m = _WATT_RE.search(text or "")
    return int(m.group(1)) if m else None


def parse_kw(text: str):
    """Puissance (kW/kVA) lue dans un nom — exclut d'abord les « kWh »."""
    cleaned = _KWH_RE.sub(" ", text or "")
    m = _KW_RE.search(cleaned)
    return float(m.group(1).replace(",", ".")) if m else None


# ═══════════════════════════════════════════════════════════════════════════
# LA TABLE DE CLASSIFICATION PRODUIT DU BACKEND — IL N'Y EN A QU'UNE (QJR78)
# ═══════════════════════════════════════════════════════════════════════════
# Les commentaires de ce fichier ANNONÇAIENT depuis toujours une classification
# « ALIGNÉE sur quote_engine/builder.py, mots-clés identiques ». Ce n'était plus
# vrai : le 19/08/2026, un audit adversarial a ÉLARGI la détection panneau du
# seul builder (module + qualifiant PV, marque + wattage, exclusions), et les
# deux autres jeux — celui-ci et celui de l'ex-`services.py` (aujourd'hui
# `domain/catalogue.py`) — sont restés à la version étroite « panneau /
# panneaux ». Conséquence mesurable : un devis dont la ligne panneau s'appelle
# « Module PV 550 W » était vu comme n'ayant AUCUN panneau à l'enregistrement,
# alors que le PDF, lui, la comptait. C'est exactement le patron de l'incident
# de PRODUCTION DEV-202608-0024, que les commentaires du code citent déjà.
#
# Depuis QJR78, ce module est la SEULE table backend : `domain/catalogue.py` et
# `quote_engine/builder.py` importent ces fonctions au lieu d'en garder une
# copie. Le jeu retenu est le PLUS LARGE (celui du builder) — le rétrécir
# aurait fait régresser le PDF, qui classe correctement depuis le 19/08.
#
# La moitié ÉCRAN (`frontend/src/features/ventes/solar.js`) s'y branche par le
# contrat QJR2 : c'est QJR92, pas cette tâche.

#: STKCAT22 — ALIAS de la table PARTAGÉE (``core.product_roles``). Les deux
#: tuples étaient déclarés ici et re-devinés ailleurs ; ils ne le sont plus.
#: Les noms locaux restent : ``quote_engine/builder.py`` les ré-exporte.
_PANEL_MODULE_QUALIFIERS = PANNEAU_MODULE_QUALIFIERS
_PANEL_BRANDS = PANNEAU_MARQUES


def _autre_famille_que_panneau(blob: str) -> bool:
    """Le texte (DÉJÀ minusculé) désigne-t-il une AUTRE famille ?

    Un onduleur, une batterie, un Smart Meter ou une clé Wi-Fi n'est JAMAIS un
    panneau, quelle que soit la marque de panneau écrite dessus.
    """
    return bool(is_inverter(blob) or is_battery(blob)
                or is_smart_meter(blob) or is_wifi_dongle(blob))


def is_panel(designation: str, produit_nom: str = "") -> bool:
    """STKCAT22 — reconnaissance panneau : LA TABLE PARTAGÉE, pas une copie.

    Le corps de la reconnaissance (mot « panneau » à frontière de mot, puis
    « module » + qualifiant PV, puis marque + wattage) vit dans
    ``core.product_roles.est_panneau`` et est lu à l'identique par le seeder
    ``apps.stock`` (catégorie ET prédicat fiscal). Ce qui reste ici est ce qui
    appartient VRAIMENT au moteur de devis : le TEXTE classé (désignation + nom
    du produit, convention QJR301) et l'exclusion « autre famille ».
    """
    # QJR424 — SEULE définition du texte de classement (QJR301,
    # ``apps.ventes.utils.options.texte_classement``). Import LOCAL : ce
    # module reste PUR au chargement (voir l'en-tête) — `utils.options`
    # importe `quote_engine.builder`, qui importe CE module au niveau
    # module (`from apps.ventes import solar_design as _sd`) ; un import
    # de tête ici romprait ce cycle avant que `is_battery`/`is_panel` etc.
    # n'existent encore.
    from apps.ventes.utils.options import texte_classement
    blob = texte_classement(designation, produit_nom).lower()
    return est_panneau(blob, exclut=_autre_famille_que_panneau)


def is_battery(designation: str) -> bool:
    return "batterie" in (designation or "").lower()


#: QJR-OFFGRID (incident fondateur 01/09/2026) — LES MOTS D'UN ONDULEUR
#: AUTONOME (site isolé, aucun raccordement ONEE). Le piège est FRANÇAIS :
#: « hors réseau » CONTIENT « réseau », si bien qu'un onduleur off-grid nommé
#: en français tombait dans le panier RÉSEAU (une option « sans batterie »
#: FANTÔME, que le devis ne peut pas livrer) tandis qu'un « Off-Grid » anglais
#: ne tombait NULLE PART (aucune option servable → PDF refusé, panneaux et
#: options disparus de la page client). Les deux orthographes accentuées et
#: non accentuées sont listées, comme le fait déjà ``is_reseau_inverter``.
OFFGRID_KEYWORDS = (
    "off-grid", "off grid", "offgrid",
    "hors reseau", "hors réseau",
    "autonome",
)


def _a_mot_cle_offgrid(d: str) -> bool:
    """Le texte (DÉJÀ minusculé) porte-t-il un mot-clé hors-réseau ?"""
    return any(mot in d for mot in OFFGRID_KEYWORDS)


#: QJR-OFFGRID ROUND 2 (incident fondateur 01/09/2026) — les VRAIS produits du
#: fondateur en prod s'appellent « Deye off-Grid 6kw » / « Deye off grid 6kw » :
#: AUCUN mot « onduleur » dans le nom. Exiger « onduleur » ratait donc son
#: propre catalogue — la composition refusait (« Aucun onduleur hors
#: réseau… »), le groupe du sélecteur disparaissait. La machine doit s'adapter
#: à SA façon de nommer, pas l'inverse : sans « onduleur » dans le nom, on
#: accepte quand même — SAUF si un mot-clé d'une AUTRE famille de produit
#: (batterie, câble, coffret…) est présent, pour ne jamais voler la
#: classification d'un accessoire simplement parce qu'un revendeur a mis
#: « off-grid » dans son propre nom marketing (« Kit solaire off-grid »,
#: « Batterie off-grid 5kWh »). Accentué ET non accentué, comme ce module le
#: fait déjà partout (il ne retire jamais les accents, seulement la casse).
OFFGRID_AUTRE_FAMILLE_KEYWORDS = (
    "batterie", "panneau", "panneaux", "module", "pompe", "variateur",
    "structure", "cable", "câble", "coffret", "disjoncteur",
    "differentiel", "différentiel", "parafoudre", "compteur",
    "smart meter", "wifi", "kit", "chargeur",
)


def is_hybrid_inverter(designation: str) -> bool:
    d = (designation or "").lower()
    return "onduleur" in d and "hybride" in d


def is_offgrid_inverter(designation: str) -> bool:
    """Onduleur AUTONOME — ni réseau, ni hybride.

    PRÉCÉDENCE : « hybride » l'emporte. Un « Onduleur Hybride Off-Grid » est un
    HYBRIDE (il sait faire les deux) — le classer autonome le sortirait du
    panier « avec » que la règle hybride lui garantit déjà.

    ROUND 2 : le mot « onduleur » n'est plus OBLIGATOIRE dans le nom — le
    fondateur ne l'y met pas (« Deye off-Grid 6kw »). Sans lui, un mot-clé
    hors-réseau suffit, À CONDITION qu'aucun mot-clé d'une AUTRE famille de
    produit ne soit présent (sinon on volerait un panneau/une batterie/un
    accessoire nommé « ... off-grid ... » par le revendeur).
    """
    d = (designation or "").lower()
    if not _a_mot_cle_offgrid(d) or "hybride" in d:
        return False
    if "onduleur" in d:
        return True
    return not any(mot in d for mot in OFFGRID_AUTRE_FAMILLE_KEYWORDS)


def is_reseau_inverter(designation: str) -> bool:
    d = (designation or "").lower()
    return ("onduleur" in d
            and ("réseau" in d or "reseau" in d or "injection" in d)
            # QJR-OFFGRID — « hors réseau » n'est PAS « réseau ».
            and not _a_mot_cle_offgrid(d))


def is_any_inverter(designation: str) -> bool:
    return (is_hybrid_inverter(designation)
            or is_reseau_inverter(designation)
            or is_offgrid_inverter(designation))


def is_inverter(designation: str) -> bool:
    return "onduleur" in (designation or "").lower()


def is_smart_meter(designation: str) -> bool:
    return "smart meter" in (designation or "").lower()


#: QJR301 — « Wi-Fi » S'ÉCRIT DE PLUSIEURS FAÇONS. Le prédicat testait
#: ``"wifi" in d`` : ``Passerelle Wi-Fi Deye`` (trait d'union) passait donc au
#: travers, vérifié par exécution — ``est_accessoire_huawei('Passerelle Wi-Fi
#: Deye')`` rendait ``False``. Les séparateurs usuels entre « wi » et « fi »
#: sont désormais tolérés ; le reste du prédicat est inchangé.
_WIFI_RE = re.compile(r"wi[\s\-_.]*fi")


def is_wifi_dongle(designation: str) -> bool:
    d = (designation or "").lower()
    return "dongle" in d or bool(_WIFI_RE.search(d))


def _as_kw(value):
    try:
        v = float(value)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


# ═════════════════════════════════════════════════════════════════════════════
# PV10 — Pont UNIQUE catalogue → paramètres de dimensionnement
# ═════════════════════════════════════════════════════════════════════════════
# Le catalogue porte désormais une fiche technique normalisée (PV5) lue en
# cross-app par le SÉLECTEUR ``apps.stock.selectors.specs_for_produit`` (PV6).
# Les deux fonctions ci-dessous sont le SEUL pont entre ce sélecteur et les
# clés de ``DEFAULT_MODULE`` / ``DEFAULT_INVERTER_WINDOW`` : tout futur
# appelant (conception électrique, cible de dimensionnement, pont toiture 3D…)
# passe par ici plutôt que de re-mapper les champs de fiche à sa façon.
#
# GARANTIE : produit sans fiche (ou fiche d'un autre ``type_fiche``) → dict
# VIDE, donc ``{**DEFAULT_MODULE, **specs_module_pour_produit(p)}`` reste
# byte-identique à ``DEFAULT_MODULE``. Aucun défaut n'est jamais deviné.

# Clé sélecteur stock (PV6) → clé de ce module, avec son convertisseur. Les
# valeurs de fiche sont des ``Decimal`` : la conversion en ``float`` est
# OBLIGATOIRE (les calculs de tension mélangent coefficients et flottants).
_MODULE_SPEC_MAP = (
    ('vmp_v', 'vmp', float),
    ('voc_v', 'voc', float),
    ('pmax_wc', 'puissance_w', float),
    ('temp_coeff_voc_pct_c', 'temp_coeff_voc', float),
    # PVCOMPAT (fondateur 20/08/2026) — LES COURANTS. Ils étaient structurellement
    # ignorés : la fiche les porte (PV5) mais rien ne les descendait jusqu'au
    # noyau, si bien qu'aucun verdict de courant ne pouvait sortir de
    # ``string_design`` — d'où « il n'y a pas de PV parce que le courant maxi par
    # MPPT de cet onduleur est sous le courant de nos panneaux » qui n'était
    # jamais dit. La clé de destination GARDE son unité dans son nom (convention
    # du noyau), un courant se confondant trop facilement avec une tension.
    ('isc_a', 'isc_a', float),
    ('imp_a', 'imp_a', float),
)
# NOTE : ``temp_coeff_pmax_pct_c`` n'est volontairement PAS mappé sur
# ``temp_coeff_vmp`` — le coefficient de Pmax et celui de Vmp sont deux
# grandeurs différentes ; à défaut de champ dédié sur la fiche, le défaut
# conservateur du module reste en place.

_INVERTER_SPEC_MAP = (
    ('n_mppt', 'n_mppt', int),
    ('mppt_v_min', 'v_mppt_min', float),
    ('mppt_v_max', 'v_mppt_max', float),
    ('v_max_abs', 'v_max', float),
    ('ac_kw', 'ac_kw', float),
    # PVCOMPAT — les DEUX bornes de courant d'entrée, que le noyau distingue :
    # ``i_max_mppt_a`` est la borne de FONCTIONNEMENT (somme des Imp — au-delà
    # l'onduleur écrête en permanence), ``isc_max_mppt_a`` la borne MATÉRIELLE
    # (somme des Isc). Absente, la seconde retombe sur la première côté noyau
    # (repli PRUDENT de ``SpecOnduleur.courant_isc_max_a``) : jamais une borne
    # plus permissive que ce que la fiche garantit.
    ('i_max_mppt_a', 'i_max_mppt_a', float),
    ('isc_max_mppt_a', 'isc_max_mppt_a', float),
    # PVOND-H a ajouté le champ de tension de DÉMARRAGE à la fiche ; la clé
    # historique de ce module s'appelle ``v_min`` et sert DÉJÀ exactement à ça
    # (elle est passée telle quelle à ``SpecOnduleur.v_demarrage_v``, cf.
    # ``_entree_electrique_du_dict``). Le mapping est donc trivialement
    # cohérent : une fiche qui déclare sa tension de démarrage l'emporte sur le
    # défaut de marché ; une fiche muette garde ce défaut, à l'identique.
    ('v_demarrage_v', 'v_min', float),
)
# NOTE : ``phases`` n'entre pas dans la conception de chaînes (c'est une
# contrainte de RACCORDEMENT, portée par la composition) : ignoré ici.


def _specs_produit(produit):
    """Specs normalisées d'un produit — lecture cross-app PAR LE SÉLECTEUR.

    Import FONCTION-LOCAL de ``apps.stock.selectors`` : la lecture cross-app
    passe exclusivement par le sélecteur de l'app cible et l'import différé
    évite tout cycle au chargement des modules.
    """
    if produit is None:
        return {}
    from apps.stock.selectors import specs_for_produit
    return specs_for_produit(produit) or {}


def _remap(specs, mapping):
    """Traduit les clés sélecteur en clés de ce module (valeurs converties).

    Une clé absente, nulle ou non convertible est OMISE — jamais rendue à
    ``None`` : le dict retourné se fusionne sans risque sur un dict de défauts.
    """
    out = {}
    for src, dst, cast in mapping:
        value = specs.get(src)
        if value is None:
            continue
        try:
            out[dst] = cast(value)
        except (TypeError, ValueError):
            continue
    return out


def specs_module_pour_produit(produit):
    """PV10 — paramètres électriques MODULE d'un produit, prêts pour ``module=``.

    Traduit la fiche technique ``type_fiche='module'`` (PV5, lue via le
    sélecteur stock PV6) dans les clés de ``DEFAULT_MODULE`` :
    ``vmp_v→vmp``, ``voc_v→voc``, ``pmax_wc→puissance_w``,
    ``temp_coeff_voc_pct_c→temp_coeff_voc`` (le signe de la fiche est repris
    tel quel : un coefficient de Voc est négatif sur toute fiche constructeur),
    ``isc_a→isc_a`` et ``imp_a→imp_a`` (PVCOMPAT — les courants, sans lesquels
    aucun verdict de courant d'entrée MPPT ne peut être prononcé).

    Usage : ``string_design(n, module=specs_module_pour_produit(panneau))``.
    Produit ``None``, sans fiche, ou fiche d'un autre type → ``{}``.
    """
    return _remap(_specs_produit(produit), _MODULE_SPEC_MAP)


def fenetre_onduleur_pour_produit(produit):
    """PV10 — fenêtre de tension ONDULEUR d'un produit, prête pour ``inverter=``.

    Traduit la fiche technique ``type_fiche='onduleur'`` (PV5, lue via le
    sélecteur stock PV6) dans les clés de ``DEFAULT_INVERTER_WINDOW`` :
    ``n_mppt→n_mppt``, ``mppt_v_min→v_mppt_min``, ``mppt_v_max→v_mppt_max``,
    ``v_max_abs→v_max``, ``ac_kw→ac_kw``, et — PVCOMPAT —
    ``i_max_mppt_a→i_max_mppt_a``, ``isc_max_mppt_a→isc_max_mppt_a``,
    ``v_demarrage_v→v_min``.

    Usage : ``string_design(n, inverter=fenetre_onduleur_pour_produit(ond))``.
    Produit ``None``, sans fiche, ou fiche d'un autre type → ``{}``.
    """
    return _remap(_specs_produit(produit), _INVERTER_SPEC_MAP)


# ═════════════════════════════════════════════════════════════════════════════
# FG246 — Calcul de chaînes (string design) & vérification du ratio DC/AC
# ═════════════════════════════════════════════════════════════════════════════
# PV83 (ARC6) — la PHYSIQUE de ce calcul ne vit plus ici : elle vit dans
# ``core.electrique.chaines`` (PV34), la couche fondation. Ce
# module n'en garde que l'ADAPTATEUR : il traduit les dicts historiques
# (``module=`` / ``inverter=``) en ``EntreeElectrique``, appelle le noyau, et
# reconstruit la charge utile historique clé pour clé.
#
# CE QUI RESTE LOCAL, ET POURQUOI (aucun comportement changé en silence) :
#
# 1. **Les tensions PUBLIÉES et les contrôles sont ARRONDIS au dixième.**
#    L'historique compare ``round(voc_froid × longueur, 1)`` à ``v_max`` ; le
#    noyau compare la valeur non arrondie. Sur un cas juste à la borne les deux
#    ne rendent pas le même verdict — l'arrondi historique est donc conservé
#    ici, sur les tensions unitaires FOURNIES PAR LE NOYAU.
# 2. **Le repli « répartition non homogène » compte les chaînes au PLAFOND.**
#    L'historique fait ``strings = ceil(n / longueur)`` (la dernière chaîne est
#    incomplète) ; le noyau fait un plancher et ANNONCE le reste en réserve
#    d'appoint. Les deux longueurs de chaîne sont identiques, le nombre de
#    chaînes non : la convention historique est conservée ici.
# 3. **``dc_kw`` compte TOUS les panneaux**, réserve d'appoint comprise, alors
#    que le noyau ne compte que la puissance réellement mise en chaîne.
# 4. **Le texte des avertissements** est celui de l'historique (« V_max
#    onduleur », « ratio DC/AC … élevé ») : des écrans, des tests et des
#    dossiers le citent. Le noyau rédige les siens autrement.
def _voltage_at_temp(v_stc: float, temp_coeff_pct_per_c: float,
                     cell_temp_c: float) -> float:
    """Tension à ``cell_temp_c`` à partir d'une tension STC (25 °C).

    RE-EXPORT (PV83) de la dérive linéaire du noyau
    ``core.electrique.types`` : même formule, même convention de signe (à FROID
    la tension MONTE, coeff négatif × écart négatif = positif). Conservé comme
    point d'entrée nommé pour les appelants historiques de ce module.
    """
    from core.electrique.types import _tension_a_temperature
    return _tension_a_temperature(v_stc, temp_coeff_pct_per_c, cell_temp_c)


def _entree_electrique_du_dict(mod, inv, n, n_mppt, cold_temp_c, hot_temp_c):
    """PV83 — traduit les dicts historiques en ``EntreeElectrique`` du noyau.

    Un seul ``GroupePan`` : le calcul historique ne connaît pas les pans, il
    répartit un total de panneaux sur les entrées MPPT d'un onduleur.

    PVCOMPAT (fondateur 20/08/2026) — LES COURANTS PASSENT DÉSORMAIS. Ils
    étaient mis à 0 EN DUR ici, si bien que le noyau sautait TOUS ses verdicts
    de courant quelle que soit la richesse des fiches : le cas même que le
    fondateur cite (« pas de PV parce que le courant maxi par MPPT de cet
    onduleur est sous le courant de nos panneaux ») ne pouvait pas être
    prononcé. Ils viennent maintenant des dicts (donc de la fiche technique via
    le pont PV10) — et VALENT ENCORE 0 quand la fiche ne les porte pas, ce qui
    fait retomber le noyau, à l'identique, sur son silence : dégradé, jamais
    inventé.
    """
    from core.electrique.types import (
        EntreeElectrique, GroupePan, SpecModule, SpecOnduleur)

    def _courant(valeur):
        """Courant en ampères, 0.0 quand la donnée manque (jamais deviné)."""
        try:
            v = float(valeur)
        except (TypeError, ValueError):
            return 0.0
        return v if v > 0 else 0.0

    isc_max = inv.get("isc_max_mppt_a")
    try:
        isc_max = float(isc_max) if isc_max is not None else None
    except (TypeError, ValueError):
        isc_max = None
    if isc_max is not None and isc_max <= 0:
        # 0 n'est pas une borne, c'est une absence : on rend la main au repli
        # PRUDENT du noyau (``courant_isc_max_a`` → ``i_max_mppt_a``).
        isc_max = None

    spec_module = SpecModule(
        vmp_v=float(mod["vmp"]),
        voc_v=float(mod["voc"]),
        isc_a=_courant(mod.get("isc_a")),
        imp_a=_courant(mod.get("imp_a")),
        pmax_wc=float(mod.get("puissance_w")
                      or DEFAULT_MODULE["puissance_w"]),
        temp_coeff_voc_pct_c=float(mod["temp_coeff_voc"]),
        temp_coeff_pmax_pct_c=float(mod["temp_coeff_vmp"]),
    )
    spec_onduleur = SpecOnduleur(
        n_mppt=n_mppt,
        mppt_v_min=float(inv["v_mppt_min"]),
        mppt_v_max=float(inv["v_mppt_max"]),
        v_max_abs=float(inv["v_max"]),
        i_max_mppt_a=_courant(inv.get("i_max_mppt_a")),
        ac_kw=_as_kw(inv.get("ac_kw")) or 0.0,
        # L'historique distingue la tension de DÉMARRAGE (``v_min``) du bas de
        # plage MPPT ; le noyau retombe sur le bas de plage à défaut : on la
        # lui passe explicitement pour garder les deux bornes distinctes.
        v_demarrage_v=float(inv["v_min"]),
        isc_max_mppt_a=isc_max,
    )
    return EntreeElectrique(
        module=spec_module,
        onduleur=spec_onduleur,
        groupes=(GroupePan(label="champ", nb_modules=n,
                           azimut_deg=0.0, inclinaison_deg=0.0),),
        temp_froid_c=cold_temp_c,
        temp_chaud_c=hot_temp_c,
    )


def _alertes_courant(resultat_chaines, entree):
    """PVCOMPAT — les SEULES alertes de COURANT d'une conception de chaînes.

    ``ResultatChaines.alertes`` mélange trois natures : la forme de la
    répartition (« aucune découpe en chaînes ÉGALES », « modules en réserve »),
    les bornes de TENSION, et les bornes de COURANT. Les deux premières sont
    déjà rédigées par ce module dans son propre vocabulaire historique — les
    reprendre les dirait deux fois. On redemande donc au noyau ses SEULS
    verdicts de courant, en rappelant sa fonction dédiée sur une liste neuve :
    aucun tri par mot-clé, donc aucune divergence possible le jour où le noyau
    reformule ses phrases.

    Les verdicts de courant ont DEUX sévérités depuis DEV-202608-0016 (Isc
    cumulé au-dessus de la borne matérielle PUBLIÉE = bloquant ; écrêtage sur
    l'Imp = alerte). Cette liste les rend TOUS les deux : elle répond « quels
    verdicts de courant le noyau prononce-t-il ? », pas « lesquels sont
    graves ? » — la sévérité se lit dans ``bloquants``/``alertes``, qui
    viennent du noyau eux aussi. Sans cela, le message le plus grave serait le
    seul à disparaître des ``warnings`` de ``string_design``.
    """
    from core.electrique.chaines import _verdicts_courant
    alertes = []
    bloquants = _verdicts_courant(resultat_chaines.chaines, entree.onduleur,
                                  alertes)
    return list(bloquants) + alertes


def verdicts_chaines(n_panels, module=None, inverter=None,
                     cold_temp_c=None, hot_temp_c=None):
    """PVCOMPAT — la TAXONOMIE du noyau pour un couple module/onduleur.

    ``string_design`` rend une charge utile historique (des ``checks`` binaires
    et une liste de ``warnings`` à plat) qui ne dit PAS ce qui, dans le verdict,
    arrête le dossier et ce qui le dégrade seulement. Le noyau, lui, sépare :

    * ``bloquants`` — le matériel est en danger (Voc à froid au-dessus de la
      tension maximale absolue) ou aucune longueur de chaîne n'existe (fenêtre
      de tension vide) ;
    * ``alertes`` — la production est dégradée mais rien ne casse (écrêtage par
      la plage MPPT, MPPT hors plage en été, ET les DEUX bornes de courant
      d'entrée : Imp cumulé au-dessus du courant admissible, Isc cumulé
      au-dessus de la borne matérielle).

    Cette fonction EXPOSE cette séparation telle quelle, sans la retraduire :
    tout appelant qui doit trancher « incompatible » / « sous réserve » lit ici
    plutôt que de rejouer une règle à lui (règle qui divergerait du jour où le
    noyau change d'avis). Retourne un dict JSON-sérialisable
    ``{bloquants, alertes, alertes_courant, fenetre_trop_etroite,
    longueur_chaine, nb_chaines, homogene}``. Ne lève jamais.

    CALX286 — ``cold_temp_c`` / ``hot_temp_c`` NE sont PLUS supposées : sans
    elles, aucun verdict n'est prononcé (valeurs ``None``) et la charge utile
    porte ``omissions`` qui nomme la température manquante.
    """
    from core.electrique.chaines import concevoir_chaines

    mod = {**DEFAULT_MODULE, **(module or {})}
    inv = {**DEFAULT_INVERTER_WINDOW, **(inverter or {})}
    try:
        n = int(n_panels)
    except (TypeError, ValueError):
        n = 0
    n_mppt = max(1, int(inv.get("n_mppt") or 1))

    if n <= 0:
        return {
            "bloquants": [], "alertes": ["aucun module à répartir"],
            "alertes_courant": [], "fenetre_trop_etroite": False,
            "longueur_chaine": 0, "nb_chaines": 0, "homogene": True,
        }

    omissions = _omissions_temperatures(
        cold_temp_c, hot_temp_c,
        ["bloquants", "alertes", "alertes_courant", "fenetre_trop_etroite",
         "longueur_chaine", "nb_chaines", "homogene"])
    if omissions:
        return {
            "bloquants": None, "alertes": None, "alertes_courant": None,
            "fenetre_trop_etroite": None, "longueur_chaine": None,
            "nb_chaines": None, "homogene": None, "omissions": omissions,
        }

    entree = _entree_electrique_du_dict(mod, inv, n, n_mppt,
                                        cold_temp_c, hot_temp_c)
    resultat = concevoir_chaines(entree)
    repartition = (resultat.repartitions[0] if resultat.repartitions else None)
    return {
        "bloquants": list(resultat.bloquants),
        "alertes": list(resultat.alertes),
        "alertes_courant": _alertes_courant(resultat, entree),
        "fenetre_trop_etroite": bool(
            resultat.fenetre.trop_etroite if resultat.fenetre else False),
        "longueur_chaine": (repartition.longueur_chaine
                            if repartition else 0),
        "nb_chaines": repartition.nb_chaines if repartition else 0,
        "homogene": bool(repartition.homogene) if repartition else True,
    }


def string_design(n_panels, module=None, inverter=None,
                  cold_temp_c=None, hot_temp_c=None):
    """FG246 — répartit ``n_panels`` panneaux sur les MPPT et vérifie la fenêtre.

    Distribue les panneaux en chaînes série équilibrées sur les ``n_mppt``
    entrées de l'onduleur, choisit une longueur de chaîne qui respecte les
    bornes de tension, puis VÉRIFIE :

    * Voc de la chaîne à FROID (``cold_temp_c``) ≤ ``v_max`` (sécurité absolue).
    * Vmp de la chaîne à FROID dans la plage MPPT haute (``v_mppt_max``).
    * Vmp de la chaîne à CHAUD (``hot_temp_c``) ≥ ``v_mppt_min`` (démarrage MPPT).
    * Vmp à chaud ≥ ``v_min`` (démarrage onduleur).

    Et rapporte le ratio DC/AC (puissance crête DC ÷ puissance AC onduleur).

    PVCOMPAT — quand les fiches portent les COURANTS (Isc/Imp module, courant
    admissible par entrée MPPT), les verdicts de courant du noyau rejoignent
    ``warnings`` (jamais ``checks`` : ce sont des ALERTES au sens du noyau, pas
    des contrôles de la fenêtre de tension — cf. ``verdicts_chaines`` pour la
    taxonomie bloquant/alerte séparée). Fiches muettes ⇒ aucun verdict de
    courant, comme avant.

    Paramètres
    ----------
    n_panels : nombre total de panneaux.
    module : dict de paramètres électriques module (défaut ``DEFAULT_MODULE``).
    inverter : dict de fenêtre onduleur (défaut ``DEFAULT_INVERTER_WINDOW``).
    cold_temp_c / hot_temp_c : températures cellule de dimensionnement (°C).

    Retourne un dict JSON-sérialisable ``{n_panels, n_mppt, strings,
    panels_per_string, dc_kw, ac_kw, dc_ac_ratio, voltages{...}, checks{...},
    ok, warnings[]}``. Ne lève jamais sur des entrées dégradées : sur 0 panneau,
    retourne une structure vide cohérente.

    PV83 (ARC6) — SHIM : la physique (fenêtre de tension et découpe en chaînes
    égales) est celle de ``core.electrique.chaines``. Les quatre points
    volontairement conservés ici sont listés en tête de section.

    CALX286 — ``cold_temp_c`` / ``hot_temp_c`` NE sont PLUS supposées : sans
    elles, la répartition, les tensions et les contrôles valent ``None`` et
    ``omissions`` nomme la température manquante ; ``n_panels``, ``n_mppt``,
    ``dc_kw``, ``ac_kw`` et le ratio DC/AC (qui n'en dépendent pas) restent
    publiés. Un ``module`` / ``inverter`` absent retombe sur ``DEFAULT_MODULE``
    / ``DEFAULT_INVERTER_WINDOW`` et le DIT dans ``hypotheses``. Les deux clés
    n'apparaissent que non vides : la charge utile historique reste identique
    clé pour clé quand tout est fourni.
    """
    from core.electrique.chaines import concevoir_chaines

    mod = {**DEFAULT_MODULE, **(module or {})}
    inv = {**DEFAULT_INVERTER_WINDOW, **(inverter or {})}
    hypotheses = []
    if not module:
        hypotheses.append(_hypothese(
            "module", dict(DEFAULT_MODULE), _source_defaut("DEFAULT_MODULE"),
            ["dc_kw", "dc_ac_ratio", "voltages", "strings",
             "panels_per_string", "string_layout"]))
    if not inverter:
        hypotheses.append(_hypothese(
            "inverter", dict(DEFAULT_INVERTER_WINDOW),
            _source_defaut("DEFAULT_INVERTER_WINDOW"),
            ["n_mppt", "string_layout", "strings", "panels_per_string",
             "checks"]))

    try:
        n = int(n_panels)
    except (TypeError, ValueError):
        n = 0
    n_mppt = max(1, int(inv.get("n_mppt") or 1))

    warnings = []

    vmp_stc = float(mod["vmp"])

    v_max = float(inv["v_max"])
    v_min = float(inv["v_min"])
    v_mppt_min = float(inv["v_mppt_min"])
    v_mppt_max = float(inv["v_mppt_max"])

    def _avec_publication(charge, omissions=()):
        """Ajoute ``hypotheses`` / ``omissions`` SEULEMENT s'ils sont non vides."""
        if hypotheses:
            charge["hypotheses"] = hypotheses
        if omissions:
            charge["omissions"] = list(omissions)
        return charge

    if n <= 0:
        return _avec_publication({
            "n_panels": 0, "n_mppt": n_mppt, "strings": 0,
            "panels_per_string": 0, "string_layout": [],
            "dc_kw": 0.0, "ac_kw": _as_kw(inv.get("ac_kw")),
            "dc_ac_ratio": None,
            "voltages": {}, "checks": {}, "ok": False,
            "warnings": ["aucun panneau à répartir"],
        })

    omissions = _omissions_temperatures(
        cold_temp_c, hot_temp_c,
        ["strings", "panels_per_string", "string_layout", "voltages",
         "checks", "ok"])
    if omissions:
        panel_w_seul = float(mod.get("puissance_w")
                             or DEFAULT_MODULE["puissance_w"])
        dc_kw = round(n * panel_w_seul / 1000.0, 3)
        ac_kw = _as_kw(inv.get("ac_kw"))
        return _avec_publication({
            "n_panels": n, "n_mppt": n_mppt, "strings": None,
            "panels_per_string": None, "string_layout": None,
            "dc_kw": dc_kw, "ac_kw": ac_kw,
            "dc_ac_ratio": (round(dc_kw / ac_kw, 3)
                            if ac_kw and ac_kw > 0 else None),
            "voltages": None, "checks": None, "ok": None,
            "warnings": [o["motif"] for o in omissions],
        }, omissions)

    entree = _entree_electrique_du_dict(mod, inv, n, n_mppt,
                                        cold_temp_c, hot_temp_c)
    panel_w = entree.module.pmax_wc
    resultat_chaines = concevoir_chaines(entree)
    fenetre = resultat_chaines.fenetre

    # Tensions unitaires aux températures de dimensionnement — celles du noyau.
    voc_cold = fenetre.voc_froid_unitaire_v
    vmp_cold = fenetre.vmp_froid_unitaire_v
    vmp_hot = fenetre.vmp_chaud_unitaire_v

    # ── Longueur de chaîne admissible (bornée par le Voc à froid) ──
    # Les quatre bornes sont celles de ``fenetre_admissible`` (PV34), qui est le
    # port À L'IDENTIQUE du calcul historique.
    max_len = fenetre.longueur_max
    window_too_narrow = fenetre.trop_etroite
    if window_too_narrow:
        # Motif rédigé à l'identique de l'historique (le noyau rédige le sien).
        warnings.append(
            "fenêtre de tension trop étroite pour ce module : aucune longueur "
            "de chaîne ne respecte à la fois la borne haute (froid) et le "
            "démarrage MPPT (chaud) — vérifier le couple module/onduleur")

    # ── Répartition équilibrée sur les MPPT ──
    # Le noyau vise une longueur de chaîne qui partitionne n en chaînes ÉGALES
    # sur les entrées MPPT, dans [longueur_min, longueur_max], la plus longue
    # possible — un seul pan ici, donc toutes les entrées lui sont allouées.
    repartition = resultat_chaines.repartitions[0]
    panels_per_string = repartition.longueur_chaine
    strings = repartition.nb_chaines

    uneven = not repartition.homogene
    if uneven:
        # Aucun découpage propre — repli HISTORIQUE : la dernière chaîne est
        # incomplète (plafond), là où le noyau annonce un reste en réserve.
        panels_per_string = min(n, max_len)
        strings = int(math.ceil(n / panels_per_string))
        warnings.append(
            "répartition non homogène : les chaînes ne sont pas toutes de "
            "longueur égale (vérifier la conception)")

    # Disposition réelle des chaînes par MPPT (équilibrée).
    string_layout = _distribute_strings(strings, n_mppt)

    # ── Tensions au niveau CHAÎNE ──
    string_voc_cold = round(voc_cold * panels_per_string, 1)
    string_vmp_cold = round(vmp_cold * panels_per_string, 1)
    string_vmp_hot = round(vmp_hot * panels_per_string, 1)
    string_vmp_stc = round(vmp_stc * panels_per_string, 1)

    # ── Vérifications ──
    checks = {
        # Sécurité absolue : Voc froid sous le V_max DC.
        "voc_cold_under_vmax": string_voc_cold <= v_max,
        # Vmp froid sous le haut de plage MPPT.
        "vmp_cold_under_mppt_max": string_vmp_cold <= v_mppt_max,
        # Vmp chaud au-dessus du bas de plage MPPT.
        "vmp_hot_over_mppt_min": string_vmp_hot >= v_mppt_min,
        # Vmp chaud au-dessus du démarrage onduleur.
        "vmp_hot_over_vmin": string_vmp_hot >= v_min,
    }
    if not checks["voc_cold_under_vmax"]:
        warnings.append(
            f"Voc à froid {string_voc_cold} V > V_max onduleur {v_max} V — "
            "chaîne trop longue, RISQUE matériel (réduire le nombre de modules "
            "par chaîne)")
    if not checks["vmp_cold_under_mppt_max"]:
        warnings.append(
            f"Vmp à froid {string_vmp_cold} V > haut de plage MPPT {v_mppt_max} "
            "V — l'onduleur écrête, perte de production")
    if not checks["vmp_hot_over_mppt_min"]:
        warnings.append(
            f"Vmp à chaud {string_vmp_hot} V < bas de plage MPPT {v_mppt_min} V "
            "— chaîne trop courte, MPPT hors plage en été")
    if not checks["vmp_hot_over_vmin"]:
        warnings.append(
            f"Vmp à chaud {string_vmp_hot} V < démarrage onduleur {v_min} V")

    # ── PVCOMPAT — verdicts de COURANT d'entrée MPPT, prononcés par le NOYAU ──
    # Ils ne rejoignent PAS ``checks`` : la charge utile historique de cette
    # fonction est épinglée clé pour clé (``test_pv83_shims_electrique``), et
    # ces verdicts sont des ALERTES au sens du noyau — pas des contrôles
    # binaires de la fenêtre de tension. Ils rejoignent ``warnings``, la liste
    # que tous les appelants lisent déjà, avec le TEXTE du noyau (jamais un
    # texte réécrit : les chiffres qu'il cite viennent de la fiche).
    warnings.extend(_alertes_courant(resultat_chaines, entree))

    # ── Ratio DC/AC ──
    dc_kw = round(n * panel_w / 1000.0, 3)
    ac_kw = _as_kw(inv.get("ac_kw"))
    dc_ac_ratio = round(dc_kw / ac_kw, 3) if ac_kw and ac_kw > 0 else None
    if dc_ac_ratio is not None:
        if dc_ac_ratio > 1.5:
            warnings.append(
                f"ratio DC/AC {dc_ac_ratio} élevé (> 1.5) — surdimensionnement "
                "DC important, écrêtage probable")
        elif dc_ac_ratio < 1.0:
            warnings.append(
                f"ratio DC/AC {dc_ac_ratio} faible (< 1.0) — onduleur "
                "surdimensionné par rapport au champ PV")

    ok = all(checks.values()) and not uneven and not window_too_narrow

    return _avec_publication({
        "n_panels": n,
        "n_mppt": n_mppt,
        "strings": strings,
        "panels_per_string": panels_per_string,
        "string_layout": string_layout,
        "dc_kw": dc_kw,
        "ac_kw": ac_kw,
        "dc_ac_ratio": dc_ac_ratio,
        "voltages": {
            "voc_cold": string_voc_cold,
            "vmp_cold": string_vmp_cold,
            "vmp_hot": string_vmp_hot,
            "vmp_stc": string_vmp_stc,
            "cold_temp_c": cold_temp_c,
            "hot_temp_c": hot_temp_c,
        },
        "checks": checks,
        "ok": ok,
        "warnings": warnings,
    })


def _choose_string_layout(n, n_mppt, min_len, max_len):
    """Choisit (panels_per_string, strings) : chaînes ÉGALES, longueur valide.

    PV83 (ARC6) — RE-EXPORT de ``core.electrique.chaines._choisir_longueur`` :
    même recherche (partition de ``n`` en chaînes ÉGALES dont la longueur ∈
    [min_len, max_len], en privilégiant un nombre de chaînes multiple de
    ``n_mppt`` puis les chaînes les plus longues), même ``(0, 0)`` quand aucune
    partition égale n'existe. Conservé comme point d'entrée nommé pour les
    appelants historiques de ce module.
    """
    from core.electrique.chaines import _choisir_longueur
    return _choisir_longueur(n, n_mppt, min_len, max_len)


def _distribute_strings(strings, n_mppt):
    """Répartit ``strings`` chaînes sur ``n_mppt`` entrées, le plus égal possible.

    Renvoie une liste de longueur ``n_mppt`` : nombre de chaînes par MPPT.
    """
    base = strings // n_mppt
    extra = strings % n_mppt
    return [base + (1 if i < extra else 0) for i in range(n_mppt)]


# ═════════════════════════════════════════════════════════════════════════════
# FG247 — Appariement module–onduleur depuis le catalogue
# ═════════════════════════════════════════════════════════════════════════════
def match_inverter(produits, *, n_panels, panel_w=None, hybrid=False,
                   module=None, inverter_window=None,
                   cold_temp_c=None, hot_temp_c=None):
    """FG247 — propose l'onduleur catalogue compatible pour une config panneaux.

    Parcourt ``produits`` (itérable de ``stock.Produit``), retient les onduleurs
    de la bonne FAMILLE — hybride si ``hybrid`` sinon réseau/injection, mots-clés
    ALIGNÉS sur ``builder.py`` — puis choisit le plus petit onduleur (kW) dont :

    * la puissance AC supporte un ratio DC/AC raisonnable (≤ ``MAX_DC_AC``) ;
    * la fenêtre de tension accepte au moins une longueur de chaîne valide pour
      le module (réutilise ``string_design`` pour la vérif Vmp/Voc à froid).

    Le nom du produit fournit la puissance kW (``parse_kw``). PV10 — la fenêtre
    de tension de CHAQUE candidat vient d'abord de sa fiche technique
    (``fenetre_onduleur_pour_produit``, sélecteur stock PV6) ; un candidat sans
    fiche garde la fenêtre par défaut, à l'identique de l'existant. Ordre de
    priorité : défauts < fiche du produit < ``inverter_window`` explicite <
    puissance AC lue au nom (elle reste la référence du ratio DC/AC affiché).
    Appelant côté base : préférer ``select_related('fiche_technique')`` sur le
    queryset de produits. Aucun prix d'achat n'est lu.

    Retourne un dict ``{inverter, ac_kw, dc_kw, dc_ac_ratio, string_design,
    compatible, candidates_considered, reason}`` ; ``inverter`` est le
    ``Produit`` choisi (ou None si aucun ne convient).

    CALX286 — sans ``cold_temp_c`` / ``hot_temp_c`` fournies, aucune fenêtre
    de tension ne peut être vérifiée : aucun onduleur n'est proposé
    (``inverter: None``, ``compatible: None``) et ``omissions`` le dit, plutôt
    que de trancher sur des températures supposées.
    """
    mod = {**DEFAULT_MODULE, **(module or {})}
    if panel_w:
        try:
            mod["puissance_w"] = float(panel_w)
        except (TypeError, ValueError):
            pass

    try:
        n = int(n_panels)
    except (TypeError, ValueError):
        n = 0

    dc_kw = round(n * float(mod["puissance_w"]) / 1000.0, 3)

    omissions = _omissions_temperatures(
        cold_temp_c, hot_temp_c,
        ["inverter", "ac_kw", "dc_ac_ratio", "string_design", "compatible"])
    if omissions:
        return {
            "inverter": None, "ac_kw": None, "dc_kw": dc_kw,
            "dc_ac_ratio": None, "string_design": None, "compatible": None,
            "candidates_considered": 0,
            "reason": omissions[0]["motif"], "omissions": omissions,
        }

    def _window_for(produit, kw):
        """Fenêtre de tension du candidat : défauts < fiche < surcharge < kW."""
        return {**DEFAULT_INVERTER_WINDOW,
                **fenetre_onduleur_pour_produit(produit),
                **(inverter_window or {}),
                "ac_kw": kw}

    family_pred = is_hybrid_inverter if hybrid else is_reseau_inverter
    # Candidats : bonne famille, puissance lisible, prix de vente réel (jamais
    # un produit « prix à renseigner » — même garde que l'auto-fill).
    candidates = []
    for p in produits:
        nom = getattr(p, "nom", "") or ""
        if not family_pred(nom):
            continue
        kw = parse_kw(nom)
        if kw is None or kw <= 0:
            continue
        prix = getattr(p, "prix_vente", None)
        try:
            priced = prix is not None and float(prix) > 0
        except (TypeError, ValueError):
            priced = False
        if not priced:
            continue
        candidates.append((p, kw))

    # Tri : plus petite puissance d'abord (puis id stable).
    candidates.sort(key=lambda x: (x[1], getattr(x[0], "id", 0) or 0))

    considered = len(candidates)
    chosen = None
    chosen_kw = None
    chosen_design = None
    chosen_ratio = None
    reason = ""

    for p, kw in candidates:
        ratio = (dc_kw / kw) if kw > 0 else None
        # Onduleur trop petit pour le champ (ratio DC/AC excessif) → suivant.
        if ratio is not None and ratio > MAX_DC_AC:
            continue
        window = _window_for(p, kw)
        design = string_design(
            n, module=mod, inverter=window,
            cold_temp_c=cold_temp_c, hot_temp_c=hot_temp_c)
        if design["ok"]:
            chosen, chosen_kw = p, kw
            chosen_design, chosen_ratio = design, design["dc_ac_ratio"]
            reason = ("onduleur le plus petit respectant ratio DC/AC et "
                      "fenêtre de tension")
            break

    if chosen is None and candidates:
        # Aucun candidat parfait : on retient le plus gros (meilleur ratio) en
        # le signalant, plutôt que de ne rien proposer.
        p, kw = candidates[-1]
        window = _window_for(p, kw)
        chosen_design = string_design(
            n, module=mod, inverter=window,
            cold_temp_c=cold_temp_c, hot_temp_c=hot_temp_c)
        chosen, chosen_kw = p, kw
        chosen_ratio = chosen_design["dc_ac_ratio"]
        reason = ("aucun onduleur catalogue parfaitement compatible — plus "
                  "grosse puissance retenue, vérifier la conception")

    if chosen is None:
        reason = ("aucun onduleur "
                  + ("hybride" if hybrid else "réseau/injection")
                  + " chiffrable au catalogue pour cette configuration")

    return {
        "inverter": chosen,
        "ac_kw": chosen_kw,
        "dc_kw": dc_kw,
        "dc_ac_ratio": chosen_ratio,
        "string_design": chosen_design,
        "compatible": bool(chosen_design and chosen_design.get("ok")),
        "candidates_considered": considered,
        "reason": reason,
    }


# ═════════════════════════════════════════════════════════════════════════════
# FG249 — Optimisation inclinaison / azimut (balayage via PVGIS existant)
# ═════════════════════════════════════════════════════════════════════════════
# Convention d'azimut founder (= PVGIS aspect) : Sud 0 / Est −90 / Ouest +90.
DEFAULT_TILT_RANGE = (0, 60, 5)        # (min, max, pas) en degrés
DEFAULT_AZIMUTH_RANGE = (-90, 90, 15)  # (min, max, pas), Sud=0


def _frange(start, stop, step):
    """Plage inclusive d'entiers de ``start`` à ``stop`` par pas ``step``."""
    if step <= 0:
        return [int(start)]
    vals = []
    v = int(start)
    while v <= int(stop):
        vals.append(v)
        v += int(step)
    if vals and vals[-1] != int(stop):
        vals.append(int(stop))
    return vals


def optimize_orientation(settings, lat, lon, *, peakpower_kwc=1.0,
                         tilt_range=DEFAULT_TILT_RANGE,
                         azimuth_range=DEFAULT_AZIMUTH_RANGE,
                         fetch=None):
    """FG249 — balaie (inclinaison, azimut) → orientation au productible maximal.

    Réutilise l'intégration PVGIS EXISTANTE
    (``apps.parametres.pvgis.fetch_productible``, injectable via ``fetch`` pour
    les tests) : pour chaque couple (tilt, azimuth) de la grille, on demande le
    productible (kWh/kWc/an) et on retient le maximum. La fonction PVGIS retombe
    déjà sur l'hypothèse manuelle hors-ligne (jamais d'exception réseau), donc ce
    balayage fonctionne aussi sans réseau (toutes les cases renvoient alors la
    même valeur manuelle → l'orientation par défaut société est retenue).

    Paramètres
    ----------
    settings : ``TariffSettings`` (défauts inclinaison/azimut + repli manuel).
    lat, lon : coordonnées GPS du site.
    peakpower_kwc : puissance crête pour la requête (1 → kWh/kWc/an direct).
    tilt_range / azimuth_range : ``(min, max, pas)`` en degrés.
    fetch : surcharge de ``fetch_productible`` (signature identique) — pour les
        tests, on injecte un stub qui ne touche pas le réseau.

    Retourne ``{best{tilt, azimuth, productible_kwh_kwc, source}, grid[...],
    evaluated, source, default_orientation{tilt, azimuth}, gain_vs_default_pct}``.
    Ne lève jamais sur PVGIS indisponible.
    """
    if fetch is None:
        from apps.parametres.pvgis import fetch_productible as fetch

    tilts = _frange(*tilt_range)
    azimuths = _frange(*azimuth_range)

    default_tilt = int(getattr(settings, "inclinaison_defaut_deg", 30) or 30)
    default_azimuth = int(getattr(settings, "azimut_defaut_deg", 0) or 0)

    grid = []
    best = None
    default_prod = None
    any_pvgis = False

    for tilt in tilts:
        for az in azimuths:
            res = fetch(settings, lat, lon, peakpower_kwc=peakpower_kwc,
                        tilt=tilt, azimuth=az)
            prod = res.get("productible_kwh_kwc")
            src = res.get("source")
            if src == "pvgis":
                any_pvgis = True
            cell = {
                "tilt": tilt, "azimuth": az,
                "productible_kwh_kwc": prod, "source": src,
            }
            grid.append(cell)
            if prod is not None and (
                    best is None or prod > best["productible_kwh_kwc"]):
                best = cell
            if tilt == default_tilt and az == default_azimuth and prod is not None:
                default_prod = prod

    # Productible à l'orientation par défaut société : on l'interroge à part
    # s'il n'est pas tombé sur une case de la grille (gain de référence).
    if default_prod is None:
        res = fetch(settings, lat, lon, peakpower_kwc=peakpower_kwc,
                    tilt=default_tilt, azimuth=default_azimuth)
        default_prod = res.get("productible_kwh_kwc")
        if res.get("source") == "pvgis":
            any_pvgis = True

    gain_pct = None
    if best and default_prod and default_prod > 0:
        gain_pct = round(
            (best["productible_kwh_kwc"] - default_prod) / default_prod * 100, 1)

    return {
        "best": best,
        "grid": grid,
        "evaluated": len(grid),
        "source": "pvgis" if any_pvgis else "manual",
        "default_orientation": {
            "tilt": default_tilt, "azimuth": default_azimuth,
            "productible_kwh_kwc": default_prod,
        },
        "gain_vs_default_pct": gain_pct,
    }


# ── FG250 — Analyse d'ombrage & profil d'horizon ─────────────────────────────
# Transforme l'ombrage QUALITATIF (obstacles + profil d'horizon) en une PERTE
# d'ombrage CHIFFRÉE, mensuelle. Module PUR : aucune base, aucun réseau.
#
# Modèle simplifié et transparent (pas de tracé de rayon par minute) :
#   * Le profil d'horizon est une liste d'élévations (degrés au-dessus de
#     l'horizontale) par secteur d'azimut. Plus l'horizon est haut au Sud, plus
#     la perte est forte ; l'Est/Ouest pèse moins, le Nord (hémisphère N) ~0.
#   * Des obstacles ponctuels (arbre, mur, cheminée) ajoutent une perte locale
#     pondérée par leur azimut et par la saison (soleil bas en hiver → pertes
#     accrues).
# Le résultat donne une perte mensuelle (%) et une perte annuelle moyenne (%),
# un facteur de production (1 - perte) prêt à multiplier un productible PVGIS.

# Poids saisonnier de l'élévation solaire : en hiver le soleil culmine bas, donc
# un horizon haut masque davantage. Index 0 = janvier … 11 = décembre.
_SHADING_SEASON_WEIGHT = [
    1.35, 1.25, 1.10, 0.95, 0.85, 0.80,
    0.82, 0.90, 1.05, 1.20, 1.32, 1.40,
]

_MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _azimuth_solar_weight(azimuth, hemisphere_north=True):
    """Poids de pénalité d'un obstacle selon son azimut (0=N, 90=E, 180=S, 270=O).

    Le soleil utile est au Sud (hémisphère Nord) : un masque plein Sud coûte le
    plus (poids ~1), l'Est/Ouest ~0.5, le Nord ~0 (le soleil n'y passe jamais).
    """
    try:
        az = float(azimuth) % 360.0
    except (TypeError, ValueError):
        return 0.5
    # Azimut solaire de référence : 180° (Sud) au Nord, 0° (Nord) au Sud.
    ref = 180.0 if hemisphere_north else 0.0
    delta = abs((az - ref + 180.0) % 360.0 - 180.0)  # écart angulaire 0..180
    # cos décroît du Sud (0°) vers le Nord (180°) ; borné à [0, 1].
    return max(0.0, math.cos(math.radians(min(delta, 90.0))))


def shading_analysis(horizon_profile=None, obstacles=None, *,
                     hemisphere_north=True):
    """FG250 — perte d'ombrage mensuelle depuis l'horizon + les obstacles.

    Paramètres
    ----------
    horizon_profile : liste de points ``{azimuth, elevation}`` (degrés). Une
        élévation d'horizon ``e`` au secteur d'azimut ``a`` masque le soleil
        bas ; sa pénalité est ``e/90`` pondérée par le poids solaire de ``a``.
    obstacles : liste de masques ponctuels ``{azimuth, elevation, type?}`` —
        même pénalité, additive et bornée.
    hemisphere_north : True (Maroc) → soleil au Sud.

    Retourne un dict JSON-sérialisable ::

        {monthly_loss_pct: [12], annual_loss_pct, production_factor,
         monthly_production_factor: [12], horizon_severity, n_obstacles,
         warnings: []}

    Ne lève jamais : entrées vides → perte 0, facteur 1.0 (aucun ombrage).
    """
    horizon_profile = horizon_profile or []
    obstacles = obstacles or []
    warnings = []

    def _pt_penalty(pt):
        """Pénalité de base (0..1) d'un point d'horizon/obstacle, hors saison."""
        try:
            elev = float(pt.get("elevation") or 0.0)
        except (TypeError, ValueError, AttributeError):
            return 0.0
        if elev <= 0:
            return 0.0
        elev = min(elev, 90.0)
        az_w = _azimuth_solar_weight(pt.get("azimuth"), hemisphere_north)
        # Fraction du ciel utile masquée par cette élévation à cet azimut.
        return (elev / 90.0) * az_w

    # Sévérité de base = moyenne des pénalités d'horizon + somme bornée des
    # obstacles (un obstacle plein Sud à 30° pèse lourd, plusieurs s'ajoutent).
    horizon_pen = 0.0
    if horizon_profile:
        horizon_pen = sum(_pt_penalty(p) for p in horizon_profile) \
            / len(horizon_profile)
    obstacle_pen = sum(_pt_penalty(p) for p in obstacles)

    # Pénalité de référence (annuelle, avant pondération saisonnière), bornée.
    base_pen = min(0.6, horizon_pen + obstacle_pen)

    if base_pen <= 0:
        return {
            "monthly_loss_pct": [0.0] * 12,
            "annual_loss_pct": 0.0,
            "production_factor": 1.0,
            "monthly_production_factor": [1.0] * 12,
            "horizon_severity": 0.0,
            "n_obstacles": len(obstacles),
            "warnings": ["aucun ombrage significatif détecté"]
            if not (horizon_profile or obstacles) else [],
        }

    monthly_loss_pct = []
    monthly_factor = []
    for w in _SHADING_SEASON_WEIGHT:
        # Perte du mois = pénalité de base × poids saisonnier, en %, bornée à 90.
        loss = min(90.0, round(base_pen * w * 100.0, 1))
        monthly_loss_pct.append(loss)
        monthly_factor.append(round(1.0 - loss / 100.0, 4))

    annual_loss = round(sum(monthly_loss_pct) / 12.0, 1)
    production_factor = round(1.0 - annual_loss / 100.0, 4)

    if annual_loss >= 20.0:
        warnings.append(
            "ombrage important (perte annuelle ≥ 20 %) — envisager un "
            "repositionnement des panneaux ou des optimiseurs/micro-onduleurs")
    elif annual_loss >= 8.0:
        warnings.append(
            "ombrage modéré — vérifier la disposition des chaînes pour limiter "
            "l'impact d'un panneau masqué sur sa chaîne")

    return {
        "monthly_loss_pct": monthly_loss_pct,
        "monthly_labels": list(_MONTHS_FR),
        "annual_loss_pct": annual_loss,
        "production_factor": production_factor,
        "monthly_production_factor": monthly_factor,
        "horizon_severity": round(base_pen, 4),
        "n_obstacles": len(obstacles),
        "warnings": warnings,
    }


# ── FG251 — Générateur de nomenclature électrique (BOQ) ───────────────────────
# Déduit du design (nb panneaux, kWc, conception de chaînes, type d'installation)
# une nomenclature électrique : câbles DC/AC, disjoncteurs, parafoudres,
# coffrets, mise à la terre, structure. Module PUR ; aucun prix (le BOQ liste des
# QUANTITÉS et des spécifications, jamais de prix d'achat/marge).

# Section de câble AC (mm²) par tranche de courant — barème prudent (cuivre).
_AC_CABLE_BY_AMP = [
    (16, 2.5), (25, 4.0), (32, 6.0), (40, 10.0),
    (63, 16.0), (80, 25.0), (100, 35.0), (125, 50.0),
]


def _ac_cable_section(amps):
    for amp_max, section in _AC_CABLE_BY_AMP:
        if amps <= amp_max:
            return section
    return 70.0


def generate_boq(*, n_panels=0, kwc=None, string_result=None,
                 installation_type="reseau", phases=1, has_battery=False,
                 ac_cable_length_m=15.0, dc_cable_length_m=None):
    """FG251 — nomenclature électrique (BOQ) déduite du design.

    Paramètres
    ----------
    n_panels : nombre de panneaux.
    kwc : puissance crête DC (kWc) ; déduite de ``string_result.dc_kw`` sinon.
    string_result : sortie de ``string_design`` (strings/panels_per_string/
        ac_kw…) — pilote la longueur DC et le nombre de protections de chaîne.
    installation_type : 'reseau' | 'hybride' | 'autonome' (pompage exclu — pas
        de BOQ PV classique).
    phases : 1 (mono) ou 3 (triphasé) → calibre disjoncteur AC + section câble.
    has_battery : ajoute le câblage/protections batterie (DC).
    ac_cable_length_m / dc_cable_length_m : longueurs estimées (m) ; le DC est
        déduit du nombre de chaînes si non fourni.

    Retourne ``{items: [{categorie, designation, quantite, unite, spec}],
    summary: {...}, warnings: []}``. JSON-sérialisable, jamais de prix.

    PV83 (ARC6) — POURQUOI CE BORDEREAU N'EST **PAS** UN SHIM.
    ``core.electrique.nomenclature.nomenclature_dict`` (PV37) rend la MÊME
    FORME (``items``/``summary``/``warnings``, mêmes clés de résumé) mais un
    CONTENU délibérément différent, et le remplacement serait un changement de
    comportement silencieux — pas une refactorisation :

    * la SOURCE des lignes diffère. Ici chaque organe est posé par DÉFAUT
      (parafoudre DC, sectionneur-fusible par chaîne, câble « DC 6 mm² » écrit
      en dur). Là-bas chaque ligne descend d'un organe RETENU par une règle
      (IEC 62548, UTE C 15-712-1) ou d'un câble DIMENSIONNÉ : sur une liaison
      DC courte, le parafoudre DISPARAÎT du bordereau ;
    * les DÉSIGNATIONS diffèrent. Le noyau préfixe le repère
      (« F1 — Fusible gPV »), l'historique nomme l'organe (« Sectionneur-fusible
      DC par chaîne ») — des écrans, des exports et des dossiers citent la
      seconde forme ;
    * les SPÉCIFICATIONS diffèrent au caractère près (« selon couverture
      (tuile/bac acier) » ici, « (tuile / bac acier) » là-bas ; la mise à la
      terre cite NF C 15-100 §542 là-bas) ;
    * ``ac_breaker_amp`` est un ENTIER plafonné à 160 A ici (barème
      ``_STD_BREAKERS``) et un FLOTTANT allant à 250 A dans le noyau.

    Le bordereau NORMATIF est donc offert par le noyau, à un appelant qui le
    demande explicitement ; celui-ci reste le bordereau historique du devis,
    inchangé. Un test épingle les deux formes (``test_pv83_shims_electrique``).
    """
    warnings = []
    sr = string_result or {}
    if kwc is None:
        kwc = sr.get("dc_kw")
    try:
        kwc = float(kwc or 0.0)
    except (TypeError, ValueError):
        kwc = 0.0
    try:
        n_panels = int(n_panels or sr.get("n_panels") or 0)
    except (TypeError, ValueError):
        n_panels = 0
    strings = int(sr.get("strings") or (1 if n_panels else 0))
    phases = 3 if int(phases or 1) == 3 else 1

    items = []

    def add(categorie, designation, quantite, unite, spec=""):
        items.append({
            "categorie": categorie,
            "designation": designation,
            "quantite": quantite,
            "unite": unite,
            "spec": spec,
        })

    if n_panels <= 0:
        return {
            "items": [],
            "summary": {"kwc": kwc, "n_panels": 0, "strings": 0,
                        "phases": phases},
            "warnings": ["aucun panneau — pas de nomenclature à générer"],
        }

    # ── Courant & calibre AC ──
    # Puissance AC de référence = ac_kw onduleur si connu, sinon kWc / 1.2.
    ac_kw = sr.get("ac_kw") or (kwc / 1.2 if kwc else 0.0)
    voltage = 400.0 if phases == 3 else 230.0
    sqrt3 = math.sqrt(3) if phases == 3 else 1.0
    ac_amps = (ac_kw * 1000.0) / (voltage * sqrt3) if ac_kw else 0.0
    # Calibre disjoncteur AC : 1.25× le courant nominal, arrondi au calibre std.
    breaker_amp = _round_breaker(ac_amps * 1.25)

    # ── Câble DC (chaînes) ──
    if dc_cable_length_m is None:
        # ~2 conducteurs (+/-) par chaîne, longueur estimée par chaîne.
        dc_cable_length_m = max(10.0, strings * 20.0)
    add("Câblage DC", "Câble solaire DC 6 mm² (PV1-F)",
        round(dc_cable_length_m, 1), "m",
        "1000 V DC, double isolation, résistant UV")

    # ── Câble AC ──
    ac_section = _ac_cable_section(max(ac_amps, 1.0))
    n_cond_ac = 5 if phases == 3 else 3  # 3P+N+T ou P+N+T
    add("Câblage AC",
        f"Câble AC {ac_section:g} mm² ({'triphasé' if phases == 3 else 'monophasé'})",
        round(ac_cable_length_m * n_cond_ac, 1), "m",
        f"{n_cond_ac} conducteurs, U-1000 R2V")

    # ── Protections DC ──
    add("Protection DC", "Parafoudre DC Type 2", 1, "u",
        "1000 V DC, pour string box / entrée onduleur")
    add("Protection DC", "Sectionneur-fusible DC par chaîne", max(strings, 1),
        "u", "porte-fusible + fusible gPV 1000 V DC")
    add("Coffret", "Coffret de chaîne DC (string box)",
        1 if strings <= 2 else 2, "u",
        "IP65, presse-étoupes, embase parafoudre")

    # ── Protections AC ──
    add("Protection AC", f"Disjoncteur AC {breaker_amp} A "
        f"{'tétrapolaire' if phases == 3 else 'bipolaire'}", 1, "u",
        f"courbe C, {voltage:g} V")
    add("Protection AC", "Parafoudre AC Type 2", 1, "u",
        f"{'triphasé' if phases == 3 else 'monophasé'}, In 20 kA")
    add("Coffret", "Coffret de protection AC", 1, "u",
        "IP65, prêt à raccorder au tableau")

    # ── Mise à la terre ──
    add("Mise à la terre", "Piquet de terre + barrette de coupure", 1, "ens",
        "≤ 100 Ω, conforme NF C 15-100")
    add("Mise à la terre", "Câble de terre cuivre nu 25 mm²",
        round(dc_cable_length_m * 0.6 + ac_cable_length_m, 1), "m",
        "liaison équipotentielle structure + masses")

    # ── Structure ──
    add("Structure", "Rail de fixation aluminium", n_panels * 2, "u",
        "rail anodisé, longueur ajustée au module")
    add("Structure", "Pince de fixation (milieu + extrémité)",
        n_panels * 2 + 4, "u", "inox A2, milieu et extrémité")
    add("Structure", "Crochet / patte de fixation toiture",
        max(4, int(math.ceil(n_panels * 0.6))), "u",
        "selon couverture (tuile/bac acier)")

    # ── Batterie (hybride/autonome) ──
    if has_battery or installation_type in ("hybride", "autonome"):
        add("Batterie", "Câble batterie DC 25 mm²", 6.0, "m",
            "section forte courant, cosses serties")
        add("Protection batterie", "Fusible / disjoncteur DC batterie", 1, "u",
            "calibre selon courant batterie")

    if string_result and not string_result.get("ok", True):
        warnings.append(
            "la conception de chaînes signale des avertissements — vérifier la "
            "compatibilité tension avant de figer la nomenclature")

    summary = {
        "kwc": round(kwc, 3),
        "n_panels": n_panels,
        "strings": strings,
        "phases": phases,
        "ac_breaker_amp": breaker_amp,
        "ac_cable_section_mm2": ac_section,
        "n_lignes": len(items),
    }
    return {"items": items, "summary": summary, "warnings": warnings}


# Calibres de disjoncteur AC normalisés (A).
_STD_BREAKERS = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160]


def _round_breaker(amps):
    """Arrondit au calibre normalisé immédiatement supérieur."""
    try:
        amps = float(amps)
    except (TypeError, ValueError):
        amps = 0.0
    for b in _STD_BREAKERS:
        if amps <= b:
            return b
    return _STD_BREAKERS[-1]


# ── FG255 — Dimensionnement borne de recharge VE couplée au PV ───────────────
# Dimensionne une borne de recharge de véhicule électrique (puissance kW, mono
# ou triphasé, nombre de sessions/jour) et chiffre son IMPACT sur
# l'autoconsommation du champ PV : combien de l'énergie VE peut être couverte
# par le surplus solaire journalier, et de combien la borne augmente le taux
# d'autoconsommation global de l'installation. Module PUR : aucune base, aucun
# réseau, aucun prix. Les entrées numériques ne sont JAMAIS rejetées (la liberté
# de saisie du founder est préservée) — seules les valeurs absurdes (≤ 0) sont
# bornées à un défaut sensé pour éviter une division par zéro.

# Bornes monophasées usuelles au Maroc (230 V) et triphasées (400 V).
_EV_VOLTAGE_MONO = 230.0
_EV_VOLTAGE_TRI = 400.0
# Rendement de charge AC→batterie (pertes chargeur embarqué + câble).
_EV_CHARGE_EFFICIENCY = 0.90
# Calibres de borne courants (kW) pour l'aide au choix.
_EV_STD_POWER_KW = [3.7, 7.4, 11.0, 22.0]


def ev_charger_sizing(*, borne_kw=None, phases=None, sessions_per_day=None,
                      energy_per_session_kwh=None, kwh_per_100km=None,
                      km_per_session=None, pv_kwc=None,
                      pv_daily_production_kwh=None,
                      pv_self_consumption_kwh=None,
                      pv_surplus_kwh=None, charge_window_h=None,
                      productible_kwh_kwc_year=None):
    """FG255 — dimensionne une borne VE et chiffre son impact autoconsommation.

    Côté BORNE, à partir de la puissance ``borne_kw``, du nombre de phases
    (``phases`` = 1 mono / 3 tri) et des ``sessions_per_day`` :

    * courant de ligne (A) et calibre disjoncteur dédié (1.25× le nominal,
      arrondi au calibre normalisé) ;
    * énergie VE journalière requise — soit ``energy_per_session_kwh`` fournie,
      soit déduite de la conso véhicule (``kwh_per_100km`` × ``km_per_session``
      / 100) — multipliée par les sessions et divisée par le rendement de
      charge ;
    * durée de charge d'une session à ``borne_kw`` (h) et vérification qu'elle
      tient dans la fenêtre de charge ``charge_window_h`` si fournie.

    Côté PV (IMPACT AUTOCONSOMMATION), si un contexte PV est donné :

    * le SURPLUS solaire journalier (``pv_surplus_kwh`` direct, sinon
      production − autoconsommation existante, sinon déduit de ``pv_kwc`` via
      ``productible_kwh_kwc_year``) est la réserve disponible pour le VE ;
    * la part de l'énergie VE couvrable par ce surplus (``solar_covered_kwh``)
      et donc importée du réseau (``grid_kwh``) ;
    * le NOUVEAU taux d'autoconsommation : (autoconsommation existante + énergie
      VE couverte par le solaire) ÷ production — la borne RECYCLE le surplus
      qui partait au réseau, donc le taux MONTE.

    Toutes les sorties sont JSON-sérialisables et sûres sur entrées dégradées
    (jamais d'exception, division par zéro bornée). Retourne ::

        {borne: {kw, phases, line_current_a, breaker_a, voltage_v,
                 session_charge_h, fits_window, recommended_kw},
         energy: {per_session_kwh, daily_demand_kwh, sessions_per_day},
         pv_impact: {available_surplus_kwh, solar_covered_kwh, grid_kwh,
                     solar_coverage_pct, base_self_consumption_pct,
                     new_self_consumption_pct, self_consumption_gain_pts,
                     pv_daily_production_kwh},
         hypotheses: [...], warnings: []}

    CALX286 — chaque défaut encore appliqué faute de saisie (puissance de
    borne, phases, sessions, consommation véhicule, km par session, rendement
    de charge, tension nominale) est PUBLIÉ dans ``hypotheses`` avec sa
    provenance et les sorties qu'il gouverne — les valeurs rendues sont
    inchangées.
    """
    warnings = []
    hypotheses = []

    # ── Normalisation des entrées (bornage minimal, jamais de rejet) ──
    def _pos(value, default):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return float(default)
        return v if v > 0 else float(default)

    def _pos_ou_hypothese(value, cle, defaut, couvre):
        lu = _taux_ou_none(value)
        if lu is not None and lu > 0:
            return lu
        hypotheses.append(_hypothese(
            cle, defaut, _source_defaut(f"ev_charger_sizing {cle}={defaut}"),
            couvre))
        return float(defaut)

    def _nonneg(value):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        return v if v >= 0 else None

    kw = _pos_ou_hypothese(
        borne_kw, "borne_kw", 7.4,
        ["borne.kw", "borne.line_current_a", "borne.breaker_a",
         "borne.session_charge_h", "borne.recommended_kw"])
    if phases is None:
        hypotheses.append(_hypothese(
            "phases", 1, _source_defaut("ev_charger_sizing phases=1"),
            ["borne.phases", "borne.voltage_v", "borne.line_current_a",
             "borne.breaker_a"]))
    ph = 3 if int(phases or 1) == 3 else 1
    sessions = _pos_ou_hypothese(
        sessions_per_day, "sessions_per_day", 1,
        ["energy.sessions_per_day", "energy.daily_demand_kwh"])

    # ── Énergie d'une session ──
    if energy_per_session_kwh is not None:
        per_session = _pos(energy_per_session_kwh, 0.0)
        if per_session <= 0:
            per_session = 0.0
    else:
        # Déduite de la conso véhicule × km par session.
        couvre_session = ["energy.per_session_kwh", "energy.daily_demand_kwh",
                          "borne.session_charge_h"]
        kwh_100 = _pos_ou_hypothese(kwh_per_100km, "kwh_per_100km", 18.0,
                                    couvre_session)
        km = _pos_ou_hypothese(km_per_session, "km_per_session", 40.0,
                               couvre_session)
        per_session = kwh_100 * km / 100.0
    # Deux constantes toujours appliquées : le rendement de charge (non
    # sourcé) et la tension nominale BT normalisée (sourcée).
    hypotheses.append(_hypothese(
        "charge_efficiency", _EV_CHARGE_EFFICIENCY,
        _source_defaut("_EV_CHARGE_EFFICIENCY"),
        ["energy.charge_efficiency", "energy.daily_demand_kwh",
         "borne.session_charge_h"]))
    hypotheses.append(_hypothese(
        "voltage_v", {"mono": _EV_VOLTAGE_MONO, "tri": _EV_VOLTAGE_TRI},
        "tension nominale basse tension normalisée 230 V / 400 V "
        "(CEI 60038)",
        ["borne.voltage_v", "borne.line_current_a", "borne.breaker_a"]))

    # Énergie à PRÉLEVER au tableau (pertes de charge incluses).
    daily_demand = round(
        per_session * sessions / _EV_CHARGE_EFFICIENCY, 2)

    # ── Électricité borne : courant de ligne & calibre ──
    voltage = _EV_VOLTAGE_TRI if ph == 3 else _EV_VOLTAGE_MONO
    sqrt3 = math.sqrt(3) if ph == 3 else 1.0
    line_current = (kw * 1000.0) / (voltage * sqrt3)
    breaker_a = _round_breaker(line_current * 1.25)

    # Durée d'une session à la puissance borne (pertes incluses).
    session_charge_h = round(
        (per_session / _EV_CHARGE_EFFICIENCY) / kw, 2) if kw > 0 else None

    fits_window = None
    win = _nonneg(charge_window_h)
    if win is not None and session_charge_h is not None:
        fits_window = session_charge_h <= win
        if not fits_window:
            warnings.append(
                f"charge d'une session {session_charge_h} h > fenêtre "
                f"disponible {win} h — augmenter la puissance de borne ou "
                "réduire l'énergie par session")

    # Borne recommandée : la plus petite puissance standard ≥ celle saisie.
    recommended_kw = next((p for p in _EV_STD_POWER_KW if p >= kw - 1e-6), kw)

    # ── Impact PV / autoconsommation ──
    prod = _nonneg(pv_daily_production_kwh)
    if prod is None:
        kwc = _nonneg(pv_kwc)
        if kwc is not None and kwc > 0:
            # QJR146 (h) — AUCUN PRODUCTIBLE ARME ICI (cf. jumelle).
            _prodctbl = _pos(productible_kwh_kwc_year, 0.0)
            if _prodctbl > 0:
                prod = round(kwc * _prodctbl / 365.0, 2)

    surplus = _nonneg(pv_surplus_kwh)
    base_self = _nonneg(pv_self_consumption_kwh)
    if surplus is None and prod is not None and base_self is not None:
        surplus = max(0.0, round(prod - base_self, 2))

    pv_impact = {
        "pv_daily_production_kwh": prod,
        "available_surplus_kwh": surplus,
        "solar_covered_kwh": None,
        "grid_kwh": None,
        "solar_coverage_pct": None,
        "base_self_consumption_pct": None,
        "new_self_consumption_pct": None,
        "self_consumption_gain_pts": None,
    }

    if surplus is not None and daily_demand > 0:
        # Le VE consomme d'abord le surplus solaire, le reste vient du réseau.
        solar_covered = round(min(surplus, daily_demand), 2)
        grid_kwh = round(max(0.0, daily_demand - solar_covered), 2)
        pv_impact["solar_covered_kwh"] = solar_covered
        pv_impact["grid_kwh"] = grid_kwh
        pv_impact["solar_coverage_pct"] = round(
            solar_covered / daily_demand * 100.0, 1)
        if solar_covered < daily_demand * 0.5:
            warnings.append(
                "le surplus solaire couvre moins de la moitié des besoins VE — "
                "envisager d'agrandir le champ PV ou de programmer la charge en "
                "milieu de journée")

        # Nouveau taux d'autoconsommation : la borne recycle le surplus.
        if prod is not None and prod > 0:
            base_sc = base_self if base_self is not None else max(
                0.0, prod - surplus)
            pv_impact["base_self_consumption_pct"] = round(
                base_sc / prod * 100.0, 1)
            new_sc = base_sc + solar_covered
            pv_impact["new_self_consumption_pct"] = round(
                min(new_sc, prod) / prod * 100.0, 1)
            pv_impact["self_consumption_gain_pts"] = round(
                pv_impact["new_self_consumption_pct"]
                - pv_impact["base_self_consumption_pct"], 1)

    return {
        "borne": {
            "kw": round(kw, 2),
            "phases": ph,
            "voltage_v": voltage,
            "line_current_a": round(line_current, 1),
            "breaker_a": breaker_a,
            "session_charge_h": session_charge_h,
            "fits_window": fits_window,
            "recommended_kw": recommended_kw,
        },
        "energy": {
            "per_session_kwh": round(per_session, 2),
            "daily_demand_kwh": daily_demand,
            "sessions_per_day": round(sessions, 2),
            "charge_efficiency": _EV_CHARGE_EFFICIENCY,
        },
        "pv_impact": pv_impact,
        "hypotheses": hypotheses,
        "warnings": warnings,
    }


# ── FG256 — Étude de stockage & dispatch batterie (backup) ───────────────────
# Dimensionne le parc batterie d'une installation PV pour DEUX objectifs
# distincts, puis désigne la contrainte DIMENSIONNANTE (binding) :
#
#   (a) AUTOCONSOMMATION MAX — stocker le SURPLUS solaire de la journée pour le
#       restituer le soir/la nuit. La capacité utile vise à absorber le surplus
#       journalier (production − autoconsommation directe), elle-même bornée par
#       l'énergie réellement déchargée la nuit (besoin du soir). La puissance
#       utile suit le pic de décharge nocturne.
#   (b) BACKUP N heures critiques — tenir une charge critique (kW) pendant un
#       nombre d'heures de coupure. La capacité utile = charge critique × heures,
#       la puissance utile = charge critique (avec une marge de pointe).
#
# On part toujours de la capacité UTILE (kWh utilisables) puis on remonte à la
# capacité NOMINALE installée en divisant par la profondeur de décharge (DoD) et
# le rendement aller-retour (round-trip) — deux pertes physiques bien réelles.
# Module PUR : aucune base, aucun réseau, aucun prix. Les entrées numériques ne
# sont JAMAIS rejetées (liberté de saisie du founder) — seules les valeurs
# absurdes (≤ 0) sont bornées à un défaut sensé pour éviter une division par
# zéro.

# CALX286 — les quatre constantes ci-dessous NE sont PLUS des défauts de
# ``battery_storage_sizing`` (grandeurs omises sans saisie). Elles restent
# définies parce que ``apps/calepinage/services/batterie.py`` relit DoD et
# rendement comme « hypothèses de référence » ÉTIQUETÉES (source publiée).
# Profondeur de décharge utilisable par défaut (lithium LFP courant : 90 %).
_BATTERY_DEFAULT_DOD = 0.90
# Rendement aller-retour (charge → décharge) d'un parc lithium + onduleur.
_BATTERY_DEFAULT_ROUND_TRIP = 0.90
# Facteur de pointe pour la puissance backup (démarrages moteurs, appels).
_BATTERY_BACKUP_PEAK_FACTOR = 1.25
# Fraction du surplus journalier réellement restituée le soir si le besoin
# nocturne n'est pas précisé (le reste serait réinjecté/perdu).
_BATTERY_DEFAULT_NIGHT_FRACTION = 0.80


def battery_storage_sizing(*, mode="autoconso",
                           pv_daily_production_kwh=None,
                           pv_self_consumption_kwh=None,
                           daily_surplus_kwh=None,
                           night_load_kwh=None,
                           pv_kwc=None,
                           productible_kwh_kwc_year=None,
                           critical_load_kw=None,
                           backup_hours=None,
                           evening_peak_kw=None,
                           depth_of_discharge=None,
                           round_trip_efficiency=None,
                           system_voltage_v=None,
                           backup_peak_factor=None):
    """FG256 — capacité (kWh) et puissance (kW) batterie utiles + nominales.

    Calcule le dimensionnement pour le ou les objectifs demandés et désigne la
    contrainte DIMENSIONNANTE (``binding_objective``).

    Modes (``mode``) :

    * ``"autoconso"`` — autoconsommation max : stocker le surplus journalier.
    * ``"backup"`` — autonomie : tenir la charge critique N heures.
    * ``"both"`` — calcule les deux ; la capacité retenue est la PLUS GRANDE et
      ``binding_objective`` indique laquelle dimensionne le parc.

    AUTOCONSOMMATION : le surplus journalier (``daily_surplus_kwh`` direct,
    sinon production − autoconsommation directe, sinon déduit de ``pv_kwc`` via
    ``productible_kwh_kwc_year``) est l'énergie EXCÉDENTAIRE de la journée. La
    capacité UTILE visée est ``min(surplus, besoin nocturne)`` : inutile de
    stocker plus que ce qui sera redéchargé le soir (``night_load_kwh`` ; à
    défaut une fraction du surplus). La puissance UTILE suit le pic de décharge
    nocturne (``evening_peak_kw`` si fourni, sinon estimée du besoin nocturne).

    BACKUP : capacité UTILE = ``critical_load_kw`` × ``backup_hours`` ; puissance
    UTILE = ``critical_load_kw`` × marge de pointe (``_BATTERY_BACKUP_PEAK_FACTOR``).

    De l'UTILE au NOMINAL : la capacité nominale installée =
    capacité utile ÷ (DoD × √rendement_round_trip) — la profondeur de décharge
    limite la fraction exploitable et le rendement aller-retour ajoute des pertes
    de stockage. Le courant batterie indicatif = puissance utile ÷ tension
    système.

    Toutes les sorties sont JSON-sérialisables et sûres sur entrées dégradées
    (jamais d'exception, division par zéro bornée). Retourne ::

        {mode, autoconso: {usable_kwh, usable_kw, nominal_kwh, ...} | None,
         backup: {usable_kwh, usable_kw, nominal_kwh, ...} | None,
         recommended: {usable_kwh, usable_kw, nominal_kwh, current_a},
         binding_objective, depth_of_discharge, round_trip_efficiency,
         omissions: [...], hypotheses: [...], warnings: []}

    CALX286 — AUCUN défaut batterie n'est plus appliqué d'office :
    ``depth_of_discharge`` / ``round_trip_efficiency`` absents ⇒ capacités
    NOMINALES ``None`` ; ``night_load_kwh`` absent ⇒ capacité utile
    d'autoconsommation ``None`` (plus de « 80 % du surplus ») ;
    ``backup_peak_factor`` absent ⇒ puissance utile de secours ``None`` —
    chaque fois avec une entrée ``omissions``. Les constantes
    ``_BATTERY_DEFAULT_*`` restent définies : ``apps/calepinage/services/
    batterie.py`` les relit comme HYPOTHÈSES DE RÉFÉRENCE étiquetées.
    """
    warnings = []
    omissions = []
    hypotheses = []

    def _pos(value, default):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return float(default)
        return v if v > 0 else float(default)

    def _pos_ou_none(value):
        v = _taux_ou_none(value)
        return v if v is not None and v > 0 else None

    def _nonneg(value):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        return v if v >= 0 else None

    # DoD et rendement bornés à ]0, 1] (jamais une division par zéro) —
    # SAISIS, sinon omis (CALX286).
    dod = _pos_ou_none(depth_of_discharge)
    if dod is None:
        omissions.append(_omission(
            "depth_of_discharge",
            "omis : profondeur de décharge non fournie (depth_of_discharge) — "
            "à lire sur la fiche de la batterie",
            ["depth_of_discharge", "autoconso.nominal_kwh",
             "backup.nominal_kwh", "recommended.nominal_kwh"]))
    elif dod > 1.0:
        dod = 1.0
        warnings.append("profondeur de décharge plafonnée à 100 %")
    rte = _pos_ou_none(round_trip_efficiency)
    if rte is None:
        omissions.append(_omission(
            "round_trip_efficiency",
            "omis : rendement aller-retour non fourni (round_trip_efficiency) "
            "— à lire sur la fiche de la batterie",
            ["round_trip_efficiency", "autoconso.nominal_kwh",
             "backup.nominal_kwh", "recommended.nominal_kwh"]))
    elif rte > 1.0:
        rte = 1.0
        warnings.append("rendement aller-retour plafonné à 100 %")
    voltage = _pos_ou_none(system_voltage_v)
    if voltage is None:
        voltage = 48.0
        hypotheses.append(_hypothese(
            "system_voltage_v", 48.0,
            _source_defaut("system_voltage_v=48.0"),
            ["system_voltage_v", "recommended.current_a"]))
    peak_factor = _pos_ou_none(backup_peak_factor)

    mode = (mode or "autoconso").lower()
    want_autoconso = mode in ("autoconso", "both")
    want_backup = mode in ("backup", "both")
    if mode not in ("autoconso", "backup", "both"):
        want_autoconso = True
        warnings.append(
            f"mode « {mode} » inconnu — autoconsommation par défaut")

    def _usable_to_nominal(usable_kwh):
        # Capacité nominale = utile / (DoD × √rendement aller-retour). Le √
        # répartit la perte round-trip entre charge et décharge (modèle simple).
        if dod is None or rte is None or usable_kwh is None:
            return None
        denom = dod * math.sqrt(rte)
        return round(usable_kwh / denom, 2) if denom > 0 else None

    # ── (a) AUTOCONSOMMATION MAX ──────────────────────────────────────────────
    autoconso = None
    if want_autoconso:
        prod = _nonneg(pv_daily_production_kwh)
        if prod is None:
            kwc = _nonneg(pv_kwc)
            if kwc is not None and kwc > 0:
                # QJR146 (h) — AUCUN PRODUCTIBLE ARME ICI. Le forfait
                # 1700 kWh/kWc/an etait applique en silence des qu'un
                # appelant donnait un kWc sans productible : une production
                # journaliere INVENTEE, dans une fonction qu'aucun appelant
                # de production n'utilise (donc jamais confrontee au reel).
                # Sans productible fourni, la production reste inconnue.
                _prodctbl = _pos(productible_kwh_kwc_year, 0.0)
                if _prodctbl > 0:
                    prod = round(kwc * _prodctbl / 365.0, 2)

        surplus = _nonneg(daily_surplus_kwh)
        base_self = _nonneg(pv_self_consumption_kwh)
        if surplus is None and prod is not None and base_self is not None:
            surplus = max(0.0, round(prod - base_self, 2))

        if surplus is None:
            autoconso = {
                "usable_kwh": None, "usable_kw": None, "nominal_kwh": None,
                "daily_surplus_kwh": None, "night_load_kwh": _nonneg(night_load_kwh),
                "stored_kwh": None, "spilled_surplus_kwh": None,
                "pv_daily_production_kwh": prod,
            }
            warnings.append(
                "autoconsommation : surplus solaire inconnu — fournir production "
                "+ autoconsommation, surplus direct, ou kWc")
        elif _nonneg(night_load_kwh) is None:
            # CALX286 — plus de « 80 % du surplus » supposés : sans besoin
            # nocturne fourni, la capacité utile n'est pas publiée.
            omissions.append(_omission(
                "night_load_kwh",
                "omis : besoin nocturne non fourni (night_load_kwh) — la part "
                "du surplus restituée le soir n'est pas supposée",
                ["autoconso.usable_kwh", "autoconso.usable_kw",
                 "autoconso.nominal_kwh", "autoconso.stored_kwh",
                 "autoconso.spilled_surplus_kwh", "recommended"]))
            autoconso = {
                "usable_kwh": None, "usable_kw": None, "nominal_kwh": None,
                "daily_surplus_kwh": round(surplus, 2), "night_load_kwh": None,
                "stored_kwh": None, "spilled_surplus_kwh": None,
                "pv_daily_production_kwh": prod,
            }
        else:
            # Énergie redéchargée le soir : le besoin nocturne FOURNI.
            night = _nonneg(night_load_kwh)
            # On ne stocke pas plus que ce qui sera redéchargé (ni que le surplus).
            usable_kwh = round(min(surplus, night), 2)
            spilled = round(max(0.0, surplus - usable_kwh), 2)
            # Pic de décharge nocturne : fourni, sinon ~le besoin réparti sur une
            # soirée de pointe de 4 h (modèle simple, publié comme hypothèse).
            peak = _nonneg(evening_peak_kw)
            if peak is None or peak <= 0:
                peak = round(usable_kwh / 4.0, 2) if usable_kwh > 0 else 0.0
                hypotheses.append(_hypothese(
                    "evening_peak_kw", "besoin nocturne réparti sur 4 h",
                    _source_defaut("pic du soir = besoin ÷ 4 h"),
                    ["autoconso.usable_kw", "recommended.usable_kw",
                     "recommended.current_a"]))
            autoconso = {
                "usable_kwh": usable_kwh,
                "usable_kw": round(peak, 2),
                "nominal_kwh": _usable_to_nominal(usable_kwh),
                "daily_surplus_kwh": round(surplus, 2),
                "night_load_kwh": round(night, 2),
                "stored_kwh": usable_kwh,
                "spilled_surplus_kwh": spilled,
                "pv_daily_production_kwh": prod,
            }
            if spilled > 0:
                warnings.append(
                    "autoconsommation : une partie du surplus dépasse le besoin "
                    "nocturne et ne sera pas stockée (réinjection/écrêtage)")

    # ── (b) BACKUP N heures critiques ─────────────────────────────────────────
    backup = None
    if want_backup:
        crit_kw = _nonneg(critical_load_kw)
        hours = _nonneg(backup_hours)
        if crit_kw is None or hours is None:
            backup = {
                "usable_kwh": None, "usable_kw": None, "nominal_kwh": None,
                "critical_load_kw": crit_kw, "backup_hours": hours,
            }
            warnings.append(
                "backup : charge critique (kW) et heures d'autonomie requises")
        else:
            usable_kwh = round(crit_kw * hours, 2)
            # Puissance utile = charge critique avec marge de pointe (appels
            # moteurs, démarrages) — l'onduleur batterie doit la soutenir.
            # CALX286 — la marge est SAISIE (``backup_peak_factor``), sinon
            # la puissance utile est omise (plus de 1,25 supposé).
            if peak_factor is None:
                usable_kw = None
                omissions.append(_omission(
                    "backup_peak_factor",
                    "omis : marge de pointe de secours non fournie "
                    "(backup_peak_factor) — la puissance utile de secours en "
                    "dépend",
                    ["backup.usable_kw", "recommended.usable_kw",
                     "recommended.current_a"]))
            else:
                usable_kw = round(crit_kw * peak_factor, 2)
            backup = {
                "usable_kwh": usable_kwh,
                "usable_kw": usable_kw,
                "nominal_kwh": _usable_to_nominal(usable_kwh),
                "critical_load_kw": round(crit_kw, 2),
                "backup_hours": round(hours, 2),
                "peak_factor": peak_factor,
            }
            if usable_kwh <= 0:
                warnings.append(
                    "backup : énergie d'autonomie nulle (charge ou heures à 0)")

    # ── Contrainte dimensionnante (binding) ───────────────────────────────────
    candidates = []
    if autoconso and autoconso.get("usable_kwh") is not None:
        candidates.append(("autoconso", autoconso))
    if backup and backup.get("usable_kwh") is not None:
        candidates.append(("backup", backup))

    binding = None
    recommended = {
        "usable_kwh": None, "usable_kw": None,
        "nominal_kwh": None, "current_a": None,
    }
    if candidates:
        # La contrainte dimensionnante est celle qui exige la plus grande
        # capacité utile ; la puissance retenue est le max des deux pics.
        binding, chosen = max(
            candidates, key=lambda c: c[1].get("usable_kwh") or 0.0)
        usable_kwh = chosen.get("usable_kwh") or 0.0
        # CALX286 — une puissance utile omise (marge de secours non saisie)
        # rend la puissance retenue inconnue : jamais un max qui l'ignore.
        if any(c[1].get("usable_kw") is None for c in candidates):
            usable_kw = None
            current_a = None
        else:
            usable_kw = max(c[1]["usable_kw"] for c in candidates)
            current_a = round(usable_kw * 1000.0 / voltage, 1) \
                if voltage > 0 and usable_kw else 0.0
        nominal_kwh = _usable_to_nominal(usable_kwh)
        recommended = {
            "usable_kwh": round(usable_kwh, 2),
            "usable_kw": None if usable_kw is None else round(usable_kw, 2),
            "nominal_kwh": nominal_kwh,
            "current_a": current_a,
        }

    return {
        "mode": mode,
        "autoconso": autoconso,
        "backup": backup,
        "recommended": recommended,
        "binding_objective": binding,
        "depth_of_discharge": None if dod is None else round(dod, 4),
        "round_trip_efficiency": None if rte is None else round(rte, 4),
        "system_voltage_v": round(voltage, 1),
        "omissions": omissions,
        "hypotheses": hypotheses,
        "warnings": warnings,
    }


# ── FG257 — Simulation bankable P50/P90 avec modèle de pertes ─────────────────
# Transforme une production de BASE (le productible « brut », p. ex. PVGIS au
# point de fonctionnement idéal × kWc) en une production FINANCIÈREMENT EXPLOITABLE
# (« bankable ») en deux temps :
#
#   1) MODÈLE DE PERTES → RATIO DE PERFORMANCE (PR). Chaque source de perte
#      physique (température, salissure/poussière, câblage DC+AC, rendement
#      onduleur, et des pertes diverses : mismatch, ombrage déjà chiffré ailleurs,
#      indisponibilité) ronge une fraction de l'énergie. Le PR est le produit des
#      rendements de chaque poste : PR = Π (1 − perte_i). La production P50 (valeur
#      médiane attendue, « 1 année sur 2 on fait au moins ça ») = base × PR.
#
#   2) VARIABILITÉ INTERANNUELLE → P90 / P75. L'ensoleillement varie d'une année
#      à l'autre (météo) ; on modélise la production annuelle comme une gaussienne
#      de moyenne P50 et d'écart-type relatif σ (typiquement 5–7 %). Les banques
#      financent sur le P90 : la production DÉPASSÉE 9 années sur 10. Avec le
#      quantile gaussien z₉₀ = 1.282, P90 = P50 × (1 − z₉₀·σ) ; de même
#      P75 = P50 × (1 − z₇₅·σ) avec z₇₅ = 0.674.
#
# Module PUR : aucune base, aucun réseau, aucun prix. Les entrées numériques ne
# sont JAMAIS rejetées (liberté de saisie du founder) — seuls les facteurs de
# perte sont bornés à [0, 1] (une perte hors de cet intervalle n'a pas de sens
# physique) et σ est borné ≥ 0 pour éviter un P90 > P50.

# Postes de perte par défaut (fractions), valeurs marché conservatrices pour une
# centrale PV au Maroc bien conçue. Tout est surchargeable par l'appelant.
# CALX286 — ``simulate_bankable_yield`` NE les applique PLUS d'office (PR omis
# sans arbre fourni). Ils restent la PONDÉRATION RELATIVE que
# ``apps/ventes/etude.py::loss_factors_canoniques`` cale sur les 20 % du
# fondateur avant de les passer explicitement (D12).
DEFAULT_LOSS_FACTORS = {
    "temperature": 0.08,   # échauffement cellule au-dessus du STC (climat chaud)
    "soiling": 0.03,       # salissure / poussière (Maroc : sable, à nettoyer)
    "wiring": 0.02,        # pertes ohmiques câblage DC + AC
    "inverter": 0.025,     # rendement de conversion onduleur (≈ 97.5 %)
    "mismatch": 0.02,      # dispersion modules + connectique + LID/dégradation 1re année
    "availability": 0.01,  # indisponibilité réseau / maintenance
}

# Quantiles de la loi normale centrée réduite (borne basse) :
#   P90 = production dépassée 90 % du temps → z tel que Φ(−z) = 10 % → z = 1.282.
#   P75 = production dépassée 75 % du temps → Φ(−z) = 25 % → z = 0.674.
Z_P90 = 1.282
Z_P75 = 0.674

# Écart-type relatif interannuel par défaut (variabilité météo), typiquement 5–7 %.
DEFAULT_ANNUAL_VARIABILITY = 0.06


def _clamp01(value, default):
    """Borne un facteur de perte à [0, 1]. Entrée illisible → ``default``."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def simulate_bankable_yield(base_production_kwh, *, loss_factors=None,
                            annual_variability=None,
                            kwc=None, include_p75=True):
    """FG257 — simulation bankable P50/P90 (+P75) avec modèle de pertes & PR.

    Calcule un RATIO DE PERFORMANCE (PR) à partir des postes de perte, l'applique
    à une production de base pour obtenir le P50 (médiane), puis dérive le P90
    (et optionnellement le P75) via le quantile gaussien d'une variabilité
    interannuelle ``annual_variability`` (σ relatif).

    Paramètres
    ----------
    base_production_kwh : production de base AVANT pertes (kWh/an) — typiquement
        le productible idéal (PVGIS au point de fonctionnement) × kWc. Une valeur
        ≤ 0 ou illisible → 0 (toutes les sorties à 0, jamais d'exception).
    loss_factors : dict ``{poste: fraction}`` surchargeant ``DEFAULT_LOSS_FACTORS``
        (température, soiling/salissure, wiring/câblage, inverter/onduleur, …).
        Chaque facteur est borné à [0, 1] ; les postes inconnus sont acceptés et
        comptés (extensibilité). Le PR = produit des (1 − perte_i).
    annual_variability : écart-type relatif σ de la production annuelle (météo),
        typiquement 0.05–0.07. Borné ≥ 0 (un σ négatif est ramené à 0 → P90=P50).
    kwc : puissance crête (kWc) facultative, pour rapporter un ``specific_yield``
        (kWh/kWc/an) au P50 — purement indicatif, jamais de prix.
    include_p75 : ajoute le P75 (médiane des banques moins conservatrices).

    Retourne un dict JSON-sérialisable ::

        {base_production_kwh, performance_ratio, total_loss_pct,
         loss_breakdown: {poste: {fraction, pct}}, applied_losses,
         p50_kwh, p90_kwh, p75_kwh|None, annual_variability,
         z_p90, z_p75, specific_yield_kwh_kwc|None, warnings: []}

    Ne lève jamais : entrées dégradées → structure cohérente à 0.

    CALX286 — ``loss_factors`` N'EST PLUS complété par ``DEFAULT_LOSS_FACTORS``
    (valeurs « marché » non sourcées) : absent ⇒ PR, P50, P90, P75 et
    productible spécifique ``None`` avec une entrée ``omissions`` ; fourni ⇒ il
    EST l'arbre de pertes de l'appelant, poste pour poste (un poste illisible
    est omis en le nommant, et le PR avec lui). ``annual_variability`` absente
    ⇒ ``DEFAULT_ANNUAL_VARIABILITY`` publiée dans ``hypotheses`` avec sa
    provenance (CALX285 la remplacera par une variabilité d'origine publiée).
    """
    warnings = []
    omissions = []
    hypotheses = []

    try:
        base = float(base_production_kwh)
    except (TypeError, ValueError):
        base = 0.0
    if base < 0.0:
        base = 0.0
        warnings.append("production de base négative ramenée à 0")

    # ── PR = produit des rendements (1 − perte) de chaque poste ──
    loss_breakdown = {}
    pr = 1.0
    if not loss_factors:
        pr = None
        omissions.append(_omission(
            "loss_factors",
            "omis : arbre de pertes non fourni (loss_factors) — aucun poste "
            "« marché » n'est supposé",
            ["performance_ratio", "total_loss_pct", "p50_kwh", "p90_kwh",
             "p75_kwh", "specific_yield_kwh_kwc", "loss_breakdown"]))
    else:
        for poste, raw in dict(loss_factors).items():
            if _taux_ou_none(raw) is None:
                pr = None
                omissions.append(_omission(
                    f"loss_factors.{poste}",
                    f"omis : perte « {poste} » illisible "
                    f"(loss_factors.{poste})",
                    ["performance_ratio", "total_loss_pct", "p50_kwh",
                     "p90_kwh", "p75_kwh", "specific_yield_kwh_kwc"]))
                continue
            frac = _clamp01(raw, 0.0)
            loss_breakdown[poste] = {
                "fraction": round(frac, 4),
                "pct": round(frac * 100.0, 2),
            }
            if pr is not None:
                pr *= (1.0 - frac)

    performance_ratio = None if pr is None else round(pr, 4)
    total_loss_pct = None if pr is None else round((1.0 - pr) * 100.0, 2)
    if performance_ratio is not None and performance_ratio < 0.70 \
            and loss_breakdown:
        warnings.append(
            "ratio de performance < 0.70 — pertes cumulées élevées, vérifier les "
            "postes (température/salissure/câblage/onduleur)")

    # ── P50 = base × PR (production médiane attendue) ──
    p50 = None if pr is None else round(base * pr, 1)

    # ── Variabilité interannuelle → P90 / P75 (quantile gaussien borne basse) ──
    sigma = _taux_ou_none(annual_variability)
    if sigma is None:
        sigma = DEFAULT_ANNUAL_VARIABILITY
        hypotheses.append(_hypothese(
            "annual_variability", DEFAULT_ANNUAL_VARIABILITY,
            _source_defaut("DEFAULT_ANNUAL_VARIABILITY"),
            ["annual_variability", "p90_kwh", "p75_kwh"]))
    if sigma < 0.0:
        sigma = 0.0
        warnings.append("variabilité interannuelle négative ramenée à 0")
    if sigma > 0.30:
        warnings.append(
            "variabilité interannuelle > 30 % — valeur inhabituelle, vérifier σ")

    # P90/P75 = P50 × (1 − z·σ), borné ≥ 0 (un σ énorme ne donne pas un négatif).
    p90 = None if p50 is None else round(
        p50 * max(0.0, 1.0 - Z_P90 * sigma), 1)
    p75 = (round(p50 * max(0.0, 1.0 - Z_P75 * sigma), 1)
           if include_p75 and p50 is not None else None)

    specific_yield = None
    try:
        k = float(kwc) if kwc is not None else None
    except (TypeError, ValueError):
        k = None
    if k is not None and k > 0 and p50 is not None:
        specific_yield = round(p50 / k, 1)

    return {
        "base_production_kwh": round(base, 1),
        "performance_ratio": performance_ratio,
        "total_loss_pct": total_loss_pct,
        "loss_breakdown": loss_breakdown,
        "applied_losses": sorted(loss_breakdown.keys()),
        "p50_kwh": p50,
        "p90_kwh": p90,
        "p75_kwh": p75,
        "annual_variability": round(sigma, 4),
        "z_p90": Z_P90,
        "z_p75": Z_P75,
        "specific_yield_kwh_kwc": specific_yield,
        "omissions": omissions,
        "hypotheses": hypotheses + [_hypothese(
            "z_quantiles", {"z_p90": Z_P90, "z_p75": Z_P75},
            "quantiles de la loi normale centrée réduite, Φ⁻¹(0,90) et "
            "Φ⁻¹(0,75) — constantes mathématiques de la méthode",
            ["z_p90", "z_p75"])],
        "warnings": warnings,
    }


# ── FG258 — Profil d'autoconsommation horaire depuis la courbe de charge ──────
# Croise une COURBE DE CHARGE horaire (consommation, kWh par heure) avec un
# PROFIL DE PRODUCTION horaire (PV, kWh par heure) pour calculer le taux
# d'autoconsommation RÉEL — heure par heure, l'autoconsommé instantané vaut
# min(charge, production) (on ne peut pas autoconsommer plus que ce que l'on
# produit NI plus que ce que l'on consomme à cet instant). Le surplus
# (production − autoconsommé) part au réseau ; le complément (charge −
# autoconsommé) est importé.
#
#   taux d'autoconsommation = Σ autoconsommé / Σ production
#       → quelle part de MA production je consomme moi-même (le reste injecté).
#   taux de couverture (autoproduction) = Σ autoconsommé / Σ charge
#       → quelle part de MA consommation est couverte par le solaire.
#
# Le calcul est PUR (aucune base, aucun réseau, aucun prix) et tolère des
# courbes de longueurs différentes (on aligne sur la plus courte, en signalant).
# Un profil annuel 8760 h fonctionne exactement comme un profil type 24 h : la
# routine ne suppose AUCUNE longueur particulière. La liberté de saisie est
# préservée : aucune valeur n'est rejetée — les valeurs illisibles ou négatives
# sont ramenées à 0 (une charge/production négative n'a pas de sens physique),
# jamais d'exception, division par zéro bornée (Σproduction = 0 → taux = 0).
#
# Le PARSING d'un classeur .xlsx (openpyxl, déjà une dépendance du projet) est
# tenu SÉPARÉ du calcul : ``load_curve_from_xlsx`` lit une colonne en liste de
# floats, puis on passe cette liste à ``hourly_self_consumption``. Aucune
# dépendance pip nouvelle n'est introduite.

# ── Profils horaires types (24 valeurs, part de la grandeur journalière) ──────
# Profil de CHARGE résidentiel marocain type : creux la nuit, pics matin & soir
# (cuisine, éclairage, clim/TV en soirée). Somme = 1.0 (fractions de la conso
# journalière). Index 0 = 00 h … 23 = 23 h.
TYPICAL_LOAD_PROFILE_RESIDENTIAL = [
    0.020, 0.018, 0.016, 0.016, 0.018, 0.025,  # 00–05 h
    0.040, 0.055, 0.050, 0.040, 0.035, 0.035,  # 06–11 h
    0.038, 0.035, 0.030, 0.030, 0.035, 0.050,  # 12–17 h
    0.075, 0.090, 0.085, 0.065, 0.045, 0.029,  # 18–23 h
]

# Profil de CHARGE tertiaire / commerce (journée ouvrée) : plat la nuit, plateau
# diurne aligné sur le soleil — beaucoup plus favorable à l'autoconsommation.
TYPICAL_LOAD_PROFILE_COMMERCIAL = [
    0.010, 0.010, 0.010, 0.010, 0.010, 0.015,  # 00–05 h
    0.030, 0.055, 0.075, 0.085, 0.090, 0.085,  # 06–11 h
    0.075, 0.085, 0.090, 0.085, 0.070, 0.045,  # 12–17 h
    0.025, 0.015, 0.010, 0.010, 0.010, 0.010,  # 18–23 h
]

# Profil de PRODUCTION PV type (jour clair) : cloche centrée sur midi solaire,
# nulle la nuit. Somme = 1.0 (fractions de la production journalière).
TYPICAL_PV_PROFILE = [
    0.0, 0.0, 0.0, 0.0, 0.0, 0.005,            # 00–05 h
    0.020, 0.045, 0.075, 0.100, 0.120, 0.130,  # 06–11 h
    0.130, 0.120, 0.100, 0.075, 0.045, 0.020,  # 12–17 h
    0.010, 0.005, 0.0, 0.0, 0.0, 0.0,          # 18–23 h
]

_TYPICAL_LOAD_PROFILES = {
    "residential": TYPICAL_LOAD_PROFILE_RESIDENTIAL,
    "residentiel": TYPICAL_LOAD_PROFILE_RESIDENTIAL,
    "commercial": TYPICAL_LOAD_PROFILE_COMMERCIAL,
    "tertiaire": TYPICAL_LOAD_PROFILE_COMMERCIAL,
}


def _scaled_typical_load(total_kwh, profile_key="residential"):
    """Distribue ``total_kwh`` sur 24 h selon un profil type (somme→total)."""
    try:
        total = float(total_kwh)
    except (TypeError, ValueError):
        total = 0.0
    if total < 0.0:
        total = 0.0
    profile = _TYPICAL_LOAD_PROFILES.get(
        (profile_key or "residential").lower(),
        TYPICAL_LOAD_PROFILE_RESIDENTIAL)
    # QJR146 (h) — RIEN DE CONNU ⇒ LISTE VIDE, jamais 24 zéros. Une série de
    # 24 zéros est INDISTINGUABLE d'une journée réellement mesurée à zéro :
    # elle donnait à ``hourly_self_consumption`` une longueur de 24 h qui
    # TRONQUAIT une production de 288 points, et faisait publier « hours: 24 »
    # sur un calcul qui n'avait aucune donnée d'entrée.
    if total <= 0.0:
        return []
    s = sum(profile)
    if s <= 0:
        return []
    return [total * (p / s) for p in profile]


def _scaled_typical_pv(total_kwh):
    """Distribue ``total_kwh`` de production sur 24 h selon ``TYPICAL_PV_PROFILE``."""
    try:
        total = float(total_kwh)
    except (TypeError, ValueError):
        total = 0.0
    if total < 0.0:
        total = 0.0
    # QJR146 (h) — même règle que la jumelle ci-dessus : rien de connu ⇒ [].
    if total <= 0.0:
        return []
    s = sum(TYPICAL_PV_PROFILE)
    if s <= 0:
        return []
    return [total * (p / s) for p in TYPICAL_PV_PROFILE]


def hourly_self_consumption(load_curve=None, production_curve=None, *,
                            daily_load_kwh=None, daily_production_kwh=None,
                            load_profile="residential"):
    """FG258 — taux d'autoconsommation RÉEL depuis courbes horaires.

    Aligne heure par heure une COURBE DE CHARGE (consommation, kWh/h) et un
    PROFIL DE PRODUCTION (PV, kWh/h). Pour chaque heure :

        autoconsommé[h] = min(charge[h], production[h])
        surplus_injecté[h] = production[h] − autoconsommé[h]
        importé_réseau[h] = charge[h] − autoconsommé[h]

    puis agrège ::

        taux_autoconsommation = Σ autoconsommé / Σ production
        taux_couverture       = Σ autoconsommé / Σ charge

    Paramètres
    ----------
    load_curve : itérable de consommations horaires (kWh/h) — 24 h, 8760 h ou
        toute longueur. Les valeurs illisibles/négatives sont ramenées à 0
        (jamais de rejet). Si absent, on synthétise un profil type
        (``load_profile``) calé sur ``daily_load_kwh``.
    production_curve : itérable de productions PV horaires (kWh/h). Si absent,
        on synthétise ``TYPICAL_PV_PROFILE`` calé sur ``daily_production_kwh``.
    daily_load_kwh / daily_production_kwh : énergies journalières servant à
        générer les profils type quand une courbe n'est pas fournie.
    load_profile : clé de profil type de charge (``"residential"`` |
        ``"commercial"`` / ``"tertiaire"``) utilisée comme repli.

    Retourne un dict JSON-sérialisable ::

        {hours, total_load_kwh, total_production_kwh, self_consumed_kwh,
         surplus_kwh, grid_import_kwh,
         self_consumption_rate, self_consumption_pct,
         coverage_rate, coverage_pct,
         load_source, production_source, warnings: []}

    Σproduction = 0 → taux d'autoconso 0 ; Σcharge = 0 → couverture 0 ; une
    série absente ou vide (rien de connu de ce côté) rend 0 h et des zéros.

    QJR146 (h) — SEULE EXCEPTION AU « ne lève jamais » historique : deux
    courbes NON VIDES de longueurs DIFFÉRENTES lèvent ``ValueError`` au lieu
    d'être tronquées sur la plus courte. Une charge de 288 points contre une
    production de 24 h produisait des totaux « annuels » calculés sur un seul
    jour, avec un avertissement que rien n'imprime.
    """
    warnings = []

    load = _coerce_series(load_curve)
    load_source = "courbe fournie"
    if not load:
        load = _scaled_typical_load(daily_load_kwh, load_profile)
        load_source = f"profil type ({load_profile})"

    prod = _coerce_series(production_curve)
    production_source = "courbe fournie"
    if not prod:
        prod = _scaled_typical_pv(daily_production_kwh)
        production_source = "profil type PV"

    # ── QJR146 (h) — DEUX COURBES DE LONGUEURS DIFFÉRENTES SONT REFUSÉES ────
    # Elles étaient TRONQUÉES sur la plus courte, avec un simple avertissement
    # que personne n'imprime : une charge de 288 points (12 mois × 24 h) contre
    # une production de 24 h sortait des totaux « annuels » calculés sur UN
    # jour — un chiffre faux d'un facteur 12, présenté comme un calcul. Deux
    # séries qui ne décrivent pas la même période ne s'intègrent pas.
    # Une seule série vide (rien de connu de ce côté) n'est PAS une divergence :
    # elle rend 0 h, donc des zéros honnêtes.
    if load and prod and len(load) != len(prod):
        raise ValueError(
            "hourly_self_consumption: courbes de longueurs différentes "
            f"(charge={len(load)} h, production={len(prod)} h) — elles ne "
            "décrivent pas la même période ; aucun total n'est calculable "
            "(QJR146).")
    n = min(len(load), len(prod))

    total_load = 0.0
    total_prod = 0.0
    self_consumed = 0.0
    for i in range(n):
        c = load[i]
        p = prod[i]
        total_load += c
        total_prod += p
        self_consumed += c if c < p else p   # min(charge, production)

    total_load = round(total_load, 3)
    total_prod = round(total_prod, 3)
    self_consumed = round(self_consumed, 3)
    surplus = round(max(0.0, total_prod - self_consumed), 3)
    grid_import = round(max(0.0, total_load - self_consumed), 3)

    sc_rate = round(self_consumed / total_prod, 4) if total_prod > 0 else 0.0
    cov_rate = round(self_consumed / total_load, 4) if total_load > 0 else 0.0

    if total_prod <= 0:
        warnings.append("production horaire nulle — taux d'autoconsommation 0")
    elif sc_rate >= 0.95:
        warnings.append(
            "autoconsommation quasi totale (≥ 95 %) — peu/pas de surplus "
            "injecté ; un champ plus grand resterait autoconsommé")
    elif sc_rate <= 0.30 and total_prod > 0:
        warnings.append(
            "autoconsommation faible (≤ 30 %) — fort surplus injecté au "
            "réseau ; envisager stockage, décalage des usages ou champ réduit")

    return {
        "hours": n,
        "total_load_kwh": total_load,
        "total_production_kwh": total_prod,
        "self_consumed_kwh": self_consumed,
        "surplus_kwh": surplus,
        "grid_import_kwh": grid_import,
        "self_consumption_rate": sc_rate,
        "self_consumption_pct": round(sc_rate * 100.0, 1),
        "coverage_rate": cov_rate,
        "coverage_pct": round(cov_rate * 100.0, 1),
        "load_source": load_source,
        "production_source": production_source,
        "warnings": warnings,
    }


def load_curve_from_xlsx(file_or_path, *, sheet=None, column=1,
                         skip_header=True, max_rows=8760):
    """FG258 (I/O) — lit une courbe de charge depuis un classeur .xlsx.

    PARSING SÉPARÉ du calcul : extrait UNE colonne d'un classeur openpyxl en
    liste de floats, prête à passer à :func:`hourly_self_consumption`. openpyxl
    est déjà une dépendance du projet (exports .xlsx) — aucune nouvelle
    dépendance n'est ajoutée.

    Paramètres
    ----------
    file_or_path : chemin, objet fichier ou flux ouvert par ``load_workbook``.
    sheet : nom de la feuille (défaut : feuille active).
    column : index de colonne 1-based contenant les valeurs (défaut 1 = A).
    skip_header : ignore la première ligne (en-tête) si True.
    max_rows : nombre maximal de lignes de DONNÉES lues (8760 = année horaire).

    Retourne la liste de floats (cellule vide/illisible → 0.0 pour préserver
    l'alignement horaire). Ne lève pas sur une cellule illisible.
    """
    import openpyxl  # déjà une dépendance projet (cf. requirements.txt)

    wb = openpyxl.load_workbook(file_or_path, read_only=True, data_only=True)
    try:
        ws = wb[sheet] if sheet else wb.active
        col_idx = max(1, int(column or 1))
        limit = int(max_rows) + (1 if skip_header else 0)
        values = []
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx,
                                values_only=True):
            cell = row[0] if row else None
            try:
                values.append(float(cell))
            except (TypeError, ValueError):
                values.append(0.0)
            if len(values) >= limit:
                break
    finally:
        wb.close()

    if skip_header and values:
        values = values[1:]
    return values[:max_rows]


# ── FG261 — Optimisation de la puissance souscrite (C&I) après PV ─────────────
# Pour un client COMMERCIAL / INDUSTRIEL facturé sur une PUISSANCE SOUSCRITE
# (kVA ou kW, « prime fixe » / redevance de puissance MT-BT) : le PV écrête la
# pointe de soutirage RÉSEAU pendant les heures ensoleillées. En croisant la
# courbe de charge horaire avec la production PV horaire, on calcule la demande
# RÉSEAU nette heure par heure (charge − PV, plancher 0), on en tire la NOUVELLE
# pointe de soutirage, et on recommande une puissance souscrite réduite. La
# baisse de redevance de puissance (MAD/kVA/an) est alors chiffrée.
#
# RÈGLE :
#   * demande_réseau[h] = max(0, charge[h] − production[h])  (en kW)
#   * pointe_post_pv = max(demande_réseau)  ;  pointe_pre_pv = max(charge)
#   * puissance recommandée = ceil(pointe_post_pv × marge_sécurité)
#       — jamais SUPÉRIEURE à la souscription actuelle (on n'augmente pas) ;
#       — bornée au plus à la souscription actuelle même si la pointe ne baisse
#         pas (recommandation = pas de réduction → économie 0).
#   * facteur de puissance / conversion kW→kVA : si ``power_factor`` est fourni
#     (cos φ), la demande en kVA = demande_kW / cos φ ; sinon on raisonne dans
#     l'unité de la souscription telle quelle (la souscription est déjà en kVA
#     ou en kW selon le contrat — on ne convertit que si on a le cos φ).
#   * économie annuelle = (souscription_actuelle − recommandée) × tarif_capacité.
#     Le tarif est en MAD par unité de puissance et par AN (``capacity_tariff``,
#     ``tariff_period="year"``) ou par MOIS (``tariff_period="month"`` → ×12).
#
# Module PUR : aucune base, aucun réseau, aucun prix d'achat/marge. Les entrées
# numériques ne sont JAMAIS rejetées (liberté de saisie du founder) — les
# valeurs illisibles/négatives sont ramenées à 0, jamais d'exception, division
# par zéro bornée.

# Marge de sécurité par défaut sur la pointe post-PV pour dimensionner la
# souscription recommandée (aléas météo, croissance de charge, démarrages).
DEFAULT_SUBSCRIBED_SAFETY_MARGIN = 1.10

#: QJR139 (audit QJR79) — LA SEULE UNITÉ QUE CETTE FONCTION SAIT LIRE.
#: Ses courbes sont des PUISSANCES instantanées (kW, ≈ kWh sur l'heure), pas des
#: énergies cumulées. Un appelant lui a réellement passé des kWh MENSUELS
#: (``apps/ventes/etude.py``, 288 points « 12 mois × jour type ») : la case du
#: soir valait 90 « kW » au lieu de ≈ 3 kW réels, et la puissance souscrite
#: recommandée sortait ~30× trop grande. Le paramètre ``curve_unit`` rend
#: l'unité DÉCLARÉE et refusable ; toute autre valeur (y compris ``None``, une
#: unité d'énergie, ou une unité inconnue) fait REFUSER la courbe.
SUBSCRIBED_CURVE_UNIT_KW = "kw"


def _refus_unite_souscrite(curve_unit):
    """QJR139 — refus STRUCTURÉ d'une courbe dont l'unité n'est pas la bonne.

    Le module ne lève jamais (contrat) : on rend donc le MÊME jeu de clés avec
    des valeurs ABSENTES plutôt qu'une pointe plausible et fausse — omettre
    plutôt que publier, la règle du dépôt. L'avertissement nomme l'unité reçue
    pour que l'appelant sache quoi corriger.
    """
    return {
        "hours": 0,
        "peak_pre_pv_kw": None,
        "peak_post_pv_kw": None,
        "peak_reduction_kw": None,
        "peak_reduction_pct": None,
        "demand_unit": None,
        "power_factor": None,
        "peak_post_pv_demand": None,
        "current_subscribed": None,
        "recommended_subscribed": None,
        "subscribed_reduction": None,
        "annual_capacity_tariff": None,
        "annual_saving": None,
        "monthly_saving": None,
        "safety_margin": None,
        "load_source": None,
        "production_source": None,
        "hypotheses": [],
        "warnings": [
            "unité de courbe non déclarée ou non lisible (%r) : cette fonction "
            "lit des PUISSANCES instantanées (%r), jamais des énergies "
            "cumulées — aucune puissance souscrite n'est recommandée."
            % (curve_unit, SUBSCRIBED_CURVE_UNIT_KW)
        ],
    }


def optimize_subscribed_power(load_curve=None, production_curve=None, *,
                              curve_unit=SUBSCRIBED_CURVE_UNIT_KW,
                              current_subscribed_kva=None,
                              capacity_tariff=0.0,
                              tariff_period="year",
                              safety_margin=None,
                              power_factor=None,
                              daily_load_kwh=None,
                              daily_production_kwh=None,
                              load_profile="commercial"):
    """FG261 — recommande une puissance souscrite réduite après PV (C&I).

    Croise la COURBE DE CHARGE horaire (kW/h ≈ kWh par heure) et la PRODUCTION
    PV horaire (kW/h) pour calculer la demande RÉSEAU nette heure par heure
    (``max(0, charge − PV)``), en déduit la pointe de soutirage POST-PV, puis
    recommande une puissance souscrite réduite et chiffre l'économie sur la
    redevance de puissance (prime fixe).

    Paramètres
    ----------
    load_curve : itérable de demandes horaires (kW, ≈ kWh/h) — 24 h, 8760 h ou
        toute longueur. Valeurs illisibles/négatives → 0 (jamais de rejet). Si
        absent, on synthétise un profil type (``load_profile``) calé sur
        ``daily_load_kwh``.
    curve_unit : QJR139 — l'unité DÉCLARÉE des deux courbes. Seule
        :data:`SUBSCRIBED_CURVE_UNIT_KW` (``"kw"``, la puissance instantanée)
        est lisible ; toute autre valeur — ``None``, une énergie cumulée, une
        unité inconnue — fait REFUSER la courbe et rend un résultat aux
        grandeurs ABSENTES avec l'avertissement qui l'explique, plutôt qu'une
        pointe plausible et fausse. Un appelant a réellement passé ici des kWh
        MENSUELS : la puissance recommandée sortait ~30× trop grande.
    production_curve : production PV horaire (kW/h). Si absent, on synthétise
        ``TYPICAL_PV_PROFILE`` calé sur ``daily_production_kwh``.
    current_subscribed_kva : puissance souscrite ACTUELLE (kVA ou kW selon le
        contrat). Si absente/illisible → la pointe pré-PV sert de référence.
    capacity_tariff : redevance de puissance (MAD par unité de puissance et par
        période ``tariff_period``).
    tariff_period : ``"year"`` (défaut) ou ``"month"`` (×12 pour l'annuel).
    safety_margin : marge sur la pointe post-PV pour dimensionner la
        souscription recommandée (défaut 1.10). Bornée ≥ 1.0.
    power_factor : cos φ facultatif — convertit la demande kW en kVA
        (kVA = kW / cos φ) quand la souscription est en kVA. Si absent, on
        raisonne dans l'unité de la souscription telle quelle.
    daily_load_kwh / daily_production_kwh : énergies journalières pour générer
        les profils type quand une courbe n'est pas fournie.
    load_profile : clé de profil type de charge (repli) — ``"commercial"`` par
        défaut (la cible C&I).

    Retourne un dict JSON-sérialisable ::

        {hours, peak_pre_pv_kw, peak_post_pv_kw, peak_reduction_kw,
         peak_reduction_pct, demand_unit, power_factor,
         peak_post_pv_demand, current_subscribed, recommended_subscribed,
         subscribed_reduction, annual_capacity_tariff,
         annual_saving, monthly_saving, load_source, production_source,
         warnings: []}

    Ne lève jamais : courbes vides → pointe 0 ; pas de réduction possible →
    recommandation = souscription actuelle et économie 0 ; division par zéro
    bornée (cos φ ≤ 0 ignoré) ; unité non déclarée → refus STRUCTURÉ (toutes
    les grandeurs absentes + avertissement), jamais une exception.
    """
    # QJR139 — GARDE D'UNITÉ, AVANT TOUT CALCUL. Une courbe d'énergies cumulées
    # lue comme des puissances donne une pointe absurde sans le moindre signal :
    # le refus est structuré, nommé, et ne publie aucun nombre.
    if (not isinstance(curve_unit, str)
            or curve_unit.strip().lower() != SUBSCRIBED_CURVE_UNIT_KW):
        return _refus_unite_souscrite(curve_unit)

    warnings = []

    load = _coerce_series(load_curve)
    load_source = "courbe fournie"
    if not load:
        load = _scaled_typical_load(daily_load_kwh, load_profile)
        load_source = f"profil type ({load_profile})"

    prod = _coerce_series(production_curve)
    production_source = "courbe fournie"
    if not prod:
        prod = _scaled_typical_pv(daily_production_kwh)
        production_source = "profil type PV"

    # Alignement des longueurs (on borne sur la plus courte).
    n = min(len(load), len(prod)) if prod else len(load)
    if load and prod and len(load) != len(prod):
        warnings.append(
            f"courbes de longueurs différentes (charge={len(load)} h, "
            f"production={len(prod)} h) — alignées sur {n} h")

    # ── Pointe de soutirage réseau pré-PV et post-PV (en kW) ──
    peak_pre = 0.0
    peak_post = 0.0
    if prod:
        for i in range(n):
            c = load[i]
            net = c - prod[i]
            if net < 0.0:
                net = 0.0
            if c > peak_pre:
                peak_pre = c
            if net > peak_post:
                peak_post = net
    else:
        # Aucune production fournie ni synthétisable : pointe post-PV = pré-PV.
        for c in load:
            if c > peak_pre:
                peak_pre = c
        peak_post = peak_pre

    peak_pre = round(peak_pre, 3)
    peak_post = round(peak_post, 3)
    peak_reduction_kw = round(max(0.0, peak_pre - peak_post), 3)
    peak_reduction_pct = (
        round(peak_reduction_kw / peak_pre * 100.0, 1) if peak_pre > 0 else 0.0)

    # ── Conversion kW → kVA si cos φ fourni (souscription en kVA) ──
    pf = None
    try:
        pf_val = float(power_factor)
        if 0.0 < pf_val <= 1.0:
            pf = pf_val
    except (TypeError, ValueError):
        pf = None
    if pf is not None:
        demand_unit = "kVA"
        peak_post_demand = round(peak_post / pf, 3)
    else:
        demand_unit = "kW/kVA"
        peak_post_demand = peak_post

    # ── Souscription actuelle (référence) ──
    try:
        current = float(current_subscribed_kva)
    except (TypeError, ValueError):
        current = None
    if current is None or current <= 0:
        # Pas de souscription fournie : on prend la pointe pré-PV convertie
        # comme référence (l'économie est alors purement indicative).
        ref = peak_pre / pf if pf else peak_pre
        current = round(ref, 3)
        if current > 0:
            warnings.append(
                "puissance souscrite actuelle non fournie — pointe pré-PV "
                "utilisée comme référence (économie indicative)")

    # ── Marge de sécurité ──
    # CALX286 — la marge non fournie reste celle du module, PUBLIÉE avec sa
    # provenance (valeur inchangée).
    hypotheses = []
    margin = _taux_ou_none(safety_margin)
    if margin is None:
        margin = DEFAULT_SUBSCRIBED_SAFETY_MARGIN
        hypotheses.append(_hypothese(
            "safety_margin", DEFAULT_SUBSCRIBED_SAFETY_MARGIN,
            _source_defaut("DEFAULT_SUBSCRIBED_SAFETY_MARGIN"),
            ["safety_margin", "recommended_subscribed",
             "subscribed_reduction", "annual_saving", "monthly_saving"]))
    if margin < 1.0:
        margin = 1.0

    # Souscription recommandée = ceil(pointe post-PV × marge), bornée à la
    # souscription actuelle (on ne RECOMMANDE jamais d'augmenter).
    recommended_raw = peak_post_demand * margin
    recommended = int(math.ceil(recommended_raw)) if recommended_raw > 0 else 0
    if current > 0 and recommended > current:
        # La pointe post-PV (× marge) dépasse déjà la souscription : aucune
        # réduction possible — on garde la souscription actuelle.
        recommended = round(current, 3)
        warnings.append(
            "la pointe réseau après PV (avec marge) atteint la puissance "
            "souscrite actuelle — aucune réduction recommandée")

    subscribed_reduction = round(max(0.0, current - recommended), 3)

    # ── Tarif annuel de capacité ──
    try:
        tariff = float(capacity_tariff)
    except (TypeError, ValueError):
        tariff = 0.0
    if tariff < 0.0:
        tariff = 0.0
    annual_tariff = tariff * 12.0 if (tariff_period or "year") == "month" \
        else tariff

    annual_saving = round(subscribed_reduction * annual_tariff, 2)
    monthly_saving = round(annual_saving / 12.0, 2)

    if peak_reduction_kw <= 0 and prod:
        warnings.append(
            "le PV n'écrête pas la pointe de soutirage (pointe hors heures "
            "solaires) — pas de gain sur la puissance souscrite")
    if subscribed_reduction > 0 and tariff <= 0:
        warnings.append(
            "réduction de puissance possible mais tarif de capacité non "
            "fourni — économie non chiffrée (renseigner capacity_tariff)")

    return {
        "hours": n,
        "peak_pre_pv_kw": peak_pre,
        "peak_post_pv_kw": peak_post,
        "peak_reduction_kw": peak_reduction_kw,
        "peak_reduction_pct": peak_reduction_pct,
        "demand_unit": demand_unit,
        "power_factor": pf,
        "peak_post_pv_demand": peak_post_demand,
        "current_subscribed": round(current, 3),
        "recommended_subscribed": recommended,
        "subscribed_reduction": subscribed_reduction,
        "safety_margin": round(margin, 4),
        "annual_capacity_tariff": round(annual_tariff, 4),
        "annual_saving": annual_saving,
        "monthly_saving": monthly_saving,
        "load_source": load_source,
        "production_source": production_source,
        "hypotheses": hypotheses,
        "warnings": warnings,
    }


# ── FG264 — Rendement pompage par cycle de marche (volume d'eau jour/mois) ─────
# AGR109 — le calcul a DÉMÉNAGÉ dans le noyau pur ``core.pompage.volumes``
# (partagé par ventes et calepinage, sans base de données). Ce module garde des
# RÉ-EXPORTS pour que ses appelants restent inchangés (comportement
# octet-identique).
from core.pompage.volumes import (  # noqa: E402,F401
    _CLEARSKY_HOURLY_SHAPE,
    _DAYS_IN_MONTH,
    _PUMP_START_IRRADIANCE_FRACTION,
    clearsky_hourly_irradiance,
    pumping_cycle_yield,
)


def _safe_float(value, default=0.0):
    """Float tolérant : illisible → ``default`` (jamais d'exception)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


# ── FG266 — Comparateur de scénarios de devis ────────────────────────────────
# Compare plusieurs DIMENSIONNEMENTS d'une même affaire (kWc / batterie /
# orientation) sur trois axes décisionnels : PRODUCTION annuelle, ÉCONOMIES
# annuelles et PAYBACK (retour sur investissement). Calcul PUR (aucune écriture
# base, aucun changement de statut de devis) ; jamais aucun prix d'achat / marge
# en sortie — seuls le coût TTC fourni et l'économie figurent. Réutilise
# ``tariff_escalation_projection`` (FG260) pour le payback/VAN/TRI cohérent.


def _productible_de_repli_devis():
    """ACAL270 — LE productible de repli « PVGIS indisponible / ville inconnue ».

    Défaut gravé D-ACAL : « productible de repli = celui du devis partout » —
    ``productible_for_city('')`` (DEFAULT_PRODUCTIBLE, 1651) × PRODUCTION_DERATE
    (≈ 0,9302) ≈ 1 536 kWh/kWc, exactement ce que le moteur du devis applique.
    Remplace l'ancien repli brut 1600.0 (jumeau supprimé). Lecture seule des
    constantes du moteur (règle #4 : rien n'y est modifié). Import LOCAL : ce
    module reste pur au chargement (``quote_engine.builder`` importe CE module).
    Le seuil / la production attendue du suivi de production (monitoring) est
    HORS périmètre (usage différent, défaut gravé).
    """
    from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
    from apps.ventes.quote_engine.productible import productible_for_city
    return productible_for_city('') * PRODUCTION_DERATE


def _scenario_annual_production(scenario):
    """Production annuelle (kWh) d'un scénario.

    Priorité à ``annual_production_kwh`` s'il est fourni ; sinon dérivée de
    ``kwc`` × ``productible_kwh_kwc`` × facteur d'orientation. Le facteur
    d'orientation (``orientation_factor``, base 1.0) module l'effet d'une
    orientation/inclinaison non optimale. Renvoie un float ≥ 0.
    """
    direct = scenario.get('annual_production_kwh')
    if direct is not None:
        return max(0.0, _safe_float(direct, 0.0))
    kwc = max(0.0, _safe_float(scenario.get('kwc'), 0.0))
    productible = _safe_float(scenario.get('productible_kwh_kwc'),
                              _productible_de_repli_devis())
    orient = scenario.get('orientation_factor')
    orient_f = _safe_float(orient, 1.0) if orient is not None else 1.0
    orient_f = max(0.0, orient_f)
    return round(kwc * productible * orient_f, 1)


def compare_scenarios(scenarios, *, escalation_rate=None,
                      degradation_rate=None, horizon_years=None,
                      discount_rate=None):
    """FG266 — compare des scénarios de dimensionnement et les classe.

    Chaque scénario est un dict pouvant porter ::

        {label, kwc, battery_kwh, orientation_factor, productible_kwh_kwc,
         annual_production_kwh, annual_savings, upfront_cost}

    Pour chaque scénario on calcule la production annuelle (kWh), l'économie
    annuelle (MAD/an, telle que fournie), puis le payback / VAN / TRI via
    ``tariff_escalation_projection`` (FG260) avec une convention COMMUNE
    (mêmes taux d'escalade/dégradation/actualisation/horizon pour tous, pour une
    comparaison équitable). On classe ensuite les scénarios par production,
    économie et payback (le plus court d'abord) et on désigne le « meilleur »
    payback (recommandation indicative, jamais bloquante).

    Ne lève JAMAIS sur entrées dégradées ; jamais de prix d'achat/marge. Renvoie
    un dict JSON-sérialisable ::

        {scenarios: [{...metrics}], ranking: {by_production, by_savings,
         by_payback}, best_payback_index, warnings}
    """
    warnings = []
    if not isinstance(scenarios, (list, tuple)) or not scenarios:
        return {
            'scenarios': [],
            'ranking': {'by_production': [], 'by_savings': [],
                        'by_payback': []},
            'best_payback_index': None,
            'warnings': ['aucun scénario fourni'],
        }

    # Paramètres financiers communs (défauts FG260 si non fournis).
    proj_kwargs = {}
    if escalation_rate is not None:
        proj_kwargs['escalation_rate'] = _safe_float(escalation_rate, None)
    if degradation_rate is not None:
        proj_kwargs['degradation_rate'] = _safe_float(degradation_rate, None)
    if horizon_years is not None:
        proj_kwargs['horizon_years'] = int(_safe_float(horizon_years, 25))
    if discount_rate is not None:
        proj_kwargs['discount_rate'] = _safe_float(discount_rate, None)

    enriched = []
    for idx, raw in enumerate(scenarios):
        scenario = raw if isinstance(raw, dict) else {}
        label = scenario.get('label') or f'Scénario {idx + 1}'
        production = _scenario_annual_production(scenario)
        annual_savings = max(0.0, _safe_float(scenario.get('annual_savings'),
                                              0.0))
        upfront = max(0.0, _safe_float(scenario.get('upfront_cost'), 0.0))

        payback_year = None
        npv = None
        irr = None
        if annual_savings > 0:
            proj = tariff_escalation_projection(
                annual_savings_year1=annual_savings,
                upfront_cost=upfront,
                **proj_kwargs)
            summary = proj.get('summary', {})
            payback_year = summary.get('payback_year')
            npv = summary.get('npv')
            irr = summary.get('irr')
        else:
            warnings.append(
                f'{label} : économie annuelle nulle, payback non calculé')

        enriched.append({
            'index': idx,
            'label': label,
            'kwc': round(_safe_float(scenario.get('kwc'), 0.0), 2),
            'battery_kwh': round(_safe_float(scenario.get('battery_kwh'),
                                             0.0), 2),
            'annual_production_kwh': production,
            'annual_savings': round(annual_savings, 2),
            'upfront_cost': round(upfront, 2),
            'payback_year': payback_year,
            'npv': npv,
            'irr': irr,
        })

    # Classements (indices d'origine). Production/économie décroissantes ;
    # payback croissant (None relégué en fin, jamais « meilleur »).
    by_production = [s['index'] for s in sorted(
        enriched, key=lambda s: s['annual_production_kwh'], reverse=True)]
    by_savings = [s['index'] for s in sorted(
        enriched, key=lambda s: s['annual_savings'], reverse=True)]

    def _payback_key(s):
        py = s['payback_year']
        return (float('inf'), s['index']) if py is None else (py, s['index'])

    by_payback = [s['index'] for s in sorted(enriched, key=_payback_key)]

    best_payback_index = None
    for s in sorted(enriched, key=_payback_key):
        if s['payback_year'] is not None:
            best_payback_index = s['index']
            break

    return {
        'scenarios': enriched,
        'ranking': {
            'by_production': by_production,
            'by_savings': by_savings,
            'by_payback': by_payback,
        },
        'best_payback_index': best_payback_index,
        'warnings': warnings,
    }
