# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Directe — PAGE 2 : « Ce que vous recevez ».

Le tableau du devis (désignation · quantité · P.U. · TVA · total, chiffres
tabulaires), la chaîne de totaux, les garanties en grands nombres, les
trois étapes, votre activité, l'énergie mois par mois. Classes ``dr2-``.
"""
from .. import commun, donnees, graphiques
from .gagnez import bil


def build(ctx, m, j):
    d, p = m["d"], "dr"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    B = lambda cle, fr, **v: bil(d, cle, fr, p, **v)

    tableau = commun.tableau_equipements(m, p, j, L)
    totaux = commun.chaine_totaux(m, p, L)
    note = (f'<div class="dr-cap" style="margin-top:4px;white-space:pre-line;">'
            f'<b>{L("ci_note", "Note")}</b> {m["note_client"]}</div>' if m["note_client"] else "")
    from ...clauses_cgv import bloc_clauses_html
    clauses = bloc_clauses_html(d.get("clauses_cgv"), couleur_titre=j["ink"], couleur_texte=j["ink"], langue=m["langue"])
    option_avec = donnees.option_avec_html(d, L, fmt_mad, (j["ink"], j["muted"], j["line_soft"], j["wash"]))
    extras = commun.options_et_injection(m, p, j, L)

    garanties = commun.garanties_rangee(m, p, j, L, 24)
    steps = [(L("ci_etape_etude_t", "Étude &amp; validation"),
              L("ci_etape_etude_s", "Dimensionnement, visite technique et validation du projet.")),
             (L("ci_etape_installation_t", "Installation"),
              L("ci_etape_installation_s", "Pose des équipements par nos équipes, en coordination avec votre activité.")),
             (L("ci_etape_mes_t", "Mise en service"),
              L("ci_etape_mes_s", "Raccordement, tests et réception — votre production démarre."))]
    etapes = "".join(
        f'<div class="dr-col dr2-step"><div class="dr2-sn">{i}</div>'
        f'<div class="dr-h3">{t}</div><div class="dr-cap">{s}</div></div>'
        for i, (t, s) in enumerate(steps, 1))

    etapes_html = "" if m["palier"] >= 2 else (
        f'<div class="dr2-sec"><div class="dr-lab2">'
        + B("ci_comment_nous_procedons", "Comment nous procédons")
        + f'</div><div class="dr-row" style="margin-top:2.5mm;">{etapes}</div></div>')
    cat = m["categorie"]
    activite = ""
    if cat["lignes"]:
        puces = "".join(f'<div class="dr2-li">{li}</div>' for li in cat["lignes"])
        activite = (f'<div class="dr-h3">{cat["titre_bloc"]}</div>'
                    f'<div style="margin-top:2mm;font-size:8.8pt;line-height:1.45;">{puces}</div>')
    rangees = donnees.installation_en_bref(d, L, fmt)
    bref = ""
    if rangees:
        lignes = "".join(
            f'<tr><td style="color:{j["muted"]};width:32%;padding:3px 6px 3px 0;border-bottom:0.5pt solid {j["line_soft"]};vertical-align:top;">{lib}</td>'
            f'<td style="padding:3px 0;border-bottom:0.5pt solid {j["line_soft"]};">{val}</td></tr>' for lib, val in rangees)
        bref = (f'<div class="dr-h3">{L("ci_inst_titre", "Votre installation en bref")}</div>'
                f'<table style="width:100%;border-collapse:collapse;font-size:8.2pt;margin-top:2mm;">{lignes}</table>')

    energie = ""
    if m["energie"]:
        plafond = max(max(x["consommation_kwh"], x["production_kwh"]) for x in m["energie"])
        svg = graphiques.barres_mensuelles(
            m["energie"], (j["ink"], j["accent"], j["accent_soft"], j["line"], j["muted"]), "IBM Plex Sans",
            list("JFMAMJJASOND") if m["langue"] != "ar" else [str(i) for i in range(1, 13)],
            f'{fmt(round(plafond))} kWh', 176, 42,
            legende=(L("ci_legende_conso", "Votre consommation"), L("ci_legende_autoconso", "Production autoconsommée"),
                     L("ci_legende_surplus", "Surplus non consommé sur place")))
        energie = (f'<div class="dr-lab2">{L("ci_energie_mois_titre", "Ce que la centrale produit, mois par mois")}</div>'
                   f'<div style="margin-top:2mm;">{svg}</div>')

    css = f"""
<style>
.dr2-sec{{margin-top:4mm;padding-top:3mm;border-top:0.5pt solid {j['line']};}}
.dr2-step{{padding-right:6mm;}}
.dr2-sn{{font-family:{j['display']};font-size:20pt;color:{j['accent']};line-height:1;margin-bottom:2px;}}
.dr2-li{{padding-left:10px;position:relative;margin-top:2px;}}
.dr2-li:before{{content:'';position:absolute;left:0;top:6px;width:5px;height:5px;border-radius:50%;background:{j['accent']};}}
</style>"""
    return f"""{css}
<div class="dr-root">
  <div class="dr-kicker">{L("ci_votre_installation", "Votre installation")}</div>
  <div class="dr-h2" style="margin-top:1.5mm;">{B("ci_equipements_investissement", "Équipements &amp; investissement")}</div>
  <div style="margin-top:3.5mm;">{tableau}</div>
  {totaux}{note}{clauses}{option_avec}{extras}
  <div class="dr2-sec">
    <div class="dr-lab2">{B("ci_garanties", "Garanties")}</div>
    <div style="margin-top:2.5mm;">{garanties}</div>
  </div>
  {etapes_html}
  <div class="dr2-sec dr-row">
    <div class="dr-col" style="width:55%;">{bref}</div><div class="dr-gap"></div>
    <div class="dr-col">{activite}</div>
  </div>
  <div class="dr2-sec">{energie}</div>
</div>"""
