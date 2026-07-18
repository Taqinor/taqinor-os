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


def build_pages(ctx) -> list:
    """QRES17 — pagination VARIABLE (fondateur, 2026-07-18).

    Rend 1..N pages « Votre installation » : un devis standard tient sur UNE
    page (l'historique) ; un devis chargé (10+ lignes) découpe proprement —
    page équipement (tableau complet, découpé par tranches de hauteur s'il le
    faut, avec « suite ») puis page rentabilité dédiée (courbe plus grande +
    garanties). Le pied « Page n / N » suit tout seul (QX6). Jamais de
    débordement rogné ni de 4ᵉ page orpheline.
    """
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
    # QRES27 — en-têtes recomposés (« Spécifique à … », plus de « ajoute »
    # pendu), texte NAVY sur la barre or (jamais blanc sur #F5A623 — contraste)
    # et une ligne « Pourquoi » sous l'option recommandée qui JUSTIFIE la
    # recommandation au lieu de la seule pastille.
    if deux_options:
        deltas_html = (
            '<div class="p2-deltas">'
            '<div class="p2-dcard">'
            f'<div class="p2-dhead" style="background:{C["navy"]}">'
            'Spécifique à l&rsquo;option 1 — Sans batterie</div>'
            f'<div class="p2-dbody"><ul>{delta_sans_html}</ul></div></div>'
            '<div class="p2-dcard">'
            f'<div class="p2-dhead" style="background:{C["gold"]};'
            f'color:{C["navy"]}">'
            'Spécifique à l&rsquo;option 2 — Avec batterie</div>'
            f'<div class="p2-dbody"><ul>{delta_avec_html}</ul>'
            '<div class="p2-dwhy">Pourquoi nous la recommandons : vos '
            'soirées et les coupures passent sur batterie.</div></div></div>'
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
    # QRES28 — le multiple (« ≈ 5,6× votre investissement ») rend le gain net
    # tangible ; calculé, jamais inventé (gain net / investissement).
    gain_mult = (round(gain25 / _tot_ref, 1) if _tot_ref and gain25 > 0
                 else None)
    gain_mult_txt = (f"{gain_mult:g}".replace(".", ",")
                     if gain_mult and gain_mult >= 1 else None)
    gain_mult_sub = (
        f" — soit ≈ <b>{gain_mult_txt}×</b> votre investissement"
        if gain_mult_txt else "")

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
        f'<div class="p2-badge-l">{label}</div>'
        f'<div class="p2-badge-s">{sub}</div></div>'
        for n, u, label, sub in theme.WARRANTIES)

    # ── QRES17 — modèle de hauteur (mm) : décide si tout tient sur UNE page ──
    # Estimations calibrées sur le rendu réel (110 dpi) avec marge de sécurité ;
    # la garde CI (pages exactes + bande légale non rognée) verrouille le tout.
    def _row_mm(it):
        return 4.5 + (3.2 if len(str(it.get("designation") or "")) > 55
                      else 0.0)

    def _table_mm(items):
        return 6.5 + sum(_row_mm(it) for it in items)

    def _deltas_mm():
        if not deux_options:
            return 0.0
        rows = max(len(delta_sans), len(delta_avec), 1)
        return 7.0 + rows * 4.6

    # QRES49 (fondateur, 2026-07-18) — FINI le mode « dense » qui écrasait la
    # courbe de rentabilité pour tasser un devis chargé en 3 pages : un devis
    # dont l'équipement dépasse le confort de la page unique PASSE en mise en
    # page multi-pages — tableau à l'aise + la page rentabilité dédiée (grande
    # courbe) que le fondateur préfère. La densité ne rapetisse plus jamais le
    # graphe ni les badges.
    fits_one = (_table_mm(shared) + _deltas_mm()) <= 46.0

    def _chunk_rows(items, budgets):
        """Découpe les lignes par tranches de hauteur (budgets mm par page)."""
        out, cur, h, bi = [], [], 0.0, 0
        for it in items:
            ih = _row_mm(it)
            budget = budgets[min(bi, len(budgets) - 1)]
            if cur and h + ih > budget:
                out.append(cur)
                cur, h, bi = [], 0.0, bi + 1
            cur.append(it)
            h += ih
        if cur:
            out.append(cur)
        return out

    style = f"""
<style>
  .p2-wrap {{ padding:6mm 14mm 5mm 14mm; }}

  /* Section header */
  .p2-kick {{ font-size:8.5pt; letter-spacing:.22em; text-transform:uppercase;
    color:{C['gold']}; font-weight:700; }}
  .p2-title {{ font-family:{fonts['serif']}; font-weight:700; font-size:21.5pt;
    color:{C['navy']}; line-height:1.04; margin-top:1.5mm; letter-spacing:-.3px; }}

  /* Top band: roof schematic + spec list */
  .p2-band {{ display:flex; align-items:center; gap:6mm; margin-top:2mm;
    padding:1.2mm 5mm; background:{C['wash']}; border:1px solid {C['line']};
    border-radius:12px; }}
  .p2-roof {{ flex:0 0 32mm; text-align:center; }}
  .p2-roof img {{ width:30mm; height:auto; }}
  /* QRES39 — photo réelle de toiture : cadrée, arrondie, légendée */
  .p2-roof-photo {{ width:30mm; height:17.5mm; object-fit:cover;
    border-radius:9px; display:block; margin:0 auto; }}
  .p2-roof-cap {{ font-size:6.3pt; color:{C['muted_2']}; margin-top:0.8mm;
    letter-spacing:.06em; text-transform:uppercase; font-weight:700; }}
  .p2-specs {{ flex:1; display:flex; gap:5mm; }}
  .p2-spec {{ flex:1; display:flex; flex-direction:column; gap:1mm;
    padding-left:5mm; border-left:2px solid {C['line']}; }}
  .p2-spec:first-child {{ border-left:none; padding-left:0; }}
  .p2-spec-v {{ font-family:{fonts['display']}; font-size:18pt;
    color:{C['navy']}; line-height:1; }}
  .p2-spec-l {{ font-size:8pt; color:{C['muted']}; line-height:1.2; }}

  /* Block label */
  .p2-lbl {{ font-size:8.5pt; letter-spacing:.16em; text-transform:uppercase;
    color:{C['navy']}; font-weight:700; margin:3mm 0 1.5mm; }}

  /* Shared equipment table */
  .p2-tbl {{ width:100%; border-collapse:collapse; font-size:8.7pt; }}
  .p2-tbl thead th {{ font-size:7.4pt; letter-spacing:.08em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    text-align:left; padding:0 0 2mm; border-bottom:1.5px solid {C['line']}; }}
  .p2-tbl th.p2-c, .p2-tbl td.p2-c {{ text-align:center; }}
  /* QRES36 — gouttière P.U. ↔ TVA (les deux colonnes se frôlaient) */
  .p2-tbl th:nth-child(4), .p2-tbl td:nth-child(4) {{ padding-left:14px; }}
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
  .p2-deltas {{ display:flex; gap:5mm; margin-top:1.5mm; align-items:stretch; }}
  .p2-dcard {{ flex:1; border:1px solid {C['line']}; border-radius:10px;
    overflow:hidden; display:flex; flex-direction:column; }}
  .p2-dhead {{ padding:2.2mm 3.5mm; font-size:8.4pt; font-weight:700;
    color:#fff; }}
  .p2-dhead small {{ font-weight:500; opacity:.85; }}
  /* QRES35 — display:block (PAS flex-column) : WeasyPrint rétrécissait la
     colonne désignation et superposait prix et « Pourquoi » (cf.
     RENDERING_NOTES, pièges flex). */
  .p2-dbody {{ display:block; }}
  .p2-dbody ul {{ list-style:none; width:100%; }}
  .p2-dwhy {{ padding:1.1mm 3.5mm 1.4mm; font-size:7.6pt; color:{C['muted']};
    border-top:1px solid {C['line_soft']}; }}
  .p2-dbody li {{ display:flex; justify-content:space-between; align-items:center;
    padding:1.7mm 3.5mm; font-size:8.5pt; border-bottom:1px solid {C['line_soft']}; }}
  .p2-dbody li:last-child {{ border-bottom:none; }}
  .p2-dl-n {{ color:{C['ink']}; }}
  .p2-dl-p {{ color:{C['navy']}; font-weight:700; white-space:nowrap;
    margin-left:6px; }}

  .p2-fiche {{ font-size:8pt; color:{C['muted']}; margin-top:1.5mm; }}
  .p2-fiche-btn {{ text-decoration:none; color:{C['navy']}; font-weight:700;
    white-space:nowrap; }}
  .p2-fiche-i {{ color:{C['gold']}; font-weight:700; }}

  /* Totals chains side by side */
  .p2-totals {{ display:flex; gap:5mm; margin-top:2mm; }}
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
  .p2-tva-note {{ font-size:7.4pt; color:{C['muted']}; margin-top:1.5mm;
    text-align:center; }}

  /* Finance: rentabilité — the curve gets real height BESIDE airy stats */
  .p2-fin {{ margin-top:1.5mm; }}
  /* QRES29 — sous-titre sur SA ligne (l'inline collait au titre serif) */
  .p2-fin-head {{ display:block; }}
  .p2-fin-title {{ display:block; font-family:{fonts['serif']};
    font-weight:700; font-size:13pt; color:{C['navy']}; }}
  .p2-fin-sub {{ display:block; font-size:7.8pt; color:{C['muted']};
    margin-top:0.2mm; }}
  .p2-side-gain .p2-stat-s b {{ color:{C['gold_soft']}; }}
  .p2-callout {{ margin-top:6mm; background:{C['navy']}; color:#fff;
    border-radius:12px; padding:5mm 7mm; font-family:{fonts['display']};
    font-size:13.5pt; line-height:1.25; }}
  .p2-callout b {{ color:{C['gold']}; font-weight:400; }}
  /* margin-left:auto est ignoré par WeasyPrint sur ce conteneur flex →
     marge déterministe pour caler le TOTAL TTC sur le rail monétaire droit. */
  .p2-totals-solo {{ width:60%; margin-left:40%; }}
  .p2-tbl tbody td {{ font-feature-settings:'tnum' 1; }}
  .p2-dcard, .p2-badge {{ box-shadow:0 1px 2px rgba(26,43,74,.04),
    0 5px 14px rgba(26,43,74,.05); }}

  /* CSS table: chart cell (left, full height) + stats cell (right, airy) */
  /* QRES51 — courbe agrandie (retour fondateur) : 36 mm au lieu de 28,5,
     compensée par les marges resserrées de la page. */
  .p2-fin-grid {{ display:table; width:100%; table-layout:fixed; margin-top:1.5mm; }}
  .p2-fin-cc {{ display:table-cell; width:62%; vertical-align:middle; }}
  .p2-fin-cc img {{ display:block; height:36mm; width:auto; max-width:100%; }}
  .p2-fin-sc {{ display:table-cell; width:38%; vertical-align:middle;
    padding-left:8mm; }}
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
    margin-top:2mm; font-style:italic; }}
  .p2-fin-cap b {{ color:{C['navy']}; font-weight:700; font-style:normal; }}

  /* QRES5 — garanties (badges déplacés de la page 3) */
  .p2-badges {{ display:flex; gap:9px; margin-top:0.8mm; }}
  .p2-badge {{ flex:1; text-align:center; border:1px solid {C['line']};
    border-top:3px solid {C['gold']}; border-radius:11px; padding:7px 4px 6px;
    background:{C['paper']}; }}
  .p2-badge-n {{ font-family:{fonts['display']}; font-size:17pt;
    color:{C['navy']}; line-height:1; }}
  .p2-badge-u {{ font-family:{fonts['sans']}; font-size:7.5pt;
    color:{C['gold']}; font-weight:700; margin-left:3px; }}
  .p2-badge-l {{ font-size:7.4pt; color:{C['navy']}; font-weight:700;
    margin-top:4px; letter-spacing:.05em; text-transform:uppercase; }}
  .p2-badge-s {{ font-size:6.4pt; color:{C['muted_2']}; margin-top:1.5px;
    text-transform:none; letter-spacing:0; font-weight:500; }}

  /* QRES17 — pages de continuation / page rentabilité dédiée */
  .p2-cont-note {{ font-size:7.6pt; color:{C['muted']}; font-style:italic;
    margin-top:2mm; text-align:right; }}
  /* QRES37/38 — page rentabilité : courbe pleine largeur (bornée par la
     largeur, jamais par une hauteur fixe qui la faisait déborder), stats en
     rangée de trois sous la courbe. */
  .p2-fin-wide {{ display:block; width:100%; height:auto; margin-top:4mm; }}
  .p2-finstats {{ display:flex; gap:8mm; margin-top:5mm; }}
  .p2-finstats .p2-side-stat {{ flex:1; margin-bottom:0; padding:4mm 5mm;
    background:{C['paper']}; border:1px solid {C['line']}; border-radius:11px;
    box-shadow:0 1px 2px rgba(26,43,74,.04),0 5px 14px rgba(26,43,74,.05); }}
  .p2-fin-xl .p2-fin-sub {{ margin-top:0; }}
  .p2-fin-xl {{ margin-top:6mm; }}
  .p2-finpage-badges {{ margin-top:7mm; }}

  /* QRES50 — bande financement de la page rentabilité (économies − crédit =
     dans votre poche) : séparation par cellules fixes, jamais par flex gap */
  .p2-finband {{ display:flex; align-items:stretch; margin-top:1mm; }}
  .p2-fb-c {{ flex:1; text-align:center; padding:4mm 3mm;
    background:{C['paper']}; border:1px solid {C['line']}; border-radius:11px;
    box-shadow:0 1px 2px rgba(26,43,74,.04),0 5px 14px rgba(26,43,74,.05); }}
  .p2-fb-sep {{ flex:0 0 10mm; text-align:center; align-self:center;
    font-family:{fonts['display']}; font-size:15pt; color:{C['muted_2']}; }}
  .p2-fb-k {{ display:block; font-size:6.7pt; letter-spacing:.12em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    margin-bottom:1mm; }}
  .p2-fb-v {{ display:block; font-family:{fonts['display']}; font-size:14.5pt;
    color:{C['navy']}; }}
  .p2-fb-v small {{ font-family:{fonts['sans']}; font-size:7.5pt;
    color:{C['muted']}; font-weight:600; }}
  .p2-fb-net {{ border:1.5px solid {C['gold']}; background:#FFFCF5; }}
  .p2-fb-net .p2-fb-v {{ color:{C['gold_soft']}; }}

  /* QRES53 — bande impact environnemental (page rentabilité) */
  .p2-impact {{ display:flex; gap:8mm; margin-top:1mm; }}
  .p2-imp-c {{ flex:1; text-align:center; padding:3.5mm 3mm;
    background:linear-gradient(180deg,{C['green_bg']},#ffffff 85%);
    border:1px solid {C['green_bg']}; border-left:4px solid {C['green']};
    border-radius:11px; }}
  .p2-imp-v {{ display:block; font-family:{fonts['display']}; font-size:14.5pt;
    color:{C['green']}; }}
  .p2-imp-l {{ display:block; font-size:7pt; color:{C['muted']};
    margin-top:1mm; line-height:1.3; }}

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

    # ── QRES17 — fragments réutilisables, composés en 1..N pages ─────────────
    head_html = (
        '<div class="p2-kick">Votre installation</div>'
        '<div class="p2-title">Le détail de votre projet</div>')
    cont_head_html = (
        '<div class="p2-kick">Votre installation</div>'
        '<div class="p2-title">Équipement — suite</div>')
    fin_head_html = (
        '<div class="p2-kick">Votre rentabilité</div>'
        '<div class="p2-title">Rentabilité de votre investissement</div>')

    # QRES39 — la VRAIE toiture du client (photo/plan joint au devis) remplace
    # le schéma illustratif quand elle existe ; repli schéma sinon.
    roof_photo = (d.get("roof_photo") or "").strip()
    if roof_photo:
        band_visual = (
            f'<div><img class="p2-roof-photo" src="{roof_photo}" '
            f'alt="Votre toiture — implantation des panneaux">'
            '<div class="p2-roof-cap">Votre toiture</div></div>')
    else:
        band_visual = (f'<img src="{charts["roof"]}" '
                       'alt="Schéma de l\'installation">')
    band_html = (
        f'<div class="p2-band">'
        f'<div class="p2-roof">{band_visual}</div>'
        f'<div class="p2-specs">{spec_html}</div></div>')

    def _table_html(items, label):
        rows = "".join(_row(it, fmt, produits_link) for it in items)
        return (
            f'<div class="p2-lbl">{label}</div>'
            '<table class="p2-tbl"><thead><tr>'
            '<th class="p2-d">Désignation</th>'
            '<th class="p2-c">Qté</th>'
            '<th class="p2-r">P.U. HT</th>'
            '<th class="p2-c">TVA</th>'
            '<th class="p2-r">Total HT</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>')

    fiche_html = (
        '<div class="p2-fiche">Chaque équipement renvoie à sa fiche technique '
        'complète — bibliothèque&nbsp;: <a class="p2-fiche-btn" '
        f'href="{_produits_href(produits_link)}">{produits_link}'
        '<span class="p2-fiche-i"> &rsaquo;</span></a></div>')

    # QRES30/48 — mono-option : carte de totaux PLEINE LARGEUR (les montants
    # internes s'alignent déjà à droite, donc le TOTAL TTC retombe sur le rail
    # monétaire — sans laisser un demi-bloc mort à gauche).
    totals_wrap_cls = ""
    closing_html = (
        f'{deltas_html}'
        f'{fiche_html}'
        f'<div class="p2-totals{totals_wrap_cls}">{totals_html}</div>'
        f'<div class="p2-tva-note">{tva_note}</div>'
        f'{multi_html}')

    _stats_html = f"""
        <div class="p2-side-stat">
          <span class="p2-stat-k">Retour sur investissement</span>
          <span class="p2-stat-v">{roi_range}</span>
          <span class="p2-stat-s">l'installation se rembourse</span>
        </div>
        <div class="p2-side-stat p2-side-gain">
          <span class="p2-stat-k">Gain net sur 25 ans</span>
          <span class="p2-stat-v">≈ {fmt(gain25)} <small>MAD</small></span>
          <span class="p2-stat-s">{gain25_label}{gain_mult_sub}</span>
        </div>
        <div class="p2-side-stat">
          <span class="p2-stat-k">Performance garantie</span>
          <span class="p2-stat-v">30 ans</span>
          <span class="p2-stat-s">panneaux — 87,4 % de rendement à 30 ans</span>
        </div>"""
    _fin_cap = (
        '<div class="p2-fin-cap">Projection <b>à tarif ONEE constant</b> — '
        "toute hausse future du prix de l'électricité accélère votre "
        'rentabilité, votre coût solaire restant fixe.</div>')

    # QRES46 — sur la page rentabilité dédiée, le bandeau navy porte déjà le
    # gain net : la carte-stat « Gain net » disparaît (plus de doublon).
    _stats_xl_html = f"""
        <div class="p2-side-stat">
          <span class="p2-stat-k">Retour sur investissement</span>
          <span class="p2-stat-v">{roi_range}</span>
          <span class="p2-stat-s">l'installation se rembourse</span>
        </div>
        <div class="p2-side-stat">
          <span class="p2-stat-k">Performance garantie</span>
          <span class="p2-stat-v">30 ans</span>
          <span class="p2-stat-s">panneaux — 87,4 % de rendement à 30 ans</span>
        </div>"""

    def _fin_html(xl=False):
        if xl:
            # QRES38 — page rentabilité dédiée : composition VERTICALE (courbe
            # pleine largeur, stats en rangée dessous) — la page respire au
            # lieu de laisser sa moitié basse vide.
            # QRES51 — variante haute de la courbe (charts['payback_xl']) :
            # affichée sur 182 mm, elle gagne ~20 mm de hauteur et ses
            # polices déjà agrandies deviennent très lisibles.
            return f"""
  <div class="p2-fin p2-fin-xl">
    <div class="p2-fin-sub">{fin_sub}</div>
    <img class="p2-fin-wide" src="{charts.get('payback_xl', charts['payback'])}"
      alt="Courbe de rentabilité sur 25 ans">
    <div class="p2-finstats">{_stats_xl_html}</div>
    {_fin_cap}
  </div>"""
        return f"""
  <div class="p2-fin">
    <div class="p2-fin-head">
      <span class="p2-fin-title">Rentabilité sur 25 ans</span>
      <span class="p2-fin-sub">{fin_sub}</span>
    </div>

    <div class="p2-fin-grid">
      <div class="p2-fin-cc">
        <img src="{charts['payback']}" alt="Courbe de rentabilité sur 25 ans">
      </div>
      <div class="p2-fin-sc">{_stats_html}</div>
    </div>

    {_fin_cap}
  </div>"""

    badges_block = (
        '<div class="p2-lbl">Nos garanties</div>'
        f'<div class="p2-badges">{badges_html}</div>')

    def _wrap_page(inner, dense_c=""):
        return f'{style}<div class="p2-wrap{dense_c}">{inner}</div>'

    if fits_one:
        # Mise en page historique : tout sur UNE page (petits devis).
        return [_wrap_page(
            head_html + band_html
            + _table_html(shared, equipement_lbl)
            + closing_html + _fin_html()
            + badges_block)]

    # ── Devis chargé : page(s) équipement + page rentabilité dédiée ──────────
    # Budgets (mm) : 1ʳᵉ page équipement (bande projet + titre + clôture
    # tableau), pages « suite » (titre court seulement — la clôture suit le
    # DERNIER morceau de tableau).
    chunks = _chunk_rows(shared, budgets=[118.0, 165.0])

    # QRES52 — quand LA page équipement (non découpée) garde une réserve
    # confortable, les badges de garantie la terminent — à côté de
    # l'équipement qu'ils couvrent, plus de bas de page vide ; sinon ils
    # clôturent la page rentabilité comme avant.
    _est_equip = 13 + 26 + _table_mm(shared) + (71 if deux_options else 55)
    badges_on_equip = len(chunks) == 1 and (271 - _est_equip) >= 60

    pages = []
    for i, chunk in enumerate(chunks):
        is_first = i == 0
        is_last = i == len(chunks) - 1
        label = equipement_lbl if is_first else f"{equipement_lbl} (suite)"
        inner = (head_html + band_html if is_first else cont_head_html)
        inner += _table_html(chunk, label)
        if not is_last:
            inner += ('<div class="p2-cont-note">Suite de l\'équipement '
                      'page suivante &rsaquo;</div>')
        else:
            inner += closing_html
            if badges_on_equip:
                inner += f'<div class="p2-finpage-badges">{badges_block}</div>'
        pages.append(_wrap_page(inner))

    # QRES28 — la page rentabilité dédiée (espace abondant) reçoit le bandeau
    # navy de gain net (le chiffre-héros du document, en pleine largeur).
    _callout = ""
    if gain_mult_txt:
        _callout = (
            f'<div class="p2-callout">≈ {fmt(gain25)} MAD de gain net sur '
            f'25 ans — <b>{gain_mult_txt}× le prix de votre installation'
            '</b></div>')

    # QRES50 (fondateur, 2026-07-18) — la zone blanche du bas de page devient
    # l'argument cashflow-positif : bande « économies − crédit = dans votre
    # poche », données réelles du bloc financing uniquement (sinon omise).
    fin_d = d.get("financing") or {}
    fin_credit = fin_d.get("credit") or {}
    finband_html = ""
    if fin_d.get("indicatif") and fin_credit.get("mensualite"):
        _mens = int(round(fin_credit["mensualite"]))
        _eco_ref_m = (d.get("eco_a_ann") if (deux_options or avec_ok)
                      else d.get("eco_s_ann")) or 0
        _eco_mois = int(round(_eco_ref_m / 12.0))
        if _eco_mois > _mens:
            _duree_ans = round((fin_credit.get("duree_mois") or 0) / 12)
            _prog = fin_credit.get("programme_nom") or "crédit vert"
            finband_html = (
                '<div class="p2-lbl" style="margin-top:8mm">Financement '
                'possible — et si vous financiez au lieu de payer '
                'comptant&nbsp;?</div>'
                '<div class="p2-finband">'
                '<div class="p2-fb-c"><span class="p2-fb-k">Économies '
                'estimées</span>'
                f'<span class="p2-fb-v">≈ {fmt(_eco_mois)} '
                '<small>MAD/mois</small></span></div>'
                '<div class="p2-fb-sep">&minus;</div>'
                '<div class="p2-fb-c"><span class="p2-fb-k">Crédit</span>'
                f'<span class="p2-fb-v">≈ {fmt(_mens)} '
                '<small>MAD/mois</small></span></div>'
                '<div class="p2-fb-sep">=</div>'
                '<div class="p2-fb-c p2-fb-net"><span class="p2-fb-k">Dans '
                'votre poche</span>'
                f'<span class="p2-fb-v">≈ +{fmt(_eco_mois - _mens)} '
                '<small>MAD/mois</small></span></div>'
                '</div>'
                f'<div class="p2-fin-cap">sur {_duree_ans} ans ({_prog}) — '
                'indicatif, à confirmer avec votre banque.</div>')

    # QRES53 — l'impact environnemental complète la page rentabilité (le
    # retour de l'investissement ne se compte pas qu'en dirhams) : mêmes
    # facteurs de calcul que la page 1 (0,81 t CO₂/MWh, ~21 kg CO₂/arbre/an),
    # cumul 25 ans PRUDENT (dégradation panneau 0,5 %/an intégrée, ×23,5).
    _prod = d.get("prod_kwh") or 0
    impact_html = ""
    if _prod:
        _co2_t = _prod * 0.81 / 1000.0
        _trees = max(1, round(_prod * 0.81 / 21))
        _co2_25 = _co2_t * 23.5

        def _fr1(v):
            return (f"{v:.1f}".replace(".", ",") if v < 10
                    else fmt(round(v)))
        impact_html = (
            '<div class="p2-lbl" style="margin-top:7mm">Et pour la planète'
            '</div>'
            '<div class="p2-impact">'
            f'<div class="p2-imp-c"><span class="p2-imp-v">≈ {_fr1(_co2_t)} '
            't</span><span class="p2-imp-l">de CO<sub>2</sub> évitées '
            'chaque année</span></div>'
            f'<div class="p2-imp-c"><span class="p2-imp-v">≈ {fmt(_trees)}'
            '</span><span class="p2-imp-l">arbres plantés — l\'équivalent '
            'annuel</span></div>'
            f'<div class="p2-imp-c"><span class="p2-imp-v">≈ {_fr1(_co2_25)} '
            't</span><span class="p2-imp-l">de CO<sub>2</sub> évitées sur '
            '25 ans</span></div>'
            '</div>')

    _fin_badges = ("" if badges_on_equip
                   else f'<div class="p2-finpage-badges">{badges_block}</div>')
    pages.append(_wrap_page(
        fin_head_html + _fin_html(xl=True) + _callout
        + finband_html + impact_html + _fin_badges))
    return pages


def build(ctx) -> str:
    """Compat : forme mono-chaîne (concatène les pages équipement)."""
    return "".join(build_pages(ctx))
