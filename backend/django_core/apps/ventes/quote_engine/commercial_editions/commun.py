# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Système visuel commun des deux éditions : jetons (couleurs, polices,
grille) et fragments HTML/CSS partagés (tableau des équipements, chaîne de
totaux, garanties, échéancier, hypothèses, conditions, bon pour accord).

Doctrine (synthèse des lanes 01/04/07, 29/10/2026) : trois rôles
typographiques (titre / texte / légende), un seul chiffre-héros par page,
filets fins au lieu de cartes, une couleur d'accent porteuse de sens,
chiffres tabulaires alignés à droite, unités dites une fois, marges
asymétriques généreuses. CSS tables seulement (WeasyPrint, RENDERING_NOTES).
"""
from __future__ import annotations

from . import harnais

# ── Polices vendorisées (assets/fonts, OFL) ─────────────────────────────────
#: Famille logique → [(fichier, poids, style)]. Les fichiers manquants sont
#: ignorés (repli système) : le document se rend toujours.
POLICES = {
    "EdDisplay": [("Fraunces-300.ttf", 300, "normal"),
                  ("Fraunces-400.ttf", 400, "normal"),
                  ("Fraunces-300italic.ttf", 300, "italic")],
    "EdSans": [("IBMPlexSans-400.ttf", 400, "normal"),
               ("IBMPlexSans-500.ttf", 500, "normal"),
               ("IBMPlexSans-600.ttf", 600, "normal")],
    "EdArabe": [("IBMPlexSansArabic-400.ttf", 400, "normal"),
                ("IBMPlexSansArabic-600.ttf", 600, "normal")],
}

#: Piles : la police texte (Plex Sans, qui porte U+202F — le séparateur de
#: milliers de ``montants``) suit toujours la police d'affichage et la
#: police arabe, qui ne l'ont pas (mesuré fontTools, 29/10/2026).
SANS = "'EdSans','IBM Plex Sans','DM Sans',system-ui,sans-serif"
DISPLAY = "'EdDisplay','EdSans',Georgia,serif"
ARABE = "'EdArabe','EdSans','Noto Sans Arabic',sans-serif"


def fonts_css() -> str:
    return "".join(harnais.font_face(fam, f, p, s)
                   for fam, faces in POLICES.items() for f, p, s in faces)


# ── Palettes ────────────────────────────────────────────────────────────────
SIGNATURE = {
    "nom": "signature",
    "paper": "#FBFAF7", "ink": "#15191F", "muted": "#5F6670",
    "muted_2": "#8C939C", "line": "#D9D4CA", "line_soft": "#ECE8DF",
    "wash": "#F3F0E9", "accent": "#0F3D5C", "accent_soft": "#DCE7EE",
    "ochre": "#B7791F", "ochre_soft": "#F2E7CF", "green": "#2F7D4F",
    "marge": "18mm", "marge_g": "20mm", "haut": "18mm",
}

DIRECTE = {
    "nom": "directe",
    "paper": "#FBF7EF", "ink": "#1F1B16", "muted": "#6B6259",
    "muted_2": "#978D82", "line": "#E2D9C8", "line_soft": "#EFE8DA",
    "wash": "#F4EEE2", "accent": "#C0522B", "accent_soft": "#F6E0D5",
    "ochre": "#B7791F", "ochre_soft": "#F2E7CF", "green": "#2F7D4F",
    "marge": "16mm", "marge_g": "18mm", "haut": "16mm",
}


def jeton(palette: dict) -> dict:
    j = dict(palette)
    j.update({"fonts_css": fonts_css(), "sans": SANS, "display": DISPLAY,
              "arabe": ARABE})
    return j


# ── CSS partagée ────────────────────────────────────────────────────────────

def css_commune(j: dict, p: str) -> str:
    """Règles communes aux pages d'une édition ; ``p`` = préfixe de classes
    (« sg » / « dr »)."""
    return f"""
