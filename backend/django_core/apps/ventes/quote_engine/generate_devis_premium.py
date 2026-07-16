#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# flake8: noqa
# Vendored from RedaSolar/devis-simulator (founder's quote engine), adapted for
# the OS: fonts/logo bundled locally (no runtime network), matplotlib config dir.
"""
generate_devis_premium.py  FINAL
Page 1 : white-background v1 layout
Pages 2-3 : v4 premium dark design
Usage : python generate_devis_premium.py
"""
import base64, html, io, json, re, subprocess, sys, tempfile, threading
from pathlib import Path


def _render_pdf_weasyprint(html_string, out_path):
    """Render HTML to PDF using WeasyPrint (no browser needed)."""
    from weasyprint import HTML
    base_dir = str(Path(__file__).resolve().parent)
    HTML(string=html_string, base_url=f"file://{base_dir}/").write_pdf(str(out_path))
    if not Path(out_path).exists():
        raise RuntimeError("WeasyPrint PDF generation failed.")
    print(f"WeasyPrint rendered: {out_path}")


import os

# matplotlib needs a writable config dir; in the container $HOME may be read-only.
os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())
import matplotlib
matplotlib.use("Agg")

BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"
ASSET_DIR = BASE_DIR / "assets"

# ERR17 — a render writes ~40 module-level globals and reads them back while
# building the HTML; under Gunicorn --threads two concurrent renders would
# interleave one client's data into another's PDF (cross-tenant leak).
# Serialize every render on one process-level lock.
_RENDER_LOCK = threading.RLock()


def _esc(value):
    """HTML-escape a user-controlled scalar (ERR37). Byte-identical for text
    without &<>"' so legitimate names/PDFs are unchanged."""
    return html.escape(str(value)) if value is not None else ""


def _esc_items(items):
    """Copy line-item dicts with their user-controlled text fields HTML-escaped
    (ERR37). Numeric fields and the designation/marque classification keywords
    are unaffected (escape only touches &<>"')."""
    out = []
    for it in (items or []):
        e = dict(it)
        for k in ("designation", "marque", "description", "garantie"):
            if e.get(k) is not None:
                e[k] = html.escape(str(e[k]))
        out.append(e)
    return out


def _guard_huawei_accessories(items):
    """QF9 — défense en profondeur : ne jamais rendre Smart Meter / Clé Wifi
    (dongle) quand l'onduleur des lignes n'est pas Huawei. Le builder filtre
    déjà ces lignes en amont ; ce garde-fou empêche qu'une ligne obsolète glissée
    dans ``data`` réapparaisse dans le PDF. Huawei détecté sur la désignation +
    la marque de l'onduleur des lignes fournies."""
    rows = items or []
    inverters = [it for it in rows
                 if "onduleur" in (it.get("designation", "") or "").lower()]
    if not inverters:
        return list(rows)
    is_huawei = all(
        "huawei" in (f"{it.get('designation', '')} "
                     f"{it.get('marque', '')}").lower()
        for it in inverters)
    if is_huawei:
        return list(rows)
    out = []
    for it in rows:
        d = (it.get("designation", "") or "").lower()
        if "smart meter" in d or "wifi" in d or "dongle" in d:
            continue
        out.append(it)
    return out

# ── Inline SVG icons for Page 1 (WeasyPrint renders inline SVG perfectly) ────
SVG_CHECK   = '<svg width="13" height="13" viewBox="0 0 13 13" style="vertical-align:middle;margin-right:4px;"><path d="M2 6.5l3.5 3.5 5.5-6" stroke="#2e7d32" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
SVG_BOLT    = '<svg width="13" height="13" viewBox="0 0 13 13" style="vertical-align:middle;margin-right:4px;"><path d="M8 1L4 7.5H7L5 12L10 6H7Z" fill="#d4a84b"/></svg>'
SVG_CHART   = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><rect rx="3" width="14" height="14" fill="#e8f5e9"/><path d="M3 10L6 6l2 2 3-4" stroke="#2e7d32" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>'
SVG_CHART2  = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><rect rx="3" width="14" height="14" fill="#1a1a2e"/><path d="M3 10L6 6l2 2 3-4" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>'
SVG_STAR    = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><path d="M7 1l2 4h4l-3 3 1 4-4-2-4 2 1-4-3-3h4z" fill="#d4a84b"/></svg>'
SVG_HOUSE   = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><path d="M7 1L1 7h2v5h3V9h2v3h3V7h2L7 1z" fill="white"/></svg>'
SVG_FACTORY = '<svg width="14" height="14" viewBox="0 0 14 14" style="vertical-align:middle;margin-right:3px;"><rect x="1" y="7" width="12" height="6" fill="white" rx="1"/><rect x="3" y="4" width="3" height="3" fill="white"/><rect x="8" y="4" width="3" height="3" fill="white"/><rect x="5" y="1" width="4" height="3" fill="white"/></svg>'
SVG_SUN     = '<svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;"><circle cx="6" cy="6" r="3" fill="#d4a84b"/><g stroke="#d4a84b" stroke-width="1"><line x1="6" y1="0" x2="6" y2="2"/><line x1="6" y1="10" x2="6" y2="12"/><line x1="0" y1="6" x2="2" y2="6"/><line x1="10" y1="6" x2="12" y2="6"/></g></svg>'
SVG_ZAP     = '<svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;"><path d="M7 1L3 7h3l-1 4 5-6H7l1-4z" fill="#d4a84b"/></svg>'
SVG_GLOBE   = '<svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;"><circle cx="6" cy="6" r="5" fill="none" stroke="#4caf50" stroke-width="1"/><ellipse cx="6" cy="6" rx="2.5" ry="5" fill="none" stroke="#4caf50" stroke-width="0.8"/><line x1="1" y1="6" x2="11" y2="6" stroke="#4caf50" stroke-width="0.8"/></svg>'

SVG_ARROW   = '<svg width="6" height="6" viewBox="0 0 6 6" style="vertical-align:middle;margin:0 2px;"><path d="M1 3h4M3 1l2 2-2 2" stroke="rgba(255,255,255,0.55)" stroke-width="1" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'

def svg_num(n):
    return (f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
            f'background:#d4a84b;color:white;font-size:8px;font-weight:700;'
            f'text-align:center;line-height:14px;vertical-align:middle;margin-right:2px;">{n}</span>')

def _load_gfont(filename):
    """Load a bundled woff2 font from assets/fonts and return base64.

    Fonts are vendored locally so PDF rendering NEVER makes a network call.
    Returns None if the file is missing (template falls back to system fonts).
    """
    path = FONT_DIR / filename
    if not path.exists():
        return None
    try:
        return base64.b64encode(path.read_bytes()).decode()
    except Exception:
        return None

def _font_face(family, weight, style, b64):
    if not b64:
        return ""
    return (f'@font-face{{font-family:"{family}";font-style:{style};font-weight:{weight};'
            f'font-display:block;src:url("data:font/woff2;base64,{b64}") format("woff2");}}')

# Load all bundled fonts needed for page 1 (local files — no network)
_DS400     = _load_gfont("DMSerifDisplay-400.woff2")   # DM Serif Display Regular
_DMSANS400 = _load_gfont("DMSans-400.woff2")            # DM Sans Regular
_DMSANS500 = _load_gfont("DMSans-500.woff2")            # DM Sans Medium
_DMSANS700 = _load_gfont("DMSans-700.woff2")            # DM Sans Bold

# Playfair Display (pages 2-3 backward compat)
_PF700 = _load_gfont("PlayfairDisplay-700.woff2")
_PF400 = _load_gfont("PlayfairDisplay-400.woff2")

