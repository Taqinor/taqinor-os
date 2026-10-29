# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Normale — PAGE 2 : équipements et investissement (synthèse §4) :
bandeau d'en-tête 10 mm, tableau, chaîne de totaux, note, clauses, option
batterie, options proposées, surplus, activité et installation en bref côte
à côte ; en variante A, garanties et échéancier remontent ici. Classes
``no2-``.
"""
from .. import commun, donnees


def build(ctx, m, j):
    d, p = m["d"], "no"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    ar = donnees.ar
    entete = commun.bande_entete(ctx, j, p, L("ci_votre_installation", "Votre installation"),
                                 f'{L("ci_ref_devis", "Réf. devis")} {m["ref"]}')
    tableau = commun.tableau_equipements(m, p, j, L)
    totaux = commun.chaine_totaux(m, p, L, ar_ttc=ar("total_ttc"))
    note = (f'<div class="no-cap" style="margin-top:4px;white-space:pre-line;">'
            f'<b>{L("ci_note", "Note")}</b> {m["note_client"]}</div>' if m["note_client"] else "")
    from ...clauses_cgv import bloc_clauses_html
    clauses = bloc_clauses_html(d.get("clauses_cgv"), couleur_titre=j["ink"], couleur_texte=j["ink"], langue=m["langue"])
    option_avec = donnees.option_avec_html(d, L, fmt_mad, (j["ink"], j["muted"], j["line_soft"], j["wash"]))
    extras = commun.options_et_injection(m, p, j, L)
    cat = m["categorie"]
    activite = ""
    if cat["lignes"]:
        puces = "".join(f'<div class="no-li">{commun.losange(j["or"], 1.6)}{li}</div>' for li in cat["lignes"])
        activite = (f'<div class="no-h3">{cat["titre_bloc"]}</div>'
                    f'<div style="margin-top:2mm;font-size:8.2pt;line-height:1.45;">{puces}</div>')
    rangees = donnees.installation_en_bref(d, L, fmt)
    bref = ""
    if rangees:
        lignes = "".join(
            f'<tr><td style="color:{j["muted"]};width:32%;padding:3px 6px 3px 0;border-bottom:0.5pt solid {j["line_soft"]};vertical-align:top;">{lib}</td>'
            f'<td style="padding:3px 0;border-bottom:0.5pt solid {j["line_soft"]};">{val}</td></tr>' for lib, val in rangees)
        bref = (f'<div class="no-h3">{L("ci_inst_titre", "Votre installation en bref")}</div>'
                f'<table style="width:100%;border-collapse:collapse;font-size:7.8pt;margin-top:2mm;">{lignes}</table>')
    duo = ""
    if activite or bref:
        duo = (f'<div class="no-row no-sec"><div class="no-col" style="width:56%;">{bref}</div>'
               f'<div class="no-gap"></div><div class="no-col">{activite}</div></div>')
    remontes = ""
    if m["variante"] == "A":
        garanties = commun.garanties_rangee(m, p, j, L, 20, 600, etoiles=True)
        echeancier = commun.echeancier_rangee(m, p, j, L)
        if garanties:
            remontes += (f'<div class="no-sec">{commun.kicker(L("ci_garanties", "Garanties"), j, p, ar("ci_garanties"))}'
                         f'<div style="margin-top:2.5mm;">{garanties}</div></div>')
        if echeancier:
            remontes += (f'<div class="no-sec">{commun.kicker(L("ci_cpdf_echeancier", "Échéancier de paiement"), j, p, ar("ci_cpdf_echeancier"))}'
                         f'<div style="margin-top:2.5mm;">{echeancier}</div></div>')
    return f"""
<div class="no-root" style="padding-top:22mm;">
  {entete}
  {commun.kicker(L("ci_votre_installation", "Votre installation"), j, p, ar("ci_votre_installation"))}
  <div class="no-h2" style="margin-top:1.5mm;">{L("ci_equipements_investissement", "Équipements &amp; investissement")}</div>
  <div style="margin-top:3.5mm;">{tableau}</div>
  {totaux}{note}{clauses}{option_avec}{extras}
  {duo}
  {remontes}
</div>"""
