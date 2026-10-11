# flake8: noqa
"""Residential render harness — assembles the 3 page modules into one A4 PDF.
Driven by `residential.renderer` from the single quote engine."""
from __future__ import annotations
import re
from pathlib import Path

from . import theme
from . import charts as charts_mod
from . import cover, options, trust
from .. import i18n_labels
from ..premium_base import build_ctx as _ctx_socle

# QRES62 — joints élastiques : marqueurs inertes posés par les gabarits de
# page ; le second passage de rendu les remplace par des espaceurs
# dimensionnés d'après le vide MESURÉ de chaque page.
_QJ_RE = re.compile(r'<div class="qj" data-w="(\d+)"></div>')


def build_ctx(data: dict, compact_p3: bool = False) -> dict:
    # QX4 — identité société (multi-tenant) résolue UNE fois et partagée par
    # toutes les pages. Chaque littéral d'identité (footer, bande légale,
    # « Pourquoi … », signature, cover, liens) lit ``ident`` et retombe sur le
    # littéral Taqinor historique quand le champ correspondant est vide → un
    # devis sans profil enrichi reste rendu strictement à l'identique.
    # Le socle (identité, palette, formats, polices, logo APDF4) est celui
    # de ``premium_base.build_ctx`` — UNE définition (check_duplicats).
    ctx = _ctx_socle(data)
    ctx.update({
        "hero_img": theme.hero_image_b64(data.get("puissance_kwc"),
                                         "residentiel"),
        "charts": charts_mod.build_all(data),
        # ERR114 — rythme vertical resserré de la page 3, demandé par le
        # renderer UNIQUEMENT après avoir MESURÉ un débordement réel.
        "compact_p3": bool(compact_p3),
    })
    return ctx


def _apply_elastic(inner: str, slack_mm: float) -> str:
    """QRES62 — remplace les joints ``.qj`` d'une page par des espaceurs
    proportionnels à leur poids ``data-w`` (somme des poids ≈ 100), pour un
    total de ``slack_mm`` millimètres. ``slack_mm`` ≤ 0 → joints retirés
    (page identique au premier passage)."""
    weights = [int(w) for w in _QJ_RE.findall(inner)]
    if not weights:
        return inner
    total_w = sum(weights) or 1

    def _sub(m):
        if slack_mm <= 0:
            return ""
        h = slack_mm * int(m.group(1)) / total_w
        return f'<div style="height:{h:.1f}mm"></div>' if h >= 0.5 else ""

    return _QJ_RE.sub(_sub, inner)


def _wrap(inner: str, n: int, data: dict, ident: dict, total: int = 3,
          slack_mm: float = 0.0) -> str:
    # QX6 — le pied lit le NOMBRE RÉEL de pages rendues (jamais « / 3 » codé).
    foot = (theme.page_footer(data, ident, total_pages=total, traduire=True)
            .replace("{page}", str(n)))
    inner = _apply_elastic(inner, slack_mm)
    return f'<div class="page">{inner}{foot}</div>'


def calepinage_demande(data: dict) -> bool:
    """QJR666 (décision fondateur 01/10) — la planche de calepinage n'entre
    dans le document résidentiel que si le commercial l'a EXPLICITEMENT
    demandée (``include_calepinage = True`` au dialogue PDF : le builder pose
    alors ``include_calepinage_demande``) ET que la planche existe. L'AUTO
    (``None``) n'ajoute aucune page à un devis résidentiel. Une planche
    PÉRIMÉE (QJR522, ``layout_stale``) n'est jamais composée par le builder :
    pas de SVG, pas de page."""
    return bool(data.get("include_calepinage_demande")
                and data.get("calepinage_svg"))


def page_annexe_domicile(ctx) -> str:
    """AMOT23 — page « Droit de rétractation » du gabarit résidentiel : le
    corps légal partagé (``quote_engine.annexe_domicile``) dans le cadre de
    page résidentiel. AUCUN montant."""
    from ..annexe_domicile import corps_annexe_domicile
    d, C = ctx["d"], ctx["C"]
    serif = ctx["fonts"]["serif"]
    ident = ctx["ident"]
    corps = corps_annexe_domicile(
        ref=theme._esc(d.get("ref") or ""),
        vendeur=ident.get("brand_name") or "",
        couleurs={"navy": C["navy"], "texte": C["ink"], "muet": C["muted"],
                  "fond": C["paper"], "filet": C["line"]})
    return f"""
<div style="padding:11mm 14mm 0 14mm;">
  <div style="font-size:8.5pt;letter-spacing:.24em;text-transform:uppercase;color:{C['gold']};font-weight:700;">Annexe</div>
  <div style="font-family:{serif};font-weight:700;font-size:23pt;color:{C['navy']};line-height:1.04;margin:3px 0 8px;">Droit de rétractation</div>
  {corps}
</div>
"""


