# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Normale — PAGE 1 : la couverture du devis actuel, mieux composée
(synthèse §4). Bandeau marine tramé 64 mm (logo, référence, kicker, titre
Fraunces 400 24 pt, accroche), filet or, ligne client, réserve, registre de
six faits (économies en royal), méthode, phrase autoconsommation à filet
royal, investissement sur papier, énergie mois par mois avec les prochaines
étapes et le QR. Classes ``no1-``.
"""
from .. import commun, donnees, graphiques
from ...figures import ancre


def build(ctx, m, j):
    d, p = m["d"], "no"
    fmt = m["fmt"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    c, inv, cl, cat = m["chiffres"], m["invest"], m["client"], m["categorie"]
    validite = (L("ci_valable_jusqu", "Valable jusqu&#8217;au {date}", date=m["valid_until"])
                if m["valid_until"] else "")
    corrections = "".join(f'<div class="no1-hd">{x}</div>' for x in m["marques_correction"])
    kicker = (f'{cat["label"]} &nbsp;·&nbsp; ' if cat["label"] else "") + \
        L("ci_kicker_autoconso_commerciale", "Autoconsommation solaire commerciale")
    titre_brut = donnees.ci_couverture.titre_projet(d, "com", c["kwc"], cl["nom"])
    titre = commun.titre_scinde(titre_brut, m["langue"], j["on_hero_3"], 17, 24, 21, 30)
    ligne_client = donnees.ci_couverture.ligne_client(d, "com", cl["nom"], cl["meta"], "no1")
    bandeau_txt = donnees.bandeau_reserve(d, "no1")

    def fait(val, unite, lib, a="", sous="", royal=False):
        return (f'<div class="no-reg-c"><div class="no-rv{" royal" if royal else ""}">{val}'
                f'<span class="no-ru">{unite}</span></div>{a}<div class="no-lab">{lib}</div>'
                + (f'<div class="no-cap" style="font-size:6.9pt;">{sous}</div>' if sous else "") + '</div>')

    r1, r2 = [], []
    if not m["deux_options"]:
        r1.append(fait(c["kwc"], L("res_unite_kwc", "&nbsp;kWc"), L("ci_puissance_crete", "Puissance crête"),
                       ancre("puissance_kwc", c["kwc"])))
    if c["production"] is not None:
        r1.append(fait(c["production"], L("ci_unite_kwh_an", "&nbsp;kWh/an"), L("ci_production_annuelle", "Production annuelle"),
                       ancre("production_annuelle_kwh", c["production"])))
    if c["autoconso"] is not None:
        r1.append(fait(c["autoconso"], "&nbsp;%", L("ci_autoconsommation", "Autoconsommation"),
                       ancre("autoconsommation_pct", c["autoconso"]), c["definitions"].get("autoconso") or ""))
    if not m["deux_options"]:
        if c["couverture"] is not None:
            r2.append(fait(c["couverture"], "&nbsp;%", L("ci_part_conso_couverte", "Part de votre consommation couverte"),
                           ancre("couverture_pct", c["couverture"])))
        if c["economies"] is not None:
            sous = c["economies_ttc"] or ""
            if c["postes_hors_total"]:
                sous = L("ci_retour_prix_complet", "retour calculé sur le prix complet, après la visite") + (f" · {sous}" if sous else "")
            r2.append(fait(c["economies"], "&nbsp;MAD",
                           L("ci_economies_estimees", "Économies estimées / an") + (f' ({c["economies_base"]})' if c["economies_base"] else ""),
                           ancre("economie_annuelle", c["economies"]), sous, royal=True))
        if c["payback"]:
            r2.append(fait(c["payback"], c["payback_unite"], L("ci_retour_estime_base", "Retour estimé ({base})", base=c["payback_base"]),
                           ancre("payback_ans", c["payback"])))
        elif c["motif_investissement"] and c["economies"] is not None:
            r2.append(fait(f'<span style="font-size:8.5pt;">{c["motif_investissement"]}</span>', "", L("ci_retour_estime", "Retour estimé")))
    if c["co2_t"]:
        (r2 if len(r2) < 3 else r1).append(fait(f'≈&#160;{c["co2_t"]}', "&nbsp;t", L("ci_co2_evite", "CO₂ évité / an"), "", c["co2_facteur"]))
    registre = "".join(f'<div class="no-reg" style="margin-top:{"4mm" if i == 0 else "0"};{"border-top:0;" if i else ""}">{"".join(r)}</div>'
                       for i, r in enumerate([r for r in (r1, r2) if r]))
    methode = "".join(f'<div>{t}</div>' for t in m["methode"])
    if c["motif_non_chiffre"]:
        methode += f'<div>{c["motif_non_chiffre"]}</div>'
    pointe = (L("ci_note_autoconso_commercial",
                "L'installation vise l'<b>autoconsommation</b> : la valeur porte "
                "d'abord sur\n      la consommation de <b>journée</b> de votre "
                "établissement.") + " " + (c["note_pointe"] or ""))
    if m["deux_options"]:
        from ...ci import options_cote
        invest_html = ('<div style="margin-top:4mm;">'
                       + options_cote.cartes_options(d, "com", "no1", fmt, m["fmt_mad"], d.get("_invest_ttc") or 0) + '</div>')
    else:
        invest_html = (
            f'<div class="no-row no1-inv"><div class="no-col" style="vertical-align:middle;">'
            f'<div class="no1-invl">{inv["titre"]}</div>'
            + (f'<div class="no-cap">{inv["secondaire"]}' + (f' · {inv["note"]}' if inv["note"] else "") + '</div>' if inv["secondaire"] else "")
            + f'</div><div class="no-col" style="text-align:right;vertical-align:middle;white-space:nowrap;">'
            f'<span class="no1-invv">{inv["montant"]}</span><span class="no1-invu">&nbsp;MAD'
            + (f'&nbsp;{inv["unite"]}' if inv["unite"] else "") + f'</span>{inv["ancre"]}</div></div>')
    chart = ""
    if m["energie"]:
        plafond = max(max(x["consommation_kwh"], x["production_kwh"]) for x in m["energie"])
        svg = graphiques.barres_mensuelles(
            m["energie"], (j["bar_conso"], j["accent"], j["or"], j["line"], j["muted"]), "IBM Plex Sans",
            list("JFMAMJJASOND") if m["langue"] != "ar" else [str(i) for i in range(1, 13)],
            f'{fmt(round(plafond))} kWh', 106, 48,
            legende=(L("ci_legende_conso", "Votre consommation"), L("ci_legende_autoconso", "Production autoconsommée"),
                     L("ci_legende_surplus", "Surplus non consommé sur place")), contour=j["ink"], echelle_texte=1.2)
        chart = (f'<div class="no-h3">{L("ci_energie_mois_titre_court", "Votre énergie mois par mois")}</div>'
                 f'<div style="margin-top:2mm;">{svg}</div>'
                 f'<div class="no-cap">{L("ci_energie_mois_legende", "kWh par mois : votre consommation et la production estimée de la centrale, calculées heure par heure.")}</div>')
    uri, lien = m["qr"]
    etapes = "".join(f'<div style="margin-top:2px;"><span class="no1-n">{i}</span>&#160;{t}</div>'
                     for i, t in enumerate(m["etapes"], 1))
    qr_html = (f'<div style="margin-top:4mm;"><img src="{uri}" style="width:18mm;height:18mm;display:block;" alt="QR">'
               f'<div class="no-cap">{L("ci_proposition_en_ligne", "Votre proposition en ligne")} · {commun.esc(lien)}</div></div>' if uri else "")
    bas = (f'<div class="no-row no1-bas"><div class="no-col" style="width:108mm;">{chart}</div><div class="no-gap" style="width:6mm;"></div>'
           f'<div class="no-col"><div class="no-h3">{L("ci_prochaines_etapes", "Prochaines étapes")}</div>'
           f'<div style="margin-top:2mm;font-size:8.4pt;">{etapes}</div>{qr_html}</div></div>')

    css = f"""
