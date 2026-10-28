#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
# Vendored from RedaSolar/devis-simulator (founder's quote engine), adapted for
# the OS: fonts/logo bundled locally (no runtime network), matplotlib config dir.
"""
generate_devis_premium.py  FINAL
Page 1 : white-background v1 layout
Pages 2-3 : v4 premium dark design
Rendu seul : ``generate_premium_pdf(data, out_path)`` / ``render_html_for(data)``
(QJR629 — plus de devis démo embarqué ni d'exécution en script).
"""
import base64, html, io, re, subprocess, sys, tempfile, threading
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# NTI18N5 — catalogue des libellés structurels du document (fr/en/ar). Données
# pures : ni Django, ni ``apps``, ni I/O — ce moteur vendoré reste donc
# démarrable hors Django, et importable directement depuis son dossier (d'où le
# double chemin d'import : paquet d'abord, module voisin ensuite).
try:
    from . import i18n_labels
except ImportError:  # exécution directe du moteur depuis son dossier
    import i18n_labels

# QA-FIGURES — ancres ``data-figure`` masquées posées À CÔTÉ de chaque chiffre
# client (jamais dedans : aucune chaîne existante ne change ; ``hidden`` =
# aucun rendu, aucune pagination touchée). Module pur, même double chemin
# d'import que ``i18n_labels``. Voir ``quote_engine/figures.py``.
try:
    from .figures import ancre as _ancre_figure
except ImportError:  # exécution directe du moteur depuis son dossier
    from figures import ancre as _ancre_figure

# QJR613 — formateur monétaire au centime UNIQUE (stdlib), partagé avec les
# paquets premium ; même double chemin d'import.
try:
    from .montants import (decimale, fmt_centimes, fmt_centimes_mad, fmt_dirhams, format_anglais,
                           format_langue, pct_fr, poser_regles_origine, regles_origine)
except ImportError:  # exécution directe du moteur depuis son dossier
    from montants import (decimale, fmt_centimes, fmt_centimes_mad, fmt_dirhams, format_anglais,
                          format_langue, pct_fr, poser_regles_origine, regles_origine)

# QJR617 — ordre d'affichage sections / notes ↔ lignes produit (XSAL14), UNE
# fonction pure partagée ; même double chemin d'import.
try:
    from .sequence import sequence_affichage
except ImportError:  # exécution directe du moteur depuis son dossier
    from sequence import sequence_affichage


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


from .identite import (ligne_rib as _ligne_rib_identite,  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    LEGALE_TAQINOR_LEGACY, mentions_legales as _mentions_legales,
    profil_renseigne as _profil_renseigne)
from . import logo as _logo  # noqa: E402 — R3, module pur (D-ENF22)
# AMOT57 — « est-ce un onduleur ? » : LE classifieur partagé (« Deye off-Grid »).
from apps.ventes.solar_classification import is_inverter  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)


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


# ── QJR408 — LA SECONDE PASSE DE CLASSIFICATION EST SUPPRIMÉE ──────────────
#
# ``_guard_huawei_accessories`` vivait ici : une SECONDE passe QF9 sur les
# listes par option, armée exactement quand ``nb_options == 2``. Or le
# builder applique DÉJÀ la règle du noyau à ces deux paniers dans ce cas
# précis (``builder._drop_huawei_accessories``, branche ``if deux_options``)
# — et il le fait AVANT de retirer la clé interne ``_produit_nom`` des
# items. Ce garde-fou, lui, s'exécutait APRÈS ce retrait : il ne classait
# donc plus que sur la DÉSIGNATION SEULE, précisément la divergence que
# QJR301 déclare fermée. Un panier dont l'identité Huawei ne vit que dans
# le NOM du produit lié était vu « Huawei » par le builder (accessoire
# CONSERVÉ, donc COMPTÉ dans le total figé) et « non-Huawei » ici
# (accessoire RETIRÉ du tableau) : le client lisait un tableau dont la
# somme ne fait pas le total. Cette passe ne pouvait que SOUS-compter le
# tableau, jamais le sur-compter.
#
# Issue retenue : SUPPRESSION (règle permanente 2 — le code mort part dans
# le même commit). La règle QF9 garde UN seul propriétaire
# (``utils.options.retirer_accessoires_huawei``) et UN seul site
# d'application (le builder, là où la clé de classement existe encore).


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
        logger.warning("generate_devis_premium._load_gfont : erreur ignorée (mode dégradé)", exc_info=True)
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
# QJR629 — DÉFAUTS INERTES des globales du rendu. Le devis démo embarqué
# (QUOTE_INPUT : coordonnées réelles du fondateur) et sa seconde formule de
# prix par blocs (calculate_quote, exécutée à l'import) sont SUPPRIMÉS : chaque
# rendu passe par ``apply_quote_data``, qui réécrit toutes ces globales.
# ═══════════════════════════════════════════════════════════════════════════════

CLIENT_NAME  = ""
CLIENT_ADDR  = ""
CLIENT_PHONE = ""
CLIENT_ICE   = ""
# L-NIV (24/08/2026) — filigrane PDF DISCRET, posé UNIQUEMENT sur le PDF
# public niveau standard (jamais le PDF interne). None par défaut → les
# footers restent byte-identiques à avant L-NIV (mêmes tests de page-count).
WATERMARK_STANDARD = None
REF          = ""
DATE_STR     = ""
# QJR628 — « Document mis à jour le … » / « Remplace le devis … » ('' = rien).
MIS_A_JOUR_LE = ""
REMPLACE_REF  = ""
KWC          = 0.0
NB_PAN       = 0
WP           = 0
PROD_KWH     = 0
TOTAL_SANS        = 0.0
TOTAL_AVEC        = 0.0
DISCOUNT_PCT      = 0.0
TOTAL_SANS_BEFORE = 0.0
TOTAL_AVEC_BEFORE = 0.0
ECO_S_ANN    = 0
ECO_A_ANN    = 0
ROI_S        = 0.0
ROI_A        = 0.0
# ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — cumul 25 ans jamais positif.
ROI_S_JAMAIS = False
ROI_A_JAMAIS = False
INST_TYPE    = ""
# AMOT22 — ville de calcul du productible (libellé), posée par le builder.
VILLE_CALCUL = ""
SANS_ITEMS   = []
AVEC_ITEMS   = []
# XSAL14/XSAL5 \u2014 lignes de structure (sections/notes) + options propos\u00e9es.
# D\u00e9faut vide \u2192 un devis sans structure/option est rendu strictement comme avant.
LIGNES_STRUCTURE = []
OPTIONS_PROPOSEES = []
# QXMT \u2014 d\u00e9fauts INERTES : sans les cl\u00e9s du builder, le rendu est
# byte-identique \u00e0 aujourd'hui (aucun dossier MT \u21d2 aucune omission).
MASQUER_ECONOMIES = False
TARIF_MT_MENTION = ""
# M2 — aucun ancrage réel de puissance (ni ligne panneau, ni fiche produit, ni
# calepinage) : puissance, production, économies et prix-au-kWc en dérivent
# tous, donc AUCUN d'eux n'est imprimé. Défaut INERTE (False) : sans la clé du
# builder, le rendu est byte-identique.
PUISSANCE_INCONNUE = False
# F1/L-2OPT - scalaires PAR OPTION (les deux options d'un devis peuvent porter
# des champs PV de tailles differentes). Defauts INERTES : sans les cles du
# builder, ``PANNEAUX_DIVERGENTS`` reste faux et tout le rendu lit le scalaire
# global comme avant - byte-identique.
PANNEAUX_DIVERGENTS = False
KWC_SANS = 0.0
KWC_AVEC = 0.0
NB_PAN_SANS = 0
NB_PAN_AVEC = 0
# PDFPROD - la production DERIVE du kWc : elle diverge donc avec lui. Memes
# defauts inertes (0 = « rien par option », la vignette lit le scalaire).
PROD_KWH_SANS = 0
PROD_KWH_AVEC = 0

MONTHS  = ["Jan","F\u00e9v","Mar","Avr","Mai","Jun",
           "Jul","Ao\u00fb","Sep","Oct","Nov","D\u00e9c"]
ECO_S_M    = [0] * 12
ECO_A_M    = [0] * 12
# M1 (audit 19/08/2026) — factures mensuelles RÉELLES, ou RIEN. L'ancien défaut
# reconstruisait une facture depuis les économies (÷ 0,65) : une mine, parce
# qu'il reprenait la main dès que le builder cessait d'en fournir une. Liste
# vide ⇒ `make_chart_monthly` n'imprime aucune barre et aucune légende ONEE.
FACTURES_M = []

YEARS   = list(range(26))
CUMUL_S = [-TOTAL_SANS + ECO_S_ANN * y for y in YEARS]
CUMUL_A = [-TOTAL_AVEC + ECO_A_ANN * y for y in YEARS]
# QJR125 — la série tracée est-elle le cashflow RÉEL du devis (dégradation,
# rendement batterie, provision onduleur) ou le repli « économie plate » ? Le
# repli est faux de +14,5 % / +36,6 % sur le gain final (M5) : on ne le TRACE
# plus. Ces drapeaux sont posés par ``apply_quote_data``.
CUMUL_S_REEL = False
CUMUL_A_REEL = False

SCENARIO    = "Les deux (Sans + Avec)"
RECOMMENDED = "Avec batterie"

DEVIS_FINAL    = False
# FG52 — devise portée par le document (ISO 4217, défaut MAD). Lue depuis
# data["devise"] ; permet l'affichage de la bonne devise sur le PDF.
# Q8 (fondateur, 20/08/2026) — les documents sont en MAD, point. La variable
# reste (exports/compat) mais n'est plus imprimée : `fmt()` écrit MAD.
DEVISE = "MAD"
# NTI18N5 — LANGUE DU DOCUMENT (fr/en/ar) et sa table de libellés structurels,
# routée par le builder. Défauts FRANÇAIS : le chemin autonome et tout appel
# sans ces clés rendent EXACTEMENT le document d'aujourd'hui, au caractère près
# (les valeurs françaises du catalogue sont les littéraux historiques du
# gabarit, entités numériques comprises).
LANGUE_SORTIE = i18n_labels.LANGUE_DE_REPLI
LIBELLES_DOC = i18n_labels.libelles(i18n_labels.LANGUE_DE_REPLI)
PAGES_TOTAL = 3                # nombre réel de pages (+1 étude, +1 annexe PV46)
PAGE3_NUM = 3                  # numéro de la page de signature
# PV46 — annexe technique : défauts INERTES (le chemin autonome et tout appel
# sans les clés du builder rendent exactement le PDF d'aujourd'hui).
INCLUDE_ANNEXE = False
ELECTRICAL_DESIGN = {}
SLD_SVG = ""
# CAL182 — page « Calepinage » (planche cotée CAL171) : mêmes défauts INERTES.
# Sans les clés du builder, la page n'existe pas et le PDF est byte-identique.
INCLUDE_CALEPINAGE = False
CALEPINAGE_SVG = ""
CALEPINAGE_EMPREINTE = ""
# CAD122 — signature AU DOMICILE (loi 31-08, art. 45) : même défaut INERTE.
# Faux ⇒ aucune annexe de rétractation, document byte-identique à celui
# d'avant. Le délai est celui des articles 49 et 50 — c'est la loi, pas un
# réglage société, et il ne se recopie nulle part ailleurs dans ce module.
SIGNE_AU_DOMICILE = False
# AMOT23 — délai légal : UNE source (annexe_domicile, partagée avec le
# gabarit résidentiel).
from .annexe_domicile import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    DELAI_RETRACTATION_DOMICILE_JOURS,
    corps_annexe_domicile as _corps_annexe_domicile,
)
TOTAUX_ALL = None              # totaux canoniques toutes-lignes (one-page)
# AGR313 — la synthèse agricole (``agricole/synthese.synthese_agricole``) : la
# MÊME fonction que le document de 3 pages et /proposition. None hors agricole.
SYNTHESE_AGRICOLE = None
# CIQ210 (complément) — les chiffres-clés C&I (``ci.synthese.chiffres_cles``
# sur ``synthese_ci``) : la MÊME projection que la couverture du document
# complet et /proposition. None hors commercial/industriel.
CHIFFRES_CI = None
SYNTHESE_CI = None  # AMOT86 — la ``synthese_ci`` projetée en ``CHIFFRES_CI``.
# Conditions de paiement par mode — TOUJOURS fournies par le builder ;
# défaut résidentiel pour le chemin autonome.
PAY_A, PAY_M, PAY_S = 30, 60, 10
# QJR623 — cases « Modalités de paiement » calculées par le builder (par
# branche « sans » / « avec », au centime) ; le moteur ne fait qu'imprimer.
MONTANTS_TRANCHES = {}
# Devis deux-options rendu en une page : option 1 seule + mention discrète.
ONEPAGE_NOTE_BATTERIE = False
# M4 — branche ('sans' | 'avec' | None) dont proviennent les lignes du format
# une page. Défaut None = aucune économie affichée sur le chemin autonome ;
# le builder la pose TOUJOURS pour un vrai devis.
ONEPAGE_BRANCHE = None
# BAT-DIFF — libellé de l'option « avec » (« Avec batterie » ou « Hybride,
# batterie plus tard ») posé par le builder ; sert la mention du une-page.
LIBELLE_AVEC = "Avec batterie"
# QJR13 — capacité batterie TOTALE des LIGNES du devis (``data
# ['batterie_kwh_total']``, calculé par ``builder._battery_kwh_from_items`` sur
# l'option AVEC). Défaut 0 = « aucune batterie connue » : un optimum du moteur
# qui annonce du stockage ne peut alors PAS être prouvé conforme au devis, donc
# il n'est pas publié (voir ``_optimum_decrit_ce_devis``).
BATTERIE_KWH_TOTAL = 0.0
# QJR609 — capacité UTILE vendue (``data['batterie_kwh_utile_vendue']``, lue
# par le builder via ``capacite_batterie_des_lignes`` : fiche, puis nominal ×
# DoD, puis nom), couplée au nominal qu'elle accompagne. Sert UNIQUEMENT la
# garde ``_optimum_decrit_ce_devis`` (un optimum est mesuré en kWh UTILES) ;
# ``BATTERIE_KWH_TOTAL`` reste le chiffre nominal. ``None`` ⇒ repli nominal.
BATTERIE_KWH_UTILE_VENDUE = None
# QRP1 — liens client-facing posés par le builder (``data['links']``). Le seul
# consommé ici est ``signer`` : l'URL TOKENISÉE de la proposition en ligne
# (ShareLink, ``utils.client_links.chemin_proposition``). Aucune URL n'est
# forgée dans ce module ; dict vide ⇒ le format une page est byte-identique.
LINKS = {}
# M7 — date d'échéance RÉELLE du devis, format « JJ/MM/AAAA », ou "" quand elle
# est indéterminable (les mentions de validité disparaissent alors).
VALID_UNTIL = ""
# Q5 (fondateur, 20/08/2026) — délais commerciaux INDICATIFS, réglages
# société. Vides ⇒ le délai n'apparaît nulle part (jamais un littéral
# codé ici, jamais dans la boîte « Conditions »).
DELAI_VISITE = ""
DELAI_INSTALLATION = ""
# M10 (audit du 19/08/2026) — le modèle d'économies est-il une ESTIMATION
# (aucun barème réel du client n'a servi) ? Le builder le calcule depuis
# toujours (``savings_estimated``) mais AUCUN renderer ne le lisait : le
# document ne distinguait pas une économie calculée sur le barème réel du
# client d'une économie estimée sur un tarif de référence. Défaut False =
# rendu inchangé pour tout appel sans la clé.
SAVINGS_ESTIMATED = False

# ── DC1 — identité société (multi-tenant) ──────────────────────────────────────
# Chaque littéral d'identité (nom de marque du footer, coordonnées, ligne légale
# RC/ICE/adresse, ligne RIB) devient une variable pilotée par ENT (posée depuis
# data["entreprise"] = CompanyProfile). Les DÉFAUTS ci-dessous reproduisent
# EXACTEMENT les littéraux Taqinor historiques : tant qu'aucun profil enrichi
# n'est fourni, le PDF reste byte-identique. Un devis d'un AUTRE tenant affiche
# désormais SON identité — plus de fuite de l'ICE/RIB/RC de Taqinor.
ENT_NOM_MARQUE = "TAQINOR"                       # nom affiché dans les footers
# Ligne de coordonnées (email · téléphone · site) — littéral historique exact.
ENT_CONTACT_LINE = ("contact@taqinor.ma &nbsp;&#183;&nbsp; "
                    "+212&#160;6&#160;61&#160;85&#160;04&#160;10 "
                    "&nbsp;&#183;&nbsp; www.taqinor.ma")
# Pied de la page ETUDE (email · site, sans téléphone) — littéral historique
# exact (SCA27 : reconstruit par _apply_entreprise dès qu’un email ou un site
# de profil est fourni — plus de fuite du contact fondateur sur la page étude).
ENT_ETUDE_CONTACT = "contact@taqinor.ma &nbsp;·&nbsp; www.taqinor.ma"
# Ligne légale du footer page 3 — APDF3 : repli « aucun profil » (identite).
_ENT_DEFAULT_LEGAL_LINE = LEGALE_TAQINOR_LEGACY
ENT_LEGAL_LINE = _ENT_DEFAULT_LEGAL_LINE
# Ligne RIB (bénéficiaire · banque · RIB · BIC) — APDF2 : LA règle unique de
# ``quote_engine.identite`` (un seul littéral, partagé avec le résidentiel).


def _gras_rib_legacy(texte):
    """APDF2 — balise du bénéficiaire propre au moteur legacy (``{cg7}`` est
    substitué au rendu, jamais par ``.format()``, QJR146)."""
    return f'<strong style="color:{{cg7}}">{texte}</strong>'


ENT_RIB_LINE = _ligne_rib_identite(None, gras=_gras_rib_legacy)

# Snapshot des DÉFAUTS Taqinor : les ENT_* actifs sont réinitialisés depuis eux
# au début de chaque rendu (sous _RENDER_LOCK) avant surcharge par le profil,
# pour qu'aucune identité de tenant ne persiste d'un rendu au suivant.
_ENT_DEFAULT_NOM_MARQUE = ENT_NOM_MARQUE
_ENT_DEFAULT_CONTACT_LINE = ENT_CONTACT_LINE
_ENT_DEFAULT_ETUDE_CONTACT = ENT_ETUDE_CONTACT
_ENT_DEFAULT_RIB_LINE = ENT_RIB_LINE
#: APDF4 — logo d'en-tête de la société (``theme.logo_societe_b64``) ; None =
#: aucun profil → l'asset TAQINOR historique.
ENT_LOGO_B64 = None


def _apply_entreprise(ent):
    """DC1 — pose les variables d'identité société depuis data["entreprise"].

    ``ent`` est le dict renvoyé par ``parametres.selectors.company_identity``.
    Toute valeur vide laisse le littéral Taqinor historique (byte-identique) ;
    dès qu'une valeur est renseignée, elle remplace la ligne correspondante et
    le devis d'un autre tenant n'affiche plus jamais l'identité de Taqinor.
    """
    global ENT_NOM_MARQUE, ENT_CONTACT_LINE, ENT_LEGAL_LINE, ENT_RIB_LINE
    global ENT_ETUDE_CONTACT, ENT_LOGO_B64
    global CA
    # Réinitialise TOUJOURS depuis les défauts d'abord : pas de fuite d'un rendu
    # précédent (les globals sont mutés sous _RENDER_LOCK).
    ENT_NOM_MARQUE = _ENT_DEFAULT_NOM_MARQUE
    ENT_CONTACT_LINE = _ENT_DEFAULT_CONTACT_LINE
    ENT_ETUDE_CONTACT = _ENT_DEFAULT_ETUDE_CONTACT
    # APDF9 — repli « aucun profil » : « Siège » dans la langue du document.
    ENT_LEGAL_LINE = _ENT_DEFAULT_LEGAL_LINE.replace(
        "Si\u00e8ge\u00a0:", _L("op_siege"))
    ENT_RIB_LINE = _ENT_DEFAULT_RIB_LINE
    ENT_LOGO_B64 = None
    CA = _CA_DEFAULT
    if not isinstance(ent, dict):
        return
    nom = (ent.get("nom") or "").strip()
    adresse = (ent.get("adresse") or "").strip()
    email = (ent.get("email") or "").strip()
    tel = (ent.get("telephone") or "").strip()

    # Aucun profil (APDF3 : la définition d'identite) → byte-identique.
    if not _profil_renseigne(ent):
        return
    from .residential.theme import logo_societe_b64
    ENT_LOGO_B64 = logo_societe_b64({"entreprise": ent})

    if nom:
        ENT_NOM_MARQUE = _esc(nom.upper())

    # Ligne de contact : reconstruite dès qu'un contact est fourni.
    if email or tel:
        parts = [p for p in (_esc(email), _esc(tel)) if p]
        ENT_CONTACT_LINE = " &nbsp;&#183;&nbsp; ".join(parts)
    else:
        # AMOT17 (C-AMOT-016) — société IDENTIFIÉE sans contact : la ligne
        # est OMISE, jamais le contact de TAQINOR sous le nom d'un autre.
        ENT_CONTACT_LINE = ""

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
    else:
        # AMOT17 — idem pour le pied de la page Étude.
        ENT_ETUDE_CONTACT = ""

    # APDF3 — ligne légale par LA fonction de la bande premium (identite) :
    # raison sociale [forme, capital] · RC · ICE · IF · Patente, puis Siège.
    legal_bits = _mentions_legales(ent, gras=None, fiscales=True) or []
    if adresse:
        legal_bits.append(_L("op_siege") + " " + _esc(adresse))
    ENT_LEGAL_LINE = " &middot; ".join(legal_bits)

    # APDF2 (C-APDF-001) — ligne RIB par LA règle unique (identite.py) :
    # RIB/banque du profil → sa ligne ; société identifiée SANS RIB → AUCUNE
    # ligne (plus jamais le RIB Taqinor sous le nom d'un autre tenant).
    ENT_RIB_LINE = _ligne_rib_identite(ent, gras=_gras_rib_legacy)

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
    bits = _L("lg_votre_conseiller").format(nom=_esc(nom))
    if tel:
        bits += f" &#8212; {_esc(tel)}"
    ENT_CONTACT_LINE = (f"{ENT_CONTACT_LINE} &nbsp;&#183;&nbsp; {bits}"
                        if ENT_CONTACT_LINE else bits)


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
    # M7 (audit du 19/08/2026) — plus AUCUN « 30 jours » codé ici : le devis
    # porte sa vraie échéance (``date_validite``, sinon création + réglage
    # société ``quote_validity_days``), que le builder sert dans ``valid_until``
    # et que le marqueur {validite} substitue. Échéance indéterminable ⇒ le
    # marqueur rend une chaîne VIDE et le badge/la puce DISPARAÎT — jamais une
    # date fausse en face de la vraie, affichée elle sur le portail client.
    "validite_badge_p1": "{validite}",
    "validite_onepage": "&#183; {validite}",
    # D2/N60 — conditions générales (titre + 7 puces ; placeholders substitués).
    "cgv_titre": "Conditions générales du devis",
    "cgv_bullets": [
        "{validite_offre}",
        "Acompte à la commande&#160;: {acompte}&#37;",
        "{materiel}&#37; à la réception du matériel",
        "{solde}&#37; après la mise en marche",
        "{tva_note}",
        "Tarifs de référence&#160;: barème ONEE/SRM",
    ],
    # N67 — garanties (titre, détail, libellé performance). Entités HTML EXACTES.
    # QRES56 (fondateur, 2026-08-17) — « Structure 20 ans » RETIRÉE ici aussi :
    # le moteur résidentiel v2 ne publie plus que les garanties traçables aux
    # fiches produit (theme.WARRANTIES), les deux moteurs disent enfin la même
    # chose. Le reste du littéral est inchangé au caractère près.
    # M6 (audit du 19/08/2026) — plus AUCUNE durée ni pourcentage codés ici.
    # Ces trois littéraux annonçaient « jusqu'à 30 ans », « 12 ans produit +
    # 30 ans performance (87,4 %) », « Performance panneau (87,4 %) » sur TOUS
    # les devis, y compris ceux dont le panneau est d'une autre marque (Longi :
    # 30 ans à 88,9 %) ou dont aucune garantie n'est saisie. Le titre et le
    # détail sont désormais COMPOSÉS depuis les fiches produit du devis
    # (``_garanties_du_devis``) ; ces défauts ne servent plus que de repli
    # non chiffré, et une surcharge société explicite reste souveraine.
    "garantie_titre": "",
    "garantie_detail": "",
    "garantie_perf_label": "Performance panneau",
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
# QJR627 (D-QJR5-6) — texte CLIENT du champ « Notes » (échappé à l'ingestion).
NOTE_CLIENT = ""
# QJR668 — clauses/CGV de l'affaire gelées (échappées à l'ingestion).
CLAUSES_CGV = []
# APDF13 — conditions générales imprimées (``cgv_imprimees``, APDF12), posées
# par ``apply_quote_data`` ; la ligne de conditions du une-page les imprime.
CGV_IMPRIMEES = {"titre": "", "puces": []}


