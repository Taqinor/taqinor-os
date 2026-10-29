# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Système visuel commun des trois éditions — direction « Khatam : zellige
discret, marine et or » (panel du 29/10/2026 : 4 directions, 3 juges,
synthèse `scratchpad/panel/synthese.md`).

Une seule marque : marine #0F2345 en aplats tramés d'un carreau khatam
(étoile à huit branches au trait, jamais par opacité), or #C9A04E en filets
et losanges seulement (jamais en texte sur papier : 2,3:1), bleu royal
#1E4A8C réservé aux DONNÉES (chiffre-héros, barres, courbe), laiton
#7A5C1E comme seul or lisible en texte sur papier. Fraunces 400 pour les
grands chiffres et titres (réponse au « trop léger »), IBM Plex Sans pour le
corps (chiffres tabulaires par défaut), IBM Plex Sans Arabic pour l'arabe du
catalogue. CSS tables seulement (WeasyPrint) ; ni dégradé, ni ombre, ni
opacité, ni clipPath.
"""
from __future__ import annotations

import base64
import re

from . import harnais

# ── Polices vendorisées (assets/fonts, OFL, TTF statiques) ─────────────────
POLICES = {
    "EdDisplay": [("Fraunces-300.ttf", 300, "normal"),
                  ("Fraunces-400.ttf", 400, "normal"),
                  ("Fraunces-600.ttf", 600, "normal"),
                  ("Fraunces-700.ttf", 700, "normal"),
                  ("Fraunces-300italic.ttf", 300, "italic")],
    "EdSans": [("IBMPlexSans-400.ttf", 400, "normal"),
               ("IBMPlexSans-500.ttf", 500, "normal"),
               ("IBMPlexSans-600.ttf", 600, "normal")],
    "EdArabe": [("IBMPlexSansArabic-400.ttf", 400, "normal"),
                ("IBMPlexSansArabic-600.ttf", 600, "normal")],
}

#: Plex Sans suit toujours Fraunces et Plex Arabic : il porte U+202F, le
#: séparateur de milliers du moteur, qu'elles n'ont pas (mesuré fontTools).
SANS = "'EdSans','IBM Plex Sans','DM Sans',system-ui,sans-serif"
DISPLAY = "'EdDisplay','EdSans',Georgia,serif"
ARABE = "'EdArabe','EdSans','Noto Sans Arabic',sans-serif"


def fonts_css() -> str:
    return "".join(harnais.font_face(fam, f, p, s)
                   for fam, faces in POLICES.items() for f, p, s in faces)


# ── Palette Khatam (contrastes WCAG mesurés, synthèse §1.1) ────────────────
_KHATAM = {
    "ink": "#14213D", "muted": "#5A6274", "muted_2": "#5A6274",
    "hero_bg": "#0F2345", "hero_fg": "#FFFFFF", "on_hero": "#FFFFFF",
    "on_hero_2": "#C9D2E2", "on_hero_3": "#B4C2DA",
    # Critique 29/10 (lentille marocaine) : l'accent de DONNÉES est le vert
    # zellige de Fès #0E6B53 (6,2:1 sur blanc), l'or s'aligne sur le soleil du
    # logo, la trame khatam devient lisible (≈ 2:1 sur le marine).
    "accent": "#0E6B53", "accent_soft": "#DCEDE6", "data_soft": "#E3EFEA",
    "or": "#D4A853", "or_texte": "#F0BE56", "laiton": "#7A5C1E",
    "ochre": "#D4A853", "ochre_soft": "#F3E6C6", "point_logo": "#F5A623",
    "green": "#0E6B53", "vert": "#0E6B53", "sable": "#EEE9DD",
    "bar_conso": "#DCE3EE", "bar_sans": "#9AA5B8",
    "motif_11": "#3C5280", "motif_8": "#2F4470", "galon": "#D4A853",
}

SIGNATURE = dict(_KHATAM, nom="signature", paper="#FFFFFF", line="#D9DCE3",
                 line_soft="#E8EAEF", wash="#F3F4F7", pied="plein",
                 marge="20mm", marge_g="20mm", haut="22mm")
NORMALE = dict(_KHATAM, nom="normale", paper="#FFFFFF", line="#D9DCE3",
               line_soft="#E8EAEF", wash="#F3F4F7", pied="plein",
               marge="20mm", marge_g="20mm", haut="18mm")
BASIQUE = dict(_KHATAM, nom="basique", paper="#FFFFFF", line="#D9DCE3",
               line_soft="#E8EAEF", wash="#F3F4F7", pied="filet",
               marge="20mm", marge_g="20mm", haut="18mm")


def jeton(palette: dict) -> dict:
    j = dict(palette)
    j.update({"fonts_css": fonts_css(), "sans": SANS, "display": DISPLAY,
              "arabe": ARABE})
    return j


# ── Motif khatam (synthèse §2) ──────────────────────────────────────────────
KHATAM_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">'
    '<g fill="none" stroke="{COULEUR}" stroke-width="{TRAIT}" stroke-linejoin="miter">'
    '<path d="M20 0 L25.86 5.86 L34.14 5.86 L34.14 14.14 L40 20 L34.14 25.86 L34.14 34.14 '
    'L25.86 34.14 L20 40 L14.14 34.14 L5.86 34.14 L5.86 25.86 L0 20 L5.86 14.14 L5.86 5.86 L14.14 5.86Z"/>'
    '<path d="M23.22 12.22 L27.78 16.78 L27.78 23.22 L23.22 27.78 L16.78 27.78 L12.22 23.22 '
    'L12.22 16.78 L16.78 12.22Z"/>'
    '<path d="M25.86 5.86L23.22 12.22M34.14 14.14L27.78 16.78M34.14 25.86L27.78 23.22'
    'M25.86 34.14L23.22 27.78M14.14 34.14L16.78 27.78M5.86 25.86L12.22 23.22'
    'M5.86 14.14L12.22 16.78M14.14 5.86L16.78 12.22"/></g></svg>')
#: Le premier chemin du carreau : l'étoile à huit branches.
ETOILE_D = ("M20 0 L25.86 5.86 L34.14 5.86 L34.14 14.14 L40 20 L34.14 25.86 L34.14 34.14 "
            "L25.86 34.14 L20 40 L14.14 34.14 L5.86 34.14 L5.86 25.86 L0 20 L5.86 14.14 "
            "L5.86 5.86 L14.14 5.86Z")
#: Le second chemin : l'octogone intérieur.
OCTOGONE_D = ("M23.22 12.22 L27.78 16.78 L27.78 23.22 L23.22 27.78 L16.78 27.78 "
              "L12.22 23.22 L12.22 16.78 L16.78 12.22Z")


def motif_uri(couleur: str, trait: str = ".4") -> str:
    """``url(data:image/svg+xml;base64,…)`` du carreau en couleur pleine
    pré-mélangée (jamais d'opacité CSS : rendu SVG stable dans WeasyPrint)."""
    svg = KHATAM_SVG.replace("{COULEUR}", couleur).replace("{TRAIT}", trait)
    return "url(data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode() + ")"