def _pf_face(weight, b64):
    if not b64:
        return ""
    return (f'@font-face{{font-family:"Playfair Display";font-style:normal;'
            f'font-weight:{weight};font-display:block;'
            f'src:url("data:font/woff2;base64,{b64}") format("woff2");}}')

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── Design tokens ────────────────────────────────────────────────────────────
CN  = "#0F1E35"
CNM = "#1A2B4A"
CA  = "#F5A623"
CAL = "#FDF3E3"
CW  = "#FFFFFF"
CG1 = "#F7F8FA"
CG2 = "#EAECF0"
CG4 = "#9BA3AE"
CG7 = "#374151"
CGR = "#16A34A"
# DC1 — couleur d'accent par défaut (Taqinor). CA peut être surchargée par la
# couleur de charte de la société (CompanyProfile.couleur_principale) au rendu ;
# on la réinitialise depuis ce défaut au début de chaque rendu.
_CA_DEFAULT = CA

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTE_INPUT — seule section à modifier pour changer un devis
# ═══════════════════════════════════════════════════════════════════════════════
QUOTE_INPUT = {
    "ref":              "412",
    "date":             "28/02/2026",
    "client_name":      "Reda Kasri",
    "client_addr":      "5 Rue Ennoussour RDC",
    "client_phone":     "0661850410",
    "inst_type":        "R\u00e9sidentielle",
    "puissance_kwc":    10.65,
    "nb_panneaux":      15,
    "watt_par_panneau": 710,
    "city":             "Casablanca",
    "prod_kwh":         13190,
    "eco_s_ann":        15828,   # \u00e9conomies/an affich\u00e9es \u2014 Option 1
    "eco_a_ann":        25232,   # \u00e9conomies/an affich\u00e9es \u2014 Option 2 (KPI)
    "eco_a_cumul":      19478,   # taux r\u00e9el pour courbe ROI cumulatif
    "roi_s":            3.3,
    "roi_a":            5.5,
    "eco_s_monthly":    [850, 980,1320,1560,1820,1850,1840,1610,1390,1120, 830, 760],
    "eco_a_monthly":    [1380,1590,2140,2220,2470,2640,2650,2510,2280,1890,1380,1230],
    # Batteries incluses dans l'Option 2
    "battery_option": [
        {"designation": "Batterie 5\u202fkWh",  "marque": "Deye", "quantite": 1, "prix_unit_ttc": 16000},
        {"designation": "Batterie 10\u202fkWh", "marque": "Deye", "quantite": 1, "prix_unit_ttc": 27000},
    ],
    # Overrides — None = formule bloc automatique
    "overrides": {
        "onduleur_reseau":   15000,
        "smart_meter":       1800,
        "wifi_dongle":       1200,
        "prix_panneau":      1100,
        "onduleur_hybride":  29000,
        "structures_unit":   450,
        "installation":      4000,   # override formule: (blocks+1)\u00d72400
        "tableau":           2000,   # override formule: blocks\u00d71500
        "accessoires":       None,   # None \u2192 blocks\u00d71000 = 2000
        "transport":         1000,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# PRICING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_quote(q):
    """Block-based pricing engine. blocks = max(1, round(kwc/5))."""
    kwc    = q["puissance_kwc"]
    nb_pan = q["nb_panneaux"]
    ovr    = q.get("overrides", {})

    blocks = max(1, round(kwc / 5))

    def ov(key, default):
        v = ovr.get(key)
        return v if v is not None else default

    installation     = ov("installation",     (blocks + 1) * 2400)
    accessoires      = ov("accessoires",      blocks * 1000)
    tableau          = ov("tableau",          blocks * 1500)
    transport        = ov("transport",        1000)
    structures_unit  = ov("structures_unit",  450)
    onduleur_reseau  = ov("onduleur_reseau",  14000)
    smart_meter      = ov("smart_meter",      1500)
    wifi_dongle      = ov("wifi_dongle",      0)
    prix_panneau     = ov("prix_panneau",     1100)
    onduleur_hybride = ov("onduleur_hybride", 29000)

    sans_items = [
        {"designation": "Onduleur r\u00e9seau",              "marque": "Huawei",         "quantite": 1,      "prix_unit_ttc": onduleur_reseau},
        {"designation": "Smart Meter",                       "marque": "Huawei",         "quantite": 1,      "prix_unit_ttc": smart_meter},
        {"designation": "Wifi Dongle",                       "marque": "Huawei",         "quantite": 1,      "prix_unit_ttc": wifi_dongle},
        {"designation": "Panneaux",                          "marque": "Canadian Solar", "quantite": nb_pan, "prix_unit_ttc": prix_panneau},
        {"designation": "Structures acier",                  "marque": "",               "quantite": nb_pan, "prix_unit_ttc": structures_unit},
        {"designation": "Socles",                            "marque": "",               "quantite": 30,     "prix_unit_ttc": 80},
        {"designation": "Accessoires",                       "marque": "",               "quantite": 1,      "prix_unit_ttc": accessoires},
        {"designation": "Tableau De Protection AC/DC",       "marque": "",               "quantite": 1,      "prix_unit_ttc": tableau},
        {"designation": "Installation",                      "marque": "",               "quantite": 1,      "prix_unit_ttc": installation},
        {"designation": "Transport",                         "marque": "",               "quantite": 1,      "prix_unit_ttc": transport},
    ]

    avec_base = [
        {"designation": "Onduleur hybride",                  "marque": "Deye",           "quantite": 1,      "prix_unit_ttc": onduleur_hybride},
        {"designation": "Panneaux",                          "marque": "Canadian Solar", "quantite": nb_pan, "prix_unit_ttc": prix_panneau},
    ]
    batteries = list(q.get("battery_option", []))
    avec_tail = [
        {"designation": "Structures acier",                  "marque": "",               "quantite": nb_pan, "prix_unit_ttc": structures_unit},
        {"designation": "Socles",                            "marque": "",               "quantite": 30,     "prix_unit_ttc": 80},
        {"designation": "Accessoires",                       "marque": "",               "quantite": 1,      "prix_unit_ttc": accessoires},
        {"designation": "Tableau De Protection AC/DC",       "marque": "",               "quantite": 1,      "prix_unit_ttc": tableau},
        {"designation": "Installation",                      "marque": "",               "quantite": 1,      "prix_unit_ttc": installation},
        {"designation": "Transport",                         "marque": "",               "quantite": 1,      "prix_unit_ttc": transport},
    ]
    avec_items = avec_base + batteries + avec_tail

    total_sans = sum(it["quantite"] * it["prix_unit_ttc"] for it in sans_items)
    total_avec = sum(it["quantite"] * it["prix_unit_ttc"] for it in avec_items)

    return {
        "sans_items": sans_items, "avec_items": avec_items,
        "total_sans": total_sans, "total_avec": total_avec,
        "blocks": blocks,
    }

# ── Run pricing engine ────────────────────────────────────────────────────────
_Q = calculate_quote(QUOTE_INPUT)

CLIENT_NAME  = QUOTE_INPUT["client_name"]
CLIENT_ADDR  = QUOTE_INPUT["client_addr"]
CLIENT_PHONE = QUOTE_INPUT["client_phone"]
CLIENT_ICE   = QUOTE_INPUT.get("client_ice", "")
REF          = QUOTE_INPUT["ref"]
DATE_STR     = QUOTE_INPUT["date"]
KWC          = QUOTE_INPUT["puissance_kwc"]
NB_PAN       = QUOTE_INPUT["nb_panneaux"]
WP           = QUOTE_INPUT["watt_par_panneau"]
PROD_KWH     = QUOTE_INPUT["prod_kwh"]
TOTAL_SANS        = _Q["total_sans"]
TOTAL_AVEC        = _Q["total_avec"]
DISCOUNT_PCT      = 0.0
TOTAL_SANS_BEFORE = _Q["total_sans"]
TOTAL_AVEC_BEFORE = _Q["total_avec"]
ECO_S_ANN    = QUOTE_INPUT["eco_s_ann"]
ECO_A_ANN    = QUOTE_INPUT["eco_a_ann"]
ROI_S        = QUOTE_INPUT["roi_s"]
ROI_A        = QUOTE_INPUT["roi_a"]
INST_TYPE    = QUOTE_INPUT["inst_type"]
SANS_ITEMS   = _Q["sans_items"]
AVEC_ITEMS   = _Q["avec_items"]

MONTHS  = ["Jan","F\u00e9v","Mar","Avr","Mai","Jun",
           "Jul","Ao\u00fb","Sep","Oct","Nov","D\u00e9c"]
ECO_S_M    = QUOTE_INPUT["eco_s_monthly"]
ECO_A_M    = QUOTE_INPUT["eco_a_monthly"]
# Actual monthly bills entered by user; fallback to proxy if not in QUOTE_INPUT
FACTURES_M = QUOTE_INPUT.get("factures_mensuelles") or [
    round(v * (ECO_S_ANN / 0.65) / max(1, sum(QUOTE_INPUT["eco_s_monthly"])))
    for v in QUOTE_INPUT["eco_s_monthly"]
]

YEARS   = list(range(26))
CUMUL_S = [-TOTAL_SANS + ECO_S_ANN * y for y in YEARS]
CUMUL_A = [-TOTAL_AVEC + QUOTE_INPUT["eco_a_cumul"] * y for y in YEARS]

SCENARIO    = "Les deux (Sans + Avec)"
RECOMMENDED = "Avec batterie"

DEVIS_FINAL    = False
PAYMENT_MODE   = "standard"   # "standard" or "custom"
CUSTOM_ACOMPTE = None          # user-defined acompte (MAD) for custom mode
# FG52 — devise portée par le document (ISO 4217, défaut MAD). Lue depuis
# data["devise"] ; permet l'affichage de la bonne devise sur le PDF.
DEVISE = "MAD"
PAGES_TOTAL = 3                # nombre réel de pages (4 avec l'étude)
PAGE3_NUM = 3                  # numéro de la page de signature
TOTAUX_ALL = None              # totaux canoniques toutes-lignes (one-page)
# Conditions de paiement par mode — TOUJOURS fournies par le builder ;
# défaut résidentiel pour le chemin autonome.
PAY_A, PAY_M, PAY_S = 30, 60, 10
# Devis deux-options rendu en une page : option 1 seule + mention discrète.
ONEPAGE_NOTE_BATTERIE = False

# ── DC1 — identité société (multi-tenant) ──────────────────────────────────────
# Chaque littéral d'identité (nom de marque du footer, coordonnées, ligne légale
# RC/ICE/adresse, ligne RIB) devient une variable pilotée par ENT (posée depuis
# data["entreprise"] = CompanyProfile). Les DÉFAUTS ci-dessous reproduisent
# EXACTEMENT les littéraux Taqinor historiques : tant qu'aucun profil enrichi
# n'est fourni, le PDF reste byte-identique. Un devis d'un AUTRE tenant affiche
# désormais SON identité — plus de fuite de l'ICE/RIB/RC de Taqinor.
ENT_NOM_MARQUE = "TAQINOR"                       # nom affiché dans les footers
# Ligne de coordonnées (email · téléphone · site) — littéral historique exact.
ENT_CONTACT_LINE = ("contact@taqinor.com &nbsp;&#183;&nbsp; "
                    "+212&#160;6&#160;61&#160;85&#160;04&#160;10 "
                    "&nbsp;&#183;&nbsp; www.taqinor.ma")
# Pied de la page ETUDE (email · site, sans téléphone) — littéral historique
# exact (SCA27 : reconstruit par _apply_entreprise dès qu’un email ou un site
# de profil est fourni — plus de fuite du contact fondateur sur la page étude).
ENT_ETUDE_CONTACT = "contact@taqinor.com &nbsp;·&nbsp; www.taqinor.ma"
# Ligne légale du footer page 3 (raison sociale · RC · ICE · capital · siège).
ENT_LEGAL_LINE = ("Taqinor Solutions SARLAU &middot; RC 691213 &middot; "
                  "ICE 003799642000067 &middot; Capital 100&#8239;000 MAD "
                  "&middot; Siège : 5 Rue Ennoussour RDC, Casablanca")
# Ligne RIB (bénéficiaire · banque · RIB · BIC) — littéral historique exact.
ENT_RIB_LINE = ('<strong style="color:{cg7}">TAQINOR SOLUTION</strong> '
                '· Saham Bank · '
                'RIB 022 780 0002720029379418 74 '
                '· BIC SGMBMAMCXXX')

# Snapshot des DÉFAUTS Taqinor : les ENT_* actifs sont réinitialisés depuis eux
# au début de chaque rendu (sous _RENDER_LOCK) avant surcharge par le profil,
# pour qu'aucune identité de tenant ne persiste d'un rendu au suivant.
_ENT_DEFAULT_NOM_MARQUE = ENT_NOM_MARQUE
_ENT_DEFAULT_CONTACT_LINE = ENT_CONTACT_LINE
_ENT_DEFAULT_ETUDE_CONTACT = ENT_ETUDE_CONTACT
_ENT_DEFAULT_LEGAL_LINE = ENT_LEGAL_LINE
_ENT_DEFAULT_RIB_LINE = ENT_RIB_LINE


def _apply_entreprise(ent):
    """DC1 — pose les variables d'identité société depuis data["entreprise"].

    ``ent`` est le dict renvoyé par ``parametres.selectors.company_identity``.
    Toute valeur vide laisse le littéral Taqinor historique (byte-identique) ;
    dès qu'une valeur est renseignée, elle remplace la ligne correspondante et
    le devis d'un autre tenant n'affiche plus jamais l'identité de Taqinor.
    """
    global ENT_NOM_MARQUE, ENT_CONTACT_LINE, ENT_LEGAL_LINE, ENT_RIB_LINE
    global ENT_ETUDE_CONTACT
    global CA
    # Réinitialise TOUJOURS depuis les défauts d'abord : pas de fuite d'un rendu
    # précédent (les globals sont mutés sous _RENDER_LOCK).
    ENT_NOM_MARQUE = _ENT_DEFAULT_NOM_MARQUE
    ENT_CONTACT_LINE = _ENT_DEFAULT_CONTACT_LINE
    ENT_ETUDE_CONTACT = _ENT_DEFAULT_ETUDE_CONTACT
    ENT_LEGAL_LINE = _ENT_DEFAULT_LEGAL_LINE
    ENT_RIB_LINE = _ENT_DEFAULT_RIB_LINE
    CA = _CA_DEFAULT
    if not isinstance(ent, dict):
        return
    nom = (ent.get("nom") or "").strip()
    adresse = (ent.get("adresse") or "").strip()
    email = (ent.get("email") or "").strip()
    tel = (ent.get("telephone") or "").strip()
    ice = (ent.get("ice") or "").strip()
    rc = (ent.get("rc") or "").strip()
    if_ = (ent.get("identifiant_fiscal") or "").strip()
    patente = (ent.get("patente") or "").strip()
    rib = (ent.get("rib") or "").strip()
    banque = (ent.get("banque") or "").strip()

    # Aucun champ d'identité renseigné → on ne touche à rien (byte-identique).
    if not any([nom, adresse, email, tel, ice, rc, if_, patente, rib, banque]):
        return

    if nom:
        ENT_NOM_MARQUE = _esc(nom.upper())

    # Ligne de contact : reconstruite dès qu'un contact est fourni.
    if email or tel:
        parts = [p for p in (_esc(email), _esc(tel)) if p]
        ENT_CONTACT_LINE = " &nbsp;&#183;&nbsp; ".join(parts)

    # Pied de page ÉTUDE : reconstruit dès QU'UN contact quelconque est fourni
    # (email, site OU téléphone) — même sémantique que la ligne de contact
    # ci-dessus (SCA27). On préfère email + site ; si les deux manquent mais
    # qu'un téléphone est présent (profil PME tel-seul), on affiche le tél afin
    # de ne JAMAIS laisser le littéral fondateur près d'un nom de tenant. Seul
    # le cas « aucun contact » (nom-seul / DC1) garde le défaut Taqinor, donc le
    # rendu du fondateur (email+tél+site) reste byte-identique.
    site_web = (ent.get("site_web") or "").strip()
    if email or tel or site_web:
        etude_parts = [p for p in (_esc(email), _esc(site_web)) if p]
        if not etude_parts and tel:
            etude_parts = [_esc(tel)]
        ENT_ETUDE_CONTACT = " &nbsp;·&nbsp; ".join(etude_parts)

    # Ligne légale : raison sociale · RC · ICE · IF · Patente · Siège.
    legal_bits = []
    if nom:
        legal_bits.append(_esc(nom))
    if rc:
        legal_bits.append("RC " + _esc(rc))
    if ice:
        legal_bits.append("ICE " + _esc(ice))
    if if_:
        legal_bits.append("IF " + _esc(if_))
    if patente:
        legal_bits.append("Patente " + _esc(patente))
    if adresse:
        legal_bits.append("Siège : " + _esc(adresse))
    if legal_bits:
        ENT_LEGAL_LINE = " &middot; ".join(legal_bits)

    # Ligne RIB : reconstruite dès qu'un RIB ou une banque est fourni.
    if rib or banque:
        benef = _esc(nom) if nom else "Virement"
        rib_bits = [f'<strong style="color:{{cg7}}">{benef}</strong>']
        if banque:
            rib_bits.append(_esc(banque))
        if rib:
            rib_bits.append("RIB " + _esc(rib))
        ENT_RIB_LINE = " · ".join(rib_bits)

    # Couleur de charte (accent) — surcharge CA quand un hex valide est fourni.
    couleur = (ent.get("couleur_principale") or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", couleur):
        CA = couleur


def _apply_seller(seller):
    """QG7 — ajoute le contact du CRÉATEUR du devis à la ligne de coordonnées.

    ``seller`` = {"nom", "telephone"} posé par le builder depuis
    ``Devis.created_by`` (repli téléphone société si l'utilisateur n'en a pas).
    On AJOUTE « · Votre conseiller : Nom — tél » à ``ENT_CONTACT_LINE`` déjà
    posée par ``_apply_entreprise`` (donc appelé APRÈS). Données seulement : pas
    de nouvelle structure de gabarit. Seller vide → aucune modification
    (byte-identique au devis d'aujourd'hui)."""
    global ENT_CONTACT_LINE
    if not isinstance(seller, dict):
        return
    nom = (seller.get("nom") or "").strip()
    tel = (seller.get("telephone") or "").strip()
    if not nom:
        return
    bits = f"Votre conseiller&#160;: {_esc(nom)}"
    if tel:
        bits += f" &#8212; {_esc(tel)}"
    ENT_CONTACT_LINE = f"{ENT_CONTACT_LINE} &nbsp;&#183;&nbsp; {bits}"


# ═══════════════════════════════════════════════════════════════════════════════
# DOC_TEXTS — portions de TEXTE éditables du devis (D2/N60/N67/N26/N59)
# ═══════════════════════════════════════════════════════════════════════════════
# Chaque entrée est un fragment de texte INTÉRIEUR (le balisage/les styles qui
# l'entourent restent codés en dur et inchangés). Le DÉFAUT ci-dessous reproduit
# EXACTEMENT le littéral historique — au caractère et à l'entité HTML près — donc
# tant qu'aucun réglage société n'est édité, le PDF est OCTET-POUR-OCTET identique.
# Les valeurs portent les entités HTML telles quelles (&#8217; &#8201; &#160;
# &#37; &#233; …) car le moteur n'échappe pas ces fragments : un défaut en
# Unicode brut casserait l'identité du HTML rendu (cf. le test garantie 30 ans).
# Les marqueurs {acompte}/{materiel}/{solde}/{tva_note} des puces CGV sont
# substitués par le moteur (PAY_A/PAY_M/PAY_S/TVA_NOTE) — défauts inchangés.
DEFAULT_DOC_TEXTS = {
    # D2/N60 — validité de l'offre (3 emplacements, libellés distincts).
    "validite_badge_p1": "Validit&#233;&#160;: 30 jours",
    "validite_onepage": "&#183; Validit&#233;&#160;: 30 jours",
    # D2/N60 — conditions générales (titre + 7 puces ; placeholders substitués).
    "cgv_titre": "Conditions générales du devis",
    "cgv_bullets": [
        "Validité de l&#8217;offre&#160;: 30 jours",
        "Acompte à la commande&#160;: {acompte}&#37;",
        "{materiel}&#37; à la réception du matériel",
        "{solde}&#37; après la mise en marche",
        "Délai d&#8217;installation&#160;: 7–14 jours ouvrés",
        "{tva_note}",
        "Tarifs de référence&#160;: barème ONEE/SRM",
    ],
    # N67 — garanties (titre, détail, libellé performance). Entités HTML EXACTES.
    "garantie_titre": "Garanties jusqu&#8217;à 30 ans",
    "garantie_detail": ("Structure 20 ans, panneaux 12 ans produit + 30 ans "
                        "performance (87,4&#8201;%), onduleur 10 ans. "
                        "Sérénité totale."),
    "garantie_perf_label": "Performance panneau (87,4&#8201;%)",
    # D2/N60 — bloc « Bon pour accord » (titre + mention manuscrite).
    "bpa_titre": "Bon pour accord",
    "bpa_mention": ("Lu et approuvé — Signature précédée "
                    "de « Bon pour accord »"),
    # N26 — tampon d'acceptation. Rendu UNIQUEMENT quand le devis est accepté
    # (nom + date présents) ; vide sinon → byte-identique au devis d'aujourd'hui.
    # Marqueurs {date}/{nom} substitués par le moteur.
    "acceptance_stamp": "Accepté le {date} par {nom}",
}
# Réglages effectifs (fusion défaut + surcharges société) — posés par
# generate_premium_pdf depuis data["doc_texts"]. Défaut = littéraux historiques.
DOC_TEXTS = dict(DEFAULT_DOC_TEXTS)
# N26 — métadonnées d'acceptation (posées côté serveur, jamais du corps client).
ACCEPTE_PAR_NOM = ""
DATE_ACCEPTATION = ""
# QF3 — bloc « Comment nous calculons vos économies » (méthode + exemple), posé
# depuis data["savings_method"]. Vide → aucun bloc rendu (byte-identique).
SAVINGS_METHOD = None


def _savings_method_html():
    """QF3 — bloc « Comment nous calculons vos économies » (méthode + exemple
    chiffré compact). Rendu UNIQUEMENT quand data["savings_method"] est fourni.
    Aucune donnée fabriquée : le texte vient du builder (une seule source)."""
    sm = SAVINGS_METHOD
    if not isinstance(sm, dict) or not sm.get("ligne_methode"):
        return ""
    methode = _esc(sm.get("ligne_methode", ""))
    exemple = sm.get("exemple")
    approx = " (approximatif)" if sm.get("approximatif") else ""
    ex_html = ""
    if exemple:
        ex_html = (
            f'<div style="margin-top:4px;font-size:8pt;color:{CN};font-weight:700;">'
            f'{_esc(exemple)}{approx}</div>')
    return (
        f'<div style="background:{CG1};border-radius:8px;padding:7px 12px;'
        f'border:1px solid {CG2};border-left:4px solid {CA};margin-bottom:5px;">'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};'
        f'text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px;">'
        f'Comment nous calculons vos &#233;conomies</div>'
        f'<div style="font-size:7.5pt;color:{CG7};line-height:1.4;">{methode}</div>'
        f'{ex_html}</div>')


# QK4 — bloc « Nos hypothèses » (transparence des hypothèses d'économies), posé
# depuis data["hypotheses"]. Vide → aucun bloc rendu (byte-identique).
HYPOTHESES = None


def _hypotheses_html():
    """QK4 — bloc « Nos hypothèses » : liste des hypothèses derrière les
    économies (tarif, source barème, autoconsommation-first loi 82-21, base de
    production). Rendu UNIQUEMENT quand data["hypotheses"] est fourni. Le texte
    vient du builder (une seule source) ; aucun chiffre inventé ici."""
    h = HYPOTHESES
    if not isinstance(h, dict):
        return ""
    items = [i for i in (h.get("items") or []) if i]
    if not items:
        return ""
    titre = _esc(h.get("titre") or "Nos hypothèses")
    lis = "".join(
        f'<li style="font-size:7.3pt;color:{CG7};padding-left:11px;'
        f'position:relative;line-height:1.35;margin-bottom:1px;">'
        f'<span style="position:absolute;left:0;color:{CA};">&#183;</span>'
        f'{_esc(i)}</li>'
        for i in items)
    return (
        f'<div style="background:{CG1};border-radius:8px;padding:7px 12px;'
        f'border:1px solid {CG2};border-left:4px solid {CG4};margin-bottom:5px;">'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};'
        f'text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px;">'
        f'{titre}</div>'
        f'<ul style="list-style:none;padding:0;margin:0;">{lis}</ul></div>')


# QK3 — bloc financement (indicatif, QJ12), posé depuis data["financing"].
# Vide → aucun bloc rendu (byte-identique).
FINANCING = None

# QJ30 — multi-propriétés (rendu). NB_PROPRIETES = ×N villas identiques (défaut
# 1 → aucun rendu). MULTI_VILLA = sections par-villa (sous-totaux + total
# général). Vides → mise en page à plat d'aujourd'hui (byte-identique).
NB_PROPRIETES = 1
DISPLAY_TOTAL_MULTI = None
MULTI_VILLA = None


def _multi_proprietes_line_html():
    """QJ30 (A) — ligne « × N propriétés identiques » + total mis à l'échelle.
    Rendu UNIQUEMENT quand NB_PROPRIETES > 1. Aucun chiffre inventé : le total
    multi vient du builder (total unitaire × N)."""
    if not NB_PROPRIETES or NB_PROPRIETES <= 1:
        return ""
    total_txt = ""
    if DISPLAY_TOTAL_MULTI:
        total_txt = (f' &#8212; total pour {NB_PROPRIETES} propriétés&#160;: '
                     f'<b>{fmt(DISPLAY_TOTAL_MULTI)}</b>')
    return (
        f'<div style="background:{CAL};border:1px solid {CA};border-radius:8px;'
        f'padding:6px 12px;margin-bottom:5px;font-size:8.5pt;color:{CN};">'
        f'&#215;&#160;{NB_PROPRIETES} propriétés identiques'
        f'{total_txt}</div>')


def _multi_villa_html():
    """QJ30 (B) — sections par-villa (sous-totaux) + total général, dans UN
    document. Rendu UNIQUEMENT quand MULTI_VILLA est fourni. Les montants
    viennent du builder/selector (une source) ; jamais de prix d'achat/marge."""
    mv = MULTI_VILLA
    if not isinstance(mv, dict) or not mv.get("groupes"):
        return ""
    rows = ""
    for g in mv["groupes"]:
        t = g.get("totaux") or {}
        rows += (
            f'<tr><td style="padding:3px 8px;color:{CG7};">{_esc(g.get("label", ""))}</td>'
            f'<td style="padding:3px 8px;text-align:right;color:{CG7};">'
            f'{_fmt2(t.get("ht_net", 0))}</td>'
            f'<td style="padding:3px 8px;text-align:right;font-weight:700;'
            f'color:{CN};white-space:nowrap;">{fmt(t.get("ttc", 0))}</td></tr>')
    gt = mv.get("grand_total") or {}
    rows += (
        f'<tr style="background:{CN};"><td style="padding:4px 8px;color:{CA};'
        f'font-weight:800;">Total général</td>'
        f'<td style="padding:4px 8px;text-align:right;color:{CA};font-weight:800;">'
        f'{_fmt2(gt.get("ht_net", 0))}</td>'
        f'<td style="padding:4px 8px;text-align:right;color:{CA};font-weight:800;'
        f'white-space:nowrap;">{fmt(gt.get("ttc", 0))}</td></tr>')
    return (
        f'<div style="border:1px solid {CG2};border-radius:8px;overflow:hidden;'
        f'margin-bottom:5px;">'
        f'<div style="background:{CG1};padding:5px 12px;font-size:9pt;'
        f'font-weight:700;color:{CN};text-transform:uppercase;'
        f'letter-spacing:.8px;">Détail par propriété</div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:8pt;">'
        f'<thead><tr>'
        f'<th style="padding:3px 8px;text-align:left;color:{CG4};font-size:6.5pt;'
        f'text-transform:uppercase;">Propriété</th>'
        f'<th style="padding:3px 8px;text-align:right;color:{CG4};font-size:6.5pt;'
        f'text-transform:uppercase;">Total HT</th>'
        f'<th style="padding:3px 8px;text-align:right;color:{CG4};font-size:6.5pt;'
        f'text-transform:uppercase;">Total TTC</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>')


def _financing_html():
    """QK3 — bloc « Financement possible » (mensualité indicative + programme).
    Rendu UNIQUEMENT quand data["financing"] est fourni (QJ12). Indicatif ; le
    texte vient du builder, jamais de prix d'achat/marge."""
    f = FINANCING
    if not isinstance(f, dict) or not f.get("indicatif"):
        return ""
    credit = f.get("credit") or {}
    mens = credit.get("mensualite")
    if not mens:
        return ""
    mens_txt = f"{int(round(mens)):,}".replace(",", " ")
    duree_ans = round((credit.get("duree_mois") or 0) / 12)
    prog = _esc(credit.get("programme_nom") or "crédit vert")
    comp = f.get("onee_comparison") or {}
    comp_txt = ""
    if comp.get("show") and comp.get("message"):
        comp_txt = (f'<div style="margin-top:3px;font-size:7.3pt;color:{CGR};'
                    f'font-weight:700;">{_esc(comp["message"])}</div>')
    return (
        f'<div style="background:{CG1};border-radius:8px;padding:7px 12px;'
        f'border:1px solid {CG2};border-left:4px solid {CGR};margin-bottom:5px;">'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};'
        f'text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px;">'
        f'Financement possible</div>'
        f'<div style="font-size:7.5pt;color:{CG7};line-height:1.4;">'
        f'À partir de ≈ <b>{mens_txt} MAD/mois</b> sur {duree_ans} ans '
        f'({prog}) — indicatif, à confirmer avec votre banque.</div>'
        f'{comp_txt}</div>')


