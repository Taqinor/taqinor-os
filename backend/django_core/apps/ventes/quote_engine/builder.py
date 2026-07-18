"""Glue between an OS Devis and the vendored premium PDF generator.

Builds the data dict that ``generate_premium_pdf`` expects from a real OS quote,
computes the ROI numbers on the fly (no stored fields), renders the 3-page
premium PDF and stores it in MinIO under the same key scheme the old engine used
so the existing download endpoint keeps working.

Nothing here writes new DB columns. Pipeline stages, document statuses, invoices
and orders are untouched.
"""
from __future__ import annotations

import logging
import re
import tempfile
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

_WATT_RE = re.compile(r"(\d{3,4})\s*(?:wc|w)\b", re.IGNORECASE)
# Repli SÛR quand une ligne panneau n'a aucune puissance lisible dans sa
# désignation ni dans le nom du produit lié : on prend le STANDARD du catalogue
# (710 W — « Panneau Canadien Solar 710W »/« Panneau Jinko 710W », cf.
# seed_catalogue + generate_devis_premium.watt_par_panneau), JAMAIS l'ancien 450
# obsolète. Le chemin normal lit la VRAIE puissance via _parse_watt(nom produit).
_DEFAULT_WATT = 710

# ── Conditions de paiement par mode d'installation (SOURCE UNIQUE) ──
# Décision propriétaire 2026-06-12. Tous les formats PDF ET l'échéancier
# devis → factures (acompte/tranches) lisent CE mapping ; plus aucun
# pourcentage de paiement en dur ailleurs. Agricole = défaut résidentiel
# (30/60/10) en attente d'un éventuel veto du fondateur.
PAYMENT_TERMS_BY_MODE = {
    "residentiel": {"acompte": 30, "materiel": 60, "solde": 10},
    "industriel": {"acompte": 50, "materiel": 40, "solde": 10},
    # QX43 — commercial : mêmes conditions que l'industriel (50/40/10), en
    # attente d'un éventuel veto du fondateur.
    "commercial": {"acompte": 50, "materiel": 40, "solde": 10},
    "agricole": {"acompte": 30, "materiel": 60, "solde": 10},
}

# Brand tokens from the simulator catalogue — longest/most specific first so
# 'Deyness' wins over its substring 'Deye'.
_BRAND_TOKENS = [
    "Canadien Solar", "Canadian Solar", "Deyness", "Jinko",
    "Huawei", "Deye", "Lithium", "Gel",
]


def _roof_photo_data_uri(devis) -> str:
    """QRES39 (fondateur, 2026-07-18) — visuel RÉEL de la toiture du client.

    Cherche parmi les pièces jointes du devis (``records.Attachment``, magasin
    MinIO existant — records est une app fondation, import direct autorisé) la
    plus récente IMAGE dont le nom évoque la toiture (toiture / calepinage /
    implantation / roof / panneaux) et la renvoie en data-URI : la page « Le
    détail de votre projet » remplace alors le schéma illustratif par la vraie
    toiture du client. '' si absente (repli schéma). Jamais bloquant, jamais
    plus de 6 Mo. Le vendeur n'a RIEN de nouveau à apprendre : il joint la
    photo/le plan au devis via le panneau de pièces jointes existant.
    """
    try:
        import base64
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import fetch_attachment
        ct = ContentType.objects.get(app_label='ventes', model='devis')
        keys = ('toiture', 'calepinage', 'implantation', 'roof', 'panneaux')
        att = None
        for a in (Attachment.objects
                  .filter(content_type=ct, object_id=devis.pk)
                  .order_by('-created_at')[:50]):
            if not (a.mime or '').startswith('image/'):
                continue
            if any(k in (a.filename or '').lower() for k in keys):
                att = a
                break
        if att is None:
            return ""
        data, err = fetch_attachment(att.file_key)
        if err or not data or len(data) > 6 * 1024 * 1024:
            return ""
        return (f"data:{att.mime};base64,"
                + base64.b64encode(data).decode())
    except Exception:
        return ""


def _parse_marque(*texts) -> str:
    """Extract the product brand from designation/product name (one-page badge)."""
    blob = " ".join(t for t in texts if t).lower()
    for brand in _BRAND_TOKENS:
        if brand.lower() in blob:
            return brand
    return ""


def _parse_watt(*texts) -> int | None:
    """Pull a panel wattage (e.g. '450W', '550 Wc') from any of the given strings."""
    for t in texts:
        if not t:
            continue
        m = _WATT_RE.search(str(t))
        if m:
            return int(m.group(1))
    return None


def _normalize_site_host(site: str) -> str:
    """SCA27 — forme d'AFFICHAGE d'un site tenant (comme le littéral fondateur
    ``exemple.ma``) : sans schéma, sans ``www.``, sans chemin ni slash final.

    ``https://www.helios.ma/`` → ``helios.ma``. Chaîne vide/None → '' (le moteur
    garde alors ses littéraux historiques). N'invente jamais de domaine.
    """
    s = (site or "").strip()
    if not s:
        return ""
    # Retire le schéma (http/https/…) puis un éventuel www.
    if "://" in s:
        s = s.split("://", 1)[1]
    if s.lower().startswith("www."):
        s = s[4:]
    # Garde uniquement l'hôte (coupe au premier / ? #).
    for sep in ("/", "?", "#"):
        if sep in s:
            s = s.split(sep, 1)[0]
    return s.strip().rstrip("/")


def _is_battery(designation: str) -> bool:
    return "batterie" in (designation or "").lower()


def _is_hybrid_inverter(designation: str) -> bool:
    d = (designation or "").lower()
    return "onduleur" in d and "hybride" in d


def _is_reseau_inverter(designation: str) -> bool:
    d = (designation or "").lower()
    return "onduleur" in d and ("réseau" in d or "reseau" in d or "injection" in d)


def _is_panel(designation: str, produit_nom: str = "") -> bool:
    blob = f"{designation} {produit_nom}".lower()
    return "panneau" in blob or "panneaux" in blob


def _is_inverter(designation: str) -> bool:
    return "onduleur" in (designation or "").lower()


def _is_smart_meter(designation: str) -> bool:
    return "smart meter" in (designation or "").lower()


def _is_wifi_dongle(designation: str) -> bool:
    d = (designation or "").lower()
    return "wifi" in d or "dongle" in d


def _quote_is_huawei(items) -> bool:
    """QF9 — True quand l'onduleur du devis est Huawei.

    Smart Meter + Clé Wifi (dongle) sont des accessoires Huawei propres à
    l'onduleur Huawei : ils ne doivent JAMAIS figurer sur un devis dont
    l'onduleur est d'une autre marque (ex. Deye). On lit la marque de l'onduleur
    (réseau ou hybride) via sa désignation, sa marque et le nom du produit lié.
    Sans onduleur identifiable → False (on n'affiche pas ces accessoires par
    défaut). Comportement conservateur : le moindre onduleur non-Huawei suffit à
    retirer les accessoires du document.
    """
    inverters = [it for it in items if _is_inverter(it.get("designation", ""))]
    if not inverters:
        return False
    huawei_seen = False
    for it in inverters:
        blob = (f"{it.get('designation', '')} {it.get('marque', '')} "
                f"{it.get('_produit_nom', '')}").lower()
        if "huawei" in blob:
            huawei_seen = True
        else:
            # Un onduleur non-Huawei dans le devis → pas d'accessoires Huawei.
            return False
    return huawei_seen


def _line_to_item(ligne, taux_tva: Decimal) -> dict:
    """Convert an OS LigneDevis (HT prices) into a premium item dict.

    Carries both HT and TTC unit prices (the PDFs show per-line HT with an
    HT → TVA → TTC totals block) plus the product's commercial sheet
    (brand, description lines, warranty) for rich rendering.

    Réforme TVA : le taux de la LIGNE prime quand il existe (10 % panneaux,
    20 % le reste) ; une ligne historique (taux NULL) garde le taux du devis —
    son rendu ne change pas d'un centime.
    """
    ligne_taux = getattr(ligne, "taux_tva", None)
    if ligne_taux is None:
        ligne_taux = taux_tva
    pu_ht = Decimal(ligne.prix_unitaire) * (Decimal(1) - Decimal(ligne.remise) / Decimal(100))
    pu_ttc = pu_ht * (Decimal(1) + Decimal(ligne_taux) / Decimal(100))
    produit = getattr(ligne, "produit", None)
    produit_nom = getattr(produit, "nom", "") or ""
    return {
        "designation": ligne.designation,
        "marque": (getattr(produit, "marque", "") or ""),
        "description": (getattr(produit, "description", "") or ""),
        "garantie": (getattr(produit, "garantie", "") or ""),
        "quantite": float(ligne.quantite),
        "prix_unit_ht": float(round(pu_ht, 2)),
        "prix_unit_ttc": float(round(pu_ttc, 2)),
        "taux_tva": float(ligne_taux),
        # XSAL14 — position d'affichage (0 par défaut) : sert à intercaler les
        # intertitres de section/notes au bon endroit dans la liste une-page.
        "ordre": getattr(ligne, "ordre", 0) or 0,
        "_produit_nom": produit_nom,
    }


# Whitelisted PDF format options (mirroring the simulator's payload). The
# defaults reproduce today's premium 3-page output exactly.
DEFAULT_PDF_OPTIONS = {
    'pdf_mode': 'full',        # 'full' (3 pages) | 'onepage' (1 page)
    'show_monthly': True,      # monthly-savings chart on page 2
    'devis_final': False,      # payment terms + RIB block on page 3
    'payment_mode': 'standard',  # 'standard' (30/60/10) | 'custom'
    'custom_acompte': None,    # MAD down-payment when payment_mode == 'custom'
    'include_etude': False,    # page Étude (industriel) — 4th premium page
    # ── Agricole (pompage) — toggleable persuasion sections (default on) ──
    'show_subsidy': True,          # FDA 30% subsidy block
    'show_fuel_comparison': True,  # solaire vs butane vs diesel + payback
    'show_environmental': True,    # CO₂ / fuel-avoided strip
    'show_schematic': True,        # system schematic on the study page
    'show_water_yield': True,      # water-delivered-per-month chart
    'current_fuel': None,          # 'butane' | 'diesel' | 'none' (else étude/default)
}


