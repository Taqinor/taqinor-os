# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Directe — PAGE 3 : « Votre retour et votre accord ».

La position nette (frise du cumul servi), les bases du calcul, services et
financement, conditions, bon pour accord avec cachet, bande légale.
Classes ``dr3-``.
"""
from .. import commun, donnees, graphiques
from .gagnez import bil


def build(ctx, m, j):
    d, p = m["d"], "dr"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    B = lambda cle, fr, **v: bil(d, cle, fr, p, **v)
    c, cu = m["chiffres"], m["cumul"]

    retour = ""
    if cu:
        fin = cu["serie"][-1]
        lib_retour = L("ci_retour_en", "Retour en {ans} ans", ans=c["payback"]) if c["payback"] else ""
        lib_fin = f'{"+" if fin[1] >= 0 else "−"}{fmt(round(abs(fin[1])))} MAD · {fin[0]} {L("ci_ans", "ans")}'
        svg = graphiques.frise_cumul(cu["serie"], cu["jalons"], cu["retour"], (lib_retour, lib_fin, "0"),
                                     (j["ink"], j["accent"], j["line"], j["muted"], j["ochre"]), "IBM Plex Sans", 112, 50)
        jalons = "".join(
            f'<tr><td style="color:{j["muted"]};padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};">{L("ci_apres_n_ans", "Après {n} ans", n=a)}</td>'
            f'<td style="text-align:right;padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};white-space:nowrap;">{lib} MAD</td></tr>'
            for a, lib in cu["jalons"])
        retour = (f'<div class="dr-kicker">{L("ci_votre_retour", "Votre retour")}</div>'
                  f'<div class="dr-h2" style="margin-top:1.5mm;">'
                  + L("ci_position_nette_titre", "Position nette cumulée sur {n} ans ({base})", n=cu["horizon"] or fin[0], base=cu["base"])
                  + f'</div><div class="dr-row" style="margin-top:3mm;"><div class="dr-col" style="width:114mm;">{svg}</div>'
                  f'<div class="dr-gap"></div><div class="dr-col"><table style="width:100%;border-collapse:collapse;font-size:8.4pt;">{jalons}</table></div></div>')
    elif c["motif_investissement"]:
        retour = (f'<div class="dr-kicker">{L("ci_votre_retour", "Votre retour")}</div>'
                  f'<div style="margin-top:2mm;font-size:9pt;">{c["motif_investissement"]}</div>')

    hyp = commun.hypotheses_tableau(m, p, j, L, colonnes=2)
    methode = "".join(f'<div>{t}</div>' for t in m["methode"])
    hyp_html = (f'<div class="dr-h3" style="margin-top:5mm;">{L("ci_bases_calcul", "Bases du calcul")}</div>'
                f'<div class="dr-cap" style="margin-top:1.5mm;">{methode}</div>'
                f'<div style="margin-top:2mm;">{hyp}</div>') if hyp else (
        f'<div class="dr-cap" style="margin-top:4mm;">{methode}</div>' if methode else "")
    services = donnees.services_html(d, "dr3", j["ink"], j["ink"])
    financement = donnees.financement_html(d, "dr3", j["ink"], j["ink"])
    conditions = commun.conditions_bloc(m, p, j)
    accord = commun.bon_pour_accord(m, p, j, L, haut_mm=18)
    legale = commun.bande_legale(m, p, j)

    css = f"""
<style>
.dr3-sec{{margin-top:5mm;padding-top:3.5mm;border-top:0.5pt solid {j['line']};}}
.dr3-services{{font-size:8.5pt;line-height:1.45;}}
</style>"""
    return f"""{css}
<div class="dr-root">
  {retour}{hyp_html}
  <div class="dr3-sec dr-row"><div class="dr-col dr3-services">{services}{financement}</div></div>
  {conditions}
  {accord}
  {legale}
</div>"""