def css_motif(couleur: str, carreau_mm: float, trait: str = ".7",
              repeat: str = "repeat") -> str:
    """La trame en fond, rognée à la boîte de remplissage (jamais sous un
    filet : les débordements lisaient comme des traits de coupe)."""
    return (f"background-image:{motif_uri(couleur, trait)};"
            f"background-size:{carreau_mm:g}mm {carreau_mm:g}mm;background-repeat:{repeat};"
            f"background-clip:padding-box;background-origin:padding-box;background-position:0 0;")


def losange(couleur: str, mm: float = 2.2, marge_droite_mm: float = 1.6) -> str:
    """La petite étoile khatam or qui ouvre une capitale ou un filet
    (critique 29/10 : le losange était générique)."""
    return (f'<svg width="{mm:g}mm" height="{mm:g}mm" viewBox="0 0 40 40" '
            f'style="display:inline-block;vertical-align:middle;margin-right:{marge_droite_mm:g}mm;">'
            f'<path d="{ETOILE_D}" fill="{couleur}"/></svg>')


def etoile(couleur: str, mm: float = 3.0, pleine: bool = False, trait: float = 2.2) -> str:
    """L'étoile khatam seule : pleine (point de retour) ou au trait (séparateur)."""
    attrs = f'fill="{couleur}"' if pleine else f'fill="none" stroke="{couleur}" stroke-width="{trait:g}"'
    return (f'<svg width="{mm:g}mm" height="{mm:g}mm" viewBox="0 0 40 40" '
            f'style="display:inline-block;vertical-align:middle;"><path d="{ETOILE_D}" {attrs}/></svg>')


def octogone(n, couleur_trait: str, couleur_texte: str, police: str, mm: float = 5.5) -> str:
    """Le numéro d'étape dans l'octogone khatam au trait or."""
    return (f'<svg width="{mm:g}mm" height="{mm:g}mm" viewBox="10 10 20 20" style="display:block;">'
            f'<path d="{OCTOGONE_D}" fill="none" stroke="{couleur_trait}" stroke-width=".9"/>'
            f'<text x="20" y="23.3" text-anchor="middle" font-family="{police}" font-weight="400" '
            f'font-size="9.5" fill="{couleur_texte}">{n}</text></svg>')