def clean_pdf_options(raw) -> dict:
    """Sanitize client-supplied options to the simulator's exact value space."""
    raw = raw or {}
    opts = dict(DEFAULT_PDF_OPTIONS)
    if raw.get('pdf_mode') in ('full', 'onepage'):
        opts['pdf_mode'] = raw['pdf_mode']
    if 'show_monthly' in raw:
        opts['show_monthly'] = bool(raw['show_monthly'])
    if 'devis_final' in raw:
        opts['devis_final'] = bool(raw['devis_final'])
    if 'include_etude' in raw:
        opts['include_etude'] = bool(raw['include_etude'])
    if raw.get('payment_mode') in ('standard', 'custom'):
        opts['payment_mode'] = raw['payment_mode']
    # Agricole toggles — booleans default True; current_fuel a small enum.
    for _flag in ('show_subsidy', 'show_fuel_comparison', 'show_environmental',
                  'show_schematic', 'show_water_yield'):
        if _flag in raw:
            opts[_flag] = bool(raw[_flag])
    if raw.get('current_fuel') in ('butane', 'diesel', 'none'):
        opts['current_fuel'] = raw['current_fuel']
    try:
        acompte = raw.get('custom_acompte')
        # ERR76 — never forward a negative acompte; the engine additionally
        # clamps it to the order total.
        opts['custom_acompte'] = max(0.0, float(acompte)) if acompte not in (None, '') else None
    except (TypeError, ValueError):
        opts['custom_acompte'] = None
    return opts


# ── QJ12 — Financing comparison block ──────────────────────────────────────
# Indicative figures only (no live bank API).  All amounts are MAD TTC.
#
# Green loan parameters (APPROXIMATIF — marché marocain 2026, à confirmer
# avec les banques partenaires). NEVER presented as confirmed prices.
#
# Tatwir Croissance Verte (CIH/BMCE/Attijariwafa — PME):
#   Taux: ~4–5 % an (HT), durée max 7 ans.
# CAM « Saquii Solaire » (Crédit Agricole du Maroc — pompage agricole):
#   QK3 correction — le pompage solaire est financé par l'offre CAM dédiée
#   « Saquii Solaire » (~5–6 % an, 10 ans, 1 an de différé), cumulable avec la
#   subvention FDA 30 %. Le pompage n'est PAS éligible à ISTIDAMA — d'où la
#   correction ci-dessous (ISTIDAMA retiré du bloc agricole).
#
# Residential / uncategorised fall back to a generic green-mortgage proxy
# (MCMA-style): ~6 % an, 10 ans.
_FINANCING_PROGRAMS = {
    "residentiel": {
        "nom": "Crédit vert résidentiel",
        "taux_annuel": 0.06,          # indicatif
        "duree_mois": 120,
        "programme_label": None,      # no specific named programme
    },
    "industriel": {
        "nom": "Tatwir Croissance Verte (PME)",
        "taux_annuel": 0.045,         # milieu fourchette 4–5 %
        "duree_mois": 84,             # 7 ans
        "programme_label": "Tatwir",
    },
    # QX43 — commercial : réutilise le programme PME industriel « Tatwir
    # Croissance Verte » (mêmes bénéficiaires PME/TPE) — aucun programme inventé,
    # sauf veto du fondateur.
    "commercial": {
        "nom": "Tatwir Croissance Verte (PME)",
        "taux_annuel": 0.045,         # milieu fourchette 4–5 %
        "duree_mois": 84,             # 7 ans
        "programme_label": "Tatwir",
    },
    "agricole": {
        "nom": "CAM « Saquii Solaire » (Crédit Agricole du Maroc)",
        "taux_annuel": 0.055,         # milieu fourchette 5–6 %
        "duree_mois": 120,            # 10 ans (1 an de différé)
        "programme_label": "Saquii Solaire",
    },
}
_DEFAULT_FINANCING_KEY = "residentiel"


def _monthly_loan_payment(principal: float, annual_rate: float, n_months: int) -> float:
    """Standard annuity formula.  annual_rate = 0.06 means 6 % per year.
    Returns 0 if inputs are degenerate.
    """
    if principal <= 0 or n_months <= 0:
        return 0.0
    if annual_rate <= 0:
        return round(principal / n_months, 2)
    r = annual_rate / 12
    factor = r * (1 + r) ** n_months / ((1 + r) ** n_months - 1)
    return round(principal * factor, 2)


def compute_financing_block(
    display_total: float,
    eco_s_ann: float,
    eco_a_ann: float,
    mode_installation: str = "residentiel",
) -> dict | None:
    """QJ12 — Build the indicative financing comparison block.

    Returns a dict to be embedded in build_quote_data output under the key
    ``financing``, or ``None`` when the total is zero / unknown (degrades cleanly
    — callers must handle None and omit the block).

    The block is PURELY INDICATIVE.  Every figure carries the flag
    ``indicatif=True``.  Never show buy prices or margins — the returned dict
    contains only TTC client-facing numbers.

    Structure:
        {
            indicatif: True,
            cash: {montant_ttc: float, label: str},
            credit: {
                mensualite: float,
                duree_mois: int,
                taux_annuel_pct: float,
                programme_nom: str,
                programme_label: str | None,
            },
            onee_comparison: {
                show: bool,           # mensualité < économie mensuelle ONEE
                message: str,         # French message if show=True
                eco_mensuelle_sans: float,
                eco_mensuelle_avec: float,
            },
            guidance_text: str | None,  # Tatwir / Saquii Solaire text or None
        }
    """
    if not display_total or display_total <= 0:
        return None

    key = mode_installation if mode_installation in _FINANCING_PROGRAMS else _DEFAULT_FINANCING_KEY
    prog = _FINANCING_PROGRAMS[key]

    mensualite = _monthly_loan_payment(
        display_total,
        prog["taux_annuel"],
        prog["duree_mois"],
    )

    # Monthly savings (use option-1 / sans-batterie as the reference for comparison)
    eco_mensuelle_sans = round(eco_s_ann / 12, 2) if eco_s_ann else 0.0
    eco_mensuelle_avec = round(eco_a_ann / 12, 2) if eco_a_ann else 0.0

    # "mensualité < économie ONEE mensuelle" — when the monthly payment is below
    # even the option-1 monthly savings, the system "pays for itself each month".
    onee_ref = eco_mensuelle_sans  # conservative reference (sans batterie)
    shows_comparison = mensualite > 0 and onee_ref > 0 and mensualite < onee_ref
    if shows_comparison:
        comparison_msg = (
            f"La mensualité indicative ({int(mensualite):,} MAD) est inférieure "
            f"à votre économie mensuelle estimée ({int(onee_ref):,} MAD) — "
            "l'installation se rembourse chaque mois."
        ).replace(',', ' ')
    else:
        comparison_msg = ""

    # Programme guidance text
    guidance = None
    if key == "industriel":
        guidance = (
            "Les PME et professionnels peuvent financer cette installation via "
            "Tatwir Croissance Verte (CIH, BMCE, Attijariwafa) — taux préférentiel "
            "réservé aux projets d'efficacité énergétique. Demandez à votre banque."
        )
    elif key == "agricole":
        # QK3 — le pompage solaire relève de l'offre CAM « Saquii Solaire »
        # (≈ 5–6 % an, 10 ans, 1 an de différé), cumulable avec la subvention
        # FDA 30 %. Le pompage n'est PAS éligible à ISTIDAMA.
        guidance = (
            "L'offre « Saquii Solaire » du Crédit Agricole du Maroc finance le "
            "pompage solaire (≈ 5–6 % an, 10 ans, 1 an de différé), cumulable "
            "avec la subvention FDA 30 %. Contactez votre agence CAM pour les "
            "conditions exactes."
        )

    return {
        "indicatif": True,
        "cash": {
            "montant_ttc": display_total,
            "label": "Paiement comptant (TTC)",
        },
        "credit": {
            "mensualite": mensualite,
            "duree_mois": prog["duree_mois"],
            "taux_annuel_pct": round(prog["taux_annuel"] * 100, 2),
            "programme_nom": prog["nom"],
            "programme_label": prog["programme_label"],
        },
        "onee_comparison": {
            "show": shows_comparison,
            "message": comparison_msg,
            "eco_mensuelle_sans": eco_mensuelle_sans,
            "eco_mensuelle_avec": eco_mensuelle_avec,
        },
        "guidance_text": guidance,
    }