def _doc_text(key):
    """Fragment de texte éditable `key`, repli sur le littéral historique."""
    val = DOC_TEXTS.get(key)
    if val is None:
        return DEFAULT_DOC_TEXTS.get(key, "")
    return val


def _cgv_bullets_html():
    """Puces CGV éditables rendues avec le MÊME enrobage <li> qu'avant.

    Les marqueurs {acompte}/{materiel}/{solde}/{tva_note} sont substitués par
    les valeurs dynamiques (PAY_A/PAY_M/PAY_S/TVA_NOTE). Défaut → puces
    identiques au caractère près.
    """
    bullets = _doc_text("cgv_bullets") or DEFAULT_DOC_TEXTS["cgv_bullets"]
    out = ""
    for raw in bullets:
        try:
            txt = raw.format(acompte=PAY_A, materiel=PAY_M, solde=PAY_S,
                             tva_note=TVA_NOTE)
        except (KeyError, IndexError, ValueError):
            txt = raw
        # Enrobage <li> + indentation/retours IDENTIQUES au bloc historique
        # (newline + 8 espaces avant chaque puce) → HTML byte-identique au défaut.
        out += (f'\n        <li style="font-size:12px;color:{CG7};'
                f'padding-left:12px;position:relative;line-height:1.4;">'
                f'<span style="position:absolute;left:0;color:{CA};'
                f'font-size:11pt;line-height:1.1;">·</span>{txt}</li>')
    return out + "\n      "


def _acceptance_stamp_html():
    """Tampon « Accepté le … par … » — N26.

    Rendu UNIQUEMENT lorsque nom ET date d'acceptation sont posés (devis
    accepté). Sinon chaîne VIDE → bloc « Bon pour accord » byte-identique.
    """
    nom = (ACCEPTE_PAR_NOM or "").strip()
    date = (DATE_ACCEPTATION or "").strip()
    if not nom or not date:
        return ""
    tmpl = _doc_text("acceptance_stamp") or DEFAULT_DOC_TEXTS["acceptance_stamp"]
    try:
        txt = tmpl.format(date=date, nom=nom)
    except (KeyError, IndexError, ValueError):
        txt = tmpl
    return (f'<div style="margin-bottom:6px;display:inline-block;'
            f'background:{CAL};border:1px solid {CA};border-radius:6px;'
            f'padding:4px 10px;font-size:8pt;font-weight:700;color:{CN};">'
            f'{txt}</div>')


# ── SVG equipment icons ──────────────────────────────────────────────────────
_SVG = {
"onduleur":     '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#1A2B4A"/><rect x="6" y="8" width="28" height="20" rx="3" fill="none" stroke="#F5A623" stroke-width="2"/><circle cx="14" cy="18" r="4" fill="none" stroke="#F5A623" stroke-width="1.5"/><path d="M22 14 L28 18 L22 22" fill="none" stroke="#F5A623" stroke-width="1.5" stroke-linejoin="round"/><rect x="10" y="30" width="20" height="3" rx="1.5" fill="#F5A623" opacity="0.6"/></svg>',
"panneaux":     '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#004B87"/><rect x="5" y="10" width="30" height="20" rx="2" fill="none" stroke="white" stroke-width="1.5"/><line x1="5" y1="20" x2="35" y2="20" stroke="white" stroke-width="1"/><line x1="18" y1="10" x2="18" y2="30" stroke="white" stroke-width="1"/><line x1="27" y1="10" x2="27" y2="30" stroke="white" stroke-width="1"/><circle cx="20" cy="5" r="3" fill="#F5A623"/><line x1="20" y1="8" x2="20" y2="10" stroke="#F5A623" stroke-width="1.5"/></svg>',
"batterie":     '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#FF6B00"/><rect x="5" y="12" width="26" height="16" rx="3" fill="none" stroke="white" stroke-width="2"/><rect x="31" y="16" width="4" height="8" rx="2" fill="white"/><rect x="8" y="15" width="6" height="10" rx="1" fill="white" opacity="0.9"/><rect x="17" y="15" width="6" height="10" rx="1" fill="white" opacity="0.6"/></svg>',
"smart meter":  '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#2C5F8A"/><rect x="8" y="8" width="24" height="24" rx="3" fill="none" stroke="white" stroke-width="1.5"/><path d="M14 20 Q20 12 26 20" fill="none" stroke="#F5A623" stroke-width="2"/><circle cx="20" cy="20" r="2" fill="#F5A623"/><line x1="20" y1="22" x2="20" y2="26" stroke="white" stroke-width="1.5"/></svg>',
"wifi":         '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#2C5F8A"/><path d="M10 18 Q20 10 30 18" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M13 22 Q20 16 27 22" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M16 26 Q20 22 24 26" fill="none" stroke="#F5A623" stroke-width="2" stroke-linecap="round"/><circle cx="20" cy="30" r="2" fill="#F5A623"/></svg>',
"structures":   '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#64748B"/><path d="M5 30 L15 15 L25 22 L35 10" fill="none" stroke="white" stroke-width="2" stroke-linejoin="round"/><line x1="5" y1="30" x2="35" y2="30" stroke="#F5A623" stroke-width="2"/><line x1="15" y1="15" x2="15" y2="30" stroke="white" stroke-width="1" stroke-dasharray="2,2"/><line x1="25" y1="22" x2="25" y2="30" stroke="white" stroke-width="1" stroke-dasharray="2,2"/></svg>',
"socles":       '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#374151"/><rect x="8" y="28" width="24" height="4" rx="2" fill="#F5A623"/><rect x="12" y="20" width="16" height="4" rx="2" fill="white" opacity="0.8"/><rect x="16" y="13" width="8" height="5" rx="2" fill="white" opacity="0.6"/></svg>',
"accessoires":  '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#374151"/><circle cx="12" cy="15" r="4" fill="none" stroke="#F5A623" stroke-width="2"/><circle cx="28" cy="15" r="4" fill="none" stroke="white" stroke-width="2"/><circle cx="20" cy="28" r="4" fill="none" stroke="#F5A623" stroke-width="2"/><line x1="16" y1="15" x2="24" y2="15" stroke="white" stroke-width="1.5"/><line x1="14" y1="19" x2="18" y2="24" stroke="white" stroke-width="1.5"/><line x1="26" y1="19" x2="22" y2="24" stroke="white" stroke-width="1.5"/></svg>',
"tableau":      '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#1A2B4A"/><rect x="7" y="7" width="26" height="26" rx="3" fill="none" stroke="#F5A623" stroke-width="2"/><rect x="11" y="11" width="8" height="8" rx="1" fill="#F5A623" opacity="0.8"/><rect x="21" y="11" width="8" height="8" rx="1" fill="white" opacity="0.6"/><rect x="11" y="21" width="8" height="8" rx="1" fill="white" opacity="0.6"/><rect x="21" y="21" width="8" height="8" rx="1" fill="#F5A623" opacity="0.4"/></svg>',
"installation": '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#F5A623"/><path d="M28 8 C32 8 34 12 32 16 L18 30 C15 33 11 33 9 30 C7 27 7 23 10 21 L24 7 C25.5 6.5 28 8 28 8Z" fill="white"/><circle cx="11" cy="29" r="3" fill="#F5A623"/></svg>',
"transport":    '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#16A34A"/><rect x="3" y="14" width="22" height="13" rx="2" fill="white" opacity="0.9"/><path d="M25 19 L34 19 L37 25 L37 27 L25 27 Z" fill="white" opacity="0.9"/><circle cx="9" cy="30" r="3.5" fill="#16A34A" stroke="white" stroke-width="2"/><circle cx="29" cy="30" r="3.5" fill="#16A34A" stroke="white" stroke-width="2"/></svg>',
"suivi":        '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect width="40" height="40" rx="6" fill="#6B7280"/><rect x="6" y="9" width="28" height="24" rx="3" fill="none" stroke="white" stroke-width="1.5"/><rect x="6" y="9" width="28" height="8" rx="3" fill="white" opacity="0.15"/><line x1="13" y1="6" x2="13" y2="12" stroke="#F5A623" stroke-width="2" stroke-linecap="round"/><line x1="27" y1="6" x2="27" y2="12" stroke="#F5A623" stroke-width="2" stroke-linecap="round"/><path d="M11 24 L16 28 L29 19" fill="none" stroke="#F5A623" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
}

_BRAND_C = {
    "huawei":   ("#CF0A2C", "#fff"),
    "canadian": ("#004B87", "#fff"),
    "canadien": ("#004B87", "#fff"),
    "deye":     ("#FF6B00", "#fff"),
    "deyness":  ("#FF6B00", "#fff"),
}

_GAR = {
    "onduleur":"10 ans","panneaux":"12 ans","batterie":"10 ans","structures":"20 ans",
    "smart meter":"2 ans","wifi":"2 ans","tableau":"\u2014","installation":"\u2014",
    "transport":"\u2014","accessoires":"\u2014","socles":"\u2014","suivi":"\u2014",
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def fmt(v):
    """Format as French currency amount: 52\u202f650\u00a0MAD (or DEVISE).

    FG52 \u2014 utilise le global DEVISE (positionn\u00e9 par _render_premium_pdf depuis
    data["devise"]) pour afficher la bonne devise sur le PDF. Le comportement
    reste byte-identique pour MAD (d\u00e9faut = comportement historique).
    """
    try:
        return f"{int(round(float(v))):,}".replace(",", "\u202f") + "\u00a0" + DEVISE
    except Exception:
        return str(v)

def fnum(v):
    """Format number with French thin-space thousands separator."""
    try:
        return f"{int(round(float(v))):,}".replace(",", "\u202f")
    except Exception:
        return str(v)

def kwc_fr(v):
    """Format kWc value with French decimal comma: 10,65"""
    return f"{v:.2f}".replace(".", ",")

def b64(src):
    if isinstance(src, (str, Path)):
        raw = open(src, "rb").read()
        ext = str(src).rsplit(".", 1)[-1].lower()
        mime = "image/png" if ext == "png" else "image/jpeg"
    else:
        src.seek(0); raw = src.read(); mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

def svg_uri(svg_str):
    return "data:image/svg+xml;base64," + base64.b64encode(svg_str.encode()).decode()

def icon_img(des, _mar=""):
    d = des.lower()
    key = None
    if   "panneaux"     in d: key = "panneaux"
    elif "batterie"     in d: key = "batterie"
    elif "smart meter"  in d: key = "smart meter"
    elif "wifi" in d or "dongle" in d: key = "wifi"
    elif "onduleur"     in d: key = "onduleur"
    elif "structures"   in d: key = "structures"
    elif "socles"       in d: key = "socles"
    elif "accessoires"  in d: key = "accessoires"
    elif "tableau"      in d: key = "tableau"
    elif "installation" in d: key = "installation"
    elif "transport"    in d: key = "transport"
    elif "suivi"        in d: key = "suivi"
    svg = _SVG.get(key, _SVG["accessoires"])
    # Size via CSS (not width/height attrs): WeasyPrint ignores the attributes for
    # an SVG data-URI without an intrinsic size and would render it huge. The
    # per-row scale logic (.eq .ti img {...!important}) still overrides this.
    return (f'<img src="{svg_uri(svg)}" width="36" height="36" '
            f'style="width:36px;height:36px;border-radius:5px;display:block;">')

def badge(mar):
    if not mar or mar.lower() in ("", "nan"): return ""
    bg, fg = CNM, "#fff"
    for k, (b_, f_) in _BRAND_C.items():
        if k in mar.lower(): bg, fg = b_, f_; break
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border-radius:3px;'
            f'padding:1px 5px;font-size:5.5pt;font-weight:700;vertical-align:middle;">{mar}</span>')

def logo_html(h="36px"):
    """Dark logo for pages 2-3 navy headers — transparent, matching page 1 style."""
    try:
        b64_data = _logo_dark_b64()
    except Exception:
        b64_data = None
    if b64_data:
        return f'<img src="data:image/png;base64,{b64_data}" alt="TAQINOR" style="height:{h};width:auto;object-fit:contain;">'
    return (f'<span style="font-size:15pt;font-weight:900;letter-spacing:1px;color:white;">'
            f'TAQIN<span style="color:{CA};">&#9728;</span>R</span>')

def logo_badge_p1():
    """Navy badge for page 1 white header."""
    p = ASSET_DIR / "logo.png"
    if p.exists():
        return f'<img src="{b64(p)}" alt="TAQINOR" style="height:44px;object-fit:contain;">'
    return f'''<div style="background:{CN};border-radius:8px;padding:7px 14px;display:inline-flex;flex-direction:column;align-items:flex-start;">
      <div style="font-size:14pt;font-weight:900;color:white;letter-spacing:1px;line-height:1.1;">TAQIN<span style="color:{CA};">&#9728;</span>R</div>
      <div style="font-size:5pt;letter-spacing:2.5px;color:{CA};font-weight:700;text-transform:uppercase;margin-top:1px;">TAQA&#183;INNOVATION&#183;NOR</div>
    </div>'''

def _logo_dark_b64():
    """Return base64 PNG of logo.png with white bg removed and dark pixels → white."""
    from PIL import Image
    p = ASSET_DIR / "logo.png"
    if not p.exists():
        return None
    img = Image.open(p).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lightness = (r + g + b) / 765.0
    # Near-white → transparent (removes white background)
    white = lightness > 0.88
    arr[white, 3] = 0
    # Dark pixels (navy/black text) → white for visibility on dark bg
    dark = (~white) & (lightness < 0.42)
    arr[dark, 0] = 255; arr[dark, 1] = 255; arr[dark, 2] = 255
    from PIL import Image as _I
    buf = io.BytesIO()
    _I.fromarray(arr.astype(np.uint8), 'RGBA').save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()

def logo_p1_dark():
    """Logo for dark header — white bg removed, dark pixels → white, rendered on navy."""
    try:
        b64_data = _logo_dark_b64()
    except Exception:
        b64_data = None
    if b64_data:
        return (f'<img src="data:image/png;base64,{b64_data}" alt="TAQINOR" '
                f'style="height:144px;width:auto;object-fit:contain;display:block;">')
    # Fallback: text on dark background
    return (f'<div style="display:inline-block;">'
            f'<div style="font-size:17px;font-weight:900;color:white;letter-spacing:1px;line-height:1.1;">'
            f'TAQIN<span style="color:{CA};">&#9733;</span>R</div>'
            f'</div>')

def footer_p1():
    """Page 1 footer — white background."""
    return (f'<div style="background:white;padding:7px 24px;flex-shrink:0;display:flex;'
            f'align-items:center;justify-content:space-between;border-top:1px solid {CG2};">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>'
            f'<div style="font-size:7pt;color:#888888;text-align:center;">'
            f'{ENT_CONTACT_LINE}</div>'
            f'<div style="font-size:7pt;color:#888888;">Page 1&nbsp;/&nbsp;{PAGES_TOTAL} &nbsp;|&nbsp; R\u00e9f.&nbsp;{REF}</div>'
            f'</div>')

def footer(n, total=None):
    """Pages 2-3 footer — dark navy."""
    total = total or PAGES_TOTAL
    return (f'<div style="background:{CN};padding:7px 24px;flex-shrink:0;display:flex;'
            f'align-items:center;justify-content:space-between;">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>'
            f'<div style="font-size:7pt;color:#888;text-align:center;">'
            f'{ENT_CONTACT_LINE}</div>'
            f'<div style="font-size:7pt;color:#888;">Page {n}&nbsp;/&nbsp;{total} &nbsp;|&nbsp; R\u00e9f.&nbsp;{REF}</div>'
            f'</div>')

def footer_p3(extra_style=""):
    """Page 3 footer — dark navy + legal identity line."""
    return (f'<div style="{extra_style}background:{CN};padding:6px 24px 5px;flex-shrink:0;">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>'
            f'<div style="font-size:7pt;color:#888;text-align:center;">'
            f'{ENT_CONTACT_LINE}</div>'
            f'<div style="font-size:7pt;color:#888;">Page {PAGE3_NUM}&nbsp;/&nbsp;{PAGES_TOTAL} &nbsp;|&nbsp; R\u00e9f.&nbsp;{REF}</div>'
            f'</div>'
            f'<div style="font-size:7.5px;color:#888;text-align:center;font-style:italic;">'
            f'{ENT_LEGAL_LINE}'
            f'</div>'
            f'</div>')

