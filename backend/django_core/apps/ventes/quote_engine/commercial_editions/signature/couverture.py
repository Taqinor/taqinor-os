# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Signature — PAGE 1 : la couverture (synthèse §3, page 1).

Bandeau marine tramé khatam (0-118 mm) : logo, référence, kicker or, titre
Fraunces 400 30 pt scindé, accroche en italique, ligne client, réserve ;
fenêtre en arc sur la photo réelle. Galon or. Héros (économie de l'année 1
en Fraunces 400 60 pt royal sur double ligne de base) et facture
avant/après. Registre de quatre faits. Méthode et note sur la pointe. Bloc
prix marine tramé à double filet. Prochaines étapes et QR. Classes ``sg1-``.
"""
from .. import commun, donnees, graphiques
from ...figures import ancre
from ...residential import theme


def build(ctx, m, j):
    d, p = m["d"], "sg"
    fmt = m["fmt"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    c, inv, cl, cat = m["chiffres"], m["invest"], m["client"], m["categorie"]
    ar = donnees.ar
    photo = theme.hero_image_b64(d.get("com_kwc"), "commercial")

    # ── Bandeau ───────────────────────────────────────────────────────────
    validite = (L("ci_valable_jusqu", "Valable jusqu&#8217;au {date}", date=m["valid_until"])
                if m["valid_until"] else "")
    corrections = "".join(f'<div class="sg1-hd">{x}</div>' for x in m["marques_correction"])
    ar_ref = ar("ci_ref_devis")
    kicker = (f'{cat["label"]} &nbsp;·&nbsp; ' if cat["label"] else "") + \
        L("ci_kicker_autoconso_commerciale", "Autoconsommation solaire commerciale")
    titre_brut = donnees.ci_couverture.titre_projet(d, "com", c["kwc"], cl["nom"])
    titre = commun.titre_scinde(titre_brut, m["langue"], j["on_hero_3"], 20, 30, 25, 24)
    taille_titre = 30
    ligne_client = donnees.ci_couverture.ligne_client(d, "com", cl["nom"], cl["meta"], "sg1")
    bandeau_txt = donnees.bandeau_reserve(d, "sg1")
    reserve = f'<div class="sg1-reserve">{bandeau_txt}</div>' if bandeau_txt else ""
    arc = commun.fenetre_arc(photo, j["hero_bg"], j["or"])

    # ── Héros ─────────────────────────────────────────────────────────────
    if m["deux_options"]:
        hero_lab = L("ci_production_annuelle", "Production annuelle")
        hero_ar = ar("ci_production_annuelle")
        hero_val = c["production"] or "—"
        hero_unit = L("ci_unite_kwh_an", "&nbsp;kWh/an")
        hero_ancre = ancre("production_annuelle_kwh", c["production"]) if c["production"] else ""
        hero_cap = ""
    elif c["economies"] is not None:
        hero_lab = (L("ci_economies_estimees", "Économies estimées / an")
                    + (f' ({c["economies_base"]})' if c["economies_base"] else ""))
        hero_ar = ar("ci_economies_estimees")
        hero_val, hero_unit = c["economies"], "&nbsp;MAD"
        hero_ancre = ancre("economie_annuelle", c["economies"])
        hero_cap = c["economies_ttc"] or ""
        if c["postes_hors_total"]:
            hero_cap = (L("ci_retour_prix_complet", "retour calculé sur le prix complet, après la visite")
                        + (f" · {hero_cap}" if hero_cap else ""))
    else:
        hero_lab = L("ci_puissance_crete", "Puissance crête")
        hero_ar = ar("ci_puissance_crete")
        hero_val, hero_unit = c["kwc"], L("res_unite_kwc", "&nbsp;kWc")
        hero_ancre = ancre("puissance_kwc", c["kwc"])
        hero_cap = c["motif_non_chiffre"] or c["motif_investissement"] or ""

    droite = ""
    if m["facture"] and not m["deux_options"] and c["part_facture_pct"]:
        f = m["facture"]
        svg = graphiques.facture_avant_apres(
            f["avant_num"], f["apres_num"],
            (L("ci_facture_sans_solaire", "Sans solaire"), L("ci_facture_avec_solaire", "Avec solaire"),
             "", "", f'−{c["part_facture_pct"]}&#160;%'),
            (j["bar_sans"], j["accent"], j["line"], j["ink"]), "IBM Plex Sans", 70, 26)
        droite = (f'<div class="sg-kicker">{L("ci_facture_energie_an1", "Votre facture d&#8217;énergie, année 1")}'
                  f' ({f["unite"]})</div><div style="margin-top:3mm;">{svg}</div>')
    elif c["couverture"] is not None and not m["deux_options"]:
        droite = (f'<div class="sg-kicker">{L("ci_part_conso_couverte", "Part de votre consommation couverte")}</div>'
                  f'<div class="sg1-fv" style="font-size:22pt;margin-top:2mm;">{c["couverture"]}'
                  f'<span class="sg-ru">&nbsp;%</span></div>{ancre("couverture_pct", c["couverture"])}'
                  f'<div style="margin-top:2mm;">{graphiques.jauge(float(c["couverture"]), (j["accent"], j["data_soft"]), 60, 3)}</div>')
    elif c["production"] is not None and not m["deux_options"]:
        droite = (f'<div class="sg-kicker">{L("ci_production_annuelle", "Production annuelle")}</div>'
                  f'<div class="sg1-fv" style="font-size:22pt;margin-top:2mm;">{c["production"]}'
                  f'<span class="sg-ru">{L("ci_unite_kwh_an", "&nbsp;kWh/an")}</span></div>')

    # ── Registre des faits ────────────────────────────────────────────────
    faits = []
    if not m["deux_options"]:
        if c["payback"]:
            faits.append((L("ci_retour_estime_base", "Retour estimé ({base})", base=c["payback_base"]),
                          f'{c["payback"]}<span class="sg-ru">{c["payback_unite"]}</span>',
                          ancre("payback_ans", c["payback"]), ""))
        elif c["motif_investissement"] and c["economies"] is not None:
            faits.append((L("ci_retour_estime", "Retour estimé"),
                          f'<span style="font-size:8.5pt;">{c["motif_investissement"]}</span>', "", ""))
        if c["couverture"] is not None and m["facture"]:
            faits.append((L("ci_part_conso_couverte", "Part de votre consommation couverte"),
                          f'{c["couverture"]}<span class="sg-ru">&nbsp;%</span>',
                          ancre("couverture_pct", c["couverture"]),
                          graphiques.jauge(float(c["couverture"]), (j["accent"], j["data_soft"]), 30, 2)))
    if c["autoconso"] is not None:
        faits.append((L("ci_autoconsommation", "Autoconsommation"),
                      f'{c["autoconso"]}<span class="sg-ru">&nbsp;%</span>',
                      ancre("autoconsommation_pct", c["autoconso"]), ""))
    if c["production"] is not None and (c["economies"] is not None or m["facture"]) and not m["deux_options"]:
        faits.append((L("ci_production_annuelle", "Production annuelle"),
                      f'{c["production"]}<span class="sg-ru">{L("ci_unite_kwh_an", "&nbsp;kWh/an")}</span>',
                      ancre("production_annuelle_kwh", c["production"]), ""))
    if c["co2_t"]:
        faits.append((L("ci_co2_evite", "CO₂ évité / an"), f'≈&#160;{c["co2_t"]}<span class="sg-ru">&nbsp;t</span>',
                      "", ""))
    faits = faits[:4]
    faits_html = ""
    for lib, val, a, jauge in faits:
        jauge_html = f'<div style="margin-top:3px;">{jauge}</div>' if jauge else ""
        faits_html += (f'<div class="sg-reg-c"><div class="sg-rv">{val}</div>{a}'
                       f'<div class="sg-lab">{lib}</div>{jauge_html}</div>')

    methode = "".join(f'<div>{t}</div>' for t in m["methode"])
    pointe = (L("ci_note_autoconso_commercial",
                "L'installation vise l'<b>autoconsommation</b> : la valeur porte "
                "d'abord sur\n      la consommation de <b>journée</b> de votre "
                "établissement.") + " " + (c["note_pointe"] or ""))

    # ── Bloc prix ─────────────────────────────────────────────────────────
    if m["deux_options"]:
        from ...ci import options_cote
        prix = ('<div class="sg1-opts">'
                + options_cote.cartes_options(d, "com", "sg1", fmt, m["fmt_mad"], d.get("_invest_ttc") or 0)
                + '</div>')
    else:
        ar_inv = ar(inv.get("cle_titre") or "")
        prix = (f'<div class="sg1-prix"><div class="sg1-prix-in"><div class="sg-row">'
                f'<div class="sg-col" style="vertical-align:middle;">'
                f'<div class="sg1-pl">{inv["titre"]}</div>'
                + (f'<div class="sg-ar sg1-par">{ar_inv}</div>' if ar_inv else "")
                + (f'<div class="sg1-ps">{inv["secondaire"]}' + (f' · {inv["note"]}' if inv["note"] else "") + '</div>'
                   if inv["secondaire"] else "")
                + f'</div><div class="sg-col" style="text-align:right;vertical-align:middle;white-space:nowrap;width:46%;">'
                f'<span class="sg1-pv">{inv["montant"]}</span>'
                f'<span class="sg1-pu">&nbsp;MAD{("&nbsp;" + inv["unite"]) if inv["unite"] else ""}</span>{inv["ancre"]}'
                f'</div></div></div></div>')

    # ── Étapes + QR ───────────────────────────────────────────────────────
    uri, lien = m["qr"]
    etapes = " &nbsp;·&nbsp; ".join(
        f'<span class="sg1-n">{i}</span>&#160;{t}' for i, t in enumerate(m["etapes"], 1))
    qr_html = (f'<div class="sg-col" style="width:20mm;text-align:right;vertical-align:middle;">'
               f'<img src="{uri}" style="width:18mm;height:18mm;" alt="QR"></div>' if uri else "")
    qr_cap = (f'<div class="sg-cap">{L("ci_proposition_en_ligne", "Votre proposition en ligne")} · {commun.esc(lien)}</div>'
              if uri else "")
    bas = (f'<div class="sg-row sg1-bas"><div class="sg-col" style="vertical-align:middle;">'
           + commun.kicker(L("ci_prochaines_etapes", "Prochaines étapes"), j, p)
           + f'<div style="margin-top:2mm;font-size:8.6pt;">{etapes}</div>{qr_cap}</div>{qr_html}</div>')

    css = f"""
