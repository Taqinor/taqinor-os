# flake8: noqa
"""quote_engine commercial — PAGE 1 (cover catégorie-aware).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``c1c-``.
"""
from . import categories


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

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    ref = d["ref"]
    date = d["date"]
    client_full = theme.titlecase_name(d.get("client_full") or d.get("client_name") or "Client")
    client_meta = theme.join_meta(d.get("client_addr", ""), d.get("client_city", ""),
                                  d.get("client_phone", ""))
    validity_days = d.get("validity_days", 30)

    cat = d.get("com_category")
    meta = categories.meta(cat)
    icon = meta["icon"]
    cat_label = meta["label"]
    accroche = meta["accroche"]

    kwc = _kwc_str(d.get("com_kwc"))
    economies = d.get("com_economies") or 0
    autoconso = d.get("com_autoconso")
    couverture = d.get("com_couverture")
    invest = d.get("_invest_ttc") or 0

    def kpi(val, unit, label):
        return (f'<td class="c1c-kpi"><div class="c1c-kv">{val}'
                f'<span class="c1c-ku">{unit}</span></div>'
                f'<div class="c1c-kl">{label}</div></td>')

    kpis = kpi(kwc, "&nbsp;kWc", "Puissance crête")
    kpis += '<td class="c1c-kgap"></td>'
    if autoconso is not None:
        kpis += kpi(f"{round(autoconso)}", "&nbsp;%", "Autoconsommation")
        kpis += '<td class="c1c-kgap"></td>'
    if couverture is not None:
        kpis += kpi(f"{round(couverture)}", "&nbsp;%", "Couverture conso")
        kpis += '<td class="c1c-kgap"></td>'
    kpis += kpi(fmt(economies), "&nbsp;MAD", "Économies / an")

    css = f"""
<style>
.c1c-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;
  position:relative;background:{paper};-weasy-hyphens:none;}}
.c1c-root *{{box-sizing:border-box;}}
.c1c-serif{{font-family:{f_display};}}
.c1c-hero{{background:{navy_900};padding:11mm 14mm 9mm 14mm;border-bottom:3px solid {gold};}}
.c1c-htop{{display:table;width:100%;}}
.c1c-hlogo{{display:table-cell;vertical-align:middle;}}
.c1c-hlogo img{{height:9mm;width:auto;}}
.c1c-hmeta{{display:table-cell;vertical-align:middle;text-align:right;color:#fff;}}
.c1c-rl{{font-size:6.5pt;letter-spacing:1.6px;text-transform:uppercase;color:{muted_2};}}
.c1c-rv{{font-size:12pt;font-weight:700;color:#fff;}}
.c1c-hd{{font-size:8pt;color:rgba(255,255,255,.72);margin-top:2px;}}
.c1c-pill{{display:inline-block;margin-top:5px;background:{gold};color:{navy_900};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:700;}}
.c1c-hbody{{margin-top:8mm;color:#fff;}}
.c1c-catrow{{display:table;}}
.c1c-caticon{{display:table-cell;vertical-align:middle;font-size:24pt;padding-right:10px;}}
.c1c-catlab{{display:table-cell;vertical-align:middle;}}
.c1c-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{gold};font-weight:700;}}
.c1c-title{{font-family:{f_display};font-size:23pt;line-height:1.05;margin-top:3px;}}
.c1c-acc{{font-size:10.5pt;color:rgba(255,255,255,.88);margin-top:8px;max-width:150mm;}}
.c1c-client{{padding:6mm 14mm 0 14mm;font-size:8.5pt;color:{muted};}}
.c1c-client b{{color:{ink};}}
.c1c-tag{{display:inline-block;margin-left:8px;background:{wash};border:1px solid {line};
  border-radius:20px;padding:2px 10px;font-size:7pt;font-weight:600;color:{navy};}}
.c1c-wrap{{padding:6mm 14mm 0 14mm;}}
.c1c-kpirow{{display:table;width:100%;border-spacing:0;}}
.c1c-kpi{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-left:4px solid {gold};border-radius:12px;padding:12px 14px;background:#fff;}}
.c1c-kgap{{display:table-cell;width:11px;}}
.c1c-kv{{font-family:{f_display};font-size:18pt;color:{navy};line-height:1;}}
.c1c-ku{{font-size:9pt;color:{muted};}}
.c1c-kl{{font-size:7pt;color:{muted};margin-top:3px;letter-spacing:.3px;}}
.c1c-note{{margin-top:12px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:10px 14px;font-size:8.5pt;color:{ink};line-height:1.45;}}
.c1c-note b{{color:{navy};}}
.c1c-inv{{margin-top:12px;display:table;width:100%;border:1px solid {line};
  border-radius:12px;background:{wash};padding:11px 16px;}}
.c1c-inv-l{{display:table-cell;vertical-align:middle;font-size:8.5pt;color:{muted};}}
.c1c-inv-v{{display:table-cell;vertical-align:middle;text-align:right;
  font-family:{f_display};font-size:20pt;color:{navy};}}
.c1c-inv-v span{{font-size:10pt;color:{muted};}}
</style>
"""

    html = f"""{css}
<div class="c1c-root">
  <div class="c1c-hero">
    <div class="c1c-htop">
      <div class="c1c-hlogo"><img src="data:image/png;base64,{logo_dark}" alt="{brand}"></div>
      <div class="c1c-hmeta">
        <div class="c1c-rl">Réf. devis</div>
        <div class="c1c-rv">{ref}</div>
        <div class="c1c-hd">{date}</div>
        <div class="c1c-pill">Validité {validity_days} jours</div>
      </div>
    </div>
    <div class="c1c-hbody">
      <div class="c1c-kicker">Proposition — Autoconsommation solaire commerciale</div>
      <div class="c1c-catrow">
        <div class="c1c-caticon">{icon}</div>
        <div class="c1c-catlab"><div class="c1c-serif c1c-title">{cat_label}</div></div>
      </div>
      <div class="c1c-acc">{accroche}</div>
    </div>
  </div>

  <div class="c1c-client">
    <b>{client_full}</b>
    {f'&nbsp;·&nbsp;{client_meta}' if client_meta else ''}
    <span class="c1c-tag">{cat_label}</span>
  </div>

  <div class="c1c-wrap">
    <div class="c1c-kpirow">{kpis}</div>
    <div class="c1c-note">
      L'installation vise l'<b>autoconsommation</b> : la valeur porte d'abord sur
      la consommation de <b>journée</b> de votre établissement. La <b>pointe</b>
      (soir/nuit) n'est sécurisée qu'avec un <b>stockage</b> — non promise sans batterie.
    </div>
    <div class="c1c-inv">
      <div class="c1c-inv-l">Investissement (TTC, clé en main)</div>
      <div class="c1c-inv-v">{fmt(invest)}<span>&nbsp;MAD</span></div>
    </div>
  </div>
</div>
"""
    return html