# ── Data loading ─────────────────────────────────────────────────────────────
def load_equip(devis_id):
    """Load Option 1 equipment from devis_history.json."""
    f = BASE_DIR / "devis_history.json"
    if not f.exists(): return [], []
    try:
        with open(f, "r", encoding="utf-8") as fh: h = json.load(fh)
        e = h.get(str(devis_id), {})
        sys.path.insert(0, str(BASE_DIR))
        import pandas as pd
        from utils import sanitize_df
        def parse(recs):
            if not recs: return []
            df = pd.DataFrame(recs)
            try: df = sanitize_df(df)
            except Exception: pass
            cols = df.columns.tolist()
            def col(hints):
                for h in hints:
                    for c in cols:
                        if h in c.lower(): return c
                return None
            dc = col(["d\u00e9signation","designation","signation","design"])
            qc = col(["quantit\u00e9","quantit","qty","qt\u00e9"])
            pc = col(["unit. ttc","unit.ttc","unit ttc","prix unit","unit_ttc","prix_unit"])
            mc = col(["marque"])
            out = []
            for _, r in df.iterrows():
                qty = float(r[qc]) if qc else 0
                if qty <= 0: continue
                out.append({"designation": str(r[dc]).strip() if dc else "",
                             "marque":     str(r[mc]).strip() if mc else "",
                             "quantite":   qty,
                             "prix_unit_ttc": float(r[pc]) if pc else 0})
            return out
        return parse(e.get("df_sans", [])), parse(e.get("df_avec", []))
    except Exception:
        return [], []

# ── Charts ────────────────────────────────────────────────────────────────────
def _style_ax(fig, ax):
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#E5E7EB"); ax.spines["bottom"].set_color("#E5E7EB")
    ax.tick_params(colors=CG4, labelsize=8)
    ax.grid(axis="y", color="#F3F4F6", linewidth=0.8, zorder=0)

def make_chart_roi():
    # Ratio EXACTEMENT celui du cadre d'affichage (680×170 px = 4:1) et
    # rendu SANS recadrage : l'image remplit son cadre, nette, sans
    # letterboxing (WeasyPrint ne gère pas object-fit de façon fiable).
    fig, ax = plt.subplots(figsize=(13.6, 3.4), dpi=140)
    _style_ax(fig, ax)
    x = np.array(YEARS); ys = np.array(CUMUL_S); ya = np.array(CUMUL_A)
    ax.axhline(0, color="#D1D5DB", linewidth=1.0, linestyle="--", zorder=1)
    _show_s = SCENARIO != 'Avec batterie'
    _show_a = SCENARIO != 'Sans batterie'
    if _show_s:
        ax.fill_between(x, ys, 0, where=(ys >= 0), alpha=0.08, color=CNM, zorder=2)
        ax.plot(x, ys, color=CNM, linewidth=2.5, label="Sans batterie", zorder=4, solid_capstyle="round")
    if _show_a:
        ax.fill_between(x, ya, 0, where=(ya >= 0), alpha=0.08, color=CA,  zorder=2)
        ax.plot(x, ya, color=CA,  linewidth=2.5, label="Avec batterie",  zorder=4, solid_capstyle="round")
    _roi_pts = []
    if _show_s: _roi_pts.append((ROI_S, CUMUL_S, CNM, f"ROI ~{ROI_S} ans"))
    if _show_a: _roi_pts.append((ROI_A, CUMUL_A, CA,  f"ROI ~{ROI_A} ans"))
    _y_offsets = [15, -25]  # Sans batterie above, Avec batterie below
    for i, (roi, cumul, color, lbl) in enumerate(_roi_pts):
        yr = int(roi); fr = roi - yr
        yv = cumul[yr] + fr * (cumul[yr+1] - cumul[yr]) if yr < 25 else cumul[25]
        ax.scatter([roi], [yv], color=color, s=120, zorder=6, marker="*")
        yoff = _y_offsets[i] if i < len(_y_offsets) else 10
        ax.annotate(lbl, (roi, yv), xytext=(6, yoff), textcoords="offset points",
                    fontsize=8.5, color=color, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color=color, lw=0.8))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    ax.set_xlabel("Ann\u00e9es", fontsize=9, color=CG4, labelpad=4)
    ax.set_ylabel("Gain cumul\u00e9 (MAD)", fontsize=9, color=CG4, labelpad=4)
    ax.set_xlim(0, 25)
    leg = ax.legend(fontsize=9, frameon=True, loc="upper left", edgecolor="#E5E7EB", facecolor="white")
    leg.get_frame().set_linewidth(0.8)
    plt.tight_layout(pad=0.5)
    # PAS de bbox_inches="tight" : le recadrage changerait le ratio et
    # recréerait le letterboxing dans le cadre fixe.
    buf = io.BytesIO(); plt.savefig(buf, format="png", facecolor="white"); plt.close(fig)
    return b64(buf)

def make_chart_monthly():
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    # Real monthly bills from the simulator input
    _onee_m = FACTURES_M

    # Même ratio 4:1 que le cadre 680×170 — image pleine, jamais en vignette.
    fig, ax = plt.subplots(figsize=(13.6, 3.4), dpi=140)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#EAECF0"); ax.spines["bottom"].set_color("#EAECF0")
    ax.spines["left"].set_linewidth(0.8); ax.spines["bottom"].set_linewidth(0.8)

    x = np.arange(12)
    c_bar = "#B5C0CE"  # light steel-blue/grey for ONEE bill bars

    # Bars: ONEE bill — full-width, one per month
    ax.bar(x, _onee_m, 0.60, color=c_bar, alpha=0.60, zorder=2, linewidth=0)

    # Lines: Option 1 (navy) and/or Option 2 (amber) based on scenario
    _show_s = SCENARIO != 'Avec batterie'
    _show_a = SCENARIO != 'Sans batterie'
    if _show_s:
        ax.plot(x, ECO_S_M, color=CNM, linewidth=2.2, marker="o", markersize=5.5,
                markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CNM,
                zorder=4, solid_capstyle="round")
    if _show_a:
        ax.plot(x, ECO_A_M, color=CA,  linewidth=2.2, marker="o", markersize=5.5,
                markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CA,
                zorder=4, solid_capstyle="round")

    ax.set_xticks(x)
    ax.set_xticklabels(MONTHS, fontsize=9, color="#374151")
    ax.tick_params(axis="x", length=0, pad=5)
    ax.tick_params(axis="y", colors="#9BA3AE", labelsize=8)
    ax.set_ylabel("MAD / mois", fontsize=9, color="#9BA3AE", labelpad=6)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", "\u202f")))

    # Soft horizontal gridlines only — no vertical
    ax.grid(axis="y", color="#F0F2F5", linewidth=0.65, zorder=0)
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
    ax.set_xlim(-0.55, 11.55)

    # Custom legend handles: patch for bar, line+marker for each line series
    legend_handles = [Patch(facecolor=c_bar, alpha=0.60, label="Facture ONEE sans PV", linewidth=0)]
    if _show_s:
        legend_handles.append(Line2D([0], [0], color=CNM, linewidth=2.2, marker="o", markersize=5.5,
               markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CNM,
               label="\u00c9conomies Option\u00a01 \u2013 Sans batterie"))
    if _show_a:
        legend_handles.append(Line2D([0], [0], color=CA,  linewidth=2.2, marker="o", markersize=5.5,
               markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CA,
               label="\u00c9conomies Option\u00a02 \u2013 Avec batterie"))
    leg = ax.legend(handles=legend_handles, fontsize=8.5, frameon=True,
                    loc="upper center", bbox_to_anchor=(0.5, 1.20), ncol=3,
                    edgecolor="#E5E7EB", facecolor="white",
                    handlelength=1.6, handleheight=0.9,
                    borderpad=0.7, columnspacing=1.6)
    leg.get_frame().set_linewidth(0.8)

    plt.tight_layout(pad=0.4); fig.subplots_adjust(top=0.82)
    # Pas de recadrage : ratio fidèle au cadre 680×170 (pas de vignette).
    buf = io.BytesIO(); plt.savefig(buf, format="png", facecolor="white"); plt.close(fig)
    return b64(buf)

# ── Equipment rows ────────────────────────────────────────────────────────────
def _fmt2(v):
    """Two-decimal French money formatting: 1\u202f166,67."""
    return f"{v:,.2f}".replace(",", "\u202f").replace(".", ",")


def _item_pu_ht(it):
    """Per-line HT unit price (stored, or derived from the TTC)."""
    pu_ht = it.get("prix_unit_ht")
    if pu_ht is None:
        pu_ht = it["prix_unit_ttc"] / (1 + TVA_PCT / 100)
    return float(pu_ht)


def _desc_lines_html(it, max_lines, font_pt):
    """Indented detail lines under the designation (competitor style)."""
    desc = (it.get("description") or "").strip()
    if not desc:
        return ""
    lines = [ln.strip() for ln in desc.splitlines() if ln.strip()][:max_lines]
    return "".join(
        f'<div style="font-size:{font_pt}pt;color:{CG4};font-weight:400;'
        f'padding-left:6px;">\u2013 {ln}</div>'
        for ln in lines)


def _totals_block_rows(totaux, colspan):
    """Sous-total HT \u2192 Remise visible \u2192 Total HT \u2192 TVA \u2192 Total TTC.

    Renders the CANONICAL totals computed once by the builder \u2014 every page
    shows these exact figures (never re-derived, no rounding drift).
    """
    total_ht = totaux["ht_brut"]
    remise = totaux["remise"]
    net_ht = totaux["ht_net"]
    tva = totaux["tva"]
    ttc = totaux["ttc"]

    def row(label, value, navy=False, neg=False):
        color = CA if navy else (CGR if neg else CG7)
        bg = f"background:{CN};" if navy else f"background:{CG1};"
        weight = 800 if navy else 600
        return (f'<tr style="{bg}"><td></td>'
                f'<td colspan="{colspan}" style="text-align:right;color:{color};'
                f'font-weight:{weight};padding:3px 5px;">{label}</td>'
                f'<td style="text-align:right;color:{color};font-weight:{weight};'
                f'padding:3px 5px;white-space:nowrap;">{value}</td></tr>')

    rows = row("Sous-total HT", _fmt2(total_ht))
    if DISCOUNT_PCT > 0:
        pct = int(DISCOUNT_PCT) if DISCOUNT_PCT == int(DISCOUNT_PCT) else DISCOUNT_PCT
        rows += row(f"Remise ({pct}\u202f%)", "\u2212" + _fmt2(remise), neg=True)
        rows += row("Total HT", _fmt2(net_ht))
    # TVA \u00e9clat\u00e9e par taux (r\u00e9forme 10/20) \u2014 une ligne par taux pr\u00e9sent ;
    # un seul taux (devis historiques) \u2192 exactement l'ancienne ligne unique.
    buckets = totaux.get("tva_par_taux") or []
    if len(buckets) > 1:
        for b in buckets:
            r = int(b["taux"]) if b["taux"] == int(b["taux"]) else b["taux"]
            rows += row(f"TVA ({r}\u202f%)", _fmt2(b["montant"]))
    else:
        rate = buckets[0]["taux"] if buckets else TVA_PCT
        tva_pct = int(rate) if rate == int(rate) else rate
        rows += row(f"TVA ({tva_pct}\u202f%)", _fmt2(tva))
    rows += row("Total TTC", fmt(ttc), navy=True)
    return rows


def equip_rows(items, totaux, hi_bat=False):
    rows = ""
    for i, it in enumerate(items):
        des = it["designation"]; qty = it["quantite"]
        pu_ht = _item_pu_ht(it)
        mar = (it.get("marque") or "").strip()
        # Enrich panel designation with watt info
        if "panneaux" in des.lower() and WP:
            des = f"{des} {WP}\u00a0Wc"
        ico = icon_img(des, mar); bdg = badge(mar)
        gar = (it.get("garantie") or "").strip()
        if not gar:
            gar = "\u2014"
            for k, v in _GAR.items():
                if k in des.lower(): gar = v; break
        # Texte de garantie complet \u2014 il S'ENROULE dans la colonne, jamais
        # tronqu\u00e9 en plein mot.
        is_bat = "batterie" in des.lower() and hi_bat
        bg = f"background:{CAL};" if is_bat else (f"background:{CG1};" if i % 2 == 1 else "")
        qty_s = int(qty) if qty == int(qty) else qty
        desc_html = _desc_lines_html(it, max_lines=2, font_pt=5)
        dash = "\u2014"
        pu_ht_s = _fmt2(pu_ht) if pu_ht > 0 else dash
        tot_ht_s = _fmt2(qty * pu_ht) if pu_ht > 0 else dash
        taux = it.get("taux_tva", TVA_PCT)
        taux_s = f"{int(taux)}%" if taux == int(taux) else f"{taux}%"
        rows += (f'<tr style="{bg}"><td class="ti">{ico}</td>'
                 f'<td class="tl">{des}{"<br>" + bdg if bdg else ""}{desc_html}</td>'
                 f'<td class="tc" style="word-wrap:break-word;font-size:5pt;">{gar}</td>'
                 f'<td class="tc">{qty_s}</td>'
                 f'<td class="tr">{pu_ht_s}</td>'
                 f'<td class="tc" style="font-size:5.5pt;">{taux_s}</td>'
                 f'<td class="tr">{tot_ht_s}</td></tr>')
    rows += _totals_block_rows(totaux, colspan=5)
    return rows

# ── Global CSS ────────────────────────────────────────────────────────────────
CSS = f"""
{_font_face("DM Serif Display", 400, "normal", _DS400)}
{_font_face("DM Sans", 400, "normal", _DMSANS400)}
{_font_face("DM Sans", 500, "normal", _DMSANS500)}
{_font_face("DM Sans", 700, "normal", _DMSANS700)}
{_pf_face(700, _PF700)}
{_pf_face(400, _PF400)}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
html{{background:#FFFFFF !important;}}
body{{font-family:'DM Sans',sans-serif;font-size:9pt;color:{CG7};
  background:#FFFFFF !important;
  -webkit-print-color-adjust:exact;print-color-adjust:exact;}}
@page{{size:A4;margin:0;background:#FFFFFF;}}
.page{{width:210mm;height:297mm;overflow:hidden;break-after:page;display:flex;flex-direction:column;background:#FFFFFF !important;}}
.serif{{font-family:'DM Serif Display',Georgia,serif;}}
.hc-serif{{font-family:'Playfair Display','Palatino Linotype','Book Antiqua',Georgia,serif;}}
.eq{{width:100%;border-collapse:collapse;font-size:6.5pt;}}
.option-check{{color:#2e7d32;font-size:15px;font-weight:700;vertical-align:middle;margin-right:3px;}}
.eq th{{background:{CG1};color:{CG4};font-size:5.5pt;font-weight:700;text-transform:uppercase;
  letter-spacing:.5px;padding:4px 5px;border-bottom:1px solid {CG2};text-align:left;}}
.eq td{{padding:3px 4px;border-bottom:1px solid {CG2}80;vertical-align:middle;}}
.eq .ti{{width:44px;text-align:center;padding:2px 3px;}}
.eq .tl{{font-weight:500;}}
.eq .tc{{text-align:center;color:{CG4};}}
.eq .tr{{text-align:right;}}
/* page3-content: no individual page-break rules — handled by single wrapper */
"""

