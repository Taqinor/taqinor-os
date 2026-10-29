# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Signature — PAGE 1 : la couverture-affiche.

Photo réelle en bandeau haut (voile plat), le projet en titre, UN
chiffre-héros (l'économie de l'année 1 servie par ``synthese_ci.argent``),
la facture d'énergie avant / après, quatre faits en filets, l'investissement
sur sa propre rangée. Classes ``sg1-``. CSS tables seulement.
"""
from .. import commun, donnees, graphiques
from ...figures import ancre
from ...residential import theme


def build(ctx, m, j):
    d, p = m["d"], "sg"
    fmt = m["fmt"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    c, inv, cl, cat = m["chiffres"], m["invest"], m["client"], m["categorie"]
    photo = theme.hero_image_b64(d.get("com_kwc"), "commercial")
    logo = commun.logo(ctx, 9, sombre=True)

    # ── Bandeau photo + en-tête ───────────────────────────────────────────
    corrections = "".join(f'<div class="sg1-hd">{x}</div>'
                          for x in m["marques_correction"])
    validite = (L("ci_valable_jusqu", "Valable jusqu&#8217;au {date}",
                  date=m["valid_until"]) if m["valid_until"] else "")
    entete = (
        f'<div class="sg1-photo" style="background-image:url(data:image/jpeg;base64,{photo});"></div>'
        f'<div class="sg1-voile"></div>'
        f'<div class="sg1-entete"><div class="sg1-elogo">{logo}</div>'
        f'<div class="sg1-emeta"><div class="sg1-rl">{L("ci_ref_devis", "Réf. devis")}</div>'
        f'<div class="sg1-rv">{m["ref"]}</div><div class="sg1-hd">{m["date"]}'
        + (f' &nbsp;·&nbsp; {validite}' if validite else '') + f'</div>{corrections}</div></div>')

    # ── Titre du projet ───────────────────────────────────────────────────
    kicker = (f'{cat["label"]} &nbsp;·&nbsp; ' if cat["label"] else "") + \
        L("ci_kicker_autoconso_commerciale", "Autoconsommation solaire commerciale")
    titre = donnees.ci_couverture.titre_projet(d, "com", c["kwc"], cl["nom"])
    # Le titre servi, scindé pour l'œil sur son tiret : la centrale sur une
    # ligne (teinte retenue), le client sur la suivante — même chaîne.
    if " — " in titre and m["langue"] != "ar":
        avant, apres = titre.split(" — ", 1)
        titre = (f'<span style="color:{j["muted"]};">{avant}</span><br>{apres}')
    ligne_client = donnees.ci_couverture.ligne_client(d, "com", cl["nom"], cl["meta"], "sg1")

    # ── Chiffre-héros ─────────────────────────────────────────────────────
    bandeau = donnees.bandeau_reserve(d, "sg1")
    sous_reserve = f'<div class="sg1-reserve">{bandeau}</div>' if bandeau else ""
    # A5 (CPDF3) — devis à deux options : chaque carte dit puissance, argent
    # et part couverte ; la couverture garde production et autoconsommation.
    if m["deux_options"]:
        hero_kicker = L("ci_production_annuelle", "Production annuelle")
        hero = (f'<div class="sg1-hero">{c["production"] or "—"}<span class="sg1-hunit">'
                + L("ci_unite_kwh_an", "&nbsp;kWh/an") + '</span></div>'
                + (ancre("production_annuelle_kwh", c["production"]) if c["production"] else ""))
        hero_cap = ""
    elif c["economies"] is not None:
        hero_kicker = (L("ci_economies_estimees", "Économies estimées / an")
                       + (f' ({c["economies_base"]})' if c["economies_base"] else ""))
        hero = (f'<div class="sg1-hero">{c["economies"]}'
                f'<span class="sg1-hunit">&nbsp;MAD</span></div>{ancre("economie_annuelle", c["economies"])}')
        hero_cap = c["economies_ttc"] or ""
        if c["postes_hors_total"]:
            # A6 (AMOT86) — postes hors total : le retour n'est pas imprimé,
            # la légende dit sur quel prix il le sera.
            hero_cap = (L("ci_retour_prix_complet", "retour calculé sur le prix "
                          "complet, après la visite") + (f" · {hero_cap}" if hero_cap else ""))
    else:
        hero_kicker = L("ci_puissance_crete", "Puissance crête")
        hero = (f'<div class="sg1-hero">{c["kwc"]}<span class="sg1-hunit">'
                + L("res_unite_kwc", "&nbsp;kWc") + '</span></div>'
                + ancre("puissance_kwc", c["kwc"]))
        hero_cap = c["motif_investissement"] or ""

    # Facture avant / après (servie, un poste) — sinon la jauge de couverture.
    droite = ""
    if m["facture"] and not m["deux_options"] and c["part_facture_pct"]:
        f = m["facture"]
        svg = graphiques.facture_avant_apres(
            f["avant_num"], f["apres_num"],
            (L("ci_facture_sans_solaire", "Sans solaire"),
             L("ci_facture_avec_solaire", "Avec solaire"),
             "", "", f'−{c["part_facture_pct"]}&#160;%'),
            (j["ink"], j["accent"], j["line"], j["ink"]), "IBM Plex Sans", 86, 26)
        droite = (f'<div class="sg-kicker">'
                  + L("ci_facture_energie_an1", "Votre facture d&#8217;énergie, année 1")
                  + f' ({f["unite"]})</div><div style="margin-top:4px;">{svg}</div>')

    # ── Quatre faits ──────────────────────────────────────────────────────
    faits = []
    if m["deux_options"]:
        pass
    elif c["payback"]:
        faits.append((L("ci_retour_estime_base", "Retour estimé ({base})", base=c["payback_base"]),
                      f'{c["payback"]}<span class="sg-unit sg1-fu">{c["payback_unite"]}</span>',
                      ancre("payback_ans", c["payback"]), ""))
    elif c["motif_investissement"] and c["economies"] is not None:
        faits.append((L("ci_retour_estime", "Retour estimé"),
                      f'<span style="font-size:8.5pt;">{c["motif_investissement"]}</span>', "", ""))
    if c["couverture"] is not None and not m["deux_options"]:
        faits.append((L("ci_part_conso_couverte", "Part de votre consommation couverte"),
                      f'{c["couverture"]}<span class="sg-unit sg1-fu">&nbsp;%</span>',
                      ancre("couverture_pct", c["couverture"]),
                      graphiques.jauge(float(c["couverture"]), (j["accent"], j["line_soft"]), 34, 2.2)))
    if c["autoconso"] is not None:
        faits.append((L("ci_autoconsommation", "Autoconsommation"),
                      f'{c["autoconso"]}<span class="sg-unit sg1-fu">&nbsp;%</span>',
                      ancre("autoconsommation_pct", c["autoconso"]), ""))
    if c["production"] is not None:
        faits.append((L("ci_production_annuelle", "Production annuelle"),
                      f'{c["production"]}<span class="sg-unit sg1-fu">{L("ci_unite_kwh_an", "&nbsp;kWh/an")}</span>',
                      ancre("production_annuelle_kwh", c["production"]), ""))
    if c["economies"] is not None and not m["deux_options"]:
        faits.append((L("ci_puissance_crete", "Puissance crête"),
                      f'{c["kwc"]}<span class="sg-unit sg1-fu">{L("res_unite_kwc", "&nbsp;kWc")}</span>',
                      ancre("puissance_kwc", c["kwc"]), ""))
    faits = faits[:4]
    faits_html = ""
    for lib, val, a, jauge in faits:
        jauge_html = f'<div style="margin-top:3px;">{jauge}</div>' if jauge else ""
        faits_html += (f'<div class="sg-col sg1-fait"><div class="sg1-fv">{val}</div>{a}'
                       f'<div class="sg-lab">{lib}</div>{jauge_html}</div>')

    # ── Lignes de méthode, note sur la pointe ─────────────────────────────
    methode = "".join(f'<div>{t}</div>' for t in m["methode"])
    pointe = (L("ci_note_autoconso_commercial",
                "L'installation vise l'<b>autoconsommation</b> : la valeur porte "
                "d'abord sur\n      la consommation de <b>journée</b> de votre "
                "établissement.") + " " + (c["note_pointe"] or ""))
    a_confirmer = ""  # A3 — liste interne, jamais imprimée (fondateur 26/10)

    # ── Investissement ────────────────────────────────────────────────────
    if m["deux_options"]:
        from ...ci import options_cote
        invest_html = options_cote.cartes_options(
            d, "com", "sg1", fmt, m["fmt_mad"], d.get("_invest_ttc") or 0)
    else:
        invest_html = (
            f'<div class="sg-row sg1-inv"><div class="sg-col" style="vertical-align:middle;">'
            f'<div class="sg1-invl">{inv["titre"]}</div>'
            + (f'<div class="sg-cap">{inv["secondaire"]}'
               + (f' · {inv["note"]}' if inv["note"] else "") + '</div>' if inv["secondaire"] else "")
            + f'</div><div class="sg-col" style="text-align:right;vertical-align:middle;white-space:nowrap;">'
            f'<span class="sg1-invv">{inv["montant"]}</span>'
            f'<span class="sg1-invu">&nbsp;MAD{("&nbsp;" + inv["unite"]) if inv["unite"] else ""}</span>{inv["ancre"]}'
            f'</div></div>')

    # ── Prochaines étapes + QR ────────────────────────────────────────────
    uri, lien = m["qr"]
    etapes = " &nbsp;·&nbsp; ".join(
        f'<span class="sg1-n">{i}</span>&#160;{t}' for i, t in enumerate(m["etapes"], 1))
    qr_html = (f'<div class="sg-col" style="width:20mm;text-align:right;">'
               f'<img src="{uri}" style="width:17mm;height:17mm;" alt="QR"></div>' if uri else "")
    qr_cap = (f'<div class="sg-cap">{L("ci_proposition_en_ligne", "Votre proposition en ligne")} · {commun.esc(lien)}</div>'
              if uri else "")
    bas = (f'<div class="sg-row sg1-bas"><div class="sg-col" style="vertical-align:middle;">'
           f'<div class="sg-kicker">{L("ci_prochaines_etapes", "Prochaines étapes")}</div>'
           f'<div style="margin-top:3px;font-size:8.4pt;">{etapes}</div>{qr_cap}</div>{qr_html}</div>')

    css = f"""
