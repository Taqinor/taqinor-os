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

import hashlib
import json
from collections import OrderedDict
from pathlib import Path


class Unsupported(Exception):
    """The devis/options are outside the residential renderer's scope."""


# ── QX8 — cache LRU des octets PDF rendus, clé = empreinte du dict de données ──
# Un second rendu du MÊME devis inchangé (rafale de clients ouvrant le même
# lien) réutilise les octets déjà rendus au lieu de refaire polices/logo/4
# graphiques + WeasyPrint. Bornée (petite) pour ne pas gonfler la mémoire ;
# l'empreinte couvre tout ce qui influe sur le rendu, donc toute édition du
# devis change la clé et force un vrai re-rendu (jamais un PDF périmé). Sortie
# byte-identique au chemin sans cache. Complète (sans dupliquer) la persistance
# /proposal (ERR74) : ici on ne touche AUCUN modèle, on mémorise juste les octets.
_PDF_CACHE: "OrderedDict[str, bytes]" = OrderedDict()
_PDF_CACHE_MAX = 32


def _fingerprint(data: dict) -> str | None:
    """Empreinte stable et déterministe du dict de données de rendu.

    Le dict est JSON-sérialisable (il est aussi renvoyé par l'endpoint public
    proposal-data). Sur toute donnée non sérialisable, renvoie None → le cache
    est simplement contourné (le rendu se fait normalement)."""
    try:
        blob = json.dumps(data, sort_keys=True, default=str,
                          ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


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


# ── PVCOV (fondateur, 18/08/2026) — LA synthèse économies/couverture, extraite
# pour être servie TELLE QUELLE à la proposition en ligne (public_views) : la
# page web et la couverture du PDF lisent ainsi le MÊME calcul — le « −85 % »
# et la donut de couverture ne peuvent plus diverger entre les deux supports.
# Fonction PURE (dict → dict | None) : aucun accès BD, aucune dépendance lourde.
def synthese_economies(data: dict) -> dict | None:
    """Avant/après facture + couverture solaire, formules de la page 1 du PDF.

    Retourne None quand le devis n'a pas la forme requise (12 factures
    mensuelles, économies mensuelles, production) — l'appelant public sert
    alors des None et la page web n'affiche rien, jamais un chiffre inventé.
    """
    try:
        before = list(data.get("factures_mensuelles") or [])
        eco_m = list(data.get("eco_a_monthly") or [])
        prod_kwh = data.get("prod_kwh") or 0
        if len(before) != 12 or len(eco_m) != 12 or not prod_kwh:
            return None
        after = [max(0, round(b - s)) for b, s in zip(before, eco_m)]
        annual_before, annual_after = sum(before), sum(after)
        if annual_before <= 0:
            return None
        # Même formule que la couverture (cover.py) : « facture réduite de X % ».
        pct_cut = round((1 - annual_after / max(1, annual_before)) * 100)
        # QX7a — couverture HONNÊTE : conso réelle d'abord, sinon dérivée de la
        # facture au tarif réel ; plancher 1 %, plafond 100 %, drapeau
        # « estimation » quand la conso n'est pas mesurée.
        conso_kwh = data.get("conso_annuelle_kwh")
        coverage_estimated = False
        if conso_kwh and conso_kwh > 0:
            conso = conso_kwh
        else:
            tarif = data.get("tarif_kwh") or 0
            if tarif and tarif > 0:
                conso = max(1, round(annual_before / float(tarif)))
            else:
                conso = max(1, round(annual_before))  # dernier repli (1 MAD/kWh)
            coverage_estimated = True
        coverage = min(100, max(1, round(prod_kwh / conso * 100)))
        return {
            "bills_before": before, "bills_after": after,
            "annual_before": annual_before, "annual_after": annual_after,
            "pct_cut": pct_cut,
            "coverage_pct": coverage, "coverage_estimated": coverage_estimated,
        }
    except (TypeError, ValueError):
        return None


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

    if len(data["factures_mensuelles"]) != 12:
        raise Unsupported("need 12 monthly bills for the avant/après chart")
    # PVCOV — le calcul vit dans synthese_economies (servi tel quel à la
    # proposition en ligne) ; _augment ne fait plus que le consommer.
    synth = synthese_economies(data)
    if synth is None:
        raise Unsupported("no bill baseline")

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
        **synth,
        "validity_days": d.get("validity_days", 30),
        "site_url": site_url,
        "links": links,
    })
    return d