# ── PAGE 1 — exact match to v5 ──────────────────────────────────────────────
def page1():
    # Local formatters — use U+00A0 (NON-BREAKING SPACE) for reliable rendering in all fonts
    _s      = "\u00a0"
    ts      = f"{int(TOTAL_SANS):,}".replace(",", _s) + "\u00a0MAD"
    ta      = f"{int(TOTAL_AVEC):,}".replace(",", _s) + "\u00a0MAD"
    esa_mad = f"{int(ECO_S_ANN):,}".replace(",", _s) + "\u00a0MAD"
    eaa_mad = f"{int(ECO_A_ANN):,}".replace(",", _s) + "\u00a0MAD"
    pk      = f"{int(PROD_KWH):,}".replace(",", _s)
    # Scenario-aware option card visibility
    _s1   = 'display:none;' if SCENARIO == 'Avec batterie' else ''
    _s2   = 'display:none;' if SCENARIO == 'Sans batterie' else ''
    _both = not _s1 and not _s2
    # Espacement entre cartes par MARGE + padding droit du conteneur
    # compensé : WeasyPrint ne déduit pas l'espacement des enfants flex:1.
    _opt1_margin = 'margin-right:12px;' if _both else ''
    _opts_pad_right = 36 if _both else 24
    # Badge: position:absolute at the top of the card — does NOT shift price downwards
    _badge_css = (f'position:absolute;top:0;left:0;right:0;background:{CA};color:{CN};'
                  f'font-size:7pt;font-weight:700;letter-spacing:1px;padding:5px 9px;'
                  f'border-radius:4px 4px 0 0;text-transform:uppercase;text-align:center;')
    _r1   = (f'<div style="{_badge_css}">{SVG_STAR} RECOMMAND\u00c9</div>'
             if _both and RECOMMENDED == 'Sans batterie' else '')
    _r2   = (f'<div style="{_badge_css}">{SVG_STAR} RECOMMAND\u00c9</div>'
             if _both and RECOMMENDED == 'Avec batterie' else '')
    # Price display — crossed-out original + discount badge + new price when discount active
    if DISCOUNT_PCT > 0:
        _s_before = f"{int(TOTAL_SANS_BEFORE):,}".replace(",", _s) + "\u00a0MAD"
        _a_before = f"{int(TOTAL_AVEC_BEFORE):,}".replace(",", _s) + "\u00a0MAD"
        _disc_str = f"\u2212{int(DISCOUNT_PCT)}\u202f%"
        _ts_price = (
            f'<div style="font-size:10pt;color:{CG4};text-decoration:line-through;'
            f'opacity:0.75;margin-bottom:1px;white-space:nowrap;">{_s_before}</div>'
            f'<div style="margin-bottom:4px;">'
            f'<span style="background:{CA};color:{CN};border-radius:3px;padding:2px 8px;'
            f'font-size:6pt;font-weight:800;letter-spacing:0.5px;">{_disc_str}\u00a0REMISE</span>'
            f'</div>'
            f'<div class="serif" style="font-size:27pt;font-weight:400;color:{CGR};'
            f'line-height:1.0;letter-spacing:-0.5px;margin-bottom:2px;">'
            f'<span style="white-space:nowrap;">{ts}</span></div>'
        )
        _ta_price = (
            f'<div style="font-size:10pt;color:{CG4};text-decoration:line-through;'
            f'opacity:0.75;margin-bottom:1px;white-space:nowrap;">{_a_before}</div>'
            f'<div style="margin-bottom:4px;">'
            f'<span style="background:{CA};color:{CN};border-radius:3px;padding:2px 8px;'
            f'font-size:6pt;font-weight:800;letter-spacing:0.5px;">{_disc_str}\u00a0REMISE</span>'
            f'</div>'
            f'<div class="serif" style="font-size:27pt;font-weight:400;color:{CGR};'
            f'line-height:1.0;letter-spacing:-0.5px;margin-bottom:2px;">'
            f'<span style="white-space:nowrap;">{ta}</span></div>'
        )
    else:
        _ts_price = (
            f'<div class="serif" style="font-size:30pt;font-weight:400;color:{CN};'
            f'line-height:1.0;letter-spacing:-0.5px;margin-bottom:2px;">'
            f'<span style="white-space:nowrap;">{ts}</span></div>'
        )
        _ta_price = (
            f'<div class="serif" style="font-size:30pt;font-weight:400;color:{CN};'
            f'line-height:1.0;letter-spacing:-0.5px;margin-bottom:2px;">'
            f'<span style="white-space:nowrap;">{ta}</span></div>'
        )
    # Prix par kWc installé (résumé compétiteur) — sous chaque prix d'option
    _pkwc_s = f' &#183; soit {fmt(TOTAL_SANS / KWC)}/kWc' if KWC > 0 else ''
    _pkwc_a = f' &#183; soit {fmt(TOTAL_AVEC / KWC)}/kWc' if KWC > 0 else ''
    # Puces générées depuis l'équipement RÉEL de chaque option (jamais de
    # texte boilerplate qui contredirait la liste d'équipements).
    _sb_lis = "".join(f"<li>{SVG_CHECK}{b}</li>" for b in SANS_BULLETS) or \
        f"<li>{SVG_CHECK}Équipement détaillé en page 2</li>"
    _ab_lis = "".join(f"<li>{SVG_CHECK}{b}</li>" for b in AVEC_BULLETS) or \
        f"<li>{SVG_CHECK}Équipement détaillé en page 2</li>"
    # KPI economies card — scenario-aware
    if SCENARIO == 'Sans batterie':
        _eco_val   = f'<span style="white-space:nowrap;">{esa_mad}</span>'
        _eco_size  = "17pt"
        _eco_sub   = "&#233;conomies par an"
    elif SCENARIO == 'Avec batterie':
        _eco_val   = f'<span style="white-space:nowrap;">{eaa_mad}</span>'
        _eco_size  = "17pt"
        _eco_sub   = "&#233;conomies par an"
    else:
        _eco_val   = f'<span style="white-space:nowrap;">{esa_mad}&nbsp;&#8211;&nbsp;{eaa_mad}</span>'
        _eco_size  = "13pt"
        _eco_sub   = "selon option choisie"
    return f"""
<div class="page" style="background:#FFFFFF !important;">

  <!-- ═══ DARK NAVY HERO ═══ — min-height 37% of A4 (≈110 mm) -->
  <div style="background:{CN};flex-shrink:0;position:relative;padding:30px 28px 72px 28px;min-height:37%;">
    <!-- Amber radial glow — top-right, behind N°412 -->
    <div style="position:absolute;top:0;right:0;width:260px;height:170px;background:radial-gradient(ellipse at 82% 12%, rgba(245,166,35,0.26) 0%, transparent 62%);pointer-events:none;z-index:0;"></div>

    <!-- Row 1: Logo box (left) + subtitle text (right) -->
    <div style="display:flex;align-items:flex-start;justify-content:space-between;">
      {logo_p1_dark()}
      <div style="text-align:right;padding-top:2px;">
        <div style="font-size:7px;color:rgba(255,255,255,0.38);line-height:1.7;">Installation solaire photovolta&#239;que</div>
        <div style="font-size:7px;color:rgba(255,255,255,0.38);">Proposition commerciale &#8212; Confidentiel</div>
      </div>
    </div>

    <!-- Tagline BELOW logo box — 20px gap -->
    <div style="color:{CA};font-size:6px;letter-spacing:2.5px;font-weight:600;margin-top:8px;margin-bottom:3px;white-space:nowrap;">TAQA &nbsp;&#183;&nbsp; INNOVATION &nbsp;&#183;&nbsp; NOR</div>

    <!-- Gold separator — AFTER tagline, BEFORE PROPOSITION -->
    <div style="height:1px;background:{CA};opacity:0.80;margin-bottom:4px;"></div>

    <!-- Row 2: Title+client left / Ref+validity right -->
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;">

      <!-- LEFT: PROPOSITION label + serif title -->
      <div style="flex:1;min-width:0;">
        <div style="font-size:6.5pt;letter-spacing:2.5px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:6px;">PROPOSITION COMMERCIALE</div>
        <div class="serif" style="font-size:44pt;font-weight:400;color:white;line-height:1.0;letter-spacing:-0.5px;margin-bottom:8px;">Installation<br>Solaire</div>
      </div>

      <!-- RIGHT: Ref label + N°412 + date + Validité badge -->
      <div style="text-align:right;flex-shrink:0;">
        <div style="font-size:7pt;color:{CG4};margin-bottom:1px;">R&#233;f&#233;rence devis</div>
        <div class="serif" style="font-size:17.5pt;font-weight:400;color:{CA};line-height:0.90;letter-spacing:-1px;">N&#176;&nbsp;{REF}</div>
        <div style="font-size:8.5pt;color:rgba(255,255,255,0.82);margin-top:5px;">{DATE_STR}</div>
        <div style="margin-top:5px;display:inline-block;background:{CA};color:{CN};border-radius:5px;padding:3px 10px;font-size:6.5pt;font-weight:700;">{_doc_text("validite_badge_p1")}</div>
      </div>

    </div>

    <!-- Diagonal cut — very gentle slope: left 82% height, right 70% height -->
    <div style="position:absolute;bottom:0;left:0;right:0;line-height:0;overflow:hidden;">
      <svg viewBox="0 0 100 10" preserveAspectRatio="none" style="display:block;width:100%;height:20px;">
        <polygon points="0,10 0,8.2 100,7 100,10" fill="white"/>
      </svg>
    </div>
  </div>

  <!-- WHITE CONTENT AREA — bloc simple (le flex-colonne imbriqué faisait
       ignorer le padding droit des sections à WeasyPrint : colonne de
       droite rognée au bord de page). flex:1 garde le remplissage vertical. -->
  <div style="display:block;padding:0;margin:0;flex:1;background:#FFFFFF !important;">

  <!-- CLIENT INFO — white area, below header band, no overlap -->
  <div style="padding:8px 24px 4px;flex-shrink:0;background:#FFFFFF !important;">
    <div style="font-size:13pt;font-weight:700;color:{CA};margin-bottom:2px;">{CLIENT_NAME}</div>
    <div style="font-size:8pt;color:{CG4};line-height:1.6;">{CLIENT_ADDR}<br>{CLIENT_PHONE}{'<br><span style="color:' + CG7 + ';"><span style="font-weight:600;">ICE&#160;:</span>&#160;' + CLIENT_ICE + '</span>' if CLIENT_ICE else ''}</div>
    <div style="margin-top:4px;display:inline-block;background:{CN};border-radius:3px;padding:2px 7px;font-size:7.5px;color:white;">{SVG_FACTORY if 'ndustr' in INST_TYPE else SVG_HOUSE}{INST_TYPE}</div>
  </div>

  <!-- KPI CARDS -->
  <!-- FIX v39: removed box-shadow from all 3 KPI cards (was: 0 3px 14px rgba(0,0,0,0.07) and 0 2px 8px rgba(0,0,0,0.09)) -->
  <!-- FIX v39: padding-bottom on KPI container changed from 8px → 4px (shadow bleed zone closed) -->
  <div style="padding:2px 42px 4px 24px;flex-shrink:0;background:#FFFFFF !important;">
    <!-- COMPENSATION WeasyPrint : son flex ne déduit pas les espacements
         entre enfants flex:1 — la rangée débordait à droite et rognait la
         carte Économies. Le padding droit du conteneur (42px = 24px de marge
         + 2×9px d'espacement) ramène le bord droit exactement sur la marge. -->
    <div style="display:flex;background:#FFFFFF !important;">

      <div style="flex:1;min-width:0;margin-right:9px;border:1px solid {CG2};border-left:4px solid {CA};border-radius:6px;padding:14px 12px;background:white;">
        <div style="font-size:4.5pt;letter-spacing:1.5px;color:{CG4};font-weight:400;text-transform:uppercase;margin-bottom:4px;">Puissance Install&#233;e</div>
        <div class="serif" style="font-size:19pt;color:{CN};line-height:1.05;">{KWC}&nbsp;kWc</div>
        <div style="font-size:6.5pt;color:{CG4};margin-top:3px;">{NB_PAN} panneaux &#215; {WP}&nbsp;W</div>
      </div>

      <div style="flex:1;min-width:0;margin-right:9px;border:1px solid {CG2};border-left:4px solid {CA};border-radius:6px;padding:14px 12px;background:white;">
        <div style="font-size:4.5pt;letter-spacing:1.5px;color:{CG4};font-weight:400;text-transform:uppercase;margin-bottom:4px;">Production Annuelle</div>
        <div class="serif" style="font-size:19pt;color:{CN};line-height:1.05;">{pk}&nbsp;kWh</div>
        <div style="font-size:6.5pt;color:{CG4};margin-top:3px;">&#233;nergie propre / an</div>
      </div>

      <div style="flex:1;min-width:0;overflow-wrap:anywhere;border:2px solid {CA};border-left:5px solid {CA};border-radius:6px;padding:14px 12px;background:#FFFBF2;box-shadow:0 2px 10px rgba(245,166,35,0.18);">
        <div style="font-size:4.5pt;letter-spacing:1.5px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">&#201;conomies estim&#233;es / an</div>
        <div class="serif" style="font-size:{_eco_size};color:{CN};line-height:1.1;">{_eco_val}</div>
        <div style="font-size:6.5pt;color:{CA};font-weight:600;margin-top:3px;">{_eco_sub}</div>
      </div>

    </div>
  </div>

  <!-- SECTION TITLE -->
  <div style="padding:5px 24px 7px;flex-shrink:0;background:#FFFFFF !important;">
    <div style="display:block;background:#FFFFFF !important;">
      <div style="font-size:7pt;letter-spacing:3px;color:{CG4};font-weight:500;text-transform:uppercase;">Vos Options d&#8217;Installation</div>
      <div style="height:2px;background:{CA};border-radius:1px;margin-top:3px;width:40px;"></div>
    </div>
  </div>

  <!-- OPTION CARDS ROW — equal height, fill remaining space -->
  <!-- Rangée d'options : padding droit compensé ({_opts_pad_right}px) — le
       flex de WeasyPrint ne déduit pas l'espacement entre cartes et rognait
       la carte Option 2 au bord droit de la page. -->
  <div style="display:flex;padding:0 {_opts_pad_right}px 10px 24px;align-items:stretch;background:#FFFFFF !important;">

    <!-- OPTION 1 -->
    <div style="flex:1;min-width:0;overflow:hidden;{_opt1_margin}border:1.5px solid #E8A020;border-radius:6px;padding:28px 12px 12px;display:flex;flex-direction:column;background:#FFFFFF;position:relative;{_s1}">
      {_r1}
      <div style="font-size:6.5pt;letter-spacing:3px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">Option 1</div>
      <div style="font-size:13pt;font-weight:500;color:{CN};margin-bottom:2px;">Sans batterie</div>
      <div style="font-size:7pt;color:{CGR};font-weight:600;margin-bottom:7px;">Autoconsommation directe</div>
      {_ts_price}
      <div style="font-size:7pt;color:{CG4};margin-bottom:5px;">Prix total TTC{_pkwc_s}</div>
      <div style="display:inline-block;align-self:flex-start;background:#e8f5e9;color:#2e7d32;border-radius:12px;padding:4px 10px;font-size:13px;font-weight:600;margin-bottom:7px;">{SVG_CHART}Retour en {ROI_S} ans</div>
      <div style="height:1px;background:{CG2};margin-bottom:6px;"></div>
      <ul style="list-style:none;padding:0;font-size:7pt;line-height:1.8;color:{CG7};margin-bottom:6px;">
        {_sb_lis}
      </ul>
      <div style="height:1px;background:{CG2};margin-top:auto;margin-bottom:6px;"></div>
      <div style="background:{CG1};border:1px solid {CG2};border-radius:5px;padding:5px 9px;">
        <span style="font-size:7pt;color:{CG4};">&#201;conomie estim&#233;e&#160;: </span>
        <span style="font-size:10pt;font-weight:800;color:{CN};">{esa_mad}/an</span>
      </div>
    </div>

    <!-- OPTION 2 -->
    <div style="flex:1;min-width:0;overflow:hidden;border:1.5px solid #E8A020;border-radius:6px;padding:28px 12px 12px;display:flex;flex-direction:column;background:#FFF3E0;position:relative;{_s2}">
      {_r2}
      <div style="font-size:6.5pt;letter-spacing:3px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">Option 2</div>
      <div style="font-size:13pt;font-weight:500;color:{CN};margin-bottom:2px;">Avec batterie</div>
      <div style="font-size:7pt;color:{CGR};font-weight:600;margin-bottom:7px;">Stockage + autonomie nocturne</div>
      {_ta_price}
      <div style="font-size:7pt;color:{CG4};margin-bottom:5px;">Prix total TTC{_pkwc_a}</div>
      <div style="display:inline-block;align-self:flex-start;background:#1a1a2e;color:white;border-radius:12px;padding:4px 10px;font-size:13px;font-weight:600;margin-bottom:7px;">{SVG_CHART2}Retour en {ROI_A} ans</div>
      <div style="height:1px;background:{CG2};margin-bottom:6px;"></div>
      <ul style="list-style:none;padding:0;font-size:7pt;line-height:1.8;color:{CG7};margin-bottom:6px;">
        {_ab_lis}
      </ul>
      <div style="height:1px;background:{CG2};margin-top:auto;margin-bottom:6px;"></div>
      <div style="background:white;border:1px solid {CG2};border-radius:5px;padding:5px 9px;">
        <span style="font-size:7pt;color:{CG4};">&#201;conomie estim&#233;e&#160;: </span>
        <span style="font-size:10pt;font-weight:800;color:{CN};">{eaa_mad}/an</span>
      </div>
    </div>

  </div>

  </div><!-- end white content area -->

  <!-- BOTTOM DARK STRIP — solid edge-to-edge dark navy, compact height -->
  <div style="background:{CN};flex-shrink:0;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:8px 24px;gap:16px;">
    <div style="display:flex;gap:5px;flex-shrink:0;">
      <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.35);border-radius:11px;padding:2px 7px;font-size:6.5pt;color:white;white-space:nowrap;">{SVG_SUN}3&#8239;000&#160;h/an d&#8217;ensoleillement</span>
      <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.35);border-radius:11px;padding:2px 7px;font-size:6.5pt;color:white;white-space:nowrap;">{SVG_ZAP}Prix ONEE en hausse</span>
      <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.35);border-radius:11px;padding:2px 7px;font-size:6.5pt;color:white;white-space:nowrap;">{SVG_GLOBE}&#201;nergie 100&#37; propre</span>
    </div>
    <div style="width:1px;height:16px;background:rgba(255,255,255,0.2);flex-shrink:0;"></div>
    <div style="font-size:6.5pt;color:rgba(255,255,255,0.70);white-space:nowrap;flex-shrink:0;">
      {svg_num(1)} Devis {SVG_ARROW} {svg_num(2)} Visite {SVG_ARROW} {svg_num(3)} Install. 7&#8211;14&#160;j {SVG_ARROW} {svg_num(4)} Mise en service
    </div>
  </div>

  {footer_p1()}
</div>
"""

