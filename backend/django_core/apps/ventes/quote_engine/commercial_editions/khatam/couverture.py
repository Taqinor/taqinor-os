# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Khatam — PAGE 1 : la couverture ACTUELLE (``commercial/cover.py``),
dans le même ordre et la même grammaire (héros marine, tuiles, note
autoconsommation, investissement, énergie mois par mois, prochaines étapes),
avec la touche marocaine et le style d'écriture :

* héros marine tramé d'une étoile khatam, filet et frise or ; la fenêtre en
  arc outrepassé n'apparaît qu'avec une photo DU SITE servie (``roof_photo``),
  jamais une photo de stock ;
* titre et chiffres en Fraunces 600, texte en IBM Plex Sans, chiffres
  tabulaires ; aucun arabe (fondateur 30/10) ;
* tuiles à filet or (rayon 6 px, plus de pastilles), économie en vert
  zellige ; investissement sur bloc marine tramé à double filet or.
Classes ``kh1-``.
"""
from .. import commun, donnees, graphiques
from ...figures import ancre


def _txt_b64(v) -> str:
    """Le base64 d'une photo servie (data-URI ou brut), '' sinon."""
    s = str(v or "").strip()
    if "," in s[:40] and s.startswith("data:"):
        s = s.split(",", 1)[1]
    return s if len(s) > 200 else ""