def build_quote_data(devis, pdf_options=None) -> dict:
    """Build the dict consumed by generate_premium_pdf from a Devis instance."""
    from .pricing import calculate_savings_roi
    from .catalog import pick_default_battery

    client = devis.client
    taux_tva = devis.taux_tva or Decimal(20)
    lignes = list(devis.lignes.select_related("produit").all())

    # ── XSAL14 — Lignes de section/note : rendues HORS totaux, à part ─────────
    # Une ligne de section (intertitre) ou de note (texte sans prix) ne porte NI
    # produit NI prix : on la retire de ``lignes`` (elle ne peut pas devenir un
    # ``item`` — pas de prix) et on la surface ordonnée dans ``lignes_structure``.
    structure_lignes = [
        li for li in lignes
        if getattr(li, "type_ligne", "produit") != "produit"]
    lignes = [
        li for li in lignes
        if getattr(li, "type_ligne", "produit") == "produit"]

    # ── XSAL5 — Lignes optionnelles : rendues HORS totaux ────────────────────
    # Une ligne ``optionnelle`` (add-on non activé) n'entre NI dans le découpage
    # d'options NI dans les totaux : on la retire de ``lignes`` (donc de
    # ``items``) et on la surface à part dans ``options_proposees`` (bloc opt-in
    # client, jamais de prix d'achat/marge). Une ligne activée (optionnelle=False)
    # est déjà une ligne normale → chemin inchangé. Zéro option ⇒ octet-identique.
    option_lignes = [li for li in lignes if getattr(li, "optionnelle", False)]
    lignes = [li for li in lignes if not getattr(li, "optionnelle", False)]

    items = [_line_to_item(li, taux_tva) for li in lignes]
    # Mode « réforme » dès qu'une ligne porte son propre taux ; un devis
    # historique (toutes lignes NULL) reste rendu strictement comme avant.
    per_line_tva = any(getattr(li, "taux_tva", None) is not None for li in lignes)

    # ── Derive power from the panel line(s) ──────────────────────────────────
    nb_panneaux = 0
    watt = None
    for it in items:
        if _is_panel(it["designation"], it.get("_produit_nom", "")):
            nb_panneaux += int(round(it["quantite"]))
            watt = watt or _parse_watt(it["designation"], it.get("_produit_nom", ""))
    watt = watt or _DEFAULT_WATT

    # ── Split into the two options ───────────────────────────────────────────
    # Option 1 "Sans batterie": réseau/injection inverter, NO hybrid, NO battery.
    # Option 2 "Avec batterie": hybrid inverter + battery, NO réseau inverter.
    # HARD RULE: an option NEVER renders without an inverter — an option whose
    # equipment lacks one is dropped (single-option document); a quote with no
    # inverter at all cannot produce an option-based PDF at all.
    # Classification sur désignation ET nom du produit lié : une désignation
    # éditée à la main ne peut pas casser silencieusement le découpage.
    def _blob(it):
        return f"{it['designation']} {it.get('_produit_nom', '')}"

    sans_items = [
        it for it in items
        if not _is_battery(_blob(it)) and not _is_hybrid_inverter(_blob(it))
    ]
    avec_items = [
        it for it in items
        if not _is_reseau_inverter(_blob(it))
    ]

    # ── QF9 — Smart Meter + Clé Wifi (dongle) uniquement si onduleur Huawei ───
    # Ces accessoires sont propres à l'onduleur Huawei ; sur une option dont
    # l'onduleur n'est PAS Huawei (ex. onduleur hybride Deye), ils ne doivent
    # jamais apparaître, même si une ligne obsolète a été copiée à la main. On
    # évalue Huawei PAR option (l'onduleur réseau de « sans » peut être Huawei
    # alors que l'onduleur hybride de « avec » est Deye) et on retire les lignes
    # Smart Meter / Wifi de l'option non-Huawei.
    def _drop_huawei_accessories(rows):
        if _quote_is_huawei(rows):
            return rows
        return [it for it in rows
                if not _is_smart_meter(it.get("designation", ""))
                and not _is_wifi_dongle(it.get("designation", ""))]

    sans_items = _drop_huawei_accessories(sans_items)
    avec_items = _drop_huawei_accessories(avec_items)

    def _has_qty(rows, pred):
        return any(pred(_blob(r)) and r["quantite"] > 0 for r in rows)

    has_reseau = _has_qty(sans_items, _is_reseau_inverter)
    has_hybride = _has_qty(avec_items, _is_hybrid_inverter)
    has_batterie = _has_qty(avec_items, _is_battery)

    # Power: prefer real panels; otherwise estimate from the equipment total.
    if nb_panneaux > 0:
        puissance_kwc = round(nb_panneaux * watt / 1000, 2)
    else:
        _approx = float(sum(r["quantite"] * r["prix_unit_ttc"] for r in sans_items))
        puissance_kwc = max(3.0, round(_approx / 12000, 2))
        nb_panneaux = max(1, round(puissance_kwc * 1000 / watt))

    # Battery synthesis only at residential scale (≤ 15 kWc) where a single
    # default module is sensible — never a token battery on a large plant.
    if has_hybride and not has_batterie and puissance_kwc <= 15:
        synth = dict(pick_default_battery())
        # Une batterie n'est jamais un panneau : 20 % en mode réforme,
        # taux du devis pour les devis historiques.
        synth_taux = 20.0 if per_line_tva else float(taux_tva)
        synth.setdefault("taux_tva", synth_taux)
        synth.setdefault(
            "prix_unit_ht",
            round(synth.get("prix_unit_ttc", 0) / (1 + synth_taux / 100), 2))
        avec_items = avec_items + [synth]
        has_batterie = True

    opts = clean_pdf_options(pdf_options)
    mode = devis.mode_installation or ""
    # Mode agricole : le format à options n'a pas de sens (pas d'onduleur) —
    # la demande « premium » dégrade proprement vers le format une page.
    pdf_mode = opts['pdf_mode']
    if mode == "agricole" and pdf_mode == "full":
        pdf_mode = "onepage"

    sans_ok = has_reseau
    avec_ok = has_hybride and has_batterie
    # Deux VRAIES options (avant tout repli) — pilote la règle d'intégrité :
    # total d'affichage = option 1, et le une-page ne mélange jamais.
    deux_options = sans_ok and avec_ok
    if not sans_ok and not avec_ok and pdf_mode == "full":
        # RÈGLE DURE : une option ne se rend JAMAIS sans onduleur. Un devis
        # sans aucun onduleur ne peut pas produire le document à options.
        raise ValueError(
            f"Devis {devis.reference} : aucune option ne contient d'onduleur — "
            "génération du PDF à options refusée (règle de sécurité).")
    if not sans_ok and not avec_ok:
        # Format une page (liste simple) : pas d'options — valeurs neutres.
        sans_ok = True

    # ── QF6 — respecter le choix avec/sans-batterie STOCKÉ par le vendeur ─────
    # L'écran générateur persiste le scénario choisi dans etude_params
    # ('scenario' = « Sans batterie » / « Avec batterie » / « Les deux (Sans +
    # Avec) ») et l'option recommandée ('recommended_option'). On LIT ce choix
    # d'abord ; l'inférence depuis les lignes n'est qu'un REPLI quand rien n'est
    # stocké. Un choix stocké ne peut jamais être satisfait au-delà de ce que
    # l'équipement permet : « Avec » sans onduleur hybride+batterie ne peut pas
    # rendre l'option avec — dans ce cas on retombe sur ce qui est disponible.
    _stored_choice = (devis.etude_params or {}).get('scenario')
    _valid_choices = {
        'Sans batterie', 'Avec batterie', 'Les deux (Sans + Avec)'}
    if _stored_choice in _valid_choices and (sans_ok or avec_ok):
        if _stored_choice == 'Les deux (Sans + Avec)' and sans_ok and avec_ok:
            scenario = 'Les deux (Sans + Avec)'
        elif _stored_choice == 'Sans batterie' and sans_ok:
            scenario = 'Sans batterie'
        elif _stored_choice == 'Avec batterie' and avec_ok:
            scenario = 'Avec batterie'
        elif sans_ok and avec_ok:
            scenario = 'Les deux (Sans + Avec)'
        elif avec_ok:
            scenario = 'Avec batterie'
        else:
            scenario = 'Sans batterie'
        # Option recommandée stockée si valide, sinon dérivée du scénario.
        _stored_reco = (devis.etude_params or {}).get('recommended_option')
        if _stored_reco in ('Sans batterie', 'Avec batterie'):
            recommended = _stored_reco
        elif scenario == 'Sans batterie':
            recommended = 'Sans batterie'
        else:
            recommended = 'Avec batterie'
    elif sans_ok and avec_ok:
        scenario = "Les deux (Sans + Avec)"
        recommended = "Avec batterie"
    elif sans_ok:
        scenario = "Sans batterie"
        recommended = "Sans batterie"
    else:
        scenario = "Avec batterie"
        recommended = "Avec batterie"

    # QF6 — le scénario STOCKÉ « Sans/Avec » restreint le document à une seule
    # option même si les deux existent dans les lignes. On aligne donc les
    # drapeaux d'option et le mélange une-page sur ce scénario (SANS = réseau
    # seul, sans batterie ni onduleur hybride ; AVEC = hybride + batterie, sans
    # onduleur réseau). Comportement « les deux » et repli inchangés.
    if scenario == 'Sans batterie':
        avec_ok = False
        deux_options = False
    elif scenario == 'Avec batterie':
        sans_ok = False
        deux_options = False

    # ── Canonical totals: ONE computation from the stored HT lines ───────────
    # Every page must display these exact values — never re-derive.
    discount_pct = float(devis.remise_globale or 0)
    tva_pct = float(taux_tva)

    def _canonical_totaux(rows):
        """Chaîne HT → remise → TVA (par taux) → TTC, calculée UNE fois.

        Un seul taux présent (tous les devis historiques) : calcul strictement
        identique à l'ancien. Taux mixtes (réforme 10/20) : la remise globale
        s'applique proportionnellement à chaque ligne, donc chaque panier de
        taux se réduit du même % ; les paniers nets sont réconciliés au
        centime avec le HT net global avant de calculer chaque TVA.
        """
        ht_brut = round(sum(r["quantite"] * r["prix_unit_ht"] for r in rows), 2)
        remise = round(ht_brut * discount_pct / 100, 2) if discount_pct > 0 else 0.0
        ht_net = round(ht_brut - remise, 2)

        buckets_brut = {}
        for r in rows:
            rate = float(r.get("taux_tva", tva_pct))
            buckets_brut[rate] = (
                buckets_brut.get(rate, 0.0) + r["quantite"] * r["prix_unit_ht"])

        if len(buckets_brut) <= 1:
            rate = next(iter(buckets_brut), tva_pct)
            tva_amt = round(ht_net * rate / 100, 2)
            tva_par_taux = [{"taux": rate, "montant": tva_amt, "ht_net": ht_net}]
        else:
            rates = sorted(buckets_brut)
            nets = {
                rate: round(buckets_brut[rate] * (1 - discount_pct / 100), 2)
                for rate in rates
            }
            residu = round(ht_net - sum(nets.values()), 2)
            nets[rates[-1]] = round(nets[rates[-1]] + residu, 2)
            tva_par_taux = [
                {"taux": rate, "montant": round(nets[rate] * rate / 100, 2),
                 "ht_net": nets[rate]}
                for rate in rates
            ]
            tva_amt = round(sum(b["montant"] for b in tva_par_taux), 2)

        ttc_exact = round(ht_net + tva_amt, 2)
        ttc = round(ttc_exact)
        if len(buckets_brut) <= 1:
            _rate0 = next(iter(buckets_brut), tva_pct)
            ttc_avant = round(ht_brut * (1 + _rate0 / 100))  # = calcul historique
        else:
            ttc_avant = round(sum(
                buckets_brut[rate] * (1 + rate / 100) for rate in buckets_brut))
        return {"ht_brut": ht_brut, "remise": remise, "ht_net": ht_net,
                "tva": tva_amt, "tva_par_taux": tva_par_taux,
                "ttc": ttc, "ttc_exact": ttc_exact, "ttc_avant": ttc_avant}

    totaux_sans = _canonical_totaux(sans_items)
    totaux_avec = _canonical_totaux(avec_items)
    # Une page : option 1 seule quand deux vraies options ; l'option choisie
    # quand le scénario stocké restreint à une seule (QF6) ; sinon tout le devis.
    if deux_options:
        _all_rows = sans_items
    elif scenario == 'Avec batterie' and avec_ok:
        _all_rows = avec_items
    elif scenario == 'Sans batterie' and has_reseau:
        _all_rows = sans_items
    else:
        _all_rows = items
    totaux_all = _canonical_totaux(_all_rows)

    # ── Total d'AFFICHAGE canonique (liste des devis) ────────────────────────
    # Deux options → total de l'option 1 (remise incluse), jamais la somme
    # mensongère des deux. Mono-option → le total de cette option ; devis
    # libre/pompage → le total complet. Identique au PDF au dirham près.
    if deux_options:
        display_total = totaux_sans["ttc"]
        nb_options = 2
    elif avec_ok:
        display_total = totaux_avec["ttc"]
        nb_options = 1
    elif has_reseau:
        display_total = totaux_sans["ttc"]
        nb_options = 1
    else:
        display_total = totaux_all["ttc"]
        nb_options = 1
    total_sans = totaux_sans["ttc"]
    total_avec = totaux_avec["ttc"]
    total_sans_before = totaux_sans["ttc_avant"]
    total_avec_before = totaux_avec["ttc_avant"]

    # ── Q5 — Toiture 3D : figures du layout FINALISÉ (additif, GARDÉ) ─────────
    # Quand le devis porte un layout 3D finalisé (Devis.roof_layout), ses
    # kWc / production / économies réels remplacent l'estimation — UNIQUEMENT
    # quand le layout est présent. Sans layout, RIEN ici ne s'exécute et la
    # sortie reste byte-identique (back-compat, règle #4). On n'écrase jamais
    # une étude déjà saisie : on ne fait que COMPLÉTER les figures manquantes.
    roof_layout = getattr(devis, "roof_layout", None)
    if roof_layout:
        _res = (roof_layout.get("result") or {}) if isinstance(
            roof_layout, dict) else {}
        _kwc = _res.get("kwc")
        if _kwc:
            puissance_kwc = round(float(_kwc), 2)
        _stored = dict(devis.etude_params or {})
        if _res.get("annualKwh") and not _stored.get("production_annuelle"):
            _stored["production_annuelle"] = int(_res["annualKwh"])
        if _res.get("savings") and not _stored.get("economies_annuelles"):
            _stored["economies_annuelles"] = int(_res["savings"])
        devis_etude_override = _stored
    else:
        devis_etude_override = devis.etude_params or {}

    # ── Canonical performance figures: ONE source of truth ───────────────────
    # When the quote carries a stored étude (industrial), its consumption-driven
    # production/savings are canonical; payback and prix/kWc are recomputed from
    # the canonical totals so edited lines can never desynchronize the document.
    etude = dict(devis_etude_override or {})
    # Agricole : le carburant de référence du comparatif peut être forcé par
    # l'option PDF (sinon l'étude / le défaut « butane » s'applique).
    if opts.get('current_fuel'):
        etude['current_fuel'] = opts['current_fuel']
    # QJ13 — tariff / self-consumption overrides from etude_params.
    # Resolves: tarif_kwh_override → tranches_override → utility name → fallback.
    # All are seller-editable via etude_params; nothing is fabricated from thin air.
    _tarif_kwh_override = etude.get("tarif_kwh")  # explicit flat price (seller set)
    _tranches_override = etude.get("tarif_tranches")  # custom schedule [[ceil, price], …]
    _utility = etude.get("distributeur")  # "onee" | "lydec" | "redal"
    _conso_annuelle = etude.get("conso_annuelle")  # from industrial étude if available
    # Autoconsommation overrides (seller/study can refine these)
    _autoconso_sans = float(etude.get("autoconso_sans") or 0) or None
    _autoconso_avec = float(etude.get("autoconso_avec") or 0) or None
    from .pricing import AUTOCONSO_SANS, AUTOCONSO_AVEC
    # DC2 — repères ROI de la société (source unique CompanyProfile via le
    # sélecteur parametres) : productible annuel et tarif ONEE de repli. Le
    # productible pilote la production annuelle et donc le ROI, même à l'écran ;
    # le tarif ONEE ne s'applique qu'en dernier repli (aucune donnée de conso),
    # de sorte que le simulateur et le PDF ne divergent plus.
    # QX7c/QX38 — ville du client depuis le lead lié (lead.ville). Accès attribut
    # sur l'instance liée (aucun import crm.models) ; vide si pas de lead/ville.
    # Sert au productible PVGIS par ville (QX38) ET à la ligne meta du PDF (QX7c).
    _client_city = ""
    try:
        _lead = getattr(devis, "lead", None)
        if _lead is not None:
            _client_city = (getattr(_lead, "ville", "") or "").strip()
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus
        _client_city = ""

    _tariff = {}
    try:
        from apps.parametres.selectors import tariff_for
        _tariff = tariff_for(getattr(devis, "company", None))
    except Exception:  # noqa: BLE001 — un PDF/une liste ne casse jamais ici
        _tariff = {}
    # ── QX38 — productible CANONIQUE (source unique PVGIS par ville) ──────────
    # CompanyProfile.productible_kwh_kwc devient un OVERRIDE éditable, pas un
    # modèle physique concurrent : quand il vaut le défaut historique 1600, on
    # lit le productible PVGIS de la ville du lead/devis (aligné écran/PDF/web).
    # Une valeur société ≠ 1600 (réglage explicite) prime. Repli sûr : sur toute
    # erreur, on garde l'ancien productible du tarif (comportement inchangé).
    _co_productible = _tariff.get("productible_kwh_kwc") or None
    try:
        from .productible import productible_for_city
        _productible = productible_for_city(
            _client_city, override=_co_productible)
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus
        _productible = _co_productible
    _onee_tarif = _tariff.get("onee_tarif_kwh") or None
    roi_kwargs = dict(
        conso_annuelle_kwh=float(_conso_annuelle) if _conso_annuelle else None,
        utility=_utility or None,
        tarif_kwh_override=float(_tarif_kwh_override) if _tarif_kwh_override else None,
        tranches_override=_tranches_override or None,
        autoconso_sans=_autoconso_sans if _autoconso_sans else AUTOCONSO_SANS,
        autoconso_avec=_autoconso_avec if _autoconso_avec else AUTOCONSO_AVEC,
        productible=_productible,
        fallback_tarif_kwh=_onee_tarif,
    )
    roi = calculate_savings_roi(puissance_kwc, total_sans, total_avec, **roi_kwargs)
    if etude.get("production_annuelle"):
        roi["prod_kwh"] = int(etude["production_annuelle"])
        if etude.get("economies_annuelles"):
            eco = int(etude["economies_annuelles"])
            roi["eco_s_ann"] = eco
            roi["eco_a_ann"] = eco
            roi["eco_a_cumul"] = eco
            _ref_total = total_sans if sans_ok else total_avec
            roi["roi_s"] = round(_ref_total / eco, 1) if eco > 0 else 0.0
            roi["roi_a"] = roi["roi_s"]
            _sf = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116,
                   0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
            roi["eco_s_monthly"] = [round(eco * f) for f in _sf]
            roi["eco_a_monthly"] = list(roi["eco_s_monthly"])
        # L'étude rendue reprend les valeurs canoniques (jamais deux versions)
        etude["production_annuelle"] = roi["prod_kwh"]
        _ref_total = total_sans if sans_ok else total_avec
        if etude.get("economies_annuelles"):
            etude["economies_annuelles"] = roi["eco_s_ann"]
            etude["payback"] = roi["roi_s"]
        if puissance_kwc > 0:
            etude["prix_kwc"] = round(_ref_total / puissance_kwc)

    # ── QF2 — modèle « deux factures » (économies réelles, par tranche) ──────
    # Le modèle effectivement utilisé pour les économies affichées :
    #   'factures'   — facture_sans − facture_avec, par tranche (données réelles)
    #   'etude'      — économies imposées par l'étude stockée (bloc ci-dessus)
    #   'estimation' — ancienne approximation production × autoconso × prix,
    #                  toujours étiquetée comme estimation (aucun chiffre inventé).
    savings_model = roi.get("savings_model", "estimation")
    if etude.get("production_annuelle") and etude.get("economies_annuelles"):
        savings_model = "etude"
    if savings_model == "factures":
        # Persistance dans les paramètres d'étude RENDUS : la page étude et la
        # proposition web reprennent exactement les mêmes chiffres (une seule
        # source). Rendu seulement — aucun statut, aucune écriture en base.
        etude["facture_annuelle_sans_solaire"] = roi["facture_sans"]
        etude["facture_annuelle_avec_solaire_opt1"] = roi["facture_avec_s"]
        etude["facture_annuelle_avec_solaire_opt2"] = roi["facture_avec_a"]
        etude["economie_reelle_opt1"] = roi["eco_s_ann"]
        etude["economie_reelle_opt2"] = roi["eco_a_ann"]

    # ── QF3 — bloc « Comment nous calculons vos économies » ──────────────────
    # Méthode + exemple chiffré compact, calculés UNE fois ici : le PDF premium
    # et la proposition web (/proposal) rendent EXACTEMENT le même bloc.
    def _fr_int(n):
        return f"{int(round(n)):,}".replace(",", " ")

    _sm_eco_ref = roi["eco_a_ann"] if scenario == "Avec batterie" else roi["eco_s_ann"]
    if savings_model == "factures":
        _sm_avec = (roi["facture_avec_a"] if scenario == "Avec batterie"
                    else roi["facture_avec_s"])
        savings_method = {
            "model": "factures",
            "facture_actuelle": roi["facture_sans"],
            "facture_avec_solaire": _sm_avec,
            "economie": roi["facture_sans"] - _sm_avec,
            "approximatif": bool(roi.get("factures_approximatif")),
            "ligne_methode": (
                "Chaque kWh est valorisé au prix de SA tranche (barème "
                "progressif du distributeur) : facture actuelle moins facture "
                "résiduelle après autoconsommation — jamais un prix moyen "
                "inventé."),
            # QRES40 — MAD partout (le document n'emploie jamais « DH » :
            # une seule unité monétaire, aucune hésitation possible).
            "exemple": (
                f"Facture actuelle ≈ {_fr_int(roi['facture_sans'])} MAD/an → "
                f"avec solaire ≈ {_fr_int(_sm_avec)} MAD/an → économie ≈ "
                f"{_fr_int(roi['facture_sans'] - _sm_avec)} MAD/an"),
        }
    elif savings_model == "etude":
        savings_method = {
            "model": "etude",
            "facture_actuelle": None,
            "facture_avec_solaire": None,
            "economie": _sm_eco_ref,
            "approximatif": False,
            "ligne_methode": (
                "Économies issues de l'étude de consommation enregistrée avec "
                "ce devis (production et économies calculées sur votre profil "
                "réel)."),
            "exemple": None,
        }
    else:
        savings_method = {
            "model": "estimation",
            "facture_actuelle": None,
            "facture_avec_solaire": None,
            "economie": _sm_eco_ref,
            "approximatif": True,
            "ligne_methode": (
                "Estimation : production annuelle × part autoconsommée × tarif "
                "kWh (loi 82-21 : seul l'autoconsommé est valorisé — détail "
                "dans nos hypothèses). Fournissez une facture réelle pour un "
                "calcul par tranche exact."),
            "exemple": None,
        }

    # ── QK4 — « Nos hypothèses » : transparence des hypothèses d'économies ────
    # Surface côté client les hypothèses derrière les économies : tarif MAD/kWh
    # utilisé, source du barème (ONEE/Lydec/Redal — approximatif pour les
    # distributeurs privés), autoconsommation d'abord (loi 82-21, injection OFF —
    # rachat BT résidentiel différé par l'ANRE), base de production/dégradation.
    # Toutes les valeurs viennent de roi/etude (une source) ; dégrade proprement.
    _util_labels = {"onee": "ONEE", "lydec": "Lydec", "redal": "Redal"}
    _util_key = (str(_utility).lower() if _utility else "")
    _util_name = _util_labels.get(_util_key, "")
    _util_approx = _util_key in ("lydec", "redal")
    _tarif_val = roi.get("tarif_kwh")
    _tarif_txt = (f"{_tarif_val:.2f}".replace(".", ",")
                  if isinstance(_tarif_val, (int, float)) else None)
    _prod_factor = roi.get("productible")
    hypotheses = []
    if savings_model == "factures" and _util_name:
        hypotheses.append(
            f"Tarif électricité : barème {_util_name} par tranche"
            + (" (approximatif — distributeur privé)" if _util_approx
               else " (barème public)"))
    elif _tarif_txt:
        # QRES16 (fondateur, 2026-07-18) — ne JAMAIS présenter le défaut
        # interne du simulateur comme un « tarif retenu » réfléchi : le 1,75
        # historique (constants.KWH_PRICE, marqué « ne pas afficher dans les
        # PDF/UI ») s'imprimait tel quel via ce bloc et fragilisait la
        # confiance. Un tarif ÉGAL au défaut est présenté comme référence de
        # calcul avec le chemin vers l'exactitude (facture → barème par
        # tranches) ; un tarif réellement personnalisé reste affiché comme
        # tel ; le cas barème (« factures ») garde sa ligne dédiée ci-dessus.
        # QRES55 (fondateur, 2026-07-18) — le tarif de référence interne ne
        # s'affiche JAMAIS en chiffres sur le document (ni « 1,75 » ni un
        # autre) : la ligne dit la MÉTHODE et le chemin vers l'exactitude.
        # Seul un tarif réellement personnalisé (saisi pour CE devis, différent
        # du défaut) reste affiché, car c'est la donnée du client.
        from .constants import KWH_PRICE as _KWH_DEFAULT
        if _util_name:
            hypotheses.append(
                f"Tarif électricité retenu : {_tarif_txt} MAD/kWh "
                f"({_util_name})")
        elif abs(float(_tarif_val) - float(_KWH_DEFAULT)) < 1e-6:
            hypotheses.append(
                "Tarif électricité : référence résidentielle prudente — "
                "transmettez une facture récente et nous recalculons vos "
                "économies par tranches, sur votre barème exact.")
        else:
            hypotheses.append(
                f"Tarif électricité : {_tarif_txt} MAD/kWh, personnalisé "
                "pour votre profil de consommation — un calcul par tranches "
                "sur facture réelle reste possible.")
    # QRES55 — formulations COMPACTES (le fondateur veut la même transparence
    # « en plus petit ») : une idée, une ligne courte.
    hypotheses.append(
        "Loi 82-21 : seuls les kWh autoconsommés réduisent la facture — le "
        "surplus injecté n'est pas rémunéré (plafond d'injection 20 % "
        "intégré, rachat BT non publié).")
    if _prod_factor:
        # QRES54 — production NETTE affichée : pertes système de 14 % déduites
        # (PRODUCTION_DERATE), la même que TOUS les calculs du document.
        from .pricing import PRODUCTION_DERATE as _DERATE
        hypotheses.append(
            f"Production estimée : ≈ {_fr_int(_prod_factor * _DERATE)} "
            "kWh par kWc et par an, pertes système de 14 % déduites.")
    _ac_s = roi.get("autoconso_sans")
    _ac_a = roi.get("autoconso_avec")
    if _ac_s and _ac_a:
        hypotheses.append(
            f"Autoconsommation retenue : {int(round(_ac_s * 100))} % sans "
            f"batterie · {int(round(_ac_a * 100))} % avec batterie.")
    # QX39 — hypothèses du cashflow 25 ans (dégradation/escalade/batterie),
    # documentées et rendues sur le PDF/la proposition. Le payback vient
    # désormais du croisement du cumul à zéro, pas d'un ratio année-1.
    # QRES1 — dédoublonnage SÉMANTIQUE : le bloc cumulait trois formulations de
    # la loi 82-21 (la sienne, celle de savings_method, celle du cashflow) —
    # une idée n'apparaît qu'une fois, le mur de texte de la page 3 disparaît.
    _cf_assum = roi.get("cashflow_assumptions") or {}
    for _n in (_cf_assum.get("notes") or []):
        _n = str(_n).strip()
        if not _n or _n in hypotheses:
            continue
        if "82-21" in _n and any("82-21" in h for h in hypotheses):
            continue
        hypotheses.append(_n)
    # QRES59 — « toute hausse vous profite » ne se dit qu'UNE fois (la note
    # cashflow ci-dessus) : la ligne finale reste sobre.
    hypotheses.append("Estimations non contractuelles.")
    hypotheses_block = {
        "titre": "Nos hypothèses",
        "items": hypotheses,
        "tarif_kwh": _tarif_val,
        "tarif_kwh_txt": _tarif_txt,
        "tranche_source": _util_name or None,
        "tranche_approximatif": bool(_util_approx),
        "autoconso_first": True,
        "productible_kwh_kwc": (int(round(_prod_factor)) if _prod_factor
                                else None),
    }

    # ONEE monthly bill proxy (bars sit above the savings curves): full-price bill
    # ≈ Option-2 monthly savings / 0.85 autoconsumption.
    factures_mensuelles = [round(v / 0.85) for v in roi["eco_a_monthly"]]

    client_name = f"{(client.prenom or '').strip()} {(client.nom or '').strip()}".strip()

    # Liste d'articles du format UNE PAGE. RÈGLE D'INTÉGRITÉ : une facture ne
    # mélange JAMAIS deux options — un devis à deux vraies options (réseau ET
    # hybride+batterie) rend l'OPTION 1 (sans batterie) seule, avec une
    # mention discrète vers la proposition complète. Devis mono-option ou sans
    # options (pompage, liste libre) : toutes les lignes, comme avant.
    # QF6 — le scénario choisi pilote aussi la liste une-page : « Sans » → les
    # lignes de l'option sans batterie, « Avec » → celles de l'option avec
    # batterie, « Les deux » → option 1 seule (jamais deux onduleurs), sinon
    # tout le devis (liste libre/pompage).
    if deux_options:
        onepage_source = sans_items
    elif scenario == 'Avec batterie' and avec_ok:
        onepage_source = avec_items
    elif scenario == 'Sans batterie' and has_reseau:
        onepage_source = sans_items
    else:
        onepage_source = items
    onepage_note_batterie = deux_options
    all_items = [
        {
            **{k: v for k, v in it.items() if k != "_produit_nom"},
            "marque": it["marque"] or _parse_marque(
                it["designation"], it.get("_produit_nom", "")),
        }
        for it in onepage_source if it["quantite"] > 0
    ]

    # Strip the internal helper key before handing items to the generator.
    for rows in (sans_items, avec_items):
        for r in rows:
            r.pop("_produit_nom", None)

    inst_type = {
        "residentiel": "Résidentielle",
        # QX43 — industriel et commercial séparés (le libellé industriel ne dit
        # plus « / Commerciale »).
        "industriel": "Industrielle",
        "commercial": "Commerciale",
        "agricole": "Agricole",
    }.get(mode, "Résidentielle")

    # Modes industriel ET commercial (QX43) : l'étude fait partie du document
    # (page dédiée incluse d'office quand des données d'étude existent).
    include_etude = opts['include_etude'] or (
        mode in ("industriel", "commercial") and bool(etude))

    # Puces des cartes d'option de la page 1 — générées depuis l'équipement
    # RÉEL de chaque option, jamais du texte boilerplate.
    def _bullets(rows):
        out = []
        panels = [r for r in rows if _is_panel(r["designation"]) and r["quantite"] > 0]
        if panels:
            n = int(sum(r["quantite"] for r in panels))
            out.append(f"{n} panneaux {watt} W")
        for r in rows:
            if r["quantite"] <= 0:
                continue
            d = r["designation"]
            if _is_reseau_inverter(d) or _is_hybrid_inverter(d):
                q = int(r["quantite"]) if r["quantite"] == int(r["quantite"]) else r["quantite"]
                out.append(f"{q} × {d}" if q > 1 else d)
        for r in rows:
            if _is_battery(r["designation"]) and r["quantite"] > 0:
                q = int(r["quantite"]) if r["quantite"] == int(r["quantite"]) else r["quantite"]
                out.append(f"{q} × {r['designation']}" if q > 1 else r["designation"])
        if any("smart meter" in r["designation"].lower() and r["quantite"] > 0 for r in rows):
            out.append("Smart Meter + monitoring")
        out.append("Structures + installation complète")
        return out[:6]

    # Conditions de paiement par mode — réglage éditable de la société, repli
    # sur PAYMENT_TERMS_BY_MODE (défaut historique → PDF identique).
    from apps.ventes.utils.company_settings import payment_terms_for
    payment_terms = payment_terms_for(getattr(devis, "company", None), mode)

    # D2/N60/N67/N59 — textes éditables du devis (en-têtes/CGV/validité/garanties
    # /BPA/tampon). SURCHARGES non vides seulement ; toute clé absente → le moteur
    # applique son littéral historique, donc le PDF reste byte-identique tant que
    # rien n'est édité. Repli silencieux sur {} si la table n'existe pas encore.
    #
    # SCA43 / NTPLT16 — la LECTURE de config est mémorisée PAR REQUÊTE (contextvar,
    # en amont du moteur) : le dict de surcharges est constant par société le temps
    # d'une requête, donc la liste des devis ne relit plus DocumentTemplates une
    # fois par devis (dé-N+1). Hors requête (Celery/PDF) le mémo est inactif → même
    # lecture qu'avant. Le RENDU ne change pas : ``doc_texts`` est bit-identique.
    _company = getattr(devis, "company", None)

    def _load_doc_texts():
        try:
            from apps.parametres.models_documents import DocumentTemplates
            return DocumentTemplates.get(company=_company).as_doc_texts()
        except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus
            return {}

    from core import request_cache
    doc_texts = request_cache.memoize(
        ("ventes.devis_doc_texts", getattr(_company, "id", None)),
        _load_doc_texts)

    # DC1 — identité société (multi-tenant) : nom/RC/ICE/RIB/banque/adresse/tel/
    # couleur lus depuis CompanyProfile via le sélecteur parametres. Le moteur
    # premium retombe sur ses littéraux historiques (Taqinor) pour toute valeur
    # vide, donc un devis sans profil enrichi reste rendu strictement à
    # l'identique. Fuite multi-tenant corrigée : plus aucune identité en dur.
    entreprise = {}
    try:
        from apps.parametres.selectors import company_identity
        entreprise = company_identity(getattr(devis, "company", None))
    except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus
        entreprise = {}

    # ── SCA27 (complément) — site du tenant câblé au moteur résidentiel ───────
    # ``build_quote_data`` peuplait ``entreprise`` (identité) mais laissait le
    # renderer retomber sur ``taqinor.ma`` pour la ligne « site » du pied de page
    # ET la base des fiches produits, faisant fuiter le site du fondateur sur le
    # PDF d'un autre tenant. On passe désormais SON site quand il est renseigné :
    #   • ``site_url`` = forme d'affichage de son site (helios.ma) ;
    #   • ``links["produits"]`` = son site + '/produits' → ``theme.fiche_href``
    #     omet naturellement les fiches taqinor.ma (base non-taqinor) ; les autres
    #     liens pointent sur son site (aucun 404 vers le fondateur).
    # Site ABSENT → aucune clé posée : le renderer garde ses littéraux historiques
    # (taqinor.ma) et le rendu fondateur/sans-profil reste byte-identique (DC1).
    _tenant_site = _normalize_site_host(entreprise.get("site_web") or "")

    # ── QX6 — CTA de signature : lien tokenisé VERS LA VRAIE proposition ──────
    # L'ancien « taqinor.ma/signer/<ref> » (404) est remplacé par un ShareLink
    # tokenisé vers la page proposition publique (<base>/proposition/<token>).
    # RÈGLE #4 (fusion SCA27) : la BASE du lien est le site DU TENANT quand il
    # est renseigné (helios.ma) — jamais le domaine fondateur — de sorte qu'aucun
    # « taqinor.ma » ne fuit dans le PDF d'un autre tenant. Sans site tenant, on
    # retombe sur ``SITE_URL`` (taqinor.ma) : rendu fondateur inchangé. Mint/
    # réutilise un ShareLink (lecture seule, expirant) — cela NE CHANGE AUCUN
    # statut. Repli silencieux : sur toute erreur, le renderer garde son lien
    # historique (aucun PDF ne casse ici).
    links = {}
    try:
        from django.conf import settings
        from apps.ventes.models import ShareLink
        _pk = getattr(devis, "pk", None)
        if _pk is not None:
            _share = ShareLink.for_devis(devis)
            if _tenant_site:
                _signer_base = "https://" + _tenant_site
            else:
                # Repli plateforme : settings.SITE_URL (SCA29 — jamais de marque
                # en dur ici ; le défaut vit dans settings.base, configurable).
                _signer_base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
            links["signer"] = f"{_signer_base}/proposition/{_share.token}"
    except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus
        links = {}

    # ── QG7 — contact du CRÉATEUR du devis (nom + téléphone) ─────────────────
    # Le bloc contact du PDF affichait uniquement la société (donc toujours le
    # fondateur). On expose le créateur (Devis.created_by : first_name/last_name/
    # phone_number) pour que le client sache qui le suit. Repli sur le contact
    # société quand l'utilisateur n'a pas de téléphone. Données seulement.
    seller = {"nom": "", "telephone": ""}
    try:
        _creator = getattr(devis, "created_by", None)
        if _creator is not None:
            _fn = (getattr(_creator, "first_name", "") or "").strip()
            _ln = (getattr(_creator, "last_name", "") or "").strip()
            _full = (f"{_fn} {_ln}").strip()
            _tel = (getattr(_creator, "phone_number", "") or "").strip()
            if _full:
                seller["nom"] = _full
            # Repli sur le téléphone société quand l'utilisateur n'en a pas.
            seller["telephone"] = _tel or (entreprise.get("telephone") or "")
    except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus
        seller = {"nom": "", "telephone": ""}

    tva_label = int(tva_pct) if tva_pct == int(tva_pct) else tva_pct
    # Texte TVA UNIQUE, partagé par toutes les notes/conditions des PDF.
    # Réforme (taux par ligne) : le texte décrit la règle 10/20 ; devis
    # historiques : l'ancien texte au taux global, rendu inchangé.
    if per_line_tva:
        tva_note = ("TVA : 10% panneaux photovoltaïques · "
                    "20% autres équipements et prestations")
    else:
        tva_note = f"TVA {tva_label} % appliquée sur l'ensemble des équipements et travaux."
    data = {
        "ref": devis.reference,
        "date": devis.date_creation.strftime("%d/%m/%Y"),
        "client_name": client_name or "Client",
        # QRES39 — vraie toiture du client (pièce jointe image du devis dont
        # le nom évoque la toiture) ; '' → schéma illustratif.
        "roof_photo": _roof_photo_data_uri(devis),
        "client_addr": client.adresse or "",
        "client_phone": client.telephone or "",
        "client_ice": (getattr(client, "ice", "") or ""),
        # QX7c — ville du client : résolue depuis le lead lié (lead.ville) quand
        # il existe, sinon vide (le champ était lu mais jamais alimenté). Accès
        # attribut sur l'instance liée — aucun import de crm.models. Vide → la
        # ligne meta ne montre pas de ville fantôme (join_meta l'omet).
        "client_city": _client_city,
        "inst_type": inst_type,
        "puissance_kwc": puissance_kwc,
        "nb_panneaux": nb_panneaux,
        "watt_par_panneau": watt,
        "prod_kwh": roi["prod_kwh"],
        "total_sans": total_sans,
        "total_avec": total_avec,
        "total_sans_before": total_sans_before,
        "total_avec_before": total_avec_before,
        # Totaux canoniques (chaîne HT → remise → TVA → TTC calculée UNE fois)
        "totaux_sans": totaux_sans,
        "totaux_avec": totaux_avec,
        "totaux_all": totaux_all,
        "per_line_tva": per_line_tva,
        "discount_pct": discount_pct,
        "eco_s_ann": roi["eco_s_ann"],
        "eco_a_ann": roi["eco_a_ann"],
        "eco_a_cumul": roi["eco_a_cumul"],
        "roi_s": roi["roi_s"],
        "roi_a": roi["roi_a"],
        "eco_s_monthly": roi["eco_s_monthly"],
        "eco_a_monthly": roi["eco_a_monthly"],
        # QX39 — cumul du cashflow 25 ans (dégradation/escalade/batterie/onduleur)
        # : pilote la courbe de rentabilité (plus de droite linéaire « plate »).
        "cashflow_sans": roi.get("cashflow_sans"),
        "cashflow_avec": roi.get("cashflow_avec"),
        "net_gain_sans": roi.get("net_gain_sans"),
        "net_gain_avec": roi.get("net_gain_avec"),
        # QJ13 — honest-number guard: True when savings are an estimate (no tariff data)
        "savings_estimated": roi.get("savings_estimated", False),
        "tarif_kwh": roi.get("tarif_kwh"),
        # QX7a — consommation annuelle RÉELLE (kWh) quand elle est connue
        # (étude industrielle ou dérivée d'une vraie facture via le tarif kWh) ;
        # None sinon. Le renderer calcule alors une couverture honnête à partir
        # de cette conso au lieu de fabriquer un diviseur /1.3. Jamais inventée.
        "conso_annuelle_kwh": (
            int(_conso_annuelle) if _conso_annuelle else None),
        # QF2 — modèle « deux factures » : les deux factures annuelles et le
        # modèle d'économie réellement utilisé ('factures'/'etude'/'estimation').
        # Les factures sont None hors modèle 'factures' — jamais inventées.
        "savings_model": savings_model,
        "facture_sans_solaire": (
            roi.get("facture_sans") if savings_model == "factures" else None),
        "facture_avec_solaire_s": (
            roi.get("facture_avec_s") if savings_model == "factures" else None),
        "facture_avec_solaire_a": (
            roi.get("facture_avec_a") if savings_model == "factures" else None),
        "factures_approximatif": (
            bool(roi.get("factures_approximatif"))
            if savings_model == "factures" else False),
        # QF3 — bloc « Comment nous calculons vos économies » (méthode + exemple
        # chiffré compact). Même dict rendu par le PDF premium et /proposal.
        "savings_method": savings_method,
        # QK4 — bloc « Nos hypothèses » (tarif, source barème, autoconso-first,
        # productible). Même dict rendu par le PDF premium et /proposal.
        "hypotheses": hypotheses_block,
        "factures_mensuelles": factures_mensuelles,
        "sans_items": sans_items,
        "avec_items": avec_items,
        "sans_bullets": _bullets(sans_items),
        "avec_bullets": _bullets(avec_items),
        "scenario": scenario,
        "recommended": recommended,
        # QX5 — drapeaux d'option RÉELS (après repli/QF6) : le rendu résidentiel
        # gate les deux cartes dessus. `deux_options` True = document à deux
        # options (rendu inchangé) ; mono-option → une seule carte, la page 2
        # abandonne le découpage delta et renomme l'en-tête « commun ».
        "sans_ok": bool(sans_ok),
        "avec_ok": bool(avec_ok),
        "deux_options": bool(deux_options),
        "all_items": all_items,
        "onepage_note_batterie": onepage_note_batterie,
        "display_total": display_total,
        "nb_options": nb_options,
        "pdf_mode": pdf_mode,
        "show_monthly": opts['show_monthly'],
        "devis_final": opts['devis_final'],
        "payment_mode": opts['payment_mode'],
        "custom_acompte": opts['custom_acompte'],
        "include_etude": include_etude,
        "taux_tva": tva_pct,
        "tva_note": tva_note,
        "payment_terms": payment_terms,
        "mode_installation": mode,
        "etude": etude,
        # Agricole — toggleable persuasion sections + company (Paramètres
        # economics override). Ignored by every other renderer.
        "show_subsidy": opts['show_subsidy'],
        "show_fuel_comparison": opts['show_fuel_comparison'],
        "show_environmental": opts['show_environmental'],
        "show_schematic": opts['show_schematic'],
        "show_water_yield": opts['show_water_yield'],
        # company id only (JSON-serializable — this dict is also returned by the
        # public proposal-data endpoint; never put the model instance here).
        "_company_id": getattr(devis, "company_id", None),
        # D2/N60/N67/N59 — surcharges de texte éditables (vide → littéral moteur).
        "doc_texts": doc_texts,
        # DC1 — identité société (multi-tenant). Champs vides → le moteur premium
        # applique ses littéraux historiques (aucune fuite d'un autre tenant).
        "entreprise": entreprise,
        # QX6 — liens tokenisés/site (signer réel posé ici ; produits/réalisations
        # /avis/garanties dérivés du site public par le renderer). Vide → le
        # renderer applique ses littéraux historiques.
        "links": links,
        # QX6/SCA27 — site public de la société (pilote les liens du renderer),
        # normalisé depuis le champ CANONIQUE ``site_web`` (SCA27). Vide → repli
        # historique « taqinor.ma ».
        "site_url": _tenant_site,
        # QG7 — contact du créateur du devis (nom + tél ; repli société).
        # Vide → le moteur retombe sur le contact société (byte-identique).
        "seller": seller,
        # N26 — tampon d'acceptation : nom + date posés à l'acceptation du devis
        # (le moteur ne l'affiche QUE si les deux sont présents). Date au format
        # FR jj/mm/aaaa, vide sinon → devis byte-identique à aujourd'hui.
        "accepte_par_nom": (getattr(devis, "accepte_par_nom", "") or ""),
        "date_acceptation": (
            devis.date_acceptation.strftime("%d/%m/%Y")
            if getattr(devis, "date_acceptation", None) else ""),
        # FG52 — devise portée par le document (ISO 4217, défaut MAD).
        # Aucun impact sur les montants en base (stockés en MAD) ; uniquement
        # affiché sur le PDF et porté dans l'export UBL.
        "devise": (getattr(devis, "devise", None) or "MAD"),
        "taux_change": float(getattr(devis, "taux_change", 1) or 1),
    }
    # Q5 — visuel « votre installation » : la clé MinIO du rendu 3D N'EST
    # ajoutée que si le devis en porte un. Sans rendu, aucune clé n'est
    # ajoutée → la sortie reste strictement identique à aujourd'hui.
    roof_image = getattr(devis, "roof_image", None)
    if roof_image:
        data["roof_image_key"] = roof_image
    # QJ12 — financing block (indicatif / à confirmer). Added additively after
    # all other keys so omitting it never changes any existing key's value.
    # Degrades to None when display_total is unavailable — callers omit the block.
    financing = compute_financing_block(
        display_total=display_total,
        eco_s_ann=roi.get("eco_s_ann", 0),
        eco_a_ann=roi.get("eco_a_ann", 0),
        mode_installation=mode,
    )
    if financing is not None:
        data["financing"] = financing

    # ── SCA27 (complément) — site du tenant : ligne site + base fiches ────────
    # Posé UNIQUEMENT quand le profil porte un site : le renderer résidentiel lit
    # alors ``data["site_url"]``/``data["links"]`` (au lieu de ``taqinor.ma``),
    # et ``theme.fiche_href`` omet les fiches taqinor.ma (base non-taqinor). Site
    # absent → aucune clé → littéraux moteur historiques (byte-identique DC1).
    # QX6 : on PRÉSERVE le lien signer tokenisé (ShareLink) déjà minté ci-dessus —
    # il pointe sur la VRAIE proposition publique (jamais un « /signer/<ref> » 404).
    if _tenant_site:
        data["site_url"] = _tenant_site
        data["links"] = {
            "realisations": f"{_tenant_site}/realisations",
            "avis": f"{_tenant_site}/realisations",
            "produits": f"{_tenant_site}/produits",
            "garanties": f"{_tenant_site}/garanties",
            "signer": links.get("signer") or f"{_tenant_site}/signer/{devis.reference}",
        }

    # ── QJ29 — Multi-propriétés (additif, tout optionnel) ────────────────────
    # (A) ×N villas identiques : multiplicateur whole-quote (défaut 1) qui met à
    #     l'échelle HT/TVA/TTC + production/économies. N=1 → aucune clé ajoutée
    #     (chemin mono-système inchangé au bit près).
    # (B) villas différentes : sous-totaux par villa + total général calculés
    #     depuis les groupes de lignes (LigneDevis.groupe_index) via le sélecteur.
    # Les clés ci-dessous ne sont posées QUE lorsqu'elles s'appliquent, donc un
    # devis mono-système garde une sortie strictement identique.
    try:
        from apps.ventes.selectors import multi_villa_totaux, nombre_proprietes
        _n = nombre_proprietes(devis)
        if _n > 1:
            def _scale_tot(t):
                if not isinstance(t, dict):
                    return t
                out = dict(t)
                for k in ("ht_brut", "remise", "ht_net", "tva", "ttc",
                          "ttc_exact", "ttc_avant"):
                    if isinstance(out.get(k), (int, float)):
                        out[k] = round(out[k] * _n, 2) if k not in (
                            "ttc", "ttc_avant") else round(out[k] * _n)
                if isinstance(out.get("tva_par_taux"), list):
                    out["tva_par_taux"] = [
                        {**b, "montant": round(b.get("montant", 0) * _n, 2),
                         "ht_net": round(b.get("ht_net", 0) * _n, 2)}
                        for b in out["tva_par_taux"]]
                return out
            data["nombre_proprietes"] = _n
            data["display_total_unitaire"] = display_total
            data["display_total_multi"] = round(display_total * _n)
            data["totaux_multi"] = {
                "sans": _scale_tot(totaux_sans),
                "avec": _scale_tot(totaux_avec),
                "all": _scale_tot(totaux_all),
            }
            data["prod_kwh_multi"] = int(round(roi["prod_kwh"] * _n))
            data["eco_s_ann_multi"] = int(round(roi["eco_s_ann"] * _n))
            data["eco_a_ann_multi"] = int(round(roi["eco_a_ann"] * _n))
        _mv = multi_villa_totaux(devis)
        if _mv is not None:
            # Rendu-friendly : totaux Decimal → float pour la sérialisation JSON.
            def _f(t):
                out = {k: (float(v) if hasattr(v, "quantize") else v)
                       for k, v in t.items() if k != "tva_par_taux"}
                out["tva_par_taux"] = [
                    {"taux": float(b["taux"]),
                     "montant": float(b["montant"]),
                     "ht_net": float(b["ht_net"])}
                    for b in t.get("tva_par_taux", [])]
                return out
            data["multi_villa"] = {
                "groupes": [
                    {"index": g["index"], "label": g["label"],
                     "totaux": _f(g["totaux"])}
                    for g in _mv["groupes"]],
                "grand_total": _f(_mv["grand_total"]),
            }
    except Exception:  # noqa: BLE001 — un PDF/une liste ne casse jamais ici
        logger.exception("QJ29 multi-propriétés: ignoré (devis %s)",
                         getattr(devis, "reference", "?"))

    # ── XSAL5 — Bloc « Options proposées » (opt-in, HORS totaux) ─────────────
    # Rendu SEUL, additif : la clé n'est posée QUE lorsqu'il existe au moins une
    # ligne optionnelle → un devis sans option reste octet-identique. Chaque
    # entrée est client-facing (P.U. HT/TTC, total), JAMAIS de prix d'achat/marge
    # (``_line_to_item`` ne les porte pas). Le client active une option via le
    # service ``activate_optional_line`` (self-service proposition) : la ligne
    # devient alors normale et entre dans les totaux/documents avals.
    if option_lignes:
        _opts = []
        for li in option_lignes:
            it = _line_to_item(li, taux_tva)
            it.pop("_produit_nom", None)
            qte = float(li.quantite or 0)
            _opts.append({
                "id": li.id,
                "designation": it["designation"],
                "marque": it["marque"] or _parse_marque(it["designation"]),
                "quantite": qte,
                "taux_tva": it["taux_tva"],
                "prix_unit_ht": it["prix_unit_ht"],
                "prix_unit_ttc": it["prix_unit_ttc"],
                "total_ht": round(it["prix_unit_ht"] * qte, 2),
                "total_ttc": round(it["prix_unit_ttc"] * qte, 2),
            })
        data["options_proposees"] = _opts

    # ── XSAL14 — Lignes de structure (sections/notes) ────────────────────────
    # Additif : la clé n'est posée QUE lorsqu'il existe au moins une ligne de
    # section/note → un devis sans structure reste octet-identique. Ordonnées par
    # ``ordre`` puis ``id`` (comme le queryset). Rendues comme intertitres/notes
    # sur l'écran ET le PDF premium ; jamais de prix (elles n'en portent pas).
    if structure_lignes:
        _struct = sorted(
            structure_lignes,
            key=lambda li: (getattr(li, "ordre", 0) or 0, li.id))
        data["lignes_structure"] = [
            {
                "id": li.id,
                "type": getattr(li, "type_ligne", "section"),
                "ordre": getattr(li, "ordre", 0) or 0,
                "texte": li.designation,
            }
            for li in _struct
        ]

    return data