<style>
.sg1-root{{padding:0;}}
.sg1-bandeau{{position:relative;min-height:118mm;background:{j['hero_bg']};{commun.css_motif(j['motif_11'], 14)}
  color:{j['on_hero']};padding:12mm {j['marge']} 8mm {j['marge_g']};}}
.sg1-top{{display:table;width:100%;}}
.sg1-tl{{display:table-cell;vertical-align:top;}}
.sg1-tr{{display:table-cell;vertical-align:top;text-align:right;}}
.sg1-rl{{font-size:6.6pt;letter-spacing:.14em;text-transform:uppercase;color:{j['or_texte']};font-weight:500;}}
.sg1-rl .sg-ar{{font-size:7.6pt;color:{j['on_hero_2']};text-transform:none;letter-spacing:0;margin-left:6px;}}
.sg1-rv{{font-size:12pt;font-weight:600;letter-spacing:.02em;margin-top:1px;}}
.sg1-hd{{font-size:7.4pt;color:{j['on_hero_2']};margin-top:1px;}}
.sg1-filet{{margin-top:4mm;width:98mm;border-top:0.5pt solid {j['or']};position:relative;}}
.sg1-filet svg{{position:absolute;left:0;top:-1mm;}}
.sg1-kick{{margin-top:4mm;font-size:7pt;letter-spacing:.16em;text-transform:uppercase;color:{j['or_texte']};font-weight:500;}}
.sg1-titre{{font-family:{j['display']};font-weight:400;font-size:{taille_titre}pt;line-height:1.08;letter-spacing:-.01em;
  margin-top:2.5mm;max-width:108mm;color:{j['on_hero']};}}