def build(ctx, m, j):
    d, p = m["d"], "kh"
    fmt = m["fmt"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    c, inv, cl, cat = m["chiffres"], m["invest"], m["client"], m["categorie"]
    # Fondateur 30/10 : aucune information étrangère au dossier — la photo
    # n'est que celle du site quand le devis la sert, jamais la photothèque.
    photo = _txt_b64(d.get("roof_photo"))

    # ── Héros ─────────────────────────────────────────────────────────────
    validite = (L("ci_valable_jusqu", "Valable jusqu&#8217;au {date}", date=m["valid_until"])
                if m["valid_until"] else "")
    corrections = "".join(f'<div class="kh1-hd">{x}</div>' for x in m["marques_correction"])
    pill = f'<div class="kh1-pill">{validite}</div>' if validite else ""
    kicker = (f'{cat["label"]} &nbsp;·&nbsp; ' if cat["label"] else "") + \
        L("ci_kicker_autoconso_commerciale", "Autoconsommation solaire commerciale")
    titre = donnees.ci_couverture.titre_projet(d, "com", c["kwc"], cl["nom"])
    ligne_client = donnees.ci_couverture.ligne_client(d, "com", cl["nom"], cl["meta"], "kh1")
    arc = ""
    if photo:
        arc = commun.fenetre_arc(photo, j["hero_bg"], j["or"], left_mm=20 if m["rtl"] else 138, top_mm=9,
                                 largeur_mm=50, hauteur_mm=70)
        arc += (f'<div style="position:absolute;left:{20 if m["rtl"] else 138}mm;top:80.5mm;width:50mm;'
                f'font-size:6.6pt;color:{j["on_hero_2"]};text-align:center;">'
                + L("ci_realisation", "Réalisation {marque}", marque=commun.esc(m["brand"])) + '</div>')

    # ── Tuiles (la même sélection que le devis actuel) ─────────────────────
    def tuile(val, unite, lib, a="", sous="", vert=False):
        # Fraunces rend l'espace fine insécable (U+202F) quasi invisible :
        # l'insécable ordinaire sur les grands chiffres (critique 29/10).
        val = str(val).replace("\u202f", "\u00a0")
        return (f'<td class="kh1-kpi"><div class="kh1-kv{" vert" if vert else ""}">{val}'
                f'<span class="kh1-ku">{unite}</span></div>{a}<div class="kh1-kl">{lib}</div>'
                + (f'<div class="kh1-ks">{sous}</div>' if sous else "") + '</td>')
    gap = '<td class="kh1-kgap"></td>'
    cellules = []
    if not m["deux_options"]:
        cellules.append(tuile(c["kwc"], L("res_unite_kwc", "&nbsp;kWc"), L("ci_puissance_crete", "Puissance crête"),
                              ancre("puissance_kwc", c["kwc"])))
    if c["production"] is not None:
        cellules.append(tuile(c["production"], L("ci_unite_kwh_an", "&nbsp;kWh/an"),
                              L("ci_production_annuelle", "Production annuelle"),
                              ancre("production_annuelle_kwh", c["production"])))
    if c["autoconso"] is not None:
        cellules.append(tuile(c["autoconso"], "&nbsp;%", L("ci_autoconsommation", "Autoconsommation"),
                              ancre("autoconsommation_pct", c["autoconso"]), c["definitions"].get("autoconso") or ""))
    if c["couverture"] is not None and not m["deux_options"]:
        cellules.append(tuile(c["couverture"], "&nbsp;%", L("ci_part_conso_couverte", "Part de votre consommation couverte"),
                              ancre("couverture_pct", c["couverture"])))
    if c["co2_t"]:
        cellules.append(tuile(f'≈&#160;{c["co2_t"]}', "&nbsp;t", L("ci_co2_evite", "CO₂ évité / an"), "", c["co2_facteur"]))
    argent = []
    if not m["deux_options"]:
        if c["economies"] is not None:
            sous = c["economies_ttc"] or ""
            if c["postes_hors_total"]:
                sous = L("ci_retour_prix_complet", "retour calculé sur le prix complet, après la visite") + (f" · {sous}" if sous else "")
            lib = (L("ci_economies_estimees", "Économies estimées / an")
                   + (f' ({c["economies_base"]})' if c["economies_base"] else ""))
            argent.append(tuile(c["economies"], "&nbsp;MAD", lib, ancre("economie_annuelle", c["economies"]), sous, vert=True))
        if c["payback"]:
            argent.append(tuile(c["payback"], c["payback_unite"],
                                L("ci_retour_estime_base", "Retour estimé ({base})", base=c["payback_base"]),
                                ancre("payback_ans", c["payback"])))
        elif c["motif_investissement"] and c["economies"] is not None:
            argent.append(tuile(f'<span style="font-size:8.5pt;">{c["motif_investissement"]}</span>', "",
                                L("ci_retour_estime", "Retour estimé")))
    kpis = f'<table class="kh1-kpirow"><tr>{gap.join(cellules)}</tr></table>' if cellules else ""
    kpis_argent = (f'<table class="kh1-kpirow" style="margin-top:3mm;"><tr>{gap.join(argent)}</tr></table>'
                   if argent else "")
    methode = "".join(f'<div>{t}</div>' for t in m["methode"])
    if c["motif_non_chiffre"]:
        methode += f'<div>{c["motif_non_chiffre"]}</div>'
    bandeau_txt = donnees.bandeau_reserve(d, "kh1")
    reserve = f'<div class="kh1-reserve">{bandeau_txt}</div>' if bandeau_txt else ""
    note = (L("ci_note_autoconso_commercial",
              "L'installation vise l'<b>autoconsommation</b> : la valeur porte "
              "d'abord sur\n      la consommation de <b>journée</b> de votre "
              "établissement.") + " " + (c["note_pointe"] or ""))

    # ── Investissement : bloc marine tramé à double filet (touche Signature) ─
    if m["deux_options"]:
        from ...ci import options_cote
        inv_html = ('<div class="kh1-opts">'
                    + options_cote.cartes_options(d, "com", "kh1", fmt, m["fmt_mad"], d.get("_invest_ttc") or 0)
                    + '</div>')
    else:
        inv_html = (f'<div class="kh1-inv"><div class="kh1-inv-in"><div class="kh-row">'
                    f'<div class="kh-col" style="vertical-align:middle;">'
                    f'<div class="kh1-invl">{inv["titre"]}</div>'
                    + (f'<div class="kh1-invn">{inv["secondaire"]}' + (f' · {inv["note"]}' if inv["note"] else "") + '</div>'
                       if inv["secondaire"] else "")
                    + f'</div><div class="kh-col" style="text-align:right;vertical-align:middle;white-space:nowrap;width:46%;">'
                    f'<span class="kh1-invv">{str(inv["montant"]).replace(chr(0x202F), chr(0xA0))}</span>'
                    f'<span class="kh1-invu">&nbsp;MAD{("&nbsp;" + inv["unite"]) if inv["unite"] else ""}</span>{inv["ancre"]}'
                    f'</div></div></div></div>')

    # ── Énergie mois par mois + prochaines étapes (comme aujourd'hui) ──────
    chart = ""
    if m["energie"]:
        plafond = max(max(x["consommation_kwh"], x["production_kwh"]) for x in m["energie"])
        svg = graphiques.barres_mensuelles(
            m["energie"], (j["bar_conso"], j["accent"], j["or"], j["line"], j["muted"]), "IBM Plex Sans",
            list("JFMAMJJASOND") if m["langue"] != "ar" else [str(i) for i in range(1, 13)],
            f'{fmt(round(plafond))} kWh', 118, 46,
            legende=(L("ci_legende_conso", "Votre consommation"), L("ci_legende_autoconso", "Production autoconsommée"),
                     L("ci_legende_surplus", "Surplus non consommé sur place")), contour=j["ink"])
        chart = (f'<div class="kh-h3">{L("ci_energie_mois_titre_court", "Votre énergie mois par mois")}</div>'
                 f'<div style="margin-top:1.5mm;">{svg}</div>'
                 f'<div class="kh-cap">{L("ci_energie_mois_legende", "kWh par mois : votre consommation et la production estimée de la centrale, calculées heure par heure.")}</div>')
    uri, lien = m["qr"]
    etapes = "".join(f'<div style="margin-top:2px;"><span class="kh1-n">{i}</span>&#160;{t}</div>'
                     for i, t in enumerate(m["etapes"], 1))
    qr_html = (f'<div style="margin-top:3.5mm;"><img src="{uri}" style="width:18mm;height:18mm;display:block;" alt="QR">'
               f'<div class="kh-cap">{L("ci_proposition_en_ligne", "Votre proposition en ligne")} · {commun.esc(lien)}</div></div>' if uri else "")
    bas = (f'<table class="kh1-bas"><tr><td style="width:120mm;vertical-align:top;">{chart}</td>'
           f'<td class="kh1-bas-d"><div class="kh-h3">{L("ci_prochaines_etapes", "Prochaines étapes")}</div>'
           f'<div style="margin-top:1.5mm;font-size:8.2pt;">{etapes}</div>{qr_html}</td></tr></table>')

    cote, autre = ("right", "left") if m["rtl"] else ("left", "right")
    css = f"""
<style>
.kh1-root{{padding:0;}}
.kh1-hero{{position:relative;min-height:86mm;background:{j['hero_bg']};{commun.css_motif(j['motif_11'], 14)}
  padding:9mm 14mm 7mm 14mm;color:{j['on_hero']};border-bottom:1pt solid {j['or']};}}
.kh1-galon{{height:5mm;{commun.css_motif(j['galon'], 5, '1.1', 'repeat-x')}border-bottom:0.4pt solid {j['or']};}}
.kh1-htop{{display:table;{('margin-left:60mm;width:122mm' if m['rtl'] else 'width:116mm') if photo else 'width:100%'};}}
.kh1-hlogo{{display:table-cell;vertical-align:middle;}}
.kh1-hmeta{{display:table-cell;vertical-align:middle;text-align:right;}}
.kh1-rl{{font-size:6.5pt;letter-spacing:.14em;text-transform:uppercase;color:{j['or_texte']};font-weight:500;}}
.kh1-rv{{font-size:12pt;font-weight:600;letter-spacing:.02em;}}
.kh1-hd{{font-size:7.6pt;color:{j['on_hero_2']};margin-top:2px;}}
.kh1-pill{{display:inline-block;margin-top:5px;background:{j['or']};color:{j['hero_bg']};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:600;}}
.kh1-hbody{{margin-top:6mm;{('margin-left:60mm' if m['rtl'] else 'max-width:116mm') if photo else 'max-width:150mm'};}}
.kh1-kicker{{font-size:7.2pt;letter-spacing:.12em;text-transform:uppercase;color:{j['or_texte']};font-weight:600;line-height:1.5;}}
.kh1-catrow{{display:table;margin-top:2mm;}}
.kh1-caticon{{display:table-cell;vertical-align:top;padding-{autre}:3.5mm;padding-top:1mm;color:{j['or']};}}
.kh1-caticon svg{{display:block;width:20pt;height:20pt;}}
.kh1-catlab{{display:table-cell;vertical-align:top;}}
.kh1-title{{font-family:{j['display']};font-weight:600;font-size:21pt;line-height:1.12;letter-spacing:-.01em;}}
.kh1-acc{{font-size:10pt;color:{j['on_hero_2']};margin-top:3mm;line-height:1.45;}}
.kh1-client{{padding:5mm 14mm 0 14mm;font-size:8.5pt;color:{j['muted']};}}
.kh1-client b{{color:{j['ink']};font-weight:600;}}
.kh1-wrap{{padding:4mm 14mm 0 14mm;}}
.kh1-reserve{{margin-bottom:4mm;border:0.5pt solid {j['or']};border-{cote}:3px solid {j['or']};border-radius:6px;
  background:{j['ochre_soft']};padding:6px 12px;font-size:8.4pt;font-weight:600;color:{j['ink']};}}
.kh1-kpirow{{display:table;width:100%;border-spacing:0;table-layout:fixed;}}
.kh1-kpi{{display:table-cell;vertical-align:top;border:0.5pt solid {j['line']};border-{cote}:3px solid {j['or']};
  border-radius:6px;padding:8px 12px;background:#fff;}}
.kh1-kgap{{display:table-cell;width:9px;}}
.kh1-kv{{font-family:{j['display']};font-weight:600;font-size:18pt;color:{j['hero_bg']};line-height:1;letter-spacing:-.01em;white-space:nowrap;}}
.kh1-kv.vert{{color:{j['accent']};}}
.kh1-ku{{font-family:{j['sans']};font-size:8.5pt;font-weight:500;color:{j['muted']};letter-spacing:0;}}
.kh1-kl{{font-size:7.2pt;color:{j['muted']};margin-top:3px;letter-spacing:.2px;line-height:1.35;}}
.kh1-ks{{font-size:6.4pt;color:{j['muted']};margin-top:1px;line-height:1.3;}}
.kh1-mtsrc{{margin-top:5px;font-size:6.9pt;color:{j['muted']};line-height:1.4;}}
.kh1-note{{margin-top:3.5mm;border-{cote}:3px solid {j['accent']};border-radius:{"6px 0 0 6px" if m["rtl"] else "0 6px 6px 0"};background:{j['data_soft']};
  padding:8px 12px;font-size:8.4pt;color:{j['ink']};line-height:1.45;}}
.kh1-note b{{color:{j['hero_bg']};font-weight:600;}}
.kh1-inv{{margin-top:4mm;background:{j['hero_bg']};{commun.css_motif(j['motif_8'], 10)}border-top:0.8pt solid {j['or']};
  padding:1.2mm;color:{j['on_hero']};border-radius:2px;}}
.kh1-inv-in{{border:0.3pt solid {j['or']};padding:4mm 6mm;}}
.kh1-invl{{font-size:9pt;font-weight:500;}}
.kh1-invar{{font-size:8pt;color:{j['on_hero_2']};margin-top:1px;text-align:left;}}
.kh1-invn{{font-size:7.4pt;color:{j['on_hero_2']};margin-top:2px;}}
.kh1-invv{{font-family:{j['display']};font-weight:600;font-size:24pt;letter-spacing:-.01em;line-height:1;}}
.kh1-invu{{font-size:8.5pt;font-weight:600;color:{j['or_texte']};}}
.kh1-opts{{margin-top:4mm;}}
.kh1-bas{{width:100%;border-collapse:collapse;margin-top:4mm;}}
.kh1-bas td{{vertical-align:top;padding:0;}}
.kh1-bas-d{{padding-left:8mm !important;padding-top:1mm !important;}}
.kh1-n{{font-family:{j['display']};font-weight:600;font-size:12pt;color:{j['laiton']};}}
{__import__('apps.ventes.quote_engine.ci.options_cote', fromlist=['css_options']).css_options('kh1', (j['line'], j['wash'], j['muted'], j['accent'], j['ink'], j['or']), 10) if m['deux_options'] else ''}
</style>"""
    return f"""{css}
<div class="kh-root kh1-root" style="padding:0;">
  <div class="kh1-hero">
    <div class="kh1-htop">
      <div class="kh1-hlogo">{commun.logo(ctx, "couverture", sombre=True)}</div>
      <div class="kh1-hmeta">
        <div class="kh1-rl">{L("ci_ref_devis", "Réf. devis")}</div>
        <div class="kh1-rv">{m["ref"]}</div>
        <div class="kh1-hd">{m["date"]}</div>
        {corrections}{pill}
      </div>
    </div>
    <div class="kh1-hbody">
      <div class="kh1-kicker">{kicker}</div>
      <div class="kh1-catrow">
        <div class="kh1-caticon">{cat["icon"]}</div>
        <div class="kh1-catlab"><div class="kh1-title">{titre}</div></div>
      </div>
      <div class="kh1-acc">{cat["accroche"]}</div>
    </div>
    {arc}
  </div>
  <div class="kh1-galon"></div>
  <div class="kh1-client">{ligne_client}</div>
  <div class="kh1-wrap">
    {reserve}
    {kpis}{kpis_argent}
    <div class="kh1-mtsrc">{methode}</div>
    <div class="kh1-note">{note}</div>
    {inv_html}
    {bas}
  </div>
</div>"""
