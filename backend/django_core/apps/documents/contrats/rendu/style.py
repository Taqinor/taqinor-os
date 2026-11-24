"""Feuille de style des actes du dossier contractuel.

Même famille visuelle que le devis (bleu nuit, or, DM Serif Display / DM Sans),
mais une mise en page de TEXTE : pages qui s'enchaînent (le devis, lui, pose
des pages fixes), titre d'article en marge, colonne de lecture d'une
soixantaine de signes, pied répété avec l'identité légale, la pagination et
les paraphes.

Règles tenues (sources : docs/contrats/conception.md § Mise en page) :
- corps 10,5 pt, interligne 1,55, aligné à gauche, jamais justifié ;
- aucun texte en or sur blanc (contraste 2:1) : l'or sert aux filets, aux
  pastilles et au texte sur bleu nuit ; les petits libellés sont en bronze
  (≥ 4,5:1) ;
- la couleur ne porte jamais seule une information (photocopie noir et blanc) :
  chaque état a son mot (« Réglé », « À régler », « À venir »).
"""
import base64
import functools

NAVY = '#1A2B4A'
NAVY_900 = '#12203B'
OR = '#F5A623'
BRONZE = '#8A5A00'
ENCRE = '#1F2937'
GRIS = '#5B6472'
FILET = '#E3E6EB'
LAVIS = '#F6F7F9'
LAVIS_OR = '#FDF6E7'
VERT = '#157A3C'
VERT_FOND = '#E9F5EE'
PAPIER = '#FFFFFF'

POLICE_TITRE = "'DM Serif Display', Georgia, serif"
POLICE_TEXTE = "'DM Sans', 'Noto Sans', system-ui, sans-serif"


def _uri_svg(svg):
    return 'data:image/svg+xml;base64,' + base64.b64encode(
        svg.encode('utf-8')).decode('ascii')


# Khatam (étoile à huit branches : deux carrés croisés) — le motif de l'en-tête.
_MOTIF_KHATAM = _uri_svg(
    "<svg xmlns='http://www.w3.org/2000/svg' width='44' height='44' "
    "viewBox='0 0 44 44'><g fill='none' stroke='#FFFFFF' "
    "stroke-opacity='.075' stroke-width='.9'>"
    "<rect x='11' y='11' width='22' height='22'/>"
    "<rect x='11' y='11' width='22' height='22' transform='rotate(45 22 22)'/>"
    "<circle cx='22' cy='22' r='4.2'/>"
    "<path d='M0 22h6.4M37.6 22H44M22 0v6.4M22 37.6V44'/>"
    "</g></svg>")


def etoile_svg(taille_mm=3.2, couleur=OR):
    """La petite étoile khatam des intertitres (vecteur, tient en noir et blanc)."""
    return (
        f"<svg class='etoile' xmlns='http://www.w3.org/2000/svg' "
        f"width='{taille_mm}mm' height='{taille_mm}mm' viewBox='0 0 24 24'>"
        f"<g fill='{couleur}'><rect x='5' y='5' width='14' height='14'/>"
        f"<rect x='5' y='5' width='14' height='14' "
        f"transform='rotate(45 12 12)'/></g>"
        f"<circle cx='12' cy='12' r='3.1' fill='#FFFFFF'/></svg>")


def _polices():
    """@font-face du moteur de devis (woff2 embarqués), sinon rien : le repli
    Georgia / système garde le document lisible."""
    try:
        from apps.ventes.quote_engine.residential.theme import font_face_css
        return font_face_css()
    except Exception:  # pragma: no cover - rendu dégradé hors dépôt complet
        return ''


_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
@page{size:A4;margin:17mm 0 25mm 0;
  @top-left{content:string(acte);font-family:__TEXTE__;font-size:7.4pt;
    letter-spacing:.14em;text-transform:uppercase;color:__GRIS__;
    padding-left:20mm;vertical-align:bottom;padding-bottom:4mm}
  @top-right{content:string(reference);font-family:__TEXTE__;font-size:7.4pt;
    letter-spacing:.06em;color:__GRIS__;padding-right:20mm;
    vertical-align:bottom;padding-bottom:4mm}
  @bottom-center{content:element(pied);width:100%}}