def fenetre_arc(photo_b64: str, fond: str, or_: str, left_mm=136, top_mm=30,
                largeur_mm=54, hauteur_mm=76) -> str:
    """La fenêtre en arc plein cintre de la photo (synthèse §2.3) : la photo
    en bloc rectangulaire, puis un SVG qui ne remplit que les deux écoinçons
    de la couleur du bandeau et trace le cadre or ; sans photo, le cadre
    seul, jamais une image de remplacement."""
    svg_left, svg_top = left_mm - 3, top_mm - 3
    # Arc outrepassé (fer à cheval) : rayon 28, centre (30, 33), naissances
    # à y = 42,6 où l'ouverture se resserre à 52,6 de large (critique 29/10).
    arche = "M3.7 79V42.6A28 28 0 1 1 56.3 42.6V79"
    cadre = "M1.9 79V43.2A29.8 29.8 0 1 1 58.1 43.2V79"
    if photo_b64:
        photo = (f'<div style="position:absolute;left:{left_mm}mm;top:{top_mm}mm;width:{largeur_mm}mm;'
                 f'height:{hauteur_mm}mm;background-image:url(data:image/jpeg;base64,{photo_b64});'
                 f'background-size:cover;background-position:center 45%;"></div>')
        ecoincons = (f'<path d="M0 0H60V79H56.3V42.6A28 28 0 1 0 3.7 42.6V79H0Z" '
                     f'fill="{fond}" fill-rule="evenodd"/>')
    else:
        photo = ""
        ecoincons = f'<path d="{arche}" fill="none" stroke="{or_}" stroke-width=".21"/>'
    return (photo + f'<svg width="60mm" height="79mm" viewBox="0 0 60 79" style="position:absolute;'
            f'left:{svg_left}mm;top:{svg_top}mm;">{ecoincons}'
            f'<path d="{cadre}" fill="none" stroke="{or_}" stroke-width=".21"/></svg>')


# ── CSS partagée ────────────────────────────────────────────────────────────

