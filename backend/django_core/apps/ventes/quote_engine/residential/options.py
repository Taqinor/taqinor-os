# flake8: noqa
"""Page 2 — VOTRE INSTALLATION : détail du projet + finance.

Restructured vs the old design: the old page 2 carried TWO near-identical
13-row equipment tables (~80 % duplicated). Here we show ONE "équipement commun
aux deux options" table + a small per-option delta ("ce que chaque option
ajoute"), then promote the finance charts (25-yr payback curve gets real space).

build(ctx) returns the INNER HTML of one A4 page (no .page wrapper, no footer).
Every class is prefixed `p2-` so it never clashes with pages 1/3.
"""
from __future__ import annotations


def _split_items(sans_items, avec_items):
    """Partition lines by designation membership across the two options.

    Returns (shared, delta_sans, delta_avec). `shared` keeps the order of
    sans_items; the value used is the sans-side line (prices match avec-side).
    """
    avec_names = {it["designation"] for it in avec_items}
    sans_names = {it["designation"] for it in sans_items}
    common = sans_names & avec_names

    shared = [it for it in sans_items if it["designation"] in common]
    delta_sans = [it for it in sans_items if it["designation"] not in avec_names]
    delta_avec = [it for it in avec_items if it["designation"] not in sans_names]
    return shared, delta_sans, delta_avec


def _row(it, fmt):
    """One <tr> for the shared equipment table."""
    desig = it["designation"]
    marque = it.get("marque") or ""
    qte = it["quantite"]
    qte_txt = f"{qte:g}"
    pu = fmt(it["prix_unit_ht"])
    tva = f"{int(round(it['taux_tva']))}%"
    total_ht = fmt(it["prix_unit_ht"] * it["quantite"])
    marque_html = (f'<span class="p2-mk">{marque}</span>' if marque else "")
    return (
        f'<tr>'
        f'<td class="p2-d"><span class="p2-name">{desig}</span>{marque_html}</td>'
        f'<td class="p2-c">{qte_txt}</td>'
        f'<td class="p2-r">{pu}</td>'
        f'<td class="p2-c p2-tva">{tva}</td>'
        f'<td class="p2-r p2-tot">{total_ht}</td>'
        f'</tr>'
    )


def _delta_lines(items, fmt):
    """Compact list of the extra products one option adds."""
    out = []
    for it in items:
        qte = it["quantite"]
        q = f"{qte:g}× " if qte and qte != 1 else ""
        total_ht = fmt(it["prix_unit_ht"] * it["quantite"])
        out.append(
            f'<li><span class="p2-dl-n">{q}{it["designation"]}</span>'
            f'<span class="p2-dl-p">{total_ht} HT</span></li>'
        )
    return "".join(out)


def _totals_chain(label, accent, tot, fmt, C, recommended=False):
    """One compact HT→TVA→TTC chain card for a single option."""
    rows = [
        f'<div class="p2-tl"><span>Sous-total HT</span>'
        f'<span>{fmt(tot["ht_brut"])}</span></div>'
    ]
    if tot.get("remise", 0) and tot["remise"] > 0:
        rows.append(
            f'<div class="p2-tl p2-tl-rem"><span>Remise</span>'
            f'<span>− {fmt(tot["remise"])}</span></div>'
        )
        rows.append(
            f'<div class="p2-tl"><span>Total HT</span>'
            f'<span>{fmt(tot["ht_net"])}</span></div>'
        )
    for t in tot.get("tva_par_taux", []):
        taux = int(round(t["taux"]))
        rows.append(
            f'<div class="p2-tl p2-tl-sub"><span>TVA {taux}%</span>'
            f'<span>{fmt(t["montant"])}</span></div>'
        )
    badge = '<span class="p2-badge">Recommandé</span>' if recommended else ""
    return (
        f'<div class="p2-tot-card" style="border-top:3px solid {accent}">'
        f'<div class="p2-tot-head"><span class="p2-tot-opt" '
        f'style="color:{accent}">{label}</span>{badge}</div>'
        f'<div class="p2-tot-rows">{"".join(rows)}</div>'
        f'<div class="p2-tot-grand">'
        f'<span>Total TTC</span>'
        f'<span class="p2-grand-v">{fmt(tot["ttc"])} <small>MAD</small></span>'
        f'</div>'
        f'</div>'
    )


