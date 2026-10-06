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
    # CIQ333 — « Réf. » suit la langue du document (français inchangé).
    foot = (theme.page_footer(data, ident, total_pages=total, traduire=True)
            .replace("{page}", str(n)))
    return f'<div class="page">{inner}{foot}</div>'


def build_html(data: dict, pages_fn) -> str:
    """Assemble les pages rendues par ``pages_fn(ctx) -> list[str]``.

    CIQ333 — un document en anglais ou en arabe porte ``lang`` (et
    ``dir="rtl"`` en arabe, d'où WeasyPrint tire l'alignement à droite et
    l'ordre miroir des tableaux) et la police arabe vendorisée, comme le
    document agricole (AGR314) ; le français reste octet pour octet."""
    from . import i18n_labels
    ctx = build_ctx(data)
    ident = ctx["ident"]
    pages = pages_fn(ctx)
    total = len(pages)
    body = "".join(
        wrap_page(inner, n, data, ident, total)
        for n, inner in enumerate(pages, start=1))
    langue = theme.langue_doc(data)
    racine, css_langue = "<html>", ""
    if langue != "fr":
        racine = (f'<html lang="{langue}" '
                  f'dir="{i18n_labels.direction(langue)}">')
    if i18n_labels.est_rtl(langue):
        # Rendu RÉEL mesuré : l'espacement de lettres (petites capitales,
        # en-têtes) casse la liaison des lettres arabes, et la face 700
        # vendorisée sort illisible en gras — l'arabe prend la police
        # système (Noto Sans Arabic de l'image), sans espacement de lettres.
        css_langue = (".i18n-rtl{unicode-bidi:isolate;}"
                      "body *{letter-spacing:0 !important;}")
    return (f"<!doctype html>{racine}<head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}{css_langue}</style></head>"
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

    La composition (profil société d'un tenant, sinon repli fondateur) vit
    dans ``residential.theme.bande_legale``, à côté des autres replis de
    marque du moteur (SCA29)."""
    return theme.bande_legale(d, ident)