def css_commune(j: dict, p: str) -> str:
    """Règles communes aux pages d'une édition ; ``p`` = préfixe de classes
    (sg / no / ba)."""
    return f"""
.{p}-root{{position:relative;width:210mm;height:297mm;overflow:hidden;
  padding:{j['haut']} {j['marge']} 0 {j['marge_g']};font-family:{j['sans']};
  color:{j['ink']};font-size:9pt;line-height:1.4;
  font-variant-numeric:tabular-nums lining-nums;font-feature-settings:"tnum" 1,"lnum" 1;}}
.{p}-root *{{box-sizing:border-box;}}
.{p}-ar{{font-family:{j['arabe']};direction:rtl;unicode-bidi:isolate;letter-spacing:0;line-height:1.55;}}
.{p}-kicker{{font-size:7pt;letter-spacing:.14em;text-transform:uppercase;color:{j['muted']};font-weight:500;}}
.{p}-kicker .{p}-ar{{text-transform:none;letter-spacing:0;font-size:8pt;margin-left:7px;font-weight:400;}}
.{p}-h2{{font-family:{j['display']};font-weight:400;font-size:15pt;line-height:1.2;color:{j['ink']};}}
.{p}-h2 .{p}-ar{{font-size:11.5pt;color:{j['muted']};margin-left:9px;}}
.{p}-h3{{font-size:8.6pt;font-weight:600;color:{j['ink']};}}
.{p}-cap{{font-size:7.2pt;color:{j['muted']};line-height:1.4;}}
.{p}-lab{{font-size:7.6pt;color:{j['muted']};margin-top:3px;line-height:1.35;}}
.{p}-rule{{border-top:0.5pt solid {j['line']};}}
.{p}-row{{display:table;width:100%;border-spacing:0;table-layout:fixed;}}
.{p}-col{{display:table-cell;vertical-align:top;}}
.{p}-gap{{display:table-cell;width:8mm;}}
.{p}-sec{{margin-top:5mm;padding-top:3.5mm;border-top:0.5pt solid {j['line']};}}
/* Bandeau d'en-tête des pages intérieures (marine tramé, logo, rubrique, réf.) */
.{p}-bande{{position:absolute;left:0;top:0;width:210mm;height:16mm;background:{j['hero_bg']};{css_motif(j['motif_11'], 14)}
  color:{j['on_hero']};padding:0 {j['marge']} 0 {j['marge_g']};border-bottom:0.5pt solid {j['or']};}}
.{p}-bande-in{{display:table;width:100%;height:16mm;}}
.{p}-bande-l,.{p}-bande-r{{display:table-cell;vertical-align:middle;line-height:16mm;height:16mm;}}
.{p}-bande-l > *{{display:inline-block;vertical-align:middle;line-height:1;}}
.{p}-bande-r{{text-align:right;font-size:7pt;}}
.{p}-bande-r b{{color:{j['or_texte']};letter-spacing:.14em;text-transform:uppercase;font-weight:500;}}
/* Registre de faits : filet encre 1 pt dessus, 0,3 pt dessous, séparateurs or */
.{p}-reg{{display:table;width:100%;border-spacing:0;table-layout:fixed;border-top:1pt solid {j['ink']};border-bottom:0.3pt solid {j['ink']};}}
.{p}-reg-c{{display:table-cell;vertical-align:top;padding:6px 3mm 7px 3.5mm;border-left:0.5pt solid {j['or']};}}
.{p}-reg-c:first-child{{border-left:0;padding-left:0;}}
.{p}-rv{{font-family:{j['display']};font-weight:600;font-size:19pt;line-height:1;letter-spacing:-.01em;color:{j['ink']};white-space:nowrap;}}
.{p}-ru{{font-family:{j['sans']};font-size:7.5pt;font-weight:500;color:{j['muted']};letter-spacing:0;}}
.{p}-rv.royal{{color:{j['accent']};}}
/* Tableau du devis */
.{p}-tbl{{width:100%;border-collapse:collapse;}}
.{p}-tbl.c5{{table-layout:fixed;}}
.{p}-tbl.c5 th:nth-child(2){{width:11mm;}}.{p}-tbl.c5 th:nth-child(3){{width:22mm;}}
.{p}-tbl.c5 th:nth-child(4){{width:13mm;}}.{p}-tbl.c5 th:nth-child(5){{width:28mm;}}
.{p}-tbl.c3{{table-layout:fixed;}}
.{p}-tbl.c3 th:nth-child(2){{width:11mm;}}.{p}-tbl.c3 th:nth-child(3){{width:30mm;}}
.{p}-tbl th{{text-align:left;font-size:6.8pt;letter-spacing:.08em;text-transform:uppercase;color:{j['muted']};
  font-weight:500;padding:0 0 5px 0;border-bottom:0.8pt solid {j['ink']};}}
.{p}-tbl th.r,.{p}-tbl td.r{{text-align:right;white-space:nowrap;}}
.{p}-tbl tr.orr td{{padding:0;height:0.8mm;border-bottom:0.3pt solid {j['or']};}}
.{p}-tbl td{{padding:5px 0;border-bottom:0.5pt solid {j['line_soft']};vertical-align:top;font-size:8.6pt;}}
.{p}-tbl td.d{{padding-right:10px;}}
.{p}-mq{{display:block;font-size:7.5pt;color:#4A5263;margin-top:1px;}}
.{p}-tbl tr.sec td{{font-size:6.8pt;letter-spacing:.08em;text-transform:uppercase;color:{j['muted']};font-weight:500;padding-top:9px;border-bottom:0.5pt solid {j['line']};}}
.{p}-tbl tr.note td{{font-style:italic;color:{j['muted']};}}
.{p}-tot{{display:table;width:100%;margin-top:4px;}}
.{p}-tot-sp{{display:table-cell;width:52%;vertical-align:top;}}
.{p}-tot-box{{display:table-cell;width:48%;vertical-align:top;}}
.{p}-tot-tbl{{width:100%;border-collapse:collapse;font-size:8.6pt;}}
.{p}-tot-tbl td{{padding:3px 0;color:{j['muted']};}}
.{p}-tot-tbl td:last-child{{text-align:right;white-space:nowrap;color:{j['ink']};}}
.{p}-tot-tbl tr.ttc td{{border-top:1pt solid {j['ink']};padding-top:7px;font-size:13pt;color:{j['ink']};font-weight:600;}}
.{p}-tot-tbl tr.ttc td .{p}-mad{{color:{j['ink']};}}
.{p}-tot-tbl tr.ttc td:first-child{{font-size:8.6pt;font-weight:500;padding-top:10px;}}
.{p}-tot-tbl tr.ttc td .{p}-ar{{font-size:8pt;font-weight:400;color:{j['muted']};margin-left:6px;}}
/* Rangée Total TTC sur bande marine tramée (Signature) */
.{p}-tot-tbl tr.ttcm td{{background-color:{j['hero_bg']};{css_motif(j['motif_8'], 10)}color:{j['on_hero']};padding:8px 8px;font-size:13pt;font-weight:600;border-top:0.8pt solid {j['or']};}}
.{p}-tot-tbl tr.ttcm td:first-child{{font-size:8.6pt;font-weight:500;padding-top:11px;color:{j['on_hero']};}}
.{p}-tot-tbl tr.ttcm td:last-child{{color:{j['on_hero']};}}
.{p}-tot-tbl tr.ttcm td .{p}-ar{{font-size:8pt;font-weight:400;color:{j['on_hero_2']};margin-left:6px;}}
.{p}-tot-tbl tr.ttcm td .{p}-mad{{color:{j['or_texte']};}}
.{p}-mad{{display:inline-block;width:8mm;text-align:left;margin-left:3px;font-size:7.5pt;font-weight:500;color:{j['muted']};}}
.{p}-big{{font-family:{j['display']};font-weight:300;letter-spacing:-.01em;line-height:1;color:{j['ink']};}}
.{p}-unit{{font-family:{j['sans']};font-weight:500;letter-spacing:0;}}
/* Cartouche à double filet (encre 0,8 pt + or 0,3 pt, deux div imbriquées) */
.{p}-cart{{border:0.8pt solid {j['ink']};padding:1.2mm;}}
.{p}-cart-in{{border:0.3pt solid {j['or']};padding:4mm 5mm;}}
.{p}-laiton{{color:{j['laiton']};}}
.{p}-li{{padding-left:4mm;position:relative;margin-top:2px;}}
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
#: Plancher absolu 6,2 pt (synthèse §6) ; le héros et le titre de
#: couverture ne rétrécissent jamais (classes distinctes de ``-big``).
PALIERS = (None, (7.9, 3.5, 8.6, 3.5, 13), (7.3, 2.5, 8.2, 2.5, 11),
           (6.8, 1.6, 7.8, 1.8, 9))


def css_densite(p: str, j: dict, palier: int) -> str:
    """Surcharges CSS du palier ``palier`` ('' au palier 0)."""
    if not palier or palier >= len(PALIERS):
        return ""
    pt, pad, corps, marge, sig = PALIERS[palier]
    return (f"<style>.{p}-root{{font-size:{corps}pt;line-height:1.32;}}"
            f".{p}-tbl td{{padding:{pad}px 0;font-size:{pt}pt;}}"
            f".{p}-tbl th{{padding-bottom:{pad}px;}}"
            f".{p}-mq{{font-size:{max(pt - 1.0, 6.0):g}pt;}}"
            f".{p}-tot-tbl{{font-size:{pt}pt;}}.{p}-tot-tbl td{{padding:{max(pad - 1, 1):g}px 0;}}"
            f".{p}-tot-tbl tr.ttc td{{font-size:{pt + 4:g}pt;padding-top:{pad + 1:g}px;}}"
            f".{p}-cap{{font-size:{max(corps - 1.6, 6.2):g}pt;}}"
            f".{p}-lab{{font-size:{max(corps - 1.2, 6.4):g}pt;}}"
            f".{p}-h2{{font-size:{13 if palier == 1 else 12}pt;}}"
            f".{p}-sec{{margin-top:{marge}mm;padding-top:{max(marge - 1, 1.5):g}mm;}}"
            f".{p}-sig{{height:{sig}mm !important;}}"
            f".{p}-big{{font-size:{18 if palier == 1 else 16}pt !important;}}"
            f".{p}-rv{{font-size:{18 if palier == 1 else 17}pt;}}"
            "</style>")


def esc(v) -> str:
    import html
    return html.escape(str(v or ""), quote=True)


def kicker(texte: str, j: dict, p: str, ar_txt: str = "") -> str:
    """Capitale de section ouverte par le losange or (+ arabe du catalogue)."""
    ar_html = f'<span class="{p}-ar">{ar_txt}</span>' if ar_txt else ""
    return f'<div class="{p}-kicker">{losange(j["or"])}{texte}{ar_html}</div>'


def bande_entete(ctx, j: dict, p: str, rubrique: str, ref: str, hauteur_mm: float = 16,
                 logo_mm: float = 22) -> str:
    """Le bandeau d'en-tête des pages intérieures."""
    return (f'<div class="{p}-bande" style="height:{hauteur_mm:g}mm;"><div class="{p}-bande-in" style="height:{hauteur_mm:g}mm;">'
            f'<div class="{p}-bande-l">{logo(ctx, logo_mm, sombre=True, hauteur_mm=max(6.0, hauteur_mm * 0.45))}</div>'
            f'<div class="{p}-bande-r"><b>{rubrique}</b>&nbsp;&nbsp;·&nbsp;&nbsp;{ref}</div></div></div>')


