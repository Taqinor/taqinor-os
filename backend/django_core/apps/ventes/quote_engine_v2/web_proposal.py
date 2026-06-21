"""v2 PROTOTYPE — CLIENT WEB PROPOSAL (the link we send the client).

A single-scroll, mobile-first proposal page (the web counterpart of the PDF):
hero with the real roof render, facture avant->apres + couverture, the two
options, the detail, garanties + trust links, and a sticky "Signer en ligne"
e-signature CTA. This is a MOCK of WEB_PLAN W116/W117 rendered with WeasyPrint
(desktop + phone widths) so the design can be reviewed before the Astro build.

Inert prototype — wired to nothing live.
"""
from __future__ import annotations
from pathlib import Path
from . import theme, charts as charts_mod, sample_data

C = theme.C


def _opt_card(d, name, kicker, total, pkwc, roi, bullets, reco=False):
    fmt = theme.fmt
    badge = ('<span class="wp-reco">Recommandé</span>' if reco else "")
    lis = "".join(f'<li><span class="wp-ck">✓</span>{b}</li>' for b in bullets[:4])
    cls = "wp-opt wp-opt-reco" if reco else "wp-opt"
    return f"""
    <div class="{cls}">
      <div class="wp-opt-top"><div><div class="wp-opt-k">{kicker}</div>
        <div class="wp-opt-n">{name}</div></div>{badge}</div>
      <div class="wp-opt-price">{fmt(total)}<small> MAD</small></div>
      <div class="wp-opt-sub">soit {pkwc} MAD/kWc · TTC</div>
      <div class="wp-roi">↗ Rentabilisé en {roi} ans</div>
      <ul class="wp-opt-list">{lis}</ul>
      <a class="wp-choose">Choisir cette option →</a>
    </div>"""


