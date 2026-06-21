# flake8: noqa
"""Agricole — PAGE 3 (water yield + PV production charts + equipment list).
Returns INNER HTML of one A4 page. Classes a3-*."""
from __future__ import annotations


def _short(text, n=78):
    t = " ".join((text or "").split())
    return (t[: n - 1] + "…") if len(t) > n else t


def build(ctx) -> str:
    from . import theme
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]; charts = ctx["charts"]

    navy = C["navy"]; gold = C["gold"]; green = C["green"]; water = C["water"]
    ink = C["ink"]; muted = C["muted"]; muted_2 = C["muted_2"]; line = C["line"]
    line_soft = C["line_soft"]; wash = C["wash"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]

    has_water = d.get("has_water")
    show_water = d.get("show_water_yield", True) and has_water
    annual_m3 = d.get("annual_m3") or 0
    prod_kwh = d.get("prod_kwh_year") or 0
    totaux = d.get("totaux_all") or {}
    items = [it for it in (d.get("all_items") or []) if (it.get("quantite") or 0) > 0]

    # ── charts row ───────────────────────────────────────────────────────────
    chart_cards = []
    if show_water:
        chart_cards.append(
            f'<div class="a3-chart"><div class="a3-ch-head">'
            f'<div class="a3-ch-t">Eau livrée mois par mois</div>'
            f'<div class="a3-ch-s">≈ {fmt(annual_m3)} m³/an</div></div>'
            f'<img src="{charts["water"]}" alt="Eau par mois"></div>')
    if prod_kwh > 0:
        chart_cards.append(
            f'<div class="a3-chart"><div class="a3-ch-head">'
            f'<div class="a3-ch-t">Production solaire</div>'
            f'<div class="a3-ch-s">≈ {fmt(prod_kwh)} kWh/an</div></div>'
            f'<img src="{charts["production"]}" alt="Production par mois"></div>')
    charts_html = (f'<div class="a3-charts">{"".join(chart_cards)}</div>'
                   if chart_cards else "")

    # ── equipment table ──────────────────────────────────────────────────────
    rows = []
    for it in items:
        q = it.get("quantite") or 0
        q_txt = str(int(q)) if float(q) == int(q) else fmt_dec(q)
        pu = it.get("prix_unit_ht") or 0
        tot = q * pu
        marque = (it.get("marque") or "").strip()
        desc = _short(it.get("description") or "", 64)
        gar = (it.get("garantie") or "").strip()
        sub_bits = []
        if desc:
            sub_bits.append(desc)
        if gar:
            sub_bits.append(f"Garantie {gar}")
        sub = (f'<div class="a3-rd">{" · ".join(sub_bits)}</div>' if sub_bits else "")
        rows.append(
            f'<tr><td class="a3-td-d"><div class="a3-rn">{it.get("designation","")}</div>'
            f'{f"<div class=\"a3-rm\">{marque}</div>" if marque else ""}{sub}</td>'
            f'<td class="a3-td-q">{q_txt}</td>'
            f'<td class="a3-td-n">{fmt(pu)}</td>'
            f'<td class="a3-td-n">{fmt(tot)}</td></tr>')
    ht_brut = totaux.get("ht_brut") or 0
    table_html = (
        f'<table class="a3-tbl"><thead><tr>'
        f'<th class="a3-th-d">Désignation</th><th class="a3-th-q">Qté</th>'
        f'<th class="a3-th-n">P.U. HT</th><th class="a3-th-n">Total HT</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody>'
        f'<tfoot><tr><td colspan="3" class="a3-tf-l">Sous-total HT</td>'
        f'<td class="a3-tf-v">{fmt(ht_brut)} MAD</td></tr></tfoot></table>')

    css = f"""
<style>
.a3-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;background:#fff;
  padding:14mm 14mm 0;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a3-root *{{box-sizing:border-box;}}
.a3-kicker{{font-size:7pt;letter-spacing:2.4px;text-transform:uppercase;color:{gold};font-weight:700;}}
.a3-title{{font-family:{f_serif};font-weight:700;font-size:23pt;color:{navy};line-height:1.04;margin:3px 0 0;}}
.a3-intro{{font-size:9pt;color:{muted};margin-top:5px;line-height:1.4;}}
.a3-charts{{display:flex;gap:12px;margin-top:12px;}}
.a3-chart{{flex:1 1 0;min-width:0;border:1px solid {line};border-radius:12px;background:#fff;padding:10px 13px;}}
.a3-ch-head{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:4px;}}
.a3-ch-t{{font-size:8.4pt;font-weight:700;color:{navy};}}
.a3-ch-s{{font-size:8.4pt;font-weight:700;color:{water};}}
.a3-chart img{{width:100%;height:auto;display:block;}}
.a3-eq-h{{font-family:{f_serif};font-weight:700;font-size:13pt;color:{navy};margin:15px 0 8px;}}
.a3-tbl{{width:100%;border-collapse:collapse;border:1px solid {line};border-radius:12px;overflow:hidden;}}
.a3-tbl thead th{{background:{navy};color:#fff;font-size:7.4pt;font-weight:700;text-transform:uppercase;
  letter-spacing:.05em;padding:8px 12px;text-align:left;}}
.a3-th-q{{text-align:center !important;}}
.a3-th-n{{text-align:right !important;}}
.a3-tbl tbody td{{padding:9px 12px;border-bottom:1px solid {line_soft};vertical-align:top;font-size:8.6pt;}}
.a3-rn{{font-weight:700;color:{ink};}}
.a3-rm{{font-size:7.4pt;color:{gold};font-weight:700;margin-top:1px;}}
.a3-rd{{font-size:7.4pt;color:{muted};margin-top:2px;line-height:1.3;}}
.a3-td-q{{text-align:center;color:{ink};white-space:nowrap;}}
.a3-td-n{{text-align:right;color:{ink};white-space:nowrap;font-variant-numeric:tabular-nums;}}
.a3-tbl tfoot td{{padding:10px 12px;background:{wash};font-weight:700;font-size:9pt;}}
.a3-tf-l{{text-align:right;color:{navy};}}
.a3-tf-v{{text-align:right;color:{navy};white-space:nowrap;}}
.a3-note{{font-size:7.6pt;color:{muted_2};margin-top:8px;font-style:italic;}}
</style>
"""
    intro = ("Le volume d'eau pompé suit le soleil et la saison d'irrigation — fort l'été, "
             "réduit l'hiver. Voici l'estimation, mois par mois." if show_water
             else "Production solaire estimée de votre installation, mois par mois.")
    html = f"""{css}
<div class="a3-root">
  <div class="a3-kicker">Production & équipement</div>
  <div class="a3-title">Ce que votre installation délivre</div>
  <div class="a3-intro">{intro}</div>
  {charts_html}
  <div class="a3-eq-h">Équipement proposé</div>
  {table_html}
  <div class="a3-note">Prix unitaires HT. Détail des prix (remise, TVA, total TTC) et analyse financière en page suivante.
    Fiches techniques sur taqinor.ma/produits.</div>
</div>
"""
    return html
