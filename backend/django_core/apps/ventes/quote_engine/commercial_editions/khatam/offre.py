# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Khatam — PAGE 2 : la page équipements ACTUELLE
(``commercial/equip.py``) : tableau, chaîne de totaux, note, clauses, option
batterie, options proposées, surplus injecté, case d'activité, installation
en bref — avec un bandeau d'en-tête tramé, un en-tête de tableau doublé
encre + or, la rangée Total TTC sur marine, des puces en étoile khatam ;
aucun arabe (fondateur 30/10).
Classes ``kh2-``.
"""
from .. import commun, donnees


def build(ctx, m, j):
    d, p = m["d"], "kh"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    entete = commun.bande_entete(ctx, j, p, L("ci_votre_installation", "Votre installation"),
                                 f'{L("ci_ref_devis", "Réf. devis")} {m["ref"]}')
    tableau = commun.tableau_equipements(m, p, j, L)
    totaux = commun.chaine_totaux(m, p, L, ttc_marine=True)
    note = (f'<div class="kh2-note"><b>{L("ci_note", "Note")}</b>{m["note_client"]}</div>' if m["note_client"] else "")
    from ...clauses_cgv import bloc_clauses_html
    clauses = bloc_clauses_html(d.get("clauses_cgv"), couleur_titre=j["hero_bg"], couleur_texte=j["ink"], langue=m["langue"])
    option_avec = donnees.option_avec_html(d, L, fmt_mad, (j["hero_bg"], j["muted"], j["line_soft"], j["wash"]))
    extras = commun.options_et_injection(m, p, j, L)
    cat = m["categorie"]
    bloc_cat = ""
    if cat["lignes"]:
        puces = "".join(f'<div class="kh2-li">{commun.losange(j["or"], 2.0)}{li}</div>' for li in cat["lignes"])
        bloc_cat = (f'<div class="kh2b"><div class="kh2b-h">{cat["titre_bloc"]}</div>'
                    f'<div class="kh2b-body">{puces}</div></div>')
    rangees = donnees.installation_en_bref(d, L, fmt)
    bref = ""
    if rangees:
        lignes = "".join(
            f'<tr><td style="color:{j["muted"]};width:24%;padding:3px 8px;border-bottom:0.5pt solid {j["line_soft"]};vertical-align:top;">{lib}</td>'
            f'<td style="padding:3px 8px;border-bottom:0.5pt solid {j["line_soft"]};">{val}</td></tr>' for lib, val in rangees)
        bref = (f'<div class="kh2v"><div class="kh2v-h">{L("ci_inst_titre", "Votre installation en bref")}</div>'
                f'<table style="width:100%;border-collapse:collapse;font-size:7.8pt;">{lignes}</table></div>')
    css = f"""
<style>
.kh2-note{{margin-top:8px;font-size:8pt;line-height:1.35;white-space:pre-line;}}
.kh2-note b{{text-transform:uppercase;letter-spacing:.08em;font-size:7pt;margin-right:6px;}}
.kh2b{{margin-top:5mm;border:0.5pt solid {j['line']};border-left:3px solid {j['or']};border-radius:6px;background:{j['wash']};padding:9px 12px;}}
.kh2b-h{{font-size:9pt;font-weight:600;color:{j['hero_bg']};}}
.kh2b-body{{margin-top:4px;}}
.kh2-li{{font-size:8pt;color:{j['ink']};line-height:1.4;margin-top:3px;}}
.kh2v{{margin-top:4mm;border-radius:6px;background:{j['wash']};padding:8px 6px;}}
.kh2v-h{{font-size:9pt;font-weight:600;color:{j['hero_bg']};padding:0 8px 3px 8px;}}
</style>"""
    return f"""{css}
<div class="kh-root" style="padding-top:22mm;padding-left:14mm;padding-right:14mm;">
  {entete}
  {commun.kicker(L("ci_votre_installation", "Votre installation"), j, p)}
  <div class="kh-h2" style="margin-top:1.5mm;">{L("ci_equipements_investissement", "Équipements &amp; investissement")}</div>
  <div style="margin-top:3.5mm;">{tableau}</div>
  {totaux}{note}{clauses}{option_avec}{extras}
  {bloc_cat}
  {bref}
</div>"""