<style>
.sg1-photo{{position:absolute;left:0;top:0;width:210mm;height:76mm;
  background-size:cover;background-position:center 42%;}}
.sg1-voile{{position:absolute;left:0;top:0;width:210mm;height:76mm;background:#0B1A2A;opacity:.42;}}
.sg1-entete{{position:absolute;left:{j['marge_g']};right:{j['marge']};top:12mm;display:table;width:172mm;color:#fff;}}
.sg1-elogo{{display:table-cell;vertical-align:top;}}
.sg1-emeta{{display:table-cell;vertical-align:top;text-align:right;}}
.sg1-rl{{font-size:6.6pt;letter-spacing:.14em;text-transform:uppercase;opacity:.8;}}
.sg1-rv{{font-size:11pt;font-weight:600;letter-spacing:.02em;}}
.sg1-hd{{font-size:7.4pt;opacity:.85;margin-top:1px;}}
.sg1-corps{{padding-top:64mm;}}
.sg1-titre{{margin-top:9mm;}}
.sg1-acc{{margin-top:3mm;font-size:9.6pt;color:{j['muted']};max-width:128mm;line-height:1.45;}}
.sg1-client{{margin-top:2.5mm;font-size:7.8pt;color:{j['muted']};}}
.sg1-client b{{color:{j['ink']};font-weight:600;}}
.sg1-reserve{{margin-top:5mm;padding:4px 0 4px 9px;border-left:2pt solid {j['ochre']};
  font-size:8pt;font-weight:500;color:{j['ink']};}}
.sg1-heroblk{{margin-top:7mm;}}
.sg1-hero{{font-family:{j['display']};font-weight:300;font-size:54pt;line-height:1;
  letter-spacing:-.025em;color:{j['accent']};margin-top:3px;}}
.sg1-hunit{{font-family:{j['sans']};font-size:11pt;font-weight:500;letter-spacing:.02em;color:{j['muted']};}}
.sg1-faits{{margin-top:6mm;}}
.sg1-fait{{border-top:0.5pt solid {j['ink']};padding:5px 6mm 0 0;}}
.sg1-fv{{font-family:{j['display']};font-weight:300;font-size:19pt;line-height:1;letter-spacing:-.01em;}}
.sg1-fu{{font-size:7.5pt;color:{j['muted']};}}
.sg1-meth{{margin-top:4mm;font-size:6.9pt;color:{j['muted']};line-height:1.45;}}
.sg1-pointe{{margin-top:3mm;font-size:8.3pt;line-height:1.45;max-width:150mm;}}
.sg1-pointe b{{font-weight:600;}}
.sg1-inv{{border-top:1pt solid {j['ink']};border-bottom:0.5pt solid {j['line']};padding:7px 0;}}
.sg1-socle{{position:absolute;left:{j['marge_g']};right:{j['marge']};bottom:17mm;}}
.sg1-socle-flux{{margin-top:6mm;}}
.sg1-invl{{font-size:9pt;font-weight:500;}}
.sg1-invv{{font-family:{j['display']};font-weight:300;font-size:22pt;letter-spacing:-.015em;}}
.sg1-invu{{font-size:8.5pt;font-weight:500;color:{j['muted']};}}
.sg1-bas{{margin-top:5mm;}}
.sg1-n{{color:{j['accent']};font-weight:600;}}
{__import__('apps.ventes.quote_engine.ci.options_cote', fromlist=['css_options']).css_options('sg1', (j['line'], j['wash'], j['muted'], j['accent'], j['ink'], j['ochre']), 10) if m['deux_options'] else ''}
</style>"""
    return f"""{css}
<div class="sg-root">
  {entete}
  <div class="sg1-corps">
    <div class="sg1-titre">
      <div class="sg-kicker">{kicker}</div>
      <div class="sg-h1" style="margin-top:2mm;">{titre}</div>
      <div class="sg1-acc">{cat["accroche"]}</div>
      <div class="sg1-client">{ligne_client}</div>
    </div>
    {sous_reserve}
    <div class="sg-row sg1-heroblk">
      <div class="sg-col" style="width:50%;vertical-align:bottom;">
        <div class="sg-kicker">{hero_kicker}</div>{hero}
        <div class="sg-cap" style="margin-top:3px;">{hero_cap}</div>
      </div>
      <div class="sg-gap"></div>
      <div class="sg-col" style="vertical-align:bottom;">{droite}</div>
    </div>
    <div class="sg-row sg1-faits">{faits_html}</div>
    <div class="sg1-meth">{methode}</div>
    <div class="sg1-pointe">{pointe}{a_confirmer}</div>
  </div>
  <div class="{'sg1-socle-flux' if m['deux_options'] else 'sg1-socle'}">{invest_html}{bas}</div>
</div>"""