.{p}-root{{position:relative;width:210mm;height:297mm;overflow:hidden;
  padding:{j['haut']} {j['marge']} 0 {j['marge_g']};font-family:{j['sans']};
  color:{j['ink']};font-size:9pt;line-height:1.4;
  font-variant-numeric:tabular-nums lining-nums;
  font-feature-settings:"tnum" 1,"lnum" 1;}}
.{p}-root *{{box-sizing:border-box;}}
.{p}-ar{{font-family:{j['arabe']};direction:rtl;unicode-bidi:isolate;
  letter-spacing:0;line-height:1.55;}}
.{p}-kicker{{font-size:7pt;letter-spacing:.14em;text-transform:uppercase;
  color:{j['muted']};font-weight:500;}}
.{p}-h1{{font-family:{j['display']};font-weight:300;font-size:26pt;
  line-height:1.08;color:{j['ink']};letter-spacing:-.01em;}}
.{p}-h2{{font-family:{j['display']};font-weight:400;font-size:14.5pt;
  line-height:1.2;color:{j['ink']};}}
.{p}-h3{{font-size:9pt;font-weight:600;color:{j['ink']};}}
.{p}-cap{{font-size:7.2pt;color:{j['muted']};line-height:1.4;}}
.{p}-rule{{border-top:0.5pt solid {j['line']};}}
.{p}-rule-k{{border-top:1pt solid {j['ink']};}}
.{p}-tbl{{width:100%;border-collapse:collapse;}}
.{p}-tbl th{{text-align:left;font-size:6.8pt;letter-spacing:.08em;
  text-transform:uppercase;color:{j['muted']};font-weight:500;
  padding:0 0 5px 0;border-bottom:0.8pt solid {j['ink']};}}
.{p}-tbl th.r,.{p}-tbl td.r{{text-align:right;white-space:nowrap;}}
.{p}-tbl td{{padding:5px 0;border-bottom:0.5pt solid {j['line_soft']};
  vertical-align:top;font-size:8.6pt;}}
.{p}-tbl td.d{{padding-right:10px;}}
.{p}-mq{{display:block;font-size:6.8pt;color:{j['muted_2']};margin-top:1px;}}
.{p}-tbl tr.sec td{{font-size:6.8pt;letter-spacing:.08em;text-transform:uppercase;
  color:{j['muted']};font-weight:500;padding-top:9px;border-bottom:0.5pt solid {j['line']};}}
.{p}-tbl tr.note td{{font-style:italic;color:{j['muted']};}}
.{p}-tot{{display:table;width:100%;margin-top:4px;}}
.{p}-tot-sp{{display:table-cell;width:52%;vertical-align:top;}}
.{p}-tot-box{{display:table-cell;width:48%;vertical-align:top;}}
.{p}-tot-tbl{{width:100%;border-collapse:collapse;font-size:8.6pt;}}
.{p}-tot-tbl td{{padding:3px 0;color:{j['muted']};}}
.{p}-tot-tbl td:last-child{{text-align:right;white-space:nowrap;color:{j['ink']};}}
.{p}-tot-tbl tr.ttc td{{border-top:1pt solid {j['ink']};padding-top:6px;
  font-size:13pt;color:{j['ink']};font-weight:600;}}
.{p}-tot-tbl tr.ttc td:first-child{{font-size:8.6pt;font-weight:500;
  padding-top:10px;}}
.{p}-big{{font-family:{j['display']};font-weight:300;letter-spacing:-.02em;
  line-height:1;color:{j['ink']};font-variant-numeric:tabular-nums lining-nums;}}
