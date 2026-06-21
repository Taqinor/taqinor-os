# flake8: noqa
"""Agricole — PAGE 4 (investment & ROI: pricing chain, FDA subsidy, solar vs
butane vs diesel, payback, environmental). Returns INNER HTML. Classes a4-*.
Persuasion blocks are toggleable: show_subsidy / show_fuel_comparison /
show_environmental (founder choice #3)."""
from __future__ import annotations


def _yrs(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return str(int(f)) if f == int(f) else f"{f:.1f}".replace(".", ",")


def build(ctx) -> str:
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]; charts = ctx["charts"]

    navy = C["navy"]; gold = C["gold"]; green = C["green"]; green_bg = C["green_bg"]
    green_700 = C["green_700"]; water = C["water"]; water_bg = C["water_bg"]
    red = C["red"]; ink = C["ink"]; muted = C["muted"]; muted_2 = C["muted_2"]
    line = C["line"]; line_soft = C["line_soft"]; wash = C["wash"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]

    totaux = d.get("totaux_all") or {}
    ht_brut = totaux.get("ht_brut") or 0
    remise = totaux.get("remise") or 0
    ht_net = totaux.get("ht_net") or 0
    tva = totaux.get("tva") or 0
    ttc = totaux.get("ttc") or 0
    discount_pct = d.get("discount_pct") or 0

    has_water = d.get("has_water")
    show_subsidy = d.get("show_subsidy", True)
    show_fuel = d.get("show_fuel_comparison", True) and has_water
    show_env = d.get("show_environmental", True) and has_water

    fda_amount = d.get("fda_amount") or 0; fda_pct = d.get("fda_pct") or 30
    net_after_fda = d.get("net_after_fda") or ttc
    payback = d.get("payback"); payback_butane = d.get("payback_butane")
    payback_diesel = d.get("payback_diesel")
    saving_vs_butane = d.get("saving_vs_butane") or 0
    saving_vs_diesel = d.get("saving_vs_diesel") or 0
    co2_t = d.get("co2_t") or 0; trees = d.get("trees") or 0
    fuel_qty = d.get("fuel_qty_label") or ""
    b_sub = d.get("butane_12kg_subventionne") or 50
    b_reel = d.get("butane_12kg_reel") or 128

    # ── pricing chain rows ───────────────────────────────────────────────────
    chain = [("Sous-total HT", f"{fmt(ht_brut)} MAD", False)]
    if remise and remise > 0:
        chain.append((f"Remise ({fmt_dec(discount_pct)} %)", f"− {fmt(remise)} MAD", False))
        chain.append(("Total HT", f"{fmt(ht_net)} MAD", False))
    chain.append(("TVA", f"{fmt(tva)} MAD", False))
    chain.append(("Total TTC", f"{fmt(ttc)} MAD", True))
    chain_html = "".join(
        f'<div class="a4-cr {"a4-cr-tot" if big else ""}">'
        f'<span>{k}</span><b>{v}</b></div>' for k, v, big in chain)

    fda_html = ""
    if show_subsidy and fda_amount > 0:
        fda_html = (
            f'<div class="a4-fda"><div class="a4-fda-top">'
            f'<div><div class="a4-fda-k">Subvention FDA · pompage solaire</div>'
            f'<div class="a4-fda-s">{fda_pct} % du coût — versée a posteriori sur dossier DPA/ORMVA, '
            f'cumulable avec la subvention goutte-à-goutte.</div></div>'
            f'<div class="a4-fda-v">− {fmt(fda_amount)} MAD</div></div>'
            f'<div class="a4-fda-net"><span>Coût net estimé après subvention</span>'
            f'<b>≈ {fmt(net_after_fda)} MAD</b></div></div>')

    # ── payback card ─────────────────────────────────────────────────────────
    payback_html = ""
    if show_fuel and payback:
        pb_lines = []
        if payback_butane:
            pb_lines.append(f'<span class="a4-pb-row">vs butane&nbsp;: <b>{_yrs(payback_butane)} ans</b></span>')
        if payback_diesel:
            pb_lines.append(f'<span class="a4-pb-row">vs diesel&nbsp;: <b>{_yrs(payback_diesel)} ans</b></span>')
        payback_html = (
            f'<div class="a4-card a4-pb"><div class="a4-h">Rentabilité</div>'
            f'<div class="a4-pb-big">{_yrs(payback)} <span>ans</span></div>'
            f'<div class="a4-pb-sub">d\'amortissement estimé · {" · ".join(pb_lines)}</div>'
            f'<img src="{charts["payback"]}" alt="Gain cumulé"></div>')

    # ── fuel comparison block ────────────────────────────────────────────────
    fuel_html = ""
    if show_fuel:
        fuel_html = (
            f'<div class="a4-card"><div class="a4-h">Solaire vs butane vs diesel</div>'
            f'<div class="a4-fcols"><div class="a4-fc-main">'
            f'<div class="a4-cap">Coût annuel du carburant pour pomper le même volume d\'eau</div>'
            f'<img src="{charts["fuel"]}" alt="Comparatif carburant annuel"></div>'
            f'<div class="a4-fc-side"><div class="a4-cap">Coût par m³ d\'eau pompée</div>'
            f'<img src="{charts["cost_m3"]}" alt="Coût par m3"></div></div>'
            f'<div class="a4-punch"><b>« Le butane est bon marché tant qu\'il est subventionné. '
            f'Le solaire est bon marché pour toujours. »</b><br>'
            f'La bonbonne de 12 kg ({fmt(b_sub)} MAD aujourd\'hui) est destinée à atteindre son '
            f'vrai prix (~{fmt(b_reel)} MAD) à mesure que la subvention disparaît : votre facture de '
            f'pompage va plus que doubler. Le solaire supprime totalement ce coût — et ce risque.</div>'
            f'</div>')

    # ── environmental strip ──────────────────────────────────────────────────
    env_html = ""
    if show_env and co2_t and trees:
        env_html = (
            f'<div class="a4-env"><svg viewBox="0 0 24 24" fill="none">'
            f'<path d="M12 21c5-1 8-5 8-11V5l-5 1c-5 1-8 4-8 9 0 .7.1 1.4.3 2" stroke="{green}" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M7 21c0-4 2-7 6-9" stroke="{green}" stroke-width="1.7" stroke-linecap="round"/></svg>'
            f'<div class="a4-env-t">En passant au solaire, vous évitez ≈ <b>{fuel_qty}</b> par an, '
            f'soit ≈ <b>{fmt_dec(co2_t)} tonnes de CO₂</b> (≈ {fmt(trees)} arbres plantés).</div></div>')

    nowater_note = ""
    if not has_water:
        nowater_note = ('<div class="a4-note">Le comparatif carburant et la rentabilité '
                        'nécessitent un débit issu d\'une courbe pompe (m³/jour). Renseignez la '
                        'HMT et le débit souhaité avec une pompe à courbe pour les afficher.</div>')

    css = f"""
<style>
.a4-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;background:#fff;
  padding:14mm 14mm 0;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a4-root *{{box-sizing:border-box;}}
.a4-kicker{{font-size:7pt;letter-spacing:2.4px;text-transform:uppercase;color:{gold};font-weight:700;}}
.a4-title{{font-family:{f_serif};font-weight:700;font-size:23pt;color:{navy};line-height:1.04;margin:3px 0 0;}}
.a4-h{{font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};margin-bottom:7px;}}
.a4-cap{{font-size:7.4pt;color:{muted};margin-bottom:3px;}}
.a4-top{{display:flex;gap:12px;margin-top:11px;align-items:stretch;}}
.a4-col-l{{flex:0 0 70mm;}}
.a4-col-r{{flex:1 1 0;min-width:0;}}
.a4-card{{border:1px solid {line};border-radius:12px;background:#fff;padding:13px 15px;height:100%;}}
.a4-chain{{display:flex;flex-direction:column;}}
.a4-cr{{display:flex;justify-content:space-between;font-size:8.8pt;color:{ink};
  padding:7px 0;border-bottom:1px dashed {line_soft};}}
.a4-cr b{{color:{navy};font-weight:700;}}
.a4-cr-tot{{border-top:2px solid {navy};border-bottom:none;margin-top:4px;padding-top:9px;}}
.a4-cr-tot span{{font-weight:700;font-size:9.5pt;color:{navy};}}
.a4-cr-tot b{{font-family:{f_display};font-size:16pt;color:{gold};}}
.a4-fda{{margin-top:10px;border:1px solid #BFE6CB;border-radius:12px;
  background:linear-gradient(180deg,{green_bg},#fff 70%);padding:11px 13px;}}
.a4-fda-top{{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;}}
.a4-fda-k{{font-size:8.4pt;font-weight:700;color:{green_700};}}
.a4-fda-s{{font-size:7.2pt;color:{muted};margin-top:3px;line-height:1.3;}}
.a4-fda-v{{font-family:{f_display};font-size:14pt;color:{green_700};white-space:nowrap;}}
.a4-fda-net{{display:flex;justify-content:space-between;margin-top:8px;padding-top:8px;
  border-top:1px dashed #BFE6CB;font-size:8.6pt;}}
.a4-fda-net b{{color:{green_700};font-weight:700;}}
.a4-pb{{display:flex;flex-direction:column;}}
.a4-pb-big{{font-family:{f_display};font-size:30pt;color:{green};line-height:.9;}}
.a4-pb-big span{{font-size:13pt;color:{muted};}}
.a4-pb-sub{{font-size:8pt;color:{muted};margin:4px 0 6px;}}
.a4-pb-row{{margin-right:8px;}} .a4-pb-row b{{color:{navy};}}
.a4-pb img{{width:100%;height:auto;display:block;margin-top:2px;}}
.a4-mid{{margin-top:12px;}}
.a4-fcols{{display:flex;gap:12px;align-items:flex-start;}}
.a4-fc-main{{flex:1 1 0;min-width:0;}} .a4-fc-side{{flex:0 0 52mm;}}
.a4-fcols img{{width:100%;height:auto;display:block;}}
.a4-punch{{margin-top:9px;border-left:4px solid {gold};background:{wash};border-radius:8px;
  padding:9px 13px;font-size:8.2pt;color:{ink};line-height:1.4;}}
.a4-punch b{{color:{navy};}}
.a4-env{{display:flex;align-items:center;gap:9px;margin-top:11px;border:1px solid {green_bg};
  border-left:4px solid {green};border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:9px 14px;}}
.a4-env svg{{width:16px;height:16px;flex-shrink:0;}}
.a4-env-t{{font-size:8.4pt;color:{ink};line-height:1.3;}} .a4-env-t b{{color:{green};}}
.a4-note{{margin-top:11px;font-size:8pt;color:{muted_2};font-style:italic;line-height:1.35;}}
</style>
"""
    html = f"""{css}
<div class="a4-root">
  <div class="a4-kicker">Investissement & rentabilité</div>
  <div class="a4-title">Votre investissement, et ce qu'il vous fait gagner</div>
  <div class="a4-top">
    <div class="a4-col-l">
      <div class="a4-card"><div class="a4-h">Le prix, en toute transparence</div>
        <div class="a4-chain">{chain_html}</div>
        {fda_html}
      </div>
    </div>
    <div class="a4-col-r">{payback_html}</div>
  </div>
  <div class="a4-mid">{fuel_html}</div>
  {env_html}
  {nowater_note}
</div>
"""
    return html