# ── PAGE 2 — equipment tables + charts ───────────────────────────────────────
def page2(sans_items, img_roi, img_mon):
    sr = equip_rows(sans_items, TOTAUX_SANS, hi_bat=False)
    ar = equip_rows(AVEC_ITEMS, TOTAUX_AVEC, hi_bat=True)

    # Scenario visibility
    _p2_s1 = 'display:none;' if SCENARIO == 'Avec batterie' else ''
    _p2_s2 = 'display:none;' if SCENARIO == 'Sans batterie' else ''

    # ── Dynamic table row scaling ─────────────────────────────────────────────
    # When one side has many rows the table section grows and squeezes the charts.
    # Scale row height/font proportionally so everything still fits on one page.
    if SCENARIO == 'Avec batterie':
        max_rows = len(AVEC_ITEMS)
    elif SCENARIO == 'Sans batterie':
        max_rows = len(sans_items)
    else:
        max_rows = max(len(sans_items), len(AVEC_ITEMS))
    scale = 1.0 if max_rows <= 11 else max(0.62, 11.0 / max_rows)
    if scale < 1.0:
        tbl_font = f"{6.5 * scale:.2f}pt"
        th_font  = f"{5.5 * scale:.2f}pt"
        td_pady  = f"{max(1.5, 3.0 * scale):.1f}px"
        td_padx  = f"{max(2.0, 4.0 * scale):.1f}px"
        icon_sz  = f"{max(22, int(36 * scale))}px"
        icon_col = f"{max(28, int(44 * scale))}px"
        tbl_css = (
            f'<style>.eq{{font-size:{tbl_font};}}'
            f'.eq th{{font-size:{th_font};padding:{td_pady} {td_padx};}}'
            f'.eq td{{padding:{td_pady} {td_padx};}}'
            f'.eq .ti{{width:{icon_col};padding:2px 2px;}}'
            f'.eq .ti img{{width:{icon_sz} !important;height:{icon_sz} !important;}}'
            f'</style>'
        )
    else:
        tbl_css = ""

    _monthly_card = (
        f'<div style="flex:1;min-height:0;background:{CG1};border-radius:7px;padding:8px 11px;'
        f'border:1px solid {CG2};display:flex;flex-direction:column;">'
        f'<div style="font-size:7pt;font-weight:700;color:{CN};text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:1px;flex-shrink:0;">'
        f'<svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;">'
        f'<rect x="1" y="2" width="10" height="9" rx="1.5" fill="none" stroke="{CN}" stroke-width="1.3"/>'
        f'<line x1="1" y1="5" x2="11" y2="5" stroke="{CN}" stroke-width="1"/>'
        f'<line x1="4" y1="1" x2="4" y2="3" stroke="{CN}" stroke-width="1.3" stroke-linecap="round"/>'
        f'<line x1="8" y1="1" x2="8" y2="3" stroke="{CN}" stroke-width="1.3" stroke-linecap="round"/>'
        f'</svg> \u00c9conomies mensuelles estim\u00e9es (MAD\u00a0/\u00a0mois)</div>'
        f'<div style="font-size:6pt;color:{CG4};font-style:italic;margin-bottom:4px;flex-shrink:0;">'
        f'Facture ONEE vs \u00e9conomies solaires par mois</div>'
        f'<img src="{img_mon}" style="width:680px;height:170px;display:block;">'
        f'</div>'
    ) if img_mon else ""

    return f"""
<div class="page">
  {tbl_css}
  <div style="background:{CN};padding:9px 24px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">D\u00e9tail des \u00e9quipements &amp; Analyse financi\u00e8re</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">Devis N\u00b0\u00a0{REF} \u2014 {CLIENT_NAME} \u2014 {DATE_STR}</div>
    </div>
    {logo_html("42px")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <div style="padding:9px 24px 4px;flex-shrink:0;">
    <div style="display:flex;gap:10px;">

      <div style="flex:1;min-width:0;{_p2_s1}">
        <div style="background:{CN};color:white;font-size:7pt;font-weight:700;text-transform:uppercase;letter-spacing:.8px;padding:5px 9px;border-radius:5px 5px 0 0;">Option 1 \u2014 Sans batterie</div>
        <table class="eq">
          <thead><tr>
            <th class="ti"></th><th>D\u00e9signation</th>
            <th class="tc">Garantie</th><th class="tc">Qt\u00e9</th><th class="tr">P.U. HT</th><th class="tc">TVA</th><th class="tr">Total HT</th>
          </tr></thead>
          <tbody>{sr}</tbody>
        </table>
      </div>

      <div style="flex:1;min-width:0;{_p2_s2}">
        <div style="background:{CA};color:{CN};font-size:7pt;font-weight:700;text-transform:uppercase;letter-spacing:.8px;padding:5px 9px;border-radius:5px 5px 0 0;">Option 2 \u2014 Avec batterie</div>
        <table class="eq">
          <thead><tr>
            <th class="ti"></th><th>D\u00e9signation</th>
            <th class="tc">Garantie</th><th class="tc">Qt\u00e9</th><th class="tr">P.U. HT</th><th class="tc">TVA</th><th class="tr">Total HT</th>
          </tr></thead>
          <tbody>{ar}</tbody>
        </table>
      </div>

    </div>
    <div style="margin-top:4px;font-size:6pt;color:{CG4};font-style:italic;">
      * {TVA_NOTE}
    </div>
  </div>

  <!-- Charts section -->
  <div style="padding:4px 24px 6px;flex:1;min-height:0;display:flex;flex-direction:column;gap:10px;">
    <div style="flex:1;min-height:0;background:{CG1};border-radius:7px;padding:8px 11px;border:1px solid {CG2};display:flex;flex-direction:column;">
      <div style="font-size:7pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;flex-shrink:0;">
        <svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;"><polyline points="1,10 4,6 7,8 11,2" fill="none" stroke="{CN}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="8,2 11,2 11,5" fill="none" stroke="{CN}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg> Gain cumul\u00e9 sur 25 ans \u2014 Point de retour sur investissement
      </div>
      <img src="{img_roi}" style="width:680px;height:170px;display:block;">
    </div>
    {_monthly_card}
  </div>

  {footer(2)}
</div>
"""

# ── PAGE 3 — trust, guarantees, conditions, prochaines étapes, signature ─────
def page3():
    # "Option choisie" tick-boxes — only shown when both options are presented
    _opt = (
        f'<div style="margin-bottom:6px;">'
        f'<div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:5px;">Option choisie par le client</div>'
        f'<div style="display:flex;gap:10px;">'
        # Sans batterie box
        f'<div style="flex:1;border:1.5px solid {CG2};border-radius:7px;padding:7px 11px;'
        f'background:white;display:flex;align-items:center;gap:9px;">'
        f'<div style="width:17px;height:17px;border:2px solid {CG7};border-radius:3px;flex-shrink:0;"></div>'
        f'<div>'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};">Sans batterie</div>'
        f'<div style="font-size:8pt;color:{CG4};margin-top:2px;">Option 1 &#8212; R&#233;seau uniquement</div>'
        f'</div>'
        f'</div>'
        # Avec batterie box
        f'<div style="flex:1;border:1.5px solid {CA};border-radius:7px;padding:7px 11px;'
        f'background:{CAL};display:flex;align-items:center;gap:9px;">'
        f'<div style="width:17px;height:17px;border:2px solid {CA};border-radius:3px;flex-shrink:0;"></div>'
        f'<div>'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};">Avec batterie</div>'
        f'<div style="font-size:8pt;color:{CG4};margin-top:2px;">Option 2 &#8212; R&#233;seau + Stockage</div>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    ) if SCENARIO == "Les deux (Sans + Avec)" else (
        # Document à option unique : UNE confirmation, pas de cases à choix
        f'<div style="margin-bottom:6px;">'
        f'<div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:5px;">Confirmation de la commande</div>'
        f'<div style="border:1.5px solid {CA};border-radius:7px;padding:7px 11px;'
        f'background:{CAL};display:flex;align-items:center;gap:9px;">'
        f'<div style="width:17px;height:17px;border:2px solid {CA};border-radius:3px;flex-shrink:0;"></div>'
        f'<div>'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};">'
        f'Syst&#232;me photovolta&#239;que {KWC}&#160;kWc &#8212; '
        f'{"Sans batterie" if SCENARIO == "Sans batterie" else "Avec batterie"}</div>'
        f'<div style="font-size:8pt;color:{CG4};margin-top:2px;">'
        f'Je confirme la commande du syst&#232;me d&#233;crit dans ce devis</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    # ── Payment section (Devis Final only) ──
    _payment_html = ""
    if DEVIS_FINAL:
        # Pick the relevant total based on scenario / recommendation
        if SCENARIO == "Sans batterie":
            _pay_total = TOTAL_SANS
        elif SCENARIO == "Avec batterie":
            _pay_total = TOTAL_AVEC
        elif RECOMMENDED == "Sans batterie":
            _pay_total = TOTAL_SANS
        else:
            _pay_total = TOTAL_AVEC

        if PAYMENT_MODE == "custom" and CUSTOM_ACOMPTE is not None:
            _acompte = int(CUSTOM_ACOMPTE)
        else:
            _acompte = round(_pay_total * PAY_A / 100 / 1000) * 1000
        _solde = round(_pay_total * PAY_S / 100 / 1000) * 1000
        # ERR76 — clamp the acompte into [0, total - solde] so a user-supplied
        # custom acompte can never yield a negative "Matériel" or exceed 100 %.
        _acompte = max(0, min(_acompte, int(_pay_total) - _solde))
        _materiel = int(_pay_total - _acompte - _solde)

        _pct_a = round(_acompte / _pay_total * 100) if _pay_total else 0
        _pct_m = round(_materiel / _pay_total * 100) if _pay_total else 0
        _pct_s = round(_solde / _pay_total * 100) if _pay_total else 0

        def _pay_box(pct, montant, label):
            return (
                f'<div style="flex:1;text-align:center;padding:6px 5px;background:white;border-radius:8px;border:1px solid {CG2};">'
                f'<div class="serif" style="font-size:22px;font-weight:800;color:{CA};line-height:1.0;">{pct}%</div>'
                f'<div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">{fmt(montant)} MAD</div>'
                f'<div style="font-size:9px;color:{CG4};margin-top:2px;">{label}</div>'
                f'</div>')

        # QX7b — n’imprime JAMAIS une case Matériel morte à 0 % : quand
        # l’acompte custom absorbe la tranche matériel (materiel <= 0), on
        # bascule sur un échéancier à DEUX cases (Acompte + Solde) qui somment
        # à 100 % — plus de pourcentages faux. Chemin standard (materiel > 0) :
        # trois cases, rendu inchangé. Le solde reprend le reliquat exact.
        _ac_l = 'Acompte · À la signature'
        _mt_l = 'Matériel · Avant installation'
        _sd_l = 'Solde · Après installation'
        if _materiel > 0:
            _boxes = (_pay_box(_pct_a, _acompte, _ac_l)
                      + _pay_box(_pct_m, _materiel, _mt_l)
                      + _pay_box(_pct_s, _solde, _sd_l))
        else:
            _solde2 = int(_pay_total) - _acompte  # reliquat exact -> somme 100 %
            _pct_s2 = round(_solde2 / _pay_total * 100) if _pay_total else 0
            _boxes = (_pay_box(_pct_a, _acompte, _ac_l)
                      + _pay_box(_pct_s2, _solde2, 'Solde · À la livraison'))

        _payment_html = (
            f'<div style="margin-bottom:4px;">'
            f'<div style="border-left:3px solid {CN};padding-left:8px;margin-bottom:4px;">'
            f'<div style="font-size:8pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:1px;">Modalités de paiement</div>'
            f'</div>'
            f'<div style="display:flex;gap:6px;margin-bottom:3px;">'
            f'{_boxes}'
            f'</div>'
            # Note
            f'<div style="font-size:7pt;color:{CG4};font-style:italic;margin-bottom:3px;">'
            f'* La r\u00e9ception du mat\u00e9riel et le solde s\u2019appliquent m\u00eame si r\u00e9alis\u00e9s le m\u00eame jour.'
            f'</div>'
            # RIB bar
            f'<div style="background:{CG1};border-radius:5px;padding:4px 10px;margin-bottom:5px;">'
            f'<div style="font-size:7pt;color:{CG4};">Virement bancaire\u00a0: '
            f'{ENT_RIB_LINE.format(cg7=CG7)}</div>'
            f'</div>'
            f'</div>'
        )

    return f"""
<div class="page" style="display:block;position:relative;overflow:hidden;">
  <div style="background:{CN};padding:9px 24px;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">Confiance, Garanties &amp; Bon pour accord</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">Devis N\u00b0\u00a0{REF} \u2014 {CLIENT_NAME}</div>
    </div>
    {logo_html("42px")}
  </div>
  <div style="height:3px;background:{CA};"></div>

  <!-- content wrapper: clipped so it never overlaps absolutely-positioned BPA + footer -->
  <div style="overflow:hidden;max-height:820px;">

  <!-- WHY TAQINOR -->
  <div style="padding:6px 24px 4px;margin-bottom:5px;">
    <div class="serif" style="font-size:26px;color:{CN};margin-bottom:2px;">Pourquoi choisir TAQINOR&#160;?</div>
    <div style="font-size:9pt;color:{CG4};font-style:italic;margin-bottom:5px;">Des experts engag\u00e9s pour votre transition \u00e9nerg\u00e9tique</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:8px 12px;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:34px;height:34px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2" stroke-linecap="round">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
          </svg>
        </div>
        <div>
          <div style="font-size:10.5pt;font-weight:700;color:{CN};margin-bottom:3px;">Ing\u00e9nieurs sp\u00e9cialis\u00e9s</div>
          <div style="font-size:13px;color:{CG4};line-height:1.4;">Installation conforme aux normes marocaines et internationales, r\u00e9alis\u00e9e par des techniciens certifi\u00e9s.</div>
        </div>
      </div>

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:8px 12px;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:34px;height:34px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="{CA}" stroke="{CA}" stroke-width="1">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
        </div>
        <div>
          <div style="font-size:10.5pt;font-weight:700;color:{CN};margin-bottom:3px;">\u00c9quipements premium certifi\u00e9s</div>
          <div style="font-size:13px;color:{CG4};line-height:1.4;">Panneaux Canadian Solar, onduleurs Huawei &amp; Deye \u2014 certifi\u00e9s IEC avec garantie fabricant compl\u00e8te.</div>
        </div>
      </div>

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:8px 12px;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:34px;height:34px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <div>
          <div style="font-size:10.5pt;font-weight:700;color:{CN};margin-bottom:3px;">{_doc_text("garantie_titre")}</div>
          <div style="font-size:13px;color:{CG4};line-height:1.4;">{_doc_text("garantie_detail")}</div>
        </div>
      </div>

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:8px 12px;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:34px;height:34px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2">
            <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
            <line x1="12" y1="18" x2="12.01" y2="18" stroke-width="3"/>
          </svg>
        </div>
        <div>
          <div style="font-size:10.5pt;font-weight:700;color:{CN};margin-bottom:3px;">Suivi en temps r\u00e9el</div>
          <div style="font-size:13px;color:{CG4};line-height:1.4;">Application de monitoring 24/7 pour suivre production, \u00e9conomies et \u00e9tat de votre installation.</div>
        </div>
      </div>

    </div>
  </div>

  <!-- GUARANTEE BADGES -->
  <div style="padding:0 24px 4px;margin-bottom:5px;">
    <div style="display:flex;gap:5px;">
      <div style="flex:1;border:2px solid {CN};border-top:4px solid {CA};border-radius:8px;padding:6px 5px;text-align:center;background:white;">
        <div class="serif" style="font-size:38px;color:{CN};line-height:1.0;letter-spacing:-1px;">10</div>
        <div style="font-size:12px;font-weight:700;color:{CA};letter-spacing:1px;text-transform:uppercase;">ANS</div>
        <div style="font-size:8pt;color:{CG4};margin-top:2px;">Onduleur</div>
      </div>
      <div style="flex:1;border:2px solid {CN};border-top:4px solid {CA};border-radius:8px;padding:6px 5px;text-align:center;background:white;">
        <div class="serif" style="font-size:38px;color:{CN};line-height:1.0;letter-spacing:-1px;">12</div>
        <div style="font-size:12px;font-weight:700;color:{CA};letter-spacing:1px;text-transform:uppercase;">ANS</div>
        <div style="font-size:8pt;color:{CG4};margin-top:2px;">Panneaux (produit)</div>
      </div>
      <div style="flex:1;border:2px solid {CN};border-top:4px solid {CA};border-radius:8px;padding:6px 5px;text-align:center;background:white;">
        <div class="serif" style="font-size:38px;color:{CN};line-height:1.0;letter-spacing:-1px;">20</div>
        <div style="font-size:12px;font-weight:700;color:{CA};letter-spacing:1px;text-transform:uppercase;">ANS</div>
        <div style="font-size:8pt;color:{CG4};margin-top:2px;">Structure de montage</div>
      </div>
      <div style="flex:1;border:2px solid {CA};border-top:4px solid {CN};border-radius:8px;padding:6px 5px;text-align:center;background:{CAL};">
        <div class="serif" style="font-size:38px;color:{CA};line-height:1.0;letter-spacing:-1px;">30</div>
        <div style="font-size:12px;font-weight:700;color:{CN};letter-spacing:1px;text-transform:uppercase;">ANS</div>
        <div style="font-size:8pt;color:{CG4};margin-top:2px;">{_doc_text("garantie_perf_label")}</div>
      </div>
    </div>
  </div>

  <!-- QF3 — COMMENT NOUS CALCULONS VOS ÉCONOMIES (méthode + exemple) -->
  <div style="padding:0 24px;">{_savings_method_html()}</div>

  <!-- QK4 — NOS HYPOTHÈSES (transparence des hypothèses d'économies) -->
  <div style="padding:0 24px;">{_hypotheses_html()}</div>

  <!-- QK3 — FINANCEMENT (indicatif) -->
  <div style="padding:0 24px;">{_financing_html()}</div>

  <!-- QJ30 — MULTI-PROPRIÉTÉS (×N identiques / sections par-villa) -->
  <div style="padding:0 24px;">{_multi_proprietes_line_html()}{_multi_villa_html()}</div>

  <!-- CONDITIONS GENERALES -->
  <div style="padding:0 24px 4px;margin-bottom:5px;">
    <div style="background:{CG1};border-radius:8px;padding:7px 12px;border:1px solid {CG2};border-left:4px solid {CN};">
      <div style="font-size:9pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;">{_doc_text("cgv_titre")}</div>
      <ul style="list-style:none;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:2px 16px;">{_cgv_bullets_html()}</ul>
    </div>
  </div>

  <!-- NOTRE ENGAGEMENT -->
  <div style="background:{CA};padding:7px 18px;text-align:center;margin:0 24px 5px;border-radius:8px;">
    <div style="font-size:8pt;letter-spacing:2px;color:{CN};font-weight:800;text-transform:uppercase;margin-bottom:2px;">Notre Engagement</div>
    <div style="font-style:italic;color:white;font-size:9.5pt;line-height:1.4;">
      Notre \u00e9quipe reste \u00e0 votre disposition pour toute question.<br>
      Nous planifierons l&#8217;installation d\u00e8s validation du devis.
    </div>
  </div>

  <!-- PROCHAINES ÉTAPES -->
  <div style="padding:0 24px;margin-bottom:5px;">
    <div style="background:#F8F6F0;border:1px solid #EAECF0;border-radius:10px;padding:8px 12px;margin:2px 0;">
      <div style="border-left:4px solid #F5A623;padding-left:10px;margin-bottom:5px;">
        <div style="font-size:12px;font-weight:700;letter-spacing:2px;color:{CN};text-transform:uppercase;">PROCHAINES \u00c9TAPES</div>
      </div>
      <div style="display:flex;gap:6px;">
        <div style="flex:1;text-align:center;padding:7px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:36px;font-weight:800;color:{CA};line-height:1.0;">1</div>
          <div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">Signature du devis</div>
          <div style="font-size:10px;color:{CG4};margin-top:2px;">+ acompte {PAY_A}&#37;</div>
        </div>
        <div style="flex:1;text-align:center;padding:7px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:36px;font-weight:800;color:{CA};line-height:1.0;">2</div>
          <div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">Visite technique</div>
          <div style="font-size:10px;color:{CG4};margin-top:2px;">Sous 48\u201372&#160;h</div>
        </div>
        <div style="flex:1;text-align:center;padding:7px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:36px;font-weight:800;color:{CA};line-height:1.0;">3</div>
          <div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">Installation</div>
          <div style="font-size:10px;color:{CG4};margin-top:2px;">7\u201314 jours ouvr\u00e9s</div>
        </div>
        <div style="flex:1;text-align:center;padding:7px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:36px;font-weight:800;color:{CA};line-height:1.0;">4</div>
          <div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">Mise en service</div>
          <div style="font-size:10px;color:{CG4};margin-top:2px;">Tests + formation</div>
        </div>
      </div>
    </div>
  </div>

  </div><!-- end content wrapper -->

  <!-- BON POUR ACCORD — always pinned above footer via position:absolute -->
  <div style="position:absolute;bottom:{'28' if DEVIS_FINAL else '43'}px;left:0;right:0;padding:0 24px;">
    <div style="border-left:4px solid {CA};padding-left:10px;margin-bottom:{'4' if DEVIS_FINAL else '6'}px;">
      <div style="font-size:10pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:1.5px;">{_doc_text("bpa_titre")}</div>
    </div>{_acceptance_stamp_html()}
    {_opt}
    {_payment_html}
    <div style="display:flex;gap:18px;margin-bottom:4px;">
      <div style="flex:1;border:1px solid {CG2};border-radius:8px;padding:{'6px 10px' if DEVIS_FINAL else '8px 12px'};min-height:{'50' if DEVIS_FINAL else '65'}px;background:white;">
        <div style="font-size:8pt;font-weight:700;color:{CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:{'4' if DEVIS_FINAL else '6'}px;">Signature du client</div>
        <div style="border-bottom:1px solid {CG2};min-height:{'10' if DEVIS_FINAL else '14'}px;margin-bottom:3px;"></div>
        <div style="font-size:{'8' if DEVIS_FINAL else '9'}pt;color:{CG4};margin-top:2px;">Nom&#160;: <strong style="color:{CG7};">{CLIENT_NAME}</strong></div>
        <div style="border-bottom:1px solid {CG2};min-height:{'8' if DEVIS_FINAL else '12'}px;margin-top:3px;margin-bottom:3px;"></div>
        <div style="font-size:{'8' if DEVIS_FINAL else '9'}pt;color:{CG4};">Date&#160;: _______________</div>
        <div style="font-size:7pt;color:{CG4};margin-top:{'2' if DEVIS_FINAL else '3'}px;font-style:italic;">{_doc_text("bpa_mention")}</div>
      </div>
      <div style="flex:1;border:1px solid {CG2};border-radius:8px;padding:{'6px 10px' if DEVIS_FINAL else '8px 12px'};min-height:{'50' if DEVIS_FINAL else '65'}px;background:white;">
        <div style="font-size:8pt;font-weight:700;color:{CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:{'4' if DEVIS_FINAL else '6'}px;">Signature TAQINOR</div>
        <div style="border-bottom:1px solid {CG2};min-height:{'10' if DEVIS_FINAL else '14'}px;margin-bottom:3px;"></div>
        <div style="font-size:{'8' if DEVIS_FINAL else '9'}pt;color:{CG4};margin-top:2px;">Repr\u00e9sentant&#160;: <span style="display:inline-block;min-width:80px;border-bottom:1px solid {CG2};">&nbsp;</span></div>
        <div style="border-bottom:1px solid {CG2};min-height:{'8' if DEVIS_FINAL else '12'}px;margin-top:3px;margin-bottom:3px;"></div>
        <div style="font-size:{'8' if DEVIS_FINAL else '9'}pt;color:{CG4};">Date&#160;: _______________</div>
        <div style="font-size:7pt;color:{CG4};margin-top:{'2' if DEVIS_FINAL else '3'}px;font-style:italic;">Cachet et signature de la soci\u00e9t\u00e9</div>
      </div>
    </div>

  </div>

  {footer_p3("position:absolute;bottom:0;left:0;right:0;")}
</div>
"""