def page_calepinage(ctx) -> str:
    """QJR666 — page « Calepinage » du gabarit résidentiel : elle MET EN PAGE
    la planche cotée composée par le serveur (CAL171), sans rien dessiner ni
    mesurer. AUCUN montant (ni prix, ni marge) n'y figure."""
    d, C = ctx["d"], ctx["C"]
    serif = ctx["fonts"]["serif"]
    empreinte = (d.get("calepinage_empreinte") or "").strip()
    empreinte_html = (
        f'<div class="pc-emp">{theme._esc(empreinte)}</div>'
        if empreinte else "")
    return f"""
<style>
.pc-wrap {{ padding:11mm 14mm 0 14mm; }}
.pc-kicker {{ font-size:8.5pt; letter-spacing:.24em; text-transform:uppercase;
  color:{C['gold']}; font-weight:700; }}
.pc-title {{ font-family:{serif}; font-weight:700; font-size:23pt;
  color:{C['navy']}; line-height:1.04; margin:3px 0 8px; }}
.pc-intro {{ font-size:8.4pt; color:{C['muted']}; margin-bottom:9px; }}
.pc-planche {{ background:#fff; border:1px solid {C['line']};
  border-radius:11px; padding:6px; text-align:center; }}
.pc-planche svg {{ max-width:100%; height:auto; }}
.pc-note {{ margin-top:9px; font-size:7.2pt; color:{C['muted']};
  font-style:italic; }}
.pc-emp {{ margin-top:6px; font-size:6.6pt; color:{C['muted_2']}; }}
</style>
<div class="pc-wrap">
  <div class="pc-kicker">Pièce technique</div>
  <div class="pc-title">Calepinage</div>
  <div class="pc-intro">Implantation des modules relevée sur la toiture, à
    l'échelle portée par la planche. Les cotes sont mesurées sur la géométrie
    de la conception.</div>
  <div class="pc-planche">{d.get("calepinage_svg") or ""}</div>
  <div class="pc-note">Pièce technique jointe à la proposition. L'implantation
    définitive est confirmée à la visite technique ; seule la liste
    d'équipements du devis fait foi commercialement.</div>
  {empreinte_html}
</div>
"""


def build_html(data: dict, elastic: dict | None = None,
               compact_p3: bool = False) -> str:
    """``elastic`` (QRES62) : {numéro de page 1-based: mm de vide à répartir
    sur les joints de cette page}. None/absent → joints inertes (passe 1).

    ``compact_p3`` (ERR114) : resserre le rythme vertical de la page 3 sans en
    retirer le moindre bloc. Faux par défaut → HTML inchangé au bit près."""
    ctx = build_ctx(data, compact_p3=compact_p3)
    ident = ctx["ident"]
    # QRES17 — pagination variable : un devis chargé rend 2+ pages
    # « installation » (tableau découpé + page rentabilité dédiée) ; le pied
    # « Page n / N » lit le nombre RÉEL de pages (QX6).
    # QJR666 — la planche de calepinage DEMANDÉE s'intercale avant la page
    # d'engagement (du commercial au technique, puis à la signature), comme
    # dans le moteur legacy : une page de plus, seulement sur demande.
    planche = [page_calepinage(ctx)] if calepinage_demande(data) else []
    # AMOT23 (C-AMOT-021) — commande signée AU DOMICILE (BC, CAD122) : le
    # formulaire détachable de rétractation suit la page d'engagement, comme
    # dans le moteur legacy (même fonction ``annexe_domicile``).
    annexe = ([page_annexe_domicile(ctx)]
              if data.get("signe_au_domicile") else [])
    pages = ([cover.build(ctx)] + options.build_pages(ctx) + planche
             + [trust.build(ctx)] + annexe)
    total = len(pages)
    elastic = elastic or {}
    body = "".join(
        _wrap(inner, n, data, ident, total,
              slack_mm=float(elastic.get(n, 0.0)))
        for n, inner in enumerate(pages, start=1))
    # QJR666 — langue du document : un document français garde la racine
    # ``<html>`` d'origine (octet pour octet) ; en / ar portent ``lang``, et
    # l'arabe la police de ses libellés traduits.
    # APDF11 — l'arabe est une page RTL (``dir="rtl"`` sur la racine, comme le
    # commercial et l'industriel : WeasyPrint en tire l'alignement à droite et
    # l'ordre miroir des tableaux) ; fr et en gardent leur racine d'hier.
    langue = theme.langue_doc(data)
    racine = "<html>" if langue == "fr" else f'<html lang="{langue}">'
    if i18n_labels.est_rtl(langue):
        racine = f'<html lang="{langue}" dir="rtl">'
    return (f"<!doctype html>{racine}<head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}{theme.css_langue(data)}</style></head>"
            f"<body>{body}</body></html>")


def render_pdf(out_path, data: dict | None = None) -> str:
    from weasyprint import HTML
    if data is None:
        # QRES12 — le repli d'aperçu passe par le VRAI pipeline (fixture
        # sample_data + renderer._augment) ; l'ancien chemin importait une
        # fixture inexistante (ImportError latent) et sautait l'augmentation.
        from . import renderer, sample_data
        data = renderer._augment(sample_data.build())
    html = build_html(data)
    base = str(Path(__file__).resolve().parent)
    HTML(string=html, base_url=f"file://{base}/").write_pdf(str(out_path))
    return str(out_path)