# ── Fragments ───────────────────────────────────────────────────────────────

def tableau_equipements(m: dict, p: str, j: dict, L, *, simple=False, resume=False) -> str:
    """Le tableau des lignes (regroupées, remises par ligne) ; ``simple`` =
    désignation · quantité · total seulement ; ``resume`` = les sous-lignes
    d'un regroupement sur une seule ligne séparée par « · » (Basique)."""
    rows = ""
    ncols = 3 if simple else 5
    for kind, it in m["lignes"]:
        if kind == "struct":
            cls = "note" if it["type"] == "note" else "sec"
            rows += f'<tr class="{cls}"><td colspan="{ncols}">{it["texte"]}</td></tr>'
            continue
        if resume and it["sous_lignes"]:
            morceaux = [re.sub(r"<[^>]+>", "", x).strip() for x in
                        re.findall(r"<div[^>]*>(.*?)</div>", it["sous_lignes"], re.S)]
            it = dict(it, sous_lignes=f'<span class="{p}-mq">{" · ".join(m_ for m_ in morceaux if m_)}</span>')
        marque = f'<span class="{p}-mq">{esc(it["marque"])}</span>' if it["marque"] else ""
        pu = (f'<span style="text-decoration:line-through;opacity:.55;">'
              f'{it["pu_cat"]}</span> ' if it["pu_cat"] else "") + it["pu_ht"]
        if simple:
            rows += (f'<tr><td class="d">{it["designation"]}{marque}{it["sous_lignes"]}</td>'
                     f'<td class="r">{it["qte"]}</td><td class="r">{it["total"]}</td></tr>')
        else:
            rows += (f'<tr><td class="d">{it["designation"]}{marque}{it["sous_lignes"]}</td>'
                     f'<td class="r">{it["qte"]}</td><td class="r">{pu}</td>'
                     f'<td class="r">{it["taux"]}</td><td class="r">{it["total"]}</td></tr>')
    if m["hors_total"]:
        rows += (f'<tr class="sec"><td colspan="{ncols}">'
                 + L("ci_postes_hors_total", "Postes à chiffrer après la visite technique (hors total)")
                 + '</td></tr>')
        mention = L("ci_a_chiffrer_apres_visite", "à chiffrer après la visite technique")
        for nom, qte in m["hors_total"]:
            rows += (f'<tr><td class="d">{nom}</td><td class="r">{qte}</td>'
                     f'<td class="r" colspan="{1 if simple else 3}" style="font-style:italic;'
                     f'color:{j["muted"]};">{mention}</td></tr>')
    if simple:
        head = (f'<tr><th>{L("designation", "Désignation")}</th><th class="r">{L("qte", "Qté")}</th>'
                f'<th class="r">{L("total_ht", "Total HT")} (MAD)</th></tr>')
    else:
        head = (f'<tr><th>{L("designation", "Désignation")}</th><th class="r">{L("qte", "Qté")}</th>'
                f'<th class="r">{L("pu_ht", "P.U. HT")}</th><th class="r">{L("ci_tva_pct", "TVA %")}</th>'
                f'<th class="r">{L("total_ht", "Total HT")} (MAD)</th></tr>')
    return f'<table class="{p}-tbl c{ncols}">{head}<tr class="orr"><td colspan="{ncols}"></td></tr>{rows}</table>'