def build_html(data, ch, hero, width_px, height_px):
    fmt = theme.fmt
    d = data
    kwc = d["puissance_kwc"]
    pk_s = fmt(d["total_sans"] / kwc); pk_a = fmt(d["total_avec"] / kwc)

    def yrs(v):
        return (str(int(v)) if float(v) == int(v) else f"{v:.1f}").replace(".", ",")

    hero_css = (f"linear-gradient(180deg,rgba(15,30,53,.55) 0%,rgba(15,30,53,.35) 38%,"
                f"rgba(15,30,53,.92) 100%),url('data:image/jpeg;base64,{hero}') "
                f"center 40%/cover no-repeat") if hero else C["navy_900"]

    sans_b = d.get("sans_bullets", []); avec_b = d.get("avec_bullets", [])
    css = f"""
{theme.font_face_css()}
*{{margin:0;padding:0;box-sizing:border-box;}}
@page{{size:{width_px}px {height_px}px;margin:0;}}
html,body{{font-family:{theme.FONT_SANS};color:{C['ink']};background:#eef1f5;}}
.wp{{width:{width_px}px;margin:0 auto;background:#fff;}}
.serif{{font-family:{theme.FONT_SERIF};}}
.disp{{font-family:{theme.FONT_DISPLAY};}}

/* sticky bar */
.wp-bar{{display:flex;align-items:center;justify-content:space-between;
  background:{C['navy']};padding:14px 22px;}}
.wp-bar img{{height:26px;}}
.wp-bar-r{{display:flex;align-items:center;gap:16px;}}
.wp-bar-ref{{color:#cdd5e2;font-size:13px;}}
.wp-bar-sign{{background:{C['gold']};color:{C['navy']};font-weight:700;
  padding:9px 18px;border-radius:9px;font-size:14px;text-decoration:none;}}

/* hero */
.wp-hero{{background:{hero_css};min-height:340px;padding:40px 26px 30px;
  display:flex;flex-direction:column;justify-content:flex-end;color:#fff;
  text-shadow:0 1px 8px rgba(0,0,0,.4);}}
.wp-hero-k{{font-size:12px;letter-spacing:.22em;text-transform:uppercase;
  color:{C['gold']};font-weight:700;margin-bottom:10px;}}
.wp-hero h1{{font-size:40px;line-height:1.04;font-weight:400;}}
.wp-hero p{{font-size:17px;color:rgba(255,255,255,.9);margin-top:8px;}}
.wp-hero-pill{{display:inline-block;margin-top:16px;background:rgba(255,255,255,.14);
  border:1px solid rgba(255,255,255,.3);border-radius:30px;padding:6px 14px;
  font-size:13px;width:max-content;}}

/* sections */
.wp-sec{{padding:34px 26px;}}
.wp-sec-k{{font-size:12px;letter-spacing:.2em;text-transform:uppercase;
  color:{C['gold']};font-weight:700;margin-bottom:6px;}}
.wp-sec-h{{font-family:{theme.FONT_SERIF};font-weight:700;font-size:25px;
  color:{C['navy']};margin-bottom:18px;line-height:1.1;}}
.wp-alt{{background:{C['wash']};}}

/* money hook */
.wp-hook{{display:flex;flex-wrap:wrap;gap:18px;align-items:center;}}
.wp-hook-cmp{{flex:1 1 320px;display:flex;align-items:center;gap:18px;}}
.wp-cmp-old{{font-family:{theme.FONT_DISPLAY};font-size:30px;color:{C['muted_2']};
  text-decoration:line-through;}}
.wp-cmp-arrow{{font-size:26px;color:{C['gold']};}}
.wp-cmp-new{{font-family:{theme.FONT_DISPLAY};font-size:46px;color:{C['gold']};
  line-height:1;}}
.wp-cmp-new small,.wp-cmp-old small{{font-size:16px;}}
.wp-cmp-lab{{font-size:13px;color:{C['muted']};}}
.wp-donut{{flex:0 0 150px;text-align:center;}}
.wp-donut img{{width:140px;}}
.wp-bill{{margin-top:24px;}}
.wp-bill img{{width:100%;border:1px solid {C['line']};border-radius:14px;padding:14px;}}

/* KPI */
.wp-kpis{{display:flex;flex-wrap:wrap;gap:14px;margin-top:24px;}}
.wp-kpi{{flex:1 1 150px;border:1px solid {C['line']};border-left:4px solid {C['gold']};
  border-radius:14px;padding:16px 18px;}}
.wp-kpi-v{{font-family:{theme.FONT_DISPLAY};font-size:26px;color:{C['navy']};}}
.wp-kpi-v small{{font-size:13px;color:{C['muted']};}}
.wp-kpi-l{{font-size:12px;color:{C['muted']};margin-top:3px;}}

/* options */
.wp-opts{{display:flex;flex-wrap:wrap;gap:18px;}}
.wp-opt{{flex:1 1 300px;border:1px solid {C['line']};border-radius:18px;
  padding:24px;background:#fff;}}
.wp-opt-reco{{border:2px solid {C['gold']};box-shadow:0 10px 30px rgba(245,166,35,.12);}}
.wp-opt-top{{display:flex;justify-content:space-between;align-items:flex-start;}}
.wp-opt-k{{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
  color:{C['gold']};font-weight:700;}}
.wp-opt-n{{font-size:20px;font-weight:700;color:{C['navy']};margin-top:2px;}}
.wp-reco{{background:{C['gold']};color:{C['navy']};font-size:11px;font-weight:700;
  padding:4px 11px;border-radius:30px;text-transform:uppercase;letter-spacing:.04em;}}
.wp-opt-price{{font-family:{theme.FONT_DISPLAY};font-size:42px;color:{C['navy']};
  margin-top:14px;line-height:1;}}
.wp-opt-price small{{font-size:16px;color:{C['muted']};}}
.wp-opt-sub{{font-size:13px;color:{C['muted']};margin-top:4px;}}
.wp-roi{{display:inline-block;margin-top:14px;background:{C['green_bg']};
  color:{C['green']};font-weight:700;font-size:14px;padding:6px 14px;border-radius:30px;}}
.wp-opt-list{{list-style:none;margin:16px 0 0;}}
.wp-opt-list li{{display:flex;gap:9px;font-size:14px;color:{C['ink']};
  padding:6px 0;border-bottom:1px solid {C['line_soft']};}}
.wp-ck{{color:{C['green']};font-weight:700;}}
.wp-choose{{display:block;margin-top:18px;text-align:center;background:{C['navy']};
  color:#fff;font-weight:700;font-size:14px;padding:12px;border-radius:10px;
  text-decoration:none;}}

/* detail */
.wp-detail{{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-start;}}
.wp-detail-roof{{flex:1 1 280px;}}
.wp-detail-roof img{{width:100%;border-radius:14px;border:1px solid {C['line']};}}
.wp-detail-pay{{flex:1 1 320px;}}
.wp-detail-pay img{{width:100%;}}
.wp-detail-cap{{font-size:13px;color:{C['muted']};margin-top:8px;}}
.wp-fiche{{font-size:13px;color:{C['muted']};margin-top:16px;}}
.wp-fiche b{{color:{C['navy']};}}

/* garanties + trust */
.wp-badges{{display:flex;flex-wrap:wrap;gap:12px;}}
.wp-badge{{flex:1 1 120px;text-align:center;border:1px solid {C['line']};
  border-top:3px solid {C['gold']};border-radius:14px;padding:18px 8px;}}
.wp-badge-n{{font-family:{theme.FONT_DISPLAY};font-size:32px;color:{C['navy']};}}
.wp-badge-n small{{font-size:12px;color:{C['gold']};font-weight:700;}}
.wp-badge-l{{font-size:12px;color:{C['muted']};margin-top:4px;}}
.wp-trust{{display:flex;flex-wrap:wrap;gap:12px;margin-top:18px;}}
.wp-trust a{{flex:1 1 160px;background:{C['navy']};border-radius:12px;padding:14px 16px;
  text-decoration:none;}}
.wp-trust .t{{display:block;color:#fff;font-weight:700;font-size:14px;}}
.wp-trust .u{{display:block;color:{C['gold']};font-size:12px;margin-top:3px;}}

/* sign */
.wp-sign{{background:{C['navy']};color:#fff;padding:40px 26px;}}
.wp-sign h2{{font-family:{theme.FONT_SERIF};font-size:26px;margin-bottom:8px;}}
.wp-sign p{{color:#c8d2e0;font-size:15px;margin-bottom:22px;}}
.wp-sign-card{{background:#fff;border-radius:16px;padding:22px;color:{C['ink']};}}
.wp-field{{margin-bottom:14px;}}
.wp-field label{{display:block;font-size:12px;font-weight:700;color:{C['muted']};
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;}}
.wp-input{{border:1px solid {C['line']};border-radius:10px;padding:13px 14px;
  font-size:15px;color:{C['muted_2']};}}
.wp-check{{display:flex;gap:10px;align-items:flex-start;font-size:14px;
  color:{C['ink']};margin:6px 0 18px;}}
.wp-check .box{{width:18px;height:18px;border:2px solid {C['navy']};border-radius:5px;
  flex:0 0 18px;}}
.wp-sign-btn{{display:block;text-align:center;background:{C['gold']};color:{C['navy']};
  font-weight:700;font-size:17px;padding:16px;border-radius:12px;text-decoration:none;}}
.wp-sign-note{{font-size:12px;color:{C['muted']};text-align:center;margin-top:12px;}}

.wp-foot{{background:{C['navy_900']};color:#9fb0c8;padding:22px 26px;font-size:12px;
  display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;}}
.wp-foot b{{color:#fff;}}
"""

    links = d.get("links", {})
    html = f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head>
