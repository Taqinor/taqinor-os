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
    """Convert an OS LigneDevis (HT prices) into a premium TTC item dict."""
    pu_ht = Decimal(ligne.prix_unitaire) * (Decimal(1) - Decimal(ligne.remise) / Decimal(100))
    pu_ttc = pu_ht * (Decimal(1) + Decimal(taux_tva) / Decimal(100))
    produit_nom = getattr(getattr(ligne, "produit", None), "nom", "") or ""
    return {
        "designation": ligne.designation,
        "marque": "",
        "quantite": float(ligne.quantite),
        "prix_unit_ttc": float(round(pu_ttc, 2)),
        "_produit_nom": produit_nom,
    }


def build_quote_data(devis) -> dict:
    """Build the dict consumed by generate_premium_pdf from a Devis instance."""
    from .pricing import calculate_savings_roi
    from .catalog import pick_default_battery

    client = devis.client
    taux_tva = devis.taux_tva or Decimal(20)
    lignes = list(devis.lignes.select_related("produit").all())

    items = [_line_to_item(li, taux_tva) for li in lignes]

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
    # Shared equipment (panels, structures, socles, etc.) appears in both.
    sans_items = [
        it for it in items
        if not _is_battery(it["designation"]) and not _is_hybrid_inverter(it["designation"])
    ]
    avec_items = [
        it for it in items
        if not _is_reseau_inverter(it["designation"])
    ]
    if not any(_is_battery(it["designation"]) for it in avec_items):
        # Avec option has no battery → synthesize one from the catalog.
        avec_items = avec_items + [pick_default_battery()]

    def _sum(rows):
        return float(sum(r["quantite"] * r["prix_unit_ttc"] for r in rows))

    total_sans_before = _sum(sans_items)
    total_avec_before = _sum(avec_items)

    discount_pct = float(devis.remise_globale or 0)
    factor = 1 - discount_pct / 100
    total_sans = round(total_sans_before * factor)
    total_avec = round(total_avec_before * factor)

    # Power: prefer real panels; otherwise estimate from the (sans) total so ROI
    # stays sane even for quotes without an explicit panel line.
    if nb_panneaux > 0:
        puissance_kwc = round(nb_panneaux * watt / 1000, 2)
    else:
        puissance_kwc = max(3.0, round(total_sans / 12000, 2))
        nb_panneaux = max(1, round(puissance_kwc * 1000 / watt))

    # ── ROI on the fly ───────────────────────────────────────────────────────
    roi = calculate_savings_roi(puissance_kwc, total_sans, total_avec)

    # ONEE monthly bill proxy (bars sit above the savings curves): full-price bill
    # ≈ Option-2 monthly savings / 0.85 autoconsumption.
    factures_mensuelles = [round(v / 0.85) for v in roi["eco_a_monthly"]]

    client_name = f"{(client.prenom or '').strip()} {(client.nom or '').strip()}".strip()

    # Strip the internal helper key before handing items to the generator.
    for rows in (sans_items, avec_items):
        for r in rows:
            r.pop("_produit_nom", None)

    data = {
        "ref": devis.reference,
        "date": devis.date_creation.strftime("%d/%m/%Y"),
        "client_name": client_name or "Client",
        "client_addr": client.adresse or "",
        "client_phone": client.telephone or "",
        "client_ice": "",
        "inst_type": "Résidentielle",
        "puissance_kwc": puissance_kwc,
        "nb_panneaux": nb_panneaux,
        "watt_par_panneau": watt,
        "prod_kwh": roi["prod_kwh"],
        "total_sans": total_sans,
        "total_avec": total_avec,
        "total_sans_before": total_sans_before,
        "total_avec_before": total_avec_before,
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
        "scenario": "Les deux (Sans + Avec)",
        "recommended": "Avec batterie",
    }
    return data


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


def generate_premium_devis_pdf(devis_id) -> str:
    """Render the premium quote PDF for a Devis and store it in MinIO.

    Returns the stored MinIO key (also saved on devis.fichier_pdf).
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

    data = build_quote_data(devis)

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
