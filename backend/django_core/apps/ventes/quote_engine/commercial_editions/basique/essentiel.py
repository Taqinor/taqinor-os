# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Basique — PAGE 1 : l'essentiel (synthèse §5).

Bandeau marine tramé 30 mm (logo, référence, date, validité), titre sur
une ligne, ligne client, réserve, trois chiffres en registre (puissance,
économies en royal, retour) avec la seule première ligne de méthode,
tableau simple, chaîne de totaux (Total TTC en Fraunces 18 pt + arabe).
En variante « une » (une seule page), suit le reste : échéancier et
garanties sur une ligne, conditions, QR, bon pour accord, bande légale.
Classes ``ba1-``.
"""
from .. import commun, donnees
from ...figures import ancre


def bil(d, cle, fr, p="ba", **v):
    """« libellé FR » + « libellé AR » (catalogue) côte à côte."""
    fr_txt = donnees.L(d, cle, fr, **v)
    ar_txt = donnees.ar(cle, fr)
    if not ar_txt or donnees.ci_blocs.langue(d) != "fr":
        return fr_txt
    return f'{fr_txt}<span class="{p}-ar">{ar_txt}</span>'


def suite(ctx, m, j):
    """Les points 8 à 13 de la Basique : échéancier, garanties, conditions,
    QR, bon pour accord, bande légale."""
    d, p = m["d"], "ba"
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    ar = donnees.ar
    ech = commun.echeancier_ligne(m, L)
    gar = commun.garanties_ligne(m)
    lignes = ""
    def _ll(cle, fr):
        ar_txt = ar(cle)
        ar_html = f'<span class="ba-ar">{ar_txt}</span>' if ar_txt else ""
        return f'<span class="ba1-ll">{L(cle, fr)}{ar_html}</span>'
    if ech:
        lignes += f'<div class="ba1-l">{_ll("ci_cpdf_echeancier", "Échéancier de paiement")}{ech}</div>'
    if gar:
        lignes += f'<div class="ba1-l">{_ll("ci_garanties", "Garanties")}{gar}</div>'
    titre_c, puces = m["conditions"]
    if puces:
        lignes += (f'<div class="ba1-l"><span class="ba1-ll">{titre_c}</span>'
                   + " &nbsp;·&nbsp; ".join(puces) + '</div>')
    uri, lien = m["qr"]
    qr = (f'<div class="ba-col" style="width:20mm;text-align:right;vertical-align:top;">'
          f'<img src="{uri}" style="width:16mm;height:16mm;" alt="QR">'
          f'<div class="ba-cap" style="font-size:6.4pt;">{L("ci_proposition_en_ligne", "Votre proposition en ligne")}</div></div>' if uri else "")
    bloc = (f'<div class="ba-row ba-sec"><div class="ba-col">{lignes}</div>{qr}</div>' if lignes or qr else "")
    accord = commun.bon_pour_accord(m, p, j, L, haut_mm=18, ar_titre=ar("bon_pour_accord"),
                                    ar_signature=ar("ci_signature"), ar_cachet=ar("ci_cachet"))
    return bloc + accord + commun.bande_legale(m, p, j)


def build(ctx, m, j):
    d, p = m["d"], "ba"
    fmt = m["fmt"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    ar = donnees.ar
    c, inv, cl = m["chiffres"], m["invest"], m["client"]
    validite = (L("ci_valable_jusqu", "Valable jusqu&#8217;au {date}", date=m["valid_until"])
                if m["valid_until"] else "")
    corrections = "".join(f'<div class="ba1-hd">{x}</div>' for x in m["marques_correction"])
    titre = donnees.ci_couverture.titre_projet(d, "com", c["kwc"], cl["nom"])
    taille_titre = 18 if len(titre) <= 58 else 15
    ligne_client = donnees.ci_couverture.ligne_client(d, "com", cl["nom"], cl["meta"], "ba1")
    bandeau_txt = donnees.bandeau_reserve(d, "ba1")

    def fait(val, unite, lib_html, a="", royal=False):
        return (f'<div class="ba-reg-c"><div class="ba-rv{" royal" if royal else ""}" style="font-size:26pt;">{val}'
                f'<span class="ba-ru">{unite}</span></div>{a}<div class="ba-lab">{lib_html}</div></div>')
    faits = []
    if m["deux_options"]:
        from ...ci import options_cote
        registre = ('<div style="margin-top:4mm;">'
                    + options_cote.cartes_options(d, "com", "ba1", fmt, m["fmt_mad"], d.get("_invest_ttc") or 0) + '</div>')
    else:
        faits.append(fait(c["kwc"], L("res_unite_kwc", "&nbsp;kWc"), bil(d, "ci_puissance_crete", "Puissance crête"),
                          ancre("puissance_kwc", c["kwc"])))
        if c["economies"] is not None:
            lib = bil(d, "ci_economies_estimees", "Économies estimées / an") + \
                (f' <span class="ba-cap">({c["economies_base"]})</span>' if c["economies_base"] else "")
            faits.append(fait(c["economies"], "&nbsp;MAD", lib, ancre("economie_annuelle", c["economies"]), royal=True))
            if c["payback"]:
                faits.append(fait(c["payback"], c["payback_unite"],
                                  bil(d, "ci_retour_estime", "Retour estimé") + f' <span class="ba-cap">({c["payback_base"]})</span>',
                                  ancre("payback_ans", c["payback"])))
        elif c["production"] is not None:
            faits.append(fait(c["production"], L("ci_unite_kwh_an", "&nbsp;kWh/an"),
                              bil(d, "ci_production_annuelle", "Production annuelle"),
                              ancre("production_annuelle_kwh", c["production"])))
        registre = f'<div class="ba-reg" style="margin-top:4mm;">{"".join(faits)}</div>'
    methode = ""
    if m["methode"]:
        methode = f'<div class="ba-cap" style="margin-top:2mm;font-size:6.9pt;">{m["methode"][0]}</div>'
    if c["economies"] is None and (c["motif_non_chiffre"] or c["motif_investissement"]):
        methode += f'<div class="ba-cap" style="margin-top:1mm;">{c["motif_non_chiffre"] or c["motif_investissement"]}</div>'
    elif c["postes_hors_total"] and c["economies"] is not None:
        methode += (f'<div class="ba-cap" style="margin-top:1mm;">'
                    + L("ci_retour_prix_complet", "retour calculé sur le prix complet, après la visite") + '</div>')

    tableau = commun.tableau_equipements(m, p, j, L, simple=True)
    totaux = commun.chaine_totaux(m, p, L, ar_ttc=ar("total_ttc"), ttc_display=True)
    reste = suite(ctx, m, j) if m["variante"] == "une" else ""

    css = f"""