.{p}-unit{{font-family:{j['sans']};font-weight:500;letter-spacing:0;}}
.{p}-lab{{font-size:7.6pt;color:{j['muted']};margin-top:3px;line-height:1.35;}}
.{p}-row{{display:table;width:100%;border-spacing:0;table-layout:fixed;}}
.{p}-col{{display:table-cell;vertical-align:top;}}
.{p}-gap{{display:table-cell;width:8mm;}}
.{p}-q{{display:none;}}
/* Bloc « Option avec batterie » (markup de ci.blocs.bloc_option_avec, classes c2-*) */
.c2-kicker{{font-size:7pt;letter-spacing:.14em;text-transform:uppercase;color:{j['muted']};font-weight:500;}}
.c2-tbl{{width:100%;border-collapse:collapse;font-size:8.4pt;}}
.c2-tbl th{{text-align:left;font-size:6.8pt;letter-spacing:.08em;text-transform:uppercase;color:{j['muted']};font-weight:500;padding:0 0 4px 0;border-bottom:0.8pt solid {j['ink']};}}
.c2-tbl td{{padding:4px 0;border-bottom:0.5pt solid {j['line_soft']};vertical-align:top;}}
.c2-rr,.c2-q,.c2-p,.c2-v,.c2-t{{text-align:right;white-space:nowrap;}}
.c2-tot-tbl{{border-collapse:collapse;font-size:8.4pt;}}
.c2-tot-tbl td{{padding:2px 8px 2px 0;}}
.c2-tot-ttc td{{font-weight:600;}}
"""


#: Paliers de densité ``(police tableau pt, padding px, police corps pt,
#: marge de section mm, hauteur signature mm)`` — palier 0 = nominal.
PALIERS = (None, (7.9, 3.5, 8.6, 3.5, 13), (7.3, 2.5, 8.2, 2.5, 11),
           (6.7, 1.6, 7.8, 1.8, 9))


def css_densite(p: str, j: dict, palier: int) -> str:
    """Surcharges CSS du palier ``palier`` ('' au palier 0)."""
    if not palier or palier >= len(PALIERS):
        return ""
    pt, pad, corps, marge, sig = PALIERS[palier]
    return (f"<style>.{p}-root{{font-size:{corps}pt;line-height:1.32;}}"
            f".{p}-tbl td{{padding:{pad}px 0;font-size:{pt}pt;}}"
            f".{p}-tbl th{{padding-bottom:{pad}px;}}"
            f".{p}-mq{{font-size:{max(pt - 1.2, 5.5):g}pt;}}"
            f".{p}-tot-tbl{{font-size:{pt}pt;}}.{p}-tot-tbl td{{padding:{max(pad - 1, 1):g}px 0;}}"
            f".{p}-tot-tbl tr.ttc td{{font-size:{pt + 4:g}pt;padding-top:{pad + 1:g}px;}}"
            f".{p}-cap{{font-size:{max(corps - 1.6, 6.2):g}pt;}}"
            f".{p}-lab{{font-size:{max(corps - 1.2, 6.4):g}pt;}}"
            f".{p}-h2{{font-size:{13 if palier == 1 else 12}pt;}}"
            f".sg3-sec,.dr2-sec,.dr3-sec,.sg2-duo,.sg2-retour{{margin-top:{marge}mm;padding-top:{max(marge - 1, 1.5):g}mm;}}"
            f".{p}-sig{{height:{sig}mm !important;}}"
            f".{p}-big{{font-size:{18 if palier == 1 else 16}pt !important;}}"
            "</style>")


def esc(v) -> str:
    import html
    return html.escape(str(v or ""), quote=True)


# ── Fragments ───────────────────────────────────────────────────────────────

def tableau_equipements(m: dict, p: str, j: dict, L, *, simple=False) -> str:
    """Le tableau des lignes (regroupées, remises par ligne) ; ``simple`` =
    désignation · quantité · total seulement (édition Directe), le P.U. HT
    et le taux restant sur la page des conditions."""
    rows = ""
    for kind, it in m["lignes"]:
        if kind == "struct":
            if it["type"] == "note":
                rows += f'<tr class="note"><td colspan="5">{it["texte"]}</td></tr>'
            else:
                rows += f'<tr class="sec"><td colspan="5">{it["texte"]}</td></tr>'
            continue
        marque = f'<span class="{p}-mq">{esc(it["marque"])}</span>' if it["marque"] else ""
        pu = (f'<span style="text-decoration:line-through;opacity:.55;">'
              f'{it["pu_cat"]}</span> ' if it["pu_cat"] else "") + it["pu_ht"]
        if simple:
            rows += (f'<tr><td class="d">{it["designation"]}{marque}{it["sous_lignes"]}</td>'
                     f'<td class="r">{it["qte"]}</td>'
                     f'<td class="r">{it["total"]}</td></tr>')
        else:
            rows += (f'<tr><td class="d">{it["designation"]}{marque}{it["sous_lignes"]}</td>'
                     f'<td class="r">{it["qte"]}</td><td class="r">{pu}</td>'
                     f'<td class="r">{it["taux"]}</td><td class="r">{it["total"]}</td></tr>')
    if m["hors_total"]:
        rows += (f'<tr class="sec"><td colspan="5">'
                 + L("ci_postes_hors_total",
                     "Postes à chiffrer après la visite technique (hors total)")
                 + '</td></tr>')
        mention = L("ci_a_chiffrer_apres_visite", "à chiffrer après la visite technique")
        for nom, qte in m["hors_total"]:
            rows += (f'<tr><td class="d">{nom}</td><td class="r">{qte}</td>'
                     f'<td class="r" colspan="{1 if simple else 3}" style="font-style:italic;'
                     f'color:{j["muted"]};">{mention}</td></tr>')
    if simple:
        head = (f'<tr><th>{L("designation", "Désignation")}</th>'
                f'<th class="r">{L("qte", "Qté")}</th>'
                f'<th class="r">{L("total_ht", "Total HT")} (MAD)</th></tr>')
    else:
        head = (f'<tr><th>{L("designation", "Désignation")}</th>'
                f'<th class="r">{L("qte", "Qté")}</th>'
                f'<th class="r">{L("pu_ht", "P.U. HT")}</th>'
                f'<th class="r">{L("ci_tva_pct", "TVA %")}</th>'
                f'<th class="r">{L("total_ht", "Total HT")} (MAD)</th></tr>')
    return f'<table class="{p}-tbl">{head}{rows}</table>'


def chaine_totaux(m: dict, p: str, L) -> str:
    t = m["totaux"]
    remise = (f'<tr><td>{L("remise", "Remise")}{t["ancre_remise"]}</td>'
              f'<td>− {t["remise"]}</td></tr>' if t["remise"] else "")
    arrondi = (f'<tr><td>{L("arrondi", "Arrondi commercial")}{t["ancre_arrondi"]}</td>'
               f'<td>− {t["arrondi"]}</td></tr>' if t["arrondi"] else "")
    return (f'<div class="{p}-tot"><div class="{p}-tot-sp"></div>'
            f'<div class="{p}-tot-box"><table class="{p}-tot-tbl">'
            f'<tr><td>{L("sous_total_ht", "Sous-total HT")}{t["ancre_ht_brut"]}</td><td>{t["ht_brut"]}</td></tr>'
            f'{remise}{arrondi}'
            f'<tr><td>{L("total_ht", "Total HT")}{t["ancre_ht_net"]}</td><td>{t["ht_net"]}</td></tr>'
            f'<tr><td>{L("tva", "TVA")}{t["ancre_tva"]}</td><td>{t["tva"]}</td></tr>'
            f'<tr class="ttc"><td>{L("total_ttc", "Total TTC")}{t["ancre_ttc"]}</td>'
            f'<td>{t["ttc"]}<span style="font-size:8pt;font-weight:500;"> MAD</span></td></tr>'
            f'</table></div></div>')


def options_et_injection(m: dict, p: str, j: dict, L) -> str:
    html = ""
    if m["options"]:
        rows = "".join(
            f'<tr><td class="d">{q}{des}</td><td class="r">{taux}</td>'
            f'<td class="r">{ht} {L("ci_ht", "HT")}'
            f'<span class="{p}-mq">{ttc} {L("ci_ttc", "TTC")}</span></td></tr>'
            for q, des, taux, ht, ttc in m["options"])
        html += (f'<div style="margin-top:9px;"><div class="{p}-kicker">'
                 + L("ci_options_proposees", "Options propos&eacute;es (non incluses dans le total)")
                 + f'</div><table class="{p}-tbl" style="margin-top:4px;">'
                 f'<tr><th>{L("designation", "D&eacute;signation")}</th>'
                 f'<th class="r">{L("ci_tva_pct", "TVA %")}</th>'
                 f'<th class="r">{L("total_ht", "Total HT")}</th></tr>{rows}</table></div>')
    if m["injection"]:
        montant, mentions = m["injection"]
        html += (f'<div style="margin-top:8px;font-size:8pt;line-height:1.4;">'
                 f'<b style="color:{j["green"]};">+ {montant} {L("ci_mad_an", "MAD/an")}</b> — '
                 + L("ci_surplus_injecte", "surplus injecté")
                 + f'. <span class="{p}-cap">{mentions}</span></div>')
    return html


def garanties_rangee(m: dict, p: str, j: dict, L, taille_pt=20) -> str:
    """Les garanties servies en une rangée de grands nombres légers."""
    if not m["garanties"]:
        return ""
    cellules = "".join(
        f'<div class="{p}-col" style="padding-right:6mm;">'
        f'<div class="{p}-big" style="font-size:{taille_pt}pt;">{n}'
        f'<span class="{p}-unit" style="font-size:8pt;color:{j["muted"]};"> {u}</span></div>'
        f'<div class="{p}-lab">{lib}</div></div>'
        for n, u, lib in m["garanties"])
    from ..ci.blocs import legende_garanties
    return (f'<div class="{p}-row">{cellules}</div>'
            f'<div class="{p}-cap" style="margin-top:5px;">{legende_garanties(m["d"])}</div>')


def echeancier_rangee(m: dict, p: str, j: dict, L) -> str:
    if not m["echeancier"]:
        return ""
    ttc = L("ci_ttc", "TTC")
    cellules = ""
    for i, (pct, lib, montant) in enumerate(m["echeancier"]):
        cellules += (
            f'<div class="{p}-col" style="padding-right:6mm;border-top:0.5pt solid {j["line"]};padding-top:5px;">'
            f'<div style="font-size:13pt;font-weight:500;">{pct}&nbsp;%</div>'
            f'<div style="font-size:8pt;margin-top:1px;">{lib}</div>'
            + (f'<div class="{p}-cap" style="margin-top:1px;">{montant} MAD {ttc}</div>' if montant else "")
            + '</div>')
    return f'<div class="{p}-row">{cellules}</div>'


def hypotheses_tableau(m: dict, p: str, j: dict, L, colonnes=2) -> str:
    """« Bases du calcul » (AMOT91) en 1 ou 2 colonnes, petite typographie."""
    rangees = [(lib, val) for lib, val in m["hypotheses"] if val]
    if not rangees:
        return ""
    def _cell(lib, val):
        return (f'<tr><td style="color:{j["muted"]};width:38%;padding:2px 6px 2px 0;'
                f'border-bottom:0.5pt solid {j["line_soft"]};vertical-align:top;">{lib or ""}</td>'
                f'<td style="padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};">{val}</td></tr>')
    if colonnes == 1:
        return (f'<table style="width:100%;border-collapse:collapse;font-size:7pt;line-height:1.35;">'
                + "".join(_cell(*r) for r in rangees) + '</table>')
    moitie = (len(rangees) + 1) // 2
    g = "".join(_cell(*r) for r in rangees[:moitie])
    d_ = "".join(_cell(*r) for r in rangees[moitie:])
    return (f'<div class="{p}-row"><div class="{p}-col">'
            f'<table style="width:100%;border-collapse:collapse;font-size:7pt;line-height:1.35;">{g}</table>'
            f'</div><div class="{p}-gap"></div><div class="{p}-col">'
            f'<table style="width:100%;border-collapse:collapse;font-size:7pt;line-height:1.35;">{d_}</table>'
            f'</div></div>')


def conditions_bloc(m: dict, p: str, j: dict) -> str:
    titre, puces = m["conditions"]
    if not puces:
        return ""
    items = "".join(f'<li style="margin-top:1px;">{pu}</li>' for pu in puces)
    return (f'<div class="{p}-h3" style="margin-top:9px;">{titre}</div>'
            f'<ul class="{p}-cap" style="margin:3px 0 0 0;padding-left:11px;'
            f'color:{j["ink"]};">{items}</ul>')


def bon_pour_accord(m: dict, p: str, j: dict, L, haut_mm=22) -> str:
    """Le bloc d'acceptation en style CONTRAT (deux colonnes, filets,
    cadres signature/cachet), à partir des champs servis (CIQ320)."""
    a = m["acceptation"]
    lignes = "".join(
        f'<div style="margin-top:4px;">{lib}&#160;: '
        + (f'<b>{val}</b>' if val else
           f'<span style="display:inline-block;width:48mm;border-bottom:0.5pt dotted {j["line"]};">&#160;</span>')
        + '</div>' for lib, val in a["lignes"])
    cases = "".join(
        f'<div style="margin-top:4px;"><span style="display:inline-block;width:3mm;height:3mm;'
        f'border:0.8pt solid {j["ink"]};vertical-align:middle;margin-right:2mm;">&#160;</span>{c}</div>'
        for c in a["cases"])
    cadre = (f'display:table-cell;width:50%;vertical-align:top;'
             f'border:0.5pt solid {j["line"]};padding:3px 5px;font-size:6.5pt;color:{j["muted"]};')
    cadres = (f'<div style="display:table;width:100%;border-spacing:3mm 0;margin:6px -3mm 0 -3mm;">'
              f'<div class="{p}-sig" style="{cadre}">{a["signature"]}</div>'
              f'<div class="{p}-sig" style="{cadre}">{a["cachet"]}</div></div>'
              f'<style>.{p}-sig{{height:{haut_mm}mm;}}</style>')
    signe = ""
    if a["accepte_nom"] and a["date_acceptation"]:
        signe = (f'<div style="margin-top:6px;font-size:10pt;font-weight:600;">{a["accepte_nom"]}</div>'
                 f'<div class="{p}-cap">{L("ci_le_date", "Le {date}", date=a["date_acceptation"])}</div>')
    gauche = (f'<div class="{p}-kicker">{a["titre"]} — {a["pour"]}</div>'
              f'<div style="font-size:7.4pt;line-height:1.35;">{cases}{lignes}{cadres}'
              f'<div style="margin-top:4px;font-style:italic;color:{j["muted"]};">{a["mention"]}</div>'
              f'{signe}</div>')
    droite = (f'<div class="{p}-kicker">{L("ci_pour", "Pour {marque}", marque=m["brand"])}</div>'
              f'<div class="{p}-sig" style="margin-top:6px;border:0.5pt solid {j["line"]};"></div>'
              f'<div class="{p}-cap" style="margin-top:5px;">{m["ligne_vendeur"]}</div>')
    return (f'<div class="{p}-row" style="margin-top:10px;border-top:1pt solid {j["ink"]};padding-top:7px;">'
            f'<div class="{p}-col" style="width:58%;">{gauche}</div><div class="{p}-gap"></div>'
            f'<div class="{p}-col">{droite}</div></div>')


def bande_legale(m: dict, p: str, j: dict) -> str:
    return (f'<div class="{p}-cap" style="margin-top:7px;font-size:6.6pt;color:{j["muted_2"]};">'
            f'{m["bande_legale"]}</div>')


def logo(ctx, hauteur_mm=8, sombre=True) -> str:
    b64 = ctx["logo_dark"] if sombre else ctx["logo_color"]
    if not b64:
        return ""
    return (f'<img src="data:image/png;base64,{b64}" alt="" '
            f'style="height:{hauteur_mm}mm;width:auto;display:block;">')