.sg1-acc{{font-family:{j['display']};font-weight:300;font-style:italic;font-size:10.5pt;line-height:1.35;color:{j['on_hero_2']};
  margin-top:3mm;max-width:104mm;}}
.sg1-client{{margin-top:3mm;font-size:7.8pt;color:{j['on_hero_3']};max-width:108mm;}}
.sg1-client b{{color:{j['on_hero']};font-weight:600;}}
.sg1-reserve{{margin-top:4mm;padding:3px 0 3px 8px;border-left:2pt solid {j['or']};font-size:8pt;font-weight:500;color:{j['on_hero']};max-width:108mm;}}
.sg1-galon{{height:8mm;border-top:0.8pt solid {j['or']};}}
.sg1-galon-in{{height:6mm;margin-top:0.6mm;{commun.css_motif(j['galon'], 6, '.9', 'repeat-x')}border-bottom:0.4pt solid {j['or']};}}
.sg1-corps{{padding:6mm {j['marge']} 0 {j['marge_g']};}}
.sg1-hero{{font-family:{j['display']};font-weight:400;font-size:60pt;line-height:1;letter-spacing:-.01em;color:{j['accent']};margin-top:2mm;}}
.sg1-hunit{{font-family:{j['sans']};font-size:11pt;font-weight:600;letter-spacing:0;color:{j['ink']};}}
.sg1-base{{width:92mm;margin-top:2mm;border-top:0.8pt solid {j['or']};}}
.sg1-base div{{margin-top:1mm;border-top:0.3pt solid {j['ink']};}}
.sg1-fv{{font-family:{j['display']};font-weight:400;font-size:20pt;line-height:1;letter-spacing:-.01em;}}
.sg1-reg{{margin-top:4mm;}}
.sg1-meth{{margin-top:3mm;font-size:6.9pt;color:{j['muted']};line-height:1.45;}}
.sg1-pointe{{margin-top:2mm;font-size:8.3pt;line-height:1.45;max-width:160mm;}}
.sg1-pointe b{{font-weight:600;}}
.sg1-prix{{margin-top:4mm;background:{j['hero_bg']};{commun.css_motif(j['motif_8'], 10)}border-top:0.8pt solid {j['or']};padding:1.2mm;color:{j['on_hero']};}}
.sg1-prix-in{{border:0.3pt solid {j['or']};padding:4.5mm 6mm;}}
.sg1-pl{{font-size:9.5pt;font-weight:500;}}
.sg1-par{{font-size:8pt;color:{j['on_hero_2']};margin-top:1px;text-align:left;}}
.sg1-ps{{font-size:7.6pt;color:{j['on_hero_2']};margin-top:2px;}}
.sg1-pv{{font-family:{j['display']};font-weight:400;font-size:28pt;letter-spacing:-.01em;line-height:1;}}
.sg1-pu{{font-size:8.5pt;font-weight:600;color:{j['or_texte']};}}
.sg1-opts{{margin-top:4mm;}}
.sg1-bas{{margin-top:4mm;}}
.sg1-n{{font-family:{j['display']};font-weight:400;font-size:13pt;color:{j['laiton']};}}
{__import__('apps.ventes.quote_engine.ci.options_cote', fromlist=['css_options']).css_options('sg1', (j['ink'], j['wash'], j['muted'], j['accent'], j['ink'], j['or']), 10) if m['deux_options'] else ''}
</style>"""
    return f"""{css}
