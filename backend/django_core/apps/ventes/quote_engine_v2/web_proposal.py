"""v2 PROTOTYPE — CLIENT WEB PROPOSAL (the link we send the client).

Rebuilt to be clean and self-contained: large, readable type, generous
whitespace, no cramped micro-text — so it renders faithfully everywhere
(including the print engine used for previews) and opens standalone in a real
browser. Distinct from the PDF: editorial single column, big promise band,
comparison options, prominent e-sign close. Inert prototype.
"""
from __future__ import annotations
from pathlib import Path
from . import theme, charts as charts_mod, sample_data

C = theme.C


def _yrs(v):
    return (str(int(v)) if float(v) == int(v) else f"{v:.1f}").replace(".", ",")


def build_html(data, ch, hero, width_px, height_px):
    fmt = theme.fmt
    d = data
    kwc = d["puissance_kwc"]
    pct_cut = round((1 - d["annual_after"] / max(1, d["annual_before"])) * 100)
    pk_a = fmt(d["total_avec"] / kwc)
    pk_s = fmt(d["total_sans"] / kwc)
    links = d.get("links", {})
    sans_b = d.get("sans_bullets", [])[:4]
    avec_b = d.get("avec_bullets", [])[:4]

    hero_bg = (f"linear-gradient(180deg,rgba(15,30,53,.45),rgba(15,30,53,.92)),"
               f"url('data:image/jpeg;base64,{hero}') center 42%/cover no-repeat"
               ) if hero else C["navy_900"]

    def opt(name, num, total, pk, roi, bullets, reco):
        lis = "".join(f'<li>{b}</li>' for b in bullets)
        rc = " op-reco" if reco else ""
        tag = '<div class="op-tag">Recommandé</div>' if reco else ""
        return f"""<div class="op{rc}">{tag}
          <div class="op-num">{num}</div><div class="op-name">{name}</div>
          <div class="op-price">{fmt(total)}<span> MAD</span></div>
          <div class="op-meta">{pk} MAD/kWc · TTC · rentabilisé en {roi} ans</div>
          <ul>{lis}</ul>
          <div class="op-btn">Choisir cette formule</div></div>"""

    css = f"""
{theme.font_face_css()}
*{{margin:0;padding:0;box-sizing:border-box;}}
@page{{size:{width_px}px {height_px}px;margin:0;}}
body{{font-family:{theme.FONT_SANS};color:{C['ink']};background:#fff;
  font-size:16px;line-height:1.5;}}
.pg{{width:{width_px}px;background:#fff;}}
.serif{{font-family:{theme.FONT_SERIF};}}
.disp{{font-family:{theme.FONT_DISPLAY};}}
.wrap{{max-width:1000px;margin:0 auto;padding:0 40px;}}
.eyebrow{{font-size:13px;letter-spacing:.18em;text-transform:uppercase;
  color:{C['gold']};font-weight:700;}}

/* header */
.hd{{background:{C['navy']};}}
.hd .in{{max-width:1000px;margin:0 auto;padding:18px 40px;display:flex;
  align-items:center;justify-content:space-between;}}
.hd img{{height:30px;}}
.hd .ref{{color:#aebbcd;font-size:14px;margin-right:20px;}}
.hd .sign{{background:{C['gold']};color:{C['navy']};font-weight:700;
  padding:11px 22px;border-radius:10px;font-size:15px;text-decoration:none;}}

/* hero */
.hero{{background:{hero_bg};color:#fff;padding:80px 40px 56px;}}
.hero .in{{max-width:1000px;margin:0 auto;}}
.hero h1{{font-size:54px;line-height:1.02;font-weight:400;margin:14px 0 10px;}}
.hero .lead{{font-size:20px;color:#e6ebf2;max-width:560px;}}
.stats{{display:flex;gap:40px;margin-top:34px;}}
.stat .v{{font-family:{theme.FONT_DISPLAY};font-size:30px;}}
.stat .l{{font-size:14px;color:#c4cedd;margin-top:2px;}}

/* promise band */
.promise{{background:{C['navy_900']};color:#fff;padding:54px 40px;}}
.promise .in{{max-width:1000px;margin:0 auto;display:flex;align-items:center;
  gap:46px;flex-wrap:wrap;}}
.promise .txt{{flex:1 1 420px;}}
.promise .big{{font-family:{theme.FONT_DISPLAY};font-size:46px;line-height:1.1;
  margin:10px 0;}}
.promise .big .from{{color:#94a3b8;text-decoration:line-through;}}
.promise .big .to{{color:{C['gold']};}}
.promise .cut{{display:inline-block;background:{C['gold']};color:{C['navy']};
  font-weight:700;font-size:16px;padding:8px 18px;border-radius:30px;}}
.promise .donut{{flex:0 0 200px;text-align:center;}}
.promise .donut img{{width:190px;}}
.promise .donut .cap{{color:#c4cedd;font-size:14px;margin-top:6px;}}

/* sections */
.sec{{padding:64px 0;}}
.sec h2{{font-family:{theme.FONT_SERIF};font-weight:700;font-size:34px;
  color:{C['navy']};margin:8px 0 28px;}}
.alt{{background:{C['wash']};}}
.chart{{border:1px solid {C['line']};border-radius:18px;padding:22px;
  background:#fff;}}
.chart img{{width:100%;display:block;}}
.cap{{font-size:14px;color:{C['muted']};margin-top:14px;}}

/* options */
.ops{{display:flex;gap:26px;}}
.op{{flex:1;border:1px solid {C['line']};border-radius:20px;padding:30px;
  background:#fff;position:relative;}}
.op-reco{{border:2px solid {C['gold']};}}
.op-tag{{position:absolute;top:-14px;left:30px;background:{C['gold']};
  color:{C['navy']};font-weight:700;font-size:13px;padding:5px 14px;
  border-radius:20px;}}
.op-num{{font-size:13px;letter-spacing:.16em;text-transform:uppercase;
  color:{C['gold']};font-weight:700;}}
.op-name{{font-size:24px;font-weight:700;color:{C['navy']};margin-top:4px;}}
.op-price{{font-family:{theme.FONT_DISPLAY};font-size:48px;color:{C['navy']};
  margin-top:16px;line-height:1;}}
.op-price span{{font-size:18px;color:{C['muted']};}}
.op-meta{{font-size:15px;color:{C['muted']};margin-top:8px;}}
.op ul{{list-style:none;margin:22px 0;}}
.op li{{font-size:16px;color:{C['ink']};padding:9px 0;
  border-bottom:1px solid {C['line_soft']};}}
.op li:before{{content:"✓";color:{C['green']};font-weight:700;margin-right:10px;}}
.op-btn{{text-align:center;background:{C['navy']};color:#fff;font-weight:700;
  font-size:16px;padding:15px;border-radius:12px;}}
.op-reco .op-btn{{background:{C['gold']};color:{C['navy']};}}

/* detail */
.two{{display:flex;gap:30px;align-items:flex-start;}}
.two>div{{flex:1;}}
.two img{{width:100%;border-radius:18px;border:1px solid {C['line']};display:block;}}
.fiche{{font-size:15px;color:{C['muted']};margin-top:22px;}}
.fiche b{{color:{C['navy']};}}

/* garanties */
.badges{{display:flex;gap:18px;}}
.badge{{flex:1;text-align:center;background:#fff;border:1px solid {C['line']};
  border-top:4px solid {C['gold']};border-radius:18px;padding:26px 10px;}}
.badge .n{{font-family:{theme.FONT_DISPLAY};font-size:40px;color:{C['navy']};
  line-height:1;}}
.badge .u{{font-size:14px;color:{C['gold']};font-weight:700;}}
.badge .l{{font-size:15px;color:{C['muted']};margin-top:8px;}}
.links{{display:flex;gap:18px;margin-top:24px;}}
.lk{{flex:1;border:1px solid {C['line']};border-radius:16px;padding:22px 24px;
  background:#fff;}}
.lk .t{{font-size:18px;font-weight:700;color:{C['navy']};}}
.lk .u{{font-size:15px;color:{C['gold']};font-weight:600;margin-top:6px;}}

/* sign */
.sign{{background:{C['navy']};color:#fff;padding:70px 40px;}}
.sign .in{{max-width:760px;margin:0 auto;text-align:center;}}
.sign h2{{font-family:{theme.FONT_SERIF};font-size:38px;margin-bottom:12px;}}
.sign p{{color:#c8d2e0;font-size:18px;margin-bottom:34px;}}
.card{{background:#fff;color:{C['ink']};border-radius:20px;padding:34px;
  text-align:left;}}
.fld{{margin-bottom:18px;}}
.fld .lab{{font-size:13px;font-weight:700;color:{C['muted']};
  text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;}}
.fld .box{{border:1px solid {C['line']};border-radius:12px;padding:16px;
  font-size:17px;color:{C['navy']};font-weight:600;}}
.agree{{display:flex;gap:12px;align-items:center;margin:8px 0 24px;
  font-size:16px;}}
.agree .ck{{width:22px;height:22px;border:2px solid {C['navy']};
  border-radius:6px;flex:0 0 22px;}}
.signbtn{{text-align:center;background:{C['gold']};color:{C['navy']};
  font-weight:700;font-size:20px;padding:20px;border-radius:14px;}}
.signnote{{text-align:center;font-size:14px;color:{C['muted']};margin-top:16px;}}

.ft{{background:{C['navy_900']};color:#9fb0c8;padding:30px 40px;font-size:14px;}}
.ft .in{{max-width:1000px;margin:0 auto;display:flex;justify-content:space-between;
  flex-wrap:wrap;gap:10px;}}
.ft b{{color:#fff;}}

/* phones: stack everything into one column */
@media (max-width:680px){{
  .hero{{padding:54px 26px 40px;}}
  .hero h1{{font-size:40px;}}
  .stats{{flex-wrap:wrap;gap:22px;}}
  .promise{{padding:40px 26px;}}
  .promise .in{{gap:26px;}}
  .promise .big{{font-size:34px;}}
  .sec{{padding:46px 0;}}
  .sec h2{{font-size:28px;}}
  .wrap{{padding:0 24px;}}
  .ops{{flex-direction:column;}}
  .two{{flex-direction:column;}}
  .badges{{flex-wrap:wrap;}}
  .badge{{flex:1 1 42%;}}
  .links{{flex-direction:column;}}
  .hd .in,.sign{{padding-left:24px;padding-right:24px;}}
}}
"""

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Votre proposition solaire — TAQINOR</title><style>{css}</style></head><body>
<div class="pg">

  <div class="hd"><div class="in">
    <img src="data:image/png;base64,{theme.logo_dark_b64()}" alt="TAQINOR">
    <div><span class="ref">Devis N° {d['ref']}</span>
      <a class="sign" href="#signer">Signer en ligne</a></div>
  </div></div>

  <div class="hero"><div class="in">
    <div class="eyebrow">Proposition d'installation solaire</div>
    <h1 class="serif">Bonjour {d['client_full'].split()[0]},</h1>
    <div class="lead">Voici votre projet solaire, dessiné pour votre toit à {d.get('client_city','')}.</div>
    <div class="stats">
      <div class="stat"><div class="v disp">{kwc:g} kWc</div><div class="l">{d['nb_panneaux']} panneaux</div></div>
      <div class="stat"><div class="v disp">{fmt(d['prod_kwh'])}</div><div class="l">kWh produits / an</div></div>
      <div class="stat"><div class="v disp">{_yrs(d['roi_a'])} ans</div><div class="l">retour sur investissement</div></div>
    </div>
  </div></div>

  <div class="promise"><div class="in">
    <div class="txt">
      <div class="eyebrow">Ce que le solaire change</div>
      <div class="big"><span class="from">≈ {fmt(d['annual_before'])} MAD</span> →
        <span class="to">≈ {fmt(d['annual_after'])} MAD</span></div>
      <div class="cut">soit −{pct_cut}% sur votre facture annuelle</div>
    </div>
    <div class="donut"><img src="{ch['coverage']}">
      <div class="cap">de votre consommation<br>couverte par le solaire</div></div>
  </div></div>

  <div class="sec"><div class="wrap">
    <div class="eyebrow">Mois par mois</div>
    <h2>Votre facture, avant et après.</h2>
    <div class="chart"><img src="{ch['bill']}"></div>
  </div></div>

  <div class="sec alt"><div class="wrap">
    <div class="eyebrow">Vos deux options</div>
    <h2>Choisissez votre formule.</h2>
    <div class="ops">
      {opt("Sans batterie","Option 1",d['total_sans'],pk_s,_yrs(d['roi_s']),sans_b,False)}
      {opt("Avec batterie","Option 2",d['total_avec'],pk_a,_yrs(d['roi_a']),avec_b,True)}
    </div>
  </div></div>

  <div class="sec"><div class="wrap">
    <div class="eyebrow">Votre installation</div>
    <h2>Conçue sur votre toit.</h2>
    <div class="two">
      <div><img src="{ch['roof']}"><div class="cap">{d['nb_panneaux']} panneaux disposés sur votre toiture.</div></div>
      <div><img src="{ch['payback']}"><div class="cap">Gain cumulé sur 25 ans — le point marque le retour sur investissement.</div></div>
    </div>
    <div class="fiche">Fiches techniques complètes des équipements → <b>{links.get('produits','taqinor.ma/produits')}</b></div>
  </div></div>

  <div class="sec alt"><div class="wrap">
    <div class="eyebrow">Confiance &amp; engagement</div>
    <h2>Pourquoi TAQINOR.</h2>
    <div class="badges">
      <div class="badge"><div class="n">10<span class="u"> ans</span></div><div class="l">Onduleur</div></div>
      <div class="badge"><div class="n">12<span class="u"> ans</span></div><div class="l">Panneaux</div></div>
      <div class="badge"><div class="n">20<span class="u"> ans</span></div><div class="l">Structure</div></div>
      <div class="badge"><div class="n">30<span class="u"> ans</span></div><div class="l">Performance 87,4%</div></div>
    </div>
    <div class="links">
      <div class="lk"><div class="t">Nos réalisations</div><div class="u">{links.get('realisations','taqinor.ma/realisations')} ›</div></div>
      <div class="lk"><div class="t">Avis clients vérifiés</div><div class="u">{links.get('avis','taqinor.ma/avis')} ›</div></div>
      <div class="lk"><div class="t">Garanties &amp; certifications</div><div class="u">{links.get('garanties','taqinor.ma/garanties')} ›</div></div>
    </div>
  </div></div>

  <div class="sign" id="signer"><div class="in">
    <h2 class="serif">Validez votre devis en ligne</h2>
    <p>Pas de déplacement, pas d'attente. Vous signez, nous planifions la visite technique sous 48–72 h.</p>
    <div class="card">
      <div class="fld"><div class="lab">Option choisie</div>
        <div class="box">Option 2 — Avec batterie · {fmt(d['total_avec'])} MAD TTC</div></div>
      <div class="fld"><div class="lab">Votre nom</div><div class="box">{d['client_full']}</div></div>
      <div class="agree"><span class="ck"></span>
        <span>Je confirme « Bon pour accord » et j'accepte le devis et les conditions générales.</span></div>
      <div class="signbtn">✍  Signer en ligne</div>
      <div class="signnote">Signature électronique horodatée · engagement effectif à réception de l'acompte.</div>
    </div>
  </div></div>

  <div class="ft"><div class="in">
    <div><b>TAQINOR</b> · contact@taqinor.com · +212 6 61 85 04 10</div>
    <div>Devis {d['ref']} · {links.get('signer','taqinor.ma')}</div>
  </div></div>

</div></body></html>"""


def render(out_html=None, out_pdf=None, width_px=1080, height_px=4200):
    data = sample_data.build()
    ch = charts_mod.build_all(data)
    hero = theme.hero_image_b64()
    html = build_html(data, ch, hero, width_px, height_px)
    if out_html:
        Path(out_html).write_text(html, encoding="utf-8")
    if out_pdf:
        from weasyprint import HTML
        base = str(Path(__file__).resolve().parent)
        HTML(string=html, base_url=f"file://{base}/").write_pdf(str(out_pdf))
    return html
