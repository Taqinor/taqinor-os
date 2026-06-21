# flake8: noqa
"""Agricole — PAGE 3 (equipment list + transparent pricing chain + FDA subsidy
+ garanties). Returns INNER HTML of one A4 page. Classes a3-*.
The water/production charts moved up to the étude page (4-page layout)."""
from __future__ import annotations


def _short(text, n=72):
    t = " ".join((text or "").split())
    return (t[: n - 1] + "…") if len(t) > n else t


def build(ctx) -> str:
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]

    navy = C["navy"]; gold = C["gold"]; green = C["green"]; green_bg = C["green_bg"]
    green_700 = C["green_700"]; water = C["water"]; ink = C["ink"]; muted = C["muted"]
    muted_2 = C["muted_2"]; line = C["line"]; line_soft = C["line_soft"]; wash = C["wash"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]

    totaux = d.get("totaux_all") or {}
    items = [it for it in (d.get("all_items") or []) if (it.get("quantite") or 0) > 0]
    ht_brut = totaux.get("ht_brut") or 0
    remise = totaux.get("remise") or 0
    ht_net = totaux.get("ht_net") or 0
    tva = totaux.get("tva") or 0
    ttc = totaux.get("ttc") or 0
    discount_pct = d.get("discount_pct") or 0
    show_subsidy = d.get("show_subsidy", True)
    fda_amount = d.get("fda_amount") or 0; fda_pct = d.get("fda_pct") or 30
    net_after_fda = d.get("net_after_fda") or ttc

    # ── equipment table ──────────────────────────────────────────────────────
    rows = []
    for it in items:
        q = it.get("quantite") or 0
        q_txt = str(int(q)) if float(q) == int(q) else fmt_dec(q)
        pu = it.get("prix_unit_ht") or 0
        tot = q * pu
        marque = (it.get("marque") or "").strip()
        desc = _short(it.get("description") or "", 60)
        gar = (it.get("garantie") or "").strip()
        bits = [b for b in (desc, (f"Garantie {gar}" if gar else "")) if b]
        sub = f'<div class="a3-rd">{" · ".join(bits)}</div>' if bits else ""
        rows.append(
            f'<tr><td class="a3-td-d"><div class="a3-rn">{it.get("designation","")}</div>'
            f'{f"<div class=\"a3-rm\">{marque}</div>" if marque else ""}{sub}</td>'
            f'<td class="a3-td-q">{q_txt}</td>'
            f'<td class="a3-td-n">{fmt(pu)}</td>'
            f'<td class="a3-td-n">{fmt(tot)}</td></tr>')
    table_html = (
        f'<table class="a3-tbl"><thead><tr>'
        f'<th class="a3-th-d">Désignation</th><th class="a3-th-q">Qté</th>'
        f'<th class="a3-th-n">P.U. HT</th><th class="a3-th-n">Total HT</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table>')

    # ── pricing chain ────────────────────────────────────────────────────────
    chain = [("Sous-total HT", f"{fmt(ht_brut)} MAD", False)]
    if remise and remise > 0:
        chain.append((f"Remise ({fmt_dec(discount_pct)} %)", f"− {fmt(remise)} MAD", False))
        chain.append(("Total HT", f"{fmt(ht_net)} MAD", False))
    chain.append(("TVA", f"{fmt(tva)} MAD", False))
    chain.append(("Total TTC", f"{fmt(ttc)} MAD", True))
    chain_html = "".join(
        f'<div class="a3-cr {"a3-cr-tot" if big else ""}"><span>{k}</span><b>{v}</b></div>'
        for k, v, big in chain)

    fda_html = ""
    if show_subsidy and fda_amount > 0:
        fda_html = (
            f'<div class="a3-fda"><div class="a3-fda-k">Subvention FDA · pompage solaire</div>'
            f'<div class="a3-fda-v">− {fmt(fda_amount)} MAD</div>'
            f'<div class="a3-fda-s">{fda_pct} % du coût, versée a posteriori sur dossier '
            f'DPA/ORMVA — cumulable avec la subvention goutte-à-goutte.</div>'
            f'<div class="a3-fda-net"><span>Coût net estimé</span>'
            f'<b>≈ {fmt(net_after_fda)} MAD</b></div></div>')
    else:
        fda_html = ('<div class="a3-fda a3-fda-empty"><div class="a3-fda-k">Bon à savoir</div>'
                    '<div class="a3-fda-s">Le pompage solaire agricole est éligible à la '
                    'subvention FDA (30 %), versée a posteriori. Nous vous accompagnons pour '
                    'le dossier.</div></div>')

    # ── garanties (folded up from the trust page) ────────────────────────────
    badges = [("25", "ans", "Panneaux (perf.)"), ("5", "ans", "Variateur"),
              ("2", "ans", "Pompe"), ("10", "ans", "Structure")]
    badges_html = "".join(
        f'<div class="a3-badge"><div class="a3-bn">{n}<span>{u}</span></div>'
        f'<div class="a3-bl">{l}</div></div>' for n, u, l in badges)

    css = f"""
<style>
.a3-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;background:#fff;
  padding:14mm 14mm 0;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a3-root *{{box-sizing:border-box;}}
.a3-kicker{{font-size:7pt;letter-spacing:2.4px;text-transform:uppercase;color:{gold};font-weight:700;}}
.a3-title{{font-family:{f_serif};font-weight:700;font-size:23pt;color:{navy};line-height:1.04;margin:3px 0 0;}}
.a3-intro{{font-size:9pt;color:{muted};margin:5px 0 11px;line-height:1.4;}}
.a3-tbl{{width:100%;border-collapse:collapse;border:1px solid {line};border-radius:12px;overflow:hidden;}}
.a3-tbl thead th{{background:{navy};color:#fff;font-size:7.2pt;font-weight:700;text-transform:uppercase;
  letter-spacing:.05em;padding:7px 12px;text-align:left;}}
.a3-th-q{{text-align:center !important;}} .a3-th-n{{text-align:right !important;}}
.a3-tbl tbody td{{padding:7px 12px;border-bottom:1px solid {line_soft};vertical-align:top;font-size:8.4pt;}}
.a3-rn{{font-weight:700;color:{ink};}}
.a3-rm{{font-size:7.2pt;color:{gold};font-weight:700;margin-top:1px;}}
.a3-rd{{font-size:7.2pt;color:{muted};margin-top:1px;line-height:1.25;}}
.a3-td-q{{text-align:center;white-space:nowrap;}}
.a3-td-n{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;}}
/* price + FDA band */
.a3-band{{display:flex;gap:12px;margin-top:12px;align-items:stretch;}}
.a3-band-col{{flex:1 1 0;min-width:0;border:1px solid {line};border-radius:12px;background:#fff;padding:11px 14px;}}
.a3-h{{font-family:{f_serif};font-weight:700;font-size:11pt;color:{navy};margin-bottom:6px;}}
.a3-cr{{display:flex;justify-content:space-between;font-size:8.6pt;color:{ink};
  padding:6px 0;border-bottom:1px dashed {line_soft};}}
.a3-cr:last-child{{border-bottom:none;}} .a3-cr b{{color:{navy};font-weight:700;}}
.a3-cr-tot{{border-top:2px solid {navy};margin-top:3px;padding-top:8px;}}
.a3-cr-tot span{{font-weight:700;font-size:9.5pt;color:{navy};}}
.a3-cr-tot b{{font-family:{f_display};font-size:16pt;color:{gold};}}
.a3-fda{{border:1px solid #BFE6CB;border-radius:12px;background:linear-gradient(180deg,{green_bg},#fff 72%);
  padding:11px 14px;flex:1 1 0;min-width:0;display:flex;flex-direction:column;}}
.a3-fda-empty{{border-color:{line};background:{wash};}}
.a3-fda-k{{font-size:8.4pt;font-weight:700;color:{green_700};}}
.a3-fda-empty .a3-fda-k{{color:{navy};}}
.a3-fda-v{{font-family:{f_display};font-size:20pt;color:{green_700};line-height:1;margin:4px 0;}}
.a3-fda-s{{font-size:7.4pt;color:{muted};line-height:1.3;}}
.a3-fda-net{{display:flex;justify-content:space-between;align-items:baseline;margin-top:auto;padding-top:8px;
  border-top:1px dashed #BFE6CB;font-size:9pt;}}
.a3-fda-net b{{color:{green_700};font-weight:700;font-family:{f_display};font-size:13pt;}}
/* garanties */
.a3-gh{{font-family:{f_serif};font-weight:700;font-size:11pt;color:{navy};margin:14px 0 7px;}}
.a3-badges{{display:flex;gap:8px;}}
.a3-badge{{flex:1;text-align:center;border:1px solid {line};border-top:3px solid {gold};
  border-radius:10px;padding:10px 4px 9px;}}
.a3-bn{{font-family:{f_display};font-size:21pt;color:{navy};line-height:1;}}
.a3-bn span{{font-size:8pt;color:{gold};font-weight:700;margin-left:3px;}}
.a3-bl{{font-size:7.2pt;color:{muted};font-weight:600;margin-top:3px;}}
.a3-note{{font-size:7.4pt;color:{muted_2};margin-top:9px;font-style:italic;}}
</style>
"""
    html = f"""{css}
<div class="a3-root">
  <div class="a3-kicker">Équipement & investissement</div>
  <div class="a3-title">Votre installation, et son prix</div>
  <div class="a3-intro">Équipement premium, prix détaillé en toute transparence — et la subvention
    qui réduit votre coût réel.</div>
  {table_html}
  <div class="a3-band">
    <div class="a3-band-col"><div class="a3-h">Le prix, en toute transparence</div>{chain_html}</div>
    {fda_html}
  </div>
  <div class="a3-gh">Nos garanties</div>
  <div class="a3-badges">{badges_html}</div>
  <div class="a3-note">Prix unitaires HT · total TTC. Fiches techniques sur taqinor.ma/produits.
    Rentabilité et comparatif carburant en page suivante.</div>
</div>
"""
    return html
