# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Khatam — PAGE 3 : la page confiance ACTUELLE (``commercial/trust.py``)
dans le même ordre : trois étapes, garanties, échéancier, financement,
services, bases du calcul, conditions, bon pour accord, bande légale — avec
les numéros d'étapes dans l'octogone khatam, les garanties en Fraunces 600
vert zellige séparées par des filets or, le bon pour accord en cartouche à
double filet. Classes ``kh3-``.
"""
from .. import commun, donnees


def build(ctx, m, j):
    d, p = m["d"], "kh"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    ar = donnees.ar
    entete = commun.bande_entete(ctx, j, p, L("ci_kicker_etapes", "Votre projet, étape par étape"),
                                 f'{L("ci_ref_devis", "Réf. devis")} {m["ref"]}')
    steps = [(L("ci_etape_etude_t", "Étude &amp; validation"),
              L("ci_etape_etude_s", "Dimensionnement, visite technique et validation du projet.")),
             (L("ci_etape_installation_t", "Installation"),
              L("ci_etape_installation_s", "Pose des équipements par nos équipes, en coordination avec votre activité.")),
             (L("ci_etape_mes_t", "Mise en service"),
              L("ci_etape_mes_s", "Raccordement, tests et réception — votre production démarre."))]
    cells = ""
    for i, (t, s) in enumerate(steps, 1):
        gap = '<td class="kh3-sgap"></td>' if i < len(steps) else ""
        cells += (f'<td class="kh3-step">{commun.octogone(i, j["or"], j["laiton"], "EdDisplay", 6.5)}'
                  f'<div class="kh3-step-t">{t}</div><div class="kh3-step-s">{s}</div></td>{gap}')
    garanties = ""
    if m["garanties"]:
        cel = ""
        for k, (n, u, lib) in enumerate(m["garanties"]):
            sep = f'border-{"right" if m["rtl"] else "left"}:0.5pt solid {j["or"]};' if k else ""
            cel += (f'<div class="kh3-warr-c" style="{sep}"><div class="kh3-warr-v">{n}'
                    f'<span class="kh3-warr-u"> {u}</span></div><div class="kh3-warr-l">{lib}</div></div>')
        from ...ci.blocs import legende_garanties
        garanties = (f'<div class="kh3-h2">{L("ci_garanties", "Garanties")}'
                     + (f'<span class="kh-ar kh3-h2ar">{ar("ci_garanties")}</span>' if ar("ci_garanties") else "")
                     + f'</div><div class="kh3-warr"><div class="kh3-warr-row">{cel}</div>'
                     f'<div class="kh3-warr-l" style="margin-top:6px;">{legende_garanties(d)}</div></div>')
    echeancier = ""
    if m["echeancier"]:
        ttc = L("ci_ttc", "TTC")
        cel = ""
        for pct, lib, mt in m["echeancier"]:
            cel += (f'<td class="kh3-ech-c"><div class="kh3-ech-p">{pct}&nbsp;%</div><div>{lib}</div>'
                    + (f'<div class="kh3-ech-m">{mt}&#160;MAD {ttc}</div>' if mt else "") + '</td>')
        echeancier = (f'<div class="kh3-h3">{L("ci_cpdf_echeancier", "Échéancier de paiement")}'
                      + (f'<span class="kh-ar kh3-h3ar">{ar("ci_cpdf_echeancier")}</span>' if ar("ci_cpdf_echeancier") else "")
                      + f'</div><table class="kh3-ech"><tr>{cel}</tr></table>')
    financement = donnees.financement_html(d, "kh3", j["hero_bg"], j["ink"])
    services = donnees.services_html(d, "kh3", j["hero_bg"], j["ink"])
    hyp = commun.hypotheses_tableau(m, p, j, L, colonnes=2)
    hyp_html = (f'<div class="kh3-h3">{L("ci_bases_calcul", "Bases du calcul")}</div>'
                f'<div style="margin-top:2mm;">{hyp}</div>') if hyp else ""
    conditions = commun.conditions_bloc(m, p, j)
    accord = commun.bon_pour_accord(m, p, j, L, haut_mm=18, cartouche=True, ar_titre=ar("bon_pour_accord"),
                                    ar_signature=ar("ci_signature"), ar_cachet=ar("ci_cachet"))
    legale = commun.bande_legale(m, p, j)
    css = f"""
<style>
.kh3-steprow{{display:table;width:100%;margin-top:3.5mm;border-spacing:0;}}
.kh3-step{{display:table-cell;vertical-align:top;border:0.5pt solid {j['line']};border-top:3px solid {j['or']};
  border-radius:6px;padding:10px 12px;background:{j['wash']};}}
.kh3-sgap{{display:table-cell;width:9px;}}
.kh3-step-t{{font-size:8.6pt;font-weight:600;color:{j['hero_bg']};margin-top:4px;}}
.kh3-step-s{{font-size:7.2pt;color:{j['muted']};margin-top:3px;line-height:1.35;}}
.kh3-h2{{font-family:{j['display']};font-weight:600;font-size:13pt;color:{j['hero_bg']};margin-top:5mm;}}
.kh3-h2ar{{font-size:10.5pt;color:{j['muted']};margin-left:9px;font-weight:400;}}
.kh3-h3{{font-size:9pt;font-weight:600;color:{j['hero_bg']};margin-top:4.5mm;}}
.kh3-h3ar{{font-size:8.5pt;color:{j['muted']};margin-left:8px;font-weight:400;}}
.kh3-warr{{margin-top:2.5mm;border:0.5pt solid {j['line']};border-radius:6px;background:{j['wash']};padding:9px 12px;}}
.kh3-warr-row{{display:table;width:100%;border-spacing:0;table-layout:fixed;}}
.kh3-warr-c{{display:table-cell;vertical-align:top;text-align:center;padding:0 6px;}}
.kh3-warr-v{{font-family:{j['display']};font-weight:600;font-size:16pt;color:{j['accent']};line-height:1;}}
.kh3-warr-u{{font-family:{j['sans']};font-size:8pt;font-weight:500;color:{j['muted']};}}
.kh3-warr-l{{font-size:7pt;color:{j['muted']};margin-top:3px;}}
.kh3-ech{{width:100%;border-collapse:separate;border-spacing:5px 0;margin:2.5mm -5px 0 -5px;table-layout:fixed;font-size:7.5pt;}}
.kh3-ech-c{{vertical-align:top;border:0.5pt solid {j['line']};border-top:2px solid {j['or']};border-radius:6px;padding:7px 9px;}}
.kh3-ech-p{{font-family:{j['display']};font-weight:600;font-size:12pt;color:{j['hero_bg']};}}
.kh3-ech-m{{font-weight:600;color:{j['hero_bg']};margin-top:2px;}}
.kh3-services{{margin-top:3mm;font-size:8pt;line-height:1.4;}}
</style>"""
    return f"""{css}
<div class="kh-root" style="padding-top:22mm;padding-left:14mm;padding-right:14mm;">
  {entete}
  {commun.kicker(L("ci_kicker_etapes", "Votre projet, étape par étape"), j, p)}
  <div class="kh-h2" style="margin-top:1.5mm;">{L("ci_comment_nous_procedons", "Comment nous procédons")}
    {f'<span class="kh-ar">{ar("ci_comment_nous_procedons")}</span>' if ar("ci_comment_nous_procedons") else ''}</div>
  <table class="kh3-steprow"><tr>{cells}</tr></table>
  {garanties}
  {echeancier}{financement}
  <div class="kh3-services">{services}</div>
  {hyp_html}
  {conditions}
  {accord}
  {legale}
</div>"""
