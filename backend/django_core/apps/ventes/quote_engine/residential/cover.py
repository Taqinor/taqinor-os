# -*- coding: utf-8 -*-
# flake8: noqa
"""
quote_engine residential — PAGE 1 (cover + financial hook).

`build(ctx) -> str` returns the INNER HTML of one A4 page (210mm × 297mm).
NO `<div class="page">` wrapper, NO `<html>`, NO footer — the harness paints a
13mm footer at the very bottom, so all content here stays in the top ~283mm.

Design language (kept on-brand with the existing premium engine): dark-navy
hero, gold accents, ROI-green, DM Serif Display / Playfair headlines, DM Sans
body, generous whitespace, rounded 12px cards with 1px hairline borders.

Every class is prefixed `c1-` so it can never clash with pages 2/3.
Every money number goes through `ctx["fmt"]`; currency is MAD; language FR.
"""


def build(ctx):
    from . import theme

    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    logo_dark = ctx["logo_dark"]
    charts = ctx["charts"]
    hero_img = ctx.get("hero_img", "")
    # QX4 — identité société (multi-tenant) : marque affichée sur la cover
    # (logo alt + « avec <marque> »), repli sur TAQINOR quand aucun profil.
    ident = ctx.get("ident") or {}
    brand = ident.get("brand_name") or "TAQINOR"

    # ── tokens ──────────────────────────────────────────────────────────────
    navy = C["navy"]
    navy_900 = C.get("navy_900", "#0F1E35")
    gold = C["gold"]
    gold_soft = C.get("gold_soft", "#FDF3E3")
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    ink = C.get("ink", "#1F2937")
    muted = C.get("muted", "#6B7280")
    muted_2 = C.get("muted_2", "#9BA3AE")
    line = C.get("line", "#E5E7EB")
    line_soft = C.get("line_soft", "#EEF1F5")
    paper = C.get("paper", "#FFFFFF")
    wash = C.get("wash", "#F7F9FC")

    f_display = fonts["display"]   # DM Serif Display
    f_serif = fonts["serif"]       # Playfair Display
    f_sans = fonts["sans"]         # DM Sans

    # ── data ────────────────────────────────────────────────────────────────
    ref = d["ref"]
    date = d["date"]
    client_full = theme.titlecase_name(d["client_full"])
    first_name = (client_full.split() or [client_full])[0]
    client_addr = d.get("client_addr", "")
    client_city = d.get("client_city", "")
    client_phone = d.get("client_phone", "")
    inst_type = d.get("inst_type", "")
    # One clean meta line — no dangling comma when address or city is empty.
    client_meta = theme.join_meta(client_addr, client_city, client_phone)
    kwc = d["puissance_kwc"]
    nb_pan = d["nb_panneaux"]
    wp = d["watt_par_panneau"]
    prod_kwh = d["prod_kwh"]
    total_sans = d["total_sans"]
    total_avec = d["total_avec"]
    roi_s = d["roi_s"]
    roi_a = d["roi_a"]
    eco_a_ann = d["eco_a_ann"]
    annual_before = d["annual_before"]
    annual_after = d["annual_after"]
    coverage_pct = d["coverage_pct"]
    pct_cut = round((1 - annual_after / max(1, annual_before)) * 100)
    # Tangible monthly framing (research: a monthly figure lands harder than an
    # annual one) — derived straight from the annual before/after, never invented.
    month_before = round(annual_before / 12)
    month_after = round(annual_after / 12)
    # Environmental impact — a CALCULATION, not an invented statistic: Moroccan
    # grid factor ≈ 0.81 t CO₂/MWh (IEA), ~21 kg CO₂ absorbed per tree per year.
    co2_t = prod_kwh * 0.81 / 1000.0
    co2_txt = (f"{co2_t:.1f}".replace(".", ",") if co2_t < 10
               else fmt(co2_t))
    trees = max(1, round(prod_kwh * 0.81 / 21))
    validity_days = d["validity_days"]
    # QRES31 — échéance absolue sur la pastille (une date butoir concrète
    # engage plus que « 30 jours ») ; repli sur la durée si date illisible.
    _valid_until = theme.valid_until(date, validity_days)
    validity_pill = (f"Valable jusqu'au {_valid_until}" if _valid_until
                     else f"Validité {validity_days} jours")
    sans_bullets = d.get("sans_bullets", []) or []
    avec_bullets = d.get("avec_bullets", []) or []
    # QX5 — n'imprime JAMAIS d'option fantôme : deux cartes seulement quand le
    # devis porte réellement deux options (réseau ET hybride+batterie). Un devis
    # mono-option (batterie seule / réseau seul / choix vendeur restreint) rend
    # UNE carte pleine largeur pour l'option réelle — jamais une « Sans batterie »
    # fabriquée sans onduleur. Repli sûr : sans drapeau explicite, comportement
    # deux-options historique.
    deux_options = bool(d.get("deux_options", True))
    avec_ok = bool(d.get("avec_ok", True))
    # QX7a — couverture solaire : étiquetée « estimation » quand la conso réelle
    # est inconnue (dérivée d'une facture, pas d'une conso kWh réelle).
    cov_est_txt = " (estimation)" if d.get("coverage_estimated") else ""
    # QRES4 — cohérence donut / gros pourcentage : quand la couverture (part de
    # la conso produite) dépasse nettement la baisse de facture (part
    # autoconsommée valorisée), une ligne explique l'écart au lieu de laisser
    # « −85 % » côtoyer « 100 % » sans lien apparent.
    # QRES24 — le MENSUEL devient la ligne primaire du hook (l'ancrage le plus
    # parlant pour un ménage) ; l'annuel passe en secondaire. Quand le devis
    # porte deux options, une légende dit sur QUELLE option les chiffres du
    # hook sont calculés (ils lisent l'option recommandée avec batterie).
    opt_caption = ""
    if deux_options:
        opt_caption = ('<div class="c1-bigcut-cap">Chiffres calculés pour '
                       'l\'option recommandée — avec batterie.</div>')

    cov_gap_note = ""
    if coverage_pct - pct_cut >= 10:
        cov_gap_note = (
            '<div class="c1-bigcut-note">Pourquoi pas −{cov} % ? Seuls les kWh '
            'autoconsommés réduisent la facture (loi 82-21) — le surplus '
            'injecté n\'est pas rémunéré.</div>').format(cov=coverage_pct)

    kwc_str = f"{kwc:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    pkwc_sans = fmt(total_sans / kwc) if kwc else "—"
    pkwc_avec = fmt(total_avec / kwc) if kwc else "—"

    # check + arrow glyphs (inline SVG renders crisply in WeasyPrint)
    check = (f'<svg class="c1-chk" viewBox="0 0 14 14">'
             f'<circle cx="7" cy="7" r="7" fill="{green_bg}"/>'
             f'<path d="M4 7.2l2 2 4-4.4" stroke="{green}" stroke-width="1.6" '
             f'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    arrow = (f'<svg viewBox="0 0 28 16" class="c1-arrow">'
             f'<path d="M2 8h20M16 2l7 6-7 6" stroke="{gold}" stroke-width="2.4" '
             f'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')

    def bullets(items):
        items = items[:3]
        return "".join(
            f'<li>{check}<span>{b}</span></li>' for b in items
        )

    # ── Hero background: real installation photo + navy gradient overlay so
    # the logo, ref and "Bonjour …" stay readable. No photo -> flat navy. ─────
    # QRES23 — duotone navy CONTRÔLÉ : voiles renforcés (l'image refroidit,
    # le bord droit reste navy — jamais de dérive brune sous le texte).
    if hero_img:
        hero_bg = (
            "linear-gradient(180deg,rgba(15,30,53,0.78) 0%,"
            "rgba(15,30,53,0.44) 42%,rgba(15,30,53,0.94) 100%),"
            "linear-gradient(100deg,rgba(15,30,53,0.90) 0%,"
            "rgba(20,36,62,0.52) 58%,rgba(26,43,74,0.34) 100%),"
            f"url('data:image/jpeg;base64,{hero_img}') center 38%/cover no-repeat"
        )
    else:
        hero_bg = navy_900

    # ── CSS (all classes prefixed c1-) ──────────────────────────────────────
    css = f"""
<style>
.c1-root{{font-family:'{f_sans}',sans-serif;color:{ink};width:210mm;
  height:297mm;position:relative;background:transparent;
  -webkit-print-color-adjust:exact;print-color-adjust:exact;}}
/* QRES26 — profondeur matière : ombre douce commune aux cartes du hook. */
.c1-hook-left,.c1-bill,.c1-kpi,.c1-opt,.c1-impact{{
  box-shadow:0 1px 2px rgba(26,43,74,.04),0 5px 14px rgba(26,43,74,.05);}}
.c1-root *{{box-sizing:border-box;}}
.c1-serif{{font-family:'{f_display}','{f_serif}',Georgia,serif;font-weight:400;}}
.c1-kicker{{font-size:7pt;letter-spacing:2.6px;font-weight:700;text-transform:uppercase;}}

/* ── HERO ──────────────────────────────────────────────────────────────── */
.c1-hero{{position:relative;background:{hero_bg};height:53mm;overflow:hidden;
  padding:8mm 14mm 0 14mm;border-bottom:2.5px solid {gold};}}
.c1-hero-glow{{position:absolute;top:-30px;right:-40px;width:300px;height:210px;
  background:radial-gradient(ellipse at 75% 18%,rgba(245,166,35,0.30) 0%,transparent 64%);
  pointer-events:none;}}
.c1-hero-top{{display:flex;align-items:flex-start;justify-content:space-between;
  position:relative;z-index:1;}}
.c1-logo{{height:9mm;width:auto;object-fit:contain;display:block;}}
.c1-hero-meta{{text-align:right;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,0.45);}}
.c1-hero-meta .c1-ref-l{{font-size:6.5pt;letter-spacing:1.5px;text-transform:uppercase;
  color:{muted_2};}}
.c1-hero-meta .c1-ref-v{{font-size:11.5pt;font-weight:700;color:#fff;margin-top:1px;
  letter-spacing:.3px;}}
.c1-hero-meta .c1-date{{font-size:8pt;color:rgba(255,255,255,0.72);margin-top:3px;}}
.c1-pill-gold{{display:inline-block;margin-top:6px;background:{gold};color:{navy_900};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:700;letter-spacing:.3px;}}
.c1-hero-body{{position:absolute;left:14mm;right:14mm;bottom:6.5mm;z-index:1;
  text-shadow:0 1px 6px rgba(0,0,0,0.40);}}
.c1-hero-kicker{{color:{gold};margin-bottom:6px;}}
.c1-hello{{font-size:37pt;color:#fff;line-height:0.98;letter-spacing:-0.6px;}}
.c1-sub{{font-size:11pt;color:rgba(255,255,255,0.88);margin-top:7px;font-weight:400;}}

/* ── CLIENT + CREDIBILITY LINE ─────────────────────────────────────────── */
/* QRES41 — rangée identité sûre pour les LONGUES adresses : le méta est un
   bloc flex:1/min-width:0 qui REPLIE proprement (le téléphone ne chevauche
   plus jamais le nom), la pastille reste calée en haut à droite. */
/* QRES41 — TABLE CSS, pas flex (RENDERING_NOTES §1 : le flex WeasyPrint
   superposait le méta replié sur le nom). Nom insécable | adresse qui replie
   proprement | pastille calée à droite. */
.c1-client{{display:table;table-layout:auto;width:182mm;margin:5mm 14mm 0;
  font-size:8.5pt;color:{muted};line-height:1.35;}}
.c1-client-nom{{display:table-cell;white-space:nowrap;vertical-align:top;
  color:{ink};font-weight:700;padding-right:8px;}}
.c1-client-meta{{display:table-cell;width:100%;vertical-align:top;}}
.c1-tag-cell{{display:table-cell;white-space:nowrap;vertical-align:top;
  padding-left:9px;}}
.c1-dot{{color:{line};font-weight:700;}}
.c1-tag{{display:inline-block;background:{wash};border:1px solid {line};
  border-radius:20px;padding:2px 10px;font-size:7pt;font-weight:600;
  color:{navy};letter-spacing:.3px;}}
.c1-trust{{display:flex;align-items:center;gap:8px;padding:2.6mm 14mm 0 14mm;}}
.c1-trust-line{{flex:1 1 0;height:1px;background:{line_soft};}}
.c1-trust-txt{{font-size:7pt;letter-spacing:.12em;text-transform:uppercase;
  font-weight:700;color:{muted_2};white-space:nowrap;word-spacing:.35em;}}
.c1-trust-txt b{{color:{muted_2};font-weight:700;}}

/* ── MONEY HOOK ────────────────────────────────────────────────────────── */
.c1-wrap{{padding:3.5mm 14mm 0 14mm;}}
/* CSS table (not flex) so the two cards auto-equalise height — WeasyPrint flex
   align-stretch left the donut card ~24pt short of the hook card. */
.c1-hook{{display:table;width:100%;border-spacing:0;}}
.c1-hook-left{{display:table-cell;vertical-align:middle;border:1px solid {line};
  border-radius:14px;padding:15px 18px;background:#fff;}}
.c1-hook-gap{{display:table-cell;width:14px;}}
.c1-hook-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;}}
.c1-hook-eyebrow{{color:{muted};font-size:6.5pt;letter-spacing:2px;text-transform:uppercase;
  font-weight:700;}}
.c1-bigcut{{display:flex;align-items:center;gap:18px;margin-top:8px;}}
.c1-bigcut-n{{font-family:'{f_display}','{f_serif}',serif;font-size:46pt;color:{gold};
  line-height:.82;letter-spacing:-1.5px;white-space:nowrap;margin-right:20px;}}
.c1-bigcut-n span{{font-size:22pt;vertical-align:top;}}
.c1-bigcut-t{{font-size:11.5pt;font-weight:700;color:{navy};line-height:1.15;}}
/* QRES42 — le NOUVEAU mensuel devient le héros chiffré (serif or, 29pt) ;
   l'ancien, barré, le surplombe en gris discret. */
.c1-bigcut-old{{font-size:8.5pt;color:{muted};margin-top:5px;white-space:nowrap;}}
.c1-bigcut-old s{{color:{muted_2};text-decoration-thickness:1.3px;}}
.c1-bigcut-new{{font-family:'{f_display}','{f_serif}',serif;font-size:29pt;
  color:{gold};line-height:1.02;margin-top:2px;letter-spacing:-0.5px;
  white-space:nowrap;}}
.c1-bigcut-new span{{font-size:11pt;color:{muted};font-family:'{f_sans}',sans-serif;}}
.c1-bigcut-m{{font-size:8pt;color:{muted};margin-top:3px;white-space:nowrap;}}
.c1-bigcut-m s{{color:{muted_2};text-decoration-thickness:1.2px;}}
.c1-bigcut-m b{{color:{navy};font-weight:700;}}
.c1-bigcut-cap{{font-size:6.8pt;color:{muted_2};margin-top:4px;}}
.c1-bigcut-note{{font-size:6.8pt;color:{muted_2};margin-top:6px;line-height:1.3;}}
.c1-cut{{background:{gold};color:{navy_900};font-weight:700;font-size:9.5pt;
  padding:3px 11px;border-radius:20px;letter-spacing:.2px;white-space:nowrap;}}
.c1-cmp{{display:flex;align-items:center;gap:12px;}}
.c1-cmp-col{{flex:1 1 0;min-width:0;}}
.c1-cmp-lab{{font-size:7.5pt;color:{muted};margin-bottom:2px;}}
.c1-cmp-old{{font-family:'{f_display}','{f_serif}',serif;font-size:17pt;color:{muted_2};
  text-decoration:line-through;text-decoration-thickness:1.5px;line-height:1.0;
  white-space:nowrap;}}
.c1-cmp-old .c1-u{{font-size:8.5pt;letter-spacing:0;}}
.c1-cmp-new{{font-family:'{f_display}','{f_serif}',serif;font-size:25pt;color:{gold};
  line-height:1.0;white-space:nowrap;letter-spacing:-0.5px;}}
.c1-cmp-new .c1-u{{font-size:10pt;color:{gold};}}
.c1-arrow{{width:30px;height:18px;flex-shrink:0;}}

/* Donut card — donut + caption read as ONE tight, centered unit. The PNG
   already bakes in "74%" + "couverture", so the caption only COMPLEMENTS it.
   The card stays a normal flex item (block); an INNER table-cell does the
   reliable vertical centring (WeasyPrint flex column centring is flaky). */
.c1-hook-right{{display:table-cell;vertical-align:middle;width:41mm;
  border:1px solid {line};border-radius:14px;
  background:linear-gradient(180deg,{wash},#ffffff 80%);}}
.c1-donut-tab{{display:table;width:100%;height:100%;}}
.c1-donut-cell{{display:table-cell;vertical-align:middle;text-align:center;
  padding:8px 5px;}}
.c1-donut-k{{font-size:6pt;letter-spacing:2px;text-transform:uppercase;
  font-weight:700;color:{muted_2};margin-bottom:3px;}}
.c1-donut{{height:31mm;width:31mm;display:inline-block;}}
.c1-donut-cap{{font-size:7.5pt;color:{navy};text-align:center;line-height:1.25;
  margin-top:3px;font-weight:600;}}
.c1-donut-cap span{{display:block;font-size:6.8pt;color:{muted};font-weight:400;
  margin-top:1px;}}

/* ── BILL CHART ────────────────────────────────────────────────────────── */
.c1-bill{{margin-top:12px;border:1px solid {line};border-radius:14px;background:#fff;
  padding:10px 16px 8px;}}
.c1-bill-head{{display:flex;align-items:baseline;justify-content:space-between;
  margin-bottom:4px;}}
.c1-bill-t{{font-size:7.5pt;font-weight:700;color:{navy};text-transform:uppercase;
  letter-spacing:.6px;}}
.c1-bill-leg{{font-size:6.5pt;color:{muted};}}
.c1-bill-leg .c1-sw{{display:inline-block;width:8px;height:8px;border-radius:2px;
  vertical-align:middle;margin:0 3px 0 8px;}}
/* Cap chart height (PNG is ~3.3:1) so it stays crisp & airy, never dominates the
   page — centred so the shorter image reads as intentional, not floated. */
.c1-bill img{{height:33.5mm;width:auto;max-width:100%;display:block;margin:0 auto;}}

/* ── KPI CHIPS ─────────────────────────────────────────────────────────── */
.c1-kpis{{display:flex;gap:12px;margin-top:11px;}}
.c1-kpi{{flex:1 1 0;min-width:0;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;padding:9px 14px;background:#fff;}}
.c1-kpi-v{{font-family:'{f_display}','{f_serif}',serif;font-size:17pt;color:{navy};
  line-height:1.0;}}
.c1-kpi-v .c1-u{{font-size:9pt;color:{muted};}}
.c1-kpi-l{{font-size:7pt;color:{muted};margin-top:3px;letter-spacing:.4px;}}

/* ── IMPACT STRIP ──────────────────────────────────────────────────────── */
.c1-impact{{display:flex;align-items:center;gap:9px;margin-top:9px;
  border:1px solid {green_bg};border-left:4px solid {green};border-radius:12px;
  background:linear-gradient(100deg,{green_bg},#ffffff 70%);padding:8px 14px;}}
.c1-impact svg{{width:15px;height:15px;flex-shrink:0;}}
.c1-impact-t{{font-size:8pt;color:{ink};line-height:1.25;}}
.c1-impact-t b{{color:{green};font-weight:700;}}

/* ── OPTION CARDS ──────────────────────────────────────────────────────── */
.c1-opts{{display:flex;gap:14px;margin-top:9px;}}
.c1-opt{{flex:1 1 0;min-width:0;border:1px solid {line};border-radius:14px;
  background:#fff;padding:13px 17px 12px;position:relative;display:flex;
  flex-direction:column;}}
.c1-opt.c1-reco{{border:1.5px solid {gold};
  background:linear-gradient(180deg,#FFFCF5,#ffffff 55%);}}
.c1-opt-head{{display:flex;align-items:flex-start;justify-content:space-between;
  margin-bottom:2px;}}
.c1-opt-k{{font-size:6.5pt;letter-spacing:2px;color:{gold};font-weight:700;
  text-transform:uppercase;}}
.c1-opt-name{{font-size:11.5pt;font-weight:700;color:{navy};margin-top:1px;}}
.c1-reco-pill{{background:{gold};color:{navy_900};border-radius:20px;padding:2px 9px;
  font-size:6.5pt;font-weight:700;letter-spacing:.4px;white-space:nowrap;}}
.c1-opt-price{{font-family:'{f_display}','{f_serif}',serif;font-size:24pt;color:{navy};
  line-height:1.0;margin-top:7px;letter-spacing:-0.5px;}}
.c1-opt-price .c1-u{{font-size:10pt;color:{muted};}}
.c1-opt-kwc{{font-size:7pt;color:{muted};margin-top:2px;}}
.c1-roi{{display:inline-flex;align-items:center;align-self:flex-start;gap:5px;
  background:{green_bg};color:{green};border-radius:20px;padding:3px 11px;
  font-size:8pt;font-weight:700;margin-top:8px;}}
.c1-roi svg{{width:11px;height:11px;}}
.c1-opt-eco{{font-size:7.8pt;color:{muted};margin-top:5px;}}
.c1-opt-eco b{{color:{green};font-weight:700;}}
.c1-opt-hr{{height:1px;background:{line_soft};margin:9px 0 7px;}}
.c1-opt ul{{list-style:none;padding:7px 0 0;margin:7px 0 0;
  border-top:1px solid {line_soft};}}
.c1-opt li{{display:flex;align-items:flex-start;gap:7px;font-size:8pt;
  color:{ink};line-height:1.32;margin-bottom:3px;}}
.c1-chk{{width:12px;height:12px;flex-shrink:0;margin-top:1px;}}
.c1-opt li span{{min-width:0;}}
.c1-note{{font-size:6.5pt;color:{muted_2};font-style:italic;margin-top:auto;
  padding-top:5px;}}
/* QX5 — carte d'option unique : pleine largeur (aucune option fantôme). */
.c1-opt-full{{flex:1 1 100%;}}
</style>
"""

    # ── QX5 — cartes d'option (deux OU une seule, jamais fantôme) ───────────
    # QRES43 — chaque carte porte SON économie annuelle : l'option recommandée
    # (plus chère, payback plus long) montre enfin POURQUOI elle gagne.
    eco_s_ann = d.get("eco_s_ann")
    eco_a_ann = d.get("eco_a_ann")

    def _opt_card(kicker, name, price, pkwc, roi_v, bull, eco=None,
                  reco=False, full=False):
        cls = "c1-opt" + (" c1-reco" if reco else "") + (" c1-opt-full" if full else "")
        pill = ('<span class="c1-reco-pill">Recommandé</span>' if reco else "")
        eco_html = (
            f'<div class="c1-opt-eco">Économie estimée ≈ <b>{fmt(eco)} '
            'MAD/an</b></div>' if eco else "")
        return (
            f'<div class="{cls}">'
            f'<div class="c1-opt-head"><div>'
            f'<div class="c1-opt-k">{kicker}</div>'
            f'<div class="c1-opt-name">{name}</div></div>{pill}</div>'
            f'<div class="c1-opt-price">{fmt(price)}<span class="c1-u">&nbsp;MAD</span></div>'
            f'<div class="c1-opt-kwc">soit {pkwc} MAD/kWc · TTC</div>'
            f'<div class="c1-roi">{_roi_svg(green)}Rentabilisé en {_yrs(roi_v)} ans</div>'
            f'{eco_html}'
            f'<ul>{bullets(bull)}</ul>'
            f'<div class="c1-note">Détail &amp; équipement en page 2</div>'
            f'</div>')

    if deux_options:
        opts_html = (
            _opt_card("Option 1", "Sans batterie", total_sans, pkwc_sans,
                      roi_s, sans_bullets, eco=eco_s_ann)
            + _opt_card("Option 2", "Avec batterie", total_avec, pkwc_avec,
                        roi_a, avec_bullets, eco=eco_a_ann, reco=True))
    elif avec_ok:
        # Option unique AVEC batterie : une carte pleine largeur, pas de « Sans »
        # fabriquée (dépourvue d'onduleur).
        opts_html = _opt_card("Votre installation", "Avec batterie", total_avec,
                              pkwc_avec, roi_a, avec_bullets, eco=eco_a_ann,
                              full=True)
    else:
        # Option unique SANS batterie (réseau seul) : une carte pleine largeur.
        opts_html = _opt_card("Votre installation", "Sans batterie", total_sans,
                              pkwc_sans, roi_s, sans_bullets, eco=eco_s_ann,
                              full=True)

    # ── HTML ────────────────────────────────────────────────────────────────
    html = f"""{css}
<div class="c1-root">

  <!-- HERO ─────────────────────────────────────────────────────────────── -->
  <div class="c1-hero">
    <div class="c1-hero-glow"></div>
    <div class="c1-hero-top">
      <img class="c1-logo" src="data:image/png;base64,{logo_dark}" alt="{brand}">
      <div class="c1-hero-meta">
        <div class="c1-ref-l">Réf. devis</div>
        <div class="c1-ref-v">{ref}</div>
        <div class="c1-date">{date}</div>
        <div class="c1-pill-gold">{validity_pill}</div>
      </div>
    </div>
    <div class="c1-hero-body">
      <div class="c1-kicker c1-hero-kicker">Proposition commerciale — Installation solaire</div>
      <div class="c1-serif c1-hello">Bonjour {first_name},</div>
      <div class="c1-sub">Votre facture d'électricité réduite d'environ {pct_cut}&nbsp;% —
        performance garantie 30&nbsp;ans.</div>
    </div>
  </div>

  <!-- CLIENT LINE ──────────────────────────────────────────────────────── -->
  <div class="c1-client">
    <b class="c1-client-nom">{client_full}</b>
    <span class="c1-client-meta">{client_meta}</span>
    <span class="c1-tag-cell"><span class="c1-tag">{inst_type}</span></span>
  </div>

  <!-- CREDIBILITY CUE (number-free) ──────────────────────────────────────── -->
  <div class="c1-trust">
    <div class="c1-trust-line"></div>
    <div class="c1-trust-txt"><b>Ingénieurs solaires</b> &middot; Performance garantie 30 ans &middot; Suivi en temps réel</div>
    <div class="c1-trust-line"></div>
  </div>

  <div class="c1-wrap">

    <!-- MONEY HOOK ─────────────────────────────────────────────────────── -->
    <div class="c1-hook">
      <div class="c1-hook-left">
        <div class="c1-hook-eyebrow">Ce que le solaire change pour vous</div>
        <div class="c1-bigcut">
          <div class="c1-bigcut-n">&minus;{pct_cut}<span>%</span></div>
          <div class="c1-bigcut-x">
            <div class="c1-bigcut-t">sur votre facture<br>d'électricité</div>
            <div class="c1-bigcut-old">≈&nbsp;<s>{fmt(month_before)} MAD/mois</s>
              aujourd'hui</div>
            <div class="c1-bigcut-new">{fmt(month_after)}<span>&nbsp;MAD/mois</span></div>
            <div class="c1-bigcut-m">soit <s>{fmt(annual_before)} MAD/an</s>
              &nbsp;&rarr;&nbsp;<b>≈&nbsp;{fmt(annual_after)} MAD/an</b></div>
            {opt_caption}
          </div>
        </div>
        {cov_gap_note}
      </div>
      <div class="c1-hook-gap"></div>
      <div class="c1-hook-right">
        <div class="c1-donut-tab"><div class="c1-donut-cell">
          <div class="c1-donut-k">Énergie solaire</div>
          <img class="c1-donut" src="{charts['coverage']}" alt="Couverture solaire">
          <div class="c1-donut-cap">de votre consommation<span>annuelle assurée par le solaire{cov_est_txt}</span></div>
        </div></div>
      </div>
    </div>

    <!-- BILL CHART ─────────────────────────────────────────────────────── -->
    <div class="c1-bill">
      <div class="c1-bill-head">
        <div class="c1-bill-t">Votre facture mois par mois — avant / après</div>
        <div class="c1-bill-leg">
          <span class="c1-sw" style="background:#C2CCDA;"></span>aujourd'hui
          <span class="c1-sw" style="background:{gold};"></span>avec {brand}
        </div>
      </div>
      <img src="{charts['bill']}" alt="Facture mensuelle avant / après">
    </div>

    <!-- KPI CHIPS ──────────────────────────────────────────────────────── -->
    <div class="c1-kpis">
      <div class="c1-kpi">
        <div class="c1-kpi-v">{kwc_str}<span class="c1-u">&nbsp;kWc</span></div>
        <div class="c1-kpi-l">Puissance · {nb_pan} panneaux × {wp} W</div>
      </div>
      <div class="c1-kpi">
        <div class="c1-kpi-v">{fmt(prod_kwh)}<span class="c1-u">&nbsp;kWh/an</span></div>
        <div class="c1-kpi-l">Production estimée</div>
      </div>
      <div class="c1-kpi">
        <div class="c1-kpi-v">{fmt(eco_a_ann)}<span class="c1-u">&nbsp;MAD/an</span></div>
        <div class="c1-kpi-l">Économie estimée</div>
      </div>
    </div>

    <!-- IMPACT STRIP ───────────────────────────────────────────────────── -->
    <div class="c1-impact">
      <svg viewBox="0 0 24 24" fill="none"><path d="M12 21c5-1 8-5 8-11V5l-5 1c-5 1-8 4-8 9 0 .7.1 1.4.3 2"
        stroke="{green}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M7 21c0-4 2-7 6-9" stroke="{green}" stroke-width="1.7" stroke-linecap="round"/></svg>
      <div class="c1-impact-t">Et pour la planète&nbsp;: ≈&nbsp;<b>{co2_txt} tonnes de CO<sub>2</sub></b>
        évitées chaque année — l'équivalent de <b>≈&nbsp;{fmt(trees)} arbres</b> plantés.</div>
    </div>

    <!-- OPTION CARDS ───────────────────────────────────────────────────── -->
    <div class="c1-opts">{opts_html}</div>
  </div>
</div>
"""
    return html


def _yrs(v):
    """ROI like 4.7 → '4,7' (FR decimal comma), 5.0 → '5'."""
    try:
        f = float(v)
    except Exception:
        return str(v)
    if f == int(f):
        return str(int(f))
    return f"{f:.1f}".replace(".", ",")


def _roi_svg(color):
    return (f'<svg viewBox="0 0 14 14" fill="none">'
            f'<path d="M2 10l3.2-3.6 2.4 2L12 3.6" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M9 3.6h3v3" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')