def build(ctx) -> str:
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    charts = ctx["charts"]
    links = d.get("links", {})

    shared, delta_sans, delta_avec = _split_items(
        d["sans_items"], d["avec_items"]
    )

    # ── Top spec list ────────────────────────────────────────────────────────
    specs = [
        (f'{d["puissance_kwc"]:g}', "kWc installés"),
        (f'{d["nb_panneaux"]:g}', f'panneaux · {d["watt_par_panneau"]:g} W'),
        (fmt(d["prod_kwh"]), "kWh / an produits"),
    ]
    spec_html = "".join(
        f'<div class="p2-spec"><span class="p2-spec-v">{v}</span>'
        f'<span class="p2-spec-l">{l}</span></div>'
        for v, l in specs
    )

    rows_html = "".join(_row(it, fmt) for it in shared)
    delta_sans_html = _delta_lines(delta_sans, fmt)
    delta_avec_html = _delta_lines(delta_avec, fmt)

    produits_link = links.get("produits", d.get("site_url", "taqinor.ma"))

    totals_sans = _totals_chain(
        "Option 1 — Sans batterie", C["navy"], d["totaux_sans"], fmt, C
    )
    totals_avec = _totals_chain(
        "Option 2 — Avec batterie", C["gold"], d["totaux_avec"], fmt, C,
        recommended=True,
    )

    tva_note = d.get("tva_note", "")

    # ── Payback takeaway figures (read straight off the quote data) ───────────
    def _yrs(v):
        return f"{v:g}".replace(".", ",") if v else "—"
    roi_s, roi_a = d.get("roi_s"), d.get("roi_a")
    if roi_s and roi_a:
        lo, hi = sorted((roi_s, roi_a))
        roi_range = f"{_yrs(lo)} – {_yrs(hi)} ans"
    else:
        roi_range = "—"
    # Net cumulative gain over 25 yrs for the recommended (battery) option,
    # rounded to a clean headline figure.
    gain25 = max(0, round(d.get("eco_a_ann", 0) * 25 - d.get("total_avec", 0)))
    gain25 = round(gain25 / 1000) * 1000

    style = f"""
<style>
  .p2-wrap {{ padding:9mm 14mm 0 14mm; }}

  /* Section header */
  .p2-kick {{ font-size:8.5pt; letter-spacing:.22em; text-transform:uppercase;
    color:{C['gold']}; font-weight:700; }}
  .p2-title {{ font-family:{fonts['serif']}; font-weight:700; font-size:23pt;
    color:{C['navy']}; line-height:1.04; margin-top:2mm; letter-spacing:-.3px; }}

  /* Top band: roof schematic + spec list */
  .p2-band {{ display:flex; align-items:center; gap:6mm; margin-top:3.5mm;
    padding:2.5mm 5mm; background:{C['wash']}; border:1px solid {C['line']};
    border-radius:12px; }}
  .p2-roof {{ flex:0 0 36mm; text-align:center; }}
  .p2-roof img {{ width:34mm; height:auto; }}
  .p2-specs {{ flex:1; display:flex; gap:5mm; }}
  .p2-spec {{ flex:1; display:flex; flex-direction:column; gap:1mm;
    padding-left:5mm; border-left:2px solid {C['line']}; }}
  .p2-spec:first-child {{ border-left:none; padding-left:0; }}
  .p2-spec-v {{ font-family:{fonts['display']}; font-size:18pt;
    color:{C['navy']}; line-height:1; }}
  .p2-spec-l {{ font-size:8pt; color:{C['muted']}; line-height:1.2; }}

  /* Block label */
  .p2-lbl {{ font-size:8.5pt; letter-spacing:.16em; text-transform:uppercase;
    color:{C['navy']}; font-weight:700; margin:4.5mm 0 2mm; }}

  /* Shared equipment table */
  .p2-tbl {{ width:100%; border-collapse:collapse; font-size:8.7pt; }}
  .p2-tbl thead th {{ font-size:7.4pt; letter-spacing:.08em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    text-align:left; padding:0 0 2mm; border-bottom:1.5px solid {C['line']}; }}
  .p2-tbl th.p2-c, .p2-tbl td.p2-c {{ text-align:center; }}
  .p2-tbl th.p2-r, .p2-tbl td.p2-r {{ text-align:right; }}
  .p2-tbl tbody td {{ padding:1.7mm 0; border-bottom:1px solid {C['line_soft']};
    vertical-align:middle; }}
  .p2-tbl tbody tr:nth-child(even) td {{ background:{C['wash']}; }}
  .p2-tbl tbody td.p2-d {{ padding-left:2.5mm; }}
  .p2-tbl tbody td.p2-tot {{ padding-right:2.5mm; }}
  .p2-name {{ color:{C['ink']}; font-weight:600; }}
  .p2-mk {{ color:{C['muted']}; font-size:7.6pt; margin-left:5px; }}
  .p2-tva {{ color:{C['muted']}; font-size:8pt; }}
  .p2-tot {{ font-weight:700; color:{C['navy']}; white-space:nowrap; }}

  /* Per-option delta mini-cards */
  .p2-deltas {{ display:flex; gap:5mm; margin-top:3mm; }}
  .p2-dcard {{ flex:1; border:1px solid {C['line']}; border-radius:10px;
    overflow:hidden; }}
  .p2-dhead {{ padding:2.2mm 3.5mm; font-size:8.4pt; font-weight:700;
    color:#fff; }}
  .p2-dhead small {{ font-weight:500; opacity:.85; }}
  .p2-dbody ul {{ list-style:none; }}
  .p2-dbody li {{ display:flex; justify-content:space-between; align-items:center;
    padding:2mm 3.5mm; font-size:8.5pt; border-bottom:1px solid {C['line_soft']}; }}
  .p2-dbody li:last-child {{ border-bottom:none; }}
  .p2-dl-n {{ color:{C['ink']}; }}
  .p2-dl-p {{ color:{C['navy']}; font-weight:700; white-space:nowrap;
    margin-left:6px; }}

  .p2-fiche {{ font-size:8pt; color:{C['muted']}; margin-top:2mm; }}
  .p2-fiche b {{ color:{C['navy']}; font-weight:700; }}

  /* Totals chains side by side */
  .p2-totals {{ display:flex; gap:5mm; margin-top:3.5mm; }}
  .p2-tot-card {{ flex:1; border:1px solid {C['line']};
    border-radius:0 0 10px 10px; background:{C['paper']};
    box-shadow:0 1px 3px rgba(26,43,74,.05); }}
  .p2-tot-head {{ display:flex; justify-content:space-between; align-items:center;
    padding:2.6mm 4mm 1.5mm; }}
  .p2-tot-opt {{ font-size:9pt; font-weight:700; }}
  .p2-badge {{ font-size:6.6pt; font-weight:700; letter-spacing:.05em;
    text-transform:uppercase; color:{C['navy']}; background:{C['gold']};
    padding:1.5px 7px; border-radius:999px; }}
  .p2-tot-rows {{ padding:0 4mm; }}
  .p2-tl {{ display:flex; justify-content:space-between; font-size:8.4pt;
    color:{C['ink']}; padding:1.1mm 0; }}
  .p2-tl-sub {{ color:{C['muted']}; font-size:8pt; }}
  .p2-tl-rem {{ color:{C['green']}; }}
  .p2-tot-grand {{ display:flex; justify-content:space-between; align-items:baseline;
    margin:1.5mm 4mm 0; padding:2.4mm 0; border-top:1.5px solid {C['line']}; }}
  .p2-tot-grand > span:first-child {{ font-size:8.6pt; font-weight:700;
    color:{C['navy']}; text-transform:uppercase; letter-spacing:.06em; }}
  .p2-grand-v {{ font-family:{fonts['display']}; font-size:17pt;
    color:{C['navy']}; }}
  .p2-grand-v small {{ font-family:{fonts['sans']}; font-size:8.5pt;
    color:{C['muted']}; font-weight:600; }}
  .p2-tva-note {{ font-size:7.4pt; color:{C['muted']}; margin-top:2mm;
    text-align:center; }}

  /* Finance: payback */
  .p2-fin {{ margin-top:2.5mm; }}
  .p2-fin-head {{ display:flex; align-items:baseline; }}
  .p2-fin-title {{ font-family:{fonts['serif']}; font-weight:700; font-size:13pt;
    color:{C['navy']}; margin-right:4mm; }}
  .p2-fin-sub {{ font-size:8pt; color:{C['muted']}; }}
  .p2-fin-grid {{ display:flex; gap:7mm; align-items:stretch; margin-top:2mm; }}
  .p2-fin-chart {{ flex:1 1 60%; display:flex; align-items:center; }}
  .p2-fin-chart img {{ width:100%; max-height:42mm; height:auto;
    object-fit:contain; }}
  .p2-fin-panel {{ flex:0 0 36%; display:flex; flex-direction:column;
    justify-content:center; gap:3mm; border-left:1px solid {C['line']};
    padding-left:6mm; }}
  .p2-fin-k {{ display:block; font-size:6.8pt; letter-spacing:.11em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    margin-bottom:1mm; }}
  .p2-fin-v {{ display:block; font-family:{fonts['display']}; font-size:18pt;
    color:{C['navy']}; line-height:1; }}
  .p2-fin-v small {{ font-family:{fonts['sans']}; font-size:8.5pt;
    color:{C['muted']}; font-weight:600; }}
  .p2-fin-s {{ display:block; font-size:7.2pt; color:{C['muted']};
    margin-top:1mm; }}
</style>
"""

    html = f"""
{style}
<div class="p2-wrap">

  <div class="p2-kick">Votre installation</div>
  <div class="p2-title">Le détail de votre projet</div>

  <div class="p2-band">
    <div class="p2-roof"><img src="{charts['roof']}" alt="Schéma de l'installation"></div>
    <div class="p2-specs">{spec_html}</div>
  </div>

  <div class="p2-lbl">Équipement commun aux deux options</div>
  <table class="p2-tbl">
    <thead>
      <tr>
        <th class="p2-d">Désignation</th>
        <th class="p2-c">Qté</th>
        <th class="p2-r">P.U. HT</th>
        <th class="p2-c">TVA</th>
        <th class="p2-r">Total HT</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>

  <div class="p2-deltas">
    <div class="p2-dcard">
      <div class="p2-dhead" style="background:{C['navy']}">
        Option 1 — Sans batterie <small>ajoute</small>
      </div>
      <div class="p2-dbody"><ul>{delta_sans_html}</ul></div>
    </div>
    <div class="p2-dcard">
      <div class="p2-dhead" style="background:{C['gold']}">
        Option 2 — Avec batterie <small>ajoute</small>
      </div>
      <div class="p2-dbody"><ul>{delta_avec_html}</ul></div>
    </div>
  </div>

  <div class="p2-fiche">Fiches techniques complètes des produits →
    <b>{produits_link}</b></div>

  <div class="p2-totals">
    {totals_sans}
    {totals_avec}
  </div>
  <div class="p2-tva-note">{tva_note}</div>

  <div class="p2-fin">
    <div class="p2-fin-head">
      <span class="p2-fin-title">Rentabilité sur 25 ans</span>
      <span class="p2-fin-sub">gain cumulé, deux scénarios — le point marque le retour sur investissement</span>
    </div>
    <div class="p2-fin-grid">
      <div class="p2-fin-chart"><img src="{charts['payback']}" alt="Courbe de rentabilité 25 ans"></div>
      <div class="p2-fin-panel">
        <div>
          <span class="p2-fin-k">Retour sur investissement</span>
          <span class="p2-fin-v">{roi_range}</span>
        </div>
        <div>
          <span class="p2-fin-k">Gain net sur 25 ans</span>
          <span class="p2-fin-v">≈ {fmt(gain25)} <small>MAD</small></span>
          <span class="p2-fin-s">option avec batterie</span>
        </div>
        <div>
          <span class="p2-fin-k">Production garantie</span>
          <span class="p2-fin-v">25 ans</span>
          <span class="p2-fin-s">panneaux &amp; performance</span>
        </div>
      </div>
    </div>
  </div>

</div>
"""
    return html