def display_totals(devis) -> dict:
    """Total d'affichage canonique pour la liste des devis — calculé par le
    MÊME chemin que les PDF (mode une-page, qui ne lève jamais), donc identique
    au document au dirham près. Repli sûr sur le total stocké."""
    try:
        data = build_quote_data(devis, {"pdf_mode": "onepage"})
        return {"total": data["display_total"], "nb_options": data["nb_options"]}
    except Exception:  # noqa: BLE001 — une liste ne doit jamais casser
        logger.exception("display_totals: repli sur total_ttc (devis %s)",
                         getattr(devis, "reference", "?"))
        return {"total": float(devis.total_ttc), "nb_options": 1}


def _pdf_key(devis) -> str:
    """MinIO key, scoped by company to avoid cross-tenant collisions."""
    company_id = getattr(devis, "company_id", None) or "0"
    return f"devis/{company_id}/{devis.reference}.pdf"


def _ensure_pdf_bucket() -> None:
    """Create the PDF bucket if it does not exist yet (idempotent, best-effort)."""
    from django.conf import settings
    from apps.ventes.utils.minio_client import get_minio_client

    client = get_minio_client()
    bucket = settings.MINIO_BUCKET_PDF
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        except Exception as exc:
            logger.warning("Could not ensure MinIO bucket %s: %s", bucket, exc)