def chaine_totaux(m: dict, p: str, L, *, ttc_marine=False, ar_ttc="",
                  ttc_display=False) -> str:
    t = m["totaux"]
    remise = (f'<tr><td>{L("remise", "Remise")}{t["ancre_remise"]}</td>'
              f'<td>− {t["remise"]}<span class="{p}-mad">MAD</span></td></tr>' if t["remise"] else "")
    arrondi = (f'<tr><td>{L("arrondi", "Arrondi commercial")}{t["ancre_arrondi"]}</td>'
               f'<td>− {t["arrondi"]}<span class="{p}-mad">MAD</span></td></tr>' if t["arrondi"] else "")
    ar_html = f'<span class="{p}-ar">{ar_ttc}</span>' if ar_ttc else ""
    cls = "ttcm" if ttc_marine else "ttc"
    montant = (f'<span style="font-family:{DISPLAY};font-weight:400;font-size:18pt;letter-spacing:-.01em;">{t["ttc"]}</span>'
               if ttc_display else t["ttc"])
    mad = f'<span class="{p}-mad">MAD</span>'
    return (f'<div class="{p}-tot"><div class="{p}-tot-sp"></div>'
            f'<div class="{p}-tot-box"><table class="{p}-tot-tbl">'
            f'<tr><td>{L("sous_total_ht", "Sous-total HT")}{t["ancre_ht_brut"]}</td><td>{t["ht_brut"]}{mad}</td></tr>'
            f'{remise}{arrondi}'
            f'<tr><td>{L("total_ht", "Total HT")}{t["ancre_ht_net"]}</td><td>{t["ht_net"]}{mad}</td></tr>'
            f'<tr><td>{L("tva", "TVA")}{t["ancre_tva"]}</td><td>{t["tva"]}{mad}</td></tr>'
            f'<tr class="{cls}"><td>{L("total_ttc", "Total TTC")}{ar_html}{t["ancre_ttc"]}</td>'
            f'<td>{montant}{mad}</td></tr>'
            f'</table></div></div>')


def options_et_injection(m: dict, p: str, j: dict, L) -> str:
    html = ""
    if m["options"]:
        rows = "".join(
            f'<tr><td class="d">{q}{des}</td><td class="r">{taux}</td>'
            f'<td class="r">{ht} {L("ci_ht", "HT")}<span class="{p}-mq">{ttc} {L("ci_ttc", "TTC")}</span></td></tr>'
            for q, des, taux, ht, ttc in m["options"])
        html += (f'<div style="margin-top:9px;">'
                 + kicker(L("ci_options_proposees", "Options propos&eacute;es (non incluses dans le total)"), j, p)
                 + f'<table class="{p}-tbl" style="margin-top:4px;">'
                 f'<tr><th>{L("designation", "D&eacute;signation")}</th><th class="r">{L("ci_tva_pct", "TVA %")}</th>'
                 f'<th class="r">{L("total_ht", "Total HT")}</th></tr>{rows}</table></div>')
    if m["injection"]:
        montant, mentions = m["injection"]
        html += (f'<div style="margin-top:8px;font-size:8pt;line-height:1.4;">'
                 f'<b style="color:{j["vert"]};">+ {montant} {L("ci_mad_an", "MAD/an")}</b> — '
                 + L("ci_surplus_injecte", "surplus injecté") + f'. <span class="{p}-cap">{mentions}</span></div>')
    return html


def garanties_rangee(m: dict, p: str, j: dict, L, taille_pt=22, graisse=300, etoiles=True) -> str:
    """Les garanties servies en grands nombres, séparées par l'étoile khatam."""
    if not m["garanties"]:
        return ""
    cellules = []
    for i, (n, u, lib) in enumerate(m["garanties"]):
        sep = f'border-left:0.5pt solid {j["or"]};padding-left:3.5mm;' if (etoiles and i) else ""
        cellules.append(
            f'<div class="{p}-col" style="padding-right:3mm;{sep}">'
            f'<div class="{p}-big" style="font-size:{taille_pt}pt;font-weight:{graisse};">{n}'
            f'<span class="{p}-unit" style="font-size:8pt;color:{j["muted"]};"> {u}</span></div>'
            f'<div class="{p}-lab">{lib}</div></div>')
    from ..ci.blocs import legende_garanties
    return (f'<div class="{p}-row">{"".join(cellules)}</div>'
            f'<div class="{p}-cap" style="margin-top:5px;">{legende_garanties(m["d"])}</div>')