<style>
.no1-root{{padding:0;}}
.no1-bandeau{{min-height:64mm;background:{j['hero_bg']};{commun.css_motif(j['motif_8'], 14)}color:{j['on_hero']};
  padding:12mm {j['marge']} 7mm {j['marge_g']};border-bottom:0.8pt solid {j['or']};}}
.no1-top{{display:table;width:100%;}}
.no1-tl{{display:table-cell;vertical-align:top;}}
.no1-tr{{display:table-cell;vertical-align:top;text-align:right;}}
.no1-rl{{font-size:6.6pt;letter-spacing:.14em;text-transform:uppercase;color:{j['or_texte']};font-weight:500;}}
.no1-rv{{font-size:12pt;font-weight:600;margin-top:1px;}}
.no1-hd{{font-size:7.4pt;color:{j['on_hero_2']};margin-top:1px;}}
.no1-kick{{margin-top:5mm;font-size:7pt;letter-spacing:.16em;text-transform:uppercase;color:{j['or_texte']};font-weight:500;}}
.no1-titre{{font-family:{j['display']};font-weight:400;font-size:24pt;line-height:1.1;margin-top:2mm;letter-spacing:-.01em;}}
.no1-acc{{margin-top:2mm;font-size:9.6pt;color:{j['on_hero_2']};max-width:150mm;line-height:1.4;}}
.no1-corps{{padding:6mm {j['marge']} 0 {j['marge_g']};}}
.no1-client{{font-size:7.8pt;color:{j['muted']};}}
.no1-client b{{color:{j['ink']};font-weight:600;}}
.no1-reserve{{margin-top:3.5mm;padding:3px 0 3px 8px;border-left:2pt solid {j['or']};font-size:8pt;font-weight:500;}}
.no1-meth{{margin-top:3mm;font-size:6.9pt;color:{j['muted']};line-height:1.45;}}
.no1-pointe{{margin-top:2.5mm;padding-left:3mm;border-left:1.5pt solid {j['accent']};font-size:8.3pt;line-height:1.45;max-width:165mm;}}
.no1-pointe b{{font-weight:600;}}
.no1-inv{{margin-top:4mm;border-top:1pt solid {j['ink']};border-bottom:0.4pt solid {j['or']};padding:6px 0;}}
.no1-invl{{font-size:9pt;font-weight:500;}}
.no1-invv{{font-family:{j['display']};font-weight:400;font-size:24pt;letter-spacing:-.01em;line-height:1;}}
.no1-invu{{font-size:8.5pt;font-weight:500;color:{j['muted']};}}
.no1-bas{{margin-top:4.5mm;}}
.no1-n{{font-family:{j['display']};font-weight:400;font-size:13pt;color:{j['laiton']};}}
{__import__('apps.ventes.quote_engine.ci.options_cote', fromlist=['css_options']).css_options('no1', (j['ink'], j['wash'], j['muted'], j['accent'], j['ink'], j['or']), 10) if m['deux_options'] else ''}
</style>"""
    return f"""{css}
<div class="no-root no1-root" style="padding:0;">
  <div class="no1-bandeau">
    <div class="no1-top"><div class="no1-tl">{commun.logo(ctx, 30, sombre=True)}</div>
      <div class="no1-tr"><div class="no1-rl">{L("ci_ref_devis", "Réf. devis")}</div><div class="no1-rv">{m["ref"]}</div>
      <div class="no1-hd">{m["date"]}{(" &nbsp;·&nbsp; " + validite) if validite else ""}</div>{corrections}</div></div>
    <div class="no1-kick">{kicker}</div>
    <div class="no1-titre">{titre}</div>
    <div class="no1-acc">{cat["accroche"]}</div>
  </div>
  <div class="no1-corps">
    <div class="no1-client">{ligne_client}</div>
    {f'<div class="no1-reserve">{bandeau_txt}</div>' if bandeau_txt else ''}
    {registre}
    <div class="no1-meth">{methode}</div>
    <div class="no1-pointe">{pointe}</div>
    {invest_html}
    {bas}
  </div>
</div>"""