# ── Assemble HTML ─────────────────────────────────────────────────────────────
# \u2500\u2500 \u00c9TUDE PAGE (mode Industriel/Commercial \u2014 autoconsommation) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def make_chart_etude(prod_m, conso_m):
    """Monthly production vs consumption chart for the \u00e9tude page."""
    fig, ax = plt.subplots(figsize=(8.6, 2.6), dpi=150)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = list(range(12))
    ax.bar(x, conso_m, 0.60, color="#B5C0CE", alpha=0.65, zorder=2,
           linewidth=0, label="Consommation (kWh)")
    ax.plot(x, prod_m, color=CA, linewidth=2.2, marker="o", markersize=5.5,
            markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CA,
            zorder=4, solid_capstyle="round", label="Production PV (kWh)")
    ax.set_xticks(x); ax.set_xticklabels(MONTHS, fontsize=9, color="#374151")
    ax.tick_params(axis="x", length=0, pad=5)
    ax.tick_params(axis="y", colors="#9BA3AE", labelsize=8)
    ax.set_ylabel("kWh / mois", fontsize=9, color="#9BA3AE", labelpad=6)
    ax.grid(axis="y", color="#F0F2F5", linewidth=0.65, zorder=0)
    ax.grid(axis="x", visible=False); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=8.5, frameon=True, loc="upper left",
              edgecolor="#E5E7EB", facecolor="white")
    plt.tight_layout(pad=0.4)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return b64(buf)


def page_etude():
    """\u00c9tude d'autoconsommation (industriel) : param\u00e8tres, taux, graphique."""
    e = ETUDE
    prod_m = e.get("prod_mensuelle") or []
    conso_m = e.get("conso_mensuelle") or []
    img = (make_chart_etude(prod_m, conso_m)
           if len(prod_m) == 12 and len(conso_m) == 12 else "")

    def card(label, value, accent=False):
        border = f"border-left:4px solid {CA};" if accent else f"border-left:4px solid {CG2};"
        return (f'<div style="flex:1;min-width:150px;border:1px solid {CG2};{border}'
                f'border-radius:6px;padding:10px 12px;background:white;">'
                f'<div style="font-size:5.5pt;letter-spacing:1.2px;color:{CG4};'
                f'text-transform:uppercase;margin-bottom:3px;">{label}</div>'
                f'<div class="serif" style="font-size:14pt;color:{CN};">{value}</div></div>')

    def _card_if(label, key, suffix="", accent=False):
        """Card rendered ONLY when the value exists \u2014 a figure that cannot be
        computed is omitted entirely, never printed as a dash or a default."""
        v = e.get(key)
        if v in (None, ""):
            return ""
        return card(label, f"{v}{suffix}", accent=accent)

    # Sans consommation r\u00e9elle, les taux n'ont pas de sens : on les omet
    # (jamais d'\u00ab Autoconsommation 100 % \u00bb fabriqu\u00e9e).
    has_conso = e.get("conso_annuelle") not in (None, "", 0)
    cards1 = (
        card("Puissance cr\u00eate", f"{KWC}\u00a0kWc", accent=True)
        + _card_if("Production annuelle", "production_annuelle", "\u00a0kWh")
        + _card_if("Consommation annuelle", "conso_annuelle", "\u00a0kWh")
        + _card_if("Prix par kWc", "prix_kwc", "\u00a0MAD")
    )
    cards2 = (
        (_card_if("Taux d'autoconsommation", "taux_autoconso", "\u00a0%", accent=True)
         if has_conso else "")
        + (_card_if("Taux de couverture", "taux_couverture", "\u00a0%", accent=True)
           if has_conso else "")
        + _card_if("\u00c9conomies annuelles", "economies_annuelles", "\u00a0MAD")
        + _card_if("Retour sur investissement", "payback", "\u00a0ans")
    )
    _rates_note = (
        "* Taux d'autoconsommation : part de la production solaire "
        "consommée sur site. Taux de couverture : part de la "
        "consommation totale couverte par le solaire. ") if has_conso else ""
    chart_html = (
        f'<div style="background:{CG1};border-radius:7px;padding:10px 12px;'
        f'border:1px solid {CG2};margin-top:10px;">'
        f'<div style="font-size:7pt;font-weight:700;color:{CN};text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:5px;">Production PV vs consommation \u2014 mensuel</div>'
        f'<img src="{img}" style="width:680px;height:200px;object-fit:contain;display:block;">'
        f'</div>'
    ) if img else ""

    return f"""
<div class="page">
  <div style="background:{CN};padding:12px 24px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">\u00c9tude d'autoconsommation</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">Devis N\u00b0\u00a0{REF} \u2014 {CLIENT_NAME} \u2014 {DATE_STR}</div>
    </div>
    {logo_html("42px")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <div style="padding:14px 24px;flex:1;min-height:0;">
    <div style="font-size:8pt;color:{CG4};margin-bottom:10px;">
      Simulation \u00e9tablie sur l'irradiation moyenne du Maroc et le profil de
      consommation communiqu\u00e9. Mode\u00a0: {INST_TYPE} \u2014 sans batterie,
      onduleur r\u00e9seau, raccordement triphas\u00e9 (sauf indication contraire).
    </div>
    <div style="display:flex;gap:9px;margin-bottom:9px;">{cards1}</div>
    <div style="display:flex;gap:9px;">{cards2}</div>
    {chart_html}
    <div style="margin-top:10px;font-size:6.5pt;color:{CG4};font-style:italic;">
      {_rates_note}Estimations non contractuelles.
    </div>
  </div>

  <div style="background:{CN};padding:6px 24px 5px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>
    <div style="font-size:7pt;color:#888;">{ENT_ETUDE_CONTACT}</div>
    <div style="font-size:7pt;color:#888;">\u00c9tude \u2014 R\u00e9f.\u00a0{REF}</div>
  </div>
</div>
"""


def build_html():
    print("  Generating charts...")
    img_roi = make_chart_roi()
    img_mon = make_chart_monthly() if SHOW_MONTHLY else ""
    etude_html = page_etude() if (INCLUDE_ETUDE and ETUDE) else ""
    return f"""<!DOCTYPE html>
<html lang="fr" style="background:#FFFFFF !important;"><head><meta charset="UTF-8">
<title>Devis TAQINOR N\u00b0 {REF}</title>
<style>{CSS}</style></head>
<body style="background:#FFFFFF !important;">
{page1()}
{page2(SANS_ITEMS, img_roi, img_mon)}
{etude_html}
{page3()}
</body></html>"""

# ── ONE-PAGE MODE ─────────────────────────────────────────────────────────────
def page_onepage(items):
    """Single A4 page: header + summary strip + client block + HT product table + footer."""
    # Totaux CANONIQUES du builder (chaîne HT → remise → TVA par taux → TTC,
    # calculée UNE fois) ; recalcul local uniquement en mode autonome.
    if TOTAUX_ALL:
        totaux = TOTAUX_ALL
    else:
        _ht = sum(
            float(it.get("quantite", 0)) * _item_pu_ht(it)
            for it in items
            if float(it.get("quantite", 0)) > 0
        )
        _rem = _ht * DISCOUNT_PCT / 100 if DISCOUNT_PCT > 0 else 0.0
        _net = _ht - _rem
        _tva = _net * TVA_PCT / 100
        totaux = {"ht_brut": _ht, "remise": _rem, "ht_net": _net,
                  "tva": _tva, "tva_par_taux": [],
                  "ttc": round(_net + _tva)}
    total_ht = totaux["ht_brut"]
    remise = totaux["remise"]
    net_ht = totaux["ht_net"]
    tva_amt = totaux["tva"]
    total = totaux["ttc"]

    # ── Bloc résumé système (style devis concurrent) ──
    if ETUDE.get("pompe_cv"):
        # Chiffres CANONIQUES calculés à la création du devis (courbe
        # constructeur) — rendus tels quels. Une carte sans valeur est
        # OMISE : jamais de tiret ni de m³/jour inventé sans courbe.
        _sum_cells = []
        _pkw = ETUDE.get("pompe_kw")
        _sum_cells.append((
            "Puissance pompe",
            f"{ETUDE.get('pompe_cv')} CV ({_pkw} kW)" if _pkw
            else f"{ETUDE.get('pompe_cv')} CV"))
        if ETUDE.get("hmt_m"):
            _sum_cells.append(("HMT", f"{ETUDE.get('hmt_m')} m"))
        def _fdec(v):
            # entier sans décimale, sinon une décimale à la française (30,5)
            try:
                f = float(v)
                return fnum(f) if f == int(f) else f"{f:.1f}".replace(".", ",")
            except Exception:
                return str(v)
        _dq = ETUDE.get("debit_hmt_m3h")
        if _dq and ETUDE.get("hmt_m"):
            _sum_cells.append(
                (f"D&#233;bit &#224; {ETUDE.get('hmt_m')} m",
                 f"{_fdec(_dq)} m&#179;/h"))
        elif ETUDE.get("debit_m3j"):  # anciens devis (saisie manuelle)
            _sum_cells.append(
                ("D&#233;bit estim&#233;", f"{ETUDE.get('debit_m3j')} m&#179;/jour"))
        _m3j = ETUDE.get("m3_jour")
        _hrs = ETUDE.get("heures_pompage")
        if _m3j and _hrs:
            _sum_cells.append(
                (f"Eau / jour (sur {_fdec(_hrs)} h de pompage)",
                 f"&#8776; {fnum(_m3j)} m&#179;"))
        if KWC > 0:
            _sum_cells.append(("Champ PV", f"{KWC} kWc"))
    elif KWC > 0:
        _sum_cells = [
            ("Puissance cr&#234;te", f"{KWC} kWc"),
            ("Production annuelle", f"{fnum(PROD_KWH)} kWh/an"),
            ("&#201;conomie annuelle", f"{fnum(max(ECO_S_ANN, ECO_A_ANN))} MAD/an"),
            ("Prix par kWc", f"{fnum(round(total / KWC))} MAD/kWc"),
        ]
    else:
        _sum_cells = []
    summary_html = ""
    if _sum_cells:
        cells = "".join(
            f'<div style="flex:1;text-align:center;">'
            f'<div style="font-size:5.5pt;font-weight:700;color:{CG4};'
            f'text-transform:uppercase;letter-spacing:.8px;">{label}</div>'
            f'<div style="font-size:9pt;font-weight:800;color:{CN};margin-top:2px;">{val}</div>'
            f'</div>'
            for label, val in _sum_cells)
        summary_html = (
            f'<div style="display:flex;background:{CAL};border-bottom:2px solid {CA};'
            f'padding:8px 24px;">{cells}</div>')

    # Build table rows (per-line HT, with description + warranty detail lines).
    # Densité ADAPTATIVE pour tenir sur UNE page quoi qu'il arrive :
    #   ≤ 8 lignes  → descriptions complètes (4 lignes) + garantie
    #   9–12 lignes → descriptions courtes (2 lignes) + garantie
    #   > 12 lignes → table compacte (désignation + marque seulement)
    visible = [it for it in items if float(it.get("quantite", 0)) > 0]
    n_items = len(visible)
    if n_items <= 8:
        max_desc, desc_pt, pad_px, show_gar = 4, 6.5, 6, True
    elif n_items <= 12:
        max_desc, desc_pt, pad_px, show_gar = 2, 6, 4, True
    else:
        max_desc, desc_pt, pad_px, show_gar = 0, 6, 3, False

    rows_html = ""
    row_idx = 0
    for it in visible:
        qty = float(it.get("quantite", 0))
        bg = "white" if row_idx % 2 == 0 else CG1
        pu_ht = _item_pu_ht(it)
        line_total = qty * pu_ht
        marque = it.get("marque", "") or ""
        des = it.get("designation", "")
        qty_str = str(int(qty)) if qty == int(qty) else fnum(qty)
        marque_html = badge(marque) if marque else ""
        detail_html = _desc_lines_html(it, max_lines=max_desc, font_pt=desc_pt) if max_desc else ""
        gar = (it.get("garantie") or "").strip()
        if gar and show_gar:
            detail_html += (
                f'<div style="font-size:{desc_pt}pt;color:{CGR};font-weight:600;'
                f'padding-left:6px;">&#10003; {gar}</div>')
        _taux = it.get("taux_tva", TVA_PCT)
        _taux_s = f"{int(_taux)}&#37;" if _taux == int(_taux) else f"{_taux}&#37;"
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:{pad_px}px 10px;word-break:break-word;">'
            f'<div style="font-weight:700;color:{CN};">{des}</div>{detail_html}</td>'
            f'<td style="padding:{pad_px}px 10px;">{marque_html}</td>'
            f'<td style="padding:{pad_px}px 10px;text-align:center;color:{CG7};">{qty_str}</td>'
            f'<td style="padding:{pad_px}px 10px;text-align:right;color:{CG7};">{_fmt2(pu_ht)}</td>'
            f'<td style="padding:{pad_px}px 10px;text-align:center;color:{CG4};font-size:7.5pt;">{_taux_s}</td>'
            f'<td style="padding:{pad_px}px 10px;text-align:right;font-weight:500;color:{CN};">{_fmt2(line_total)}</td>'
            f'</tr>'
        )
        row_idx += 1

    # ── Bloc totaux : Sous-total HT → Remise visible → Total HT → TVA → TTC ──
    def _tot_line(label, value, navy=False, neg=False):
        color = CGR if neg else (CN if not navy else CN)
        size = "13pt" if navy else "8.5pt"
        weight = 800 if navy else 600
        return (
            f'<div style="margin-top:2px;">'
            f'<span style="font-size:8pt;font-weight:700;color:{CG4 if not navy else CN};'
            f'text-transform:uppercase;letter-spacing:.5px;margin-right:18px;">{label}</span>'
            f'<span style="display:inline-block;min-width:110px;text-align:right;'
            f'font-size:{size};font-weight:{weight};color:{color};white-space:nowrap;">{value}</span>'
            f'</div>')

    totals_html = _tot_line("Sous-total HT", _fmt2(total_ht) + "&nbsp;MAD")
    if DISCOUNT_PCT > 0:
        _pct = int(DISCOUNT_PCT) if DISCOUNT_PCT == int(DISCOUNT_PCT) else DISCOUNT_PCT
        totals_html += _tot_line(
            f"Remise ({_pct}&#8201;%)", "&#8722;" + _fmt2(remise) + "&nbsp;MAD", neg=True)
        totals_html += _tot_line("Total HT", _fmt2(net_ht) + "&nbsp;MAD")
    # TVA éclatée par taux présent (réforme 10/20) ; un seul taux → ligne
    # unique identique aux devis historiques.
    _buckets = totaux.get("tva_par_taux") or []
    if len(_buckets) > 1:
        for _b in _buckets:
            _r = int(_b["taux"]) if _b["taux"] == int(_b["taux"]) else _b["taux"]
            totals_html += _tot_line(
                f"TVA ({_r}&#8201;%)", _fmt2(_b["montant"]) + "&nbsp;MAD")
    else:
        _rate = _buckets[0]["taux"] if _buckets else TVA_PCT
        _tva_pct = int(_rate) if _rate == int(_rate) else _rate
        totals_html += _tot_line(f"TVA ({_tva_pct}&#8201;%)", _fmt2(tva_amt) + "&nbsp;MAD")
    totals_html += _tot_line("Total TTC", fmt(total), navy=True)

    return f"""
<div class="page" style="position:relative;display:block;">

  <!-- CONTENT AREA: block flow, footer space reserved (WeasyPrint-robuste :
       pas de flex:1 ni de gap, qui rendaient le total par-dessus le footer) -->
  <div style="position:absolute;top:0;left:0;right:0;bottom:72px;overflow:hidden;">

  <!-- HEADER: navy -->
  <div style="background:{CN};padding:14px 24px;display:flex;align-items:center;justify-content:space-between;">
    {logo_html("80px")}
    <div style="text-align:right;">
      <div style="color:white;font-size:11pt;font-weight:700;">DEVIS&nbsp;<span style="color:{CA};">N&#176;&#160;{REF}</span></div>
      <div style="color:rgba(255,255,255,0.6);font-size:8pt;margin-top:2px;">{DATE_STR}</div>
    </div>
  </div>

  <!-- CLIENT BLOCK -->
  <div style="background:{CG1};padding:12px 24px;border-bottom:1px solid {CG2};">
    <div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Client</div>
    <div style="font-size:11pt;font-weight:700;color:{CN};">{CLIENT_NAME}</div>
    <div style="font-size:8.5pt;color:{CG7};margin-top:2px;">{CLIENT_ADDR}</div>
    <div style="font-size:8.5pt;color:{CG4};margin-top:1px;">{CLIENT_PHONE}</div>
    {'<div style="font-size:8pt;color:' + CG7 + ';margin-top:3px;"><span style="color:' + CG4 + ';font-weight:600;">ICE&#160;:</span>&#160;' + CLIENT_ICE + '</div>' if CLIENT_ICE else ''}
  </div>

  <!-- SYSTEM SUMMARY (kWc / production / économie / prix par kWc, ou pompage) -->
  {summary_html}

  <!-- PRODUCT TABLE (per-line HT) -->
  <div style="padding:12px 24px 0;">
    <table style="width:100%;border-collapse:collapse;font-size:8.5pt;table-layout:fixed;">
      <colgroup>
        <col style="width:39%">
        <col style="width:12%">
        <col style="width:7%">
        <col style="width:16%">
        <col style="width:7%">
        <col style="width:19%">
      </colgroup>
      <thead>
        <tr style="background:{CN};">
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:left;text-transform:uppercase;letter-spacing:.5px;">D&#233;signation</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:left;text-transform:uppercase;letter-spacing:.5px;">Marque</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:center;text-transform:uppercase;letter-spacing:.5px;">Qt&#233;</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:right;text-transform:uppercase;letter-spacing:.5px;">P.U. HT (MAD)</th>
          <th style="padding:8px 6px;color:white;font-weight:700;font-size:7.5pt;text-align:center;text-transform:uppercase;letter-spacing:.5px;">TVA</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:right;text-transform:uppercase;letter-spacing:.5px;">Total HT (MAD)</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <!-- TOTALS: Sous-total HT → Remise visible → Total HT → TVA → Total TTC -->
  <div style="background:{CAL};border-top:2px solid {CA};padding:10px 14px;margin:12px 24px 0;text-align:right;">
    {totals_html}
  </div>

  <!-- QJ30 — ×N propriétés identiques (ligne compacte ; une page préservée) -->
  <div style="padding:6px 24px 0;">{_multi_proprietes_line_html()}</div>

  <!-- CONDITIONS : sous le total -->
  <div style="padding:8px 24px;">
    {'<div style="font-size:7.5pt;color:' + CG4 + ';font-style:italic;margin-bottom:3px;">Ce document chiffre l&#8217;option sans batterie. Une option avec batterie est disponible &#8212; voir la proposition compl&#232;te.</div>' if ONEPAGE_NOTE_BATTERIE else ''}
    <div style="font-size:7pt;color:{CG4};">
      <span style="margin-right:20px;">{_doc_text("validite_onepage")}</span>
      <span style="margin-right:20px;">&#183; Acompte&#160;: {PAY_A}&#37;</span>
      <span style="margin-right:20px;">&#183; {PAY_M}&#37; &#224; la r&#233;ception du mat&#233;riel</span>
      <span style="margin-right:20px;">&#183; {PAY_S}&#37; apr&#232;s mise en marche</span>
      <span>&#183; {TVA_NOTE}</span>
    </div>
  </div>

  </div><!-- /CONTENT AREA -->

  <!-- FOOTER: navy + legal identity, toujours en bas de page, jamais chevauché -->
  <div style="position:absolute;left:0;right:0;bottom:0;background:{CN};padding:6px 24px 5px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
      <div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>
      <div style="font-size:7pt;color:#888;text-align:center;">
        {ENT_CONTACT_LINE}
      </div>
      <div style="font-size:7pt;color:#888;">R&#233;f.&#160;{REF}</div>
    </div>
    <div style="font-size:7.5px;color:#888;text-align:center;font-style:italic;">
      {ENT_LEGAL_LINE}
    </div>
  </div>

</div>
"""