<style>
.ba1-root{{padding:0;}}
.ba1-bandeau{{height:30mm;background:{j['hero_bg']};{commun.css_motif(j['motif_8'], 14)}color:{j['on_hero']};
  padding:9mm {j['marge']} 0 {j['marge_g']};border-bottom:0.8pt solid {j['or']};}}
.ba1-top{{display:table;width:100%;}}
.ba1-tl{{display:table-cell;vertical-align:middle;}}
.ba1-tr{{display:table-cell;vertical-align:middle;text-align:right;}}
.ba1-rv{{font-size:11pt;font-weight:600;}}
.ba1-hd{{font-size:7.4pt;color:{j['on_hero_2']};margin-top:1px;}}
.ba1-corps{{padding:6mm {j['marge']} 0 {j['marge_g']};}}
.ba1-titre{{font-family:{j['display']};font-weight:400;font-size:{taille_titre}pt;line-height:1.15;letter-spacing:-.01em;}}
.ba1-client{{margin-top:1.5mm;font-size:7.8pt;color:{j['muted']};}}
.ba1-client b{{color:{j['ink']};font-weight:600;}}
.ba1-reserve{{margin-top:3mm;padding:3px 0 3px 8px;border-left:2pt solid {j['or']};font-size:8pt;font-weight:500;}}
.ba1-l{{margin-top:2mm;font-size:8pt;line-height:1.45;}}
.ba1-ll{{display:block;font-size:7pt;letter-spacing:.14em;text-transform:uppercase;color:{j['muted']};font-weight:500;}}
.ba1-ll .ba-ar{{text-transform:none;letter-spacing:0;font-size:8pt;margin-left:6px;font-weight:400;}}
.ba-lab .ba-ar{{display:block;text-align:left;margin:1px 0 0 0;}}
{__import__('apps.ventes.quote_engine.ci.options_cote', fromlist=['css_options']).css_options('ba1', (j['ink'], j['wash'], j['muted'], j['accent'], j['ink'], j['or']), 10) if m['deux_options'] else ''}
</style>"""
    return f"""{css}
<div class="ba-root ba1-root" style="padding:0;">
  <div class="ba1-bandeau"><div class="ba1-top">
    <div class="ba1-tl">{commun.logo(ctx, 30, sombre=True)}</div>
    <div class="ba1-tr"><div class="ba1-rv">{m["ref"]}</div>
      <div class="ba1-hd">{m["date"]}{(" &nbsp;·&nbsp; " + validite) if validite else ""}</div>{corrections}</div>
  </div></div>
  <div class="ba1-corps">
    <div class="ba1-titre">{titre}</div>
    <div class="ba1-client">{ligne_client}</div>
    {f'<div class="ba1-reserve">{bandeau_txt}</div>' if bandeau_txt else ''}
    {registre}{methode}
    <div style="margin-top:4mm;">{tableau}</div>
    {totaux}
    {reste}
  </div>
</div>"""
