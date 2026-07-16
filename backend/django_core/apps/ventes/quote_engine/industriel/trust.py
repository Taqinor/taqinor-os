# flake8: noqa
"""quote_engine industriel — PAGE 3 (tranches phasées + normes + garanties + signature).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``i3-``.
"""


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    theme = ctx["theme"]
    ident = ctx.get("ident") or {}
    brand = ident.get("brand_name") or "TAQINOR"

    navy = C["navy"]
    gold = C["gold"]
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    ink = C.get("ink", "#1F2937")
    muted = C.get("muted", "#6B7280")
    muted_2 = C.get("muted_2", "#9BA3AE")
    line = C.get("line", "#E5E7EB")
    line_soft = C.get("line_soft", "#EFF1F4")
    wash = C.get("wash", "#F7F9FC")
    blue = C.get("blue", "#2C5F8A")

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    invest = d.get("_invest_ttc") or 0
    pt = d.get("payment_terms") or {"acompte": 50, "materiel": 40, "solde": 10}
    a_pct = int(pt.get("acompte", 50))
    m_pct = int(pt.get("materiel", 40))
    s_pct = int(pt.get("solde", 10))

    def tranche(label, pct, sub):
        montant = round(invest * pct / 100)
        return (
            f'<td class="i3-tr"><div class="i3-tr-pct">{pct}%</div>'
            f'<div class="i3-tr-lab">{label}</div>'
            f'<div class="i3-tr-amt">{fmt(montant)} MAD</div>'
            f'<div class="i3-tr-sub">{sub}</div></td>')

    tranches = (
        tranche("Acompte", a_pct, "à la commande — lancement des études & appro")
        + '<td class="i3-tgap"></td>'
        + tranche("Matériel", m_pct, "à la livraison des équipements sur site")
        + '<td class="i3-tgap"></td>'
        + tranche("Solde", s_pct, "à la mise en service & réception")
    )

    # Signature — tampon d'acceptation posé à l'acceptation (sinon champ vierge).
    accepte_nom = (d.get("accepte_par_nom") or "").strip()
    date_accept = (d.get("date_acceptation") or "").strip()
    if accepte_nom and date_accept:
        sign_client = f'<div class="i3-sign-name">{theme._esc(accepte_nom)}</div><div class="i3-sign-date">Le {date_accept}</div>'
    else:
        sign_client = '<div class="i3-sign-blank">Nom, date &amp; « Bon pour accord »</div>'

    css = f"""
<style>
.i3-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.i3-root *{{box-sizing:border-box;}}
.i3-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.i3-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.i3-trrow{{display:table;width:100%;margin-top:9px;border-spacing:0;}}
.i3-tr{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-top:4px solid {gold};border-radius:12px;padding:12px 14px;background:{wash};}}
.i3-tgap{{display:table-cell;width:11px;}}
.i3-tr-pct{{font-family:{f_display};font-size:22pt;color:{navy};line-height:1;}}
.i3-tr-lab{{font-size:9pt;font-weight:700;color:{navy};margin-top:4px;}}
.i3-tr-amt{{font-size:10pt;color:{gold};font-weight:700;margin-top:2px;}}
.i3-tr-sub{{font-size:7pt;color:{muted};margin-top:4px;line-height:1.3;}}

.i3-h2{{font-family:{f_serif};font-weight:700;font-size:13pt;color:{navy};margin-top:15px;}}
.i3-two{{display:table;width:100%;margin-top:8px;border-spacing:0;}}
.i3-col{{display:table-cell;vertical-align:top;width:50%;padding-right:10px;}}
.i3-col:last-child{{padding-right:0;padding-left:10px;}}
.i3-blk{{border:1px solid {line};border-radius:12px;padding:11px 14px;background:#fff;height:100%;}}
.i3-blk-t{{font-size:8.5pt;font-weight:700;color:{navy};}}
.i3-li{{font-size:8pt;color:{ink};line-height:1.4;margin-top:5px;padding-left:12px;position:relative;}}
.i3-li:before{{content:'';position:absolute;left:0;top:5px;width:6px;height:6px;
  border-radius:50%;background:{green};}}
.i3-li b{{color:{navy};}}

.i3-warr{{margin-top:14px;border:1px solid {line};border-radius:12px;background:{wash};
  padding:11px 14px;}}
.i3-warr-row{{display:table;width:100%;border-spacing:0;}}
.i3-warr-c{{display:table-cell;vertical-align:top;text-align:center;padding:0 6px;}}
.i3-warr-v{{font-family:{f_display};font-size:16pt;color:{green};line-height:1;}}
.i3-warr-l{{font-size:7pt;color:{muted};margin-top:3px;}}

.i3-sign{{margin-top:16px;display:table;width:100%;border-spacing:0;}}
.i3-sign-c{{display:table-cell;vertical-align:top;width:50%;border:1px solid {line};
  border-radius:12px;padding:12px 14px;}}
.i3-sign-gap{{display:table-cell;width:12px;}}
.i3-sign-h{{font-size:7.5pt;letter-spacing:1.4px;text-transform:uppercase;
  color:{muted};font-weight:700;}}
.i3-sign-box{{margin-top:8px;height:20mm;border:1px dashed {line};border-radius:8px;
  background:{wash};}}
.i3-sign-name{{margin-top:8px;font-size:11pt;color:{navy};font-weight:700;}}
.i3-sign-date{{font-size:8pt;color:{muted};margin-top:2px;}}
.i3-sign-blank{{margin-top:8px;font-size:8pt;color:{muted_2};font-style:italic;}}
.i3-sign-co{{font-size:8pt;color:{muted};margin-top:8px;}}
.i3-sign-co b{{color:{navy};}}
</style>
"""

    html = f"""{css}
<div class="i3-root">
  <div class="i3-kicker">Déploiement &amp; conditions</div>
  <div class="i3-sec">Tranches de paiement phasées</div>
  <div class="i3-trrow">{tranches}</div>

  <div class="i3-h2">Conformité &amp; valeur pour l'entreprise</div>
  <div class="i3-two">
    <div class="i3-col"><div class="i3-blk">
      <div class="i3-blk-t">ISO 50001 — management de l'énergie</div>
      <div class="i3-li">Données de production/consommation exploitables pour la <b>revue énergétique</b> et les indicateurs de performance (IPE).</div>
      <div class="i3-li">Supervision temps réel : base d'un <b>plan d'actions</b> d'efficacité énergétique.</div>
    </div></div>
    <div class="i3-col"><div class="i3-blk">
      <div class="i3-blk-t">CBAM — ajustement carbone aux frontières (UE)</div>
      <div class="i3-li">Pour les <b>exportateurs</b> vers l'UE : l'électricité solaire autoconsommée réduit l'<b>intensité carbone</b> déclarée des produits.</div>
      <div class="i3-li">Traçabilité de l'énergie renouvelable à l'appui du reporting CBAM.</div>
    </div></div>
  </div>

  <div class="i3-warr">
    <div class="i3-blk-t">Garanties</div>
    <div class="i3-warr-row" style="margin-top:8px;">
      <div class="i3-warr-c"><div class="i3-warr-v">25 ans</div><div class="i3-warr-l">Performance panneaux</div></div>
      <div class="i3-warr-c"><div class="i3-warr-v">5-10 ans</div><div class="i3-warr-l">Onduleurs</div></div>
      <div class="i3-warr-c"><div class="i3-warr-v">10 ans</div><div class="i3-warr-l">Installation &amp; main-d'œuvre</div></div>
      <div class="i3-warr-c"><div class="i3-warr-v">O&amp;M</div><div class="i3-warr-l">Maintenance &amp; supervision</div></div>
    </div>
  </div>

  <div class="i3-sign">
    <div class="i3-sign-c">
      <div class="i3-sign-h">Bon pour accord — Client</div>
      <div class="i3-sign-box"></div>
      {sign_client}
    </div>
    <div class="i3-sign-gap"></div>
    <div class="i3-sign-c">
      <div class="i3-sign-h">Pour {brand}</div>
      <div class="i3-sign-box"></div>
      <div class="i3-sign-co"><b>{brand}</b> &nbsp;·&nbsp; {ident.get('email','')} &nbsp;·&nbsp; {ident.get('phone','')}</div>
    </div>
  </div>
</div>
"""
    return html
