# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Khatam — PAGE 2 : la page équipements ACTUELLE
(``commercial/equip.py``) : tableau, chaîne de totaux, note, clauses, option
batterie, options proposées, surplus injecté, case d'activité, installation
en bref, puis le retour (position nette cumulée servie, jalons, TRI) — avec un bandeau d'en-tête tramé, un en-tête de tableau doublé
encre + or, la rangée Total TTC sur marine, des puces en étoile khatam ;
aucun arabe (fondateur 30/10).
Classes ``kh2-``.
"""
from .. import commun, donnees, graphiques


def build(ctx, m, j):
    d, p = m["d"], "kh"
    fmt, fmt_mad = m["fmt"], m["fmt_mad"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    entete = commun.bande_entete(ctx, j, p)
    tableau = commun.tableau_equipements(m, p, j, L)
    totaux = commun.chaine_totaux(m, p, L, ttc_marine=True, ttc_display=True)
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
    if rangees and not m["deux"]:  # à deux options, la fiche (mono-option) cède la place aux cartes
        lignes = "".join(
            f'<tr><td style="color:{j["muted"]};width:24%;padding:3px 8px;border-bottom:0.5pt solid {j["line_soft"]};vertical-align:top;">{lib}</td>'
            f'<td style="padding:3px 8px;border-bottom:0.5pt solid {j["line_soft"]};">{val}</td></tr>' for lib, val in rangees)
        bref = (f'<div class="kh2v"><div class="kh2v-h">{L("ci_inst_titre", "Votre installation en bref")}</div>'
                f'<table style="width:100%;border-collapse:collapse;font-size:7.8pt;">{lignes}</table></div>')
    # Le retour : position nette cumulée servie (``flux.cumul_mad``), jalons et
    # TRI du moteur — rien de recalculé ; cédé aux paliers denses (≥ 2).
    c = m["chiffres"]
    cu = m["cumul"]
    retour_html = ""
    if cu and m["palier"] < 2:
        fin = cu["serie"][-1]
        lib_retour = L("ci_retour_en", "Retour en {ans} ans", ans=c["payback"]) if c["payback"] else ""
        # Le SVG est composé dans la police du graphique : l'insécable ordinaire
        # (U+00A0) y rend le séparateur de milliers visible.
        lib_fin = (f'{"+" if fin[1] >= 0 else "−"}{fmt(round(abs(fin[1])))} MAD · {fin[0]} {L("ci_ans", "ans")}'
                   .replace(" ", " "))
        origine = cu["serie"][0][1]
        origine_txt = f'{"−" if origine < 0 else ""}{fmt(round(abs(origine)))} MAD'.replace(" ", " ")
        svg = graphiques.frise_cumul(
            cu["serie"], cu["jalons"], c["payback_num"], (lib_retour, lib_fin, "0 MAD"),
            (j["sable"], j["accent"], j["line"], j["muted"], j["or"]), "IBM Plex Sans", 106, 50,
            origine_txt=origine_txt, lib_annees=L("ci_annees", "années"))
        jalons = "".join(
            f'<tr><td style="color:{j["muted"]};padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};">{L("ci_apres_n_ans", "Après {n} ans", n=a)}</td>'
            f'<td style="text-align:right;padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};white-space:nowrap;">{lib} MAD</td></tr>'
            for a, lib in cu["jalons"])
        indic = ""
        if c["tri_pct"]:
            indic = (f'<div class="kh2-ind"><span class="kh2-indv">{c["tri_pct"]}</span><span class="kh-ru"> %</span>'
                     f'<div class="kh-lab">{L("ci_tri_horizon", "TRI sur {n} ans", n=c["horizon"] or cu["horizon"])}</div></div>')
        suffixe = (f' <span style="font-family:{j["sans"]};font-size:8.5pt;font-weight:500;color:{j["muted"]};">· {L("ci_option_n_titre", "Option {n} — {o}", n=1, o=m["deux"]["titre_sans"])}</span>'
                   if m["deux"] else "")
        retour_html = (f'<div class="kh-sec">' + commun.kicker(L("ci_votre_retour", "Votre retour"), j, p)
                       + f'<div class="kh-h2" style="margin-top:1.5mm;">'
                       + L("ci_position_nette_titre", "Position nette cumulée sur {n} ans ({base})", n=cu["horizon"] or fin[0], base=cu["base"]) + suffixe
                       + f'</div><div class="kh-row" style="margin-top:3mm;"><div class="kh-col" style="width:108mm;">{svg}</div>'
                       f'<div class="kh-gap"></div><div class="kh-col">{indic}'
                       f'<table style="width:100%;border-collapse:collapse;font-size:8.2pt;margin-top:3mm;">{jalons}</table></div></div></div>')
    deux = m["deux"]
    corps_deux = ""
    if deux:
        # Fondateur 30/10 — comme le résidentiel, « l'une à côté de l'autre et
        # la table dit laquelle est laquelle » : UNE table, deux colonnes
        # nommées (quantité et total HT de chaque option), puis les deux
        # chaînes de totaux côte à côte.
        ts, ta = deux["titre_sans"], deux["titre_avec"]

        def cellules(r):
            return (f'<td class="r">{r["qte"]}</td><td class="r" style="font-weight:600;">{r["total"]}</td>' if r
                    else '<td class="r kh2-abs">—</td><td class="r kh2-abs">—</td>')
        rows = ""
        for rs, ra in deux["cote_a_cote"]:
            r0 = rs or ra
            marque = f'<span class="kh-mq">{commun.esc(r0["marque"])}</span>' if r0["marque"] else ""
            sous = r0["sous_lignes"] if (rs is None or ra is None or rs["sous_lignes"] == ra["sous_lignes"]) else ""
            pu = r0["pu_ht"] if (rs is None or ra is None or rs["pu_ht"] == ra["pu_ht"]) else f'{rs["pu_ht"]}<br>{ra["pu_ht"]}'
            taux = r0["taux"] if (rs is None or ra is None or rs["taux"] == ra["taux"]) else f'{rs["taux"]}<br>{ra["taux"]}'
            rows += (f'<tr><td class="d">{r0["designation"]}{marque}{sous}</td><td class="r">{pu}</td><td class="r">{taux}</td>'
                     f'{cellules(rs)}{cellules(ra)}</tr>')
        head = (f'<tr class="kh2-gh"><th></th><th></th><th></th>'
                f'<th colspan="2" class="kh2-gs">{ts}</th><th colspan="2" class="kh2-ga">{ta}</th></tr>'
                f'<tr><th>{L("designation", "Désignation")}</th><th class="r">{L("pu_ht", "P.U. HT")}</th><th class="r">{L("ci_tva_pct", "TVA %")}</th>'
                f'<th class="r">{L("qte", "Qté")}</th><th class="r">{L("total_ht", "Total HT")}</th>'
                f'<th class="r">{L("qte", "Qté")}</th><th class="r">{L("total_ht", "Total HT")}</th></tr>')
        colonnes = ('<colgroup><col><col style="width:22mm"><col style="width:12mm"><col style="width:11mm">'
                    '<col style="width:24mm"><col style="width:11mm"><col style="width:24mm"></colgroup>')
        tableau_deux = f'<table class="kh-tbl kh2-deux" style="margin-top:3.5mm;">{colonnes}{head}<tr class="orr"><td colspan="7"></td></tr>{rows}</table>'
        chaines = (f'<div class="kh-row" style="margin-top:4mm;"><div class="kh-col"><div class="kh2-tc">'
                   + commun.chaine_totaux_de(deux["totaux_sans"], p, L, ttc_marine=True, ttc_display=True,
                                             titre=L("ci_option_n_titre", "Option {n} — {o}", n=1, o=ts), pleine=True)
                   + '</div></div><div class="kh-gap" style="width:5mm;"></div><div class="kh-col"><div class="kh2-tc">'
                   + commun.chaine_totaux_de(deux["totaux_avec"], p, L, ttc_marine=True, ttc_display=True,
                                             titre=L("ci_option_n_titre", "Option {n} — {o}", n=2, o=ta), pleine=True)
                   + '</div></div></div>')
        corps_deux = tableau_deux + chaines
    css = f"""
