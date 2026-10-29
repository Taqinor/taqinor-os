# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Directe — PAGE 1 : « Ce que vous gagnez ».

Photo réelle, le projet, UN chiffre-héros (économie de l'année 1 servie),
votre facture avant / après en deux barres, la part couverte en
pictogrammes + nombre, le prix clé en main et ses jalons, le retour, un
numéro à appeler. Libellés FR du catalogue, doublés en arabe quand le
catalogue porte la traduction (jamais une traduction écrite ici).
Classes ``dr1-``.
"""
import re

from .. import commun, donnees, graphiques
from ...figures import ancre
from ...residential import theme


def bil(d, cle, fr, p="dr", **v):
    """« libellé FR » + « libellé AR » (catalogue) sur une rangée."""
    fr_txt = donnees.L(d, cle, fr, **v)
    ar_txt = donnees.ar(cle, fr)
    if ar_txt and v:
        try:
            ar_txt = ar_txt.format(**v)
        except (KeyError, IndexError):
            pass
    if not ar_txt or donnees.ci_blocs.langue(d) != "fr":
        return fr_txt
    return (f'<span class="{p}-fr">{fr_txt}</span>'
            f'<span class="{p}-ar">{ar_txt}</span>')


def build(ctx, m, j):
    d, p = m["d"], "dr"
    fmt = m["fmt"]
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    B = lambda cle, fr, **v: bil(d, cle, fr, p, **v)
    c, inv, cl, cat = m["chiffres"], m["invest"], m["client"], m["categorie"]
    ident = m["ident"]
    photo = theme.hero_image_b64(d.get("com_kwc"), "commercial")
    logo = commun.logo(ctx, 9, sombre=True)

    validite = (L("ci_valable_jusqu", "Valable jusqu&#8217;au {date}", date=m["valid_until"])
                if m["valid_until"] else "")
    corrections = "".join(f'<div class="dr1-hd">{x}</div>' for x in m["marques_correction"])
    entete = (
        f'<div class="dr1-photo" style="background-image:url(data:image/jpeg;base64,{photo});"></div>'
        f'<div class="dr1-voile"></div>'
        f'<div class="dr1-entete"><div class="dr1-elogo">{logo}</div>'
        f'<div class="dr1-emeta"><div class="dr1-rl">{L("ci_ref_devis", "Réf. devis")}</div>'
        f'<div class="dr1-rv">{m["ref"]}</div><div class="dr1-hd">{m["date"]}'
        + (f' &nbsp;·&nbsp; {validite}' if validite else '') + f'</div>{corrections}</div></div>')

    titre = donnees.ci_couverture.titre_projet(d, "com", c["kwc"], cl["nom"])
    if " — " in titre and m["langue"] != "ar":
        avant, apres = titre.split(" — ", 1)
        titre = f'{apres}<br><span style="color:{j["muted"]};">{avant}</span>'
    ligne_client = re.sub(r'<div class="dr1-int".*?</div>', "", donnees.ci_couverture.ligne_client(
        d, "com", cl["nom"], cl["meta"], "dr1"), flags=re.S)

    bandeau = donnees.bandeau_reserve(d, "dr1")
    reserve = f'<div class="dr1-reserve">{bandeau}</div>' if bandeau else ""

    # ── Chiffre-héros ─────────────────────────────────────────────────────
    if m["deux_options"]:
        # A5 (CPDF3) — les cartes disent l'argent de chaque option.
        hero_lab = B("ci_production_annuelle", "Production annuelle")
        hero = (f'<div class="dr1-hero">{c["production"] or "—"}<span class="dr1-hunit">'
                + L("ci_unite_kwh_an", "&nbsp;kWh/an") + '</span></div>'
                + (ancre("production_annuelle_kwh", c["production"]) if c["production"] else ""))
        hero_cap = ""
    elif c["economies"] is not None:
        hero_lab = B("ci_economies_estimees", "Économies estimées / an") + \
            (f' <span class="dr-cap">({c["economies_base"]})</span>' if c["economies_base"] else "")
        hero = (f'<div class="dr1-hero">{c["economies"]}<span class="dr1-hunit">&nbsp;MAD</span></div>'
                + ancre("economie_annuelle", c["economies"]))
        hero_cap = c["economies_ttc"] or ""
        if c["postes_hors_total"]:
            hero_cap = (L("ci_retour_prix_complet", "retour calculé sur le prix "
                          "complet, après la visite") + (f" · {hero_cap}" if hero_cap else ""))
    else:
        hero_lab = B("ci_puissance_crete", "Puissance crête")
        hero = (f'<div class="dr1-hero">{c["kwc"]}<span class="dr1-hunit">'
                + L("res_unite_kwc", "&nbsp;kWc") + '</span></div>' + ancre("puissance_kwc", c["kwc"]))
        hero_cap = c["motif_non_chiffre"] or c["motif_investissement"] or ""

    facture = ""
    if m["facture"] and not m["deux_options"] and c["part_facture_pct"]:
        f = m["facture"]
        svg = graphiques.facture_avant_apres(
            f["avant_num"], f["apres_num"],
            (L("ci_facture_sans_solaire", "Sans solaire"), L("ci_facture_avec_solaire", "Avec solaire"),
             "", "", f'−{c["part_facture_pct"]}&#160;%'),
            (j["ink"], j["accent"], j["line"], j["ink"]), "IBM Plex Sans", 150 - 8 * m["palier"], 30 - 3 * m["palier"])
        facture = (f'<div class="dr-lab2">'
                   + L("ci_facture_energie_an1", "Votre facture d&#8217;énergie, année 1")
                   + f' ({f["unite"]})</div><div style="margin-top:2mm;">{svg}</div>')

    couverture = ""
    if c["couverture"] is not None and not m["deux_options"]:
        picto = graphiques.pictogrammes(float(c["couverture"]), (j["accent"], j["line"]), 70 - 8 * m["palier"])
        couverture = (f'<div class="dr-row dr1-couv"><div class="dr-col" style="width:40%;">'
                      f'<div class="dr1-mid">{c["couverture"]}<span class="dr1-munit">&nbsp;%</span></div>'
                      + ancre("couverture_pct", c["couverture"])
                      + f'<div class="dr-lab2">{B("ci_part_conso_couverte", "Part de votre consommation couverte")}</div></div>'
                      f'<div class="dr-col" style="vertical-align:middle;">{picto}'
                      f'<div class="dr-cap" style="margin-top:2mm;">{c["note_pointe"] or ""}</div></div></div>')

    # ── Prix + jalons + retour ────────────────────────────────────────────
    if m["deux_options"]:
        from ...ci import options_cote
        prix = options_cote.cartes_options(d, "com", "dr1", fmt, m["fmt_mad"], d.get("_invest_ttc") or 0)
    else:
        prix = (f'<div class="dr-row"><div class="dr-col" style="width:55%;vertical-align:bottom;">'
                f'<div class="dr-lab2">{inv["titre"]}</div>'
                f'<div class="dr1-prix">{inv["montant"]}<span class="dr1-punit">&nbsp;MAD'
                + (f'&nbsp;{inv["unite"]}' if inv["unite"] else "") + f'</span></div>{inv["ancre"]}'
                + (f'<div class="dr-cap">{inv["secondaire"]}' + (f' · {inv["note"]}' if inv["note"] else "") + '</div>'
                   if inv["secondaire"] else "")
                + '</div><div class="dr-gap"></div><div class="dr-col" style="vertical-align:bottom;">')
        if c["payback"]:
            prix += (f'<div class="dr-lab2">{B("ci_retour_estime", "Retour estimé")} '
                     f'<span class="dr-cap">({c["payback_base"]})</span></div>'
                     f'<div class="dr1-mid">{c["payback"]}<span class="dr1-munit">{c["payback_unite"]}</span></div>'
                     + ancre("payback_ans", c["payback"]))
        elif c["motif_investissement"]:
            prix += f'<div class="dr-cap">{c["motif_investissement"]}</div>'
        prix += '</div></div>'
    jalons = ""
    if m["echeancier"]:
        cells = "".join(
            f'<div class="dr-col dr1-jal"><div class="dr1-jpct">{pct}&nbsp;%</div>'
            f'<div style="font-size:8.5pt;">{lib}</div>'
            + (f'<div class="dr-cap">{mt} MAD {L("ci_ttc", "TTC")}</div>' if mt else "") + '</div>'
            for pct, lib, mt in m["echeancier"])
        jalons = (f'<div class="dr-lab2" style="margin-top:4mm;">{B("ci_cpdf_echeancier", "Échéancier de paiement")}</div>'
                  f'<div class="dr-row" style="margin-top:1.5mm;">{cells}</div>')

    # ── Contact ───────────────────────────────────────────────────────────
    uri, lien = m["qr"]
    tel = ident.get("phone") or ""
    lab_contact = (B("ci_votre_interlocuteur", "Votre interlocuteur") if cl["interlocuteur"]
                   else B("ci_pour_nous_joindre", "Pour nous joindre"))
    contact = (f'<div class="dr-row dr1-contact"><div class="dr-col" style="vertical-align:middle;">'
               f'<div class="dr-lab2">{lab_contact}</div>'
               + (cl["interlocuteur"].replace("x-int", "dr1-int") if cl["interlocuteur"] else
                  f'<div style="margin-top:1mm;"><b>{m["brand"]}</b>'
                  + (f' &nbsp;·&nbsp; <span class="dr1-tel">{tel}</span>' if tel else "") + '</div>')
               + (f'<div class="dr-cap">{L("ci_proposition_en_ligne", "Votre proposition en ligne")} · {commun.esc(lien)}</div>' if uri else "")
               + '</div>'
               + (f'<div class="dr-col" style="width:22mm;text-align:right;"><img src="{uri}" style="width:19mm;height:19mm;" alt="QR"></div>' if uri else "")
               + '</div>')

    css = f"""
<style>
.dr1-photo{{position:absolute;left:0;top:0;width:210mm;height:58mm;background-size:cover;background-position:center 42%;}}
.dr1-voile{{position:absolute;left:0;top:0;width:210mm;height:58mm;background:#2A1A10;opacity:.40;}}
.dr1-entete{{position:absolute;left:{j['marge_g']};right:{j['marge']};top:11mm;display:table;width:176mm;color:#fff;}}
.dr1-elogo{{display:table-cell;vertical-align:top;}}
.dr1-emeta{{display:table-cell;vertical-align:top;text-align:right;}}
.dr1-rl{{font-size:6.8pt;letter-spacing:.14em;text-transform:uppercase;opacity:.85;}}
.dr1-rv{{font-size:11.5pt;font-weight:600;}}
.dr1-hd{{font-size:7.6pt;opacity:.9;margin-top:1px;}}
.dr1-corps{{padding-top:48mm;}}
.dr1-titre{{font-family:{j['display']};font-weight:400;font-size:21pt;line-height:1.12;}}
.dr1-acc{{margin-top:2.5mm;font-size:10pt;color:{j['muted']};max-width:140mm;line-height:1.45;}}
.dr1-client{{margin-top:2mm;font-size:8pt;color:{j['muted']};}}
.dr1-reserve{{margin-top:4mm;padding:5px 0 5px 10px;border-left:2.5pt solid {j['ochre']};font-size:8.6pt;font-weight:500;}}
.dr1-heroblk{{margin-top:4.5mm;}}
.dr1-hero{{font-family:{j['display']};font-weight:400;font-size:{48 - 4 * m['palier']}pt;line-height:1;letter-spacing:-.02em;color:{j['accent']};margin-top:2mm;}}
.dr1-hunit{{font-family:{j['sans']};font-size:13pt;font-weight:600;color:{j['ink']};letter-spacing:0;}}
.dr1-mid{{font-family:{j['display']};font-weight:400;font-size:26pt;line-height:1;letter-spacing:-.01em;}}
.dr1-munit{{font-family:{j['sans']};font-size:9pt;font-weight:600;color:{j['muted']};}}
.dr1-couv{{margin-top:4mm;padding-top:3mm;border-top:0.5pt solid {j['line']};}}
.dr1-prixblk{{margin-top:4mm;padding-top:3mm;border-top:1pt solid {j['ink']};}}
.dr1-prix{{font-family:{j['display']};font-weight:400;font-size:30pt;line-height:1;letter-spacing:-.015em;margin-top:1mm;}}
.dr1-punit{{font-family:{j['sans']};font-size:10pt;font-weight:600;color:{j['muted']};}}
.dr1-jal{{padding:4px 5mm 0 0;border-top:0.5pt solid {j['line']};}}
.dr1-jpct{{font-size:14pt;font-weight:600;color:{j['accent']};}}
.dr1-contact{{margin-top:4mm;padding-top:3mm;border-top:0.5pt solid {j['line']};font-size:10pt;}}
.dr1-tel{{font-size:13pt;font-weight:600;color:{j['accent']};}}
.dr1-meth{{margin-top:3mm;font-size:6.9pt;color:{j['muted']};line-height:1.45;}}
{__import__('apps.ventes.quote_engine.ci.options_cote', fromlist=['css_options']).css_options('dr1', (j['line'], j['wash'], j['muted'], j['accent'], j['ink'], j['ochre']), 10) if m['deux_options'] else ''}
</style>"""
    return f"""{css}
<div class="dr-root">
  {entete}
  <div class="dr1-corps">
    <div class="dr-kicker">{(cat["label"] + " &nbsp;·&nbsp; ") if cat["label"] else ""}{L("ci_kicker_autoconso_commerciale", "Autoconsommation solaire commerciale")}</div>
    <div class="dr1-titre" style="margin-top:1.5mm;">{titre}</div>
    <div class="dr1-acc">{cat["accroche"]}</div>
    <div class="dr1-client">{ligne_client}</div>
    {reserve}
    <div class="dr1-heroblk">
      <div class="dr-lab2">{hero_lab}</div>{hero}
      <div class="dr-cap" style="margin-top:2px;">{hero_cap}</div>
    </div>
    <div style="margin-top:4mm;">{facture}</div>
    {couverture}
    <div class="dr1-prixblk">{prix}{jalons}</div>
    {contact}
  </div>
</div>"""