<div class="sg-root sg1-root" style="padding:0;">
  <div class="sg1-bandeau">
    <div class="sg1-top">
      <div class="sg1-tl">{commun.logo(ctx, 34, sombre=True)}</div>
      <div class="sg1-tr"><div class="sg1-rl">{L("ci_ref_devis", "Réf. devis")}{f'<span class="sg-ar">{ar_ref}</span>' if ar_ref else ''}</div>
        <div class="sg1-rv">{m["ref"]}</div>
        <div class="sg1-hd">{m["date"]}{(" &nbsp;·&nbsp; " + validite) if validite else ""}</div>{corrections}</div>
    </div>
    <div class="sg1-filet">{commun.losange(j["or"], 1.8, 0)}</div>
    <div class="sg1-kick">{kicker}</div>
    <div class="sg1-titre">{titre}</div>
    <div class="sg1-acc">{cat["accroche"]}</div>
    <div class="sg1-client">{ligne_client}</div>
    {reserve}
    {arc}
  </div>
  <div class="sg1-galon"><div class="sg1-galon-in"></div></div>
  <div class="sg1-corps">
    <div class="sg-row">
      <div class="sg-col" style="width:96mm;vertical-align:bottom;">
        <div class="sg-kicker">{hero_lab}</div>
        {f'<div class="sg-ar" style="font-size:8pt;color:{j["muted"]};text-align:left;">{hero_ar}</div>' if hero_ar else ''}
        <div class="sg1-hero">{hero_val}<span class="sg1-hunit">{hero_unit}</span></div>{hero_ancre}
        <div class="sg1-base"><div></div></div>
        <div class="sg-cap" style="margin-top:2px;">{hero_cap}</div>
      </div>
      <div class="sg-gap"></div>
      <div class="sg-col" style="vertical-align:bottom;">{droite}</div>
    </div>
    {f'<div class="sg-reg sg1-reg">{faits_html}</div>' if faits_html else ''}
    <div class="sg1-meth">{methode}</div>
    <div class="sg1-pointe">{pointe}</div>
    {prix}
    {bas}
  </div>
</div>"""
