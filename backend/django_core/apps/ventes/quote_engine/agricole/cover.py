# flake8: noqa
"""Agricole — PAGE 1 (cover + the promise). Returns the INNER HTML of one A4
page (no .page wrapper, no footer — the harness paints those). Classes a1-*.

Redesign (2026-06): farmer-first. TWO co-hero numbers — water/day and money
saved/year — each made tangible (bidons / citernes / hectares ; payback). A
single tidy 3-across stat strip replaces the old stacked pile of cards. Energy
(kWc/kWh) is demoted to a small supporting stat, never the headline.
"""
from __future__ import annotations

#: QJR155 (h) — CAPACITÉ du camion-citerne de référence (m³) servant à rendre
#: le volume d'eau tangible. Elle était un « /15.0 » nu dans le calcul, jamais
#: énoncée au client : le chiffre « ≈ N camions-citernes » n'était donc pas
#: vérifiable. Elle est nommée ici et IMPRIMÉE dans le libellé, exactement
#: comme les 20 L du bidon voisin.
CITERNE_M3 = 15


def _yrs(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return str(int(f)) if f == int(f) else f"{f:.1f}".replace(".", ",")


def build(ctx) -> str:
    from . import theme
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]; logo_dark = ctx["logo_dark"]; hero_img = ctx.get("hero_img", "")
    charts = ctx.get("charts") or {}
    etude = d.get("etude") or {}

    navy = C["navy"]; navy_900 = C["navy_900"]; gold = C["gold"]; green = C["green"]
    green_bg = C["green_bg"]; green_700 = C["green_700"]; water = C["water"]
    water_bg = C["water_bg"]; ink = C["ink"]; muted = C["muted"]; muted_2 = C["muted_2"]
    line = C["line"]; line_soft = C["line_soft"]; wash = C["wash"]; earth = C["earth"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]
    f_arabic = fonts.get("arabic", f_sans)

    ref = d["ref"]; date = d["date"]
    client_full = theme.titlecase_name(d.get("client_full") or "Client")
    first = (client_full.split() or [client_full])[0]
    client_meta = theme.join_meta(d.get("client_addr", ""), d.get("client_phone", ""))
    # M7 (audit du 19/08/2026) — pastille de validité : la VRAIE date
    # d'échéance du devis (``valid_until``, posée par le builder depuis
    # ``date_validite`` ou le réglage société ``quote_validity_days``).
    # Indéterminable ⇒ pastille OMISE : le portail client affichait la
    # vraie date, le PDF un « 30 jours » codé en dur.
    _vu = (d.get("valid_until") or "").strip()
    validity_pill = (
        f'<div class="a1-pill">Valable jusqu&#8217;au {_vu}</div>'
        if _vu else "")

    kwc = d.get("puissance_kwc") or 0
    nb_pan = d.get("nb_panneaux") or 0
    wp = d.get("watt_par_panneau") or 0
    pompe_cv = etude.get("pompe_cv"); pompe_kw = etude.get("pompe_kw")
    type_pompe = (etude.get("type_pompe") or "").lower()
    type_lbl = "immergée" if "immerg" in type_pompe else ("surface" if type_pompe else "")
    hmt = etude.get("hmt_m")
    m3j = etude.get("m3_jour")
    has_water = d.get("has_water")
    annual_saving = d.get("annual_saving") or 0
    payback = d.get("payback")
    fda_pct = d.get("fda_pct") or 30
    show_subsidy = d.get("show_subsidy", True)
    hectares = d.get("hectares_irrigable")
    current_fuel = d.get("current_fuel") or "butane"
    fuel_lbl = {"butane": "le butane", "diesel": "le gasoil",
                "none": "votre carburant"}.get(current_fuel, "votre carburant")

    # ── tangibility for the water hero (bidons / citernes / hectares) ────────
    tang_items = []
    if has_water and m3j:
        bidons = round(float(m3j) * 50)                    # 1 m³ = 50 bidons 20 L
        # QJR155 (h) — la capacité du camion est ÉNONCÉE au client (elle l'est
        # dans le libellé plus bas), comme l'est déjà celle du bidon (20 L) :
        # « ≈ 7 camions-citernes » sans dire sur quelle contenance il est
        # compté n'est pas un chiffre vérifiable.
        citernes = round(float(m3j) / CITERNE_M3)
        jerry = (f'<svg viewBox="0 0 24 24" fill="none"><path d="M8 7h6l2 2v10a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z" '
                 f'stroke="{water}" stroke-width="1.6"/><path d="M10 7V5h3v2" stroke="{water}" stroke-width="1.6"/>'
                 f'<path d="M9 11h4" stroke="{water}" stroke-width="1.4"/></svg>')
        truck = (f'<svg viewBox="0 0 24 24" fill="none"><rect x="2.5" y="9" width="11" height="6" rx="3" '
                 f'stroke="{water}" stroke-width="1.6"/><path d="M13.5 11h4l3 3v1h-7z" stroke="{water}" stroke-width="1.6"/>'
                 f'<circle cx="7" cy="17" r="1.8" stroke="{water}" stroke-width="1.5"/>'
                 f'<circle cx="16.5" cy="17" r="1.8" stroke="{water}" stroke-width="1.5"/></svg>')
        field = (f'<svg viewBox="0 0 24 24" fill="none"><path d="M3 19h18" stroke="{green}" stroke-width="1.6"/>'
                 f'<path d="M7 19c0-4 1.5-7 5-9M12 19c0-3 1-6 4-8M7 13c-2 0-3-1.5-3-3 2 0 3 1 3 3z" '
                 f'stroke="{green}" stroke-width="1.5" stroke-linejoin="round"/></svg>')
        tang_items.append((jerry, f'≈ {fmt(bidons)}', 'bidons de 20 L par jour'))
        if citernes >= 1:
            tang_items.append((truck, f'≈ {fmt(citernes)}',
                               f'camions-citernes de {fmt(CITERNE_M3)} m³ '
                               f'par jour'))
        if hectares:
            tang_items.append((field, f'≈ {fmt_dec(hectares)} ha', 'de cultures irriguées'))
    # Full-width strip below the heroes (boxed cells) — room to breathe so the
    # icons never collide with the text (the cramped half-card version did).
    tang_strip = ""
    if tang_items:
        cells = "".join(
            f'<div class="a1-ts"><div class="a1-ts-ic">{ic}</div>'
            f'<div class="a1-ts-tx"><b>{v}</b><span>{l}</span></div></div>'
            for ic, v, l in tang_items[:3])
        tang_strip = f'<div class="a1-tang">{cells}</div>'

    # ── HERO A (water) ───────────────────────────────────────────────────────
    if has_water and m3j:
        heroA = (f'<div class="a1-hero-eb">L\'eau que le soleil vous pompe</div>'
                 f'<div class="a1-hero-n">{fmt(m3j)}<span class="a1-hero-u">m³</span></div>'
                 f'<div class="a1-ar">متر مكعب من الماء كل يوم</div>'
                 f'<div class="a1-hero-c">d\'eau <b>chaque jour</b> — sans gasoil, sans butane.</div>')
    else:
        heroA = (f'<div class="a1-hero-eb">Votre champ solaire</div>'
                 f'<div class="a1-hero-n">{fmt_dec(kwc)}<span class="a1-hero-u">kWc</span></div>'
                 f'<div class="a1-hero-c">{nb_pan} panneaux qui font tourner votre pompe, '
                 f'gratuitement, au soleil.</div>')

    # ── HERO B (money) ───────────────────────────────────────────────────────
    if annual_saving > 0:
        heroB = (f'<div class="a1-hero-eb a1-eb-g">Ce que vous économisez</div>'
                 f'<div class="a1-hero-n a1-n-g">{fmt(annual_saving)}<span class="a1-hero-u a1-u-g">DH</span></div>'
                 f'<div class="a1-ar a1-ar-g">درهم توفّره كل سنة</div>'
                 f'<div class="a1-hero-c">par an, en ne payant plus {fuel_lbl} pour pomper.</div>')
    else:
        heroB = (f'<div class="a1-hero-eb a1-eb-g">Votre carburant</div>'
                 f'<div class="a1-hero-n a1-n-g">0<span class="a1-hero-u a1-u-g">DH</span></div>'
                 f'<div class="a1-hero-c">Le soleil fait tourner votre pompe — '
                 f'l\'énergie est gratuite, à vie.</div>')

    # ── supporting stat strip (3-across, secondary) ─────────────────────────
    stats = []
    if kwc:
        stats.append((f"{fmt_dec(kwc)} kWc", f"Champ solaire · {nb_pan} panneaux"))
    if pompe_cv:
        sub = theme.join_meta(f"{fmt_dec(pompe_kw)} kW" if pompe_kw else "", type_lbl)
        stats.append((f"{fmt_dec(pompe_cv)} CV", f"Pompe solaire{(' · ' + sub) if sub else ''}"))
    # Q3 (fondateur, 20/08/2026) — le plafond FDA n'est pas confirmable : SEUL
    # le taux (sourcé) est montré ici, plus aucun montant en MAD/DH.
    if show_subsidy:
        stats.append((f"{fda_pct} %", "Subvention FDA possible"))
    elif hmt:
        stats.append((f"{fmt(hmt)} m", "Hauteur d'élévation de l'eau"))
    stats = stats[:3]
    stats_html = "".join(
        f'<div class="a1-stat"><div class="a1-stat-v">{v}</div>'
        f'<div class="a1-stat-l">{l}</div></div>' for v, l in stats)

    def _chk(txt):
        return (f'<div class="a1-tr"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" '
                f'fill="{green_bg}"/><path d="M7.5 12.3l3 3 6-6.5" stroke="{green_700}" stroke-width="2" '
                f'stroke-linecap="round" stroke-linejoin="round"/></svg><span>{txt}</span></div>')
    # QJR153 — plus aucune durée littérale ici : la ligne « Panneaux garantis
    # 25 ans » répliquait le forfait de la page 3 et pouvait contredire la
    # garantie RÉELLE du panneau vendu. Sans garantie panneau au devis, la
    # ligne est simplement omise (jamais un chiffre par défaut).
    _garanties = theme.garanties_du_devis(d)
    _pan = next((g for g in _garanties if g[2].startswith("Panneaux")), None)
    trust_txt = []
    if _pan:
        trust_txt.append(f"Panneaux garantis <b>{_pan[0]} {_pan[1]}</b>")
    trust_txt += ["Pompe & variateur garantis",
                  "Installation & SAV par TAQINOR",
                  ("Aide au dossier de subvention FDA" if show_subsidy
                   else "Mise en service & formation incluses")]
    trust_html = "".join(_chk(t) for t in trust_txt)

    # ── small "you cross into profit" payback graph (fills the lower third) ──
    pb_chart = charts.get("payback") or ""
    graph_html = ""
    if pb_chart and payback and annual_saving > 0:
        graph_html = (
            f'<div class="a1-graph"><div class="a1-graph-tx">'
            f'<div class="a1-graph-h">Le jour où le solaire vous rembourse</div>'
            f'<div class="a1-graph-s">Vous récupérez votre investissement en '
            f'≈ <b>{_yrs(payback)} ans</b>. Ensuite, l\'eau du soleil est quasiment '
            f'gratuite — pour 20 ans et plus.</div></div>'
            f'<img class="a1-graph-img" src="{pb_chart}" alt="Amortissement"></div>')

    # ── QRP1 — lien tokenisé + QR de la proposition en ligne ─────────────────
    # Même discipline que la page 1 résidentielle : le lien vient EXCLUSIVEMENT
    # de ``d['links']['signer']`` (builder QX6, ShareLink tokenisé), aucune URL
    # forgée ici et AUCUN paramètre de requête ajouté. L'URL porte le SLUG du
    # nom du client dans son CHEMIN (PV84 — cosmétique, jamais vérifié côté
    # serveur) et le jeton ; ni adresse ni GPS. La forme AFFICHÉE est tronquée
    # à « <hôte>/proposition » : ni le nom ni le jeton en clair. Le repli
    # « <site>/signer/<réf> » (jamais servi par le site) est exclu : sans vraie
    # proposition en ligne, la vignette s'omet plutôt que d'imprimer un QR qui
    # mène à un 404. Rendue sous la note légale, dans les ~50 mm restés libres
    # au bas de cette page (mesurés) : aucune 5ᵉ page possible.
    _signer = ((d.get("links") or {}).get("signer") or "").strip()
    qr_html = ""
    if "/proposition/" in _signer:
        from ..residential import theme as _rtheme
        _href = _rtheme.normaliser_lien(_signer)
        _court = _rtheme.lien_affiche(_signer)
        # A6 — 4 modules de zone de silence (et aucun arrondi sur l'image
        # elle-même : un rayon rogne les motifs de repérage des coins).
        _qr = _rtheme.qr_data_uri(_href, logo=False, correction="M",
                                  box_size=10, border=4)
        if _qr:
            qr_html = (
                '<div class="a1-qr"><div class="a1-qr-t">'
                '<b>Consultez votre proposition interactive</b>'
                f'<span>{_court} — scannez le code</span></div>'
                f'<div class="a1-qr-q"><img src="{_qr}" '
                'alt="QR — votre proposition en ligne"></div></div>')

    if hero_img:
        hero_bg = ("linear-gradient(180deg,rgba(15,30,53,0.66) 0%,"
                   "rgba(15,30,53,0.28) 42%,rgba(15,30,53,0.90) 100%),"
                   f"url('data:image/jpeg;base64,{hero_img}') center 40%/cover no-repeat")
    else:
        hero_bg = (f"linear-gradient(120deg,{navy_900} 0%,{navy} 60%,{water} 165%)")

    css = f"""
<style>
.a1-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;
  position:relative;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a1-root *{{box-sizing:border-box;}}
.a1-serif{{font-family:{f_display};font-weight:400;}}
.a1-hero{{position:relative;background:{hero_bg};height:58mm;overflow:hidden;
  padding:9mm 14mm 0 14mm;border-bottom:2.5px solid {gold};}}
.a1-hero-glow{{position:absolute;top:-40px;right:-50px;width:320px;height:230px;
  background:radial-gradient(ellipse at 75% 18%,rgba(245,166,35,0.34) 0%,transparent 64%);}}
.a1-hero-top{{display:flex;align-items:flex-start;justify-content:space-between;position:relative;z-index:1;}}
.a1-logo{{height:15mm;width:auto;object-fit:contain;display:block;filter:drop-shadow(0 1px 4px rgba(0,0,0,.35));}}
.a1-meta{{text-align:right;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.45);}}
.a1-meta .l{{font-size:6.5pt;letter-spacing:1.5px;text-transform:uppercase;color:{muted_2};}}
.a1-meta .v{{font-size:11.5pt;font-weight:700;color:#fff;margin-top:1px;}}
.a1-meta .dt{{font-size:8pt;color:rgba(255,255,255,.72);margin-top:3px;}}
.a1-pill{{display:inline-block;margin-top:6px;background:{gold};color:{navy_900};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:700;}}
.a1-hero-body{{position:absolute;left:14mm;right:14mm;bottom:7mm;z-index:1;text-shadow:0 1px 6px rgba(0,0,0,.40);}}
.a1-kicker{{font-size:7pt;letter-spacing:2.6px;font-weight:700;text-transform:uppercase;color:{gold};}}
.a1-hello{{font-size:30pt;color:#fff;line-height:1.0;margin-top:6px;letter-spacing:-.5px;}}
.a1-sub{{font-size:11pt;color:rgba(255,255,255,.88);margin-top:6px;}}
.a1-client{{display:flex;align-items:center;gap:9px;padding:4.5mm 14mm 0;font-size:8.5pt;color:{muted};}}
.a1-client b{{color:{ink};font-weight:700;}}
.a1-dot{{color:{line};}}
.a1-tag{{margin-left:auto;background:{green_bg};border:1px solid #BFE6CB;border-radius:20px;
  padding:2px 11px;font-size:7pt;font-weight:700;color:{green_700};letter-spacing:.3px;}}
.a1-wrap{{padding:5mm 14mm 0;}}
/* two co-heroes — table for deterministic equal columns in WeasyPrint */
.a1-heroes{{display:table;width:100%;table-layout:fixed;}}
.a1-hero-c-l,.a1-hero-c-r{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-radius:16px;padding:16px 18px;}}
.a1-hero-c-l{{border-left:5px solid {water};background:linear-gradient(120deg,{water_bg},#fff 72%);}}
.a1-hero-c-r{{border-left:5px solid {green};background:linear-gradient(120deg,{green_bg},#fff 72%);}}
.a1-hero-gap{{display:table-cell;width:14px;}}
.a1-hero-eb{{font-size:7.5pt;letter-spacing:.12em;text-transform:uppercase;color:{water};font-weight:700;}}
.a1-eb-g{{color:{green_700};}}
.a1-hero-n{{font-family:{f_display};font-size:50pt;color:{water};line-height:.9;letter-spacing:-1.5px;margin-top:6px;}}
.a1-n-g{{color:{green_700};}}
.a1-hero-u{{font-size:19pt;margin-left:6px;letter-spacing:0;}}
.a1-u-g{{color:{green_700};}}
.a1-hero-c{{font-size:10pt;color:{ink};line-height:1.4;margin-top:8px;}}
.a1-hero-c b{{color:{navy};}}
.a1-ar{{font-family:{f_arabic};direction:rtl;text-align:right;unicode-bidi:isolate;
  font-size:10.5pt;font-weight:700;color:{water};margin-top:5px;line-height:1.3;}}
.a1-ar-g{{color:{green_700};}}
/* tangibility — full-width strip below the heroes (boxed cells, icon in its own
   slot so it never collides with the text) */
.a1-tang{{display:flex;gap:11px;margin-top:12px;}}
.a1-ts{{flex:1 1 0;min-width:0;display:flex;align-items:center;gap:11px;
  border:1px solid {line};border-radius:12px;background:{wash};padding:10px 13px;}}
.a1-ts-ic{{flex-shrink:0;width:24px;height:24px;}}
.a1-ts-ic svg{{width:24px;height:24px;display:block;}}
.a1-ts-tx{{min-width:0;}}
.a1-ts-tx b{{display:block;font-family:{f_display};font-size:15pt;color:{navy};line-height:1;}}
.a1-ts-tx span{{display:block;font-size:7.4pt;color:{muted};margin-top:3px;line-height:1.2;}}
/* supporting stat strip */
.a1-stats{{display:flex;gap:11px;margin-top:13px;}}
.a1-stat{{flex:1 1 0;min-width:0;border:1px solid {line};border-top:3px solid {gold};
  border-radius:12px;padding:11px 13px;background:#fff;}}
.a1-stat-v{{font-family:{f_display};font-size:16pt;color:{navy};line-height:1.0;}}
.a1-stat-l{{font-size:7.6pt;color:{muted};margin-top:4px;line-height:1.25;}}
.a1-trust{{display:flex;flex-wrap:wrap;gap:9px 18px;margin-top:16px;padding:14px 16px;
  border:1px solid {line};border-radius:14px;background:{wash};}}
.a1-tr{{display:flex;align-items:center;gap:7px;font-size:8.6pt;color:{ink};flex:1 1 40%;}}
.a1-tr svg{{width:17px;height:17px;flex-shrink:0;}}
.a1-tr b{{color:{green_700};font-weight:700;}}
.a1-graph{{display:flex;gap:14px;align-items:center;margin-top:13px;padding:13px 16px;
  border:1px solid {line};border-left:5px solid {gold};border-radius:14px;
  background:linear-gradient(110deg,{C['gold_soft']},#fff 58%);}}
.a1-graph-tx{{flex:0 0 56mm;}}
.a1-graph-h{{font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};line-height:1.12;}}
.a1-graph-s{{font-size:8.6pt;color:{ink};line-height:1.4;margin-top:5px;}}
.a1-graph-s b{{color:{earth};}}
.a1-graph-img{{flex:1 1 0;min-width:0;display:block;width:100%;height:30mm;
  object-fit:contain;object-position:right center;}}
.a1-note{{margin-top:13px;font-size:7.8pt;color:{muted_2};line-height:1.4;}}
.a1-note b{{color:{muted};font-weight:700;}}
/* QRP1 — vignette du lien tokenise + QR. TABLE CSS, pas flex
   (RENDERING_NOTES §1). Posee sous la note legale, dans les ~50 mm restes
   libres au bas de cette page (mesures sur le rendu reel) : la bande ne peut
   pas pousser de 5e page. Omise sans lien tokenise. */
.a1-qr{{display:table;width:100%;margin-top:11px;border:1px solid {line};
  border-radius:12px;background:#fff;padding:8px 14px;}}
.a1-qr-t{{display:table-cell;vertical-align:middle;font-size:8.4pt;color:{ink};
  line-height:1.3;}}
.a1-qr-t b{{color:{navy};font-weight:700;}}
.a1-qr-t span{{display:block;font-size:7pt;color:{muted};margin-top:2px;
  word-break:break-all;}}
.a1-qr-q{{display:table-cell;width:20mm;vertical-align:middle;
  text-align:right;}}
.a1-qr-q img{{height:18mm;width:18mm;display:inline-block;}}
</style>
"""

    html = f"""{css}
<div class="a1-root">
  <div class="a1-hero">
    <div class="a1-hero-glow"></div>
    <div class="a1-hero-top">
      <img class="a1-logo" src="data:image/png;base64,{logo_dark}" alt="TAQINOR">
      <div class="a1-meta">
        <div class="l">Réf. devis</div><div class="v">{ref}</div>
        <div class="dt">{date}</div>{validity_pill}
      </div>
    </div>
    <div class="a1-hero-body">
      <div class="a1-kicker">Proposition — Pompage solaire pour l'irrigation</div>
      <div class="a1-serif a1-hello">Bonjour {first},</div>
      <div class="a1-sub">Voici, en clair, ce que le solaire change pour votre exploitation.</div>
    </div>
  </div>

  <div class="a1-client">
    <b>{client_full}</b>
    {f'<span class="a1-dot">·</span><span>{client_meta}</span>' if client_meta else ''}
    <span class="a1-tag">Agricole · Pompage</span>
  </div>

  <div class="a1-wrap">
    <div class="a1-heroes">
      <div class="a1-hero-c-l">{heroA}</div>
      <div class="a1-hero-gap"></div>
      <div class="a1-hero-c-r">{heroB}</div>
    </div>
    {tang_strip}
    <div class="a1-stats">{stats_html}</div>
    <div class="a1-trust">{trust_html}</div>
    {graph_html}
    <div class="a1-note">Tous les montants sont en dirhams (DH), TTC. Les volumes d'eau, économies
      et durées d'amortissement sont des <b>estimations</b> basées sur vos données et l'ensoleillement
      de votre région. Étude, équipement, prix et conditions détaillés dans les pages suivantes.</div>
    {qr_html}
  </div>
</div>
"""
    return html
