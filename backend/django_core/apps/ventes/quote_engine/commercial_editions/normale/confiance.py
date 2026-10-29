# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Normale — PAGE 3 : confiance et accord (synthèse §4) :
procédure en trois colonnes à filet or (numéros laiton), (variante B :
garanties et échéancier), services, financement, bases du calcul,
conditions, bon pour accord à filet maître, bande légale. Classes ``no3-``.
"""
from .. import commun, donnees


def build(ctx, m, j):
    d, p = m["d"], "no"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    ar = donnees.ar
    entete = commun.bande_entete(ctx, j, p, L("ci_kicker_etapes", "Votre projet, étape par étape"),
                                 f'{L("ci_ref_devis", "Réf. devis")} {m["ref"]}', hauteur_mm=10, logo_mm=18)
    steps = [(L("ci_etape_etude_t", "Étude &amp; validation"),
              L("ci_etape_etude_s", "Dimensionnement, visite technique et validation du projet.")),
             (L("ci_etape_installation_t", "Installation"),
              L("ci_etape_installation_s", "Pose des équipements par nos équipes, en coordination avec votre activité.")),
             (L("ci_etape_mes_t", "Mise en service"),
              L("ci_etape_mes_s", "Raccordement, tests et réception — votre production démarre."))]
    etapes = "".join(
        f'<div class="no-col no3-step"><div class="no3-sn">{i}</div>'
        f'<div class="no-h3">{t}</div><div class="no-cap">{s}</div></div>'
        for i, (t, s) in enumerate(steps, 1))
    remontes = ""
    if m["variante"] != "A":
        garanties = commun.garanties_rangee(m, p, j, L, 20, 400, etoiles=False)
        echeancier = commun.echeancier_rangee(m, p, j, L)
        if garanties:
            remontes += (f'<div class="no-sec">{commun.kicker(L("ci_garanties", "Garanties"), j, p, ar("ci_garanties"))}'
                         f'<div style="margin-top:2.5mm;">{garanties}</div></div>')
        if echeancier:
            remontes += (f'<div class="no-sec">{commun.kicker(L("ci_cpdf_echeancier", "Échéancier de paiement"), j, p)}'
                         f'<div style="margin-top:2.5mm;">{echeancier}</div></div>')
    services = donnees.services_html(d, "no3", j["ink"], j["ink"])
    financement = donnees.financement_html(d, "no3", j["ink"], j["ink"])
    hyp = commun.hypotheses_tableau(m, p, j, L, colonnes=2)
    hyp_html = (f'<div class="no-h3" style="margin-top:4mm;">{L("ci_bases_calcul", "Bases du calcul")}</div>'
                f'<div style="margin-top:2mm;">{hyp}</div>') if hyp else ""
    conditions = commun.conditions_bloc(m, p, j)
    accord = commun.bon_pour_accord(m, p, j, L, haut_mm=16, ar_titre=ar("bon_pour_accord"))
    legale = commun.bande_legale(m, p, j)
    css = f"""
<style>
.no3-step{{padding:5px 6mm 0 0;border-top:0.5pt solid {j['or']};}}
.no3-sn{{font-family:{j['display']};font-weight:400;font-size:18pt;color:{j['laiton']};line-height:1;margin-bottom:2px;}}
.no3-services{{font-size:8pt;line-height:1.4;margin-top:4mm;}}
</style>"""
    return f"""{css}
<div class="no-root" style="padding-top:18mm;">
  {entete}
  {commun.kicker(L("ci_kicker_etapes", "Votre projet, étape par étape"), j, p)}
  <div class="no-h2" style="margin-top:1.5mm;">{L("ci_comment_nous_procedons", "Comment nous procédons")}</div>
  <div class="no-row" style="margin-top:3mm;">{etapes}</div>
  {remontes}
  <div class="no3-services">{services}{financement}</div>
  {hyp_html}
  {conditions}
  {accord}
  {legale}
</div>"""
