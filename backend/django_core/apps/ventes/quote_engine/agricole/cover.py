# flake8: noqa
"""Agricole — PAGE 1 (cover + at-a-glance). Returns the INNER HTML of one A4
page (no .page wrapper, no footer — the harness paints those). Classes a1-*."""
from __future__ import annotations


def _yrs(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return str(int(f)) if f == int(f) else f"{f:.1f}".replace(".", ",")


def build(ctx) -> str:
    from . import theme
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]; logo_dark = ctx["logo_dark"]; hero_img = ctx.get("hero_img", "")
    etude = d.get("etude") or {}

    navy = C["navy"]; navy_900 = C["navy_900"]; gold = C["gold"]; green = C["green"]
    green_bg = C["green_bg"]; water = C["water"]; water_bg = C["water_bg"]
    ink = C["ink"]; muted = C["muted"]; muted_2 = C["muted_2"]; line = C["line"]
    line_soft = C["line_soft"]; wash = C["wash"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]

    ref = d["ref"]; date = d["date"]
    client_full = theme.titlecase_name(d.get("client_full") or "Client")
    first = (client_full.split() or [client_full])[0]
    client_meta = theme.join_meta(d.get("client_addr", ""), d.get("client_phone", ""))
    validity = d.get("validity_days", 30)

    kwc = d.get("puissance_kwc") or 0
    nb_pan = d.get("nb_panneaux") or 0
    wp = d.get("watt_par_panneau") or 0
    pompe_cv = etude.get("pompe_cv"); pompe_kw = etude.get("pompe_kw")
    type_pompe = (etude.get("type_pompe") or "").lower()
    type_lbl = "immergée" if "immerg" in type_pompe else ("surface" if type_pompe else "")
    hmt = etude.get("hmt_m"); debit = etude.get("debit_hmt_m3h") or etude.get("debit_souhaite_m3h")
    m3j = etude.get("m3_jour")
    has_water = d.get("has_water")
    annual_saving = d.get("annual_saving") or 0
    payback = d.get("payback"); payback_diesel = d.get("payback_diesel")
    fda_amount = d.get("fda_amount") or 0; fda_pct = d.get("fda_pct") or 30
    co2_t = d.get("co2_t") or 0; trees = d.get("trees") or 0
    hectares = d.get("hectares_irrigable")
    current_fuel = d.get("current_fuel") or "butane"
    fuel_lbl = {"butane": "butane", "diesel": "diesel", "none": "carburant"}.get(current_fuel, "carburant")

    # ── hero number ──────────────────────────────────────────────────────────
    if has_water and m3j:
        hero_n = fmt(m3j); hero_u = "m³"; hero_t = "d'eau par jour"
    elif kwc:
        hero_n = fmt_dec(kwc); hero_u = "kWc"; hero_t = "de champ solaire"
    else:
        hero_n = "—"; hero_u = ""; hero_t = ""

    # ── at-a-glance cards (only those with data) ─────────────────────────────
    cards = []
    if debit and hmt:
        cards.append((fmt_dec(debit), "m³/h", f"Débit à {fmt(hmt)} m de HMT"))
    elif debit:
        cards.append((fmt_dec(debit), "m³/h", "Débit pompé"))
    if hmt:
        cards.append((fmt(hmt), "m", "Hauteur manométrique (HMT)"))
    if pompe_cv:
        sub = f"{fmt_dec(pompe_kw)} kW" if pompe_kw else "pompe"
        if type_lbl:
            sub += f" · {type_lbl}"
        cards.append((f"{theme.fmt_dec(pompe_cv)}", "CV", f"Pompe solaire · {sub}"))
    if kwc:
        cards.append((fmt_dec(kwc), "kWc", f"{nb_pan} panneaux × {wp} W"))
    if annual_saving > 0:
        cards.append((fmt(annual_saving), "MAD/an", f"Économie carburant · vs {fuel_lbl}"))
    if payback:
        cards.append((_yrs(payback), "ans", "Amortissement estimé"))
    if fda_amount > 0:
        cards.append((fmt(fda_amount), "MAD", f"Subvention FDA {fda_pct} % (a posteriori)"))
    cards = cards[:6]
    cards_html = "".join(
        f'<div class="a1-kpi"><div class="a1-kpi-v">{v}'
        f'<span class="a1-u"> {u}</span></div>'
        f'<div class="a1-kpi-l">{l}</div></div>'
        for v, u, l in cards)

    # tangibility line
    tang = ""
    if hectares:
        crop = (etude.get("crop") or "").strip()
        crop_txt = f" — {crop}" if crop else ""
        tang = (f'<div class="a1-tang"><b>≈ {fmt_dec(hectares)} hectares</b>'
                f' irrigués par votre installation solaire{crop_txt}.</div>')

    if hero_img:
        hero_bg = ("linear-gradient(180deg,rgba(15,30,53,0.68) 0%,"
                   "rgba(15,30,53,0.30) 42%,rgba(15,30,53,0.90) 100%),"
                   f"url('data:image/jpeg;base64,{hero_img}') center 40%/cover no-repeat")
    else:
        hero_bg = (f"linear-gradient(120deg,{navy_900} 0%,{navy} 60%,{C['water']} 160%)")

    css = f"""
<style>
.a1-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;
  position:relative;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a1-root *{{box-sizing:border-box;}}
.a1-serif{{font-family:{f_display};font-weight:400;}}
.a1-hero{{position:relative;background:{hero_bg};height:62mm;overflow:hidden;
  padding:9mm 14mm 0 14mm;border-bottom:2.5px solid {gold};}}
.a1-hero-glow{{position:absolute;top:-40px;right:-50px;width:320px;height:230px;
  background:radial-gradient(ellipse at 75% 18%,rgba(245,166,35,0.34) 0%,transparent 64%);}}
.a1-hero-top{{display:flex;align-items:flex-start;justify-content:space-between;
  position:relative;z-index:1;}}
.a1-logo{{height:15mm;width:auto;object-fit:contain;display:block;
  filter:drop-shadow(0 1px 4px rgba(0,0,0,.35));}}
.a1-meta{{text-align:right;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.45);}}
.a1-meta .l{{font-size:6.5pt;letter-spacing:1.5px;text-transform:uppercase;color:{muted_2};}}
.a1-meta .v{{font-size:11.5pt;font-weight:700;color:#fff;margin-top:1px;}}
.a1-meta .dt{{font-size:8pt;color:rgba(255,255,255,.72);margin-top:3px;}}
.a1-pill{{display:inline-block;margin-top:6px;background:{gold};color:{navy_900};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:700;}}
.a1-hero-body{{position:absolute;left:14mm;right:14mm;bottom:7mm;z-index:1;
  text-shadow:0 1px 6px rgba(0,0,0,.40);}}
.a1-kicker{{font-size:7pt;letter-spacing:2.6px;font-weight:700;text-transform:uppercase;color:{gold};}}
.a1-hello{{font-size:32pt;color:#fff;line-height:1.0;margin-top:6px;letter-spacing:-.5px;}}
.a1-sub{{font-size:11pt;color:rgba(255,255,255,.88);margin-top:6px;}}
.a1-client{{display:flex;align-items:center;gap:9px;padding:4.5mm 14mm 0;font-size:8.5pt;color:{muted};}}
.a1-client b{{color:{ink};font-weight:700;}}
.a1-dot{{color:{line};}}
.a1-tag{{margin-left:auto;background:{green_bg};border:1px solid #BFE6CB;border-radius:20px;
  padding:2px 11px;font-size:7pt;font-weight:700;color:{C['green_700']};letter-spacing:.3px;}}
.a1-wrap{{padding:4.5mm 14mm 0;}}
/* hero hook */
.a1-hook{{display:flex;gap:14px;align-items:stretch;}}
.a1-hook-l{{flex:1 1 0;border:1px solid {line};border-left:5px solid {water};border-radius:14px;
  padding:14px 18px;background:linear-gradient(110deg,{water_bg},#fff 75%);display:flex;
  flex-direction:column;justify-content:center;}}
.a1-hook-eyebrow{{color:{muted};font-size:6.5pt;letter-spacing:2px;text-transform:uppercase;font-weight:700;}}
.a1-bign{{display:flex;align-items:baseline;gap:12px;margin-top:5px;}}
.a1-bign-v{{font-family:{f_display};font-size:46pt;color:{water};line-height:.85;letter-spacing:-1.5px;}}
.a1-bign-v .a1-u{{font-size:18pt;color:{water};}}
.a1-bign-t{{font-size:12pt;font-weight:700;color:{navy};line-height:1.15;}}
.a1-hook-r{{flex:0 0 56mm;border:1px solid {line};border-left:5px solid {gold};border-radius:14px;
  background:linear-gradient(180deg,#FFFCF5,#fff 60%);padding:14px 16px;display:flex;
  flex-direction:column;justify-content:center;}}
.a1-zero{{font-family:{f_display};font-size:26pt;color:{gold};line-height:1;}}
.a1-zero-t{{font-size:9pt;color:{navy};font-weight:700;margin-top:4px;line-height:1.25;}}
.a1-zero-s{{font-size:8pt;color:{muted};margin-top:4px;line-height:1.3;}}
/* kpi grid */
.a1-kpis{{display:flex;flex-wrap:wrap;gap:11px;margin-top:12px;}}
.a1-kpi{{flex:1 1 30%;min-width:0;border:1px solid {line};border-top:3px solid {gold};
  border-radius:12px;padding:11px 13px;background:#fff;}}
.a1-kpi-v{{font-family:{f_display};font-size:18pt;color:{navy};line-height:1.0;}}
.a1-kpi-v .a1-u{{font-size:9pt;color:{muted};}}
.a1-kpi-l{{font-size:7.4pt;color:{muted};margin-top:4px;line-height:1.25;}}
/* tangibility + impact */
.a1-tang{{margin-top:12px;border:1px solid #CFE3F2;border-left:4px solid {water};border-radius:12px;
  background:linear-gradient(100deg,{water_bg},#fff 72%);padding:10px 14px;font-size:9pt;color:{ink};}}
.a1-tang b{{color:{water};}}
.a1-impact{{display:flex;align-items:center;gap:9px;margin-top:10px;border:1px solid {green_bg};
  border-left:4px solid {green};border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 70%);
  padding:9px 14px;}}
.a1-impact svg{{width:16px;height:16px;flex-shrink:0;}}
.a1-impact-t{{font-size:8.4pt;color:{ink};line-height:1.3;}}
.a1-impact-t b{{color:{green};font-weight:700;}}
.a1-note{{margin-top:11px;font-size:7.6pt;color:{muted_2};font-style:italic;line-height:1.35;}}
</style>
"""
    impact = ""
    if co2_t and trees:
        impact = (f'<div class="a1-impact"><svg viewBox="0 0 24 24" fill="none">'
                  f'<path d="M12 21c5-1 8-5 8-11V5l-5 1c-5 1-8 4-8 9 0 .7.1 1.4.3 2" stroke="{green}" '
                  f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
                  f'<path d="M7 21c0-4 2-7 6-9" stroke="{green}" stroke-width="1.7" stroke-linecap="round"/></svg>'
                  f'<div class="a1-impact-t">Et pour la planète : ≈ <b>{fmt_dec(co2_t)} tonnes de CO₂</b> '
                  f'évitées par an — soit ≈ <b>{fmt(trees)} arbres</b> plantés.</div></div>')

    html = f"""{css}
<div class="a1-root">
  <div class="a1-hero">
    <div class="a1-hero-glow"></div>
    <div class="a1-hero-top">
      <img class="a1-logo" src="data:image/png;base64,{logo_dark}" alt="TAQINOR">
      <div class="a1-meta">
        <div class="l">Réf. devis</div><div class="v">{ref}</div>
        <div class="dt">{date}</div><div class="a1-pill">Validité {validity} jours</div>
      </div>
    </div>
    <div class="a1-hero-body">
      <div class="a1-kicker">Proposition commerciale — Pompage solaire</div>
      <div class="a1-serif a1-hello">Bonjour {first},</div>
      <div class="a1-sub">Voici votre proposition de pompage solaire pour l'irrigation.</div>
    </div>
  </div>

  <div class="a1-client">
    <b>{client_full}</b>
    {f'<span class="a1-dot">·</span><span>{client_meta}</span>' if client_meta else ''}
    <span class="a1-tag">Agricole · Pompage</span>
  </div>

  <div class="a1-wrap">
    <div class="a1-hook">
      <div class="a1-hook-l">
        <div class="a1-hook-eyebrow">Ce que le solaire vous apporte</div>
        <div class="a1-bign">
          <div class="a1-bign-v">{hero_n}<span class="a1-u"> {hero_u}</span></div>
          <div class="a1-bign-t">{hero_t}</div>
        </div>
      </div>
      <div class="a1-hook-r">
        <div class="a1-zero">0 carburant</div>
        <div class="a1-zero-t">Plus de bonbonnes,<br>plus de gasoil.</div>
        <div class="a1-zero-s">Le soleil fait tourner votre pompe — l'eau que vous pompez devient gratuite.</div>
      </div>
    </div>

    <div class="a1-kpis">{cards_html}</div>
    {tang}
    {impact}
    <div class="a1-note">Étude technique, rendement, comparatif carburant et conditions détaillés dans les pages suivantes.
      Montants en MAD, TTC. Chiffres de rendement et d'économie estimatifs.</div>
  </div>
</div>
"""
    return html