def _measure_page_slack(pdf_bytes: bytes) -> dict:
    """QRES62 — vide résiduel exploitable par page (mm), MESURÉ sur le PDF
    réellement rendu (PyMuPDF). La page 1 (cover pleine page) est exclue ;
    pour chaque autre page : bas du contenu = max(y) des blocs de texte et
    tracés au-dessus de la bande de pied fixe (13 mm), vide = distance entre
    ce bas et le pied, moins une marge esthétique (6 mm) et une garde de
    sécurité (4 mm). {} si PyMuPDF est absent ou sur toute erreur — le rendu
    passe-1 reste alors servi tel quel (dégradation propre)."""
    try:
        import fitz
    except Exception:
        return {}
    out = {}
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i in range(1, len(doc)):
            page = doc[i]
            mm = page.rect.height / 297.0            # points par millimètre
            footer_top = page.rect.height - 13.0 * mm
            bottom = 0.0
            for b in page.get_text("blocks"):
                if b[3] < footer_top - 0.5 * mm:
                    bottom = max(bottom, b[3])
            for dr in page.get_drawings():
                if dr["rect"].y1 < footer_top - 0.5 * mm:
                    bottom = max(bottom, dr["rect"].y1)
            if bottom <= 0:
                continue
            slack = (footer_top - bottom) / mm - 6.0 - 4.0
            if slack >= 4.0:
                out[i + 1] = round(min(slack, 68.0), 1)
        doc.close()
    except Exception:
        return {}
    return out


def render_pdf_bytes(data: dict) -> bytes:
    """Render the redesigned residential proposal to PDF bytes, or raise
    Unsupported when the quote data isn't the residential two-option shape.

    QX8 — un second rendu du MÊME devis inchangé réutilise les octets déjà
    rendus (cache LRU par empreinte de données), sans refaire polices/logo/
    graphiques/WeasyPrint. Toute édition change l'empreinte → vrai re-rendu.

    QRES62 — distribution DYNAMIQUE de l'espace : le document est rendu une
    première fois, le vide résiduel de chaque page est mesuré sur le PDF
    réel, puis le document est re-rendu UNE fois avec ce vide réparti sur les
    joints élastiques des gabarits (avant l'accord, le CTA, la bande légale,
    les totaux, le bandeau de gain…). Si le second passage changeait le
    nombre de pages (impossible en pratique : la garde de 4 mm l'empêche),
    le passe-1 est servi — jamais de régression de pagination.
    """
    from weasyprint import HTML
    from . import render as residential_render

    # _augment peut lever Unsupported : on le laisse remonter AVANT tout cache.
    d = _augment(data)
    key = _fingerprint(d)
    if key is not None:
        hit = _PDF_CACHE.get(key)
        if hit is not None:
            _PDF_CACHE.move_to_end(key)  # LRU : marque comme récemment utilisé
            return hit

    base = str(Path(residential_render.__file__).resolve().parent)
    html = residential_render.build_html(d)
    doc1 = HTML(string=html, base_url=f"file://{base}/").render()
    pdf_bytes = doc1.write_pdf()

    slack = _measure_page_slack(pdf_bytes)
    if slack:
        html2 = residential_render.build_html(d, elastic=slack)
        doc2 = HTML(string=html2, base_url=f"file://{base}/").render()
        if len(doc2.pages) == len(doc1.pages):
            pdf_bytes = doc2.write_pdf()

    if key is not None:
        _PDF_CACHE[key] = pdf_bytes
        _PDF_CACHE.move_to_end(key)
        while len(_PDF_CACHE) > _PDF_CACHE_MAX:
            _PDF_CACHE.popitem(last=False)  # évince le plus ancien
    return pdf_bytes
