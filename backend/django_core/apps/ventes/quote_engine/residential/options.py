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


def _produits_href(produits_base):
    """https URL of the fiches library hub from a bare 'taqinor.ma/produits'."""
    base = (produits_base or "taqinor.ma/produits").strip().rstrip("/")
    return base if base.startswith("http") else "https://" + base


def _name_html(it, produits_base):
    """Product name, linked to its fiche-technique page on taqinor.ma when one
    exists (panels, inverters, batteries, meter, dongle) — a tiny ' ›' marks it
    clickable; TAQINOR's own lines (structures, socles, installation…) stay
    plain text."""
    from . import theme
    desig = it["designation"]
    href = theme.fiche_href(desig, it.get("marque") or "", produits_base)
    if not href:
        return f'<span class="p2-name">{desig}</span>'
    return (f'<a class="p2-name p2-fiche-lnk" href="{href}">{desig}'
            f'<span class="p2-fiche-i">&rsaquo;</span></a>')


def _row(it, fmt, produits_base="taqinor.ma/produits"):
    """One <tr> for the shared equipment table."""
    marque = it.get("marque") or ""
    qte = it["quantite"]
    qte_txt = f"{qte:g}"
    pu = fmt(it["prix_unit_ht"])
    tva = f"{int(round(it['taux_tva']))}%"
    total_ht = fmt(it["prix_unit_ht"] * it["quantite"])
    marque_html = (f'<span class="p2-mk">{marque}</span>' if marque else "")
    return (
        f'<tr>'
        f'<td class="p2-d">{_name_html(it, produits_base)}{marque_html}</td>'
        f'<td class="p2-c">{qte_txt}</td>'
        f'<td class="p2-r">{pu}</td>'
        f'<td class="p2-c p2-tva">{tva}</td>'
        f'<td class="p2-r p2-tot">{total_ht}</td>'
        f'</tr>'
    )


