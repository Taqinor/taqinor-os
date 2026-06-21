# -*- coding: utf-8 -*-
# flake8: noqa
"""
quote_engine_v2 — PAGE 1 (cover + financial hook).

`build(ctx) -> str` returns the INNER HTML of one A4 page (210mm × 297mm).
NO `<div class="page">` wrapper, NO `<html>`, NO footer — the harness paints a
13mm footer at the very bottom, so all content here stays in the top ~283mm.

Design language (kept on-brand with the existing premium engine): dark-navy
hero, gold accents, ROI-green, DM Serif Display / Playfair headlines, DM Sans
body, generous whitespace, rounded 12px cards with 1px hairline borders.

Every class is prefixed `c1-` so it can never clash with pages 2/3.
Every money number goes through `ctx["fmt"]`; currency is MAD; language FR.
"""


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    logo_dark = ctx["logo_dark"]
    charts = ctx["charts"]
    hero_img = ctx.get("hero_img", "")

    # ── tokens ──────────────────────────────────────────────────────────────
    navy = C["navy"]
    navy_900 = C.get("navy_900", "#0F1E35")
    gold = C["gold"]
    gold_soft = C.get("gold_soft", "#FDF3E3")
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    ink = C.get("ink", "#1F2937")
    muted = C.get("muted", "#6B7280")
    muted_2 = C.get("muted_2", "#9BA3AE")
    line = C.get("line", "#E5E7EB")
    line_soft = C.get("line_soft", "#EEF1F5")
    paper = C.get("paper", "#FFFFFF")
    wash = C.get("wash", "#F7F9FC")

    f_display = fonts["display"]   # DM Serif Display
    f_serif = fonts["serif"]       # Playfair Display
    f_sans = fonts["sans"]         # DM Sans

    # ── data ────────────────────────────────────────────────────────────────
    ref = d["ref"]
    date = d["date"]
    client_full = d["client_full"]
    first_name = (client_full.split() or [client_full])[0]
    client_addr = d.get("client_addr", "")
    client_city = d.get("client_city", "")
    client_phone = d.get("client_phone", "")
    inst_type = d.get("inst_type", "")
    kwc = d["puissance_kwc"]
    nb_pan = d["nb_panneaux"]
    wp = d["watt_par_panneau"]
    prod_kwh = d["prod_kwh"]
    total_sans = d["total_sans"]
    total_avec = d["total_avec"]
    roi_s = d["roi_s"]
    roi_a = d["roi_a"]
    eco_a_ann = d["eco_a_ann"]
    annual_before = d["annual_before"]
    annual_after = d["annual_after"]
    coverage_pct = d["coverage_pct"]
    pct_cut = round((1 - annual_after / max(1, annual_before)) * 100)
    validity_days = d["validity_days"]
    sans_bullets = d.get("sans_bullets", []) or []
    avec_bullets = d.get("avec_bullets", []) or []

    kwc_str = f"{kwc:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    pkwc_sans = fmt(total_sans / kwc) if kwc else "—"
    pkwc_avec = fmt(total_avec / kwc) if kwc else "—"

    # check + arrow glyphs (inline SVG renders crisply in WeasyPrint)
    check = (f'<svg class="c1-chk" viewBox="0 0 14 14">'
             f'<circle cx="7" cy="7" r="7" fill="{green_bg}"/>'
             f'<path d="M4 7.2l2 2 4-4.4" stroke="{green}" stroke-width="1.6" '
             f'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    arrow = (f'<svg viewBox="0 0 28 16" class="c1-arrow">'
             f'<path d="M2 8h20M16 2l7 6-7 6" stroke="{gold}" stroke-width="2.4" '
             f'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')

    def bullets(items):
        items = items[:3]
        return "".join(
            f'<li>{check}<span>{b}</span></li>' for b in items
        )

    # ── Hero background: real installation photo + navy gradient overlay so
    # the logo, ref and "Bonjour …" stay readable. No photo -> flat navy. ─────
    if hero_img:
        hero_bg = (
            "linear-gradient(180deg,rgba(15,30,53,0.70) 0%,"
            "rgba(15,30,53,0.32) 42%,rgba(15,30,53,0.90) 100%),"
            "linear-gradient(100deg,rgba(15,30,53,0.85) 0%,"
            "rgba(15,30,53,0.38) 58%,rgba(15,30,53,0.12) 100%),"
            f"url('data:image/jpeg;base64,{hero_img}') center 38%/cover no-repeat"
        )
    else:
        hero_bg = navy_900

    # ── CSS (all classes prefixed c1-) ──────────────────────────────────────
    css = f"""
<style>
.c1-root{{font-family:'{f_sans}',sans-serif;color:{ink};width:210mm;
  height:297mm;position:relative;background:{paper};
  -webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.c1-root *{{box-sizing:border-box;}}
.c1-serif{{font-family:'{f_display}','{f_serif}',Georgia,serif;font-weight:400;}}
.c1-kicker{{font-size:7pt;letter-spacing:2.6px;font-weight:700;text-transform:uppercase;}}

/* ── HERO ──────────────────────────────────────────────────────────────── */
.c1-hero{{position:relative;background:{hero_bg};height:56mm;overflow:hidden;
  padding:9mm 14mm 0 14mm;}}
.c1-hero-glow{{position:absolute;top:-30px;right:-40px;width:300px;height:210px;
  background:radial-gradient(ellipse at 75% 18%,rgba(245,166,35,0.30) 0%,transparent 64%);
  pointer-events:none;}}
.c1-hero-top{{display:flex;align-items:flex-start;justify-content:space-between;
  position:relative;z-index:1;}}
.c1-logo{{height:9mm;width:auto;object-fit:contain;display:block;}}
.c1-hero-meta{{text-align:right;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,0.45);}}
.c1-hero-meta .c1-ref-l{{font-size:6.5pt;letter-spacing:1.5px;text-transform:uppercase;
  color:{muted_2};}}
.c1-hero-meta .c1-ref-v{{font-size:11.5pt;font-weight:700;color:#fff;margin-top:1px;
  letter-spacing:.3px;}}
.c1-hero-meta .c1-date{{font-size:8pt;color:rgba(255,255,255,0.72);margin-top:3px;}}
.c1-pill-gold{{display:inline-block;margin-top:6px;background:{gold};color:{navy_900};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:700;letter-spacing:.3px;}}
.c1-hero-body{{position:absolute;left:14mm;right:14mm;bottom:7mm;z-index:1;
  text-shadow:0 1px 6px rgba(0,0,0,0.40);}}
.c1-hero-kicker{{color:{gold};margin-bottom:6px;}}
.c1-hello{{font-size:30pt;color:#fff;line-height:1.0;letter-spacing:-0.5px;}}
.c1-sub{{font-size:11pt;color:rgba(255,255,255,0.82);margin-top:7px;font-weight:400;}}

/* ── CLIENT LINE ───────────────────────────────────────────────────────── */
.c1-client{{display:flex;align-items:center;gap:9px;padding:4.5mm 14mm 0 14mm;
  font-size:8.5pt;color:{muted};}}
.c1-client b{{color:{ink};font-weight:700;}}
.c1-dot{{color:{line};font-weight:700;}}
.c1-tag{{margin-left:auto;background:{wash};border:1px solid {line};border-radius:20px;
  padding:2px 10px;font-size:7pt;font-weight:600;color:{navy};letter-spacing:.3px;}}

/* ── MONEY HOOK ────────────────────────────────────────────────────────── */
.c1-wrap{{padding:4mm 14mm 0 14mm;}}
.c1-hook{{display:flex;gap:14px;align-items:stretch;}}
.c1-hook-left{{flex:1 1 0;min-width:0;border:1px solid {line};border-radius:12px;
  padding:13px 16px;background:#fff;display:flex;flex-direction:column;
  justify-content:center;}}
.c1-hook-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;}}
.c1-hook-eyebrow{{color:{muted};font-size:6.5pt;letter-spacing:2px;text-transform:uppercase;
  font-weight:700;}}
.c1-cut{{background:{gold};color:{navy_900};font-weight:700;font-size:9.5pt;
  padding:3px 11px;border-radius:20px;letter-spacing:.2px;white-space:nowrap;}}
.c1-cmp{{display:flex;align-items:center;gap:12px;}}
.c1-cmp-col{{flex:1 1 0;min-width:0;}}
.c1-cmp-lab{{font-size:7.5pt;color:{muted};margin-bottom:2px;}}
.c1-cmp-old{{font-family:'{f_display}','{f_serif}',serif;font-size:17pt;color:{muted_2};
  text-decoration:line-through;text-decoration-thickness:1.5px;line-height:1.0;
  white-space:nowrap;}}
.c1-cmp-old .c1-u{{font-size:8.5pt;letter-spacing:0;}}
.c1-cmp-new{{font-family:'{f_display}','{f_serif}',serif;font-size:25pt;color:{gold};
  line-height:1.0;white-space:nowrap;letter-spacing:-0.5px;}}
.c1-cmp-new .c1-u{{font-size:10pt;color:{gold};}}
.c1-arrow{{width:30px;height:18px;flex-shrink:0;}}
.c1-hook-right{{flex:0 0 40mm;border:1px solid {line};border-radius:12px;
  background:{wash};display:flex;flex-direction:column;align-items:center;
  justify-content:center;padding:8px 6px;}}
.c1-donut{{height:30mm;width:auto;display:block;}}
.c1-donut-cap{{font-size:7pt;color:{muted};text-align:center;line-height:1.25;
  margin-top:2px;max-width:34mm;}}
.c1-bill{{margin-top:11px;border:1px solid {line};border-radius:12px;background:#fff;
  padding:9px 14px 7px;}}
.c1-bill-head{{display:flex;align-items:baseline;justify-content:space-between;
  margin-bottom:3px;}}
.c1-bill-t{{font-size:7.5pt;font-weight:700;color:{navy};text-transform:uppercase;
  letter-spacing:.6px;}}
.c1-bill-leg{{font-size:6.5pt;color:{muted};}}
.c1-bill-leg .c1-sw{{display:inline-block;width:8px;height:8px;border-radius:2px;
  vertical-align:middle;margin:0 3px 0 8px;}}
.c1-bill img{{width:100%;height:auto;display:block;}}

/* ── KPI CHIPS ─────────────────────────────────────────────────────────── */
.c1-kpis{{display:flex;gap:12px;margin-top:11px;}}
.c1-kpi{{flex:1 1 0;min-width:0;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;padding:11px 13px;background:#fff;}}
.c1-kpi-v{{font-family:'{f_display}','{f_serif}',serif;font-size:17pt;color:{navy};
  line-height:1.0;}}
.c1-kpi-v .c1-u{{font-size:9pt;color:{muted};}}
.c1-kpi-l{{font-size:7pt;color:{muted};margin-top:3px;letter-spacing:.4px;}}

/* ── OPTION CARDS ──────────────────────────────────────────────────────── */
.c1-opts{{display:flex;gap:14px;margin-top:11px;}}
.c1-opt{{flex:1 1 0;min-width:0;border:1px solid {line};border-radius:12px;
  background:#fff;padding:15px 16px 14px;position:relative;display:flex;
  flex-direction:column;}}
.c1-opt.c1-reco{{border:1.5px solid {gold};background:#fff;}}
.c1-opt-head{{display:flex;align-items:flex-start;justify-content:space-between;
  margin-bottom:2px;}}
.c1-opt-k{{font-size:6.5pt;letter-spacing:2px;color:{gold};font-weight:700;
  text-transform:uppercase;}}
.c1-opt-name{{font-size:11.5pt;font-weight:700;color:{navy};margin-top:1px;}}
.c1-reco-pill{{background:{gold};color:{navy_900};border-radius:20px;padding:2px 9px;
  font-size:6.5pt;font-weight:700;letter-spacing:.4px;white-space:nowrap;}}
.c1-opt-price{{font-family:'{f_display}','{f_serif}',serif;font-size:24pt;color:{navy};
  line-height:1.0;margin-top:7px;letter-spacing:-0.5px;}}
.c1-opt-price .c1-u{{font-size:10pt;color:{muted};}}
.c1-opt-kwc{{font-size:7pt;color:{muted};margin-top:2px;}}
.c1-roi{{display:inline-flex;align-items:center;align-self:flex-start;gap:5px;
  background:{green_bg};color:{green};border-radius:20px;padding:3px 11px;
  font-size:8pt;font-weight:700;margin-top:8px;}}
.c1-roi svg{{width:11px;height:11px;}}
.c1-opt-hr{{height:1px;background:{line_soft};margin:11px 0 9px;}}
.c1-opt ul{{list-style:none;padding:0;margin:0;}}
.c1-opt li{{display:flex;align-items:flex-start;gap:7px;font-size:8pt;
  color:{ink};line-height:1.4;margin-bottom:6px;}}
.c1-chk{{width:12px;height:12px;flex-shrink:0;margin-top:1px;}}
.c1-opt li span{{min-width:0;}}
.c1-note{{font-size:6.5pt;color:{muted_2};font-style:italic;margin-top:auto;
  padding-top:6px;}}
</style>
"""

    # ── HTML ────────────────────────────────────────────────────────────────
    html = f"""{css}
<div class="c1-root">

  <!-- HERO ─────────────────────────────────────────────────────────────── -->
  <div class="c1-hero">
    <div class="c1-hero-glow"></div>
    <div class="c1-hero-top">
      <img class="c1-logo" src="data:image/png;base64,{logo_dark}" alt="TAQINOR">
      <div class="c1-hero-meta">
        <div class="c1-ref-l">Réf. devis</div>
        <div class="c1-ref-v">{ref}</div>
        <div class="c1-date">{date}</div>
        <div class="c1-pill-gold">Validité {validity_days} jours</div>
      </div>
    </div>
    <div class="c1-hero-body">
      <div class="c1-kicker c1-hero-kicker">Proposition commerciale — Installation solaire</div>
      <div class="c1-serif c1-hello">Bonjour {first_name},</div>
      <div class="c1-sub">Voici votre proposition d'installation solaire.</div>
    </div>
  </div>

  <!-- CLIENT LINE ──────────────────────────────────────────────────────── -->
  <div class="c1-client">
    <b>{client_full}</b>
    <span class="c1-dot">·</span><span>{client_addr}, {client_city}</span>
    <span class="c1-dot">·</span><span>{client_phone}</span>
    <span class="c1-tag">{inst_type}</span>
  </div>

  <div class="c1-wrap">

    <!-- MONEY HOOK ─────────────────────────────────────────────────────── -->
    <div class="c1-hook">
      <div class="c1-hook-left">
        <div class="c1-hook-head">
          <div class="c1-hook-eyebrow">Ce que le solaire change pour vous</div>
          <div class="c1-cut">&minus;{pct_cut}&#8201;% sur votre facture</div>
        </div>
        <div class="c1-cmp">
          <div class="c1-cmp-col">
            <div class="c1-cmp-lab">Votre facture aujourd'hui</div>
            <div class="c1-cmp-old">≈&nbsp;{fmt(annual_before)}<span class="c1-u">&nbsp;MAD/an</span></div>
          </div>
          {arrow}
          <div class="c1-cmp-col">
            <div class="c1-cmp-lab">Avec TAQINOR</div>
            <div class="c1-cmp-new">≈&nbsp;{fmt(annual_after)}<span class="c1-u">&nbsp;MAD/an</span></div>
          </div>
        </div>
      </div>
      <div class="c1-hook-right">
        <img class="c1-donut" src="{charts['coverage']}" alt="Couverture">
        <div class="c1-donut-cap">de votre consommation<br>couverte par le solaire</div>
      </div>
    </div>

    <!-- BILL CHART ─────────────────────────────────────────────────────── -->
    <div class="c1-bill">
      <div class="c1-bill-head">
        <div class="c1-bill-t">Votre facture mois par mois — avant / après</div>
        <div class="c1-bill-leg">
          <span class="c1-sw" style="background:#C2CCDA;"></span>aujourd'hui
          <span class="c1-sw" style="background:{gold};"></span>avec TAQINOR
        </div>
      </div>
      <img src="{charts['bill']}" alt="Facture mensuelle avant / après">
    </div>

    <!-- KPI CHIPS ──────────────────────────────────────────────────────── -->
    <div class="c1-kpis">
      <div class="c1-kpi">
        <div class="c1-kpi-v">{kwc_str}<span class="c1-u">&nbsp;kWc</span></div>
        <div class="c1-kpi-l">Puissance · {nb_pan} panneaux × {wp} W</div>
      </div>
      <div class="c1-kpi">
        <div class="c1-kpi-v">{fmt(prod_kwh)}<span class="c1-u">&nbsp;kWh/an</span></div>
        <div class="c1-kpi-l">Production estimée</div>
      </div>
      <div class="c1-kpi">
        <div class="c1-kpi-v">{fmt(eco_a_ann)}<span class="c1-u">&nbsp;MAD/an</span></div>
        <div class="c1-kpi-l">Économie estimée</div>
      </div>
    </div>

    <!-- OPTION CARDS ───────────────────────────────────────────────────── -->
    <div class="c1-opts">

      <div class="c1-opt">
        <div class="c1-opt-head">
          <div>
            <div class="c1-opt-k">Option 1</div>
            <div class="c1-opt-name">Sans batterie</div>
          </div>
        </div>
        <div class="c1-opt-price">{fmt(total_sans)}<span class="c1-u">&nbsp;MAD</span></div>
        <div class="c1-opt-kwc">soit {pkwc_sans} MAD/kWc · TTC</div>
        <div class="c1-roi">{_roi_svg(green)}Rentabilisé en {_yrs(roi_s)} ans</div>
        <div class="c1-opt-hr"></div>
        <ul>{bullets(sans_bullets)}</ul>
        <div class="c1-note">Détail &amp; équipement en page 2</div>
      </div>

      <div class="c1-opt c1-reco">
        <div class="c1-opt-head">
          <div>
            <div class="c1-opt-k">Option 2</div>
            <div class="c1-opt-name">Avec batterie</div>
          </div>
          <span class="c1-reco-pill">Recommandé</span>
        </div>
        <div class="c1-opt-price">{fmt(total_avec)}<span class="c1-u">&nbsp;MAD</span></div>
        <div class="c1-opt-kwc">soit {pkwc_avec} MAD/kWc · TTC</div>
        <div class="c1-roi">{_roi_svg(green)}Rentabilisé en {_yrs(roi_a)} ans</div>
        <div class="c1-opt-hr"></div>
        <ul>{bullets(avec_bullets)}</ul>
        <div class="c1-note">Détail &amp; équipement en page 2</div>
      </div>

    </div>
  </div>
</div>
"""
    return html


def _yrs(v):
    """ROI like 4.7 → '4,7' (FR decimal comma), 5.0 → '5'."""
    try:
        f = float(v)
    except Exception:
        return str(v)
    if f == int(f):
        return str(int(f))
    return f"{f:.1f}".replace(".", ",")


def _roi_svg(color):
    return (f'<svg viewBox="0 0 14 14" fill="none">'
            f'<path d="M2 10l3.2-3.6 2.4 2L12 3.6" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M9 3.6h3v3" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')