def generate_premium_devis_pdf(devis_id, pdf_options=None, persist=True) -> str:
    """Render the quote PDF for a Devis in the requested format and store it
    in MinIO. pdf_options (see DEFAULT_PDF_OPTIONS) selects the simulator
    format: full 3-page premium (default) or one-page, with the monthly-chart
    and devis-final modifiers. Returns the stored MinIO key.

    ERR74 — ``persist`` controls the ``devis.fichier_pdf`` write. The PDF is
    always rendered and uploaded to its (deterministic, company-scoped) MinIO
    key, but on a safe GET path (``/proposal``, public share link) we pass
    ``persist=False`` so the read does not also write the model row when the
    column already points at that same key — avoiding a write side-effect on a
    safe method and a redundant re-persist. With ``persist=True`` (default,
    used by the Celery generate task) the column is refreshed only when it
    actually changed.
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.pdf import _upload_pdf
    from .generate_devis_premium import generate_premium_pdf

    devis = (
        Devis.objects
        .select_related("client", "company")
        .prefetch_related("lignes__produit")
        .get(pk=devis_id)
    )

    data = build_quote_data(devis, pdf_options)

    # ONE engine, two renderers. The redesigned 3-page layout renders
    # residential quotes (full format); the legacy renderer serves every other
    # market mode / format (industriel, agricole, one-page, étude) and is also
    # the automatic fall-back, so a client PDF is never broken.
    pdf_bytes = None
    # Agricole premium multi-page proposal (full format). One-page agricole and
    # every other mode/format stay on the legacy engine / residential renderer.
    from .agricole import renderer as agricole
    if agricole.is_agricultural(devis, pdf_options):
        try:
            pdf_bytes = agricole.render_pdf_bytes(data)
        except agricole.Unsupported:
            pdf_bytes = None
        except Exception:
            logger.warning(
                "Agricole renderer failed for %s; using legacy engine",
                getattr(devis, "reference", devis_id), exc_info=True)
            pdf_bytes = None
    # QX45 — renderer INDUSTRIEL (CFO) : full/premium seulement, intercepté APRÈS
    # l'agricole et AVANT le repli legacy (qui reste l'off-switch / one-page).
    from .industriel import renderer as industriel
    if pdf_bytes is None and industriel.is_industrial(devis, pdf_options):
        try:
            pdf_bytes = industriel.render_pdf_bytes(data)
        except industriel.Unsupported:
            pdf_bytes = None
        except Exception:
            logger.warning(
                "Industriel renderer failed for %s; using legacy engine",
                getattr(devis, "reference", devis_id), exc_info=True)
            pdf_bytes = None
    # QX46 — renderer COMMERCIAL (catégorie-aware) : full/premium seulement,
    # intercepté AVANT le repli legacy (comme QX45).
    from .commercial import renderer as commercial
    if pdf_bytes is None and commercial.is_commercial(devis, pdf_options):
        try:
            pdf_bytes = commercial.render_pdf_bytes(data)
        except commercial.Unsupported:
            pdf_bytes = None
        except Exception:
            logger.warning(
                "Commercial renderer failed for %s; using legacy engine",
                getattr(devis, "reference", devis_id), exc_info=True)
            pdf_bytes = None
    from .residential import renderer as residential
    if pdf_bytes is None and residential.is_residential(devis, pdf_options):
        try:
            pdf_bytes = residential.render_pdf_bytes(data)
        except residential.Unsupported:
            pdf_bytes = None
        except Exception:
            logger.warning(
                "Residential renderer failed for %s; using legacy engine",
                getattr(devis, "reference", devis_id), exc_info=True)
            pdf_bytes = None
    if pdf_bytes is None:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tmp_path = tf.name
        try:
            generate_premium_pdf(data, tmp_path)
            pdf_bytes = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    key = _pdf_key(devis)
    _ensure_pdf_bucket()
    _upload_pdf(pdf_bytes, key)

    # Persist the key only when asked AND when it actually changed: a safe GET
    # (persist=False) never writes; the default path writes once.
    if persist and devis.fichier_pdf != key:
        devis.fichier_pdf = key
        devis.save(update_fields=["fichier_pdf"])

    logger.info("Premium quote PDF generated: %s (%d bytes)", key, len(pdf_bytes))
    return key