#: AMOT20 — vrai pendant l'ajustement du une-page quand la note et les
#: clauses ont dû être TRONQUÉES (avec renvoi déclaré) pour que le dernier
#: bloc de la zone tienne. Remis à ``False`` en fin d'ajustement : aucun autre
#: format n'est jamais tronqué.
ONEPAGE_TEXTES_TRONQUES = False
#: AMOT20 — longueurs gardées (texte BRUT, coupe au mot) quand on tronque.
_ONEPAGE_NOTE_MAX = 220
_ONEPAGE_CLAUSE_MAX = 90
#: AMOT20 — le renvoi DÉCLARÉ qui remplace la suite d'un texte tronqué.
_RENVOI_TEXTE_INTEGRAL = {
    "fr": "texte int&#233;gral sur la proposition en ligne",
    "en": "full text in the online proposal",
    # À relire par le fondateur (patron CIQM22).
    "ar": "\u0627\u0644\u0646\u0635 \u0627\u0644\u0643\u0627\u0645\u0644 "
          "\u0641\u064a \u0627\u0644\u0639\u0631\u0636 "
          "\u0639\u0628\u0631 \u0627\u0644\u0625\u0646\u062a\u0631\u0646\u062a",
}


def _renvoi_texte_integral():
    return _RENVOI_TEXTE_INTEGRAL.get(LANGUE_SORTIE,
                                      _RENVOI_TEXTE_INTEGRAL["fr"])


def _tronquer_texte_echappe(texte, longueur):
    """AMOT20 — tronque un texte DÉJÀ échappé sur son texte BRUT (au mot,
    « … ») puis le ré-échappe : jamais une entité HTML coupée."""
    # AMOT46 — LE helper unique de troncature (``textes.tronquer_au_mot``).
    from .textes import tronquer_au_mot
    return tronquer_au_mot(texte, longueur)


def _clauses_cgv_html(font_pt="7.5"):
    """QJR668 — bloc « Clauses particulières », ou '' sans clause gelée."""
    from .clauses_cgv import bloc_clauses_html
    clauses = CLAUSES_CGV
    if ONEPAGE_TEXTES_TRONQUES and clauses:
        # AMOT20 — une-page trop dense : chaque clause garde son nom et le
        # début de son texte, la suite est renvoyée à la proposition.
        clauses = [dict(c, corps_texte=_tronquer_texte_echappe(
            c.get("corps_texte"), _ONEPAGE_CLAUSE_MAX)) for c in clauses]
        clauses.append({"nom": "", "corps_texte":
                        "(" + _renvoi_texte_integral() + ")"})
    return bloc_clauses_html(clauses, couleur_titre=CN,
                             couleur_texte=CG7, taille_pt=font_pt,
                             langue=LANGUE_SORTIE)


def _note_client_html(font_pt="8"):
    """QJR627 — le bloc « Note » du devis, ou '' quand le champ est vide."""
    if not NOTE_CLIENT:
        return ""
    note = NOTE_CLIENT
    if ONEPAGE_TEXTES_TRONQUES:
        tronquee = _tronquer_texte_echappe(note, _ONEPAGE_NOTE_MAX)
        if tronquee != note:
            note = f"{tronquee} ({_renvoi_texte_integral()})"
    return (f'<div style="font-size:{font_pt}pt;color:{CN};white-space:pre-line;'
            f'margin-bottom:4px;"><b style="text-transform:uppercase;'
            f'letter-spacing:.8px;margin-right:6px;">{_L("res_note")}</b>{note}</div>')
DATE_ACCEPTATION = ""
# QF3 — bloc « Comment nous calculons vos économies » (méthode + exemple), posé
# depuis data["savings_method"]. Vide → aucun bloc rendu (byte-identique).
SAVINGS_METHOD = None


def _sans_economies_publiees():
    """QJR123 — LE document publie-t-il des économies ?

    UNE seule définition, celle que ``build_html`` applique déjà aux deux
    graphes (``_sans_economies``) et ``page1`` aux pastilles ROI : dossier
    raccordé en MOYENNE TENSION (chiffres au barème BASSE tension, donc pas
    les siens) ou puissance sans ancrage réel. Tout bloc qui PORTE un chiffre
    d'économies — méthode, hypothèses — lit cette fonction.
    """
    return bool(MASQUER_ECONOMIES or PUISSANCE_INCONNUE)


def _savings_method_html():
    """QF3 — bloc « Comment nous calculons vos économies » (méthode + exemple
    chiffré compact). Rendu UNIQUEMENT quand data["savings_method"] est fourni.
    Aucune donnée fabriquée : le texte vient du builder (une seule source)."""
    # QJR123 — MÊME GARDE QUE LES GRAPHES ET LES PASTILLES ROI. Ce bloc n'avait
    # aucun garde : sur un dossier MOYENNE TENSION, les pages 1 et 2 omettent
    # scrupuleusement les économies (les chiffres sont au barème BASSE tension)
    # et la page 3 imprimait juste après « COMMENT NOUS CALCULONS VOS
    # ÉCONOMIES » avec ce même tarif BT. Idem quand la puissance n'a aucun
    # ancrage réel : la méthode décrit alors des économies non publiées.
    if _sans_economies_publiees():
        return ""
    sm = SAVINGS_METHOD
    if not isinstance(sm, dict) or not sm.get("ligne_methode"):
        return ""
    # AMOT52 — en / ar : la phrase et l'exemple du modèle employé, par LA
    # fonction du gabarit résidentiel (catalogue ``res_methode_*``).
    from .residential.trust import _methode_traduite
    methode, exemple = ((_esc(sm.get("ligne_methode", "")), sm.get("exemple"))
                        if LANGUE_SORTIE == i18n_labels.LANGUE_DE_REPLI
                        else _methode_traduite({"langue_sortie": LANGUE_SORTIE}, sm))
    # QJR123 — la mention d'estimation s'affiche INDÉPENDAMMENT de l'exemple :
    # le modèle « estimation » du builder pose ``approximatif=True`` mais
    # ``exemple=None``, donc la mention n'apparaissait JAMAIS sur les devis
    # qu'elle devait précisément qualifier.
    approx = (_L("res_approximatif")
              if (sm.get("approximatif") or SAVINGS_ESTIMATED) else "")
    ex_html = ""
    if exemple:
        ex_html = (
            f'<div style="margin-top:4px;font-size:8pt;color:{CN};font-weight:700;">'
            f'{_esc(exemple) if LANGUE_SORTIE == "fr" else exemple}{approx}</div>')
    elif approx:
        ex_html = (
            f'<div style="margin-top:4px;font-size:7.5pt;color:{CG4};'
            f'font-style:italic;">{_L("lg_eco_estimees_confirmer").format(approx=approx)}'
            f'</div>')
    return (
        f'<div style="background:{CG1};border-radius:8px;padding:7px 12px;'
        f'border:1px solid {CG2};border-left:4px solid {CA};margin-bottom:5px;">'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};'
        f'text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px;">'
        f'{_L("lg_methode_titre")}</div>'
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
    # QJR123 — même garde que le bloc « méthode » ci-dessus : ces hypothèses
    # portent le tarif MAD/kWh et la production par kWc qui SERVENT les
    # économies. Économies non publiées ⇒ hypothèses non publiées.
    if _sans_economies_publiees():
        return ""
    h = HYPOTHESES
    if not isinstance(h, dict):
        return ""
    # AMOT52 — en / ar : chaque phrase du builder dans la langue du document
    # (catalogue ``res_hyp_*``) ; français : la phrase telle quelle.
    from .residential.trust import hypothese_traduite
    items = [hypothese_traduite(LANGUE_SORTIE, i) for i in (h.get("items") or []) if i]
    if not items:
        return ""
    titre = (_esc(h.get("titre") or "Nos hypothèses")
             if LANGUE_SORTIE == "fr" else _L("res_hyp_titre"))
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
        total_txt = _L("lg_multi_total").format(
            n=NB_PROPRIETES, montant=fmt(DISPLAY_TOTAL_MULTI))
    return (
        f'<div style="background:{CAL};border:1px solid {CA};border-radius:8px;'
        f'padding:6px 12px;margin-bottom:5px;font-size:8.5pt;color:{CN};">'
        f'{_L("lg_multi_identiques").format(n=NB_PROPRIETES, total=total_txt)}'
        f'</div>')


def _multi_villa_html():
    """QJ30 (B) — sections par-villa (sous-totaux) + total général, dans UN
    document. Rendu UNIQUEMENT quand MULTI_VILLA est fourni. Les montants
    viennent du builder/selector (une source) ; jamais de prix d'achat/marge."""
    mv = MULTI_VILLA
    if not isinstance(mv, dict) or not mv.get("groupes"):
        return ""

    # QJR126 — un montant MANQUANT ne s'écrit pas « 0 ». Les replis
    # ``t.get("ht_net", 0)`` / ``fmt(gt.get("ttc", 0))`` imprimaient
    # « Total général : 0 MAD » d'apparence factuelle si la clé manquait.
    def _mont(source, cle, formateur):
        valeur = source.get(cle)
        return (formateur(valeur)
                if isinstance(valeur, (int, float)) else "")

    rows = ""
    for g in mv["groupes"]:
        t = g.get("totaux") or {}
        rows += (
            f'<tr><td style="padding:3px 8px;color:{CG7};">{_esc(g.get("label", ""))}</td>'
            f'<td style="padding:3px 8px;text-align:right;color:{CG7};">'
            f'{_mont(t, "ht_net", _fmt2)}</td>'
            f'<td style="padding:3px 8px;text-align:right;font-weight:700;'
            f'color:{CN};white-space:nowrap;">{_mont(t, "ttc", fmt)}</td></tr>')
    gt = mv.get("grand_total") or {}
    # ARRONDI-100 — seul le total général porte le palier de 100 MAD : la
    # ligne « Arrondi commercial » referme l'addition des villas.
    _arr = gt.get("arrondi")
    if isinstance(_arr, (int, float)) and _arr > 0 \
            and isinstance(gt.get("ttc"), (int, float)):
        _arr_ttc = sum(float((g.get("totaux") or {}).get("ttc") or 0)
                       for g in mv["groupes"]) - gt["ttc"]
        rows += (
            f'<tr><td style="padding:3px 8px;color:{CGR};">{_L("arrondi")}</td>'
            f'<td style="padding:3px 8px;text-align:right;color:{CGR};">'
            f'&#8722;{_fmt2(_arr)}</td>'
            f'<td style="padding:3px 8px;text-align:right;color:{CGR};'
            f'white-space:nowrap;">&#8722;{_fmt2(_arr_ttc)}</td></tr>')
    # Pas de total général chiffrable ⇒ pas de ligne « Total général ».
    if isinstance(gt.get("ttc"), (int, float)):
        rows += (
            f'<tr style="background:{CN};"><td style="padding:4px 8px;color:{CA};'
            f'font-weight:800;">{_L("res_total_general")}</td>'
            f'<td style="padding:4px 8px;text-align:right;color:{CA};font-weight:800;">'
            f'{_mont(gt, "ht_net", _fmt2)}</td>'
            f'<td style="padding:4px 8px;text-align:right;color:{CA};font-weight:800;'
            f'white-space:nowrap;">{_mont(gt, "ttc", fmt)}</td></tr>')
    return (
        f'<div style="border:1px solid {CG2};border-radius:8px;overflow:hidden;'
        f'margin-bottom:5px;">'
        f'<div style="background:{CG1};padding:5px 12px;font-size:9pt;'
        f'font-weight:700;color:{CN};text-transform:uppercase;'
        f'letter-spacing:.8px;">{_L("res_detail_propriete")}</div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:8pt;">'
        f'<thead><tr>'
        f'<th style="padding:3px 8px;text-align:left;color:{CG4};font-size:6.5pt;'
        f'text-transform:uppercase;">{_L("res_propriete")}</th>'
        f'<th style="padding:3px 8px;text-align:right;color:{CG4};font-size:6.5pt;'
        f'text-transform:uppercase;">{_L("total_ht")}</th>'
        f'<th style="padding:3px 8px;text-align:right;color:{CG4};font-size:6.5pt;'
        f'text-transform:uppercase;">{_L("total_ttc")}</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>')


# QRES66 (fondateur, 18/08/2026) — le bloc « Financement possible » (QK3)
# est SUPPRIMÉ du rendu legacy. Ne pas le réintroduire.


def _L(cle):
    """NTI18N5 — libellé STRUCTUREL du gabarit dans la langue du document.

    Lit la table déjà routée par le builder (``data["libelles_document"]``) ;
    à défaut — appelant historique, charge utile partielle, chemin autonome —
    résout depuis ``LANGUE_SORTIE``, dont le défaut est le français. Un client
    ne peut donc lire ni un blanc ni un nom de clé : au pire il lit le français.
    """
    valeur = (LIBELLES_DOC or {}).get(cle)
    return valeur if valeur else i18n_labels.libelle(cle, LANGUE_SORTIE)


def _doc_text(key):
    """Fragment de texte éditable `key`, repli sur le littéral historique."""
    val = DOC_TEXTS.get(key)
    if val is None:
        val = DEFAULT_DOC_TEXTS.get(key, "")
    # M7 — {validite} porte la VRAIE échéance du devis, ou rien du tout.
    if isinstance(val, str) and "{validite}" in val:
        val = (val.replace("{validite}",
                           _L("op_validite_jusqu").format(date=VALID_UNTIL))
               if VALID_UNTIL else "")
    return val


def _doc_text_langue(key, cle_i18n):
    """APDF46 — texte éditable ``key`` : resté au DÉFAUT du moteur, il suit la
    langue du document (clé ``cle_i18n`` d'``i18n_labels``) ; une surcharge
    société reste telle quelle. Français : :func:`_doc_text`, inchangé."""
    val = _doc_text(key)
    if (val == DEFAULT_DOC_TEXTS.get(key)
            and LANGUE_SORTIE != i18n_labels.LANGUE_DE_REPLI):
        return _L(cle_i18n)
    return val


def _pct_echeance(valeur, defaut):
    """QJR623 — un pourcentage d'échéancier tel que le document l'IMPRIME.

    L'échéancier RÉEL du devis peut porter 33,5 % : on n'en tronque pas la
    décimale (``int``) ; un entier reste un entier (« 40 », jamais
    « 40.0 »). Pure : sert le rendu (``PAY_A``/``PAY_M``/``PAY_S``) ET
    :func:`cgv_bullets_remplies` (la page publique de signature)."""
    try:
        f = float(valeur if valeur is not None else defaut)
    except (TypeError, ValueError):
        f = float(defaut)
    return int(f) if f == int(f) else round(f, 2)


def _tva_note_par_defaut(tva_pct, langue=None):
    """Mention TVA de repli (``data['tva_note']`` absent) — UNE fois.
    APDF10 — en/ar : la clé ``tva_unique`` d'``i18n_labels``."""
    tva_lbl = pct_fr(tva_pct)  # AMOT24
    if i18n_labels.normaliser(langue) != "fr":
        return i18n_labels.libelle("tva_unique", langue).format(taux=tva_lbl)
    return (f"TVA {tva_lbl} % appliquée sur l'ensemble des équipements et "
            f"travaux.")


# APDF12/APDF13 (C20) — la famille PURE des conditions générales (puces
# par défaut, remplissage, ``cgv_imprimees``, échappement des textes saisis)
# vit dans ``clauses_cgv`` (move only). Importée ICI, après
# DEFAULT_DOC_TEXTS, _esc, _pct_echeance et _tva_note_par_defaut
# que ``clauses_cgv`` relit en FIN de module : le cycle d'import se résout
# dans les deux ordres de chargement.
from .clauses_cgv import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    _conditions_echappees, _puces_cgv, remplir_cgv_bullets)


def _cgv_bullets_html():
    """Puces CGV éditables rendues avec le MÊME enrobage <li> qu'avant.

    Les marqueurs {acompte}/{materiel}/{solde}/{tva_note} sont substitués par
    les valeurs dynamiques (PAY_A/PAY_M/PAY_S/TVA_NOTE) — par
    :func:`remplir_cgv_bullets`, la fonction que la page publique appelle
    aussi. Défaut → puces identiques au caractère près.
    """
    bullets = _puces_cgv(_doc_text("cgv_bullets"), LANGUE_SORTIE,
                         globals().get("MODE_INSTALLATION"))
    out = ""
    for txt in remplir_cgv_bullets(
            bullets, acompte=PAY_A, materiel=PAY_M, solde=PAY_S,
            tva_note=TVA_NOTE, valid_until=VALID_UNTIL,
            langue=LANGUE_SORTIE):
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
    tmpl = (_doc_text_langue("acceptance_stamp", "lg_accepte_le")
            or DEFAULT_DOC_TEXTS["acceptance_stamp"])
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

# Couleur du badge de marque. « dyness » est l'orthographe RÉELLE (correction
# fondateur 2026-08-18) ; « deyness » reste listé pour que les désignations
# FIGÉES des devis déjà émis gardent leur badge coloré.
_BRAND_C = {
    "huawei":   ("#CF0A2C", "#fff"),
    "canadian": ("#004B87", "#fff"),
    "canadien": ("#004B87", "#fff"),
    "deye":     ("#FF6B00", "#fff"),
    "dyness":   ("#FF6B00", "#fff"),
    "deyness":  ("#FF6B00", "#fff"),
}

# M6 (audit adversarial du 19/08/2026) \u2014 LE DICTIONNAIRE DE REPLI EST SUPPRIM\u00c9.
# Il attribuait \u00ab 10 ans \u00bb \u00e0 tout ce qui contient \u00ab onduleur \u00bb, \u00ab 12 ans \u00bb \u00e0
# tout ce qui contient \u00ab panneaux \u00bb, \u00ab 20 ans \u00bb aux structures\u2026 sur la foi d'un
# mot dans la d\u00e9signation, pour des produits dont AUCUNE garantie n'\u00e9tait
# saisie. Un document client engageait donc l'entreprise sur des dur\u00e9es
# invent\u00e9es. D\u00e9sormais : garantie saisie sur la fiche produit \u21d2 affich\u00e9e ;
# absente \u21d2 \u00ab \u2014 \u00bb. La colonne existe pour dire ce qu'on sait, pas pour la
# remplir.

# ── Helpers ──────────────────────────────────────────────────────────────────
def fmt(v):
    """Montant \u00e0 la fran\u00e7aise : 52\u202f650\u00a0MAD.

    Q8 (d\u00e9cision fondateur du 20/08/2026) \u2014 MAD PARTOUT. Le global ``DEVISE``
    imprimait l'\u00e9tiquette port\u00e9e par le devis, alors qu'AUCUN montant n'\u00e9tait
    jamais converti (le ``taux_change`` n'\u00e9tait lu nulle part) : un document
    \u00e9tiquet\u00e9 EUR aurait affich\u00e9 des dirhams sous un signe euro. L'\u00e9tiquette
    suit d\u00e9sormais la r\u00e9alit\u00e9 des montants.
    """
    # AMOT26 — HALF_UP par ``montants.fmt_dirhams`` (même dirham que l'écran).
    try:
        float(v)
    except Exception:
        logger.warning("generate_devis_premium.fmt : erreur ignorée (mode dégradé)", exc_info=True)
        return str(v)
    return fmt_dirhams(v) + "\u00a0MAD"

# QJR623 — ``_repartir_paiement`` (cases arrondies au millier, reliquat sur un
# total arrondi au dirham — ERR120) est SUPPRIMÉE : les montants des cases
# « Modalités de paiement » sont calculés au centime par le builder
# (``builder.repartition_paiement``) et servis dans ``montants_tranches``.


def fnum(v):
    """Format number with French thin-space thousands separator."""
    try:
        return f"{int(round(float(v))):,}".replace(",", "," if format_anglais() else "\u202f")
    except Exception:
        logger.warning("generate_devis_premium.fnum : erreur ignorée (mode dégradé)", exc_info=True)
        return str(v)

def kwc_fr(v):
    """QJR145 (a) — puissance à la française : 10,65 (jamais « 10.65 »).

    Le formateur existait depuis l'origine SANS aucun site d'appel : les cinq
    impressions de puissance du document sortaient le point décimal anglais.
    Les décimales inutiles sont retirées (« 10 kWc », pas « 10,00 kWc »).
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return decimale(f"{f:.2f}".rstrip("0").rstrip(".") or "0")


def _fdec_fr(v, decimales=2):
    """AGR302 — nombre à la française : entier sans décimale (« 80 »), sinon
    au plus ``decimales`` décimales sans zéro inutile, virgule décimale
    (« 5,5 », « 4,05 », « 62,5 »). Une valeur non numérique est rendue telle
    quelle (jamais un zéro inventé). Format seulement : aucun arrondi métier
    au-delà de la précision d'affichage.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return fnum(f)
    return (f"{f:.{decimales}f}".rstrip("0").rstrip(".")
            or "0").replace(".", ",")


def _renvoi_detail_complet():
    """AGR302 — où trouver les lignes retirées d'une table une-page tronquée.

    AGR312 — le pompage a de nouveau son document complet : le renvoi pointe
    vers le « document complet (3 pages) » du renderer agricole.
    """
    if (globals().get("MODE_INSTALLATION") or "").strip().lower() == "agricole":
        return _L("op_renvoi_agricole")
    return _L("op_renvoi_multipages")


def _kwc_mention(prefixe="&#160;", suffixe="&#160;kWc"):
    """QJR145 (a) — « 10,65 kWc » prêt à imprimer, ou RIEN.

    La case de confirmation de commande n'avait pas la garde
    ``PUISSANCE_INCONNUE`` que ``page1`` et ``build_html`` appliquent déjà :
    elle imprimait « Système photovoltaïque 0.0 kWc » sur un devis dont la
    puissance n'a aucun ancrage réel.
    """
    if PUISSANCE_INCONNUE or not KWC:
        return ""
    return f"{prefixe}{kwc_fr(KWC)}{suffixe}"

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

# STKCAT23 — LE RÔLE STOCKÉ D'UNE LIGNE → SA VIGNETTE. La table de mots-clés
# ci-dessous est au PLURIEL (« panneaux », « structures », « socles ») parce
# qu'elle lit une désignation de catalogue ; le vocabulaire de rôles, lui, est
# au SINGULIER (« panneau », « structure », « socle »). C'est exactement le
# genre d'écart qui faisait retomber une ligne « Panneau Jinko 710W » sur
# l'icône générique. Les trois familles d'onduleur et les deux alias dépréciés
# de structure partagent leur vignette : le PDF montre un équipement, pas une
# topologie. Les deux rôles de CÂBLE sont volontairement ABSENTS — il n'existe
# pas de vignette câble, ils doivent retomber sur le repli comme aujourd'hui.
_ICONE_PAR_ROLE = {
    "panneau":          "panneaux",
    "batterie":         "batterie",
    "smart_meter":      "smart meter",
    "wifi_dongle":      "wifi",
    "onduleur_reseau":  "onduleur",
    "onduleur_hybride": "onduleur",
    "onduleur_offgrid": "onduleur",
    "structure":        "structures",
    "structure_acier":  "structures",
    "structure_alu":    "structures",
    "socle":            "socles",
    "accessoires":      "accessoires",
    "tableau":          "tableau",
    "installation":     "installation",
    "transport":        "transport",
    "suivi":            "suivi",
}


def icon_img(des, _mar="", role=None):
    """La vignette d'une ligne : son RÔLE STOCKÉ d'abord, ses mots-clés ensuite.

    ``role`` est le ``LigneDevis.role_devis`` transporté par l'item (STKCAT23).
    Absent ou inconnu — toute ligne d'hier — la table de mots-clés décide, mot
    pour mot comme avant : c'est un REPLI PERMANENT, pas une transition.
    """
    d = (des or "").lower()
    key = _ICONE_PAR_ROLE.get(role or "")
    if   key: pass
    elif "panneaux"     in d: key = "panneaux"
    elif "batterie"     in d: key = "batterie"
    elif "smart meter"  in d: key = "smart meter"
    elif "wifi" in d or "dongle" in d: key = "wifi"
    elif is_inverter(d):      key = "onduleur"
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

def logo_html(role="entete"):
    """R3 — logo des en-têtes sombres (``quote_engine.logo``) : société ou
    TAQINOR (mot-marque seul en « entete », lockup avec tagline en « onepage »),
    dimensionné par la capitale du rôle ; repli texte sans asset."""
    try:
        b64_data = ENT_LOGO_B64 if ENT_LOGO_B64 is not None else _logo_dark_b64(role)
    except Exception:
        logger.warning("generate_devis_premium.logo_html : erreur ignorée (mode dégradé)", exc_info=True)
        b64_data = None
    if b64_data:
        return _logo.img_html(b64_data, role)
    return (f'<span style="font-size:15pt;font-weight:900;letter-spacing:1px;color:white;">'
            f'TAQIN<span style="color:{CA};">&#9728;</span>R</span>')