@page:first{margin-top:0;@top-left{content:none}@top-right{content:none}}
html{font-family:__TEXTE__;color:__ENCRE__;font-size:10.5pt;line-height:1.55;
  -weasy-hyphens:none;hyphens:none;background:__PAPIER__}
body{background:__PAPIER__}
strong,b{font-weight:700;color:__NAVY__}
.nb{white-space:nowrap}

/* ── Pied répété : identité légale, pagination, paraphes ── */
.pied{position:running(pied);padding:0 20mm;font-size:6.5pt;line-height:1.45;
  color:__GRIS__}
.pied-in{border-top:.6pt solid __FILET__;padding-top:2.6mm;display:flex;
  align-items:flex-start;justify-content:space-between}
.pied-legal{flex:1;padding-right:6mm}
.pied-legal b{color:__NAVY__;font-weight:700;letter-spacing:.04em;font-size:6.9pt}
.pied-droite{display:flex;align-items:flex-start}
.paraphes{display:flex;align-items:flex-start;margin-right:5mm}
.paraphes span{display:block;font-size:6pt;letter-spacing:.08em;
  text-transform:uppercase;color:__GRIS__;text-align:center;margin-bottom:.8mm}
.paraphe{width:12.5mm;margin-left:2mm}
.paraphe i{display:block;height:8.4mm;border:.6pt solid #C9CED6;
  border-radius:1.2mm;background:__PAPIER__}
.folio{text-align:right;white-space:nowrap;color:__GRIS__;font-size:7.2pt;
  line-height:1.5;padding-top:2.2mm}
.folio b{display:block;color:__NAVY__;font-weight:700;font-size:7.6pt;
  letter-spacing:.04em}
.folio i{font-style:normal}
.folio i::after{content:"page " counter(page) " sur " counter(pages)}

/* ── En-tête de première page (pleine largeur) ── */
.bandeau{background:__NAVY__ url("__KHATAM__");color:#FFFFFF;
  padding:11mm 20mm 9.5mm;display:flex;justify-content:space-between;
  align-items:flex-start;border-bottom:1.1mm solid __OR__}