<body><div class="wp">

  <div class="wp-bar">
    <img src="data:image/png;base64,{theme.logo_dark_b64()}" alt="TAQINOR">
    <div class="wp-bar-r">
      <span class="wp-bar-ref">Devis N° {d['ref']}</span>
      <a class="wp-bar-sign" href="#signer">Signer en ligne</a>
    </div>
  </div>

  <div class="wp-hero">
    <div class="wp-hero-k">Proposition d'installation solaire</div>
    <h1 class="serif">Bonjour {d['client_full'].split()[0]},</h1>
    <p>Voici votre projet solaire, conçu pour votre toit à {d.get('client_city','')}.</p>
    <div class="wp-hero-pill">{kwc:g} kWc · {d['nb_panneaux']} panneaux · {fmt(d['prod_kwh'])} kWh/an</div>
  </div>

  <div class="wp-sec">
    <div class="wp-sec-k">Ce que le solaire change pour vous</div>
    <div class="wp-sec-h">Votre facture, divisée.</div>
    <div class="wp-hook">
      <div class="wp-hook-cmp">
        <div><div class="wp-cmp-lab">Aujourd'hui</div>
          <div class="wp-cmp-old">≈ {fmt(d['annual_before'])}<small> MAD/an</small></div></div>
        <div class="wp-cmp-arrow">→</div>
        <div><div class="wp-cmp-lab">Avec TAQINOR</div>
          <div class="wp-cmp-new disp">≈ {fmt(d['annual_after'])}<small> MAD/an</small></div></div>
      </div>
      <div class="wp-donut"><img src="{ch['coverage']}">
        <div class="wp-cmp-lab">de votre consommation couverte</div></div>
    </div>
    <div class="wp-bill"><img src="{ch['bill']}"></div>
    <div class="wp-kpis">
      <div class="wp-kpi"><div class="wp-kpi-v">{kwc:g}<small> kWc</small></div>
        <div class="wp-kpi-l">{d['nb_panneaux']} panneaux × {d['watt_par_panneau']} W</div></div>
      <div class="wp-kpi"><div class="wp-kpi-v">{fmt(d['prod_kwh'])}<small> kWh</small></div>
        <div class="wp-kpi-l">Production / an</div></div>
      <div class="wp-kpi"><div class="wp-kpi-v">{fmt(d['eco_a_ann'])}<small> MAD</small></div>
        <div class="wp-kpi-l">Économie estimée / an</div></div>
    </div>
  </div>

  <div class="wp-sec wp-alt">
    <div class="wp-sec-k">Vos deux options</div>
    <div class="wp-sec-h">Choisissez votre formule.</div>
    <div class="wp-opts">
      {_opt_card(d, "Sans batterie", "Option 1", d['total_sans'], pk_s, yrs(d['roi_s']), sans_b)}
      {_opt_card(d, "Avec batterie", "Option 2", d['total_avec'], pk_a, yrs(d['roi_a']), avec_b, reco=True)}
    </div>
  </div>

  <div class="wp-sec">
    <div class="wp-sec-k">Votre installation</div>
    <div class="wp-sec-h">Conçue sur votre toit.</div>
    <div class="wp-detail">
      <div class="wp-detail-roof"><img src="{ch['roof']}">
        <div class="wp-detail-cap">{d['nb_panneaux']} panneaux disposés sur votre toiture.</div></div>
      <div class="wp-detail-pay"><img src="{ch['payback']}">
        <div class="wp-detail-cap">Rentabilité cumulée sur 25 ans — le point marque le retour sur investissement.</div></div>
    </div>
    <div class="wp-fiche">Fiches techniques complètes des équipements →
      <b>{links.get('produits','taqinor.ma/produits')}</b></div>
  </div>

  <div class="wp-sec wp-alt">
    <div class="wp-sec-k">Confiance & engagement</div>
    <div class="wp-sec-h">Pourquoi TAQINOR.</div>
    <div class="wp-badges">
      <div class="wp-badge"><div class="wp-badge-n">10<small> ans</small></div><div class="wp-badge-l">Onduleur</div></div>
      <div class="wp-badge"><div class="wp-badge-n">12<small> ans</small></div><div class="wp-badge-l">Panneaux</div></div>
      <div class="wp-badge"><div class="wp-badge-n">20<small> ans</small></div><div class="wp-badge-l">Structure</div></div>
      <div class="wp-badge"><div class="wp-badge-n">30<small> ans</small></div><div class="wp-badge-l">Performance 87,4%</div></div>
    </div>
    <div class="wp-trust">
      <a><span class="t">Nos réalisations</span><span class="u">{links.get('realisations','taqinor.ma/realisations')} ›</span></a>
      <a><span class="t">Avis clients vérifiés</span><span class="u">{links.get('avis','taqinor.ma/avis')} ›</span></a>
      <a><span class="t">Garanties & certifications</span><span class="u">{links.get('garanties','taqinor.ma/garanties')} ›</span></a>
    </div>
  </div>

  <div class="wp-sign" id="signer">
    <h2 class="serif">Validez votre devis en ligne</h2>
    <p>Pas de déplacement, pas d'attente. Signez et nous planifions la visite technique sous 48–72 h.</p>
    <div class="wp-sign-card">
      <div class="wp-field"><label>Option choisie</label>
        <div class="wp-input">Option 2 — Avec batterie · {fmt(d['total_avec'])} MAD TTC</div></div>
      <div class="wp-field"><label>Votre nom</label>
        <div class="wp-input">{d['client_full']}</div></div>
      <div class="wp-check"><span class="box"></span>
        <span>Je confirme « Bon pour accord » et j'accepte le devis et les conditions générales.</span></div>
      <a class="wp-sign-btn" href="#">✍  Signer en ligne</a>
      <div class="wp-sign-note">Signature électronique horodatée · valeur d'engagement dès réception de l'acompte.</div>
    </div>
  </div>

  <div class="wp-foot">
    <div><b>TAQINOR</b> · contact@taqinor.com · +212 6 61 85 04 10</div>
    <div>Devis {d['ref']} · {links.get('signer','taqinor.ma')}</div>
  </div>

</div></body></html>"""
    return html


def render(out_pdf, width_px=1080, height_px=3650):
    from weasyprint import HTML
    data = sample_data.build()
    ch = charts_mod.build_all(data)
    hero = theme.hero_image_b64()
    html = build_html(data, ch, hero, width_px, height_px)
    base = str(Path(__file__).resolve().parent)
    HTML(string=html, base_url=f"file://{base}/").write_pdf(str(out_pdf))
    return str(out_pdf)