def build_html_onepage(items):
    """Minimal HTML shell for the one-page PDF."""
    return f"""<!DOCTYPE html>
<html lang="fr" style="background:#FFFFFF !important;"><head><meta charset="UTF-8">
<title>Devis TAQINOR N\u00b0 {REF}</title>
<style>{CSS}</style></head>
<body style="background:#FFFFFF !important;">
{page_onepage(items)}
</body></html>"""


# ── Generate PDF ──────────────────────────────────────────────────────────────
def generate():
    ref = QUOTE_INPUT["ref"]
    print(f"[1/3] Building HTML for devis {ref}...")
    sys.stdout.buffer.write(
        f"  blocks={_Q['blocks']} | TOTAL_SANS={fmt(TOTAL_SANS)} | TOTAL_AVEC={fmt(TOTAL_AVEC)}\n"
        .encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    html = build_html()

    out_dir = BASE_DIR / "devis_client"
    out_dir.mkdir(exist_ok=True)
    import re as _re
    _safe_c = _re.sub(r"[^A-Za-z0-9]", "_", QUOTE_INPUT.get("client_name", "Client"))
    _kwc_str = f"{QUOTE_INPUT['puissance_kwc']:g}kWc"
    if SCENARIO == "Les deux (Sans + Avec)":
        _scen_str = "Hybride+Injection"
    elif SCENARIO == "Avec batterie":
        _scen_str = "Hybride"
    else:
        _scen_str = "Injection"
    out = out_dir / f"TAQINOR_Devis_{ref}_{_safe_c}_{_kwc_str}_{_scen_str}.pdf"

    print("[2/3] Writing temp HTML...")
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                     mode="w", encoding="utf-8") as tf:
        tf.write(html)
        tmp = tf.name

    print("[3/3] Rendering with WeasyPrint...")
    _render_pdf_weasyprint(html, str(out))
    Path(tmp).unlink(missing_ok=True)

    kb = out.stat().st_size // 1024
    msg = (f"\n\u2705 Saved: {out.name} | Pages: 3 | {kb} KB\n")
    sys.stdout.buffer.write(msg.encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    return str(out)

# ── Public API for web app ────────────────────────────────────────────────────
def generate_premium_pdf(data: dict, out_path) -> str:
    """Generate premium PDF from a dynamic data dict; returns str(out_path).

    Required keys in data: ref, date, client_name, client_addr, client_phone,
    inst_type, puissance_kwc, nb_panneaux, watt_par_panneau, prod_kwh,
    total_sans, total_avec, eco_s_ann, eco_a_ann, eco_a_cumul,
    roi_s, roi_a, eco_s_monthly, eco_a_monthly, sans_items, avec_items.

    Items dicts must have: designation, quantite, prix_unit_ttc, marque.
    """
    # ERR17 — serialize the whole render: the body writes module globals and
    # reads them back while building the HTML, so concurrent renders must not
    # interleave (one client's data leaking into another's PDF).
    with _RENDER_LOCK:
        return _render_premium_pdf(data, out_path)


def _render_premium_pdf(data: dict, out_path) -> str:
    global CLIENT_NAME, CLIENT_ADDR, CLIENT_PHONE, CLIENT_ICE, REF, DATE_STR
    global KWC, NB_PAN, WP, PROD_KWH, TOTAL_SANS, TOTAL_AVEC
    global DISCOUNT_PCT, TOTAL_SANS_BEFORE, TOTAL_AVEC_BEFORE
    global ECO_S_ANN, ECO_A_ANN, ROI_S, ROI_A, INST_TYPE
    global SANS_ITEMS, AVEC_ITEMS, ECO_S_M, ECO_A_M, CUMUL_S, CUMUL_A
    global FACTURES_M
    global SCENARIO, RECOMMENDED, SHOW_MONTHLY
    global DEVIS_FINAL, PAYMENT_MODE, CUSTOM_ACOMPTE
    global TVA_PCT, MODE_INSTALLATION, ETUDE, INCLUDE_ETUDE
    global TVA_NOTE, TOTAUX_SANS, TOTAUX_AVEC, TOTAUX_ALL, SANS_BULLETS, AVEC_BULLETS
    global PAY_A, PAY_M, PAY_S, ONEPAGE_NOTE_BATTERIE
    global DOC_TEXTS, ACCEPTE_PAR_NOM, DATE_ACCEPTATION
    global DEVISE  # FG52 — devise du document (ISO 4217)
    global SAVINGS_METHOD  # QF3 — bloc « Comment nous calculons vos économies »
    SAVINGS_METHOD = data.get("savings_method")
    global HYPOTHESES  # QK4 — bloc « Nos hypothèses »
    HYPOTHESES = data.get("hypotheses")
    global FINANCING  # QK3 — bloc financement (QJ12)
    FINANCING = data.get("financing")
    global NB_PROPRIETES, DISPLAY_TOTAL_MULTI, MULTI_VILLA  # QJ30 multi-propriétés
    try:
        NB_PROPRIETES = int(data.get("nombre_proprietes") or 1)
    except (TypeError, ValueError):
        NB_PROPRIETES = 1
    DISPLAY_TOTAL_MULTI = data.get("display_total_multi")
    MULTI_VILLA = data.get("multi_villa")

    # ERR37 — escape user-controlled client fields before they reach the PDF HTML.
    CLIENT_NAME  = _esc(data["client_name"])
    CLIENT_ADDR  = _esc(data["client_addr"])
    CLIENT_PHONE = _esc(data["client_phone"])
    CLIENT_ICE   = _esc(data.get("client_ice", ""))
    REF          = str(data["ref"])
    DATE_STR     = data["date"]
    KWC          = float(data["puissance_kwc"])
    NB_PAN       = int(data["nb_panneaux"])
    WP           = int(data["watt_par_panneau"])
    PROD_KWH     = int(data["prod_kwh"])
    TOTAL_SANS        = float(data["total_sans"])
    TOTAL_AVEC        = float(data["total_avec"])
    DISCOUNT_PCT      = float(data.get("discount_pct", 0))
    TOTAL_SANS_BEFORE = float(data.get("total_sans_before", TOTAL_SANS))
    TOTAL_AVEC_BEFORE = float(data.get("total_avec_before", TOTAL_AVEC))
    ECO_S_ANN    = int(data["eco_s_ann"])
    ECO_A_ANN    = int(data["eco_a_ann"])
    ROI_S        = float(data["roi_s"])
    ROI_A        = float(data["roi_a"])
    INST_TYPE    = data["inst_type"]
    SCENARIO     = data.get("scenario", "Les deux (Sans + Avec)")
    RECOMMENDED  = data.get("recommended", "Avec batterie")
    SHOW_MONTHLY = data.get("show_monthly", True)
    DEVIS_FINAL    = data.get("devis_final", False)
    PAYMENT_MODE   = data.get("payment_mode", "standard")
    CUSTOM_ACOMPTE = data.get("custom_acompte", None)
    TVA_PCT        = float(data.get("taux_tva", 20) or 20)
    MODE_INSTALLATION = data.get("mode_installation", "") or ""
    ETUDE          = data.get("etude") or {}
    INCLUDE_ETUDE  = bool(data.get("include_etude", False))
    _tva_lbl = int(TVA_PCT) if TVA_PCT == int(TVA_PCT) else TVA_PCT
    TVA_NOTE       = data.get("tva_note") or (
        f"TVA {_tva_lbl} % appliquée sur l'ensemble des équipements et travaux.")
    # FG52 — devise portée par le document (défaut MAD = comportement inchangé).
    DEVISE         = (data.get("devise") or "MAD").strip().upper()
    # DC1 — identité société (multi-tenant) : réinitialise les défauts puis
    # applique le profil de la société du devis. Champs vides → littéraux
    # Taqinor historiques (byte-identique) ; sinon SON identité s'affiche.
    _apply_entreprise(data.get("entreprise"))
    # QG7 — ajoute le contact du créateur du devis (nom + tél) à la ligne de
    # coordonnées, APRÈS _apply_entreprise. Seller vide → byte-identique.
    _apply_seller(data.get("seller"))

    # Totaux canoniques (une seule source pour toutes les pages). À défaut
    # (anciens appels), reconstruits une fois ici avec la même chaîne.
    def _fallback_totaux(rows):
        ht_brut = round(sum(r["quantite"] * _item_pu_ht(r) for r in rows), 2)
        remise = round(ht_brut * DISCOUNT_PCT / 100, 2) if DISCOUNT_PCT > 0 else 0.0
        ht_net = round(ht_brut - remise, 2)
        tva = round(ht_net * TVA_PCT / 100, 2)
        return {"ht_brut": ht_brut, "remise": remise, "ht_net": ht_net,
                "tva": tva, "ttc": round(ht_net + tva)}
    TOTAUX_SANS = data.get("totaux_sans") or _fallback_totaux(data["sans_items"])
    TOTAUX_AVEC = data.get("totaux_avec") or _fallback_totaux(data["avec_items"])
    TOTAUX_ALL = data.get("totaux_all") or None
    _terms = data.get("payment_terms") or {}
    PAY_A = int(_terms.get("acompte", 30))
    PAY_M = int(_terms.get("materiel", 60))
    PAY_S = int(_terms.get("solde", 10))
    ONEPAGE_NOTE_BATTERIE = bool(data.get("onepage_note_batterie", False))
    SANS_BULLETS = data.get("sans_bullets") or []
    AVEC_BULLETS = data.get("avec_bullets") or []
    # D2/N60/N67/N59 — textes éditables du devis : fusion défaut + surcharges
    # société. Toute clé absente/None retombe sur le littéral historique, donc
    # un appel sans `doc_texts` (ou avec des surcharges vides) reste byte-identique.
    _dt = data.get("doc_texts") or {}
    DOC_TEXTS = dict(DEFAULT_DOC_TEXTS)
    if isinstance(_dt, dict):
        for k, v in _dt.items():
            if v is not None:
                DOC_TEXTS[k] = v
    # N26 — métadonnées d'acceptation (posées côté serveur). Le tampon n'apparaît
    # que si les DEUX sont présents ; sinon byte-identique au devis d'aujourd'hui.
    ACCEPTE_PAR_NOM = (data.get("accepte_par_nom") or "")
    DATE_ACCEPTATION = (data.get("date_acceptation") or "")

    # Numérotation des pages cohérente avec le nombre RÉEL de pages rendues
    # (l'étude insérée entre les pages 2 et 3 porte le total à 4).
    global PAGES_TOTAL, PAGE3_NUM
    _with_etude = bool(INCLUDE_ETUDE and ETUDE) and data.get("pdf_mode", "full") == "full"
    PAGES_TOTAL = 4 if _with_etude else 3
    PAGE3_NUM = PAGES_TOTAL
    # ERR37 — escape user text in line items at the ingestion boundary so every
    # downstream renderer (full + one-page) emits safe HTML.
    # QF9 — garde-fou marque (défense en profondeur, après le filtrage builder).
    SANS_ITEMS   = _guard_huawei_accessories(_esc_items(data["sans_items"]))
    AVEC_ITEMS   = _guard_huawei_accessories(_esc_items(data["avec_items"]))
    ECO_S_M      = data["eco_s_monthly"]
    ECO_A_M      = data["eco_a_monthly"]
    FACTURES_M   = list(data["factures_mensuelles"])
    eco_a_cumul  = int(data["eco_a_cumul"])
    CUMUL_S      = [-TOTAL_SANS + ECO_S_ANN * y for y in YEARS]
    CUMUL_A      = [-TOTAL_AVEC + eco_a_cumul  * y for y in YEARS]

    out_path = Path(out_path)
    mode = data.get("pdf_mode", "full")
    if mode == "onepage":
        html = build_html_onepage(
            _guard_huawei_accessories(_esc_items(data.get("all_items", []))))
    else:
        html = build_html()

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                     mode="w", encoding="utf-8") as tf:
        tf.write(html)
        tmp = tf.name

    _render_pdf_weasyprint(html, str(out_path))
    Path(tmp).unlink(missing_ok=True)

    return str(out_path)


if __name__ == "__main__":
    try:
        generate()
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(1)
