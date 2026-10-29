# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Signature — PAGE 3 : le devis et l'accord.

Tableau des équipements (chiffres tabulaires), chaîne de totaux, option
batterie / options / surplus, garanties en grands nombres, échéancier,
services, étapes, conditions, bon pour accord en style contrat, bande
légale. Classes ``sg3-``.
"""
from .. import commun, donnees


def build(ctx, m, j):
    d, p = m["d"], "sg"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)

    tableau = commun.tableau_equipements(m, p, j, L)
    totaux = commun.chaine_totaux(m, p, L)
    note = (f'<div class="sg-cap" style="margin-top:4px;white-space:pre-line;">'
            f'<b>{L("ci_note", "Note")}</b> {m["note_client"]}</div>' if m["note_client"] else "")
    from ...clauses_cgv import bloc_clauses_html
    clauses = bloc_clauses_html(d.get("clauses_cgv"), couleur_titre=j["ink"],
                                couleur_texte=j["ink"], langue=m["langue"])
    # Palier >= 2 : l'option batterie et les options proposées se déportent
    # en page 2 (``energie.complements``) — page 3 garde le devis et l'accord.
    if m["palier"] >= 2:
        option_avec, extras = "", ""
    else:
        option_avec = donnees.option_avec_html(d, L, fmt_mad, (j["ink"], j["muted"], j["line_soft"], j["wash"]))
        extras = commun.options_et_injection(m, p, j, L)

    garanties = commun.garanties_rangee(m, p, j, L, 20)
    echeancier = commun.echeancier_rangee(m, p, j, L)
    services = donnees.services_html(d, "sg3", j["ink"], j["ink"])
    financement = donnees.financement_html(d, "sg3", j["ink"], j["ink"])

    steps = [(L("ci_etape_etude_t", "Étude &amp; validation"),
              L("ci_etape_etude_s", "Dimensionnement, visite technique et validation du projet.")),
             (L("ci_etape_installation_t", "Installation"),
              L("ci_etape_installation_s", "Pose des équipements par nos équipes, en coordination avec votre activité.")),
             (L("ci_etape_mes_t", "Mise en service"),
              L("ci_etape_mes_s", "Raccordement, tests et réception — votre production démarre."))]
    etapes = "".join(
        f'<div class="sg-col sg3-step"><div class="sg3-sn">{i}</div>'
        f'<div class="sg-h3">{t}</div><div class="sg-cap">{s}</div></div>'
        for i, (t, s) in enumerate(steps, 1))

    # Palier >= 2 : les trois étapes cèdent (la couverture dit déjà les
    # prochaines étapes) — jamais la bande légale ni l'accord.
    etapes_html = "" if m["palier"] >= 2 else (
        f'<div class="sg3-sec"><div class="sg-kicker">'
        + L("ci_comment_nous_procedons", "Comment nous procédons")
        + f'</div><div class="sg-row" style="margin-top:3mm;">{etapes}</div></div>')
    conditions = commun.conditions_bloc(m, p, j)
    accord = commun.bon_pour_accord(m, p, j, L, haut_mm=15)
    legale = commun.bande_legale(m, p, j)

    css = f"""
<style>
.sg3-sec{{margin-top:4.5mm;padding-top:3mm;border-top:0.5pt solid {j['line']};}}
.sg3-step{{padding-right:6mm;}}
.sg3-sn{{font-family:{j['display']};font-weight:300;font-size:18pt;color:{j['accent']};line-height:1;margin-bottom:2px;}}
.sg3-services{{font-size:8pt;line-height:1.4;}}
.sg3-ech{{font-size:8pt;}}
</style>"""
    return f"""{css}
<div class="sg-root">
  <div class="sg-kicker">{L("ci_votre_installation", "Votre installation")}</div>
  <div class="sg-h2" style="margin-top:1.5mm;">{L("ci_equipements_investissement", "Équipements &amp; investissement")}</div>
  <div style="margin-top:4mm;">{tableau}</div>
  {totaux}{note}{clauses}{option_avec}{extras}
  <div class="sg3-sec">
    <div class="sg-kicker">{L("ci_garanties", "Garanties")}</div>
    <div style="margin-top:3mm;">{garanties}</div>
  </div>
  <div class="sg3-sec sg-row">
    <div class="sg-col" style="width:58%;">
      <div class="sg-kicker">{L("ci_cpdf_echeancier", "Échéancier de paiement")}</div>
      <div style="margin-top:3mm;">{echeancier}</div>
    </div>
    <div class="sg-gap"></div>
    <div class="sg-col sg3-services">{services}{financement}</div>
  </div>
  {etapes_html}
  {conditions}
  {accord}
  {legale}
</div>"""
