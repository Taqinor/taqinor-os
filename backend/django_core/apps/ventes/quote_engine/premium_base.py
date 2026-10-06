"""QJR651 — LE HARNAIS DE RENDU PREMIUM industriel / commercial, UNE fois.

``industriel/render.py`` et ``commercial/render.py`` ne différaient que par
leur liste de pages : contexte, enveloppe de page (pied lisant le nombre RÉEL
de pages), assemblage HTML et rendu WeasyPrint vivent ici ; chaque marché ne
garde que ``pages(ctx)``. Rendu octet-identique à l'avant (verrouillé par
``tests/test_premium_base_harnais.py``).

Hors périmètre, DÉLIBÉRÉMENT : le harnais résidentiel (le sien a des options
de compacité propres), ``generate_devis_premium.kwc_fr`` (qui rend ``str(v)``
en erreur, pas « — ») et les ``_num`` des modules de page (défauts et NaN
différents d'un module à l'autre).

Le moteur ne fait que RENDRE — il ne change aucun statut (règle #4).
"""
from __future__ import annotations

from pathlib import Path

from . import montants
from .residential import theme


def build_ctx(data: dict) -> dict:
    ident = theme.company_identity(data)
    return {
        "d": data,
        "C": theme.C,
        "fmt": theme.fmt,
        # QJR614 — montants dérivés du prix (P.U., total de ligne, chaîne de
        # totaux, prix TTC) au CENTIME, ROUND_HALF_UP ; ``fmt`` (entier)
        # reste pour kWh, CO2, panneaux, économies estimées.
        "fmt_mad": montants.fmt_centimes,
        "fonts": {"display": theme.FONT_DISPLAY, "serif": theme.FONT_SERIF,
                  "sans": theme.FONT_SANS},
        "logo_dark": theme.logo_dark_b64(),
        "logo_color": theme.logo_color_b64(),
        "ident": ident,
        "theme": theme,
    }


def wrap_page(inner: str, n: int, data: dict, ident: dict, total: int = 3) -> str:
    # Le pied lit le NOMBRE RÉEL de pages rendues (jamais « / 3 » codé).
    foot = (theme.page_footer(data, ident, total_pages=total)
            .replace("{page}", str(n)))
    return f'<div class="page">{inner}{foot}</div>'


def build_html(data: dict, pages_fn) -> str:
    """Assemble les pages rendues par ``pages_fn(ctx) -> list[str]``."""
    ctx = build_ctx(data)
    ident = ctx["ident"]
    pages = pages_fn(ctx)
    total = len(pages)
    body = "".join(
        wrap_page(inner, n, data, ident, total)
        for n, inner in enumerate(pages, start=1))
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}</style></head>"
            f"<body>{body}</body></html>")


def render_pdf(out_path, html: str, base_dir) -> str:
    """Écrit ``html`` en PDF A4 ; ``base_dir`` = dossier du module de marché
    (résolution des ressources relatives, comme avant)."""
    from weasyprint import HTML
    base = str(Path(base_dir).resolve())
    HTML(string=html, base_url=f"file://{base}/").write_pdf(str(out_path))
    return str(out_path)


def kwc_str(v, defaut: str = "—") -> str:
    """Puissance à la française pour les couvertures (« 10,65 », « 10 ») ;
    ``defaut`` quand la valeur est illisible ou absente."""
    try:
        return f"{float(v):.2f}".rstrip("0").rstrip(".").replace(".", ",")
    except (TypeError, ValueError):
        return defaut


def kpi(val, unit, label, fig=None, *, prefixe: str) -> str:
    """Cellule KPI d'une couverture ; ``prefixe`` = préfixe de classes CSS du
    module de page (``i1`` industriel, ``c1c`` commercial)."""
    from .figures import ancre
    _a = ancre(fig, val) if fig else ""
    return (f'<td class="{prefixe}-kpi"><div class="{prefixe}-kv">{val}'
            f'<span class="{prefixe}-ku">{unit}</span></div>{_a}'
            f'<div class="{prefixe}-kl">{label}</div></td>')


def bande_legale(d: dict, ident: dict) -> str:
    """CIQ310 — la bande légale du VENDEUR (RC, ICE, capital…), composée UNE
    fois pour le résidentiel (``residential/trust``, sortie identique octet
    pour octet) et les pages de confiance commerciale et industrielle.

    Profil société d'un TENANT (nom non-TAQINOR) → SES identifiants, champs
    absents omis ; sinon le repli fondateur."""
    # SCA27 (fix règle-#4-permis) — pour un TENANT (profil au nom non-TAQINOR),
    # la bande se compose de SES identifiants (nom/RC/ICE/email/téléphone/site,
    # champs absents omis — capital et gérant n'ont pas de champ profil). Le
    # littéral fondateur reste le repli byte-identique (profil vide OU marque
    # TAQINOR — même sémantique par-la-donnée que _footer_brand/DC1).
    from html import escape as _esc
    ent = d.get("entreprise") or {}
    ent_nom = (ent.get("nom") or "").strip()
    if ent_nom and "TAQINOR" not in ent_nom.upper():
        parts = [f"<b>{_esc(ent_nom)}</b>"]
        if (ent.get("rc") or "").strip():
            parts.append("RC " + _esc(ent["rc"].strip()))
        if (ent.get("ice") or "").strip():
            parts.append("ICE " + _esc(ent["ice"].strip()))
        if (ent.get("email") or "").strip():
            parts.append(_esc(ent["email"].strip()))
        if (ent.get("telephone") or "").strip():
            parts.append(_esc(ent["telephone"].strip()))
        _site_tenant = (d.get("site_url") or "").strip()
        if _site_tenant and "taqinor" not in _site_tenant.lower():
            parts.append(_esc(_site_tenant))
        legal = " &middot; ".join(parts)
    else:
        legal = (
            '<b>TAQINOR Solutions SARLAU</b> au capital de 100 000,00 MAD'
            ' &middot; RC 691213 — Tribunal de Commerce de Casablanca'
            ' &middot; ICE 003799642000067 &middot; Gérant : M. Reda Kasri'
            # QRES10 — contact lu depuis l'identité RÉSOLUE (profil société →
            # repli littéraux fondateur) : la bande légale affiche toujours LE
            # MÊME email/téléphone que le pied de page (le PDF réel imprimait
            # « contact@taqinor.ma » en pied et « contact@taqinor.com » ici).
            f' &middot; {ident.get("email") or "contact@taqinor.com"}'
            f' &middot; {ident.get("phone") or "+212 6 61 85 04 10"}'
            ' &middot; taqinor.ma'
        )
    return legal
