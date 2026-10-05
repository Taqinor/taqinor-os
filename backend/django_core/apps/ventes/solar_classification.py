"""SPL261 — LA table de classification produit du backend (déplacée de ``solar_design.py``).

Prédicats ``is_panel`` / ``is_battery`` / onduleurs (hybride, réseau,
hors réseau) / Smart Meter / clé Wi-Fi et lecteurs ``parse_watt`` /
``parse_kw`` (QJR78, QJR301, QJR424, QJR-OFFGRID, STKCAT22). Lus par le
moteur de rendu (``quote_engine/builder.py``, import de tête), la composition
(``domain/catalogue.py``), le schéma unifilaire et le service électrique ;
``solar_design`` n'en garde que l'usage de ``match_inverter``.

Module PUR au chargement : bibliothèque standard + ``core.product_roles``
(ni Django, ni modèle, ni réglage) — le contrat de l'import de tête du
builder. ``is_panel`` garde son import LOCAL de ``utils.options`` (cycle).

Déplacement « move only » : corps, docstrings et mots-clés sont
OCTET-IDENTIQUES — prouvé par ``tests/test_split_devis_solar.py`` (golden
``split_sd_classif`` + digests de comportement + empreinte du HTML rendu).
"""
from __future__ import annotations

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