def _delta_lines(items, fmt, produits_base="taqinor.ma/produits"):
    """Compact list of the extra products one option adds."""
    out = []
    for it in items:
        qte = it["quantite"]
        q = f"{qte:g}× " if qte and qte != 1 else ""
        total_ht = fmt(it["prix_unit_ht"] * it["quantite"])
        out.append(
            f'<li><span class="p2-dl-n">{q}{_name_html(it, produits_base)}</span>'
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
    from . import theme

    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    charts = ctx["charts"]
    links = d.get("links", {})

    # QX5 — deux options seulement quand le devis en porte réellement deux.
    # Mono-option : la page 2 abandonne le découpage delta et renomme l'en-tête
    # « commun aux deux options ». Repli sûr : sans drapeau, deux-options.
    deux_options = bool(d.get("deux_options", True))
    avec_ok = bool(d.get("avec_ok", True))

    if deux_options:
        shared, delta_sans, delta_avec = _split_items(
            d["sans_items"], d["avec_items"]
        )
    else:
        # Une seule option : toutes ses lignes forment le tableau d'équipement
        # (aucun delta à comparer).
        shared = d["avec_items"] if avec_ok else d["sans_items"]
        delta_sans, delta_avec = [], []

    # ── Top spec list ────────────────────────────────────────────────────────
    specs = [
        (f'{d["puissance_kwc"]:g}'.replace(".", ","), "kWc installés"),
        (f'{d["nb_panneaux"]:g}', f'panneaux · {d["watt_par_panneau"]:g} W'),
        (fmt(d["prod_kwh"]), "kWh / an produits"),
    ]
    spec_html = "".join(
        f'<div class="p2-spec"><span class="p2-spec-v">{v}</span>'
        f'<span class="p2-spec-l">{l}</span></div>'
        for v, l in specs
    )

    produits_link = links.get("produits", d.get("site_url", "taqinor.ma"))

    rows_html = "".join(_row(it, fmt, produits_link) for it in shared)
    delta_sans_html = _delta_lines(delta_sans, fmt, produits_link)
    delta_avec_html = _delta_lines(delta_avec, fmt, produits_link)

    # QX5 — le bloc « ce que chaque option ajoute » n'existe QUE pour un vrai
    # devis à deux options ; mono-option → aucun découpage delta.
    if deux_options:
        deltas_html = (
            '<div class="p2-deltas">'
            '<div class="p2-dcard">'
            f'<div class="p2-dhead" style="background:{C["navy"]}">'
            'Option 1 — Sans batterie <small>ajoute</small></div>'
            f'<div class="p2-dbody"><ul>{delta_sans_html}</ul></div></div>'
            '<div class="p2-dcard">'
            f'<div class="p2-dhead" style="background:{C["gold"]}">'
            'Option 2 — Avec batterie <small>ajoute</small></div>'
            f'<div class="p2-dbody"><ul>{delta_avec_html}</ul></div></div>'
            '</div>')
    else:
        deltas_html = ""

    if deux_options:
        totals_html = (
            _totals_chain("Option 1 — Sans batterie", C["navy"],
                          d["totaux_sans"], fmt, C)
            + _totals_chain("Option 2 — Avec batterie", C["gold"],
                            d["totaux_avec"], fmt, C, recommended=True))
        equipement_lbl = "Équipement commun aux deux options"
    else:
        # QX5 — une seule carte de totaux pour l'unique option réelle.
        _tot = d["totaux_avec"] if avec_ok else d["totaux_sans"]
        _lbl = ("Total — Avec batterie" if avec_ok
                else "Total — Sans batterie")
        _acc = C["gold"] if avec_ok else C["navy"]
        totals_html = _totals_chain(_lbl, _acc, _tot, fmt, C)
        equipement_lbl = "Votre équipement"

    tva_note = d.get("tva_note", "")

    # ── QJ30 — multi-propriétés (rendu ; dégrade à la mise en page à plat) ────
    # (A) ×N villas identiques : ligne « × N propriétés identiques » + total mis
    #     à l'échelle. (B) villas différentes : sous-totaux par villa + total
    #     général. Vides → aucun rendu (page 2 inchangée au bit près).
    multi_html = ""
    _nprop = d.get("nombre_proprietes")
    if _nprop and _nprop > 1:
        _dtm = d.get("display_total_multi")
        _tot_txt = (f' — total pour {_nprop} propriétés : {fmt(_dtm)} MAD'
                    if _dtm else "")
        multi_html += (
            f'<div class="p2-multi-n">&times;&nbsp;{_nprop} propriétés '
            f'identiques{_tot_txt}</div>')
    _mv = d.get("multi_villa") or {}
    if _mv.get("groupes"):
        _vrows = ""
        for g in _mv["groupes"]:
            t = g.get("totaux") or {}
            _vrows += (
                f'<tr><td>{g.get("label", "")}</td>'
                f'<td class="p2-r">{fmt(t.get("ht_net", 0))}</td>'
                f'<td class="p2-r p2-tot">{fmt(t.get("ttc", 0))} MAD</td></tr>')
        _gt = _mv.get("grand_total") or {}
        _vrows += (
            f'<tr class="p2-multi-gt"><td>Total général</td>'
            f'<td class="p2-r">{fmt(_gt.get("ht_net", 0))}</td>'
            f'<td class="p2-r">{fmt(_gt.get("ttc", 0))} MAD</td></tr>')
        multi_html += (
            '<div class="p2-multi-lbl">Détail par propriété</div>'
            '<table class="p2-multi"><thead><tr>'
            '<th>Propriété</th><th class="p2-r">Total HT</th>'
            '<th class="p2-r">Total TTC</th></tr></thead>'
            f'<tbody>{_vrows}</tbody></table>')
    if multi_html:
        multi_html = f'<div class="p2-multi-wrap">{multi_html}</div>'

    # ── Payback takeaway figures (read straight off the quote data) ───────────
    def _yrs(v):
        return f"{v:g}".replace(".", ",") if v else "—"
    roi_s, roi_a = d.get("roi_s"), d.get("roi_a")
    # QX5 — deux options → fourchette de ROI ; mono-option → le ROI de l'option
    # réelle seul (jamais une fourchette entre une option et un fantôme).
    if deux_options and roi_s and roi_a:
        lo, hi = sorted((roi_s, roi_a))
        roi_range = f"{_yrs(lo)} – {_yrs(hi)} ans"
    else:
        _roi_one = (roi_a if avec_ok else roi_s)
        roi_range = f"{_yrs(_roi_one)} ans" if _roi_one else "—"
    # QX5 — gain net 25 ans + libellé calés sur l'option réellement présente
    # (jamais « option avec batterie » sur un devis sans batterie).
    if deux_options or avec_ok:
        _eco_ref, _tot_ref = d.get("eco_a_ann", 0), d.get("total_avec", 0)
        gain25_label = "option avec batterie" if deux_options else "avec batterie"
    else:
        _eco_ref, _tot_ref = d.get("eco_s_ann", 0), d.get("total_sans", 0)
        gain25_label = "sans batterie"
    gain25 = max(0, round(_eco_ref * 25 - _tot_ref))
    gain25 = round(gain25 / 1000) * 1000

    # QRES3 — sous-titre du graphe fidèle au devis : « deux scénarios »
    # seulement quand le document porte réellement deux options.
    fin_sub = ("gain cumulé, deux scénarios — le point marque le retour "
               "sur investissement" if deux_options
               else "gain cumulé — le point marque le retour sur investissement")

    # QRES5 — badges de garantie (déplacés de la page 3) : ils meublent le bas
    # de la page 2, à côté de l'équipement qu'ils couvrent, et allègent la
    # page 3. Une seule source : theme.WARRANTIES.
    badges_html = "".join(
        f'<div class="p2-badge"><div class="p2-badge-n">{n}'
        f'<span class="p2-badge-u">{u}</span></div>'
        f'<div class="p2-badge-l">{label}</div></div>'
        for n, u, label in theme.WARRANTIES)

    # QRES6 — densité adaptative : un devis à beaucoup de lignes serre le
    # tableau au lieu de pousser la page en débordement (.page = A4 FIXE).
    _nrows = len(shared) + (len(delta_sans) + len(delta_avec)
                            if deux_options else 0)
    dense_cls = " p2-dense" if _nrows > 9 else ""

    style = f"""
<style>
  .p2-wrap {{ padding:7mm 14mm 6mm 14mm; }}

  /* Section header */
  .p2-kick {{ font-size:8.5pt; letter-spacing:.22em; text-transform:uppercase;
    color:{C['gold']}; font-weight:700; }}
  .p2-title {{ font-family:{fonts['serif']}; font-weight:700; font-size:21.5pt;
    color:{C['navy']}; line-height:1.04; margin-top:1.5mm; letter-spacing:-.3px; }}

  /* Top band: roof schematic + spec list */
  .p2-band {{ display:flex; align-items:center; gap:6mm; margin-top:2.5mm;
    padding:1.7mm 5mm; background:{C['wash']}; border:1px solid {C['line']};
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
    color:{C['navy']}; font-weight:700; margin:3.5mm 0 1.5mm; }}

  /* Shared equipment table */
  .p2-tbl {{ width:100%; border-collapse:collapse; font-size:8.7pt; }}
  .p2-tbl thead th {{ font-size:7.4pt; letter-spacing:.08em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    text-align:left; padding:0 0 2mm; border-bottom:1.5px solid {C['line']}; }}
  .p2-tbl th.p2-c, .p2-tbl td.p2-c {{ text-align:center; }}
  .p2-tbl th.p2-r, .p2-tbl td.p2-r {{ text-align:right; }}
  .p2-tbl tbody td {{ padding:1.15mm 0; border-bottom:1px solid {C['line_soft']};
    vertical-align:middle; }}
  .p2-tbl tbody tr:nth-child(even) td {{ background:{C['wash']}; }}
  .p2-tbl tbody td.p2-d {{ padding-left:2.5mm; }}
  .p2-tbl tbody td.p2-tot {{ padding-right:2.5mm; }}
  .p2-name {{ color:{C['ink']}; font-weight:600; text-decoration:none; }}
  .p2-fiche-lnk {{ color:{C['navy']}; }}
  .p2-fiche-i {{ color:{C['gold']}; font-weight:700; margin-left:3px; }}
  .p2-mk {{ color:{C['muted']}; font-size:7.6pt; margin-left:5px; }}
  .p2-tva {{ color:{C['muted']}; font-size:8pt; }}
  .p2-tot {{ font-weight:700; color:{C['navy']}; white-space:nowrap; }}

  /* Per-option delta mini-cards */
  .p2-deltas {{ display:flex; gap:5mm; margin-top:2mm; align-items:stretch; }}
  .p2-dcard {{ flex:1; border:1px solid {C['line']}; border-radius:10px;
    overflow:hidden; display:flex; flex-direction:column; }}
  .p2-dhead {{ padding:2.2mm 3.5mm; font-size:8.4pt; font-weight:700;
    color:#fff; }}
  .p2-dhead small {{ font-weight:500; opacity:.85; }}
  .p2-dbody {{ flex:1 1 auto; display:flex; align-items:center; }}
  .p2-dbody ul {{ list-style:none; width:100%; }}
  .p2-dbody li {{ display:flex; justify-content:space-between; align-items:center;
    padding:1.7mm 3.5mm; font-size:8.5pt; border-bottom:1px solid {C['line_soft']}; }}
  .p2-dbody li:last-child {{ border-bottom:none; }}
  .p2-dl-n {{ color:{C['ink']}; }}
  .p2-dl-p {{ color:{C['navy']}; font-weight:700; white-space:nowrap;
    margin-left:6px; }}

  .p2-fiche {{ font-size:8pt; color:{C['muted']}; margin-top:2mm; }}
  .p2-fiche-btn {{ text-decoration:none; color:{C['navy']}; font-weight:700;
    white-space:nowrap; }}
  .p2-fiche-i {{ color:{C['gold']}; font-weight:700; }}

  /* Totals chains side by side */
  .p2-totals {{ display:flex; gap:5mm; margin-top:2.5mm; }}
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

  /* Finance: rentabilité — the curve gets real height BESIDE airy stats */
  .p2-fin {{ margin-top:2mm; }}
  .p2-fin-head {{ display:flex; align-items:baseline; }}
  .p2-fin-title {{ font-family:{fonts['serif']}; font-weight:700; font-size:14pt;
    color:{C['navy']}; margin-right:4mm; }}
  .p2-fin-sub {{ font-size:8pt; color:{C['muted']}; }}

  /* CSS table: chart cell (left, full height) + stats cell (right, airy) */
  .p2-fin-grid {{ display:table; width:100%; table-layout:fixed; margin-top:2.5mm; }}
  .p2-fin-cc {{ display:table-cell; width:60%; vertical-align:middle; }}
  .p2-fin-cc img {{ display:block; height:33mm; width:auto; }}
  .p2-fin-sc {{ display:table-cell; width:39%; vertical-align:middle;
    padding-left:9mm; }}
  .p2-side-stat {{ margin-bottom:2.5mm; }}
  .p2-side-stat:last-child {{ margin-bottom:0; }}
  .p2-stat-k {{ display:block; font-size:6.7pt; letter-spacing:.12em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    margin-bottom:0.8mm; }}
  .p2-stat-v {{ display:block; font-family:{fonts['display']}; font-size:14.5pt;
    color:{C['navy']}; line-height:1; }}
  .p2-stat-v small {{ font-family:{fonts['sans']}; font-size:8pt;
    color:{C['muted']}; font-weight:600; }}
  .p2-stat-s {{ display:block; font-size:7.2pt; color:{C['muted']};
    margin-top:0.8mm; line-height:1.2; }}
  .p2-stat-s b {{ color:{C['green']}; font-weight:700; }}
  .p2-fin-cap {{ font-size:7.3pt; color:{C['muted']}; text-align:center;
    margin-top:3mm; font-style:italic; }}
  .p2-fin-cap b {{ color:{C['navy']}; font-weight:700; font-style:normal; }}

  /* QRES5 — garanties (badges déplacés de la page 3) */
  .p2-badges {{ display:flex; gap:9px; margin-top:1.5mm; }}
  .p2-badge {{ flex:1; text-align:center; border:1px solid {C['line']};
    border-top:3px solid {C['gold']}; border-radius:11px; padding:9px 4px 8px;
    background:{C['paper']}; }}
  .p2-badge-n {{ font-family:{fonts['display']}; font-size:19pt;
    color:{C['navy']}; line-height:1; }}
  .p2-badge-u {{ font-family:{fonts['sans']}; font-size:7.5pt;
    color:{C['gold']}; font-weight:700; margin-left:3px; }}
  .p2-badge-l {{ font-size:7.2pt; color:{C['muted']}; font-weight:600;
    margin-top:4px; letter-spacing:.02em; }}

  /* QRES6 — densité adaptative pour les tableaux longs */
  .p2-dense .p2-tbl {{ font-size:8.1pt; }}
  .p2-dense .p2-tbl tbody td {{ padding:0.8mm 0; }}
  .p2-dense .p2-band {{ padding:1.2mm 5mm; }}
  .p2-dense .p2-dbody li {{ padding:1.2mm 3.5mm; font-size:8.1pt; }}
  .p2-dense .p2-fin-cc img {{ height:29mm; }}
  .p2-dense .p2-badge {{ padding:7px 4px 6px; }}
  .p2-dense .p2-badge-n {{ font-size:16pt; }}

  /* QJ30 — multi-propriétés */
  .p2-multi-wrap {{ margin-top:2.5mm; }}
  .p2-multi-n {{ background:{C['wash']}; border:1px solid {C['gold']};
    border-radius:8px; padding:1.6mm 4mm; font-size:8.4pt; color:{C['navy']};
    font-weight:700; margin-bottom:2mm; }}
  .p2-multi-lbl {{ font-size:8pt; letter-spacing:.12em; text-transform:uppercase;
    color:{C['navy']}; font-weight:700; margin:1mm 0 1.2mm; }}
  .p2-multi {{ width:100%; border-collapse:collapse; font-size:8.3pt; }}
  .p2-multi th {{ font-size:7pt; letter-spacing:.06em; text-transform:uppercase;
    color:{C['muted_2']}; font-weight:700; text-align:left;
    padding:0 4mm 1mm 0; border-bottom:1px solid {C['line']}; }}
  .p2-multi td {{ padding:1.1mm 4mm 1.1mm 0; border-bottom:1px solid {C['line_soft']};
    color:{C['ink']}; }}
  .p2-multi .p2-multi-gt td {{ font-weight:800; color:{C['navy']};
    border-top:1.5px solid {C['navy']}; border-bottom:none; }}
</style>
"""

    html = f"""
{style}
<div class="p2-wrap{dense_cls}">

  <div class="p2-kick">Votre installation</div>
  <div class="p2-title">Le détail de votre projet</div>

  <div class="p2-band">
    <div class="p2-roof"><img src="{charts['roof']}" alt="Schéma de l'installation"></div>
    <div class="p2-specs">{spec_html}</div>
  </div>

  <div class="p2-lbl">{equipement_lbl}</div>
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

  {deltas_html}

  <div class="p2-fiche">Chaque équipement renvoie à sa fiche technique complète —
    bibliothèque&nbsp;: <a class="p2-fiche-btn"
    href="{_produits_href(produits_link)}">{produits_link}<span class="p2-fiche-i"> &rsaquo;</span></a></div>

  <div class="p2-totals">
    {totals_html}
  </div>
  <div class="p2-tva-note">{tva_note}</div>
  {multi_html}

  <div class="p2-fin">
    <div class="p2-fin-head">
      <span class="p2-fin-title">Rentabilité sur 25 ans</span>
      <span class="p2-fin-sub">{fin_sub}</span>
    </div>

    <div class="p2-fin-grid">
      <div class="p2-fin-cc">
        <img src="{charts['payback']}" alt="Courbe de rentabilité sur 25 ans">
      </div>
      <div class="p2-fin-sc">
        <div class="p2-side-stat">
          <span class="p2-stat-k">Retour sur investissement</span>
          <span class="p2-stat-v">{roi_range}</span>
          <span class="p2-stat-s">l'installation se rembourse</span>
        </div>
        <div class="p2-side-stat">
          <span class="p2-stat-k">Gain net sur 25 ans</span>
          <span class="p2-stat-v">≈ {fmt(gain25)} <small>MAD</small></span>
          <span class="p2-stat-s">{gain25_label}</span>
        </div>
        <div class="p2-side-stat">
          <span class="p2-stat-k">Performance garantie</span>
          <span class="p2-stat-v">30 ans</span>
          <span class="p2-stat-s">panneaux — 87,4 % de rendement à 30 ans</span>
        </div>
      </div>
    </div>

    <div class="p2-fin-cap">
      Projection <b>à tarif ONEE constant</b> — toute hausse future du prix de
      l'électricité accélère votre rentabilité, votre coût solaire restant fixe.
    </div>
  </div>

  <div class="p2-lbl">Nos garanties</div>
  <div class="p2-badges">{badges_html}</div>

</div>
"""
    return html