.bandeau .marque{font-size:15pt;font-weight:700;letter-spacing:.06em;
  color:#FFFFFF;line-height:1.1}
.bandeau .marque img{display:block;height:11mm;width:auto}
.bandeau .ref{text-align:right;font-size:8pt;line-height:1.55;color:#C9D2E0}
.bandeau .ref b{display:block;color:__OR__;font-size:9.6pt;
  letter-spacing:.08em;font-weight:700}

/* ── Le parcours en quatre actes ── */
.parcours{display:flex;background:__LAVIS__;padding:3.4mm 20mm;
  border-bottom:.6pt solid __FILET__}
.etape{flex:1;display:flex;align-items:center;font-size:7.6pt;color:__GRIS__;
  line-height:1.25}
.etape .n{flex:none;width:5.4mm;height:5.4mm;border-radius:50%;
  border:.7pt solid #B9C0CB;color:__GRIS__;font-weight:700;font-size:7.4pt;
  text-align:center;line-height:5.1mm;margin-right:2mm;background:__PAPIER__}
.etape.fait .n{background:__NAVY__;border-color:__NAVY__;color:#FFFFFF}
.etape.ici{color:__NAVY__;font-weight:700}
.etape.ici .n{background:__OR__;border-color:__OR__;color:__NAVY_900__}
.etape small{display:block;font-size:6.3pt;font-weight:400;color:__GRIS__;
  letter-spacing:.02em}

/* ── Corps ── */
.corps{padding:0 20mm}
.titre{padding:8.5mm 0 3mm}
.surtitre{font-size:7.6pt;letter-spacing:.2em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700;margin-bottom:2.2mm;string-set:acte content()}
.reference-cachee{string-set:reference content();display:none}
h1{font-family:__TITRE__;font-weight:400;font-size:27pt;line-height:1.12;
  color:__NAVY__;letter-spacing:-.005em}
.chapeau{margin-top:3.2mm;font-size:11pt;line-height:1.5;color:__GRIS__;
  max-width:150mm}
.chapeau b{color:__NAVY__}

h2{font-family:__TITRE__;font-weight:400;font-size:15.5pt;line-height:1.2;
  color:__NAVY__;margin:7.5mm 0 3.4mm;break-after:avoid}
h2 .etoile{vertical-align:-.25mm;margin-right:2.4mm}
.intro{color:__GRIS__;margin:-1.4mm 0 4mm;max-width:150mm;font-size:9.8pt}

/* ── L'essentiel : cartes ── */
.cartes{display:flex;flex-wrap:wrap;margin:0 -1.6mm}
.carte{break-inside:avoid;width:calc(50% - 3.2mm);margin:0 1.6mm 3.2mm;
  border:.6pt solid __FILET__;border-radius:2.6mm;padding:4.2mm 4.6mm 4.4mm;
  background:__PAPIER__}
.carte.large{width:calc(100% - 3.2mm)}
.carte.forte{background:__NAVY__;border-color:__NAVY__;color:#D5DCE8}
.carte .lbl{font-size:6.9pt;letter-spacing:.16em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700;margin-bottom:1.4mm}
.carte.forte .lbl{color:__OR__}
.carte .val{font-family:__TITRE__;font-size:17pt;line-height:1.15;
  color:__NAVY__}
.carte.forte .val{color:#FFFFFF}
.carte .val small{font-family:__TEXTE__;font-size:9pt;font-weight:500;
  letter-spacing:.02em}
.carte .det{margin-top:1.4mm;font-size:8.8pt;line-height:1.45;color:__GRIS__}
.carte.forte .det{color:#C2CBDA}
.carte .det b{color:__NAVY__}
.carte.forte .det b{color:#FFFFFF}

/* ── Frise de paiement ── */
.frise{display:flex;break-inside:avoid;margin:1mm 0 2mm}
.jalon{flex:1;position:relative;padding:0 3mm 0 0}
.jalon .tete{display:flex;align-items:center;margin-bottom:2.6mm}
.jalon .pastille{flex:none;width:8.6mm;height:8.6mm;border-radius:50%;
  background:__PAPIER__;border:.9pt solid __NAVY__;color:__NAVY__;
  font-weight:700;font-size:9.4pt;text-align:center;line-height:8.2mm}
.jalon .trait{flex:1;height:.9pt;background:#C4CAD4;margin-left:2mm}
.jalon:last-child .trait{background:transparent}
.jalon.regle .pastille{background:__VERT__;border-color:__VERT__;color:#FFFFFF}
.jalon.exigible .pastille{background:__OR__;border-color:__OR__;
  color:__NAVY_900__}
.jalon .quand{font-size:6.9pt;letter-spacing:.14em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700}
.jalon .quoi{font-weight:700;color:__NAVY__;font-size:10.2pt;line-height:1.3;
  margin-top:.4mm}
.jalon .combien{font-family:__TITRE__;font-size:15pt;color:__NAVY__;
  line-height:1.25;margin-top:1mm;white-space:nowrap}
.jalon .combien small{font-family:__TEXTE__;font-size:8.4pt;color:__GRIS__;
  font-weight:500}
.jalon .etat{display:inline-block;margin-top:1.6mm;font-size:7.2pt;
  font-weight:700;letter-spacing:.06em;padding:.5mm 2.2mm;border-radius:10mm;
  border:.6pt solid #C4CAD4;color:__GRIS__;background:__PAPIER__}
.jalon.regle .etat{border-color:__VERT__;color:__VERT__;background:__VERT_FOND__}
.jalon.exigible .etat{border-color:__BRONZE__;color:__BRONZE__;
  background:__LAVIS_OR__}
.jalon .note{font-size:8.2pt;color:__GRIS__;line-height:1.4;margin-top:1.2mm}

/* ── Tableaux ── */
table{width:100%;border-collapse:collapse;font-size:9.2pt;line-height:1.4}
thead{display:table-header-group}
tr{break-inside:avoid}
th{font-size:6.9pt;letter-spacing:.14em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700;text-align:left;padding:0 2.4mm 1.8mm 0;
  border-bottom:.9pt solid __NAVY__}
td{padding:2.3mm 2.4mm 2.3mm 0;border-bottom:.6pt solid __FILET__;
  vertical-align:top}
td.n,th.n{text-align:right;padding-right:0;white-space:nowrap}
td b{color:__NAVY__}
td small{display:block;color:__GRIS__;font-size:8.2pt}
tr.total td{border-bottom:none;border-top:.9pt solid __NAVY__;font-weight:700;
  color:__NAVY__;padding-top:2.6mm}
table.garanties td:first-child{width:33%}
table.garanties td:nth-child(2){width:21%}
table.garanties.dates td:first-child{width:29%}
table.garanties.dates td:nth-child(2){width:19%}
table.garanties.dates td:nth-child(3){width:15%}
.duree{font-family:__TITRE__;font-size:13pt;color:__NAVY__;white-space:nowrap;
  line-height:1.2}
.barre{height:1.5mm;border-radius:1mm;background:#E9ECF1;margin-top:1.4mm;
  width:88%}
.barre i{display:block;height:1.5mm;border-radius:1mm;background:__NAVY__}

/* ── Parties ── */
.parties{display:flex;break-inside:avoid;margin:0 -2mm}
.partie{flex:1;margin:0 2mm;border-top:.9pt solid __NAVY__;padding-top:2.8mm;
  font-size:9.4pt;line-height:1.5}
.partie .lbl{font-size:6.9pt;letter-spacing:.16em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700;margin-bottom:1.2mm}
.partie .nom{font-family:__TITRE__;font-size:13.5pt;color:__NAVY__;
  line-height:1.2;margin-bottom:1mm}
.partie .ci-apres{margin-top:1.6mm;color:__GRIS__;font-size:8.6pt}

/* ── Articles : titre en marge, colonne de lecture ── */
.article{position:relative;padding:4mm 0 0 48mm;margin-top:4mm;
  border-top:.6pt solid __FILET__;min-height:15mm}
.article .marge{position:absolute;left:0;top:4mm;width:43mm}
.article .num{font-size:6.9pt;letter-spacing:.16em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700}
.article h3{font-family:__TITRE__;font-weight:400;font-size:12.4pt;
  line-height:1.22;color:__NAVY__;margin-top:.8mm}
.article .texte{font-size:10.2pt}
.article.plein{padding-left:0;min-height:0}
.article .texte p{margin-bottom:2.2mm;orphans:2;widows:2}
.article .texte p:last-child{margin-bottom:0}
.article .texte ul{margin:0 0 2.4mm 0;list-style:none}
.article .texte li{position:relative;padding-left:4.4mm;margin-bottom:1.1mm}
.article .texte li::before{content:"";position:absolute;left:.4mm;top:2.15mm;
  width:1.5mm;height:1.5mm;background:__OR__;transform:rotate(45deg)}

/* ── Encadrés ── */
.encadre{break-inside:avoid;border-left:1.1mm solid __OR__;
  background:__LAVIS_OR__;border-radius:0 2mm 2mm 0;padding:3.6mm 4.6mm;
  margin:3mm 0;font-size:9.6pt;line-height:1.5}
.encadre.net{border-left-color:__NAVY__;background:__LAVIS__}
.encadre.ok{border-left-color:__VERT__;background:__VERT_FOND__}
.encadre .lbl{font-size:6.9pt;letter-spacing:.16em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700;margin-bottom:1mm}
.encadre.ok .lbl{color:__VERT__}
.encadre.net .lbl{color:__NAVY__}
.grand{font-family:__TITRE__;font-size:19pt;color:__NAVY__;line-height:1.2;
  white-space:nowrap}
.lettres{font-size:8.8pt;color:__GRIS__;font-style:italic}

/* ── Cases à cocher (imprimées) ── */
.cases{margin:1.6mm 0 0}
.case{display:flex;align-items:flex-start;margin-bottom:1.9mm;
  break-inside:avoid;font-size:9.8pt;line-height:1.45}
.case i{flex:none;width:4mm;height:4mm;border:.8pt solid __NAVY__;
  border-radius:.7mm;margin:.55mm 2.8mm 0 0;background:__PAPIER__;
  text-align:center;font-style:normal;font-weight:700;font-size:8.6pt;
  line-height:3.5mm;color:__NAVY__}
.case.oui i{background:__NAVY__;color:#FFFFFF}
.lignes{margin-top:1.6mm}
.lignes i{display:block;border-bottom:.6pt dotted #9AA3B0;height:7.4mm}

/* ── Signatures ── */
.signatures{break-inside:avoid;margin-top:7mm}
.fait-a{font-size:9.8pt;margin-bottom:3.4mm}
.fait-a .trou{display:inline-block;min-width:38mm;
  border-bottom:.6pt dotted #9AA3B0}
.sig{display:table;width:100%;table-layout:fixed;border-collapse:separate;
  border-spacing:0}
.sig .cellule{display:table-cell;width:50%;vertical-align:top;
  padding-right:2mm}
.sig .cellule + .cellule{padding-right:0;padding-left:2mm}
.sig .boite{border:.7pt solid #B9C0CB;border-radius:2.6mm;
  padding:3.6mm 4.4mm 4mm;height:47mm}
.sig .lbl{font-size:6.9pt;letter-spacing:.16em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700}
.sig .qui{font-weight:700;color:__NAVY__;font-size:10.4pt;margin-top:.6mm}
.sig .mention{font-size:8.2pt;color:__GRIS__;line-height:1.4;margin-top:1.4mm}
.sig .trace{display:block;max-height:22mm;max-width:62mm;margin-top:2mm}
.sig .preuve{font-size:7.4pt;color:__GRIS__;line-height:1.4;margin-top:1.6mm}
.sceau{display:inline-block;margin-top:2mm;font-size:7.6pt;font-weight:700;
  letter-spacing:.06em;color:__VERT__;border:.7pt solid __VERT__;
  border-radius:10mm;padding:.5mm 2.6mm;background:__VERT_FOND__}

/* ── Conseils (acte 4) ── */
.conseils{display:flex;flex-wrap:wrap;margin:0 -3mm}
.conseil{break-inside:avoid;width:calc(50% - 6mm);margin:0 3mm 4mm;
  border-top:.9pt solid __NAVY__;padding-top:2.6mm}
.conseil .lbl{font-size:6.9pt;letter-spacing:.16em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700}
.conseil h3{font-family:__TITRE__;font-weight:400;font-size:12.4pt;
  color:__NAVY__;line-height:1.22;margin:.6mm 0 1.2mm}
.conseil p{font-size:9.4pt;line-height:1.5;color:__ENCRE__}
.journee{break-inside:avoid;margin:2mm 0 5mm}
.journee .rail{display:flex;height:9mm;border-radius:2mm;overflow:hidden;
  border:.6pt solid __FILET__}
.journee .rail div{font-size:7.2pt;font-weight:700;letter-spacing:.04em;
  text-align:center;line-height:9mm;white-space:nowrap;overflow:hidden}
.journee .rail .nuit{background:__NAVY__;color:#C9D2E0}
.journee .rail .bord{background:#F8E3B4;color:__NAVY_900__}
.journee .rail .plein{background:__OR__;color:__NAVY_900__}
.journee .sous{display:flex;font-size:7.4pt;line-height:1.35;color:__GRIS__;
  margin-top:1.2mm}
.journee .sous div{text-align:center;padding:0 1mm}
.journee .sous .plein{color:__BRONZE__;font-weight:700}
.journee .petit{margin-top:1.6mm}
body.proces h1{font-size:23pt}
body.proces .titre{padding:6.5mm 0 2mm}
body.proces .chapeau{font-size:10pt;margin-top:2.2mm}
body.proces h2{margin:5.4mm 0 2.6mm;font-size:14pt}
body.proces .carte{padding:3.2mm 4.2mm 3.4mm}
body.proces .carte .val{font-size:15pt}
body.proces td{padding-top:1.7mm;padding-bottom:1.7mm}
body.proces .encadre{padding:3mm 4.2mm;margin:2.4mm 0}
body.proces .signatures{margin-top:4mm}
body.proces .article .texte{font-size:9.5pt;line-height:1.45}
body.proces .article{padding-top:3.2mm;margin-top:3.2mm}
body.proces .article .marge{top:3.2mm}
body.proces .lignes i{height:6.4mm}
body.proces .sig .boite{height:29mm}
body.cloture .article .texte{font-size:9.6pt;line-height:1.45}
body.cloture .article{padding-top:3.2mm;margin-top:3.2mm}
body.cloture .article .marge{top:3.2mm}
body.cloture .article.plein{padding-left:0}
body.cloture td{padding-top:1.9mm;padding-bottom:1.9mm}
.sig.seule .boite{height:27mm}
body.cloture .signatures{margin-top:4mm}
body.cloture .titre{padding:7mm 0 2mm}
body.cloture h2{margin:6mm 0 2.8mm}
.petit{font-size:8.2pt;color:__GRIS__;line-height:1.45}
.conclusion{margin-top:3mm;font-size:8.8pt;color:__GRIS__}
.conclusion b{color:__NAVY__}

/* ── Annexe : rétractation ── */
.loi{margin-bottom:1.8mm;font-size:7.8pt;line-height:1.4}
.annexe h2{margin:5mm 0 2.4mm}
.annexe .intro{font-size:9.2pt;margin-bottom:2.4mm}
.loi b{display:block;font-size:6.9pt;letter-spacing:.16em;
  text-transform:uppercase;color:__BRONZE__;margin-bottom:.6mm}
.loi p{margin-bottom:.7mm}
.bordereau{break-inside:avoid;margin-top:4mm;border:.9pt dashed __NAVY__;
  border-radius:2.6mm;padding:3.6mm 5mm 4.4mm;font-size:9.2pt;line-height:1.5}
.bordereau .ciseaux{font-size:6.9pt;letter-spacing:.16em;
  text-transform:uppercase;color:__BRONZE__;font-weight:700;margin-bottom:1.6mm}
.bordereau h3{font-family:__TITRE__;font-weight:400;font-size:13pt;
  color:__NAVY__;margin-bottom:2mm}
.bordereau .trou{display:inline-block;min-width:52mm;
  border-bottom:.6pt dotted #9AA3B0}
.bordereau .trou.long{min-width:112mm}
.bordereau .bas{display:table;width:100%;margin-top:3mm}
.bordereau .bas div{display:table-cell;width:50%;vertical-align:top}
.suite{break-before:page}
.souffle{height:2mm}
"""


@functools.lru_cache(maxsize=1)
def css():
    """La feuille complète (polices embarquées comprises), calculée une fois."""
    remplacements = {
        '__NAVY_900__': NAVY_900, '__NAVY__': NAVY, '__OR__': OR,
        '__BRONZE__': BRONZE, '__ENCRE__': ENCRE, '__GRIS__': GRIS,
        '__FILET__': FILET, '__LAVIS_OR__': LAVIS_OR, '__LAVIS__': LAVIS,
        '__VERT_FOND__': VERT_FOND, '__VERT__': VERT, '__PAPIER__': PAPIER,
        '__TITRE__': POLICE_TITRE, '__TEXTE__': POLICE_TEXTE,
        '__KHATAM__': _MOTIF_KHATAM,
    }
    feuille = _CSS
    for jeton, valeur in remplacements.items():
        feuille = feuille.replace(jeton, valeur)
    return _polices() + feuille