def _logo_dark_b64(role="couverture"):
    """R3 — base64 PNG du logo TAQINOR des fonds sombres pour un rôle (bloc
    lu dans ``quote_engine.logo``) ; None sans asset."""
    return _logo.taqinor_b64("sombre", _logo.bloc_taqinor(role)) or None

def logo_p1_dark():
    """Logo de la couverture sombre (R3 : lockup mot-marque + tagline, ou le logo société)."""
    try:
        b64_data = ENT_LOGO_B64 if ENT_LOGO_B64 is not None else _logo_dark_b64("couverture")
    except Exception:
        logger.warning("generate_devis_premium.logo_p1_dark : erreur ignorée (mode dégradé)", exc_info=True)
        b64_data = None
    if b64_data:
        return _logo.img_html(b64_data, "couverture", style="margin-bottom:10px;")
    # Fallback: text on dark background
    return (f'<div style="display:inline-block;">'
            f'<div style="font-size:17px;font-weight:900;color:white;letter-spacing:1px;line-height:1.1;">'
            f'TAQIN<span style="color:{CA};">&#9733;</span>R</div>'
            f'</div>')

def _filigrane_suffixe():
    """L-NIV (24/08/2026) suffixe DISCRET ajoute a la ligne
    Page N / Total | Ref. XXX existante quand WATERMARK_STANDARD
    est pose (niveau standard du lien public UNIQUEMENT, jamais le PDF
    interne). SUFFIXE d'une ligne deja la, jamais une nouvelle rangee :
    ZERO changement de hauteur de pied de page, donc zero changement de
    pagination, les tests de page-count tournent aussi filigrane actif."""
    if not WATERMARK_STANDARD:
        return ""
    return f" &nbsp;|&nbsp; {WATERMARK_STANDARD}"


def _marques_correction_html(style):
    """QJR628 — « Document mis à jour le … » / « Remplace le devis … » sous la
    date d'en-tête ; '' quand le devis n'a été ni corrigé après envoi ni
    révisé (octet-identique)."""
    out = ""
    if MIS_A_JOUR_LE:
        out += (f'<div style="{style}">'
                f'{_L("lg_mis_a_jour_le").format(date=MIS_A_JOUR_LE)}</div>')
    if REMPLACE_REF:
        out += f'<div style="{style}">{_L("lg_remplace_devis").format(ref=REMPLACE_REF)}</div>'
    return out


def footer_p1():
    """Page 1 footer — white background."""
    return (f'<div style="background:white;padding:7px 24px;flex-shrink:0;display:flex;'
            f'align-items:center;justify-content:space-between;border-top:1px solid {CG2};">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>'
            f'<div style="font-size:7pt;color:#888888;text-align:center;">'
            f'{ENT_CONTACT_LINE}</div>'
            f'<div style="font-size:7pt;color:#888888;">{_L("res_page")} 1&nbsp;/&nbsp;{PAGES_TOTAL} &nbsp;|&nbsp; {_L("lg_ref")}&nbsp;{REF}{_filigrane_suffixe()}</div>'
            f'</div>')

def footer(n, total=None):
    """Pages 2-3 footer — dark navy."""
    total = total or PAGES_TOTAL
    return (f'<div style="background:{CN};padding:7px 24px;flex-shrink:0;display:flex;'
            f'align-items:center;justify-content:space-between;">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>'
            f'<div style="font-size:7pt;color:#888;text-align:center;">'
            f'{ENT_CONTACT_LINE}</div>'
            f'<div style="font-size:7pt;color:#888;">{_L("res_page")} {n}&nbsp;/&nbsp;{total} &nbsp;|&nbsp; {_L("lg_ref")}&nbsp;{REF}{_filigrane_suffixe()}</div>'
            f'</div>')

def footer_p3(extra_style=""):
    """Page 3 footer — dark navy + legal identity line."""
    return (f'<div style="{extra_style}background:{CN};padding:6px 24px 5px;flex-shrink:0;">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">'
            f'<div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>'
            f'<div style="font-size:7pt;color:#888;text-align:center;">'
            f'{ENT_CONTACT_LINE}</div>'
            f'<div style="font-size:7pt;color:#888;">{_L("res_page")} {PAGE3_NUM}&nbsp;/&nbsp;{PAGES_TOTAL} &nbsp;|&nbsp; {_L("lg_ref")}&nbsp;{REF}{_filigrane_suffixe()}</div>'
            f'</div>'
            f'<div style="font-size:7.5px;color:#888;text-align:center;font-style:italic;">'
            f'{ENT_LEGAL_LINE}'
            f'</div>'
            f'</div>')

# ── Data loading ──────────────────────────────────────────────────────────────────────────
# QJR145 (e) — ``load_equip`` SUPPRIMÉ : code mort (zéro site d'appel dans
# tout le dépôt) qui lisait un ``devis_history.json`` d'archive via pandas et
# fabriquait des lignes à ``prix_unit_ttc = 0`` quand la colonne de prix
# manquait. Les données du document viennent du builder, et de lui seul.

# ── Charts ────────────────────────────────────────────────────────────────────
def _style_ax(fig, ax):
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#E5E7EB"); ax.spines["bottom"].set_color("#E5E7EB")
    ax.tick_params(colors=CG4, labelsize=8)
    ax.grid(axis="y", color="#F3F4F6", linewidth=0.8, zorder=0)

def _roi_de_la_courbe(cumul):
    """QJR125 — année du croisement à ZÉRO de la série TRACÉE (interpolée).

    L'étoile « ROI ~N ans » était posée à l'abscisse de ``roi_s``/``roi_a``,
    qui redevient un payback LINÉAIRE (``_ref_total / eco``) dès que l'étude
    porte ses propres économies : le point d'équilibre ANNONCÉ ne coïncidait
    alors pas avec celui DESSINÉ, sous un titre qui promet « Point de retour
    sur investissement ». ``None`` quand la courbe ne croise jamais zéro —
    l'étoile n'est alors pas posée.
    """
    for annee in range(1, len(cumul)):
        if cumul[annee] >= 0:
            precedent = cumul[annee - 1]
            span = cumul[annee] - precedent
            frac = (0 - precedent) / span if span else 0.0
            return round((annee - 1) + frac, 1)
    return None


def _courbes_roi_tracables():
    """QJR125 — les branches AFFICHÉES portent-elles toutes leur cumul réel ?"""
    if SCENARIO != 'Avec batterie' and not CUMUL_S_REEL:
        return False
    if SCENARIO != 'Sans batterie' and not CUMUL_A_REEL:
        return False
    return True


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
        ax.plot(x, ya, color=CA,  linewidth=2.5, label=LIBELLE_AVEC,  zorder=4, solid_capstyle="round")
    # QJR125 — l'étoile sort du croisement à zéro de la courbe TRACÉE, plus du
    # payback annoncé ailleurs : les deux pouvaient désigner deux années
    # différentes sur la même image. Pas de croisement ⇒ pas d'étoile.
    _roi_pts = []
    if _show_s:
        _r = _roi_de_la_courbe(CUMUL_S)
        if _r is not None:
            _roi_pts.append((_r, CUMUL_S, CNM, f"ROI ~{_r} ans"))
    if _show_a:
        _r = _roi_de_la_courbe(CUMUL_A)
        if _r is not None:
            _roi_pts.append((_r, CUMUL_A, CA, f"ROI ~{_r} ans"))
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

    # M1 — factures RÉELLES uniquement. Vide = le client n'a pas donné ses 12
    # factures : la carte devient « économies solaires par mois », sans barre
    # ni légende ONEE. On ne dessine jamais une facture reconstruite.
    _onee_m = list(FACTURES_M or [])
    _has_bills = len(_onee_m) == 12

    # Même ratio 4:1 que le cadre 680×170 — image pleine, jamais en vignette.
    fig, ax = plt.subplots(figsize=(13.6, 3.4), dpi=140)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#EAECF0"); ax.spines["bottom"].set_color("#EAECF0")
    ax.spines["left"].set_linewidth(0.8); ax.spines["bottom"].set_linewidth(0.8)

    x = np.arange(12)
    c_bar = "#B5C0CE"  # light steel-blue/grey for ONEE bill bars

    # Bars: ONEE bill — full-width, one per month (seulement si RÉELLES)
    if _has_bills:
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
    legend_handles = []
    if _has_bills:
        legend_handles.append(
            Patch(facecolor=c_bar, alpha=0.60, label="Facture ONEE sans PV",
                  linewidth=0))
    if _show_s:
        legend_handles.append(Line2D([0], [0], color=CNM, linewidth=2.2, marker="o", markersize=5.5,
               markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CNM,
               label="\u00c9conomies Option\u00a01 \u2013 Sans batterie"))
    if _show_a:
        legend_handles.append(Line2D([0], [0], color=CA,  linewidth=2.2, marker="o", markersize=5.5,
               markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=CA,
               label=f"\u00c9conomies Option\u00a02 \u2013 {LIBELLE_AVEC}"))
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
# QJR613 — formateur au centime partagé (``quote_engine/montants.py``).
_fmt2 = fmt_centimes
_fmt2_mad = fmt_centimes_mad


def _item_pu_ht(it):
    """Per-line HT unit price (stored, or derived from the TTC).

    QJR146 (e) — LE TAUX DE DÉRIVATION EST CELUI DE LA LIGNE. Le repli
    divisait par le taux GLOBAL du devis (``TVA_PCT``) alors que la MÊME ligne
    imprime son PROPRE taux dans la colonne d'à côté (``it['taux_tva']``,
    réforme des taux par ligne) : sur un devis mixte 20 %/10 %, le P.U. HT
    d'une ligne à 10 % sortait 8,3 % trop bas, sous un « 10% » affiché. Le
    taux global reste le repli quand la ligne n'en porte pas.
    """
    pu_ht = it.get("prix_unit_ht")
    if pu_ht is None:
        taux = it.get("taux_tva")
        if taux in (None, ""):
            taux = TVA_PCT
        try:
            taux = float(taux)
        except (TypeError, ValueError):
            taux = float(TVA_PCT)
        pu_ht = it["prix_unit_ttc"] / (1 + taux / 100)
    return float(pu_ht)


# ── QJRREM — LA REMISE GLOBALE SUR CHAQUE LIGNE ──────────────────────────────
# Demande fondateur (07/09/2026) : « la remise de 5 % est gardée partout et
# s'applique aussi à chaque poste de la liste des composants, de l'installation,
# de tout ». Le moteur RENDAIT chaque ligne au prix CATALOGUE avec une unique
# ligne « Remise (X %) » plus bas : le client ne pouvait rapprocher aucun poste
# de la remise qu'il venait de négocier.
#
# CE QUI NE BOUGE PAS. La chaîne « Sous-total HT → Remise (X %) → Total HT →
# TVA → Total TTC » est intacte (Sous-total = somme CATALOGUE, Total HT = net),
# les valeurs viennent toujours du builder (aucun calcul ici), et la carte
# d'option garde son prix barré + son badge « −X % REMISE ».
#
# CE QUI CHANGE. Les colonnes P.U. et Total portent DEUX nombres DANS LA MÊME
# CELLULE : le prix catalogue barré, en petit, puis le prix après remise en
# chiffre principal. Aucune ligne de tableau supplémentaire — la pagination des
# trois formats (3 pages / 4 avec étude / une page qui ne déborde jamais) ne
# peut donc pas bouger du fait d'une remise.


def _item_pu_ht_remise(it):
    """P.U. HT APRÈS remise globale — le catalogue si la clé n'est pas là.

    Le repli couvre les appelants historiques qui bâtissent leurs items à la
    main (tests de gabarit, échantillons) : sans la clé du builder, la cellule
    affiche exactement ce qu'elle affichait avant.
    """
    valeur = it.get("pu_ht_remise")
    return float(valeur) if valeur is not None else _item_pu_ht(it)


def _item_total_ht_remise(it):
    """Total HT de la ligne APRÈS remise globale — le catalogue à défaut."""
    valeur = it.get("total_ht_remise")
    if valeur is not None:
        return float(valeur)
    try:
        qte = float(it.get("quantite") or 0)
    except (TypeError, ValueError):
        qte = 0.0
    return qte * _item_pu_ht(it)


def _cellule_prix_remise(valeur_catalogue, valeur_remisee, taille="0.78em"):
    """Prix catalogue BARRÉ puis prix remisé, dans UNE SEULE cellule.

    Sans remise globale (le cas courant), rend exactement ``_fmt2`` de la
    valeur CATALOGUE — c'est-à-dire l'expression d'avant, mot pour mot, et non
    une valeur re-dérivée qui pourrait différer d'un bit de flottant.
    """
    if DISCOUNT_PCT <= 0:
        return _fmt2(valeur_catalogue)
    return (f'<span style="font-size:{taille};color:{CG4};'
            f'text-decoration:line-through;white-space:nowrap;">'
            f'{_fmt2(valeur_catalogue)}</span> '
            f'<span style="white-space:nowrap;">{_fmt2(valeur_remisee)}</span>')


def _note_remise_par_ligne():
    """LA phrase qui dit ce que le tableau montre — jamais un nombre de plus.

    Un seul chiffre y figure : le pourcentage de remise déjà imprimé par le
    bloc de totaux. Aucune remise ⇒ chaîne vide (rien n'est ajouté au
    document).
    """
    if DISCOUNT_PCT <= 0:
        return ""
    pct = pct_fr(DISCOUNT_PCT)  # AMOT24
    return _L("lg_note_remise").format(pct=pct)


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


def _totals_block_rows(totaux, colspan, ancres=None):
    """Sous-total HT \u2192 Remise visible \u2192 Total HT \u2192 TVA \u2192 Total TTC.

    Renders the CANONICAL totals computed once by the builder \u2014 every page
    shows these exact figures (never re-derived, no rounding drift).

    QA-FIGURES — ``ancres`` : ``None`` → aucun marqueur (bloc masqué ou
    appelant hors document) ; ``"sans"``/``"avec"`` → marqueurs de cette
    option ; ``""`` → marqueurs du document entier. L'ancre vit dans la
    cellule VIDE de tête de ligne : les cellules libellé/montant sont intactes.
    """
    total_ht = totaux["ht_brut"]
    remise = totaux["remise"]
    net_ht = totaux["ht_net"]
    tva = totaux["tva"]
    ttc = totaux["ttc"]

    def row(label, value, navy=False, neg=False, fig=None, taux=None):
        color = CA if navy else (CGR if neg else CG7)
        bg = f"background:{CN};" if navy else f"background:{CG1};"
        weight = 800 if navy else 600
        _a = ("" if (ancres is None or fig is None)
              else _ancre_figure(fig, value, ancres, taux))
        return (f'<tr style="{bg}"><td>{_a}</td>'
                f'<td colspan="{colspan}" style="text-align:right;color:{color};'
                f'font-weight:{weight};padding:3px 5px;">{label}</td>'
                f'<td style="text-align:right;color:{color};font-weight:{weight};'
                f'padding:3px 5px;white-space:nowrap;">{value}</td></tr>')

    # ARRONDI-100 \u2014 la baisse qui ram\u00e8ne le Total TTC au palier de 100 MAD
    # inf\u00e9rieur : une ligne VISIBLE entre la remise et le Total HT (les prix
    # des lignes ne bougent pas), absente quand le total y est d\u00e9j\u00e0.
    arrondi = totaux.get("arrondi") or 0
    rows = row(_L("sous_total_ht"), _fmt2(total_ht), fig="sous_total_ht")
    if DISCOUNT_PCT > 0:
        pct = pct_fr(DISCOUNT_PCT)  # AMOT24
        rows += row(_L("lg_remise_pct").format(pct=pct), "\u2212" + _fmt2(remise), neg=True,
                    fig="remise")
    if arrondi > 0:
        rows += row(_L("arrondi"), "\u2212" + _fmt2(arrondi), neg=True,
                    fig="arrondi")
    if DISCOUNT_PCT > 0 or arrondi > 0:
        rows += row(_L("total_ht"), _fmt2(net_ht), fig="total_ht")
    # TVA \u00e9clat\u00e9e par taux (r\u00e9forme 10/20) \u2014 une ligne par taux pr\u00e9sent ;
    # un seul taux (devis historiques) \u2192 exactement l'ancienne ligne unique.
    buckets = totaux.get("tva_par_taux") or []
    if len(buckets) > 1:
        for b in buckets:
            r = pct_fr(b["taux"])  # AMOT24
            rows += row(_L("lg_tva_pct").format(r=r), _fmt2(b["montant"]),
                        fig="tva_taux", taux=b["taux"])
    else:
        rate = buckets[0]["taux"] if buckets else TVA_PCT
        tva_pct = pct_fr(rate)  # AMOT24
        rows += row(_L("lg_tva_pct").format(r=tva_pct), _fmt2(tva), fig="tva")
    # QJR122 — le Total TTC s'imprime AU CENTIME, comme les lignes au-dessus.
    # ``fmt`` arrondissait à l'unité : la chaîne affichée n'additionnait pas
    # (52 655,42 + 10 531,08 s'imprimait « 63 186 MAD »), et c'est ce montant
    # qui sert de base à l'échéancier de la page 3.
    rows += row(_L("total_ttc"), _fmt2_mad(ttc), navy=True, fig="total_ttc")
    return rows


def _ans(mois):
    """Mois → années entières, ou None si la fiche produit ne dit rien (M6)."""
    try:
        m = int(mois)
    except (TypeError, ValueError):
        return None
    return m // 12 if m >= 12 else None


def _gar_de_la_fiche(it):
    """« N ans » lu sur la FICHE PRODUIT de la ligne, ou '' (M6).

    Jamais un mot-clé de désignation : la garantie est une donnée du produit,
    pas une déduction sur son nom.
    """
    n = _ans(it.get("garantie_mois"))
    return _L("res_n_ans").format(n=n) if n else ""


def _garanties_du_devis():
    """Garanties RÉELLES des lignes rendues : [(années, libellé), …] (M6).

    Lit les fiches produit des lignes de l'option affichée — onduleur, panneaux
    (garantie produit), panneaux (garantie de PRODUCTION), batterie. Une
    famille dont aucune ligne ne porte de garantie saisie est ABSENTE de la
    liste : les badges de la page signature affichaient « 10 / 12 / 30 ANS »
    en dur, quels que soient les produits réellement vendus.

    QJR145 (d) — sur un document « Les deux (Sans + Avec) », les garanties
    partaient de ``SANS_ITEMS`` seul : la BATTERIE, qui n'existe que dans
    ``AVEC_ITEMS``, n'obtenait JAMAIS son badge alors que le document la vend.
    Les deux paniers sont donc unis avant d'extraire les familles — c'est déjà
    ce que fait ``residential.theme._composition_rows`` pour la même raison.
    """
    if SCENARIO == 'Avec batterie':
        rows = list(AVEC_ITEMS or [])
    elif SCENARIO == 'Sans batterie':
        rows = list(SANS_ITEMS or [])
    else:
        rows = list(SANS_ITEMS or []) + list(AVEC_ITEMS or [])
    rows = rows or list(SANS_ITEMS or []) or list(AVEC_ITEMS or [])

    def _premier(pred, champ):
        for it in rows:
            if pred((it.get("designation") or "").lower()):
                n = _ans(it.get(champ))
                if n:
                    return n
        return None

    _pan = lambda d: "panneau" in d or "module" in d
    _bat = lambda d: "batterie" in d

    out = []
    n = _premier(is_inverter, "garantie_mois")
    if n:
        out.append((n, _L("lg_gar_onduleur")))
    n = _premier(_pan, "garantie_mois")
    if n:
        out.append((n, _L("lg_gar_panneaux_produit")))
    n = _premier(_pan, "garantie_production_mois")
    if n:
        # Sans le pourcentage : « 87,4 % » est une spec Canadian Solar, elle ne
        # vaut pas pour un panneau d'une autre marque garanti la même durée.
        out.append((n, _L("lg_gar_performance")))
    n = _premier(_bat, "garantie_mois")
    if n:
        out.append((n, _L("lg_gar_batterie")))
    return out


def _lignes_option_rendue():
    """Lignes de l'option effectivement présentée (même choix que M6)."""
    rows = AVEC_ITEMS if SCENARIO == 'Avec batterie' else SANS_ITEMS
    return list(rows or []) or list(SANS_ITEMS or []) or list(AVEC_ITEMS or [])


def _marques_du_devis():
    """QJR121 — marques RÉELLEMENT vendues, par famille.

    Même principe que ``_garanties_du_devis`` : la page signature ne peut
    affirmer que ce que les LIGNES du devis portent. La source est le champ
    ``marque`` de la fiche produit (celui-là même qu'imprime le tableau de la
    page 2) — jamais une marque devinée dans une désignation libre. Aucune
    marque lisible ⇒ dict vide ⇒ la carte est OMISE.
    """
    familles = {"panneaux": [], "onduleurs": [], "batteries": []}
    predicats = (
        ("panneaux", lambda d: "panneau" in d or "module" in d),
        ("onduleurs", is_inverter),
        ("batteries", lambda d: "batterie" in d),
    )
    for it in _lignes_option_rendue():
        des = (it.get("designation") or "").lower()
        marque = (it.get("marque") or "").strip()
        if not marque:
            continue
        for cle, pred in predicats:
            if pred(des) and marque not in familles[cle]:
                familles[cle].append(marque)
                break
    return {k: v for k, v in familles.items() if v}


#: Mots des désignations qui ATTESTENT une supervision vendue (passerelle,
#: compteur communicant, dongle…). Sans l'un d'eux, aucune application de
#: monitoring n'est promise : un devis pompage n'en porte aucune.
_MOTS_MONITORING = ("monitoring", "supervis", "dongle", "wifi", "wi-fi",
                    "smart meter", "smartmeter", "datalogger", "data logger",
                    "passerelle", "compteur communicant")


def _monitoring_vendu():
    """QJR121 — une ligne du devis porte-t-elle la supervision promise ?"""
    for it in _lignes_option_rendue():
        blob = "%s %s" % ((it.get("designation") or "").lower(),
                          (it.get("_produit_nom") or "").lower())
        if any(mot in blob for mot in _MOTS_MONITORING):
            return True
    return False


def _struct_row_legacy(s, colspan):
    """QJR619 — ligne de STRUCTURE (section = intertitre pleine largeur, note =
    ligne en italique), sans prix — même rendu que le une-page (XSAL14)."""
    txt = s.get("texte", "") or ""
    if s.get("type") == "note":
        return (f'<tr><td colspan="{colspan}" style="font-style:italic;'
                f'color:{CG4};padding:3px 6px;">{txt}</td></tr>')
    return (f'<tr><td colspan="{colspan}" style="background:{CG1};'
            f'font-weight:800;color:{CN};text-transform:uppercase;'
            f'letter-spacing:.5px;padding:3px 6px;border-top:1px solid {CA};">'
            f'{txt}</td></tr>')


def _rangs_totaux(t):
    """RPDF21 — nombre de rangées que ``_totals_block_rows`` imprime pour ``t``."""
    rem, arr = DISCOUNT_PCT > 0, (t.get("arrondi") or 0) > 0
    return 3 + rem + arr + (rem or arr) + max(0, len(t.get("tva_par_taux") or []) - 1)


