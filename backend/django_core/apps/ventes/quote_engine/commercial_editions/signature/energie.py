# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Signature — PAGE 2 : votre énergie, votre retour.

Barres groupées mois par mois (kWh servis), l'installation en bref et la
case d'activité, puis la position nette sur l'horizon servi (cumul,
jalons, retour, TRI) et les bases du calcul. Classes ``sg2-``.
"""
from .. import commun, donnees, graphiques
from ...figures import ancre
from ...montants import decimale


def build(ctx, m, j):
    d, p = m["d"], "sg"
    fmt = m["fmt"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    c = m["chiffres"]

    # ── Énergie mois par mois ─────────────────────────────────────────────
    energie_html = ""
    if m["energie"]:
        plafond = max(max(x["consommation_kwh"], x["production_kwh"]) for x in m["energie"])
        reperes = list(graphiques.__dict__.get("REPERES", "JFMAMJJASOND")) if m["langue"] != "ar" \
            else [str(i) for i in range(1, 13)]
        svg = graphiques.barres_mensuelles(
            m["energie"], (j["ink"], j["accent"], j["accent_soft"], j["line"], j["muted"]),
            "IBM Plex Sans", reperes, f'{fmt(round(plafond))} kWh', 172,
            58 if m["palier"] < 2 else 46,
            legende=(L("ci_legende_conso", "Votre consommation"),
                     L("ci_legende_autoconso", "Production autoconsommée"),
                     L("ci_legende_surplus", "Surplus non consommé sur place")))
        energie_html = (
            f'<div class="sg-kicker">{L("ci_votre_energie", "Votre énergie")}</div>'
            f'<div class="sg-h2" style="margin-top:1.5mm;">'
            + L("ci_energie_mois_titre", "Ce que la centrale produit, mois par mois")
            + f'</div><div style="margin-top:4mm;">{svg}</div>'
            f'<div class="sg-cap" style="margin-top:2px;">'
            + L("ci_energie_mois_legende",
                "kWh par mois : votre consommation et la production estimée de la "
                "centrale, calculées heure par heure.")
            + (f' {c["methode"]}' if c["methode"] else "") + '</div>')

    # ── Installation en bref + activité ──────────────────────────────────
    # Palier >= 2 : « en bref » cède (le tableau du devis liste déjà
    # modules et onduleurs) ; le graphique se resserre.
    rangees = [] if m["palier"] >= 2 else donnees.installation_en_bref(d, L, fmt)
    bref = ""
    if rangees:
        lignes = "".join(
            f'<tr><td style="color:{j["muted"]};width:30%;padding:3px 6px 3px 0;'
            f'border-bottom:0.5pt solid {j["line_soft"]};vertical-align:top;">{lib}</td>'
            f'<td style="padding:3px 0;border-bottom:0.5pt solid {j["line_soft"]};">{val}</td></tr>'
            for lib, val in rangees)
        bref = (f'<div class="sg-h3">{L("ci_inst_titre", "Votre installation en bref")}</div>'
                f'<table style="width:100%;border-collapse:collapse;font-size:7.8pt;margin-top:3px;">{lignes}</table>')
    cat = m["categorie"]
    activite = ""
    if cat["lignes"]:
        puces = "".join(f'<div class="sg2-li">{li}</div>' for li in cat["lignes"])
        activite = (f'<div class="sg-h3">{cat["titre_bloc"]}</div>'
                    f'<div style="margin-top:3px;font-size:8pt;line-height:1.45;">{puces}</div>')
    duo = ""
    if bref or activite:
        duo = (f'<div class="sg-row sg2-duo"><div class="sg-col" style="width:58%;">{bref}</div>'
               f'<div class="sg-gap"></div><div class="sg-col">{activite}</div></div>')

    # ── Position nette (cumul servi) ──────────────────────────────────────
    retour_html = ""
    cu = m["cumul"]
    if cu:
        fin = cu["serie"][-1]
        lib_retour = (L("ci_retour_en", "Retour en {ans} ans", ans=c["payback"])
                      if c["payback"] else "")
        lib_fin = f'{"+" if fin[1] >= 0 else "−"}{fmt(round(abs(fin[1])))} MAD · {fin[0]} {L("ci_ans", "ans")}'
        svg = graphiques.frise_cumul(
            cu["serie"], [(a, lib) for a, lib in cu["jalons"]], cu["retour"],
            (lib_retour, lib_fin, "0"),
            (j["ink"], j["accent"], j["line"], j["muted"], j["ochre"]), "IBM Plex Sans", 108,
            54 if m["palier"] < 2 else 42)
        jalons = "".join(
            f'<tr><td style="color:{j["muted"]};padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};">'
            f'{L("ci_apres_n_ans", "Après {n} ans", n=a)}</td>'
            f'<td style="text-align:right;padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};white-space:nowrap;">'
            f'{lib} MAD</td></tr>' for a, lib in cu["jalons"])
        indic = ""
        if c["payback"]:
            indic += (f'<div class="sg2-ind"><span class="sg2-indv">{c["payback"]}</span>'
                      f'<span class="sg-unit sg1-fu"> {c["payback_unite"].replace("&nbsp;", " ")}</span>'
                      f'<div class="sg-lab">{L("ci_retour_estime_base", "Retour estimé ({base})", base=c["payback_base"])}</div></div>')
        if c["tri_pct"]:
            indic += (f'<div class="sg2-ind"><span class="sg2-indv">{c["tri_pct"]}</span>'
                      f'<span class="sg-unit sg1-fu"> %</span>'
                      f'<div class="sg-lab">{L("ci_tri_horizon", "TRI sur {n} ans", n=c["horizon"] or cu["horizon"])}</div></div>')
        retour_html = (
            f'<div class="sg-kicker">{L("ci_votre_retour", "Votre retour")}</div>'
            f'<div class="sg-h2" style="margin-top:1.5mm;">'
            + L("ci_position_nette_titre", "Position nette cumulée sur {n} ans ({base})",
                n=cu["horizon"] or fin[0], base=cu["base"])
            + '</div>'
            f'<div class="sg-row" style="margin-top:4mm;"><div class="sg-col" style="width:110mm;">{svg}</div>'
            f'<div class="sg-gap"></div><div class="sg-col" style="vertical-align:top;">'
            f'<div class="sg-row">{indic}</div>'
            f'<table style="width:100%;border-collapse:collapse;font-size:7.8pt;margin-top:4mm;">{jalons}</table>'
            f'</div></div>')
    elif c["motif_investissement"]:
        retour_html = (f'<div class="sg-kicker">{L("ci_votre_retour", "Votre retour")}</div>'
                       f'<div style="margin-top:2mm;font-size:8.5pt;">{c["motif_investissement"]}</div>')

    # Palier >= 2 : compléments de l'offre déportés de la page 3.
    complements = ""
    if m["palier"] >= 2:
        option_avec = donnees.option_avec_html(d, L, m["fmt_mad"], (j["ink"], j["muted"], j["line_soft"], j["wash"]))
        extras = commun.options_et_injection(m, p, j, L)
        if option_avec or extras:
            complements = (f'<div class="sg2-retour"><div class="sg-kicker">'
                           + L("ci_complements_offre", "Compléments de l&#8217;offre")
                           + f'</div>{option_avec}{extras}</div>')
    hyp = commun.hypotheses_tableau(m, p, j, L, colonnes=2)
    hyp_html = (f'<div class="sg-h3" style="margin-top:6mm;">{L("ci_bases_calcul", "Bases du calcul")}</div>'
                f'<div style="margin-top:2mm;">{hyp}</div>') if hyp else ""

    css = f"""
<style>
.sg2-duo{{margin-top:6mm;padding-top:5mm;border-top:0.5pt solid {j['line']};}}
.sg2-li{{padding-left:9px;position:relative;margin-top:2px;}}
.sg2-li:before{{content:'';position:absolute;left:0;top:6px;width:4px;height:4px;border-radius:50%;background:{j['accent']};}}
.sg2-retour{{margin-top:7mm;padding-top:5mm;border-top:0.5pt solid {j['line']};}}
.sg2-ind{{display:table-cell;vertical-align:top;padding-right:6mm;}}
.sg2-indv{{font-family:{j['display']};font-weight:300;font-size:21pt;line-height:1;}}
</style>"""
    return f"""{css}
<div class="sg-root">
  {energie_html}
  {duo}
  <div class="sg2-retour">{retour_html}{hyp_html}</div>
  {complements}
</div>"""
