# flake8: noqa
"""quote_engine commercial — PAGE 2 (équipements + totaux + bloc catégorie).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``c2-`` (+ ``c2b-`` for the category block CSS,
whose markup is emitted by ``categories.category_block``). RULE #4 : jamais de
prix_achat/marge — on ne rend que designation/quantité/PU TTC/Total TTC.
"""
from . import categories


def _num(v, default=0.0):
    try:
        f = float(v)
        return f if f == f else default
    except (TypeError, ValueError):
        return default


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]

    navy = C["navy"]
    gold = C["gold"]
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    ink = C.get("ink", "#1F2937")
    muted = C.get("muted", "#6B7280")
    muted_2 = C.get("muted_2", "#9BA3AE")
    line = C.get("line", "#E5E7EB")
    line_soft = C.get("line_soft", "#EFF1F4")
    wash = C.get("wash", "#F7F9FC")

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    items = [it for it in (d.get("all_items") or []) if _num(it.get("quantite")) > 0]
    rows = ""
    for it in items:
        qte = _num(it.get("quantite"))
        pu_ttc = _num(it.get("prix_unit_ttc"))
        if pu_ttc <= 0:  # repli : dérive du HT si le TTC manque
            pu_ttc = _num(it.get("prix_unit_ht")) * (1 + _num(it.get("taux_tva"), 20) / 100)
        total = round(pu_ttc * qte)
        marque = (it.get("marque") or "").strip()
        desig = it.get("designation") or ""
        m = f'<span class="c2-mq">{marque}</span>' if marque else ""
        rows += (
            f'<tr><td class="c2-d">{desig}{m}</td>'
            f'<td class="c2-q">{qte:g}</td>'
            f'<td class="c2-p">{fmt(round(pu_ttc))}</td>'
            f'<td class="c2-t">{fmt(total)}</td></tr>')

    tot = d.get("totaux_all") or {}
    ht_brut = _num(tot.get("ht_brut"))
    remise = _num(tot.get("remise"))
    ht_net = _num(tot.get("ht_net"))
    tva = _num(tot.get("tva"))
    ttc = _num(tot.get("ttc")) or d.get("_invest_ttc") or 0
    remise_row = (
        f'<tr><td>Remise</td><td class="c2-tr">- {fmt(round(remise))} MAD</td></tr>'
        if remise > 0 else "")

    # QX50 — ligne injection 82-21 (rendue SEULEMENT si l'étude la porte, avec
    # sa mention obligatoire ; jamais affichée sans la mention).
    _etude = d.get("etude") or {}
    _inj = _num(_etude.get("injection_dh_an"))
    injection_html = ""
    if _inj and _inj > 0:
        injection_html = (
            '<div class="c2-inj"><b>+ ' + fmt(round(_inj)) + ' MAD/an</b> — '
            'surplus injecté (loi 82-21, net des frais réseau, plafond 20 % de la '
            'production). <span class="c2-inj-m">Tarif ANRE 03/2026-02/2027, '
            'plafond en révision.</span></div>')

    block = categories.category_block(d.get("com_category"), d.get("etude"), C, fmt)

    css = f"""
<style>
.c2-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.c2-root *{{box-sizing:border-box;}}
.c2-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.c2-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.c2-tbl{{width:100%;border-collapse:collapse;margin-top:9px;font-size:8.5pt;}}
.c2-tbl th{{text-align:left;color:{muted};font-size:7pt;text-transform:uppercase;
  letter-spacing:.4px;padding:6px 8px;border-bottom:1px solid {line};}}
.c2-tbl th.c2-rr{{text-align:right;}}
.c2-tbl td{{padding:6px 8px;border-bottom:1px solid {line_soft};vertical-align:top;}}
.c2-d{{color:{ink};}}
.c2-mq{{display:block;font-size:7pt;color:{muted_2};margin-top:1px;}}
.c2-q,.c2-p,.c2-t{{text-align:right;white-space:nowrap;}}
.c2-t{{font-weight:700;color:{navy};}}
.c2-tot{{margin-top:10px;display:table;width:100%;}}
.c2-tot-sp{{display:table-cell;width:55%;}}
.c2-tot-box{{display:table-cell;width:45%;}}
.c2-tot-tbl{{width:100%;font-size:8.5pt;border-collapse:collapse;}}
.c2-tot-tbl td{{padding:4px 8px;}}
.c2-tot-tbl td:last-child{{text-align:right;white-space:nowrap;}}
.c2-tr{{text-align:right;}}
.c2-tot-ttc td{{border-top:2px solid {navy};font-family:{f_display};font-size:13pt;
  color:{navy};padding-top:6px;}}
/* Bloc catégorie (markup émis par categories.category_block) */
.c2b{{margin-top:14px;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;background:{wash};padding:11px 14px;}}
.c2b-h{{font-size:9pt;font-weight:700;color:{navy};}}
.c2b-badge{{display:inline-block;margin-left:8px;background:{green_bg};color:{green};
  border-radius:20px;padding:2px 9px;font-size:7pt;font-weight:700;}}
.c2b-body{{margin-top:6px;}}
.c2b-meta{{font-size:7.5pt;color:{muted};margin-bottom:5px;}}
.c2b-li{{font-size:8pt;color:{ink};line-height:1.4;margin-top:4px;padding-left:12px;position:relative;}}
.c2b-li:before{{content:'';position:absolute;left:0;top:5px;width:6px;height:6px;
  border-radius:50%;background:{green};}}
.c2b-li b{{color:{navy};}}
.c2b-tbl{{width:100%;border-collapse:collapse;margin-top:4px;font-size:8pt;}}
.c2b-tbl td{{padding:4px 6px;border-bottom:1px solid {line_soft};vertical-align:top;}}
.c2b-tbl td:first-child{{font-weight:700;color:{navy};white-space:nowrap;width:32%;}}
.c2-inj{{margin-top:12px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:{green_bg};padding:9px 14px;font-size:8pt;color:{ink};line-height:1.4;}}
.c2-inj b{{color:{green};}}
.c2-inj-m{{color:{muted};font-size:7pt;}}
</style>
"""

    html = f"""{css}
<div class="c2-root">
  <div class="c2-kicker">Votre installation</div>
  <div class="c2-sec">Équipements &amp; investissement</div>

  <table class="c2-tbl">
    <tr><th>Désignation</th><th class="c2-rr">Qté</th><th class="c2-rr">P.U. TTC</th><th class="c2-rr">Total TTC</th></tr>
    {rows}
  </table>

  <div class="c2-tot">
    <div class="c2-tot-sp"></div>
    <div class="c2-tot-box">
      <table class="c2-tot-tbl">
        <tr><td>Sous-total HT</td><td>{fmt(round(ht_brut))} MAD</td></tr>
        {remise_row}
        <tr><td>Total HT</td><td>{fmt(round(ht_net))} MAD</td></tr>
        <tr><td>TVA</td><td>{fmt(round(tva))} MAD</td></tr>
        <tr class="c2-tot-ttc"><td>Total TTC</td><td>{fmt(round(ttc))} MAD</td></tr>
      </table>
    </div>
  </div>

  {injection_html}
  {block}
</div>
"""
    return html
