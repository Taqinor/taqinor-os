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
_DEFAULT_WATT = 450

# Brand tokens from the simulator catalogue — longest/most specific first so
# 'Deyness' wins over its substring 'Deye'.
_BRAND_TOKENS = [
    "Canadien Solar", "Canadian Solar", "Deyness", "Jinko",
    "Huawei", "Deye", "Lithium", "Gel",
]


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
    try:
        acompte = raw.get('custom_acompte')
        opts['custom_acompte'] = float(acompte) if acompte not in (None, '') else None
    except (TypeError, ValueError):
        opts['custom_acompte'] = None
    return opts


def build_quote_data(devis, pdf_options=None) -> dict:
    """Build the dict consumed by generate_premium_pdf from a Devis instance."""
    from .pricing import calculate_savings_roi
    from .catalog import pick_default_battery

    client = devis.client
    taux_tva = devis.taux_tva or Decimal(20)
    lignes = list(devis.lignes.select_related("produit").all())

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
    if sans_ok and avec_ok:
        scenario = "Les deux (Sans + Avec)"
        recommended = "Avec batterie"
    elif sans_ok:
        scenario = "Sans batterie"
        recommended = "Sans batterie"
    else:
        scenario = "Avec batterie"
        recommended = "Avec batterie"

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
    # Une page : option 1 seule quand deux vraies options, sinon tout le devis
    totaux_all = _canonical_totaux(sans_items if deux_options else items)

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

    # ── Canonical performance figures: ONE source of truth ───────────────────
    # When the quote carries a stored étude (industrial), its consumption-driven
    # production/savings are canonical; payback and prix/kWc are recomputed from
    # the canonical totals so edited lines can never desynchronize the document.
    etude = dict(devis.etude_params or {})
    roi = calculate_savings_roi(puissance_kwc, total_sans, total_avec)
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

    # ONEE monthly bill proxy (bars sit above the savings curves): full-price bill
    # ≈ Option-2 monthly savings / 0.85 autoconsumption.
    factures_mensuelles = [round(v / 0.85) for v in roi["eco_a_monthly"]]

    client_name = f"{(client.prenom or '').strip()} {(client.nom or '').strip()}".strip()

    # Liste d'articles du format UNE PAGE. RÈGLE D'INTÉGRITÉ : une facture ne
    # mélange JAMAIS deux options — un devis à deux vraies options (réseau ET
    # hybride+batterie) rend l'OPTION 1 (sans batterie) seule, avec une
    # mention discrète vers la proposition complète. Devis mono-option ou sans
    # options (pompage, liste libre) : toutes les lignes, comme avant.
    onepage_source = sans_items if deux_options else items
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
        "industriel": "Industrielle / Commerciale",
        "agricole": "Agricole",
    }.get(mode, "Résidentielle")

    # Mode industriel : l'étude fait partie du document (page dédiée incluse
    # d'office quand des données d'étude existent).
    include_etude = opts['include_etude'] or (mode == "industriel" and bool(etude))

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

    # ── Conditions de paiement par mode d'installation (SOURCE UNIQUE) ──
    # Décision propriétaire 2026-06-12. Tous les formats rendent CE mapping ;
    # plus aucun pourcentage en dur dans les gabarits. Agricole = défaut
    # résidentiel (30/60/10) en attente d'un éventuel veto du fondateur.
    PAYMENT_TERMS_BY_MODE = {
        "residentiel": {"acompte": 30, "materiel": 60, "solde": 10},
        "industriel": {"acompte": 50, "materiel": 40, "solde": 10},
        "agricole": {"acompte": 30, "materiel": 60, "solde": 10},
    }
    payment_terms = PAYMENT_TERMS_BY_MODE.get(
        mode or "residentiel", PAYMENT_TERMS_BY_MODE["residentiel"])

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
        "client_addr": client.adresse or "",
        "client_phone": client.telephone or "",
        "client_ice": (getattr(client, "ice", "") or ""),
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
        "factures_mensuelles": factures_mensuelles,
        "sans_items": sans_items,
        "avec_items": avec_items,
        "sans_bullets": _bullets(sans_items),
        "avec_bullets": _bullets(avec_items),
        "scenario": scenario,
        "recommended": recommended,
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
    }
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


def generate_premium_devis_pdf(devis_id, pdf_options=None) -> str:
    """Render the quote PDF for a Devis in the requested format and store it
    in MinIO. pdf_options (see DEFAULT_PDF_OPTIONS) selects the simulator
    format: full 3-page premium (default) or one-page, with the monthly-chart
    and devis-final modifiers. Returns the stored MinIO key.
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

    devis.fichier_pdf = key
    devis.save(update_fields=["fichier_pdf"])

    logger.info("Premium quote PDF generated: %s (%d bytes)", key, len(pdf_bytes))
    return key
