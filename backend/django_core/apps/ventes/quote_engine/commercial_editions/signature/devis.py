# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Signature — PAGE 3 : « Équipements & engagement » (synthèse §3).

Tableau à en-tête doublé (encre + or), chaîne de totaux avec la rangée
Total TTC sur bande marine tramée, option batterie / options / surplus,
garanties séparées par l'étoile khatam, échéancier, services et procédure
(numéros en octogone), conditions, bon pour accord en cartouche à double
filet, bande légale. Classes ``sg3-``.
"""
from .. import commun, donnees


def build(ctx, m, j):
    d, p = m["d"], "sg"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    ar = donnees.ar
    entete = commun.bande_entete(ctx, j, p, L("ci_rubrique_devis", "Équipements &amp; engagement"),
                                 f'{L("ci_ref_devis", "Réf. devis")} {m["ref"]}')
    tableau = commun.tableau_equipements(m, p, j, L)
    totaux = commun.chaine_totaux(m, p, L, ttc_marine=True, ar_ttc=ar("total_ttc"))
    note = (f'<div class="sg-cap" style="margin-top:4px;white-space:pre-line;">'
            f'<b>{L("ci_note", "Note")}</b> {m["note_client"]}</div>' if m["note_client"] else "")
    from ...clauses_cgv import bloc_clauses_html
    clauses = bloc_clauses_html(d.get("clauses_cgv"), couleur_titre=j["ink"], couleur_texte=j["ink"], langue=m["langue"])
    if m["palier"] >= 2:
        option_avec, extras = "", ""
    else:
        option_avec = donnees.option_avec_html(d, L, fmt_mad, (j["ink"], j["muted"], j["line_soft"], j["wash"]))
        extras = commun.options_et_injection(m, p, j, L)

    echeancier = commun.echeancier_rangee(m, p, j, L)
    garanties3 = commun.garanties_rangee(m, p, j, L, 20, 600, etoiles=True) if m["palier"] >= 3 else ""
    services = donnees.services_html(d, "sg3", j["ink"], j["ink"])
    financement = donnees.financement_html(d, "sg3", j["ink"], j["ink"])
    steps = [(L("ci_etape_etude_t", "Étude &amp; validation"),
              L("ci_etape_etude_s", "Dimensionnement, visite technique et validation du projet.")),
             (L("ci_etape_installation_t", "Installation"),
              L("ci_etape_installation_s", "Pose des équipements par nos équipes, en coordination avec votre activité.")),
             (L("ci_etape_mes_t", "Mise en service"),
              L("ci_etape_mes_s", "Raccordement, tests et réception — votre production démarre."))]
    if m["palier"] >= 2:
        # Compact : les mêmes octogones, sans le descriptif.
        procedure = "".join(
            f'<div class="sg-row" style="margin-top:1.2mm;"><div class="sg-col" style="width:7mm;">'
            f'{commun.octogone(i, j["or"], j["laiton"], "EdDisplay", 4.8)}</div>'
            f'<div class="sg-col" style="vertical-align:middle;"><div class="sg-h3">{t}</div></div></div>'
            for i, (t, _s) in enumerate(steps, 1))
    else:
        procedure = "".join(
            f'<div class="sg-row" style="margin-top:{"2mm" if i == 1 else "1.5mm"};"><div class="sg-col" style="width:8mm;">'
            f'{commun.octogone(i, j["or"], j["laiton"], "EdDisplay")}</div>'
            f'<div class="sg-col"><div class="sg-h3">{t}</div><div class="sg-cap">{s}</div></div></div>'
            for i, (t, s) in enumerate(steps, 1))
    if m["palier"] >= 3 and services:
        import re
        services = re.sub(r"<div[^>]*>", " ", services).replace("</div>", " · ")
        services = f'<div style="font-size:7.8pt;">{services.strip(" ·")}</div>'
    conditions = commun.conditions_bloc(m, p, j)
    accord = commun.bon_pour_accord(m, p, j, L, haut_mm=20, cartouche=True, ar_titre=ar("bon_pour_accord"),
                                    ar_signature=ar("ci_signature"), ar_cachet=ar("ci_cachet"))
    legale = commun.bande_legale(m, p, j)

    css = f"""
<style>
.sg3-services{{font-size:8pt;line-height:1.4;}}
</style>"""
    return f"""{css}
<div class="sg-root">
  {entete}
  {commun.kicker(L("ci_votre_installation", "Votre installation"), j, p, ar("ci_votre_installation"))}
  <div class="sg-h2" style="margin-top:1.5mm;">{L("ci_equipements_investissement", "Équipements &amp; investissement")}</div>
  <div style="margin-top:3.5mm;">{tableau}</div>
  {totaux}{note}{clauses}{option_avec}{extras}
  {f'<div class="sg-sec">{commun.kicker(L("ci_garanties", "Garanties"), j, p, ar("ci_garanties"))}<div style="margin-top:2.5mm;">{garanties3}</div></div>' if garanties3 else ''}
  {f'<div class="sg-sec">{commun.kicker(L("ci_cpdf_echeancier", "Échéancier de paiement"), j, p, ar("ci_cpdf_echeancier"))}<div style="margin-top:2.5mm;">{echeancier}</div></div>' if echeancier else ''}
  <div class="sg-sec sg-row">
    <div class="sg-col sg3-services" style="width:50%;">{services}{financement}</div>
    <div class="sg-gap"></div>
    <div class="sg-col">{commun.kicker(L("ci_comment_nous_procedons", "Comment nous procédons"), j, p)}{procedure}</div>
  </div>
  {conditions}
  {accord}
  {legale}
</div>"""
