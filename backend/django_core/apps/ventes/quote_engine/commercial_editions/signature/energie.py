# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Signature — PAGE 2 : « Votre énergie, votre retour » (synthèse §3).

Bandeau d'en-tête, barres groupées mois par mois (consommation claire à
contour encre, autoconsommée royal, surplus or), installation en bref et
activité, position nette sur l'horizon servi (étoile khatam au point de
retour, retour et TRI, jalons), bases du calcul. Classes ``sg2-``.
"""
from .. import commun, donnees, graphiques


def build(ctx, m, j):
    d, p = m["d"], "sg"
    fmt = m["fmt"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    c = m["chiffres"]
    entete = commun.bande_entete(ctx, j, p, L("ci_rubrique_energie", "Votre énergie, votre retour"),
                                 f'{L("ci_ref_devis", "Réf. devis")} {m["ref"]}')

    energie_html = ""
    if m["energie"]:
        plafond = max(max(x["consommation_kwh"], x["production_kwh"]) for x in m["energie"])
        svg = graphiques.barres_mensuelles(
            m["energie"], (j["bar_conso"], j["accent"], j["or"], j["line"], j["muted"]), "IBM Plex Sans",
            list("JFMAMJJASOND") if m["langue"] != "ar" else [str(i) for i in range(1, 13)],
            f'{fmt(round(plafond))} kWh', 170, 58 if m["palier"] < 2 else 46,
            legende=(L("ci_legende_conso", "Votre consommation"), L("ci_legende_autoconso", "Production autoconsommée"),
                     L("ci_legende_surplus", "Surplus non consommé sur place")), contour=j["ink"])
        energie_html = (commun.kicker(L("ci_votre_energie", "Votre énergie"), j, p)
                        + f'<div class="sg-h2" style="margin-top:1.5mm;">'
                        + L("ci_energie_mois_titre", "Ce que la centrale produit, mois par mois")
                        + f'</div><div style="margin-top:3mm;">{svg}</div>'
                        f'<div class="sg-cap" style="margin-top:2px;">'
                        + L("ci_energie_mois_legende", "kWh par mois : votre consommation et la production estimée de la centrale, calculées heure par heure.")
                        + (f' {c["methode"]}' if c["methode"] else "") + '</div>')

    rangees = [] if m["palier"] >= 2 else donnees.installation_en_bref(d, L, fmt)
    bref = ""
    if rangees:
        lignes = "".join(
            f'<tr><td style="color:{j["muted"]};width:30%;padding:3px 6px 3px 0;border-bottom:0.5pt solid {j["line_soft"]};vertical-align:top;">{lib}</td>'
            f'<td style="padding:3px 0;border-bottom:0.5pt solid {j["line_soft"]};">{val}</td></tr>' for lib, val in rangees)
        bref = (f'<div class="sg-h3">{L("ci_inst_titre", "Votre installation en bref")}</div>'
                f'<table style="width:100%;border-collapse:collapse;font-size:7.8pt;margin-top:2mm;">{lignes}</table>')
    cat = m["categorie"]
    activite = ""
    if cat["lignes"]:
        puces = "".join(f'<div class="sg-li">{commun.losange(j["or"], 1.6)}{li}</div>' for li in cat["lignes"])
        activite = (f'<div class="sg-h3">{cat["titre_bloc"]}</div>'
                    f'<div style="margin-top:2mm;font-size:8pt;line-height:1.45;">{puces}</div>')
    duo = ""
    if bref or activite:
        duo = (f'<div class="sg-row sg-sec"><div class="sg-col" style="width:58%;">{bref}</div>'
               f'<div class="sg-gap"></div><div class="sg-col">{activite}</div></div>')

    retour_html = ""
    cu = m["cumul"]
    if cu:
        fin = cu["serie"][-1]
        lib_retour = L("ci_retour_en", "Retour en {ans} ans", ans=c["payback"]) if c["payback"] else ""
        lib_fin = f'{"+" if fin[1] >= 0 else "−"}{fmt(round(abs(fin[1])))} MAD · {fin[0]} {L("ci_ans", "ans")}'
        svg = graphiques.frise_cumul(
            cu["serie"], cu["jalons"], cu["retour"], (lib_retour, lib_fin, "0"),
            (j["sable"], j["accent"], j["line"], j["muted"], j["or"]), "IBM Plex Sans", 106,
            52 if m["palier"] < 2 else 42)
        jalons = "".join(
            f'<tr><td style="color:{j["muted"]};padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};">{L("ci_apres_n_ans", "Après {n} ans", n=a)}</td>'
            f'<td style="text-align:right;padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};white-space:nowrap;">{lib} MAD</td></tr>'
            for a, lib in cu["jalons"])
        indic = ""
        if c["payback"]:
            indic += (f'<div class="sg2-ind"><span class="sg2-indv">{c["payback"]}</span>'
                      f'<span class="sg-ru"> {c["payback_unite"].replace("&nbsp;", " ")}</span>'
                      f'<div class="sg-lab">{L("ci_retour_estime_base", "Retour estimé ({base})", base=c["payback_base"])}</div></div>')
        if c["tri_pct"]:
            indic += (f'<div class="sg2-ind"><span class="sg2-indv">{c["tri_pct"]}</span><span class="sg-ru"> %</span>'
                      f'<div class="sg-lab">{L("ci_tri_horizon", "TRI sur {n} ans", n=c["horizon"] or cu["horizon"])}</div></div>')
        retour_html = (commun.kicker(L("ci_votre_retour", "Votre retour"), j, p)
                       + f'<div class="sg-h2" style="margin-top:1.5mm;">'
                       + L("ci_position_nette_titre", "Position nette cumulée sur {n} ans ({base})", n=cu["horizon"] or fin[0], base=cu["base"])
                       + f'</div><div class="sg-row" style="margin-top:3mm;"><div class="sg-col" style="width:108mm;">{svg}</div>'
                       f'<div class="sg-gap"></div><div class="sg-col"><div class="sg-row">{indic}</div>'
                       f'<table style="width:100%;border-collapse:collapse;font-size:8.2pt;margin-top:3mm;">{jalons}</table></div></div>')
    elif c["motif_investissement"] or c["motif_non_chiffre"]:
        retour_html = (commun.kicker(L("ci_votre_retour", "Votre retour"), j, p)
                       + f'<div style="margin-top:2mm;font-size:8.5pt;">{c["motif_non_chiffre"] or c["motif_investissement"]}</div>')

    complements = ""
    if m["palier"] >= 2:
        option_avec = donnees.option_avec_html(d, L, m["fmt_mad"], (j["ink"], j["muted"], j["line_soft"], j["wash"]))
        extras = commun.options_et_injection(m, p, j, L)
        if option_avec or extras:
            complements = (f'<div class="sg-sec">' + commun.kicker(L("ci_complements_offre", "Compléments de l&#8217;offre"), j, p)
                           + f'{option_avec}{extras}</div>')
    hyp = commun.hypotheses_tableau(m, p, j, L, colonnes=2 if m["palier"] < 2 else 3)
    hyp_html = (f'<div class="sg-h3" style="margin-top:5mm;">{L("ci_bases_calcul", "Bases du calcul")}</div>'
                f'<div style="margin-top:2mm;">{hyp}</div>') if hyp else ""

    css = f"""
<style>
.sg2-ind{{display:table-cell;vertical-align:top;padding-right:6mm;}}
.sg2-indv{{font-family:{j['display']};font-weight:400;font-size:22pt;line-height:1;letter-spacing:-.01em;}}
</style>"""
    return f"""{css}
<div class="sg-root">
  {entete}
  {energie_html}
  {duo}
  <div class="sg-sec">{retour_html}{hyp_html}</div>
  {complements}
</div>"""