<style>
.kh2-deux{{table-layout:fixed;}}
.kh2-deux td.r{{white-space:normal;}}
.kh2-gh th{{border-bottom:0 !important;padding-bottom:2px !important;}}
.kh2-gs{{text-align:center !important;background:{j['hero_bg']};color:#fff !important;border-radius:4px 4px 0 0;letter-spacing:.06em !important;}}
.kh2-ga{{text-align:center !important;background:{j['or']};color:{j['hero_bg']} !important;border-radius:4px 4px 0 0;letter-spacing:.06em !important;}}
.kh2-abs{{color:{j['muted']};}}
.kh2-vs{{color:{j['muted']};}}
.kh2-va{{color:{j['hero_bg']};font-weight:600;}}
.kh2-sp{{border:0.5pt solid {j['line']};border-radius:6px;overflow:hidden;background:#fff;}}
.kh2-sp-h{{font-size:8.4pt;font-weight:600;padding:6px 10px;}}
.kh2-sp-b{{padding:6px 10px;}}
.kh2-sp-li{{display:table;width:100%;font-size:7.8pt;line-height:1.4;padding:2px 0;border-bottom:0.5pt solid {j['line_soft']};}}
.kh2-sp-li > span{{display:table-cell;}}
.kh2-sp-t{{text-align:right;white-space:nowrap;font-weight:600;color:{j['hero_bg']};padding-left:6px;}}
.kh2-tc{{border:0.5pt solid {j['line']};border-top:3px solid {j['or']};border-radius:6px;padding:8px 10px;background:{j['wash']};}}
.kh2-tc .kh-tot-tbl{{font-size:8pt;}}
.kh2-ind{{margin-top:1mm;}}
.kh2-indv{{font-family:{j['display']};font-weight:600;font-size:22pt;line-height:1;letter-spacing:-.01em;color:{j['accent']};}}
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
  {corps_deux if deux else f'<div style="margin-top:3.5mm;">{tableau}</div>{totaux}'}{note}{clauses}{"" if deux else option_avec}{extras}
  {bloc_cat}
  {bref}
  {retour_html}
</div>"""