def echeancier_rangee(m: dict, p: str, j: dict, L) -> str:
    if not m["echeancier"]:
        return ""
    ttc = L("ci_ttc", "TTC")
    cellules = ""
    for pct, lib, montant in m["echeancier"]:
        cellules += (
            f'<div class="{p}-col" style="padding-right:6mm;border-top:0.5pt solid {j["or"]};padding-top:5px;">'
            f'<div style="font-size:13pt;font-weight:500;">{pct}&nbsp;%</div>'
            f'<div style="font-size:7.6pt;margin-top:1px;">{lib}</div>'
            + (f'<div style="font-size:7.2pt;font-weight:600;margin-top:1px;">{montant} MAD {ttc}</div>' if montant else "")
            + '</div>')
    return f'<div class="{p}-row">{cellules}</div>'


def echeancier_ligne(m: dict, L) -> str:
    """L'échéancier sur une ligne (Basique) : « 40 % à la commande · 256 000,00 MAD TTC — … »."""
    if not m["echeancier"]:
        return ""
    ttc = L("ci_ttc", "TTC")
    morceaux = []
    for pct, lib, montant in m["echeancier"]:
        lib_txt = (lib[:1].lower() + lib[1:]) if lib else ""
        morceaux.append(f'<b>{pct}&nbsp;%</b> {lib_txt}' + (f' · {montant} MAD {ttc}' if montant else ""))
    return " &nbsp;—&nbsp; ".join(morceaux)


def garanties_ligne(m: dict) -> str:
    if not m["garanties"]:
        return ""
    return " &nbsp;·&nbsp; ".join(f'<b>{n} {u}</b> {lib}' for n, u, lib in m["garanties"])


def hypotheses_tableau(m: dict, p: str, j: dict, L, colonnes=2) -> str:
    """« Bases du calcul » (AMOT91) en 1, 2 ou 3 colonnes, petite typographie."""
    rangees = [(lib, val) for lib, val in m["hypotheses"] if val]
    if not rangees:
        return ""
    taille = "7pt" if colonnes < 3 else "6.8pt"

    def _tbl(rs):
        cells = "".join(
            f'<tr><td style="color:{j["muted"]};width:38%;padding:2px 6px 2px 0;'
            f'border-bottom:0.5pt solid {j["line_soft"]};vertical-align:top;">{lib or ""}</td>'
            f'<td style="padding:2px 0;border-bottom:0.5pt solid {j["line_soft"]};">{val}</td></tr>'
            for lib, val in rs)
        return f'<table style="width:100%;border-collapse:collapse;font-size:{taille};line-height:1.35;">{cells}</table>'
    if colonnes == 1:
        return _tbl(rangees)
    n = len(rangees)
    part = (n + colonnes - 1) // colonnes
    cols = [rangees[i * part:(i + 1) * part] for i in range(colonnes)]
    inner = f'<div class="{p}-gap" style="width:6mm;"></div>'.join(
        f'<div class="{p}-col">{_tbl(c)}</div>' for c in cols if c)
    return f'<div class="{p}-row">{inner}</div>'


def conditions_bloc(m: dict, p: str, j: dict) -> str:
    titre, puces = m["conditions"]
    if not puces:
        return ""
    items = "".join(f'<li style="margin-top:1px;">{pu}</li>' for pu in puces)
    return (f'<div class="{p}-h3" style="margin-top:9px;">{titre}</div>'
            f'<ul class="{p}-cap" style="margin:3px 0 0 0;padding-left:11px;color:{j["ink"]};font-size:7.4pt;">{items}</ul>')


