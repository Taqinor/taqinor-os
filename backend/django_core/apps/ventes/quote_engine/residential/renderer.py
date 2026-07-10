# flake8: noqa
"""Residential renderer selection + data augmentation for the single engine.

`generate_premium_devis_pdf` builds the quote data once, then asks this module
whether the redesigned 3-page residential layout applies. If so it renders PDF
bytes; if the devis isn't the residential two-option shape it raises
`Unsupported` and the engine falls back to the legacy renderer (which also
serves industriel / agricole / one-page / étude). One engine, one data builder.

Renders only — never changes a devis status (CLAUDE.md rule #4).
"""
from __future__ import annotations
from pathlib import Path


class Unsupported(Exception):
    """The devis/options are outside the residential renderer's scope."""


def is_residential(devis, options=None) -> bool:
    """True when the redesigned residential layout should render this quote.

    Residential market mode (or unset, the common default) and the standard
    full 3-page format — one-page and the étude page stay on the legacy engine.
    """
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode not in ("", "residentiel", "résidentiel"):
        return False
    opts = options or {}
    if (opts.get("pdf_mode") or "full") not in ("full", "premium"):
        return False
    if opts.get("include_etude"):
        return False
    return True


def _augment(data: dict) -> dict:
    """Add the redesigned layout's derived fields onto the built quote data,
    raising Unsupported if the devis isn't the residential two-option shape."""
    need = ("sans_items", "avec_items", "totaux_sans", "totaux_avec",
            "roi_s", "roi_a", "total_sans", "total_avec",
            "eco_s_ann", "eco_a_ann", "factures_mensuelles", "eco_a_monthly",
            "puissance_kwc", "prod_kwh", "nb_panneaux", "watt_par_panneau",
            "ref", "date")
    for k in need:
        if data.get(k) in (None, "", [], 0):
            raise Unsupported(f"missing quote field: {k}")

    before = list(data["factures_mensuelles"])
    if len(before) != 12:
        raise Unsupported("need 12 monthly bills for the avant/après chart")
    after = [max(0, round(b - s)) for b, s in zip(before, data["eco_a_monthly"])]
    annual_before, annual_after = sum(before), sum(after)
    if annual_before <= 0:
        raise Unsupported("no bill baseline")
    conso = max(1, round(annual_before / 1.3))
    coverage = max(40, min(99, round(data["prod_kwh"] / conso * 100)))

    d = dict(data)
    d.setdefault("client_full", d.get("client_name") or "Client")

    # QX4 — site public piloté par l'identité société (multi-tenant). Le
    # ``site_url`` du profil (parametres) prime ; repli sur le littéral
    # historique « taqinor.ma » quand aucun profil enrichi n'existe (sortie
    # byte-identique pour Taqinor). QX6 : les liens produits/réalisations/
    # garanties dérivent de ce site ; le lien de signature réel est déjà posé
    # par le builder (data['links']['signer']) — sinon repli historique.
    ent = d.get("entreprise") or {}
    ent_site = (ent.get("site_url") or "").strip().rstrip("/")
    site_url = ent_site or d.get("site_url") or "taqinor.ma"
    _existing_links = dict(d.get("links") or {})
    _default_links = {
        # QK5 — « avis » pointe vers /realisations (page réelle : nos
        # réalisations clients). Le chemin /avis n'existe pas sur taqinor.ma ;
        # un lien 404 sur un PDF client est corrigé ici. On ne fabrique jamais
        # d'avis : on renvoie vers les réalisations vérifiables.
        "realisations": f"{site_url}/realisations",
        "avis": f"{site_url}/realisations",
        "produits": f"{site_url}/produits",
        "garanties": f"{site_url}/garanties",
        "signer": f"{site_url}/signer/{d.get('ref', '')}",
    }
    # Les liens explicitement posés par le builder (ex. QX6 signer tokenisé)
    # priment ; les manquants dérivent du site public de la société.
    links = {**_default_links, **{k: v for k, v in _existing_links.items() if v}}

    d.update({
        "bills_before": before, "bills_after": after,
        "annual_before": annual_before, "annual_after": annual_after,
        "coverage_pct": coverage,
        "validity_days": d.get("validity_days", 30),
        "site_url": site_url,
        "links": links,
    })
    return d


def render_pdf_bytes(data: dict) -> bytes:
    """Render the redesigned residential proposal to PDF bytes, or raise
    Unsupported when the quote data isn't the residential two-option shape."""
    from weasyprint import HTML
    from . import render as residential_render
    d = _augment(data)
    html = residential_render.build_html(d)
    base = str(Path(residential_render.__file__).resolve().parent)
    return HTML(string=html, base_url=f"file://{base}/").write_pdf()