def equip_rows(items, totaux, hi_bat=False, ancres=None):
    rows = ""
    # QJR619 — sections / notes intercalées à leur ``ordre`` (QJR617) ; sans
    # structure, la boucle d'hier à l'identique.
    if LIGNES_STRUCTURE:
        _seq = sequence_affichage(items, LIGNES_STRUCTURE)
    else:
        _seq = [("item", it) for it in items]
    i = -1
    for _kind, it in _seq:
        if _kind == "struct":
            rows += _struct_row_legacy(it, 7)
            continue
        i += 1
        des = it["designation"]; qty = it["quantite"]
        pu_ht = _item_pu_ht(it)
        mar = (it.get("marque") or "").strip()
        # M3 (audit du 19/08/2026) \u2014 la D\u00c9SIGNATION FACTUR\u00c9E N'EST JAMAIS
        # R\u00c9\u00c9CRITE. Le moteur ajoutait \u00ab 710 Wc \u00bb au libell\u00e9 contractuel d'une
        # ligne, avec une puissance qui pouvait n'avoir \u00e9t\u00e9 lue nulle part
        # (d\u00e9faut catalogue) : le document engageait alors une caract\u00e9ristique
        # que le devis ne portait pas. La ligne s'affiche telle qu'elle est
        # factur\u00e9e ; la puissance vit dans la vignette \u00ab Puissance install\u00e9e \u00bb,
        # qui, elle, sait s'omettre.
        # STKCAT23 — la vignette lit le RÔLE STOCKÉ de la ligne d'abord ; sans
        # rôle (toute ligne d'hier), les mots-clés de la désignation décident.
        ico = icon_img(des, mar, it.get("role_devis")); bdg = badge(mar)
        # M6 \u2014 la garantie vient de la FICHE PRODUIT, ou n'est pas affich\u00e9e.
        gar = (it.get("garantie") or "").strip() or _gar_de_la_fiche(it) or "\u2014"
        # Texte de garantie complet \u2014 il S'ENROULE dans la colonne, jamais
        # tronqu\u00e9 en plein mot.
        is_bat = "batterie" in des.lower() and hi_bat
        bg = f"background:{CAL};" if is_bat else (f"background:{CG1};" if i % 2 == 1 else "")
        qty_s = int(qty) if qty == int(qty) else qty
        desc_html = _desc_lines_html(it, max_lines=2, font_pt=5) + ci_tableau.sous_lignes_html(it, 5, CG4)  # R2
        # QJR146 (e) \u2014 LE TIRET NE MASQUE QUE L'ABSENCE DE PRIX, jamais un
        # prix N\u00c9GATIF. ``pu_ht > 0`` renvoyait \u00ab \u2014 \u00bb sur une ligne \u00e0 montant
        # n\u00e9gatif (une reprise, un geste commercial pass\u00e9 en ligne) alors que
        # ce montant P\u00c8SE dans le sous-total imprim\u00e9 juste dessous : le client
        # ne pouvait pas rapprocher les lignes du total. Seul un prix NUL
        # continue de s'afficher en tiret.
        dash = "\u2014"
        # QJRREM - deux nombres dans la MEME cellule (catalogue barre + remise)
        # des qu'une remise globale existe ; sinon, le formatage d'avant.
        pu_ht_s = (_cellule_prix_remise(pu_ht, _item_pu_ht_remise(it))
                   if pu_ht else dash)
        tot_ht_s = (_cellule_prix_remise(qty * pu_ht, _item_total_ht_remise(it))
                    if pu_ht else dash)
        taux = it.get("taux_tva", TVA_PCT)
        taux_s = f"{pct_fr(taux)}%"  # AMOT24
        rows += (f'<tr style="{bg}"><td class="ti">{ico}</td>'
                 f'<td class="tl">{des}{"<br>" + bdg if bdg else ""}{desc_html}</td>'
                 f'<td class="tc" style="word-wrap:break-word;font-size:5pt;">{gar}</td>'
                 f'<td class="tc">{qty_s}</td>'
                 f'<td class="tr">{pu_ht_s}</td>'
                 f'<td class="tc" style="font-size:5.5pt;">{taux_s}</td>'
                 f'<td class="tr">{tot_ht_s}</td></tr>')
    rows += _totals_block_rows(totaux, colspan=5, ancres=ancres)
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
    # QJR53 (30/08/2026) \u2014 LE MEME ARRONDI QUE ``fmt``, SUR TOUTES LES PAGES.
    # Ces deux cartes d'option de la page 1 TRONQUAIENT (``int(x)``) pendant
    # que le bloc \u00ab Total TTC \u00bb de la page 2 ARRONDIT (``fmt`` fait
    # ``int(round(x))``). Tant que le builder rendait un TTC deja arrondi au
    # dirham, les deux expressions donnaient le meme entier et l'ecart etait
    # invisible ; depuis que la donnee est au CENTIME, un total en ,5+ sort
    # DIFFERENT d'une page a l'autre \u2014 51 232,80 s'imprimait \u00ab 51 232 \u00bb sur la
    # carte et \u00ab 51 233 \u00bb dans le bloc de totaux, pour la MEME option, sur le
    # document du client. Le format d'affichage reste le DIRHAM (convention
    # maison de ``fmt``, et les tranches de paiement de ce document sont
    # arrondies au millier) : seule la regle d'arrondi est alignee.
    ts      = f"{int(round(TOTAL_SANS)):,}".replace(",", _s) + "\u00a0MAD"
    ta      = f"{int(round(TOTAL_AVEC)):,}".replace(",", _s) + "\u00a0MAD"
    esa_mad = f"{int(ECO_S_ANN):,}".replace(",", _s) + "\u00a0MAD"
    eaa_mad = f"{int(ECO_A_ANN):,}".replace(",", _s) + "\u00a0MAD"
    pk      = f"{int(PROD_KWH):,}".replace(",", _s)
    # QXMT \u2014 dossier raccord\u00e9 en MOYENNE TENSION sans \u00e9conomies d'\u00e9tude : la
    # pastille \u00ab Retour en N ans \u00bb et l'encadr\u00e9 \u00ab \u00c9conomie estim\u00e9e \u00bb sont OMIS
    # des cartes d'option. Les valeurs disponibles ici (ROI_S/ROI_A,
    # ECO_S_ANN/ECO_A_ANN) sortent de ``calculate_savings_roi``, au bar\u00e8me
    # BASSE TENSION de l'ONEE : un dossier MT ne porte JAMAIS ce chiffre-l\u00e0.
    # Hors dossier MT (cas de tr\u00e8s loin le plus courant), les deux fragments
    # sont EXACTEMENT le HTML d'hier \u2014 rendu byte-identique.
    _mt_note = (
        '<div style="background:#FFF8E1;border:1px solid #E8A020;'
        'border-radius:5px;padding:5px 9px;font-size:6.5pt;line-height:1.35;'
        f'color:{CG4};">{_L("lg_mt_note")}</div>')
    if MASQUER_ECONOMIES or PUISSANCE_INCONNUE:
        # M2 — puissance sans ancrage : les économies et le retour sur
        # investissement en dérivent (ils valent 0), on les OMET plutôt que
        # d'imprimer « Retour en 0 ans ». La note MT ne s'affiche, elle, que
        # pour un vrai dossier moyenne tension.
        _roi_pill_s = _roi_pill_a = ""
        _eco_box_s = _eco_box_a = _mt_note if MASQUER_ECONOMIES else ""
    else:
        _roi_pill_s = (
            '<div style="display:inline-block;align-self:flex-start;'
            'background:#e8f5e9;color:#2e7d32;border-radius:12px;'
            'padding:4px 10px;font-size:13px;font-weight:600;'
            f'margin-bottom:7px;">{SVG_CHART}'
            + (_L("res_non_rentabilise_25") if ROI_S_JAMAIS
               else _L("lg_retour_en").format(n=kwc_fr(ROI_S))) + '</div>') if (ROI_S_JAMAIS or ROI_S > 0) else ""
        _roi_pill_a = (
            '<div style="display:inline-block;align-self:flex-start;'
            'background:#1a1a2e;color:white;border-radius:12px;'
            'padding:4px 10px;font-size:13px;font-weight:600;'
            f'margin-bottom:7px;">{SVG_CHART2}'
            + (_L("res_non_rentabilise_25") if ROI_A_JAMAIS
               else _L("lg_retour_en").format(n=kwc_fr(ROI_A))) + '</div>') if (ROI_A_JAMAIS or ROI_A > 0) else ""
        _mt_src = (
            f'<div style="font-size:6pt;color:{CG4};margin-top:3px;'
            f'line-height:1.3;">{TARIF_MT_MENTION}</div>'
            if TARIF_MT_MENTION else "")
        # Le HTML est reproduit AU CARACTÈRE PRÈS (sauts de ligne et indentation
        # compris) : hors dossier MT, le rendu reste byte-identique — deux
        # <span> inline séparés par un blanc ne s'affichent pas comme deux
        # <span> collés.
        _eco_box_s = (
            f'<div style="background:{CG1};border:1px solid {CG2};'
            'border-radius:5px;padding:5px 9px;">\n'
            f'        <span style="font-size:7pt;color:{CG4};">'
            f'{_L("lg_eco_estimee")}</span>\n'
            f'        <span style="font-size:10pt;font-weight:800;color:{CN};">'
            f'{esa_mad}{_L("lg_par_an")}</span>{_mt_src}\n'
            '      </div>')
        _eco_box_a = (
            f'<div style="background:white;border:1px solid {CG2};'
            'border-radius:5px;padding:5px 9px;">\n'
            f'        <span style="font-size:7pt;color:{CG4};">'
            f'{_L("lg_eco_estimee")}</span>\n'
            f'        <span style="font-size:10pt;font-weight:800;color:{CN};">'
            f'{eaa_mad}{_L("lg_par_an")}</span>{_mt_src}\n'
            '      </div>')
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
    _r1   = (f'<div style="{_badge_css}">{SVG_STAR} {_L("lg_recommande_maj")}</div>'
             if _both and RECOMMENDED == 'Sans batterie' else '')
    _r2   = (f'<div style="{_badge_css}">{SVG_STAR} {_L("lg_recommande_maj")}</div>'
             if _both and RECOMMENDED == 'Avec batterie' else '')
    # Price display — crossed-out original + discount badge + new price when discount active
    if DISCOUNT_PCT > 0:
        # QJR53 \u2014 meme alignement que ``ts``/``ta`` ci-dessus : le prix
        # barre est le MEME montant, il ne peut pas suivre une autre regle
        # d'arrondi que le total qu'il barre.
        _s_before = f"{int(round(TOTAL_SANS_BEFORE)):,}".replace(",", _s) + "\u00a0MAD"
        _a_before = f"{int(round(TOTAL_AVEC_BEFORE)):,}".replace(",", _s) + "\u00a0MAD"
        # AMOT24 ; devis envoyé avant la correction (décision 08/10/2026) :
        # la remise tronquée d'hier.
        _disc_str = (f"\u2212{int(DISCOUNT_PCT)}\u202f%" if regles_origine()
                     else f"\u2212{pct_fr(DISCOUNT_PCT)}\u202f%")
        _ts_price = (
            f'<div style="font-size:10pt;color:{CG4};text-decoration:line-through;'
            f'opacity:0.75;margin-bottom:1px;white-space:nowrap;">{_s_before}</div>'
            f'<div style="margin-bottom:4px;">'
            f'<span style="background:{CA};color:{CN};border-radius:3px;padding:2px 8px;'
            f'font-size:6pt;font-weight:800;letter-spacing:0.5px;">{_disc_str}\u00a0{_L("lg_remise_maj")}</span>'
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
            f'font-size:6pt;font-weight:800;letter-spacing:0.5px;">{_disc_str}\u00a0{_L("lg_remise_maj")}</span>'
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
    # F1/L-2OPT (26/08/2026) — chaque option divise SON total par SON kWc : le
    # scalaire global porte l'option AVEC dès que les champs PV divergent, donc
    # l'option 1 affichait un prix au kWc ~15 % trop bas (total « sans » ÷ kWc
    # « avec »). Options égales ⇒ les deux kWc valent ``KWC``, byte-identique.
    _kwc_s = KWC_SANS if (PANNEAUX_DIVERGENTS and KWC_SANS > 0) else KWC
    _kwc_a = KWC_AVEC if (PANNEAUX_DIVERGENTS and KWC_AVEC > 0) else KWC
    _pkwc_s = _L("lg_soit_kwc").format(prix=fmt(TOTAL_SANS / _kwc_s)) if _kwc_s > 0 else ''
    _pkwc_a = _L("lg_soit_kwc").format(prix=fmt(TOTAL_AVEC / _kwc_a)) if _kwc_a > 0 else ''
    # QA-FIGURES — une carte MASQUÉE (``display:none`` selon le scénario) ne
    # porte aucun marqueur : seul ce que le client VOIT est comparé.
    _fig_eco = not (MASQUER_ECONOMIES or PUISSANCE_INCONNUE)
    for _vis, _opt, _tt, _kw, _roi, _eco, _jamais in (
            (not _s1, "sans", ts, _kwc_s, ROI_S, esa_mad, ROI_S_JAMAIS),
            (not _s2, "avec", ta, _kwc_a, ROI_A, eaa_mad, ROI_A_JAMAIS)):
        if not _vis:
            continue
        _anc = _ancre_figure("total_ttc", _tt, _opt)
        if _kw > 0:
            _anc += _ancre_figure(
                "prix_kwc", fmt((TOTAL_SANS if _opt == "sans" else TOTAL_AVEC)
                                / _kw), _opt)
        if _fig_eco:
            # ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — aucun marqueur de
            # payback quand l'option ne se rembourse jamais (rien n'est imprimé).
            _anc += ((_ancre_figure("payback_ans", _roi, _opt)
                      if not _jamais else "")
                     + _ancre_figure("economie_annuelle", _eco, _opt))
        if _opt == "sans":
            _ts_price += _anc
        else:
            _ta_price += _anc
    # Puces générées depuis l'équipement RÉEL de chaque option (jamais de
    # texte boilerplate qui contredirait la liste d'équipements).
    _sb_lis = "".join(f"<li>{SVG_CHECK}{b}</li>" for b in SANS_BULLETS) or \
        f"<li>{SVG_CHECK}{_L('lg_eq_detaille_p2')}</li>"
    _ab_lis = "".join(f"<li>{SVG_CHECK}{b}</li>" for b in AVEC_BULLETS) or \
        f"<li>{SVG_CHECK}{_L('lg_eq_detaille_p2')}</li>"
    # KPI economies card — scenario-aware
    # QXMT — dossier MT sans économies d'étude : la vignette annonce l'absence
    # de chiffre plutôt qu'un montant calculé au barème BASSE TENSION.
    # AMOT52 — chaque branche pose ses trois valeurs en une instruction ; le
    # sous-libellé suit la langue du document.
    if MASQUER_ECONOMIES:
        _eco_val, _eco_size, _eco_sub = (
            '<span style="white-space:nowrap;">&#8212;</span>', "17pt", _L("lg_chiffrees_mt"))
    else:
        # M10 — une économie du modèle « estimation » porte la mention sur TOUS
        # les formats : sans barème réel du client, le chiffre est un ordre de
        # grandeur, et le document doit le dire là où il l'affiche.
        _est = _L("op_estimation") if SAVINGS_ESTIMATED else ""
        if SCENARIO == 'Sans batterie':
            _eco_val, _eco_size, _eco_sub = (
                f'<span style="white-space:nowrap;">{esa_mad}</span>', "17pt",
                _L("lg_eco_par_an").format(est=_est))
        elif SCENARIO == 'Avec batterie':
            _eco_val, _eco_size, _eco_sub = (
                f'<span style="white-space:nowrap;">{eaa_mad}</span>', "17pt",
                _L("lg_eco_par_an").format(est=_est))
        else:
            _eco_val, _eco_size, _eco_sub = (
                f'<span style="white-space:nowrap;">{esa_mad}'
                f'&nbsp;&#8211;&nbsp;{eaa_mad}</span>', "13pt",
                _L("lg_selon_option").format(est=_est))
        # QA-FIGURES — l'ancre suit EXACTEMENT les montants imprimés.
        if SCENARIO != 'Avec batterie':
            _eco_val += _ancre_figure("economie_annuelle", esa_mad, "sans")
        if SCENARIO != 'Sans batterie':
            _eco_val += _ancre_figure("economie_annuelle", eaa_mad, "avec")

    # ── M2 — VIGNETTES CONDITIONNELLES (audit adversarial du 19/08/2026) ──────
    # La rangée imprimait « {KWC} kWc », « {NB_PAN} panneaux × {WP} W »,
    # « {pk} kWh » et un montant d'économies comme des FAITS, y compris quand
    # le kWc venait d'une division du prix total (M2) et le watt d'un défaut
    # catalogue (M3). Chaque carte n'est désormais rendue que si sa donnée a
    # un ancrage réel ; une rangée entièrement vide disparaît. Sur un devis
    # normal (puissance lue sur les lignes), le HTML est celui d'hier.
    _kpi_cards = []
    if not PUISSANCE_INCONNUE and KWC > 0:
        # M3 — « × W » seulement si la puissance unitaire a été LUE quelque
        # part (désignation ou fiche produit) ; sinon « N panneaux » tout court.
        if NB_PAN > 0:
            _pan_line = (_L("lg_n_panneaux_w").format(n=NB_PAN, w=WP) if WP > 0
                         else _L("lg_n_panneaux").format(n=NB_PAN))
        else:
            _pan_line = ""
        # F1/L-2OPT (26/08/2026) — sur un document qui rend LES DEUX options
        # avec des champs PV de tailles différentes, un kWc unique décrit
        # l'option AVEC pendant que la page 2 affiche « sans · avec ». La
        # vignette porte donc les deux valeurs, même format sobre. Document
        # mono-option : le builder a déjà recalé le scalaire sur la variante
        # rendue. Devis non divergent ⇒ HTML byte-identique.
        # La carte ne GRANDIT pas : deux valeurs tiennent en réduisant le corps
        # du nombre (19 → 14 pt), et la ligne de légende reste sur UNE ligne.
        # QJR145 (a) — virgule française (le formateur ``kwc_fr`` existait sans
        # aucun site d'appel : le document sortait « 10.65 kWc »).
        _kpi_kwc = f'{kwc_fr(KWC)}&nbsp;kWc'
        _kpi_kwc_pt = '19pt'
        if (PANNEAUX_DIVERGENTS and _both and KWC_SANS > 0 and KWC_AVEC > 0
                and NB_PAN_SANS > 0 and NB_PAN_AVEC > 0):
            _kpi_kwc = (f'{kwc_fr(KWC_SANS)}&#160;&#183;&#160;'
                        f'{kwc_fr(KWC_AVEC)}&nbsp;kWc')
            _kpi_kwc_pt = '14pt'
            _pan_line = _L("lg_n_panneaux_sa").format(s=NB_PAN_SANS, a=NB_PAN_AVEC)
        if _kpi_kwc_pt == '14pt':
            _fig_kwc = (_ancre_figure("puissance_kwc", kwc_fr(KWC_SANS), "sans")
                        + _ancre_figure("puissance_kwc", kwc_fr(KWC_AVEC),
                                        "avec"))
        else:
            _fig_kwc = _ancre_figure("puissance_kwc", kwc_fr(KWC))
        _kpi_cards.append(
            f'<div style="flex:1;min-width:0;margin-right:9px;border:1px solid {CG2};border-left:4px solid {CA};border-radius:6px;padding:14px 12px;background:white;">'
            f'<div style="font-size:4.5pt;letter-spacing:1.5px;color:{CG4};font-weight:400;text-transform:uppercase;margin-bottom:4px;">{_L("lg_kpi_puissance")}</div>'
            f'<div class="serif" style="font-size:{_kpi_kwc_pt};color:{CN};line-height:1.05;">{_kpi_kwc}</div>'
            + _fig_kwc
            + (f'<div style="font-size:6.5pt;color:{CG4};margin-top:3px;">{_pan_line}</div>'
               if _pan_line else '')
            + '</div>')
    if not PUISSANCE_INCONNUE and PROD_KWH > 0:
        # PDFPROD (27/08/2026) — MIROIR EXACT DE LA VIGNETTE « PUISSANCE » : la
        # production DÉRIVE du kWc, elle diverge donc avec lui. Sur un document
        # qui rend LES DEUX options, cette carte annonçait la production de la
        # seule option AVEC (repli documenté du scalaire) juste à côté d'une
        # puissance écrite « sans · avec ». Deux gardes : les valeurs doivent
        # réellement DIFFÉRER (une production saisie dans l'étude vaut pour les
        # deux options) et le corps descend à 13 pt — une production s'écrit
        # sur 5 à 6 chiffres, la carte ne doit ni grandir ni passer à la ligne.
        # Devis non divergent (tout l'existant) ⇒ HTML byte-identique.
        _kpi_prod = f'{pk}&nbsp;kWh'
        _kpi_prod_pt = '19pt'
        _fig_prod = _ancre_figure("production_annuelle_kwh", pk)
        _prod_sub = _L("lg_energie_propre_an")
        if (PANNEAUX_DIVERGENTS and _both and PROD_KWH_SANS > 0
                and PROD_KWH_AVEC > 0 and PROD_KWH_SANS != PROD_KWH_AVEC):
            _pk_s = f"{PROD_KWH_SANS:,}".replace(",", _s)
            _pk_a = f"{PROD_KWH_AVEC:,}".replace(",", _s)
            _kpi_prod = f'{_pk_s}&#160;&#183;&#160;{_pk_a}&nbsp;kWh'
            _kpi_prod_pt = '13pt'
            _prod_sub = _L("lg_energie_propre_an_sa")
            _fig_prod = (
                _ancre_figure("production_annuelle_kwh", _pk_s, "sans")
                + _ancre_figure("production_annuelle_kwh", _pk_a, "avec"))
        _kpi_cards.append(
            f'<div style="flex:1;min-width:0;margin-right:9px;border:1px solid {CG2};border-left:4px solid {CA};border-radius:6px;padding:14px 12px;background:white;">'
            f'<div style="font-size:4.5pt;letter-spacing:1.5px;color:{CG4};font-weight:400;text-transform:uppercase;margin-bottom:4px;">{_L("lg_kpi_production")}</div>'
            f'<div class="serif" style="font-size:{_kpi_prod_pt};color:{CN};line-height:1.05;">{_kpi_prod}</div>'
            + _fig_prod +
            f'<div style="font-size:6.5pt;color:{CG4};margin-top:3px;">{_prod_sub}</div>'
            '</div>')
    if not PUISSANCE_INCONNUE:
        _kpi_cards.append(
            f'<div style="flex:1;min-width:0;overflow-wrap:anywhere;border:2px solid {CA};border-left:5px solid {CA};border-radius:6px;padding:14px 12px;background:#FFFBF2;box-shadow:0 2px 10px rgba(245,166,35,0.18);">'
            f'<div style="font-size:4.5pt;letter-spacing:1.5px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">{_L("op_economies_estimees_an")}</div>'
            f'<div class="serif" style="font-size:{_eco_size};color:{CN};line-height:1.1;">{_eco_val}</div>'
            f'<div style="font-size:6.5pt;color:{CA};font-weight:600;margin-top:3px;">{_eco_sub}</div>'
            '</div>')
    _kpi_cards_html = "\n".join(_kpi_cards)

    # ── Q6 (décision fondateur du 20/08/2026) — LA DONNÉE LOCALE, PAS LE SLOGAN
    # « 3 000 h/an d'ensoleillement » était un chiffre national arrondi, sans
    # rapport avec ce client ni ce devis. On imprime le productible PVGIS de SA
    # ville, celui-là même qui sert à tous les calculs du document. Ville hors
    # table PVGIS ou productible forcé par un réglage société : la pastille
    # DISPARAÎT (le builder rend alors None). « Énergie 100 % propre » perd son
    # chiffre : le qualitatif suffit, le « 100 % » ne se démontre pas.
    _h = HYPOTHESES if isinstance(HYPOTHESES, dict) else {}
    _prod_net = _h.get("productible_net_kwh_kwc")
    _prod_ville = (_h.get("productible_ville") or "").strip()
    # QJR127 — la ville NOMMÉE est celle de la table PVGIS. Quand ce n'est pas
    # la ville du client (Settat → Casablanca), la pastille le DIT au lieu de
    # présenter une valeur de Casablanca comme « donnée PVGIS à Settat ».
    _ville_est_ref = bool(_h.get("productible_ville_est_reference"))
    _prod_suffixe = (_L("lg_donnee_pvgis") if _ville_est_ref
                     else _L("lg_donnee_pvgis_ref"))
    # La pastille courte garde son ``nowrap`` d'origine (rendu inchangé) ; la
    # forme longue s'autorise un retour à la ligne plutôt que de déborder.
    _prod_wrap = "white-space:nowrap;" if _ville_est_ref else ""
    _pill_productible = (
        '<span style="background:rgba(255,255,255,0.08);border:1px solid '
        'rgba(255,255,255,0.35);border-radius:11px;padding:2px 7px;'
        f'font-size:6.5pt;color:white;{_prod_wrap}">'
        f'{SVG_SUN}'
        f'{_L("lg_pill_productible").format(n=fnum(_prod_net), ville=_esc(_prod_ville.title()), suffixe=_prod_suffixe)}'
        f'</span>'
    ) if (_prod_net and _prod_ville) else ""
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
        <div style="font-size:7px;color:rgba(255,255,255,0.38);line-height:1.7;">{_L("lg_hero_l1")}</div>
        <div style="font-size:7px;color:rgba(255,255,255,0.38);">{_L("lg_hero_l2")}</div>
      </div>
    </div>

    <!-- R3 — la tagline fait partie du lockup du logo (plus de doublon texte) -->
    <!-- Gold separator — AFTER logo, BEFORE PROPOSITION -->
    <div style="height:1px;background:{CA};opacity:0.80;margin-bottom:4px;"></div>

    <!-- Row 2: Title+client left / Ref+validity right -->
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;">

      <!-- LEFT: PROPOSITION label + serif title -->
      <div style="flex:1;min-width:0;">
        <div style="font-size:6.5pt;letter-spacing:2.5px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:6px;">{_L("lg_proposition_commerciale")}</div>
        <div class="serif" style="font-size:44pt;font-weight:400;color:white;line-height:1.0;letter-spacing:-0.5px;margin-bottom:8px;">{_L("lg_titre_hero")}</div>
      </div>

      <!-- RIGHT: Ref label + N°412 + date + Validité badge -->
      <div style="text-align:right;flex-shrink:0;">
        <div style="font-size:7pt;color:{CG4};margin-bottom:1px;">{_L("lg_reference_devis")}</div>
        <div class="serif" style="font-size:17.5pt;font-weight:400;color:{CA};line-height:0.90;letter-spacing:-1px;">N&#176;&nbsp;{REF}</div>
        <div style="font-size:8.5pt;color:rgba(255,255,255,0.82);margin-top:5px;">{DATE_STR}</div>
        {_marques_correction_html("font-size:7pt;color:rgba(255,255,255,0.82);margin-top:2px;")}
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
    <div style="margin-top:4px;display:inline-block;background:{CN};border-radius:3px;padding:2px 7px;font-size:7.5px;color:white;">{SVG_FACTORY if 'ndustr' in INST_TYPE else SVG_HOUSE}{i18n_labels.nom_option(INST_TYPE, LANGUE_SORTIE)}</div>
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
{_kpi_cards_html}
    </div>
  </div>

  <!-- SECTION TITLE -->
  <div style="padding:5px 24px 7px;flex-shrink:0;background:#FFFFFF !important;">
    <div style="display:block;background:#FFFFFF !important;">
      <div style="font-size:7pt;letter-spacing:3px;color:{CG4};font-weight:500;text-transform:uppercase;">{_L("lg_vos_options")}</div>
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
      <div style="font-size:6.5pt;letter-spacing:3px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">{_L("res_option_n").format(n=1)}</div>
      <div style="font-size:13pt;font-weight:500;color:{CN};margin-bottom:2px;">{i18n_labels.nom_option("Sans batterie", LANGUE_SORTIE)}</div>
      <div style="font-size:7pt;color:{CGR};font-weight:600;margin-bottom:7px;">{_L("lg_autoconso_directe")}</div>
      {_ts_price}
      <div style="font-size:7pt;color:{CG4};margin-bottom:5px;">{_L("lg_prix_total_ttc")}{_pkwc_s}</div>
      {_roi_pill_s}
      <div style="height:1px;background:{CG2};margin-bottom:6px;"></div>
      <ul style="list-style:none;padding:0;font-size:7pt;line-height:1.8;color:{CG7};margin-bottom:6px;">
        {_sb_lis}
      </ul>
      <div style="height:1px;background:{CG2};margin-top:auto;margin-bottom:6px;"></div>
      {_eco_box_s}
    </div>

    <!-- OPTION 2 -->
    <div style="flex:1;min-width:0;overflow:hidden;border:1.5px solid #E8A020;border-radius:6px;padding:28px 12px 12px;display:flex;flex-direction:column;background:#FFF3E0;position:relative;{_s2}">
      {_r2}
      <div style="font-size:6.5pt;letter-spacing:3px;color:{CA};font-weight:700;text-transform:uppercase;margin-bottom:4px;">{_L("res_option_n").format(n=2)}</div>
      <div style="font-size:13pt;font-weight:500;color:{CN};margin-bottom:2px;">{i18n_labels.nom_option(LIBELLE_AVEC, LANGUE_SORTIE)}</div>
      <div style="font-size:7pt;color:{CGR};font-weight:600;margin-bottom:7px;">{_sous_titre_avec()}</div>
      {_ta_price}
      <div style="font-size:7pt;color:{CG4};margin-bottom:5px;">{_L("lg_prix_total_ttc")}{_pkwc_a}</div>
      {_roi_pill_a}
      <div style="height:1px;background:{CG2};margin-bottom:6px;"></div>
      <ul style="list-style:none;padding:0;font-size:7pt;line-height:1.8;color:{CG7};margin-bottom:6px;">
        {_ab_lis}
      </ul>
      <div style="height:1px;background:{CG2};margin-top:auto;margin-bottom:6px;"></div>
      {_eco_box_a}
    </div>

  </div>

  </div><!-- end white content area -->

  <!-- BOTTOM DARK STRIP — solid edge-to-edge dark navy, compact height -->
  <div style="background:{CN};flex-shrink:0;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:8px 24px;gap:16px;">
    <div style="display:flex;gap:5px;flex-shrink:0;">
      {_pill_productible}
      <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.35);border-radius:11px;padding:2px 7px;font-size:6.5pt;color:white;white-space:nowrap;">{SVG_GLOBE}{_L("lg_energie_propre")}</span>
    </div>
    <div style="width:1px;height:16px;background:rgba(255,255,255,0.2);flex-shrink:0;"></div>
    <div style="font-size:6.5pt;color:rgba(255,255,255,0.70);white-space:nowrap;flex-shrink:0;">
      {svg_num(1)} {_L("lg_etape_devis")} {SVG_ARROW} {svg_num(2)} {_L("lg_etape_visite")} {SVG_ARROW} {svg_num(3)} {_L("res_installation")} {SVG_ARROW} {svg_num(4)} {_L("res_mise_en_service")}
    </div>
  </div>

  {footer_p1()}
