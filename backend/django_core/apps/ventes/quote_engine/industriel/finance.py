# flake8: noqa
"""quote_engine industriel — PAGE 2 (cashflow 15 ans, payback, TRI).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``i2-``.

Hypothèse PRUDENTE et HONNÊTE : économies maintenues CONSTANTES (aucune escalade
tarifaire inventée). Le cashflow est l'intégrale de ces économies nettes ; le TRI
est un VRAI calcul (bisection) sur ce flux, pas un chiffre inventé.
"""

_HORIZON = 15  # ans


def irr_flat(invest, annual_net, years=_HORIZON):
    """TRI (%) d'un flux [-invest, net, net, …] sur ``years`` ans (bisection).
    Renvoie None si dégénéré. Aucune constante inventée : pure arithmétique."""
    try:
        invest = float(invest)
        annual_net = float(annual_net)
    except (TypeError, ValueError):
        return None
    if invest <= 0 or annual_net <= 0 or years <= 0:
        return None

    def npv(r):
        total = -invest
        for t in range(1, years + 1):
            total += annual_net / ((1 + r) ** t)
        return total

    lo, hi = -0.9, 5.0
    if npv(lo) < 0:
        return None  # pas de racine positive dans la plage
    if npv(hi) > 0:
        return None  # TRI > 500 % (invraisemblable) → on n'affiche pas
    for _ in range(80):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1e-6:
            break
        if v > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2 * 100, 1)


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
    blue = C.get("blue", "#2C5F8A")

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    invest = d.get("_invest_ttc") or 0
    economies = d.get("ind_economies") or 0
    om = d.get("ind_om_annuel")
    injection = d.get("ind_injection_dh")

    # Économie NETTE annuelle = économies d'autoconso (+ injection si calculée)
    # − O&M (si fourni). Rien d'inventé : chaque terme vient de l'étude/builder.
    net_annual = economies + (injection or 0) - (om or 0)

    payback = d.get("ind_payback")
    tri = irr_flat(invest, net_annual)

    # Table cashflow 15 ans (cumul net = t × net − invest).
    rows = ""
    breakeven = None
    for t in range(1, _HORIZON + 1):
        cumul = round(t * net_annual - invest)
        if breakeven is None and cumul >= 0:
            breakeven = t
        pos = cumul >= 0
        cls = "i2-pos" if pos else "i2-neg"
        star = ' class="i2-be"' if t == breakeven else ""
        rows += (
            f'<tr{star}><td class="i2-y">Année {t}</td>'
            f'<td class="i2-e">{fmt(round(net_annual))}</td>'
            f'<td class="i2-c {cls}">{fmt(cumul)}</td></tr>')

    payback_txt = (f"{payback:.1f}".replace(".", ",") + " ans"
                   if isinstance(payback, (int, float)) else "—")
    tri_txt = (f"{tri:.1f}".replace(".", ",") + " %"
               if isinstance(tri, (int, float)) else "—")
    be_txt = (f"Année {breakeven}" if breakeven else "> 15 ans")

    # Ligne injection 82-21 — rendue UNIQUEMENT si l'étude la porte (QX50).
    injection_row = ""
    if injection:
        injection_row = (
            f'<div class="i2-inj">'
            f'<b>+ {fmt(round(injection))} MAD/an</b> — surplus injecté (loi 82-21, '
            f'net des frais réseau, plafond 20 % de la production). '
            f'<span class="i2-mini">Tarif ANRE 03/2026-02/2027, plafond en révision.</span>'
            f'</div>')

    om_txt = (f"O&amp;M déduit : {fmt(round(om))} MAD/an" if om
              else "O&amp;M (nettoyage, supervision) : inclus dans les économies nettes")

    css = f"""
<style>
.i2-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.i2-root *{{box-sizing:border-box;}}
.i2-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.i2-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.i2-lead{{font-size:8.5pt;color:{muted};margin-top:4px;}}
.i2-kpis{{display:table;width:100%;margin-top:11px;border-spacing:0;}}
.i2-kpi{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-radius:12px;padding:12px 14px;background:{wash};}}
.i2-kgap{{display:table-cell;width:12px;}}
.i2-kpi.i2-hi{{border-left:4px solid {gold};background:#fff;}}
.i2-kv{{font-family:{f_display};font-size:20pt;color:{navy};line-height:1;}}
.i2-kl{{font-size:7.5pt;color:{muted};margin-top:4px;}}
.i2-inj{{margin-top:11px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:{green_bg};padding:9px 14px;font-size:8pt;color:{ink};}}
.i2-inj b{{color:{green};}}
.i2-mini{{color:{muted};font-size:7pt;}}
.i2-cfhead{{margin-top:13px;font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};}}
.i2-tbl{{width:100%;border-collapse:collapse;margin-top:7px;font-size:8pt;}}
.i2-tbl th{{text-align:left;color:{muted};font-size:7pt;text-transform:uppercase;
  letter-spacing:.4px;padding:5px 8px;border-bottom:1px solid {line};}}
.i2-tbl th.i2-r,.i2-tbl td.i2-e,.i2-tbl td.i2-c{{text-align:right;}}
.i2-tbl td{{padding:4px 8px;border-bottom:1px solid {line_soft};}}
.i2-y{{color:{ink};}}
.i2-e{{color:{muted};}}
.i2-c{{font-weight:700;}}
.i2-pos{{color:{green};}}
.i2-neg{{color:{muted_2};}}
.i2-be td{{background:{green_bg};}}
.i2-be .i2-y{{font-weight:700;color:{navy};}}
.i2-foot{{margin-top:10px;font-size:7.5pt;color:{muted};line-height:1.4;}}
.i2-foot b{{color:{navy};}}
</style>
"""

    html = f"""{css}
<div class="i2-root">
  <div class="i2-kicker">Analyse financière</div>
  <div class="i2-sec">Rentabilité sur {_HORIZON} ans</div>
  <div class="i2-lead">Hypothèse prudente : économies maintenues constantes (hors inflation tarifaire, qui les augmenterait).</div>

  <div class="i2-kpis">
    <div class="i2-kpi i2-hi"><div class="i2-kv">{fmt(round(net_annual))}</div>
      <div class="i2-kl">Économie nette / an (MAD)</div></div>
    <div class="i2-kgap"></div>
    <div class="i2-kpi i2-hi"><div class="i2-kv">{be_txt}</div>
      <div class="i2-kl">Point mort (cumul ≥ 0)</div></div>
    <div class="i2-kgap"></div>
    <div class="i2-kpi i2-hi"><div class="i2-kv">{tri_txt}</div>
      <div class="i2-kl">TRI sur {_HORIZON} ans</div></div>
  </div>

  {injection_row}

  <div class="i2-cfhead">Cashflow cumulé</div>
  <table class="i2-tbl">
    <tr><th>Période</th><th class="i2-r">Économie nette</th><th class="i2-r">Cumul net (MAD)</th></tr>
    {rows}
  </table>

  <div class="i2-foot">
    <b>Payback</b> (retour d'investissement) ≈ {payback_txt}. {om_txt}.
    Le TRI est calculé sur le flux d'économies ci-dessus (méthode actuarielle) ;
    aucune escalade tarifaire n'est supposée. Chiffres indicatifs, hors financement.
  </div>
</div>
"""
    return html