def bon_pour_accord(m: dict, p: str, j: dict, L, haut_mm=22, cartouche=False,
                    ar_titre="", ar_signature="", ar_cachet="") -> str:
    """Le bloc d'acceptation (CIQ320) : filet maître, ou cartouche à double
    filet (Signature). Aucun emblème : jamais un faux cachet."""
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
    cadre = (f'display:table-cell;width:50%;vertical-align:top;border:0.5pt solid {j["line"]};'
             f'padding:3px 5px;font-size:6.5pt;color:{j["muted"]};')

    def _ar(t):
        return f' <span class="{p}-ar" style="font-size:7pt;">{t}</span>' if t else ""
    cadres = (f'<div style="display:table;width:100%;border-spacing:3mm 0;margin:6px -3mm 0 -3mm;">'
              f'<div class="{p}-sig" style="{cadre}">{a["signature"]}{_ar(ar_signature)}</div>'
              f'<div class="{p}-sig" style="{cadre}">{a["cachet"]}{_ar(ar_cachet)}</div></div>'
              f'<style>.{p}-sig{{height:{haut_mm}mm;}}</style>')
    signe = ""
    if a["accepte_nom"] and a["date_acceptation"]:
        signe = (f'<div style="margin-top:6px;font-size:10pt;font-weight:600;">{a["accepte_nom"]}</div>'
                 f'<div class="{p}-cap">{L("ci_le_date", "Le {date}", date=a["date_acceptation"])}</div>')
    titre_ar = (f'<span class="{p}-ar" style="text-transform:none;letter-spacing:0;font-size:8.5pt;'
                f'font-weight:600;margin-left:7px;">{ar_titre}</span>' if ar_titre else "")
    gauche = (f'<div class="{p}-kicker">{a["titre"]} — {a["pour"]}{titre_ar}</div>'
              f'<div style="font-size:7.4pt;line-height:1.35;">{cases}{lignes}{cadres}'
              f'<div style="margin-top:4px;font-style:italic;color:{j["muted"]};">{a["mention"]}</div>{signe}</div>')
    droite = (f'<div class="{p}-kicker">{L("ci_pour", "Pour {marque}", marque=m["brand"])}</div>'
              f'<div class="{p}-sig" style="margin-top:6px;border:0.5pt solid {j["line"]};"></div>'
              f'<div class="{p}-cap" style="margin-top:5px;">{m["ligne_vendeur"]}</div>')
    corps = (f'<div class="{p}-row"><div class="{p}-col" style="width:58%;">{gauche}</div>'
             f'<div class="{p}-gap"></div><div class="{p}-col">{droite}</div></div>')
    if cartouche:
        return f'<div class="{p}-cart" style="margin-top:9px;"><div class="{p}-cart-in">{corps}</div></div>'
    return f'<div style="margin-top:10px;border-top:1pt solid {j["ink"]};padding-top:7px;">{corps}</div>'


def bande_legale(m: dict, p: str, j: dict) -> str:
    return (f'<div class="{p}-cap" style="margin-top:7px;font-size:6.6pt;color:{j["muted"]};">'
            f'{m["bande_legale"]}</div>')


def logo(ctx, largeur_mm=30, sombre=True, hauteur_mm=0) -> str:
    """Le logo dimensionné par sa LARGEUR (le PNG a du vide autour : en
    hauteur il rendait minuscule), ou par sa hauteur dans un bandeau."""
    b64 = ctx["logo_dark"] if sombre else ctx["logo_color"]
    # APDF4 — société sans logo (PNG vide de 1×1 servi par ``theme``) : la
    # marque servie en lettres (jamais le logo d'une autre société).
    if not b64 or len(b64) < 200:
        marque = esc((ctx.get("ident") or {}).get("brand_name") or "")
        if not marque:
            return ""
        couleur = "#FFFFFF" if sombre else "#14213D"
        taille = max(9.0, min(16.0, largeur_mm * 0.42))
        return (f'<div style="font-family:{DISPLAY};font-weight:400;font-size:{taille:g}pt;'
                f'letter-spacing:.02em;color:{couleur};line-height:1;white-space:nowrap;">{marque}</div>')
    if hauteur_mm:
        return (f'<img src="data:image/png;base64,{b64}" alt="" '
                f'style="height:{hauteur_mm:g}mm;width:auto;display:block;">')
    return (f'<img src="data:image/png;base64,{b64}" alt="" '
            f'style="width:{largeur_mm:g}mm;height:auto;display:block;">')


def titre_scinde(titre: str, langue: str, couleur_1: str, pt_avant: float = 0,
                 pt_apres: float = 0, pt_apres_long: float = 0, seuil: int = 26,
                 ville: str = "") -> str:
    """Le titre servi, coupé sur son tiret : la centrale en teinte retenue
    (et en corps plus petit si ``pt_avant``), le client en pleine couleur
    (``pt_apres``, ou ``pt_apres_long`` au-delà de ``seuil`` caractères) —
    même chaîne (jamais en arabe)."""
    if " — " in titre and langue != "ar":
        avant, apres = titre.split(" — ", 1)
        st_avant = f"color:{couleur_1};" + (f"font-size:{pt_avant:g}pt;" if pt_avant else "")
        ville_html = ""
        if ville and apres.endswith(f", {ville}"):
            # La ville servie passe sur sa propre ligne (jamais une virgule
            # orpheline en fin de ligne), en corps intermédiaire.
            apres = apres[:-len(f", {ville}")]
            pt_v = pt_avant or pt_apres
            ville_html = f'<br><span style="color:{couleur_1};font-size:{pt_v:g}pt;">{ville}</span>' if pt_v else f"<br>{ville}"
        pt = pt_apres_long if (pt_apres_long and len(apres) > seuil) else pt_apres
        st_apres = f"font-size:{pt:g}pt;" if pt else ""
        return (f'<span style="{st_avant}">{avant}</span><br>'
                f'<span style="{st_apres}white-space:normal;">{apres}</span>{ville_html}')
    return titre