</div>
"""

# ── PAGE 2 — equipment tables + charts ───────────────────────────────────────
def page2(sans_items, img_roi, img_mon):
    sr = equip_rows(sans_items, TOTAUX_SANS, hi_bat=False,
                    ancres=None if SCENARIO == 'Avec batterie' else "sans")
    ar = equip_rows(AVEC_ITEMS, TOTAUX_AVEC, hi_bat=True,
                    ancres=None if SCENARIO == 'Sans batterie' else "avec")

    # Scenario visibility
    _p2_s1 = 'display:none;' if SCENARIO == 'Avec batterie' else ''
    _p2_s2 = 'display:none;' if SCENARIO == 'Sans batterie' else ''

    # ── Dynamic table row scaling: many rows would squeeze the charts off the page ──
    if SCENARIO == 'Avec batterie':
        max_rows = len(AVEC_ITEMS)
    elif SCENARIO == 'Sans batterie':
        max_rows = len(sans_items)
    else:
        max_rows = max(len(sans_items), len(AVEC_ITEMS))
    # QJR619 — lignes de structure et bloc d'options entrent dans la mise à l'échelle.
    max_rows += len(LIGNES_STRUCTURE or [])
    if OPTIONS_PROPOSEES:
        max_rows += 1 + len(OPTIONS_PROPOSEES)
    # RPDF21 — remise / arrondi / Total HT : ½ rangée chacun au-delà des 4 totaux (devis 1344).
    _tots = [t for t, cache in ((TOTAUX_SANS, _p2_s1), (TOTAUX_AVEC, _p2_s2)) if not cache]
    max_rows += 0.5 * max([_rangs_totaux(t) - 4 for t in _tots] + [0])
    scale = 1.0 if max_rows <= 11 else max(0.62, 11.0 / max_rows)
    _gk = 1.0 if scale >= 1.0 else max(scale, 0.8)  # RPDF21 — graphes (hors flex) à l'échelle
    _gdim = f"width:{int(680 * _gk)}px;height:{int(170 * _gk)}px;"
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

    # M5 — la carte « Gain cumulé sur 25 ans » disparaît avec sa courbe : un
    # cadre vide sous un titre qui promet un gain est pire qu'une absence.
    _roi_card = (
        f'<div style="flex:1;min-height:0;background:{CG1};border-radius:7px;'
        f'padding:8px 11px;border:1px solid {CG2};display:flex;'
        f'flex-direction:column;">'
        f'<div style="font-size:7pt;font-weight:700;color:{CN};'
        f'text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;'
        f'flex-shrink:0;">'
        f'<svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:middle;margin-right:3px;"><polyline points="1,10 4,6 7,8 11,2" fill="none" stroke="{CN}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="8,2 11,2 11,5" fill="none" stroke="{CN}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        f' {_L("lg_gain_cumule_titre")}'
        f'</div>'
        f'<img src="{img_roi}" style="{_gdim}display:block;">'
        f'</div>'
    ) if img_roi else ""

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
        f'</svg> {_L("lg_eco_mensuelles")}</div>'
        f'<div style="font-size:6pt;color:{CG4};font-style:italic;margin-bottom:4px;flex-shrink:0;">'
        f'{_L("lg_facture_vs_eco") if FACTURES_M else _L("lg_eco_solaires_mois")}</div>'
        f'<img src="{img_mon}" style="{_gdim}display:block;">'
        f'</div>'
    ) if img_mon else ""

    # QJRREM - LA phrase des deux tableaux, jointe à la note de TVA (aucune hauteur en plus).
    _nr = _note_remise_par_ligne()
    _note_remise_p2 = f" &#183; {_nr}" if _nr else ""

    # QJR619 — « Options proposées » : le SEUL ``total_ttc`` du builder (QJR616) ; sans option ⇒ ''.
    _options_p2 = ""
    if OPTIONS_PROPOSEES:
        _orows = ""
        for _o in OPTIONS_PROPOSEES:
            _oq = float(_o.get("quantite", 0) or 0)
            _oq_s = str(int(_oq)) if _oq == int(_oq) else fnum(_oq)
            _orows += (
                f'<tr><td class="tl">{_o.get("designation", "")}</td>'
                f'<td class="tc">{_oq_s}</td>'
                f'<td class="tr">{_fmt2(float(_o.get("total_ttc", 0) or 0))}'
                f'&#160;{_L("cgv_mad_ttc")}</td></tr>')
        _options_p2 = (
            f'<div style="margin-top:5px;font-size:6.5pt;font-weight:800;'
            f'color:{CA};text-transform:uppercase;letter-spacing:.6px;">'
            f'{_L("lg_options_proposees")}</div>'
            f'<table class="eq" style="border:1px dashed {CA};">{_orows}</table>')

    return f"""
