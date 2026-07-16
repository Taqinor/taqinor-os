# flake8: noqa
"""quote_engine industriel — PAGE 1 (CFO cover : baseline énergétique + KPIs).

``build(ctx) -> str`` returns the INNER HTML of one A4 page. NO page wrapper, NO
footer (the harness paints the footer). CSS tables only (never flex — WeasyPrint;
see quote_engine/RENDERING_NOTES.md). Classes prefixed ``i1-``.
"""

_MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def _kwc_str(kwc):
    try:
        return f"{float(kwc):.2f}".rstrip("0").rstrip(".").replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    logo_dark = ctx["logo_dark"]
    theme = ctx["theme"]
    ident = ctx.get("ident") or {}
    brand = ident.get("brand_name") or "TAQINOR"

    navy = C["navy"]
    navy_900 = C.get("navy_900", "#0F1E35")
    gold = C["gold"]
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    ink = C.get("ink", "#1F2937")
    muted = C.get("muted", "#6B7280")
    muted_2 = C.get("muted_2", "#9BA3AE")
    line = C.get("line", "#E5E7EB")
    paper = C.get("paper", "#FFFFFF")
    wash = C.get("wash", "#F7F9FC")
    blue = C.get("blue", "#2C5F8A")

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    ref = d["ref"]
    date = d["date"]
    client_full = theme.titlecase_name(d.get("client_full") or d.get("client_name") or "Client")
    client_meta = theme.join_meta(d.get("client_addr", ""), d.get("client_city", ""),
                                  d.get("client_phone", ""))
    validity_days = d.get("validity_days", 30)

    kwc = _kwc_str(d.get("ind_kwc"))
    prod = d.get("ind_prod")
    conso = d.get("ind_conso")
    autoconso = d.get("ind_autoconso")
    couverture = d.get("ind_couverture")
    economies = d.get("ind_economies") or 0
    invest = d.get("_invest_ttc") or 0

    bills = [float(b or 0) for b in (d.get("factures_mensuelles") or [])][:12]
    while len(bills) < 12:
        bills.append(0.0)
    annual_bill = round(sum(bills))
    avg_bill = round(annual_bill / 12) if annual_bill else 0
    bmax = max(bills) or 1.0

    # Barres CSS (hauteurs en mm — déterministes, jamais de % dans une cellule).
    bar_cells = ""
    for i, b in enumerate(bills):
        h = round(b / bmax * 26.0, 1)
        bar_cells += (
            f'<td class="i1-bc"><div class="i1-bar" style="height:{h}mm"></div>'
            f'<div class="i1-mn">{_MONTHS[i]}</div></td>')

    # KPI (autoconso/couverture omis proprement si non calculés).
    def kpi(val, unit, label):
        return (f'<td class="i1-kpi"><div class="i1-kv">{val}'
                f'<span class="i1-ku">{unit}</span></div>'
                f'<div class="i1-kl">{label}</div></td>')

    kpis = kpi(kwc, "&nbsp;kWc", f"Puissance crête")
    kpis += '<td class="i1-kgap"></td>'
    if autoconso is not None:
        kpis += kpi(f"{round(autoconso)}", "&nbsp;%", "Autoconsommation")
        kpis += '<td class="i1-kgap"></td>'
    if couverture is not None:
        kpis += kpi(f"{round(couverture)}", "&nbsp;%", "Couverture conso")
        kpis += '<td class="i1-kgap"></td>'
    kpis += kpi(fmt(economies), "&nbsp;MAD", "Économies / an")

    conso_line = (f"Consommation ≈ {fmt(round(conso))} kWh/an" if conso
                  else "Consommation à confirmer (facture 12 mois)")
    prod_line = (f"Production estimée ≈ {fmt(round(prod))} kWh/an" if prod else "")

    css = f"""
<style>
.i1-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;
  position:relative;background:{paper};-weasy-hyphens:none;}}
.i1-root *{{box-sizing:border-box;}}
.i1-serif{{font-family:{f_display};}}
.i1-hero{{background:{navy_900};padding:11mm 14mm 9mm 14mm;border-bottom:3px solid {gold};}}
.i1-htop{{display:table;width:100%;}}
.i1-hlogo{{display:table-cell;vertical-align:middle;}}
.i1-hlogo img{{height:9mm;width:auto;}}
.i1-hmeta{{display:table-cell;vertical-align:middle;text-align:right;color:#fff;}}
.i1-rl{{font-size:6.5pt;letter-spacing:1.6px;text-transform:uppercase;color:{muted_2};}}
.i1-rv{{font-size:12pt;font-weight:700;color:#fff;}}
.i1-hd{{font-size:8pt;color:rgba(255,255,255,.72);margin-top:2px;}}
.i1-pill{{display:inline-block;margin-top:5px;background:{gold};color:{navy_900};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:700;}}
.i1-hbody{{margin-top:9mm;color:#fff;}}
.i1-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{gold};font-weight:700;}}
.i1-title{{font-family:{f_display};font-size:26pt;line-height:1.05;margin-top:5px;}}
.i1-sub{{font-size:10.5pt;color:rgba(255,255,255,.85);margin-top:6px;}}
.i1-client{{padding:6mm 14mm 0 14mm;font-size:8.5pt;color:{muted};}}
.i1-client b{{color:{ink};}}
.i1-tag{{display:inline-block;margin-left:8px;background:{wash};border:1px solid {line};
  border-radius:20px;padding:2px 10px;font-size:7pt;font-weight:600;color:{navy};}}
.i1-wrap{{padding:5mm 14mm 0 14mm;}}
.i1-sec{{font-family:{f_serif};font-weight:700;font-size:14pt;color:{navy};}}
.i1-card{{border:1px solid {line};border-radius:14px;background:#fff;padding:12px 16px;margin-top:9px;}}
.i1-baserow{{display:table;width:100%;}}
.i1-basecell{{display:table-cell;vertical-align:middle;}}
.i1-big{{font-family:{f_display};font-size:30pt;color:{navy};line-height:1;}}
.i1-big span{{font-size:12pt;color:{muted};}}
.i1-basel{{font-size:8pt;color:{muted};margin-top:3px;}}
.i1-bars{{width:100%;height:30mm;border-spacing:3px 0;margin-top:6px;}}
.i1-bc{{vertical-align:bottom;text-align:center;}}
.i1-bar{{width:100%;background:linear-gradient(180deg,{blue},{navy});border-radius:3px 3px 0 0;}}
.i1-mn{{font-size:6pt;color:{muted_2};margin-top:2px;}}
.i1-kpirow{{display:table;width:100%;margin-top:11px;border-spacing:0;}}
.i1-kpi{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-left:4px solid {gold};border-radius:12px;padding:11px 13px;background:#fff;}}
.i1-kgap{{display:table-cell;width:11px;}}
.i1-kv{{font-family:{f_display};font-size:17pt;color:{navy};line-height:1;}}
.i1-ku{{font-size:9pt;color:{muted};}}
.i1-kl{{font-size:7pt;color:{muted};margin-top:3px;letter-spacing:.3px;}}
.i1-note{{margin-top:11px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:9px 14px;font-size:8pt;color:{ink};line-height:1.4;}}
.i1-note b{{color:{navy};}}
.i1-inv{{margin-top:11px;display:table;width:100%;border:1px solid {line};
  border-radius:12px;background:{wash};padding:10px 16px;}}
.i1-inv-l{{display:table-cell;vertical-align:middle;font-size:8.5pt;color:{muted};}}
.i1-inv-v{{display:table-cell;vertical-align:middle;text-align:right;
  font-family:{f_display};font-size:19pt;color:{navy};}}
.i1-inv-v span{{font-size:10pt;color:{muted};}}
</style>
"""

    html = f"""{css}
<div class="i1-root">
  <div class="i1-hero">
    <div class="i1-htop">
      <div class="i1-hlogo"><img src="data:image/png;base64,{logo_dark}" alt="{brand}"></div>
      <div class="i1-hmeta">
        <div class="i1-rl">Réf. devis</div>
        <div class="i1-rv">{ref}</div>
        <div class="i1-hd">{date}</div>
        <div class="i1-pill">Validité {validity_days} jours</div>
      </div>
    </div>
    <div class="i1-hbody">
      <div class="i1-kicker">Proposition — Autoconsommation solaire industrielle</div>
      <div class="i1-serif i1-title">Réduire votre coût de l'énergie</div>
      <div class="i1-sub">Analyse de rentabilité (CFO) — baseline, cashflow et payback.</div>
    </div>
  </div>

  <div class="i1-client">
    <b>{client_full}</b>
    {f'&nbsp;·&nbsp;{client_meta}' if client_meta else ''}
    <span class="i1-tag">{d.get('inst_type','Industrielle')}</span>
  </div>

  <div class="i1-wrap">
    <div class="i1-sec">Baseline énergétique — 12 mois</div>
    <div class="i1-card">
      <div class="i1-baserow">
        <div class="i1-basecell">
          <div class="i1-big">{fmt(annual_bill)}<span>&nbsp;MAD/an</span></div>
          <div class="i1-basel">Facture électrique actuelle · ≈ {fmt(avg_bill)} MAD/mois</div>
          <div class="i1-basel">{conso_line}{(' · ' + prod_line) if prod_line else ''}</div>
        </div>
      </div>
      <table class="i1-bars"><tr>{bar_cells}</tr></table>
    </div>

    <div class="i1-kpirow">{kpis}</div>

    <div class="i1-note">
      L'installation vise l'<b>autoconsommation</b> : la valeur porte d'abord sur
      les <b>heures pleines</b> (production en journée). La <b>pointe</b> (soir/nuit)
      n'est sécurisée qu'avec un <b>stockage</b> — non promise ici sans batterie.
    </div>

    <div class="i1-inv">
      <div class="i1-inv-l">Investissement (TTC, clé en main)</div>
      <div class="i1-inv-v">{fmt(invest)}<span>&nbsp;MAD</span></div>
    </div>
  </div>
</div>
"""
    return html
