# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Harnais de rendu des éditions commerciales : contexte, enveloppe de page,
pied, polices, assemblage HTML et rendu PDF mesuré.

Reprend ``premium_base.build_ctx`` (identité, logo, formats) et le contrat
de pages de ``commercial.equip`` (``_tient`` : pages exactes, rien sous le
pied) ; seule l'enveloppe visuelle (CSS de base, pied) est propre aux
éditions. Rendu seul — aucun statut touché (règle #4).
"""
from __future__ import annotations

import base64
from pathlib import Path

from .. import i18n_labels, premium_base
from ..montants import format_langue
from ..residential import theme

_ICI = Path(__file__).resolve().parent
_FONTS = _ICI / "assets" / "fonts"


def _b64(chemin: Path) -> str:
    return base64.b64encode(chemin.read_bytes()).decode() if chemin.exists() else ""


def font_face(famille: str, fichier: str, poids: int, style: str = "normal") -> str:
    """Une règle ``@font-face`` pour une police vendorisée (woff2) ; '' si
    le fichier manque (WeasyPrint retombe sur la pile système)."""
    b64 = _b64(_FONTS / fichier)
    if not b64:
        return ""
    ttf = fichier.lower().endswith((".ttf", ".otf"))
    mime, fmt = ("font/ttf", "truetype") if ttf else ("font/woff2", "woff2")
    return (f"@font-face{{font-family:'{famille}';font-weight:{poids};"
            f"font-style:{style};src:url(data:{mime};base64,{b64}) "
            f"format('{fmt}');}}")


def image_b64(nom: str) -> str:
    """L'image ``assets/<nom>`` en base64 ('' si absente)."""
    return _b64(_ICI / "assets" / nom)


def build_ctx(data: dict) -> dict:
    return premium_base.build_ctx(data)


def pied(data: dict, ident: dict, n: int, total: int, j: dict,
         police: str) -> str:
    """Le pied : plein (marine tramé, Signature et Normale) ou à filets
    (Basique). Même contenu que ``theme.page_footer`` (identité société,
    filigrane standard), autre habit."""
    site = ident.get("site") if "site" in ident else theme._DEFAULT_SITE
    filigrane = theme._esc(data.get("_watermark_standard") or "")
    suffixe = f" &nbsp;·&nbsp; {filigrane}" if filigrane else ""
    ref_lbl = theme.libelle_doc(data, "reference", "Réf.")
    page_lbl = theme.libelle_doc(data, "res_page", "Page")
    tel = (ident.get("phone") or "").replace(" ", "\u00a0")
    gauche = " &nbsp;·&nbsp; ".join(
        x for x in (f"<b>{ident['brand_name']}</b>", ident.get("email") or "", tel) if x)
    droite = (f"{page_lbl} {n} / {total} &nbsp;·&nbsp; {ref_lbl} {data['ref']}"
              + (f" &nbsp;·&nbsp; <span class='ed-site'>{site}</span>" if site else "") + suffixe)
    return (f'<div class="foot ed-foot ed-foot-{j.get("pied", "plein")}"><div>{gauche}</div>'
            f'<div>{droite}</div></div>')


def css_base(jeton: dict) -> str:
    """La feuille de base d'une édition."""
    from .commun import css_motif
    j = jeton
    return f"""
{j['fonts_css']}
* {{ margin:0; padding:0; box-sizing:border-box; }}
@page {{ size: A4; margin: 0; }}
html, body {{ font-family:{j['sans']}; color:{j['ink']}; -weasy-hyphens:none; font-size:9pt; line-height:1.4; }}
.page {{ position:relative; width:210mm; height:297mm; overflow:hidden; background:{j['paper']}; page-break-after:always; }}
.page:last-child {{ page-break-after:auto; }}
.foot.ed-foot {{ position:absolute; left:0; right:0; bottom:0; display:table; width:100%;
  padding:0 {j.get('marge', '20mm')} 0 {j.get('marge_g', '20mm')}; font-size:7pt; }}
.foot.ed-foot > div {{ display:table-cell; vertical-align:middle; height:12mm; }}
.foot.ed-foot > div + div {{ text-align:right; }}
.foot.ed-foot-plein {{ height:12mm; background:{j['hero_bg']}; {css_motif(j['motif_8'], 14)} color:{j['on_hero']};
  border-top:0.6pt solid {j['or']}; }}
.foot.ed-foot-plein b {{ color:{j['on_hero']}; font-weight:600; }}
.foot.ed-foot-plein .ed-site {{ color:{j['or_texte']}; }}
.foot.ed-foot-filet {{ height:10mm; color:{j['muted']}; border-top:0.5pt solid {j['ink']}; background:{j['paper']}; }}
.foot.ed-foot-filet b {{ color:{j['ink']}; font-weight:600; }}
.foot.ed-foot-filet .ed-site {{ color:{j['laiton']}; }}
.ed-foot-or {{ position:absolute; left:0; right:0; bottom:9.2mm; border-top:0.4pt solid {j['or']}; }}
.qj {{ height:0; }}
"""


def build_html(data: dict, pages_fn, jeton: dict) -> str:
    """Assemble ``pages_fn(ctx) -> list[str]`` dans l'enveloppe de
    l'édition. Langue : ``lang``/``dir`` comme ``premium_base.build_html``
    (CIQ333), police arabe système sans espacement de lettres (APDF6)."""
    ctx = build_ctx(data)
    ident = ctx["ident"]
    with format_langue(data):
        pages = pages_fn(ctx)
    total = len(pages)
    corps = "".join(
        f'<div class="page">{inner}'
        f'{pied(data, ident, n, total, jeton, jeton["sans"])}</div>'
        for n, inner in enumerate(pages, start=1))
    langue = theme.langue_doc(data)
    racine, css_langue = "<html>", ""
    if langue != "fr":
        racine = f'<html lang="{langue}" dir="{i18n_labels.direction(langue)}">'
    if i18n_labels.est_rtl(langue):
        css_langue = premium_base.css_arabe(document=True)
    return (f"<!doctype html>{racine}<head><meta charset='utf-8'>"
            f"<style>{css_base(jeton)}{css_langue}</style></head>"
            f"<body>{corps}</body></html>")


def rendre(html: str):
    """Le document WeasyPrint rendu (``.pages``, ``.write_pdf()``)."""
    from weasyprint import HTML
    return HTML(string=html, base_url=f"file://{_ICI}/").render()


def _boites(b, classes):
    el = getattr(b, "element", None)
    cls = (el.get("class") if el is not None and hasattr(el, "get") else "") or ""
    if any(c in cls.split() for c in classes):
        yield cls, b
    for c in getattr(b, "children", None) or []:
        yield from _boites(c, classes)


def socle_libre(doc, socle="sg1-socle", avant=("sg1-pointe", "sg1-meth", "sg1-faits")) -> bool:
    """B3 (revue 29/10) — le bloc ancré en bas de la couverture (position
    absolue, que ``_tient`` ne voit pas) reste SOUS le dernier bloc du flux :
    vrai quand aucune boîte ``avant`` ne descend sous le haut du socle."""
    if not doc.pages:
        return True
    page = doc.pages[0]._page_box
    socles = [b for _, b in _boites(page, (socle,))]
    if not socles:
        return True
    haut = min(b.position_y for b in socles)
    return all(b.position_y + b.margin_height() <= haut + 0.5
               for _, b in _boites(page, avant))


def tient(html: str, doc) -> bool:
    """Pages exactes, aucun texte sous la bande de pied (AMOT36) et socle
    de couverture libre (B3)."""
    from ..commercial.equip import _tient
    return _tient(html, doc) and socle_libre(doc, socle="sg1-socle")
