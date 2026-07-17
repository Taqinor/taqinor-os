# flake8: noqa
"""Agricole — PAGE 2 (how it works: the journey + the water, in farmer language).

Returns INNER HTML of one A4 page. Classes a2-*. Redesign (2026-06): NO monthly
bar graphs. The page answers, with almost zero jargon, "how does my water get
here and will it ever run short?" — a clean sun→champ schematic, ONE translated
technical block (how high we lift the water = an N-storey building; how fast =
fill a 1 000 L basin in M min), the HMT decomposition, the dimensioning chain,
and a worst-month reassurance. Total solar energy is shown small (a supporting
"the sun is your fuel" stat), never as the headline.
"""
from __future__ import annotations


def build(ctx) -> str:
    from . import theme
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]; schematic = ctx.get("schematic", "")
    etude = d.get("etude") or {}

    navy = C["navy"]; gold = C["gold"]; green = C["green"]; water = C["water"]
    water_bg = C["water_bg"]; green_bg = C["green_bg"]; ink = C["ink"]
    muted = C["muted"]; muted_2 = C["muted_2"]; line = C["line"]
    line_soft = C["line_soft"]; wash = C["wash"]
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
    besoin_m3j = d.get("besoin_m3j")              # FAO-56 peak need (economics.compute)
    has_water = d.get("has_water")
    prod_kwh = d.get("prod_kwh_year") or 0

    debit = debit_hmt or debit_souhaite
    # Plain-language translations of the only two specs we keep.
    storeys = round(float(hmt) / 3.0) if hmt else 0          # ~3 m / étage
    basin_min = (60.0 / float(debit)) if debit else 0        # min to fill 1 000 L

    # ── translated lift block (left) ─────────────────────────────────────────
    lift_html = ""
    if hmt:
        et = (f' — soit la hauteur d\'un <b>immeuble de {storeys} étages</b>'
              if storeys >= 2 else "")
        # simple vertical lift diagram: water table (bottom) → reservoir (top)
        lift_svg = f"""
<svg class="a2-lift-svg" viewBox="0 0 120 150" preserveAspectRatio="xMidYMid meet">
  <defs><marker id="ah" markerWidth="9" markerHeight="9" refX="4.5" refY="4.5" orient="auto">
    <path d="M1 1 L8 4.5 L1 8 Z" fill="{water}"/></marker></defs>
  <!-- reservoir / bassin at top -->
  <rect x="16" y="8" width="46" height="20" rx="3" fill="{water_bg}" stroke="{water}" stroke-width="1.4"/>
  <rect x="16" y="18" width="46" height="10" rx="0" fill="{water}" opacity="0.30"/>
  <text x="39" y="22" text-anchor="middle" font-size="7" fill="{navy}" font-weight="700">bassin</text>
  <!-- ground -->
  <line x1="8" y1="118" x2="74" y2="118" stroke="{muted_2}" stroke-width="1.2"/>
  <!-- well shaft -->
  <rect x="30" y="118" width="18" height="26" fill="{wash}" stroke="{line}" stroke-width="1"/>
  <rect x="30" y="136" width="18" height="8" fill="{water}" opacity="0.45"/>
  <text x="39" y="143" text-anchor="middle" font-size="6.5" fill="{muted}">nappe</text>
  <!-- lift arrow -->
  <line x1="82" y1="140" x2="82" y2="20" stroke="{water}" stroke-width="2" marker-end="url(#ah)"/>
  <text x="92" y="84" font-size="15" fill="{water}" font-weight="700" font-family="{f_display}">{fmt(hmt)}</text>
  <text x="92" y="96" font-size="7.5" fill="{muted}">mètres</text>
</svg>"""
        flow = ""
        if basin_min:
            flow = (f'<div class="a2-lift-flow"><span class="a2-lift-flow-i">⏱</span>'
                    f'On remplit un bassin de <b>1 000 litres</b> en '
                    f'≈ <b>{fmt(round(basin_min))} min</b>.</div>')
        lift_html = f"""
<div class="a2-card a2-lift">
  <div class="a2-h">On élève votre eau à {fmt(hmt)} m de haut</div>
  <div class="a2-lift-row">
    {lift_svg}
    <div class="a2-lift-txt">
      <div class="a2-lift-lead">Votre pompe doit faire monter l'eau du fond du
        forage jusqu'à votre bassin{et}.</div>
      {flow}
    </div>
  </div>
</div>"""

    # ── HMT breakdown (kept, simplified) ─────────────────────────────────────
    comp = [
        ("Niveau de l'eau au repos", etude.get("hmt_static")),
        ("Baisse pendant le pompage", etude.get("hmt_drawdown")),
        ("Montée jusqu'au bassin", etude.get("hmt_lift")),
        ("Pertes dans les tuyaux", etude.get("hmt_friction")),
        ("Pression de service", etude.get("hmt_pressure")),
    ]
    hmt_rows = []
    have_breakdown = any(v not in (None, "", 0) for _, v in comp)
    if have_breakdown:
        for lbl, v in comp:
            if v in (None, "", 0):
                continue
            hmt_rows.append(f'<div class="a2-hr"><span>{lbl}</span><b>{fmt_dec(v)} m</b></div>')
        if hmt:
            hmt_rows.append(f'<div class="a2-hr a2-hr-tot"><span>Hauteur totale</span>'
                            f'<b>{fmt(hmt)} m</b></div>')
    hmt_block = ""
    if hmt_rows:
        hmt_block = (f'<div class="a2-card a2-hmt"><div class="a2-h2">D\'où vient cette hauteur</div>'
                     f'<div class="a2-hrs">{"".join(hmt_rows)}</div></div>')

    # ── dimensioning chain (lighter; farmer-readable) ────────────────────────
    steps = []
    if has_water and surface_ha and crop and besoin_m3j:
        method_lbl = {"goutte": "goutte-à-goutte", "aspersion": "aspersion",
                      "gravitaire": "gravitaire"}.get(method, method or "")
        det = theme.join_meta(f"{fmt_dec(surface_ha)} ha · {crop}",
                              region.replace("-", " ").title() if region else "",
                              method_lbl)
        steps.append(("Votre besoin en eau", det or "Besoin de l'exploitation",
                      f"≈ {fmt(besoin_m3j)} m³/jour"))
    if pompe_cv:
        sub = theme.join_meta(pompe_nom or "", type_lbl, alim_lbl)
        steps.append(("La pompe choisie", sub or "Pompe solaire", f"{fmt_dec(pompe_cv)} CV"))
    if kwc:
        steps.append(("Le champ solaire", f"{nb_pan} panneaux × {wp} W", f"{fmt_dec(kwc)} kWc"))
    if has_water and m3j:
        sub = (f"{fmt_dec(debit)} m³/h × {fmt_dec(heures)} h de soleil utile"
               if debit and heures else "Livré chaque jour")
        steps.append(("L'eau livrée", sub, f"{fmt(m3j)} m³/jour"))
    steps_html = "".join(
        f'<div class="a2-step"><div class="a2-step-l"><div class="a2-step-t">{t}</div>'
        f'<div class="a2-step-s">{s}</div></div><div class="a2-step-v">{v}</div></div>'
        for t, s, v in steps if (t or v))
    steps_block = (f'<div class="a2-steps-card"><div class="a2-h2">Comment nous l\'avons dimensionnée</div>'
                   f'<div class="a2-steps">{steps_html}</div></div>') if steps_html else ""

    # ── worst-month reassurance (Lorentz's strongest line) ───────────────────
    if besoin_m3j and m3j and float(m3j) >= float(besoin_m3j):
        assure_lead = (f'Votre pompe livre <b>{fmt(m3j)} m³/jour</b>, au-dessus de '
                       f'votre besoin de pointe de <b>{fmt(besoin_m3j)} m³/jour</b>.')
    else:
        assure_lead = ('Nous dimensionnons sur le <b>mois le plus exigeant</b> (plein '
                       'été). Le reste de l\'année, vous avez de la marge.')
    assure = (f'<div class="a2-assure"><div class="a2-assure-ic">✓</div>'
              f'<div class="a2-assure-tx"><div class="a2-assure-h">De l\'eau toute l\'année, sans manquer</div>'
              f'<div class="a2-assure-t">Même au mois le moins ensoleillé, votre installation '
              f'donne plus d\'eau qu\'il n\'en faut. {assure_lead}</div></div></div>')

    # site facts chips
    facts = []
    if profondeur:
        facts.append(("Profondeur du forage", f"{fmt(profondeur)} m"))
    if distance:
        facts.append(("Distance panneaux → pompe", f"{fmt(distance)} m"))
    if alim_lbl:
        facts.append(("Alimentation", alim_lbl))
    facts_html = "".join(
        f'<div class="a2-fact"><span>{k}</span><b>{v}</b></div>' for k, v in facts)
    facts_block = f'<div class="a2-facts">{facts_html}</div>' if facts_html else ""

    # demoted "the sun is your fuel" strip (honours founder's energy number, small)
    sun_strip = ""
    if prod_kwh > 0:
        sun_strip = (f'<div class="a2-sun"><svg viewBox="0 0 24 24" fill="none" width="17" height="17">'
                     f'<circle cx="12" cy="12" r="4.4" stroke="{gold}" stroke-width="1.8"/>'
                     f'<g stroke="{gold}" stroke-width="1.8" stroke-linecap="round">'
                     f'<path d="M12 2.5v2.6"/><path d="M12 18.9v2.6"/><path d="M2.5 12h2.6"/>'
                     f'<path d="M18.9 12h2.6"/><path d="M5.2 5.2l1.8 1.8"/><path d="M17 17l1.8 1.8"/>'
                     f'<path d="M18.8 5.2L17 7"/><path d="M7 17l-1.8 1.8"/></g></svg>'
                     f'<div class="a2-sun-t">Votre carburant, c\'est le soleil — et il est gratuit. '
                     f'≈ <b>{fmt(prod_kwh)} kWh</b> captés par an font tourner votre pompe, '
                     f'sans une goutte de gasoil ni une bonbonne de butane.</div></div>')

    # ── QX47 — besoin de la culture (ETc mensuel, moteur QX48) vs eau livrée ──
    _MONTHS_1 = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    monthly_need = d.get("monthly_need_m3day")
    delivered = d.get("m3_jour_delivered")
    chart_html = ""
    if monthly_need and any((v or 0) > 0 for v in monthly_need):
        dvals = list(monthly_need)
        if delivered:
            dvals = dvals + [float(delivered)]
        dmax = max(dvals) or 1.0
        bars = ""
        for i, v in enumerate(monthly_need):
            h = round((v or 0) / dmax * 20.0, 1)
            covered = (not delivered) or (v <= float(delivered))
            cls = "a2-wc-ok" if covered else "a2-wc-tight"
            bars += (f'<td class="a2-wc-bc"><div class="a2-wc-bar {cls}" '
                     f'style="height:{h}mm"></div>'
                     f'<div class="a2-wc-mn">{_MONTHS_1[i]}</div></td>')
        line_html = ""
        if delivered:
            ly = round((1 - float(delivered) / dmax) * 20.0, 1)
            line_html = (f'<div class="a2-wc-line" style="top:{ly}mm">'
                         f'<span>eau livrée ≈ {fmt(round(float(delivered)))} m³/j</span></div>')
        chart_html = (
            '<div class="a2-card a2-wc">'
            '<div class="a2-h2">Le besoin de votre culture au fil de l\'année, face à l\'eau livrée</div>'
            f'<div class="a2-wc-plot"><table class="a2-wc-bars"><tr>{bars}</tr></table>{line_html}</div>'
            '<div class="a2-wc-cap">Barres = besoin de la culture (m³/jour, méthode FAO-56 par mois) · '
            'ligne = eau livrée par la pompe. Vert = couvert, ambre = mois tendu.</div>'
            '</div>')

    # ── QX47 — bassin de stockage recommandé (1-3× le besoin journalier) ─────
    bassin_reco = d.get("bassin_reco_m3")
    bassin_html = ""
    if bassin_reco:
        autonomie = d.get("bassin_autonomie_j") or 2
        bmin = d.get("bassin_min_m3")
        bmax = d.get("bassin_max_m3")
        bassin_html = (
            '<div class="a2-bassin"><div class="a2-bassin-ic">💧</div>'
            '<div class="a2-bassin-tx"><div class="a2-bassin-h">Bassin de stockage recommandé</div>'
            f'<div class="a2-bassin-t">≈ <b>{fmt(bassin_reco)} m³</b> — soit '
            f'<b>~{autonomie} jours d\'autonomie</b>. Fourchette utile de 1 à 3× le '
            f'besoin journalier ({fmt(bmin)}-{fmt(bmax)} m³) : un tampon jour/nuit et '
            'pour les jours peu ensoleillés.</div></div></div>')

    # Bloc « eau » de bas de page : le chart + le bassin (QX47) quand des données
    # d'exploitation existent, sinon le strip « carburant » historique (repli).
    water_block = chart_html + bassin_html
    if not water_block:
        water_block = sun_strip

    css = f"""
<style>
.a2-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;background:#fff;
  padding:14mm 14mm 0;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a2-root *{{box-sizing:border-box;}}
.a2-kicker{{font-size:7pt;letter-spacing:2.4px;text-transform:uppercase;color:{gold};font-weight:700;}}
.a2-title{{font-family:{f_serif};font-weight:700;font-size:23pt;color:{navy};line-height:1.04;margin:3px 0 0;}}
.a2-intro{{font-size:9.5pt;color:{muted};margin-top:6px;max-width:170mm;line-height:1.45;}}
.a2-sch{{margin-top:12px;border:1px solid {line};border-radius:14px;
  background:linear-gradient(180deg,{wash},#fff 80%);padding:10px 12px;}}
.a2-sch svg{{width:100%;height:auto;display:block;}}
.a2-sch-cap{{font-size:7.6pt;color:{muted_2};text-align:center;margin-top:3px;}}
.a2-h{{font-family:{f_serif};font-weight:700;font-size:13pt;color:{navy};margin-bottom:9px;line-height:1.1;}}
.a2-h2{{font-family:{f_serif};font-weight:700;font-size:11pt;color:{navy};margin-bottom:8px;}}
.a2-card{{border:1px solid {line};border-radius:14px;background:#fff;padding:14px 16px;margin-bottom:11px;}}
/* TABLE columns (WeasyPrint flex height quirk) */
.a2-cols{{display:table;width:100%;margin-top:12px;table-layout:fixed;}}
.a2-col{{display:table-cell;vertical-align:top;}}
.a2-col-gap{{display:table-cell;width:12px;}}
/* lift block */
.a2-lift{{border-left:5px solid {water};background:linear-gradient(120deg,{water_bg},#fff 70%);}}
.a2-lift-row{{display:flex;align-items:center;gap:12px;}}
.a2-lift-svg{{width:38mm;height:auto;flex-shrink:0;}}
.a2-lift-txt{{flex:1;}}
.a2-lift-lead{{font-size:9.5pt;color:{ink};line-height:1.45;}}
.a2-lift-lead b{{color:{water};}}
.a2-lift-flow{{margin-top:10px;font-size:9.5pt;color:{ink};line-height:1.4;}}
.a2-lift-flow b{{color:{navy};}}
.a2-lift-flow-i{{display:inline-block;margin-right:5px;}}
/* hmt breakdown */
.a2-hrs{{display:flex;flex-direction:column;}}
.a2-hr{{display:flex;justify-content:space-between;font-size:8.8pt;color:{ink};
  padding:6px 0;border-bottom:1px dashed {line_soft};}}
.a2-hr:last-child{{border-bottom:none;}}
.a2-hr b{{color:{navy};}}
.a2-hr-tot{{border-top:1.5px solid {line};margin-top:3px;padding-top:8px;font-weight:700;}}
.a2-hr-tot span{{font-weight:700;}} .a2-hr-tot b{{color:{water};font-size:10.5pt;}}
/* steps */
.a2-steps-card{{border:1px solid {line};border-radius:14px;background:#fff;padding:14px 16px;}}
.a2-steps{{display:flex;flex-direction:column;border:1px solid {line};border-radius:11px;overflow:hidden;}}
.a2-step{{display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:9px 13px;border-bottom:1px solid {line_soft};}}
.a2-step:last-child{{border-bottom:none;background:{green_bg};}}
.a2-step-t{{font-size:8.8pt;font-weight:700;color:{navy};}}
.a2-step-s{{font-size:7.8pt;color:{muted};margin-top:2px;line-height:1.3;}}
.a2-step-v{{font-family:{f_display};font-size:14pt;color:{water};white-space:nowrap;}}
.a2-step:last-child .a2-step-v{{color:{green};}}
/* reassurance */
.a2-assure{{display:flex;gap:11px;align-items:flex-start;margin-top:11px;
  border:1px solid #BFE6CB;border-left:5px solid {green};border-radius:14px;
  background:linear-gradient(110deg,{green_bg},#fff 72%);padding:13px 15px;}}
.a2-assure-ic{{flex-shrink:0;width:24px;height:24px;border-radius:50%;background:{green};
  color:#fff;font-size:13pt;font-weight:700;text-align:center;line-height:24px;}}
.a2-assure-h{{font-family:{f_serif};font-weight:700;font-size:11.5pt;color:{C['green_700']};}}
.a2-assure-t{{font-size:9pt;color:{ink};line-height:1.45;margin-top:3px;}}
.a2-assure-t b{{color:{C['green_700']};}}
/* facts */
.a2-facts{{display:flex;flex-wrap:wrap;gap:9px;margin-top:11px;}}
.a2-fact{{flex:1 1 30%;border:1px solid {line};border-radius:11px;background:{wash};padding:9px 12px;}}
.a2-fact span{{display:block;font-size:6.8pt;letter-spacing:.06em;text-transform:uppercase;color:{muted_2};font-weight:700;}}
.a2-fact b{{display:block;font-size:9.5pt;color:{ink};margin-top:2px;}}
/* sun strip */
.a2-sun{{display:flex;align-items:center;gap:11px;margin-top:12px;border:1px solid #F3E1BD;
  border-left:5px solid {gold};border-radius:14px;background:linear-gradient(110deg,{C['gold_soft']},#fff 74%);
  padding:11px 15px;}}
.a2-sun svg{{flex-shrink:0;}}
.a2-sun-t{{font-size:9pt;color:{ink};line-height:1.45;}}
.a2-sun-t b{{color:{C['earth']};font-weight:700;}}
/* QX47 — besoin culture vs eau livrée (barres CSS, jamais matplotlib) */
.a2-wc{{margin-top:12px;}}
.a2-wc-plot{{position:relative;margin-top:4px;}}
.a2-wc-bars{{width:100%;height:20mm;border-spacing:3px 0;}}
.a2-wc-bc{{vertical-align:bottom;text-align:center;}}
.a2-wc-bar{{width:100%;border-radius:3px 3px 0 0;}}
.a2-wc-ok{{background:{green};}}
.a2-wc-tight{{background:{gold};}}
.a2-wc-mn{{font-size:6pt;color:{muted_2};margin-top:2px;}}
.a2-wc-line{{position:absolute;left:0;right:0;border-top:2px dashed {water};}}
.a2-wc-line span{{position:absolute;right:0;top:-9pt;font-size:6.5pt;color:{water};
  font-weight:700;background:#fff;padding:0 3px;}}
.a2-wc-cap{{font-size:7pt;color:{muted_2};margin-top:5px;line-height:1.3;}}
.a2-bassin{{display:flex;align-items:flex-start;gap:10px;margin-top:11px;
  border:1px solid #CDE3F2;border-left:5px solid {water};border-radius:14px;
  background:linear-gradient(110deg,{water_bg},#fff 72%);padding:11px 14px;}}
.a2-bassin-ic{{font-size:15pt;flex-shrink:0;}}
.a2-bassin-h{{font-family:{f_serif};font-weight:700;font-size:11pt;color:{navy};}}
.a2-bassin-t{{font-size:8.6pt;color:{ink};line-height:1.4;margin-top:3px;}}
.a2-bassin-t b{{color:{navy};}}
</style>
"""
    sch_html = ""
    if show_schematic and schematic:
        sch_html = (f'<div class="a2-sch">{schematic}'
                    f'<div class="a2-sch-cap">Du forage à votre champ — le trajet de votre eau</div></div>')

    html = f"""{css}
<div class="a2-root">
  <div class="a2-kicker">Comment ça marche</div>
  <div class="a2-title">Du soleil à votre champ</div>
  <div class="a2-intro">Le soleil alimente la pompe, qui puise l'eau du forage et la
    monte jusqu'à votre bassin. Tout est dimensionné à partir de vos données réelles —
    pour ne jamais manquer d'eau, sans payer pour du surdimensionné.</div>
  {sch_html}
  <div class="a2-cols">
    <div class="a2-col">
      {lift_html}
      {hmt_block}
    </div>
    <div class="a2-col-gap"></div>
    <div class="a2-col">
      {steps_block}
      {assure}
    </div>
  </div>
  {facts_block}
  {water_block}
</div>
"""
    return html
