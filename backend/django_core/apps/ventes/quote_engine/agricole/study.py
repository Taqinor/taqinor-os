# flake8: noqa
"""Agricole — PAGE 2 (engineering study: schematic + hydraulic/sizing proof).
Returns INNER HTML of one A4 page. Classes a2-*."""
from __future__ import annotations


def build(ctx) -> str:
    from . import theme
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]; schematic = ctx.get("schematic", "")
    charts = ctx["charts"]
    etude = d.get("etude") or {}

    navy = C["navy"]; gold = C["gold"]; green = C["green"]; water = C["water"]
    water_bg = C["water_bg"]; ink = C["ink"]; muted = C["muted"]; muted_2 = C["muted_2"]
    line = C["line"]; line_soft = C["line_soft"]; wash = C["wash"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]

    show_schematic = d.get("show_schematic", True)
    kwc = d.get("puissance_kwc") or 0; nb_pan = d.get("nb_panneaux") or 0
    wp = d.get("watt_par_panneau") or 0
    pompe_cv = etude.get("pompe_cv"); pompe_kw = etude.get("pompe_kw")
    pompe_nom = etude.get("pompe_nom"); type_pompe = (etude.get("type_pompe") or "").lower()
    type_lbl = "immergée" if "immerg" in type_pompe else ("surface" if type_pompe else "")
    alim = (etude.get("alim") or "").lower()
    alim_lbl = "triphasé 380 V" if alim == "tri" else ("monophasé 220 V" if alim == "mono" else "")
    hmt = etude.get("hmt_m"); debit_souhaite = etude.get("debit_souhaite_m3h")
    debit_hmt = etude.get("debit_hmt_m3h"); heures = etude.get("heures_pompage")
    m3j = etude.get("m3_jour"); profondeur = etude.get("profondeur_m")
    distance = etude.get("distance_m")
    crop = (etude.get("crop") or "").strip(); region = (etude.get("region") or "").strip()
    surface_ha = etude.get("surface_ha"); method = (etude.get("irrigation_method") or "").strip()
    has_water = d.get("has_water")

    # ── HMT breakdown (optional components) ──────────────────────────────────
    hmt_rows = []
    comp = [
        ("Niveau statique de l'eau", etude.get("hmt_static")),
        ("Rabattement (pompage)", etude.get("hmt_drawdown")),
        ("Hauteur jusqu'au bassin", etude.get("hmt_lift")),
        ("Pertes de charge (tuyauterie)", etude.get("hmt_friction")),
        ("Pression de service", etude.get("hmt_pressure")),
    ]
    have_breakdown = any(v not in (None, "", 0) for _, v in comp)
    if have_breakdown:
        for lbl, v in comp:
            if v in (None, "", 0):
                continue
            hmt_rows.append(f'<div class="a2-hr"><span>{lbl}</span>'
                            f'<b>{fmt_dec(v)} m</b></div>')
        if hmt:
            hmt_rows.append(f'<div class="a2-hr a2-hr-tot"><span>HMT totale</span>'
                            f'<b>{fmt(hmt)} m</b></div>')
    elif hmt:
        hmt_rows.append(f'<div class="a2-hr a2-hr-tot"><span>Hauteur manométrique (HMT)</span>'
                        f'<b>{fmt(hmt)} m</b></div>')
    hmt_block = ""
    if hmt_rows:
        intro = ("La HMT est la hauteur totale que la pompe doit vaincre. "
                 "Nous la décomposons pour dimensionner au plus juste." if have_breakdown
                 else "Hauteur totale que la pompe doit vaincre pour livrer l'eau.")
        hmt_block = (f'<div class="a2-card"><div class="a2-h">Hauteur manométrique (HMT)</div>'
                     f'<div class="a2-sub">{intro}</div>'
                     f'<div class="a2-hrs">{"".join(hmt_rows)}</div></div>')

    # ── Sizing steps ─────────────────────────────────────────────────────────
    steps = []
    if has_water and surface_ha and crop:
        method_lbl = {"goutte": "goutte-à-goutte", "aspersion": "aspersion",
                      "gravitaire": "gravitaire"}.get(method, method or "")
        det = theme.join_meta(f"{fmt_dec(surface_ha)} ha · {crop}",
                              region.replace("-", " ").title() if region else "",
                              method_lbl)
        steps.append(("Besoin en eau", det or "Besoin de l'exploitation",
                      f"≈ {fmt(m3j)} m³/jour au mois de pointe" if m3j else ""))
    if debit_hmt and hmt:
        steps.append(("Débit requis",
                      f"À la HMT de {fmt(hmt)} m",
                      f"{fmt_dec(debit_hmt)} m³/h"))
    elif debit_souhaite:
        steps.append(("Débit souhaité", "Saisi pour le dimensionnement",
                      f"{fmt_dec(debit_souhaite)} m³/h"))
    if pompe_cv:
        sub = theme.join_meta(f"{fmt_dec(pompe_kw)} kW" if pompe_kw else "",
                              type_lbl, alim_lbl)
        steps.append(("Pompe sélectionnée",
                      pompe_nom or sub or "Pompe solaire",
                      f"{fmt_dec(pompe_cv)} CV"))
    if kwc:
        steps.append(("Champ solaire",
                      f"≈ 1,4 × la puissance pompe · {nb_pan} panneaux × {wp} W",
                      f"{fmt_dec(kwc)} kWc"))
    if has_water and debit_hmt and heures and m3j:
        steps.append(("Volume journalier",
                      f"{fmt_dec(debit_hmt)} m³/h × {fmt_dec(heures)} h de pompage",
                      f"{fmt(m3j)} m³/jour"))
    steps_html = "".join(
        f'<div class="a2-step"><div class="a2-step-l"><div class="a2-step-t">{t}</div>'
        f'<div class="a2-step-s">{s}</div></div>'
        f'<div class="a2-step-v">{v}</div></div>'
        for t, s, v in steps if (t or v))

    # site facts chips
    facts = []
    if profondeur:
        facts.append(("Profondeur forage", f"{fmt(profondeur)} m"))
    if distance:
        facts.append(("Distance panneaux → coffret", f"{fmt(distance)} m"))
    if alim_lbl:
        facts.append(("Alimentation", alim_lbl))
    facts_html = "".join(
        f'<div class="a2-fact"><span>{k}</span><b>{v}</b></div>' for k, v in facts)

    # Production / eau charts (folded up from the old page 3 to fill this page).
    show_water = d.get("show_water_yield", True) and has_water
    annual_m3 = d.get("annual_m3") or 0
    prod_kwh = d.get("prod_kwh_year") or 0
    chart_cards = []
    if show_water:
        chart_cards.append(
            f'<div class="a2-chart"><div class="a2-ch-head">'
            f'<div class="a2-ch-t">Eau livrée mois par mois</div>'
            f'<div class="a2-ch-s">≈ {fmt(annual_m3)} m³/an</div></div>'
            f'<img src="{charts["water"]}" alt="Eau par mois"></div>')
    if prod_kwh > 0:
        chart_cards.append(
            f'<div class="a2-chart"><div class="a2-ch-head">'
            f'<div class="a2-ch-t">Production solaire</div>'
            f'<div class="a2-ch-s">≈ {fmt(prod_kwh)} kWh/an</div></div>'
            f'<img src="{charts["production"]}" alt="Production par mois"></div>')
    charts_html = (f'<div class="a2-charts">{"".join(chart_cards)}</div>'
                   if chart_cards else "")

    css = f"""
<style>
.a2-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;background:#fff;
  padding:14mm 14mm 0;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a2-root *{{box-sizing:border-box;}}
.a2-kicker{{font-size:7pt;letter-spacing:2.4px;text-transform:uppercase;color:{gold};font-weight:700;}}
.a2-title{{font-family:{f_serif};font-weight:700;font-size:23pt;color:{navy};line-height:1.04;margin:3px 0 0;}}
.a2-intro{{font-size:9pt;color:{muted};margin-top:5px;max-width:165mm;line-height:1.4;}}
.a2-sch{{margin-top:11px;border:1px solid {line};border-radius:14px;background:{wash};padding:8px 10px;}}
.a2-sch svg{{width:100%;height:auto;display:block;}}
.a2-sch-cap{{font-size:7.4pt;color:{muted_2};text-align:center;margin-top:2px;}}
/* TABLE, not flex: WeasyPrint can let a flex column with nowrap content
   overflow its 50% box and collide with the other column (the chain value
   slid under the right callout). Table cells give deterministic columns. */
.a2-cols{{display:table;width:100%;margin-top:13px;table-layout:fixed;}}
.a2-col{{display:table-cell;vertical-align:top;}}
.a2-col-gap{{display:table-cell;width:12px;}}
.a2-h{{font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};margin-bottom:7px;}}
.a2-sub{{font-size:8pt;color:{muted};margin-bottom:8px;line-height:1.35;}}
.a2-card{{border:1px solid {line};border-radius:12px;background:#fff;padding:13px 15px;}}
/* steps */
.a2-steps{{display:flex;flex-direction:column;gap:0;border:1px solid {line};border-radius:12px;
  overflow:hidden;background:#fff;}}
.a2-step{{display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:10px 14px;border-bottom:1px solid {line_soft};}}
.a2-step:last-child{{border-bottom:none;background:{wash};}}
.a2-step-t{{font-size:8.6pt;font-weight:700;color:{navy};}}
.a2-step-s{{font-size:7.6pt;color:{muted};margin-top:2px;line-height:1.3;}}
.a2-step-v{{font-family:{f_display};font-size:14pt;color:{water};white-space:nowrap;}}
.a2-step:last-child .a2-step-v{{color:{green};}}
/* hmt rows */
.a2-hrs{{display:flex;flex-direction:column;}}
.a2-hr{{display:flex;justify-content:space-between;font-size:8.4pt;color:{ink};
  padding:6px 0;border-bottom:1px dashed {line_soft};}}
.a2-hr:last-child{{border-bottom:none;}}
.a2-hr b{{color:{navy};}}
.a2-hr-tot{{border-top:1.5px solid {line};margin-top:3px;padding-top:8px;font-weight:700;}}
.a2-hr-tot span{{font-weight:700;}}
.a2-hr-tot b{{color:{water};font-size:10pt;}}
.a2-facts{{display:flex;flex-wrap:wrap;gap:8px;margin-top:11px;}}
.a2-fact{{flex:1 1 30%;border:1px solid {line};border-radius:10px;background:{wash};padding:8px 11px;}}
.a2-fact span{{display:block;font-size:6.8pt;letter-spacing:.06em;text-transform:uppercase;color:{muted_2};font-weight:700;}}
.a2-fact b{{display:block;font-size:9pt;color:{ink};margin-top:2px;}}
.a2-why{{margin-top:10px;border:1px solid #CFE3F2;border-left:4px solid {water};border-radius:10px;
  background:linear-gradient(100deg,{water_bg},#fff 74%);padding:9px 13px;}}
.a2-why b{{color:{water};}}
.a2-why-t{{font-size:8pt;color:{ink};line-height:1.35;}}
.a2-charts{{display:flex;gap:12px;margin-top:12px;}}
.a2-chart{{flex:1 1 0;min-width:0;border:1px solid {line};border-radius:12px;padding:9px 12px;}}
.a2-ch-head{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:3px;}}
.a2-ch-t{{font-size:8.2pt;font-weight:700;color:{navy};}}
.a2-ch-s{{font-size:8.2pt;font-weight:700;color:{water};}}
.a2-chart img{{width:100%;height:auto;display:block;}}
</style>
"""
    sch_html = ""
    if show_schematic and schematic:
        sch_html = (f'<div class="a2-sch">{schematic}'
                    f'<div class="a2-sch-cap">Schéma de principe — du soleil au champ</div></div>')

    html = f"""{css}
<div class="a2-root">
  <div class="a2-kicker">Étude technique</div>
  <div class="a2-title">Le dimensionnement de votre installation</div>
  <div class="a2-intro">Chaque composant est choisi à partir de vos données réelles — la hauteur
    à vaincre (HMT), le débit nécessaire et l'ensoleillement — pour livrer le bon volume d'eau, sans surcoût.</div>
  {sch_html}
  <div class="a2-cols">
    <div class="a2-col">
      <div class="a2-h">La chaîne de dimensionnement</div>
      <div class="a2-steps">{steps_html}</div>
      <div class="a2-facts">{facts_html}</div>
    </div>
    <div class="a2-col-gap"></div>
    <div class="a2-col">
      {hmt_block}
      <div class="a2-why"><div class="a2-why-t">Champ solaire <b>≈ 1,4 × la pompe</b> :
        elle démarre plus tôt, traverse les passages nuageux et termine le volume du
        jour dans la fenêtre d'ensoleillement utile.</div></div>
    </div>
  </div>
  {charts_html}
</div>
"""
    return html