<div class="page">
  {tbl_css}
  <div style="background:{CN};padding:9px 24px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">{_L("lg_p2_titre")}</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">{_L("lg_devis_n_nbsp").format(ref=REF)} \u2014 {CLIENT_NAME} \u2014 {DATE_STR}</div>
    </div>
    {logo_html("entete")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <div style="padding:9px 24px 4px;flex-shrink:0;">
    <div style="display:flex;gap:10px;">

      <div style="flex:1;min-width:0;{_p2_s1}">
        <div style="background:{CN};color:white;font-size:7pt;font-weight:700;text-transform:uppercase;letter-spacing:.8px;padding:5px 9px;border-radius:5px 5px 0 0;">{_L("res_option_n_nom").format(n=1, option=i18n_labels.nom_option("Sans batterie", LANGUE_SORTIE))}</div>
        <table class="eq">
          <thead><tr>
            <th class="ti"></th><th>{_L("lg_th_designation")}</th>
            <th class="tc">{_L("lg_th_garantie")}</th><th class="tc">{_L("lg_th_qte")}</th><th class="tr">{_L("pu_ht")}</th><th class="tc">{_L("tva")}</th><th class="tr">{_L("total_ht")}</th>
          </tr></thead>
          <tbody>{sr}</tbody>
        </table>
      </div>

      <div style="flex:1;min-width:0;{_p2_s2}">
        <div style="background:{CA};color:{CN};font-size:7pt;font-weight:700;text-transform:uppercase;letter-spacing:.8px;padding:5px 9px;border-radius:5px 5px 0 0;">{_L("res_option_n_nom").format(n=2, option=i18n_labels.nom_option(LIBELLE_AVEC, LANGUE_SORTIE))}</div>
        <table class="eq">
          <thead><tr>
            <th class="ti"></th><th>{_L("lg_th_designation")}</th>
            <th class="tc">{_L("lg_th_garantie")}</th><th class="tc">{_L("lg_th_qte")}</th><th class="tr">{_L("pu_ht")}</th><th class="tc">{_L("tva")}</th><th class="tr">{_L("total_ht")}</th>
          </tr></thead>
          <tbody>{ar}</tbody>
        </table>
      </div>

    </div>{_options_p2}
    <div style="margin-top:4px;font-size:6pt;color:{CG4};font-style:italic;">
      * {TVA_NOTE}{_note_remise_p2}
    </div>
  </div>

  <!-- Charts section -->
  <div style="padding:4px 24px 6px;flex:1;min-height:0;display:flex;flex-direction:column;gap:10px;">
    {_roi_card}
    {_monthly_card}
  </div>

  {footer(2)}
</div>
"""

# ── PAGE 3 — trust, guarantees, conditions, prochaines étapes, signature ─────
def page3():
    # ── M6 (audit adversarial du 19/08/2026) — LES BADGES DISENT LES VRAIES
    # GARANTIES. Ils affichaient « 10 / 12 / 30 ANS » et « Performance panneau
    # (87,4 %) » en dur : ces chiffres sortaient sur un devis Longi comme sur un
    # Canadian Solar, et sur des produits dont aucune garantie n'est saisie. Ils
    # sont désormais dérivés des fiches produit des lignes rendues ; une famille
    # sans garantie saisie n'a PAS de badge, et la bande entière disparaît quand
    # le devis n'en porte aucune. Le « 87,4 % » — spec Canadian Solar TOPHiKu7 —
    # ne s'écrit plus ici : le libellé porte la durée, pas la marque d'un autre.
    _gars = _garanties_du_devis()
    if _gars:
        _cards = "".join(
            f'<div style="flex:1;border:2px solid '
            f'{CA if lbl == _L("lg_gar_performance") else CN};border-top:4px solid '
            f'{CN if lbl == _L("lg_gar_performance") else CA};border-radius:8px;'
            f'padding:6px 5px;text-align:center;'
            f'background:{CAL if lbl == _L("lg_gar_performance") else "white"};">'
            f'<div class="serif" style="font-size:38px;'
            f'color:{CA if lbl == _L("lg_gar_performance") else CN};'
            f'line-height:1.0;letter-spacing:-1px;">{n}</div>'
            f'<div style="font-size:12px;font-weight:700;'
            f'color:{CN if lbl == _L("lg_gar_performance") else CA};'
            f'letter-spacing:1px;text-transform:uppercase;">{_L("lg_ans_maj")}</div>'
            f'<div style="font-size:8pt;color:{CG4};margin-top:2px;">{lbl}</div>'
            f'</div>'
            for n, lbl in _gars[:4])
        _badges_garanties_html = (
            f'<div style="padding:0 24px 4px;margin-bottom:5px;">'
            f'<div style="display:flex;gap:5px;">{_cards}</div></div>')
    else:
        _badges_garanties_html = ""

    # M6 — le titre et le détail « Nos garanties » suivent les MÊMES fiches
    # produit que les badges. Surcharge société explicite (D2/N67) souveraine ;
    # à défaut, texte composé ; aucune garantie saisie ⇒ formulation sobre,
    # sans durée inventée.
    _gar_titre = _doc_text("garantie_titre") or (
        _L("lg_garanties_jusqu").format(n=max(n for n, _ in _gars))
        if _gars else _L("res_nos_garanties"))
    _gar_detail = _doc_text("garantie_detail") or (
        ", ".join(_L("lg_gar_ligne").format(lbl=lbl.lower(), n=n)
                  for n, lbl in _gars).capitalize() + "."
        if _gars else _L("lg_garanties_fabricant"))

    # ── QJR121 — LA CARTE « ÉQUIPEMENTS » NOMME LES MARQUES DU DEVIS ────────
    # Elle affirmait « Panneaux Canadian Solar, onduleurs Huawei & Deye —
    # certifiés IEC » sur TOUT devis : contredit par le tableau de la page 2 dès
    # que les lignes portent d'autres marques, et invérifiable pour la
    # certification. La phrase se compose des marques RÉELLEMENT vendues (comme
    # les garanties se composent des fiches produit) et s'OMET quand aucune
    # marque n'est lisible.
    _marques = _marques_du_devis()
    _equip_card = ""
    if _marques:
        _bouts = []
        if _marques.get("panneaux"):
            _bouts.append(_L("lg_eq_panneaux").format(m=" & ".join(_marques["panneaux"])))
        if _marques.get("onduleurs"):
            _bouts.append(_L("lg_eq_onduleurs").format(m=" & ".join(_marques["onduleurs"])))
        if _marques.get("batteries"):
            _bouts.append(_L("lg_eq_batterie").format(m=" & ".join(_marques["batteries"])))
        _equip_txt = _esc(", ".join(_bouts))
        _equip_card = f"""
      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:8px 12px;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:34px;height:34px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="{CA}" stroke="{CA}" stroke-width="1">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
        </div>
        <div>
          <div style="font-size:10.5pt;font-weight:700;color:{CN};margin-bottom:3px;">{_L("lg_eq_titre")}</div>
          <div style="font-size:13px;color:{CG4};line-height:1.4;">{_equip_txt}{_L("lg_eq_garantie")}</div>
        </div>
      </div>
"""

    # QJR121 — le monitoring n'est promis que si une LIGNE du devis le porte ; sinon pas de carte.
    _monitoring_card = ""
    if _monitoring_vendu():
        _monitoring_card = f"""
      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:8px 12px;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:34px;height:34px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2">
            <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
            <line x1="12" y1="18" x2="12.01" y2="18" stroke-width="3"/>
          </svg>
        </div>
        <div>
          <div style="font-size:10.5pt;font-weight:700;color:{CN};margin-bottom:3px;">{_L("res_suivi_temps_reel")}</div>
          <div style="font-size:13px;color:{CG4};line-height:1.4;">{_L("lg_monitoring_texte")}</div>
        </div>
      </div>
"""

    # Q5 — délais des « prochaines étapes » (réglages société, « (indicatif) ») ; réglage vidé
    # ⇒ sous-titre VIDE. Hors de la boîte « Conditions » (lus comme des engagements).
    _etape_visite = (_L("lg_delai_sous").format(delai=DELAI_VISITE)
                     if DELAI_VISITE else "")
    _etape_install = (_L("res_delai_indicatif").format(delai=DELAI_INSTALLATION)
                      if DELAI_INSTALLATION else "")

    # "Option choisie" tick-boxes — only shown when both options are presented
    _opt = (
        f'<div style="margin-bottom:6px;">'
        f'<div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:5px;">{_L("lg_option_choisie")}</div>'
        f'<div style="display:flex;gap:10px;">'
        # Sans batterie box
        f'<div style="flex:1;border:1.5px solid {CG2};border-radius:7px;padding:7px 11px;'
        f'background:white;display:flex;align-items:center;gap:9px;">'
        f'<div style="width:17px;height:17px;border:2px solid {CG7};border-radius:3px;flex-shrink:0;"></div>'
        f'<div>'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};">{i18n_labels.nom_option("Sans batterie", LANGUE_SORTIE)}</div>'
        f'<div style="font-size:8pt;color:{CG4};margin-top:2px;">{_L("lg_option1_reseau")}</div>'
        f'</div>'
        f'</div>'
        # Avec batterie box
        f'<div style="flex:1;border:1.5px solid {CA};border-radius:7px;padding:7px 11px;'
        f'background:{CAL};display:flex;align-items:center;gap:9px;">'
        f'<div style="width:17px;height:17px;border:2px solid {CA};border-radius:3px;flex-shrink:0;"></div>'
        f'<div>'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};">{i18n_labels.nom_option(LIBELLE_AVEC, LANGUE_SORTIE)}</div>'
        f'<div style="font-size:8pt;color:{CG4};margin-top:2px;">{_L("lg_option2_compo").format(compo=_composition_avec())}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    ) if SCENARIO == "Les deux (Sans + Avec)" else (
        # Document à option unique : UNE confirmation, pas de cases à choix
        f'<div style="margin-bottom:6px;">'
        f'<div style="font-size:6.5pt;font-weight:700;color:{CG4};text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:5px;">{_L("lg_confirmation_commande")}</div>'
        f'<div style="border:1.5px solid {CA};border-radius:7px;padding:7px 11px;'
        f'background:{CAL};display:flex;align-items:center;gap:9px;">'
        f'<div style="width:17px;height:17px;border:2px solid {CA};border-radius:3px;flex-shrink:0;"></div>'
        f'<div>'
        f'<div style="font-size:9pt;font-weight:700;color:{CN};">'
        f'{_L("lg_systeme_pv").format(kwc=_kwc_mention())}'
        f'{i18n_labels.nom_option("Sans batterie" if SCENARIO == "Sans batterie" else LIBELLE_AVEC, LANGUE_SORTIE)}</div>'
        f'<div style="font-size:8pt;color:{CG4};margin-top:2px;">'
        f'{_L("lg_je_confirme")}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    # ── Payment section (Devis Final only) ──
    _payment_html = ""
    if DEVIS_FINAL:
        # Pick the relevant branch based on scenario / recommendation
        if SCENARIO == "Sans batterie":
            _branche = "sans"
        elif SCENARIO == "Avec batterie":
            _branche = "avec"
        elif RECOMMENDED == "Sans batterie":
            _branche = "sans"
        else:
            _branche = "avec"

        # QJR623 / ERR120 — le moteur ne fait plus qu'IMPRIMER : les montants
        # (au centime, ×N villas compris, reliquat sur la dernière tranche,
        # acompte personnalisé borné) sont calculés par le builder
        # (``builder.repartition_paiement``). Plus d'arrondi au millier ni de
        # reliquat tronqué ici. Rendu seul : aucun statut touché (règle #4).
        _rep = (MONTANTS_TRANCHES or {}).get(_branche) or {}
        _acompte = _rep.get('acompte', 0)
        _materiel = _rep.get('materiel', 0)
        _solde = _rep.get('solde', 0)
        _pct_a, _pct_m, _pct_s = (
            _rep.get('pct_a', PAY_A), _rep.get('pct_m', PAY_M),
            _rep.get('pct_s', PAY_S))

        def _pay_box(pct, montant, label):
            # QJR145 (b) — le formateur suffixe DÉJÀ « MAD ».
            # QJR623 — montant au CENTIME (les cases somment au Total TTC).
            return (
                f'<div style="flex:1;text-align:center;padding:6px 5px;background:white;border-radius:8px;border:1px solid {CG2};">'
                f'<div class="serif" style="font-size:22px;font-weight:800;color:{CA};line-height:1.0;">{pct}%</div>'
                f'<div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">{_fmt2_mad(montant)}</div>'
                f'<div style="font-size:9px;color:{CG4};margin-top:2px;">{label}</div>'
                f'</div>')

        # QX7b — n’imprime JAMAIS une case Matériel morte à 0 % : quand
        # l’acompte custom absorbe la tranche matériel (materiel <= 0), on
        # bascule sur un échéancier à DEUX cases (Acompte + Solde) qui somment
        # à 100 % — plus de pourcentages faux. Chemin standard (materiel > 0) :
        # trois cases, rendu inchangé. Le solde reprend le reliquat exact.
        _ac_l = _L("lg_pay_acompte")
        _mt_l = _L("lg_pay_materiel")
        _sd_l = _L("lg_pay_solde")
        if not _rep:
            # Charge utile sans montants du builder : aucune case inventée.
            _boxes = ""
        elif _materiel > 0:
            _boxes = (_pay_box(_pct_a, _acompte, _ac_l)
                      + _pay_box(_pct_m, _materiel, _mt_l)
                      + _pay_box(_pct_s, _solde, _sd_l))
        else:
            _solde2, _pct_s2 = _rep['solde2'], _rep['pct_s2']  # reliquat exact
            _boxes = (_pay_box(_pct_a, _acompte, _ac_l)
                      + _pay_box(_pct_s2, _solde2, _L("lg_pay_solde_livraison")))

        _payment_html = (
            f'<div style="margin-bottom:4px;">'
            f'<div style="border-left:3px solid {CN};padding-left:8px;margin-bottom:4px;">'
            f'<div style="font-size:8pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:1px;">{_L("lg_modalites_paiement")}</div>'
            f'</div>'
            f'<div style="display:flex;gap:6px;margin-bottom:3px;">'
            f'{_boxes}'
            f'</div>'
            # Note
            f'<div style="font-size:7pt;color:{CG4};font-style:italic;margin-bottom:3px;">'
            f'{_L("lg_pay_note")}'
            f'</div>'
            # RIB bar — APDF2 : omise quand la société n'a pas de RIB.
            # QJR146 (e) — SUBSTITUTION LITTÉRALE, JAMAIS ``.format()``.
            # ``ENT_RIB_LINE`` est RECONSTRUITE à l'ingestion avec la raison
            # sociale, la banque et le RIB du tenant (échappés HTML, ce qui ne
            # touche PAS les accolades) : une raison sociale portant « { » ou
            # « } » faisait lever ``.format()`` (KeyError/ValueError) ICI, hors
            # de tout try — le PDF entier échouait sur un caractère du nom de
            # la société. ``str.replace`` ne lit aucun champ de format.
            + (f'<div style="background:{CG1};border-radius:5px;padding:4px 10px;margin-bottom:5px;">'
               f'<div style="font-size:7pt;color:{CG4};">{_L("lg_virement")}'
               f'{ENT_RIB_LINE.replace("{cg7}", CG7)}</div>'
               f'</div>' if ENT_RIB_LINE else '')
            + f'</div>'
        )

    return f"""
<div class="page" style="position:relative;overflow:hidden;">
  <div style="background:{CN};padding:9px 24px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">{_L("lg_confiance_bpa")}</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">{_L("lg_devis_n_nbsp").format(ref=REF)} \u2014 {CLIENT_NAME}</div>
    </div>
    {logo_html("entete")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <!-- RPDF22 — colonne flex : le contenu prend la place LAISSÉE par le BPA (rogné, jamais dessous) -->
  <div style="overflow:hidden;max-height:820px;flex:1;min-height:0;">

  <!-- QJR121 — POURQUOI NOUS : titre, marques et supervision dérivés du devis -->
  <div style="padding:6px 24px 4px;margin-bottom:5px;">
    <div class="serif" style="font-size:26px;color:{CN};margin-bottom:2px;">{_L("lg_pourquoi_choisir").format(marque=ENT_NOM_MARQUE)}</div>
    <div style="font-size:9pt;color:{CG4};font-style:italic;margin-bottom:5px;">{_L("lg_experts_engages")}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:8px 12px;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:34px;height:34px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2" stroke-linecap="round">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
          </svg>
        </div>
        <div>
          <div style="font-size:10.5pt;font-weight:700;color:{CN};margin-bottom:3px;">{_L("lg_ingenieurs")}</div>
          <div style="font-size:13px;color:{CG4};line-height:1.4;">{_L("lg_ingenieurs_texte")}</div>
        </div>
      </div>

      {_equip_card}

      <div style="background:white;border:1px solid {CG2};border-radius:10px;padding:8px 12px;display:flex;gap:10px;align-items:flex-start;">
        <div style="width:34px;height:34px;border-radius:50%;background:{CAL};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{CA}" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <div>
          <div style="font-size:10.5pt;font-weight:700;color:{CN};margin-bottom:3px;">{_gar_titre}</div>
          <div style="font-size:13px;color:{CG4};line-height:1.4;">{_gar_detail}</div>
        </div>
      </div>

      {_monitoring_card}

    </div>
  </div>

  <!-- GUARANTEE BADGES — M6 : dérivés des FICHES PRODUIT du devis -->
  {_badges_garanties_html}

  <!-- QF3 — COMMENT NOUS CALCULONS VOS ÉCONOMIES (méthode + exemple) -->
  <div style="padding:0 24px;">{_savings_method_html()}</div>

  <!-- QK4 — NOS HYPOTHÈSES (transparence des hypothèses d'économies) -->
  <div style="padding:0 24px;">{_hypotheses_html()}</div>

  <!-- QK3 — FINANCEMENT (indicatif) -->

  <!-- QJ30 — MULTI-PROPRIÉTÉS (×N identiques / sections par-villa) -->
  <div style="padding:0 24px;">{_multi_proprietes_line_html()}{_multi_villa_html()}</div>

  <!-- QJR627 — NOTE CLIENT (champ « Notes » du devis ; vide → rien) -->
  <div style="padding:0 24px;">{_note_client_html()}{_clauses_cgv_html()}</div>

  <!-- CONDITIONS GENERALES -->
  <div style="padding:0 24px 4px;margin-bottom:5px;">
    <div style="background:{CG1};border-radius:8px;padding:7px 12px;border:1px solid {CG2};border-left:4px solid {CN};">
      <div style="font-size:9pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;">{_doc_text_langue("cgv_titre", "ci_cgv_titre")}</div>
      <ul style="list-style:none;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:2px 16px;">{_cgv_bullets_html()}</ul>
    </div>
  </div>

  <!-- RPDF25 : bandeau « Notre engagement » retiré (coupé par le Bon pour accord, rendu 1344 du 28/10) -->
  <!-- PROCHAINES ÉTAPES -->
  <div style="padding:0 24px;margin-bottom:5px;">
    <div style="background:#F8F6F0;border:1px solid #EAECF0;border-radius:10px;padding:8px 12px;margin:2px 0;">
      <div style="border-left:4px solid #F5A623;padding-left:10px;margin-bottom:5px;">
        <div style="font-size:12px;font-weight:700;letter-spacing:2px;color:{CN};text-transform:uppercase;">{_L("lg_prochaines_etapes")}</div>
      </div>
      <div style="display:flex;gap:6px;">
        <div style="flex:1;text-align:center;padding:7px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:36px;font-weight:800;color:{CA};line-height:1.0;">1</div>
          <div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">{_L("res_signature_devis")}</div>
          <div style="font-size:10px;color:{CG4};margin-top:2px;">{_L("lg_plus_acompte").format(pct=PAY_A)}</div>
        </div>
        <div style="flex:1;text-align:center;padding:7px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:36px;font-weight:800;color:{CA};line-height:1.0;">2</div>
          <div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">{_L("res_visite_technique")}</div>
          <div style="font-size:10px;color:{CG4};margin-top:2px;">{_etape_visite}</div>
        </div>
        <div style="flex:1;text-align:center;padding:7px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:36px;font-weight:800;color:{CA};line-height:1.0;">3</div>
          <div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">{_L("res_installation")}</div>
          <div style="font-size:10px;color:{CG4};margin-top:2px;">{_etape_install}</div>
        </div>
        <div style="flex:1;text-align:center;padding:7px 6px;background:white;border-radius:8px;border:1px solid #EAECF0;">
          <div class="serif" style="font-size:36px;font-weight:800;color:{CA};line-height:1.0;">4</div>
          <div style="font-size:12px;color:{CN};font-weight:700;margin-top:2px;">{_L("res_mise_en_service")}</div>
          <div style="font-size:10px;color:{CG4};margin-top:2px;">{_L("lg_tests_formation")}</div>
        </div>
      </div>
    </div>
  </div>

  </div><!-- end content wrapper -->

  <!-- BON POUR ACCORD — dans le flux, en bas, au-dessus du pied (absolu) -->
  <div style="flex-shrink:0;margin-top:auto;margin-bottom:{'28' if DEVIS_FINAL else '43'}px;padding:0 24px;">
    <div style="border-left:4px solid {CA};padding-left:10px;margin-bottom:{'4' if DEVIS_FINAL else '6'}px;">
      <div style="font-size:10pt;font-weight:700;color:{CN};text-transform:uppercase;letter-spacing:1.5px;">{_doc_text_langue("bpa_titre", "bon_pour_accord")}</div>
    </div>{_acceptance_stamp_html()}
    {_opt}
    {_payment_html}
    <div style="display:flex;gap:18px;margin-bottom:4px;">
      <div style="flex:1;border:1px solid {CG2};border-radius:8px;padding:{'6px 10px' if DEVIS_FINAL else '8px 12px'};min-height:{'50' if DEVIS_FINAL else '65'}px;background:white;">
        <div style="font-size:8pt;font-weight:700;color:{CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:{'4' if DEVIS_FINAL else '6'}px;">{_L("lg_signature_client")}</div>
        <div style="border-bottom:1px solid {CG2};min-height:{'10' if DEVIS_FINAL else '14'}px;margin-bottom:3px;"></div>
        <div style="font-size:{'8' if DEVIS_FINAL else '9'}pt;color:{CG4};margin-top:2px;">{_L("lg_nom")} <strong style="color:{CG7};">{CLIENT_NAME}</strong></div>
        <div style="border-bottom:1px solid {CG2};min-height:{'8' if DEVIS_FINAL else '12'}px;margin-top:3px;margin-bottom:3px;"></div>
        <div style="font-size:{'8' if DEVIS_FINAL else '9'}pt;color:{CG4};">{_L("lg_date_ligne")}</div>
        <div style="font-size:7pt;color:{CG4};margin-top:{'2' if DEVIS_FINAL else '3'}px;font-style:italic;">{_doc_text_langue("bpa_mention", "ci_bpa_mention")}</div>
      </div>
      <div style="flex:1;border:1px solid {CG2};border-radius:8px;padding:{'6px 10px' if DEVIS_FINAL else '8px 12px'};min-height:{'50' if DEVIS_FINAL else '65'}px;background:white;">
        <div style="font-size:8pt;font-weight:700;color:{CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:{'4' if DEVIS_FINAL else '6'}px;">{_L("lg_signature_marque").format(marque=ENT_NOM_MARQUE)}</div>
        <div style="border-bottom:1px solid {CG2};min-height:{'10' if DEVIS_FINAL else '14'}px;margin-bottom:3px;"></div>
        <div style="font-size:{'8' if DEVIS_FINAL else '9'}pt;color:{CG4};margin-top:2px;">{_L("lg_representant")} <span style="display:inline-block;min-width:80px;border-bottom:1px solid {CG2};">&nbsp;</span></div>
        <div style="border-bottom:1px solid {CG2};min-height:{'8' if DEVIS_FINAL else '12'}px;margin-top:3px;margin-bottom:3px;"></div>
        <div style="font-size:{'8' if DEVIS_FINAL else '9'}pt;color:{CG4};">{_L("lg_date_ligne")}</div>
        <div style="font-size:7pt;color:{CG4};margin-top:{'2' if DEVIS_FINAL else '3'}px;font-style:italic;">{_L("lg_cachet_societe")}</div>
      </div>
    </div>

  </div>

  {footer_p3("position:absolute;bottom:0;left:0;right:0;")}
</div>
"""

# ── Assemble HTML ─────────────────────────────────────────────────────────────


#: QJR159 (b) — écart RELATIF toléré entre la puissance simulée et la puissance
#: VENDUE. Même esprit que ``pricing._HORAIRE_TOLERANCE_KWC`` : 2 % absorbe les
#: arrondis kWc/panneaux sans laisser passer un vrai changement de taille (un
#: panneau de plus pèse déjà bien davantage).
# AMOT35 — LA constante vit dans ``bankable`` (règle partagée).
from .bankable import TOLERANCE_KWC_SIMULATION  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
from .agricole.garanties import garantie_ligne_onepage  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
from .ci import installation as ci_installation, onepage as ci_onepage, tableau as ci_tableau  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
from .bankable import TOLERANCE_PRODUCTION_PAGE  # noqa: E402,F401 — fin de module (anti-cycle) (D-ENF22)


#: QJR115 \u2014 \u00e9cart RELATIF tol\u00e9r\u00e9 entre la P50 du bloc bancable et la
#: \u00ab Production annuelle \u00bb imprim\u00e9e sur la M\u00caME page. C'est EXACTEMENT la
#: tol\u00e9rance de la garde pos\u00e9e c\u00f4t\u00e9 moteur par QJR114 (\u00ab deux productions d'un
#: m\u00eame devis ne divergent pas de plus de 1 % \u00bb) : elle absorbe l'arrondi \u00e0
#: l'entier de la carte, jamais les ~10 % que produisait le double derate.


def _batterie_differee():
    """AMOT21 (C-AMOT-019) — l'option 2 est-elle « hybride, batterie plus
    tard » (BAT-DIFF) ? Le serveur le DIT par ``libelle_avec``."""
    return LIBELLE_AVEC != "Avec batterie"


def _sous_titre_avec():
    """AMOT21 — sous-titre de la carte option 2 : aucun stockage promis
    quand la batterie n'est pas vendue."""
    return (_L("lg_sous_titre_hybride")
            if _batterie_differee() else _L("lg_sous_titre_stockage"))


def _composition_avec():
    """AMOT21 — composition affichée de l'option 2 (« Réseau + Stockage »
    seulement quand une batterie est vendue)."""
    return _L("lg_compo_hybride") if _batterie_differee() else _L("lg_compo_stockage")


def page_annexe_technique():
    """PV46 \u2014 annexe technique : sch\u00e9ma unifilaire + nomenclature \u00e9lectrique.

    Rendue depuis ``devis.electrical_design`` (PV41) et le SVG du sch\u00e9ma, tous
    deux fournis par le builder. **AUCUN PRIX** n'y figure : le moteur
    \u00e9lectrique ne manipule que des grandeurs publiques et des quantit\u00e9s, et le
    bordereau d'annexe est une pi\u00e8ce TECHNIQUE (le chiffrage reste la liste
    d'\u00e9quipements de la page 2). Une section sans donn\u00e9e est OMISE \u2014 jamais un
    tableau vide ni un tiret fabriqu\u00e9.
    """
    design = ELECTRICAL_DESIGN or {}

    schema_html = (
        f'<div style="background:white;border:1px solid {CG2};border-radius:7px;'
        f'padding:8px 10px;margin-bottom:10px;">'
        f'<div style="font-size:7pt;font-weight:700;color:{CN};'
        f'text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;">'
        f'{_L("lg_schema")}</div>{SLD_SVG}</div>'
    ) if SLD_SVG else ""

    def _cell(texte, align="left", bold=False):
        return (f'<td style="padding:3px 6px;border-bottom:1px solid {CG2};'
                f'text-align:{align};'
                f'{"font-weight:700;" if bold else ""}">{texte}</td>')

    # QJR163 (a) — LA TRONCATURE EST DÉCLARÉE. La nomenclature était
    # coupée à 22 lignes sans mention ni marqueur : le lecteur croyait
    # tenir la liste complète des composants.
    _bom = [it for it in (design.get("bom") or []) if isinstance(it, dict)]
    _bom_reste = max(0, len(_bom) - BOM_MAX_LIGNES)
    lignes = []
    for item in _bom[:BOM_MAX_LIGNES]:
        if not isinstance(item, dict):
            continue
        quantite = item.get("quantite")
        quantite = "" if quantite in (None, "") else _esc(quantite)
        lignes.append(
            "<tr>"
            + _cell(_esc(item.get("designation") or ""))
            + _cell(quantite, align="right")
            + _cell(f'<span style="color:{CG4};">'
                    f'{_esc(item.get("spec") or "")}</span>')
            + "</tr>")
    if _bom_reste > 0:
        lignes.append(
            f'<tr><td colspan="3" style="padding:3px 6px;font-style:italic;'
            f'font-size:6.5pt;color:{CG4};">'
            f'{_L("lg_bom_reste_n" if _bom_reste > 1 else "lg_bom_reste_1").format(n=_bom_reste)}</td></tr>')
    bom_html = (
        f'<div style="background:{CG1};border:1px solid {CG2};border-radius:7px;'
        f'padding:8px 10px;">'
        f'<div style="font-size:7pt;font-weight:700;color:{CN};'
        f'text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;">'
        f'{_L("lg_nomenclature")}</div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:7pt;">'
        f'<tr><th style="text-align:left;padding:3px 6px;border-bottom:2px solid '
        f'{CN};">{_L("lg_th_designation")}</th>'
        f'<th style="text-align:right;padding:3px 6px;border-bottom:2px solid '
        f'{CN};">{_L("lg_th_qte")}</th>'
        f'<th style="text-align:left;padding:3px 6px;border-bottom:2px solid '
        f'{CN};">{_L("lg_th_spec")}</th></tr>'
        + "".join(lignes) + '</table></div>'
    ) if lignes else ""

    parametres = design.get("parametres") or {}
    _phases = parametres.get("phases")
    reperes = []
    if design.get("chaines"):
        reperes.append(_L("lg_chaines").format(n=len(design["chaines"])))
    if _phases:
        reperes.append(_L("lg_triphase") if int(_phases) == 3 else _L("lg_monophase"))
    if parametres.get("regime"):
        reperes.append(_L("lg_regime").format(r=_esc(parametres["regime"])))
    # Python 3.11 (prod/CI) refuse un antislash dans l'EXPRESSION d'une
    # f-string (3.12+ l'accepte \u2014 vert local trompeur) : s\u00e9parateur hiss\u00e9.
    sep_reperes = " \u2014 "
    reperes_html = (
        f'<div style="font-size:8pt;color:{CG4};margin-bottom:10px;">'
        f'{sep_reperes.join(reperes)}</div>') if reperes else ""

    return f"""
<div class="page">
  <div style="background:{CN};padding:12px 24px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">{_L("lg_annexe_technique")}</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">{_L("lg_devis_n_nbsp").format(ref=REF)} \u2014 {CLIENT_NAME} \u2014 {DATE_STR}</div>
    </div>
    {logo_html("entete")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <div style="padding:14px 24px;flex:1;min-height:0;">
    {reperes_html}
    {schema_html}
    {bom_html}
    <div style="margin-top:10px;font-size:6.5pt;color:{CG4};font-style:italic;">
      {_L("lg_annexe_note")}
    </div>
  </div>

  <div style="background:{CN};padding:6px 24px 5px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>
    <div style="font-size:7pt;color:#888;">{ENT_ETUDE_CONTACT}</div>
    <div style="font-size:7pt;color:#888;">{_L("lg_annexe_pied").format(ref=REF)}</div>
  </div>
</div>
"""


def page_annexe_domicile(pied=None):
    """CAD122 — annexe de rétractation, signature AU DOMICILE (loi 31-08).

    Décision fondateur du 21/09/2026. La visite technique se passe chez le
    client, après le devis, et le bon de commande s'y signe PARFOIS : l'art. 45
    (texte ONSSA) définit alors le démarchage comme la proposition d'achat au
    domicile « même à sa demande », et l'art. 46 n'exclut rien qui couvre le
    solaire. Le document doit donc porter les mentions de l'art. 48 et un
    FORMULAIRE DÉTACHABLE de rétractation.

    Trois règles de construction :

      * cette page n'existe QUE si le document porte le marqueur « signé au
        domicile » (``SIGNE_AU_DOMICILE``). Sans lui, le devis est rendu
        exactement comme avant, au caractère près — une signature à distance
        ou au bureau reste régie par l'art. 32 ;
      * AUCUN chiffre n'est inventé : le délai vient de la loi (art. 49 et 50)
        et est repris tel quel ; les dates restent à remplir à la main, parce
        que c'est la main du client qui les écrit (art. 47 al. 2) ;
      * ce n'est PAS une seconde voie de PDF (règle #4) : c'est une page de
        plus, rendue par le moteur vendu, dans le même document.

    AMOT53 (D-AMOT-2 = a) — le une-page signé au domicile porte cette MÊME
    page en 2ᵉ page déclarée ; ``pied`` (« … · Page 2 / 2 ») la compte. Sans
    ``pied`` (document plein format) : le pied d'hier, octet pour octet.
    """
    # AMOT23 — le CORPS vient de la fonction partagée (annexe_domicile) :
    # le gabarit résidentiel 3 pages imprime la MÊME annexe.
    _corps = _corps_annexe_domicile(
        ref=REF, vendeur=ENT_NOM_MARQUE,
        couleurs={'navy': CN, 'texte': CG7, 'muet': CG4, 'fond': CG1,
                  'filet': CG2}, langue=LANGUE_SORTIE)
    return f"""
<div class="page">
  <div style="background:{CN};padding:12px 24px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">{_L("lg_ret_titre")}</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">{_L("lg_devis_n_nbsp").format(ref=REF)} — {CLIENT_NAME} — {DATE_STR}</div>
    </div>
    {logo_html("entete")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <div style="padding:14px 24px;flex:1;min-height:0;">
{_corps}
  </div>

  <div style="background:{CN};padding:6px 24px 5px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>
    <div style="font-size:7pt;color:#888;">{ENT_ETUDE_CONTACT}</div>
    <div style="font-size:7pt;color:#888;">{pied or _L("lg_ret_pied").format(ref=REF)}</div>
  </div>
</div>
"""


def page_calepinage():
    """CAL182 — page « Calepinage » : la PLANCHE COTÉE, telle que le serveur la rend.

    Le document client n'emportait que l'AFFICHE du calepinage (une image sans
    cotes ni cartouche). La planche CAL171, elle, porte l'échelle, le nord, la
    légende et le cartouche : c'est la pièce qu'un client, un bureau de
    contrôle ou une équipe de pose peut lire.

    Ce que cette page fait : elle MET EN PAGE le SVG que le builder lui donne.
    Elle ne dessine rien, ne mesure rien, ne convertit rien — une seconde
    géométrie serait une seconde vérité. **AUCUN MONTANT** n'y figure : la
    planche ne porte que des longueurs et des repères, et ``Produit.prix_achat``
    n'y entre par aucun chemin.
    """
    empreinte_html = (
        f'<div style="margin-top:8px;font-size:6.5pt;color:{CG4};">'
        f'{_esc(CALEPINAGE_EMPREINTE)}</div>') if CALEPINAGE_EMPREINTE else ""

    return f"""
<div class="page">
  <div style="background:{CN};padding:12px 24px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">{_L("lg_calepinage")}</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">{_L("lg_devis_n_nbsp").format(ref=REF)} — {CLIENT_NAME} — {DATE_STR}</div>
    </div>
    {logo_html("entete")}
  </div>
  <div style="height:3px;background:{CA};flex-shrink:0;"></div>

  <div style="padding:14px 24px;flex:1;min-height:0;">
    <div style="font-size:8pt;color:{CG4};margin-bottom:10px;">
      {_L("lg_calep_intro")}
    </div>
    <div style="background:white;border:1px solid {CG2};border-radius:7px;
                padding:6px;text-align:center;">{CALEPINAGE_SVG}</div>
    <div style="margin-top:10px;font-size:6.5pt;color:{CG4};font-style:italic;">
      {_L("lg_calep_note")}
    </div>
    {empreinte_html}
  </div>

  <div style="background:{CN};padding:6px 24px 5px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div style="font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;">{ENT_NOM_MARQUE}</div>
    <div style="font-size:7pt;color:#888;">{ENT_ETUDE_CONTACT}</div>
    <div style="font-size:7pt;color:#888;">{_L("lg_calep_pied").format(ref=REF)}</div>
  </div>
</div>
"""


def build_html():
    from .legacy_etude import page_etude, etude_rendue  # SPL169 — import local (cycle)
    print("  Generating charts...")
    # M5 — la GARDE MOYENNE TENSION s'étend à la page 2. Un dossier MT n'a
    # aucun chiffre d'économies légitime (ceux disponibles sortent du barème
    # BASSE TENSION) : la page 1 les omettait déjà, la courbe « Gain cumulé sur
    # 25 ans » les traçait quand même. Idem quand la puissance n'a aucun
    # ancrage réel (M2) : sans kWc, le gain cumulé vaut zéro — on n'imprime pas
    # une courbe plate à zéro, on n'imprime rien.
    # QJR123 — UNE seule définition, partagée avec les blocs « méthode » et
    # « hypothèses » de la page 3 (qui n'en avaient aucune).
    _sans_economies = _sans_economies_publiees()
    # QJR125 — AUCUN graphe sans cashflow RÉEL. Le repli « économie plate »
    # (droite) est faux de +14,5 % / +36,6 % sur le gain final (M5) et était
    # tracé sans la moindre mention : on omet la carte, comme sous
    # ``_sans_economies``.
    img_roi = ("" if (_sans_economies or not _courbes_roi_tracables())
               else make_chart_roi())
    img_mon = "" if (_sans_economies or not SHOW_MONTHLY) else make_chart_monthly()
    etude_html = page_etude() if etude_rendue() else ""
    annexe_html = (page_annexe_technique()
                   if (INCLUDE_ANNEXE and ELECTRICAL_DESIGN) else "")
    # CAL182 — la planche s'intercale APRÈS l'annexe, avant la signature :
    # l'ordre du document va du commercial au technique, puis à l'engagement.
    calepinage_html = (page_calepinage()
                       if (INCLUDE_CALEPINAGE and CALEPINAGE_SVG) else "")
    # CAD122 — l'annexe de rétractation vient APRÈS la page de signature :
    # c'est la pièce que le client DÉTACHE, elle ne s'intercale pas au milieu
    # du document. Rendue SEULEMENT si le bon se signe au domicile ; sinon le
    # document est byte-identique à celui d'avant (art. 32 inchangé).
    domicile_html = page_annexe_domicile() if SIGNE_AU_DOMICILE else ""
    return f"""<!DOCTYPE html>
<html {_attributs_langue_html()} style="background:#FFFFFF !important;"><head><meta charset="UTF-8">
<title>Devis {ENT_NOM_MARQUE} N\u00b0 {REF}</title>
<style>{CSS}{_css_arabe() if i18n_labels.est_rtl(LANGUE_SORTIE) else ""}</style></head>
<body style="background:#FFFFFF !important;">
{page1()}
{page2(SANS_ITEMS, img_roi, img_mon)}
{etude_html}
{annexe_html}
{calepinage_html}
{page3()}
{domicile_html}
</body></html>"""


#: QRP1/A4 — hauteur de la bande d'en-tête du format UNE PAGE, en millimètres.
#: C'est la hauteur qu'y occupe le logo (80 px). Elle est désormais IMPOSÉE à
#: la rangée (et non plus subie), pour deux raisons prouvées en revue :
#:   · sans ``logo.png``, ``logo_html`` retombe sur un texte de 15 pt et la
#:     bande se serait réglée sur la vignette QR — donc une hauteur DIFFÉRENTE
#:     selon la présence d'un asset ;
#:   · la zone de contenu de cette page est bornée (``overflow:hidden``), donc
#:     un en-tête plus haut ROGNE SILENCIEUSEMENT le bas du document (le Total
#:     TTC d'un devis dense) sans qu'aucune garde de pagination ne s'en
#:     aperçoive — le PDF ferait toujours 1 page.
#: Toute la vignette QR tient sous cette hauteur, par construction.
ONEPAGE_HEADER_MM = 21.17

#: QJR161 — borne BASSE de la zone de contenu du une-page, en px CSS, telle que
#: le gabarit la pose (``bottom:72px``). Au-delà, ``overflow:hidden`` ROGNE
#: silencieusement : c'est la ligne que le bloc de totaux ne doit jamais
#: franchir. Constante partagée par le gabarit, la mesure et les tests.
ONEPAGE_FOOTER_PX = 72

#: QJR163 (a) — capacité de la nomenclature de l'annexe technique. Au-delà, les
#: lignes ne tiennent plus sur la page : elles sont retirées ET DÉCLARÉES par
#: une ligne finale (« … et N autres composants »), jamais coupées en silence.
BOM_MAX_LIGNES = 22


def _cartes_pompage_synthese(synthese):
    """AGR313 — les cartes du résumé pompage du une-page : module de la
    surface agricole (AGC2, ``agricole/onepage.py``)."""
    from .agricole.onepage import cartes_pompage
    return cartes_pompage(sys.modules[__name__], synthese)


def _cartes_ci_onepage(chiffres):
    """CIQ210 (complément) — vignettes « Production annuelle », « Économies
    estimées / an (base) » et « Retour estimé » du une-page C&I, lues sur
    ``chiffres_cles(synthese_ci)`` : la production du moteur C&I, l'argent du
    bloc ``economie_ci`` (``synthese_ci.argent``). Valeur absente ⇒ vignette
    OMISE — jamais la production par ville ni ``calculate_savings_roi``."""
    try:
        from .ci.couverture import ans
    except ImportError:  # exécution directe du moteur depuis son dossier
        from ci.couverture import ans
    cellules = []
    prod = chiffres.get("production_kwh_an")
    if prod:
        cellules.append(
            (_L("op_production_annuelle"),
             f"{fnum(prod)}{ci_onepage.unite_kwh_an(LANGUE_SORTIE, _L)}",
             _ancre_figure("production_annuelle_kwh", fnum(prod))))
    if MASQUER_ECONOMIES:
        return cellules
    eco = chiffres.get("economie_annuelle_mad")
    if eco is not None:
        base = chiffres.get("base_economie")
        # AMOT84 — base et unité dans la langue du document (fr inchangé).
        libelle = (_L("op_economies_estimees_an")
                   + (f" ({_L('ci_' + base.lower())})"
                      if base in ("HT", "TTC") else
                      f" ({base})" if base else "")
                   + ci_onepage.legende_retour(chiffres, _L) + ci_onepage.economie_ttc(chiffres, fnum, _L))
        cellules.append((libelle, f"{fnum(eco)} {_L('ci_mad_an')}",
                         _ancre_figure("economie_annuelle", fnum(eco))))
    payback = chiffres.get("payback_ans")
    if payback is not None:
        cellules.append((_L("op_retour_estime"),
                         f"{ans(payback)}{ci_onepage.annees(_L('op_unite_ans'), LANGUE_SORTIE, payback)}",
                         _ancre_figure("payback_ans", ans(payback))))
    return cellules


def _bon_pour_accord_compact_html():
    """AGR313 — bloc « Bon pour accord » compact du une-page agricole : nom,
    date, signature. Sa DERNIÈRE ligne porte le libellé, si bien que la mesure
    du une-page (``_mesure_onepage``) le garde dans la zone visible."""
    return (
        f'<div style="margin:6px 24px 0;border:1px solid {CN};'
        f'border-radius:6px;padding:5px 10px;">'
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:7pt;color:{CG7};">'
        f'<span>{_L("bpa_nom")}&#160;: {CLIENT_NAME}</span>'
        f'<span>{_L("bpa_date")}&#160;:&#160;____/____/________</span></div>'
        f'<div style="height:22px;"></div>'
        f'<div style="font-size:7.5pt;font-weight:800;color:{CN};">'
        f'{_L("bon_pour_accord")} &#8212; {_L("bpa_signature")}</div></div>')


def _css_arabe():
    """NTI18N5 \u2014 @font-face arabe (Noto Sans Arabic d\u00e9j\u00e0 vendor\u00e9e dans
    ``assets/fonts/``) + famille appliqu\u00e9e au document, pour un document ARABE
    seulement.

    Charg\u00e9e PARESSEUSEMENT : un document fr/en ne lit pas ces woff2 et ne paie
    donc rien. Fichiers absents \u21d2 cha\u00eene vide : le gabarit retombe sur une
    police syst\u00e8me (d\u00e9gradation propre, jamais un PDF cass\u00e9), au prix d'un
    rendu arabe moins soign\u00e9.
    """
    # APDF6 (C-APDF-002) — plus d'@font-face woff2 vendorisé homonyme de la
    # police système (glyphes superposés mesurés) : LA CSS arabe partagée,
    # police système de l'image, aucun espacement de lettres.
    from .premium_base import css_arabe
    return css_arabe(libelles=True, document=True)


def _attributs_langue_html():
    """NTI18N5 \u2014 attributs ``lang``/``dir`` de l'\u00e9l\u00e9ment racine du document.

    Un document fran\u00e7ais rend EXACTEMENT ``lang="fr"`` (aucun attribut ajout\u00e9) ;
    un document arabe porte ``dir="rtl"``, d'o\u00f9 WeasyPrint tire l'alignement \u00e0
    droite et l'ordre miroir des colonnes de tableau.
    """
    attrs = f'lang="{LANGUE_SORTIE}"'
    if i18n_labels.est_rtl(LANGUE_SORTIE):
        attrs += ' dir="rtl"'
    return attrs


def _formes_total_ttc():
    """QJR161 + NTI18N5 \u2014 formes du libell\u00e9 \u00ab Total TTC \u00bb \u00e0 reconna\u00eetre dans les
    bo\u00eetes de texte compos\u00e9es par WeasyPrint.

    La mesure de d\u00e9bordement du une-page REP\u00c8RE le bas du bloc de totaux par
    son libell\u00e9. Cherch\u00e9 en dur, ce libell\u00e9 devenait introuvable d\u00e8s que le
    document changeait de langue : la mesure rendait alors ``None``, la garde
    QJR161 se taisait, et un devis dense pouvait de nouveau faire dispara\u00eetre
    son propre Total TTC dans la zone ``overflow:hidden`` sans qu'aucun compteur
    de pages ne bouge. On d\u00e9rive donc les formes de la table de libell\u00e9s
    ACTIVE, en gardant les formes fran\u00e7aises comme filet.

    Les deux casses sont fournies : le libell\u00e9 est rendu en
    ``text-transform:uppercase``, et WeasyPrint compose le texte transform\u00e9.
    (Les trois traductions de cette cl\u00e9 sont sans entit\u00e9 HTML : la cha\u00eene du
    gabarit est donc bien celle du texte compos\u00e9.)
    """
    formes = []
    bruts = [_L("total_ttc"), i18n_labels.libelle("total_ttc", "fr")]
    # AGR313 — en agricole, le bloc « Bon pour accord » compact vient APRÈS
    # les totaux : son libellé (dernière ligne du bloc) borne aussi la zone
    # visible, sinon la signature pourrait être rognée sans qu'on le mesure.
    if SYNTHESE_AGRICOLE is not None or CHIFFRES_CI is not None:  # CPDF : une-page C&I aussi
        bruts += [_L("bon_pour_accord"),
                  i18n_labels.libelle("bon_pour_accord", "fr")]
    for brut in bruts:
        for forme in (brut, brut.upper()):
            if forme and forme not in formes:
                formes.append(forme)
    return tuple(formes)


def _mesure_onepage(html):
    """QJR161 \u2014 MESURE du bas du bloc de totaux et de la hauteur d'une ligne.

    Rend ``(depassement_px, hauteur_ligne_px)`` : ``depassement_px`` est de
    combien le bloc \u00ab Total TTC \u00bb franchit la ligne de rognage
    (``ONEPAGE_FOOTER_PX``), ``0`` quand il tient. ``None`` quand la mesure est
    IMPOSSIBLE (WeasyPrint absent, page non compos\u00e9e) : on ne devine alors
    rien et le document reste celui d'aujourd'hui.

    C'est une MESURE, pas une capacit\u00e9 devin\u00e9e : le gabarit n'a aucune borne
    haute (``n_items > 12`` \u21d2 table compacte, et c'est tout) et la zone de
    contenu est en ``overflow:hidden``, donc un devis dense faisait dispara\u00eetre
    son propre Total TTC sans qu'aucun compteur de pages ne bouge.
    """
    try:
        from weasyprint import HTML as _HTML
    except Exception:  # noqa: BLE001 — \u2014 pas de WeasyPrint : aucune mesure (D-ENF22-BLE001)
        logger.warning("generate_devis_premium._mesure_onepage : erreur ignorée (mode dégradé)", exc_info=True)
        return None
    try:
        pages = _HTML(string=_html_sans_base(html)).render().pages
        if not pages:
            return None
        page = pages[0]
        limite = page.height - ONEPAGE_FOOTER_PX
        bas_totaux = None
        hauteurs = []
        formes = _formes_total_ttc()
        for boite in _boites_texte_onepage(page):
            texte = (getattr(boite, "text", "") or "")
            if any(forme in texte for forme in formes):
                bas = boite.position_y + boite.height
                bas_totaux = bas if bas_totaux is None else max(bas_totaux, bas)
            hauteurs.append(boite.height)
        # AMOT20 — la postcondition porte sur le DERNIER bloc de la zone (la
        # ligne Validité/Acompte/TVA ; le bon pour accord agricole est déjà
        # dans ``formes``) : son bloc entier (toutes ses lignes) doit tenir.
        from .onepage_mesure import bas_avec_conditions
        bas_totaux = bas_avec_conditions(page, html, formes, bas_totaux, _HTML)
        if bas_totaux is None:
            # CAD177 — le bloc de totaux est ABSENT de la page composée : ce
            # n'est PAS une mesure impossible. WeasyPrint arrête la composition
            # au bord bas de la page A4 et JETTE le reste du flux de la zone
            # ``overflow:hidden`` (constaté sur 60 lignes : 42 composées, puis
            # plus rien — ni lignes, ni « Total TTC »). Rendre ``None`` ici
            # laissait le document NON rogné, sans son Total TTC. On mesure donc
            # le MÊME HTML sur une page très haute : le flux part du haut, les
            # positions au-dessus de la ligne de rognage sont identiques, et le
            # bloc de totaux est enfin composé — d'où le vrai dépassement par
            # rapport à la limite de la page A4 réelle.
            bas_totaux = _bas_totaux_page_haute(_HTML, html, formes)
            if bas_totaux is None:
                return None
        hauteur_ligne = 0.0
        if hauteurs:
            hauteurs.sort()
            hauteur_ligne = hauteurs[len(hauteurs) // 2]
        return (max(0.0, bas_totaux - limite), hauteur_ligne)
    except Exception:  # noqa: BLE001 — \u2014 un PDF ne casse jamais sur une mesure (D-ENF22-BLE001)
        logger.warning("generate_devis_premium._mesure_onepage : erreur ignorée (mode dégradé)", exc_info=True)
        return None


#: CAD177 — hauteur de la page de MESURE (jamais rendue au client) : assez
#: haute pour composer le bloc de totaux du devis le plus dense.
_ONEPAGE_MESURE_HAUTEUR_MM = 3000

_CSS_PAGE_HAUTE = (
    "<style>@page{size:210mm %dmm !important;}"
    ".page{height:%dmm !important;}</style>"
    % (_ONEPAGE_MESURE_HAUTEUR_MM, _ONEPAGE_MESURE_HAUTEUR_MM))


def _bas_totaux_page_haute(html_cls, html, formes):
    """CAD177 — bas du bloc « Total TTC » mesuré sur une page de mesure haute.

    Sert UNIQUEMENT à la mesure (le document client reste en A4) ; ``None`` si
    le libellé reste introuvable même là (gabarit inattendu : on ne devine
    rien)."""
    if "</head>" not in html:
        return None
    haute = html.replace("</head>", _CSS_PAGE_HAUTE + "</head>", 1)
    pages = html_cls(string=_html_sans_base(haute)).render().pages
    if not pages:
        return None
    bas_totaux = None
    for boite in _boites_texte_onepage(pages[0]):
        texte = (getattr(boite, "text", "") or "")
        if any(forme in texte for forme in formes):
            bas = boite.position_y + boite.height
            bas_totaux = bas if bas_totaux is None else max(bas_totaux, bas)
    # AMOT20 — même ancre que la mesure A4 : le DERNIER bloc de la zone.
    bas_fin = _bas_bloc_fin(pages[0])
    if bas_fin is not None and bas_totaux is not None:
        bas_totaux = max(bas_totaux, bas_fin)
    return bas_totaux


def _formes_bloc_fin():
    """AMOT20 — libellés de la ligne de conditions (dernier bloc de la zone
    du une-page), dans la langue du document et en français (filet).
    APDF13 — la ligne porte les puces de ``cgv_imprimees`` : leur début
    (12 caractères, lisibles sur la première ligne) sert aussi d'ancre."""
    formes = []
    for cle in ("acompte", "apres_mise_en_marche"):
        for brut in (_L(cle), i18n_labels.libelle(cle, "fr")):
            brut = html.unescape(brut or "")
            if brut and brut not in formes:
                formes.append(brut)
    for puce in CGV_IMPRIMEES.get("puces") or []:
        brut = html.unescape(re.sub(r"<[^>]+>", "", str(puce)))
        brut = brut.replace("\xa0", " ").strip()[:12]
        if brut and brut not in formes:
            formes.append(brut)
    return tuple(formes)


def _conditions_onepage_html():
    """APDF13 — la ligne de conditions du une-page : les puces de
    ``cgv_imprimees`` (APDF12 — société gelées ou vives, défaut du moteur
    sinon ; tronquées comme les clauses quand la page est dense), la validité
    et la note de TVA seulement quand aucune puce ne les porte déjà, puis la
    note de remise par ligne.
    ERR-APDF48 — la ligne s'ouvre sur le TITRE de ``cgv_imprimees`` (celui
    de la page publique, variante C&I comprise), en ligne : aucune page de
    plus, la densité adaptative mesure ce même bloc."""
    puces = list(CGV_IMPRIMEES.get("puces") or [])
    if ONEPAGE_TEXTES_TRONQUES:
        puces = [_tronquer_texte_echappe(p, _ONEPAGE_CLAUSE_MAX)
                 for p in puces]
    morceaux = [f'<strong style="color:{CN};">{t}</strong>'
                for t in [str(CGV_IMPRIMEES.get("titre") or "").strip()] if t]
    validite = _doc_text("validite_onepage")
    if validite and not (VALID_UNTIL and any(VALID_UNTIL in p
                                             for p in puces)):
        morceaux.append(validite)
    morceaux += [f"&#183; {p}" for p in puces]
    if TVA_NOTE and not any(TVA_NOTE in p for p in puces):
        morceaux.append(f"&#183; {TVA_NOTE}")
    if DISCOUNT_PCT > 0:
        morceaux.append(f"&#183; {_note_remise_par_ligne()}")
    return "".join(
        (f'<span style="margin-right:20px;">{m}</span>' if i < len(morceaux) - 1
         else f'<span>{m}</span>')
        for i, m in enumerate(morceaux))


def _bas_bloc_fin(page):
    """AMOT20 — bas du BLOC (div) qui porte la ligne de conditions du
    une-page : la boîte de bloc ancêtre la plus proche d'un texte qui porte
    l'un de ses libellés, toutes lignes comprises. ``None`` si introuvable."""
    formes = _formes_bloc_fin()
    bas = []

    def _walk(box, ancetres):
        texte = getattr(box, "text", None)
        if texte and any(f in texte for f in formes):
            for anc in reversed(ancetres):
                if type(anc).__name__ == "BlockBox":
                    _mh = getattr(anc, "margin_height", None)
                    bas.append(anc.position_y
                               + (_mh() if callable(_mh) else anc.height))
                    break
            else:
                bas.append(box.position_y + box.height)
        for child in (getattr(box, "children", None) or []):
            _walk(child, ancetres + [box])

    _walk(page._page_box, [])
    return max(bas) if bas else None


def _html_sans_base(html):
    """Le HTML tel quel \u2014 point d'extension si une base_url devient utile."""
    return html


def _boites_texte_onepage(page):
    """Toutes les bo\u00eetes de texte compos\u00e9es d'une page WeasyPrint, \u00e0 plat."""
    out = []

    def _walk(box):
        if getattr(box, "text", None):
            out.append(box)
        for child in (getattr(box, "children", None) or []):
            _walk(child)

    _walk(page._page_box)
    return out


# ── Public API for web app ────────────────────────────────────────────────────
def generate_premium_pdf(data: dict, out_path) -> str:
    """Generate premium PDF from a dynamic data dict; returns str(out_path).

    Required keys in data: ref, date, client_name, client_addr, client_phone,
    inst_type, puissance_kwc, nb_panneaux, watt_par_panneau, prod_kwh,
    total_sans, total_avec, eco_s_ann, eco_a_ann, eco_a_cumul,
    roi_s, roi_a, eco_s_monthly, eco_a_monthly, sans_items, avec_items.

    Items dicts must have: designation, quantite, prix_unit_ttc, marque.
    """
    # Décision fondateur 08/10/2026 — un devis envoyé avant les
    # corrections du moteur garde ses formats d'origine (AMOT24/26/45).
    poser_regles_origine((data or {}).get("regles_calcul_origine"), avant_2710=(data or {}).get("regles_avant_2710"))
    # ERR17 — serialize the whole render: the body writes module globals and
    # reads them back while building the HTML, so concurrent renders must not
    # interleave (one client's data leaking into another's PDF).
    with _RENDER_LOCK, format_langue(data):  # AMOT101 — nombres C&I EN
        return _render_premium_pdf(data, out_path)


def apply_quote_data(data: dict) -> None:
    """Ingère ``data`` dans les globales du module (SANS rendre quoi que ce soit).

    Extrait de ``_render_premium_pdf`` le 20/08/2026 : le rendu PDF passait par
    WeasyPrint, donc AUCUN test ne pouvait scanner le DOCUMENT réellement
    produit sans une dépendance lourde — c'est exactement le trou qui a laissé
    passer le « 87,4 % » codé en dur (audit du 18/08). Avec cette fonction, un
    test pur appelle ``render_html_for(data)`` et cherche (ou refuse) une chaîne
    dans le HTML EXACT qui part chez WeasyPrint. Le chemin PDF est inchangé :
    ``_render_premium_pdf`` appelle ces deux fonctions, dans le même ordre,
    sous le même verrou.

    QJR163 (d) — SANS VERROU : cette fonction ÉCRIT les globales du module
    (ERR17) et n'acquiert PAS ``_RENDER_LOCK`` — seul ``generate_premium_pdf``
    le prend. Tout appelant en contexte CONCURRENT doit donc le prendre
    lui-même (ou passer par ``generate_premium_pdf``), sous peine d'entrelacer
    les données de deux devis dans un même document.
    """
    global CLIENT_NAME, CLIENT_ADDR, CLIENT_PHONE, CLIENT_ICE, REF, DATE_STR
    global MIS_A_JOUR_LE, REMPLACE_REF
    global KWC, NB_PAN, WP, PROD_KWH, TOTAL_SANS, TOTAL_AVEC
    global DISCOUNT_PCT, TOTAL_SANS_BEFORE, TOTAL_AVEC_BEFORE
    global ECO_S_ANN, ECO_A_ANN, ROI_S, ROI_A, INST_TYPE, VILLE_CALCUL
    global ROI_S_JAMAIS, ROI_A_JAMAIS
    global SANS_ITEMS, AVEC_ITEMS, ECO_S_M, ECO_A_M, CUMUL_S, CUMUL_A
    global FACTURES_M
    global SCENARIO, RECOMMENDED, SHOW_MONTHLY
    global DEVIS_FINAL
    global TVA_PCT, MODE_INSTALLATION, ETUDE, INCLUDE_ETUDE
    # PV46 — annexe technique (schéma unifilaire + nomenclature). Même patron
    # de global que INCLUDE_ETUDE, mêmes défauts inertes : sans les clés du
    # builder, la page n'existe pas et le PDF est byte-identique.
    global INCLUDE_ANNEXE, ELECTRICAL_DESIGN, SLD_SVG
    # CAL182 — page « Calepinage » (planche cotée). Même patron, mêmes défauts
    # inertes : sans les clés du builder, la page n'existe pas.
    global INCLUDE_CALEPINAGE, CALEPINAGE_SVG, CALEPINAGE_EMPREINTE
    global SIGNE_AU_DOMICILE  # CAD122 — signature au domicile (loi 31-08)
    global TVA_NOTE, TOTAUX_SANS, TOTAUX_AVEC, TOTAUX_ALL, SANS_BULLETS, AVEC_BULLETS
    global PAY_A, PAY_M, PAY_S, ONEPAGE_NOTE_BATTERIE, LIBELLE_AVEC
    global LINKS  # QRP1 — liens client (proposition tokenisée)
    global DOC_TEXTS, ACCEPTE_PAR_NOM, DATE_ACCEPTATION, NOTE_CLIENT
    global CLAUSES_CGV, CGV_IMPRIMEES  # QJR668 clauses gelées, APDF13 CGV
    global DEVISE  # FG52 — devise du document (ISO 4217)
    global LANGUE_SORTIE, LIBELLES_DOC  # NTI18N5 — langue + libellés du gabarit
    global SAVINGS_METHOD  # QF3 — bloc « Comment nous calculons vos économies »
    global WATERMARK_STANDARD  # L-NIV — filigrane PDF public niveau standard
    SAVINGS_METHOD = data.get("savings_method")
    WATERMARK_STANDARD = data.get("_watermark_standard")
    # QXMT — un dossier MT sans économies d'étude n'imprime AUCUN chiffre
    # d'économies : ceux disponibles ici sont calculés au barème BASSE TENSION.
    global MASQUER_ECONOMIES, TARIF_MT_MENTION
    MASQUER_ECONOMIES = bool(data.get("masquer_economies"))
    TARIF_MT_MENTION = data.get("tarif_mt_mention") or ""
    global PUISSANCE_INCONNUE  # M2 — puissance sans ancrage réel
    PUISSANCE_INCONNUE = bool(data.get("puissance_inconnue"))
    # F1/L-2OPT — scalaires PAR OPTION. Sans les clés du builder, le drapeau
    # reste faux et chaque surface lit le scalaire global comme avant.
    global PANNEAUX_DIVERGENTS, KWC_SANS, KWC_AVEC, NB_PAN_SANS, NB_PAN_AVEC
    PANNEAUX_DIVERGENTS = bool(data.get("panneaux_divergents"))
    KWC_SANS = float(data.get("puissance_kwc_sans") or 0)
    KWC_AVEC = float(data.get("puissance_kwc_avec") or 0)
    NB_PAN_SANS = int(data.get("nb_panneaux_sans") or 0)
    NB_PAN_AVEC = int(data.get("nb_panneaux_avec") or 0)
    global PROD_KWH_SANS, PROD_KWH_AVEC  # PDFPROD — production par option
    PROD_KWH_SANS = int(data.get("prod_kwh_sans") or 0)
    PROD_KWH_AVEC = int(data.get("prod_kwh_avec") or 0)
    global HYPOTHESES  # QK4 — bloc « Nos hypothèses »
    HYPOTHESES = data.get("hypotheses")
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
    MIS_A_JOUR_LE = _esc(data.get("mis_a_jour_le") or "")
    REMPLACE_REF  = _esc(data.get("remplace_reference") or "")
    # M2/M3 — puissance, compte de panneaux et watt unitaire peuvent être
    # INCONNUS (None) : ils ne sont plus jamais déduits du prix. 0 = « rien à
    # imprimer », et chaque vignette qui en dépend est omise.
    KWC          = float(data.get("puissance_kwc") or 0)
    NB_PAN       = int(data.get("nb_panneaux") or 0)
    WP           = int(data.get("watt_par_panneau") or 0)
    PROD_KWH     = int(data.get("prod_kwh") or 0)
    TOTAL_SANS        = float(data["total_sans"])
    TOTAL_AVEC        = float(data["total_avec"])
    DISCOUNT_PCT      = float(data.get("discount_pct", 0))
    TOTAL_SANS_BEFORE = float(data.get("total_sans_before", TOTAL_SANS))
    TOTAL_AVEC_BEFORE = float(data.get("total_avec_before", TOTAL_AVEC))
    ECO_S_ANN    = int(data["eco_s_ann"])
    ECO_A_ANN    = int(data["eco_a_ann"])
    ROI_S        = float(data["roi_s"])
    ROI_A        = float(data["roi_a"])
    ROI_S_JAMAIS = bool(data.get("roi_s_jamais"))
    ROI_A_JAMAIS = bool(data.get("roi_a_jamais"))
    INST_TYPE    = data["inst_type"]
    VILLE_CALCUL = str(data.get("client_ville_libelle")
                       or data.get("client_city") or "").strip()
    SCENARIO     = data.get("scenario", "Les deux (Sans + Avec)")
    RECOMMENDED  = data.get("recommended", "Avec batterie")
    SHOW_MONTHLY = data.get("show_monthly", True)
    DEVIS_FINAL    = data.get("devis_final", False)
    # AMOT77 — un 0 % explicite reste 0 % (seul ``None`` retombe sur 20).
    TVA_PCT        = float(20 if data.get("taux_tva") is None
                           else data["taux_tva"])
    MODE_INSTALLATION = data.get("mode_installation", "") or ""
    ETUDE          = data.get("etude") or {}
    # AGR313 — le une-page agricole lit ses cartes dans la synthèse agricole
    # (mêmes valeurs, mêmes omissions que le 3 pages et la page en ligne),
    # plus dans ``ETUDE`` (un troisième chemin qui pouvait diverger).
    global SYNTHESE_AGRICOLE
    SYNTHESE_AGRICOLE = None
    if MODE_INSTALLATION.strip().lower() == "agricole":
        try:
            from .agricole.synthese import synthese_agricole
            SYNTHESE_AGRICOLE = synthese_agricole(data)
        except Exception:  # noqa: BLE001 — un rendu ne casse jamais ici (D-ENF22-BLE001)
            logger.warning("generate_devis_premium.apply_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
            SYNTHESE_AGRICOLE = None
    # CIQ210 (complément) — le une-page C&I lit production, économie et
    # retour dans ``synthese_ci`` (moteur C&I + bloc ``economie_ci``), comme
    # le document complet et /proposition ; plus jamais ``prod_kwh`` (par
    # ville) ni ``eco_s_ann`` (``calculate_savings_roi``, BT/60 %). Une
    # synthèse illisible ⇒ dict VIDE ⇒ vignettes omises, jamais un repli.
    global CHIFFRES_CI, SYNTHESE_CI
    SYNTHESE_CI, CHIFFRES_CI = ci_onepage.lire_synthese(data, MODE_INSTALLATION)
    INCLUDE_ETUDE  = bool(data.get("include_etude", False))
    INCLUDE_ANNEXE = bool(data.get("include_annexe_technique", False))
    ELECTRICAL_DESIGN = data.get("electrical_design") or {}
    SLD_SVG        = data.get("sld_svg") or ""
    INCLUDE_CALEPINAGE = bool(data.get("include_calepinage", False))
    # ACAL103 (C-ACAL-117, QJR666) — un devis RÉSIDENTIEL rendu par ce moteur
    # (cas « + étude ») n'ajoute la planche que sur une demande EXPLICITE
    # (``include_calepinage_demande``, posé par le builder) : l'AUTO n'ajoute
    # aucune page, exactement comme ``residential/render.calepinage_demande``.
    # Les autres marchés gardent l'AUTO (D-QJR5-12).
    if (MODE_INSTALLATION.strip().lower() in ("", "residentiel", "résidentiel")
            and not data.get("include_calepinage_demande")):
        INCLUDE_CALEPINAGE = False
    # CAD122 — marqueur « signé au domicile », posé CÔTÉ SERVEUR depuis le bon
    # de commande (jamais une option du corps client : c'est un fait juridique,
    # pas une préférence de rendu). Faux = document inchangé (art. 32).
    SIGNE_AU_DOMICILE = bool(data.get("signe_au_domicile", False))
    # Le SVG de la planche est un fragment composé PAR LE SERVEUR (CAL171),
    # jamais un texte saisi : il est inséré tel quel, comme ``SLD_SVG``.
    # L'empreinte, elle, est un TEXTE — donc échappée à l'usage.
    CALEPINAGE_SVG = data.get("calepinage_svg") or ""
    CALEPINAGE_EMPREINTE = data.get("calepinage_empreinte") or ""
    TVA_NOTE       = (data.get("tva_note") or _tva_note_par_defaut(
        TVA_PCT, data.get("langue_sortie")))
    # FG52 — devise portée par le document (défaut MAD = comportement inchangé).
    DEVISE         = (data.get("devise") or "MAD").strip().upper()
    # NTI18N5 — langue du document + table de libellés ROUTÉE par le builder.
    # Sans ces clés (appelant historique), la langue est le français et la table
    # est la française : document inchangé au caractère près. Une langue hors
    # fr/en/ar est ramenée au français avant d'atteindre le moindre gabarit.
    LANGUE_SORTIE  = i18n_labels.normaliser(data.get("langue_sortie"))
    _libelles_recus = data.get("libelles_document")
    LIBELLES_DOC   = (dict(_libelles_recus)
                      if isinstance(_libelles_recus, dict) and _libelles_recus
                      else i18n_labels.libelles(LANGUE_SORTIE))
    # DC1 — identité société (multi-tenant) : réinitialise les défauts puis
    # applique le profil de la société du devis. Champs vides → littéraux
    # Taqinor historiques (byte-identique) ; sinon SON identité s'affiche.
    _apply_entreprise(data.get("entreprise"))
    # QG7 — ajoute le contact du créateur du devis (nom + tél) à la ligne de
    # coordonnées, APRÈS _apply_entreprise. Seller vide → byte-identique.
    _apply_seller(data.get("seller"))

    # Totaux canoniques (une seule source pour toutes les pages). À défaut
    # (anciens appels), reconstruits une fois ici avec la même chaîne.
    # ── QJR162 (c) — PAS DE CHAÎNE DE TOTAUX FABRIQUÉE ──────────────────────
    # ``_fallback_totaux`` recalculait la chaîne avec un taux de TVA UNIQUE et
    # SANS ``tva_par_taux`` : sur un devis à taux mixtes (réforme 10/20), la
    # colonne affichait 10 % et 20 % par ligne pendant que le bloc n'imprimait
    # qu'une ligne « TVA (20 %) ». Son ``or`` mordait de surcroît sur un dict
    # VIDE. Les totaux canoniques sont calculés UNE fois par le builder : sans
    # eux, le moteur LÈVE plutôt que de publier une chaîne inventée.
    def _totaux_canoniques(cle):
        valeur = data.get(cle)
        if not isinstance(valeur, dict) or not valeur:
            raise ValueError(
                "generate_devis_premium: totaux canoniques manquants (%s) — "
                "le moteur ne fabrique pas de chaîne de totaux (QJR162)."
                % cle)
        return valeur

    TOTAUX_SANS = _totaux_canoniques("totaux_sans")
    TOTAUX_AVEC = _totaux_canoniques("totaux_avec")
    TOTAUX_ALL = data.get("totaux_all") or None

    # ── QJR146 (e) — UN SEUL TOTAL PAR OPTION, ET IL EST PROUVÉ ──────────────
    # ``total_sans``/``total_avec`` (scalaires TTC des vignettes d'option) et
    # ``totaux_sans``/``totaux_avec`` (la chaîne canonique Sous-total → TVA →
    # Total TTC du tableau) étaient ingérés depuis QUATRE clés INDÉPENDANTES,
    # sans le moindre invariant : une charge utile où elles divergent imprimait
    # deux totaux différents pour la MÊME option, sur deux pages du même
    # document. Le builder les DÉRIVE l'une de l'autre
    # (``total_sans = totaux_sans['ttc']``) — on exige donc ici qu'elles
    # coïncident, et on LÈVE plutôt que de choisir en silence (même doctrine
    # que ``_totaux_canoniques`` ci-dessus, QJR162).
    for _cle_scalaire, _valeur, _totaux in (
            ("total_sans", TOTAL_SANS, TOTAUX_SANS),
            ("total_avec", TOTAL_AVEC, TOTAUX_AVEC)):
        try:
            _ttc = float(_totaux.get("ttc"))
        except (TypeError, ValueError):
            raise ValueError(
                "generate_devis_premium: totaux canoniques sans TTC lisible "
                "(%s) — le moteur ne choisit pas entre deux totaux."
                % _cle_scalaire)
        if abs(_ttc - float(_valeur)) > 0.01:
            raise ValueError(
                "generate_devis_premium: %s (%.2f) ne correspond pas au TTC "
                "de sa chaîne de totaux (%.2f) — deux totaux pour une seule "
                "option (QJR146)." % (_cle_scalaire, float(_valeur), _ttc))
    _terms = data.get("payment_terms") or {}
    # QJR623 / QJR668 — même normalisation que la page publique de signature
    # (``_pct_echeance``, partagée avec ``cgv_bullets_remplies``).
    PAY_A = _pct_echeance(_terms.get("acompte"), 30)
    PAY_M = _pct_echeance(_terms.get("materiel"), 60)
    PAY_S = _pct_echeance(_terms.get("solde"), 10)
    global MONTANTS_TRANCHES
    MONTANTS_TRANCHES = dict(data.get("montants_tranches") or {})
    ONEPAGE_NOTE_BATTERIE = bool(data.get("onepage_note_batterie", False))
    LIBELLE_AVEC = str(data.get("libelle_avec") or "Avec batterie")
    LINKS = dict(data.get("links") or {})
    global ONEPAGE_BRANCHE  # M4 — branche des lignes du format une page
    _br = data.get("onepage_branche")
    ONEPAGE_BRANCHE = _br if _br in ("sans", "avec") else None
    # QJR13 — capacité batterie RÉELLE des lignes (jamais un défaut) : sert
    # UNIQUEMENT à prouver qu'un optimum du moteur décrit bien ce devis.
    global BATTERIE_KWH_TOTAL
    try:
        BATTERIE_KWH_TOTAL = float(data.get("batterie_kwh_total") or 0)
    except (TypeError, ValueError):
        BATTERIE_KWH_TOTAL = 0.0
    global BATTERIE_KWH_UTILE_VENDUE
    try:
        _utile = float(data.get("batterie_kwh_utile_vendue") or 0)
    except (TypeError, ValueError):
        _utile = 0.0
    BATTERIE_KWH_UTILE_VENDUE = ((BATTERIE_KWH_TOTAL, _utile)
                                 if _utile > 0 else None)
    # ── L-2OPT (chantier « deux optimiseurs », 24/08/2026) — LA PUISSANCE SUIT
    # LA BRANCHE FACTURÉE ────────────────────────────────────────────────────
    # Même doctrine que M4 pour l'économie annuelle : la page UNE chiffre UNE
    # branche (``ONEPAGE_BRANCHE``, celle de ses lignes). Depuis que les deux
    # options peuvent porter des nombres de panneaux différents, le scalaire
    # GLOBAL (``puissance_kwc``/``nb_panneaux``, qui porte l'option AVEC) ne
    # décrit plus la branche imprimée : « Puissance crête » et « Prix par kWc »
    # mélangeraient le champ PV d'une option au prix de l'autre. On lit donc les
    # figures DE CETTE BRANCHE dès que les deux divergent. Options égales (tout
    # l'existant) ⇒ aucune réécriture, sortie byte-identique.
    if (data.get("pdf_mode", "full") == "onepage" and ONEPAGE_BRANCHE
            and data.get("panneaux_divergents")):
        _kwc_br = data.get(f"puissance_kwc_{ONEPAGE_BRANCHE}")
        _nb_br = data.get(f"nb_panneaux_{ONEPAGE_BRANCHE}")
        _wp_br = data.get(f"watt_par_panneau_{ONEPAGE_BRANCHE}")
        # F1 (26/08/2026) — MÊME BRANCHE, MÊME VÉRITÉ, JUSQU'AU BOUT. Le bloc
        # recalait la puissance et les panneaux, mais laissait « Production
        # annuelle » sur le scalaire global : la vignette annonçait la
        # production de l'AUTRE option juste à côté du kWc de celle-ci (et
        # « Production ÷ kWc » ne retombait plus sur aucun productible réel).
        # L'économie annuelle, elle, était déjà choisie par branche dans
        # ``page_onepage`` (M4) et devient juste — elle aussi — maintenant que
        # le builder chiffre les économies par option.
        _prod_br = data.get(f"prod_kwh_{ONEPAGE_BRANCHE}")
        # Valeur illisible (None) ⇒ on ne remplace RIEN par un repli : la
        # vignette correspondante s'omet déjà d'elle-même sur un 0.
        if _kwc_br:
            KWC = float(_kwc_br)
        if _nb_br:
            NB_PAN = int(_nb_br)
        if _wp_br:
            WP = int(_wp_br)
        if _prod_br:
            PROD_KWH = int(_prod_br)
    global VALID_UNTIL  # M7 — échéance réelle du devis
    VALID_UNTIL = (data.get("valid_until") or "").strip()
    global DELAI_VISITE, DELAI_INSTALLATION  # Q5 — délais indicatifs
    _dl = data.get("delais") or {}
    from .residential.theme import delai_doc as _dd  # RPDF : délais dans la langue du document
    DELAI_VISITE, DELAI_INSTALLATION = (_dd(data, (_dl.get(k) or "").strip()) for k in ("visite_technique", "installation"))
    global SAVINGS_ESTIMATED  # M10 — économies estimées ?
    SAVINGS_ESTIMATED = bool(data.get("savings_estimated"))
    # XSAL14/XSAL5 — structure (sections/notes) + options proposées (rendu seul,
    # hors totaux). Absents → byte-identique. Escapés à l'ingestion (ERR37).
    global LIGNES_STRUCTURE, OPTIONS_PROPOSEES
    LIGNES_STRUCTURE = [
        {"type": str(s.get("type") or "section"),
         "ordre": s.get("ordre") or 0,
         "texte": _esc(str(s.get("texte") or ""))}
        for s in (data.get("lignes_structure") or [])
        if isinstance(s, dict)]
    OPTIONS_PROPOSEES = _esc_items(data.get("options_proposees") or [])
    # QJR30 — les puces d'option sont BÂTIES depuis des désignations de lignes
    # (donc du texte contrôlé par l'utilisateur) et étaient rendues telles
    # quelles en HTML : un « < » non apparié dans une désignation mangeait la
    # carte d'option. Même échappement ERR37 que les items ci-dessous.
    SANS_BULLETS = [_esc(b) for b in (data.get("sans_bullets") or [])]
    AVEC_BULLETS = [_esc(b) for b in (data.get("avec_bullets") or [])]
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
    # QJR154 — ERR37 échappait le nom et l'adresse du client mais PAS celui-ci,
    # qui est pourtant le seul texte du document écrit par une personne NON
    # AUTHENTIFIÉE (le « nom » posté sur le portail public, repris par
    # ``services.accept_devis``) : ``_acceptance_stamp_html`` l'injectait brut.
    ACCEPTE_PAR_NOM = _esc(data.get("accepte_par_nom") or "")
    NOTE_CLIENT = _esc((data.get("note_client") or "").strip())
    CLAUSES_CGV, CGV_IMPRIMEES = _conditions_echappees(data)
    DATE_ACCEPTATION = (data.get("date_acceptation") or "")

    # Numérotation = nombre RÉEL de pages rendues (l'étude entre les pages 2 et 3 → 4).
    global PAGES_TOTAL, PAGE3_NUM
    from .legacy_etude import etude_rendue  # RPDF20 — étude sans contenu ⇒ ni rendue ni comptée
    _full = data.get("pdf_mode", "full") == "full"
    _with_etude = etude_rendue() and _full
    # PV46 — l'annexe technique s'intercale APRÈS l'étude, avant la signature.
    # Sans conception électrique, elle DISPARAÎT (même dégradation gracieuse
    # que l'étude : la page n'est ni rendue ni comptée).
    _with_annexe = bool(INCLUDE_ANNEXE and ELECTRICAL_DESIGN) and _full
    # CAL182 — la planche suit la même dégradation : sans SVG rendu, la page
    # n'est ni rendue ni comptée. Le format 'onepage' reste à UNE page.
    _with_calepinage = bool(INCLUDE_CALEPINAGE and CALEPINAGE_SVG) and _full
    PAGES_TOTAL = (3 + (1 if _with_etude else 0) + (1 if _with_annexe else 0)
                   + (1 if _with_calepinage else 0))
    PAGE3_NUM = PAGES_TOTAL
    # ERR37 — escape user text in line items at the ingestion boundary so every
    # downstream renderer (full + one-page) emits safe HTML.
    # QJR408 — PLUS AUCUNE SECONDE PASSE DE CLASSIFICATION ICI : le tableau
    # imprime EXACTEMENT les lignes que le builder a comptées dans le total
    # figé (cf. le bloc QJR408 en tête de module).
    SANS_ITEMS   = ci_installation.lignes_client(_esc_items(data["sans_items"]), data)
    AVEC_ITEMS   = ci_installation.lignes_client(_esc_items(data["avec_items"]), data)
    ECO_S_M      = data["eco_s_monthly"]
    ECO_A_M      = data["eco_a_monthly"]
    # M1 — `data["factures_mensuelles"]` vaut None quand le client n'a pas
    # donné ses 12 factures : `list(None)` faisait EXPLOSER le legacy, seul
    # chemin de repli du renderer résidentiel. Absence ⇒ liste vide ⇒ le
    # graphique mensuel omet les barres de facture (jamais un proxy).
    FACTURES_M   = list(data.get("factures_mensuelles") or [])
    eco_a_cumul  = int(data.get("eco_a_cumul") or 0)
    # ── M5 (audit adversarial du 19/08/2026) — LA COURBE 25 ANS N'EST PLUS UNE
    # DROITE. Elle traçait `−total + économie × année` : une économie PLATE sur
    # 25 ans, alors que le modèle du devis intègre la dégradation panneau
    # (0,5 %/an), le rendement batterie et la provision onduleur. Écart mesuré
    # sur le gain final : +14,5 % (option 1) et +36,6 % (option 2) de trop.
    # Le VRAI cumul est déjà dans les données (``cashflow_sans``/
    # ``cashflow_avec``, calculé par ``compute_cashflow_payback``) : on le trace
    # tel quel — la droite ne subsiste qu'en repli, si le cumul manque.
    # QJR125 — le repli « droite plate » n'est plus TRACÉ : il n'est conservé
    # que pour garder les listes bien formées (le graphe entier est omis quand
    # le cumul réel manque, exactement comme sous ``_sans_economies``).
    global CUMUL_S_REEL, CUMUL_A_REEL
    _cf_s = list(data.get("cashflow_sans") or [])
    _cf_a = list(data.get("cashflow_avec") or [])
    CUMUL_S_REEL = len(_cf_s) >= 25
    CUMUL_A_REEL = len(_cf_a) >= 25
    CUMUL_S = ([-TOTAL_SANS] + _cf_s[:25] if CUMUL_S_REEL
               else [-TOTAL_SANS + ECO_S_ANN * y for y in YEARS])
    CUMUL_A = ([-TOTAL_AVEC] + _cf_a[:25] if CUMUL_A_REEL
               else [-TOTAL_AVEC + eco_a_cumul * y for y in YEARS])


def render_html_for(data: dict) -> str:
    """HTML EXACT que le moteur legacy envoie à WeasyPrint pour ``data``.

    Point d'entrée des tests « document rendu » : aucune dépendance PDF, même
    ingestion et même sélection de gabarit que le chemin PDF.

    ── QJR163 (d) — CONCURRENCE : LIRE AVANT D'APPELER ─────────────────────
    Cette fonction et ``apply_quote_data`` sont PUBLIQUES et n'acquièrent PAS
    ``_RENDER_LOCK`` : seul ``generate_premium_pdf`` le prend. Or l'ingestion
    ÉCRIT les globales du module (ERR17) et le rendu les relit — deux appels
    CONCURRENTS à ``render_html_for`` (ou un appel pendant un
    ``generate_premium_pdf``) peuvent donc entrelacer les données de deux
    devis dans un même document.
    Elles restent sans verrou À DESSEIN : ``_render_premium_pdf`` les appelle
    DÉJÀ sous ``_RENDER_LOCK`` (un ``RLock`` réentrant le permettrait, mais
    l'imbrication resterait à la charge de l'appelant) et toute la suite de
    tests les appelle en séquence. **Tout nouvel appelant en contexte
    concurrent doit prendre ``_RENDER_LOCK`` lui-même**, ou passer par
    ``generate_premium_pdf``.
    """
    # Décision fondateur 08/10/2026 — un devis envoyé avant les
    # corrections du moteur garde ses formats d'origine (AMOT24/26/45).
    poser_regles_origine((data or {}).get("regles_calcul_origine"), avant_2710=(data or {}).get("regles_avant_2710"))
    # AGR312 — le moteur legacy ne sert JAMAIS un devis agricole en format à
    # options (pas d'onduleur) : le document complet est le renderer agricole
    # de 3 pages (``agricole/renderer``) ; s'il refuse un devis (repli NOMMÉ
    # du builder), le legacy rend la version courte d'une page.
    if ((data.get("mode_installation") or "").strip().lower() == "agricole"
            and data.get("pdf_mode", "full") != "onepage"):
        data = {**data, "pdf_mode": "onepage"}
    with format_langue(data):  # AMOT101 — nombres C&I EN
        apply_quote_data(data)
        if data.get("pdf_mode", "full") == "onepage":
            # QJR124 — plus de re-filtrage ici : ``builder`` filtre les accessoires
            # Huawei orphelins EN AMONT, avant de figer ``totaux_all``. Retirer une
            # ligne au rendu la laissait dans le Total TTC imprimé juste dessous.
            # QJR162 (b) — ACCÈS DUR. ``data.get("all_items", [])`` était un défaut
            # SILENCIEUX à liste vide alors que le même appel exige
            # ``data["sans_items"]`` en dur : une charge utile privée d'``all_items``
            # mais porteuse de ``totaux_all`` produisait un tableau d'équipements
            # VIDE sous un Total TTC complet.
            return _onepage_html_qui_tient(ci_installation.lignes_client(_esc_items(data["all_items"]), data))
        return build_html()


#: QJR161 — nombre maximum de passes de mesure. Chaque passe compose la page,
#: donc on borne le coût ; la première correction est déjà dimensionnée par la
#: mesure (dépassement ÷ hauteur de ligne). AMOT20 — une passe de plus : la
#: première correction peut être la troncature déclarée de la note/clauses.
_ONEPAGE_PASSES = 4


def _onepage_html_qui_tient(items):
    """QJR161 — le une-page dont le bloc de totaux EST composé dans la zone
    visible.

    Le gabarit n'a AUCUNE borne haute (``n_items > 12`` ⇒ table compacte, et
    rien au-delà) tandis que ``.page`` et la zone de contenu sont en
    ``overflow:hidden`` : un devis dense faisait DISPARAÎTRE son propre Total
    TTC, et le PDF faisait toujours 1 page — le module le dit lui-même. On
    MESURE donc le rendu et, s'il déborde, on retire des lignes d'équipement
    en le DÉCLARANT (les totaux restent ceux du devis entier). Sans WeasyPrint,
    la mesure est impossible : le document reste EXACTEMENT celui d'aujourd'hui.
    """
    global ONEPAGE_TEXTES_TRONQUES
    from .legacy_onepage import build_html_onepage  # SPL168 — import local (cycle)
    lignes = list(items or [])
    tronquees = 0
    ONEPAGE_TEXTES_TRONQUES = False
    try:
        html = build_html_onepage(lignes, tronquees)
        for _ in range(_ONEPAGE_PASSES):
            mesure = _mesure_onepage(html)
            if mesure is None:
                return html
            depassement, hauteur_ligne = mesure
            if depassement <= 0:
                return html
            # AMOT20 — d'abord la note et les clauses (textes longs) :
            # tronquées au mot avec renvoi DÉCLARÉ, jamais effacées en silence.
            if not ONEPAGE_TEXTES_TRONQUES and (NOTE_CLIENT or CLAUSES_CGV):
                ONEPAGE_TEXTES_TRONQUES = True
                html = build_html_onepage(lignes, tronquees)
                continue
            if len(lignes) <= 1:
                return html
            a_retirer = 1
            if hauteur_ligne > 0:
                a_retirer = max(1, int(depassement // hauteur_ligne) + 1)
            a_retirer = min(a_retirer, len(lignes) - 1)
            lignes = lignes[:-a_retirer]
            tronquees += a_retirer
            html = build_html_onepage(lignes, tronquees)
        return html
    finally:
        ONEPAGE_TEXTES_TRONQUES = False


def _render_premium_pdf(data: dict, out_path) -> str:
    out_path = Path(out_path)
    html = render_html_for(data)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                     mode="w", encoding="utf-8") as tf:
        tf.write(html)
        tmp = tf.name

    _render_pdf_weasyprint(html, str(out_path))
    Path(tmp).unlink(missing_ok=True)

    return str(out_path)


#: SPL168 — ré-export pour d'autres propriétaires (test devis
#: test_agr302_onepage_agricole_formats : ``build_html_onepage``) des noms
#: déplacés dans ``legacy_onepage``, servis à la demande (PEP 562) — jamais par
#: un import en tête de module (cycle legacy_onepage → generate_devis_premium).
#: SPL169 — liste étendue aux noms déplacés dans ``legacy_etude`` que lisent les
#: tests devis test_qjr115_production_unique, test_qjr159_garde_optimum_complete,
#: test_qjr_optimum_publie et test_offgrid_hors_reseau.
_REEXPORTS_LEGACY = {
    "build_html_onepage": "legacy_onepage",
    "TOLERANCE_CAPACITE_KWH": "legacy_etude",
    "_bankable_block_html": "legacy_etude",
    "_bankable_concorde_avec_la_page": "legacy_etude",
    "_bankable_decrit_ce_champ": "legacy_etude",
    "_branche_nommee": "legacy_etude",
    "_branche_phrase": "legacy_etude",
    "_config_identifiante": "legacy_etude",
    "_decrit": "legacy_etude",
    "_falaise_context": "legacy_etude",
    "_part_glitch_pct": "legacy_etude",
    "_phrase_methode_etude": "legacy_etude",
}


def __getattr__(nom):
    module = _REEXPORTS_LEGACY.get(nom)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {nom!r}")
    from importlib import import_module
    return getattr(import_module(f"{__package__}.{module}"), nom)
