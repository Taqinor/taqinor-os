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
  chaque état a son mot (« Réglé », « À régler », « À venir ») ; l'état « à
  régler » et l'étape en cours portent en plus un anneau bleu nuit épais et un
  chiffre gras (en gris, l'or seul devient le plus clair des trois) ;
- toute bordure qui doit se voir en noir et blanc est à ≥ 3:1 (``TRAIT``).
"""
import base64
import functools
import logging

logger = logging.getLogger(__name__)

NAVY = '#1A2B4A'
NAVY_900 = '#12203B'
OR = '#F5A623'
BRONZE = '#8A5A00'
ENCRE = '#1F2937'
GRIS = '#5B6472'
FILET = '#E3E6EB'
LAVIS = '#F6F7F9'
LAVIS_OR = '#FDF6E7'
VERT = '#0F6630'
VERT_FOND = '#E9F5EE'
PAPIER = '#FFFFFF'
# Bordures qui doivent se voir en photocopie (paraphes, cadres de signature,
# lignes à remplir, pastille « À venir ») : contraste ≥ 3:1 sur le blanc.
TRAIT = '#8A93A1'

POLICE_TITRE = "'DM Serif Display', Georgia, serif"
POLICE_TEXTE = "'DM Sans', 'Noto Sans', system-ui, sans-serif"
# Traduction arabe : polices système de l'image (DM Serif / DM Sans n'ont aucun
# glyphe arabe). Naskh pour lire, Kufi pour les petits libellés.
POLICE_AR_TEXTE = "'Noto Naskh Arabic', 'Noto Sans Arabic', 'DM Sans', serif"
POLICE_AR_LIBELLE = "'Noto Kufi Arabic', 'Noto Sans Arabic', 'DM Sans', sans-serif"


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
        logger.warning('Polices du moteur de devis indisponibles : repli sur '
                       'les polices système', exc_info=True)
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
.paraphe i{display:block;height:8.4mm;border:.7pt solid __TRAIT__;
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
  border:.7pt solid __TRAIT__;color:__GRIS__;font-weight:500;font-size:7.4pt;
  text-align:center;line-height:5.1mm;margin-right:2mm;background:__PAPIER__}
.etape.fait .n{background:__NAVY__;border-color:__NAVY__;color:#FFFFFF;
  font-weight:700}
.etape.ici{color:__NAVY__;font-weight:700}
.etape.ici .n{background:__OR__;border:1.5pt solid __NAVY__;
  color:__NAVY_900__;font-weight:700;line-height:4.3mm}
.etape small{display:block;font-size:6.3pt;font-weight:400;color:__GRIS__;
  letter-spacing:.02em}

/* ── Corps ── */
.corps{padding:0 20mm}
.titre{padding:8.5mm 0 3mm}
.surtitre{font-size:7.6pt;letter-spacing:.2em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700;margin-bottom:2.2mm;string-set:acte content()}
.reference-courante{string-set:reference content();height:0;overflow:hidden;
  line-height:0;font-size:1pt;color:__PAPIER__}
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
  font-weight:500;font-size:9.4pt;text-align:center;line-height:8.2mm}
.jalon .trait{flex:1;height:.9pt;background:#C4CAD4;margin-left:2mm}
.jalon:last-child .trait{background:transparent}
.jalon.regle .pastille{background:__VERT__;border-color:__VERT__;color:#FFFFFF;
  font-weight:700}
.jalon.exigible .pastille{background:__OR__;border:2pt solid __NAVY__;
  color:__NAVY_900__;font-weight:700;line-height:7.2mm}
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
  border:.7pt solid __TRAIT__;color:__GRIS__;background:__PAPIER__}
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
table.garanties.dates td:first-child{width:27%}
table.garanties.dates td:nth-child(2){width:17%}
table.garanties.dates td:nth-child(3){width:20%}
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
.article{position:relative;padding:4mm 0 0 40mm;margin-top:4mm;
  border-top:.6pt solid __FILET__;min-height:15mm}
.article .marge{position:absolute;left:0;top:4mm;width:36mm}
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
.encadre.quitus p + p{margin-top:2mm}
.grand.sav{font-size:15pt}
.article .texte .encadre{margin:2.6mm 0 0}
.grand{font-family:__TITRE__;font-size:19pt;color:__NAVY__;line-height:1.2;
  white-space:nowrap}
.lettres{font-size:8.8pt;color:__GRIS__;font-style:italic}
.deux{display:table;width:100%;table-layout:fixed}
.deux .chiffre,.deux .explication{display:table-cell;vertical-align:top}
.deux .chiffre{width:40%;padding-right:5mm}
.deux .explication{padding-top:1.4mm}
.deux .explication p + p{margin-top:.8mm}

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
.part-retenue{margin-top:2.4mm;font-weight:700;color:__NAVY__;font-size:9.2pt}
.a-remplir{display:inline-block;min-width:34mm;height:4mm;margin:0 1mm;
  border-bottom:.7pt dotted __TRAIT__;vertical-align:baseline}
.insecable{break-inside:avoid}
.lignes i{display:block;border-bottom:.7pt dotted __TRAIT__;height:7.4mm}

/* ── Signatures ── */
.signatures{break-inside:avoid;break-before:avoid;margin-top:7mm}
.fait-a{font-size:9.8pt;margin-bottom:3.4mm}
.fait-a .trou{display:inline-block;min-width:38mm;
  border-bottom:.7pt dotted __TRAIT__}
.sig{display:table;width:100%;table-layout:fixed;border-collapse:separate;
  border-spacing:0}
.sig .cellule{display:table-cell;width:50%;vertical-align:top;
  padding-right:2mm}
.sig .cellule + .cellule{padding-right:0;padding-left:2mm}
.sig .boite{border:.7pt solid __TRAIT__;border-radius:2.6mm;
  padding:3.6mm 4.4mm 4mm;height:47mm}
.sig .lbl{font-size:6.9pt;letter-spacing:.16em;text-transform:uppercase;
  color:__BRONZE__;font-weight:700}
.sig .qui{font-weight:700;color:__NAVY__;font-size:10.4pt;margin-top:.6mm}
.sig .ident{font-size:8.4pt;color:__GRIS__;line-height:1.35}
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
body.proces h2{margin:4.2mm 0 2.2mm;font-size:14pt}
body.proces .carte{padding:3.2mm 4.2mm 3.4mm}
body.proces .carte .val{font-size:15pt}
body.proces td{padding-top:1.7mm;padding-bottom:1.7mm}
body.proces .encadre{padding:3mm 4.2mm;margin:2.4mm 0}
body.proces .signatures{margin-top:2.8mm}
body.proces .article .texte{font-size:9.5pt;line-height:1.4}
body.proces .article{padding:2.4mm 0 0 40mm;margin-top:2.4mm}
body.proces .article .marge{top:2.4mm}
body.proces .article .texte p{margin-bottom:1.4mm}
body.proces .article .texte ul{margin-bottom:1.4mm}
body.proces .jalon .tete{margin-bottom:1.6mm}
body.proces .jalon .pastille{width:7.6mm;height:7.6mm;line-height:7.2mm;
  font-size:8.8pt}
body.proces .jalon.exigible .pastille{line-height:6.2mm}
body.proces .jalon .combien{font-size:14pt;margin-top:.6mm}
body.proces .jalon .etat{margin-top:.9mm}
body.proces .jalon .quoi{margin-top:.2mm}
body.proces .grand{font-size:17pt}
body.proces .fait-a{margin-bottom:2mm}
body.proces .lignes i{height:6.4mm}
body.proces .sig .boite{height:38mm}
body.cloture .article .texte{font-size:9.5pt;line-height:1.42}
body.cloture .article{padding-top:2.6mm;margin-top:2.6mm}
body.cloture .article .marge{top:2.6mm}
body.cloture .article .texte p{margin-bottom:1.6mm}
body.cloture .article .texte li{margin-bottom:.7mm}
body.cloture .conseil{margin-bottom:3mm;padding-top:2.2mm}
body.cloture .conseil p{line-height:1.45}
body.cloture .journee{margin:1.6mm 0 3.6mm}
body.cloture .article.plein{padding-left:0}
body.cloture td{padding-top:1.5mm;padding-bottom:1.5mm}
.sig.seule .boite{height:27mm}
body.cloture .signatures{margin-top:4mm}
body.cloture .titre{padding:6.5mm 0 2mm}
body.cloture h2{margin:4.8mm 0 2.4mm}
.petit{font-size:8.2pt;color:__GRIS__;line-height:1.45}
.souffle{height:2mm}
"""

# ── Traduction arabe : la même page, en miroir ──────────────────────────────
# Ajoutée APRÈS la feuille commune (mêmes sélecteurs, donc elle l'emporte).
# Règles : Naskh plus grand que le latin et interligne ~1,8 ; aucun espacement
# de lettres ni capitales forcées (ils cassent la liaison) — les petits
# libellés se distinguent par le Kufi, la graisse et le bronze ; tout ce qui
# était à gauche passe à droite (titre d'article en marge, filets d'encadré,
# puces, colonnes de chiffres à gauche) ; les fragments latins (``.ltr``) sont
# isolés de gauche à droite et gardent les polices latines du français.
_CSS_AR = """
@page{
  @top-left{content:string(reference);font-family:__TEXTE__;font-size:7.4pt;
    letter-spacing:0;text-transform:none;color:__GRIS__;padding-left:20mm;
    padding-right:0;vertical-align:bottom;padding-bottom:4mm}
  @top-right{content:string(acte);font-family:__AR_LIBELLE__;font-size:7.6pt;
    letter-spacing:0;text-transform:none;color:__GRIS__;padding-right:20mm;
    padding-left:0;vertical-align:bottom;padding-bottom:4mm}}
@page:first{@top-left{content:none}@top-right{content:none}}
html{font-family:__AR_TEXTE__;font-size:11.4pt;line-height:1.8;
  direction:rtl;text-align:right}
body *{letter-spacing:0 !important;text-transform:none !important}
.ltr{unicode-bidi:isolate;direction:ltr;font-family:__TEXTE__;font-size:.9em}
strong .ltr,b .ltr{font-weight:700}

/* Pied */
.pied{font-size:7pt;line-height:1.6}
.pied-legal{padding-right:0;padding-left:6mm}
.pied-legal b{font-size:7.4pt}
.paraphes{margin-right:0;margin-left:5mm}
.paraphes span{font-family:__AR_LIBELLE__;font-size:6.4pt}
.paraphe{margin-left:0;margin-right:2mm}
.folio{text-align:left}
.folio i::after{content:"صفحة " counter(page) " من " counter(pages)}
.folio i{font-family:__AR_LIBELLE__}

/* En-tête et parcours */
.bandeau .ref{text-align:left}
.etape{font-family:__AR_LIBELLE__;font-size:8pt;line-height:1.45}
.etape .n{margin-right:0;margin-left:2mm;font-family:__TEXTE__;
  line-height:5.1mm}
.etape small{font-family:__AR_TEXTE__;font-size:7pt}

/* Titres */
.surtitre{font-family:__AR_LIBELLE__;font-size:8.2pt}
h1{font-family:__AR_TEXTE__;font-weight:700;font-size:25pt;line-height:1.45}
.chapeau{font-size:11.6pt;line-height:1.75}
h2{font-family:__AR_TEXTE__;font-weight:700;font-size:15.5pt;line-height:1.5}
h2 .etoile{margin-right:0;margin-left:2.4mm}
.intro{font-size:10.6pt;line-height:1.7}
h1 .ltr,h2 .ltr{font-family:__TITRE__;font-weight:400}

/* Cartes */
.carte .lbl{font-family:__AR_LIBELLE__;font-size:7.6pt}
.carte .val{font-family:__AR_TEXTE__;font-weight:700;font-size:17pt;
  line-height:1.4}
.carte .val .ltr{font-family:__TITRE__;font-weight:400;font-size:1em}
.carte .det{font-size:9.6pt;line-height:1.65}

/* Frise : de droite à gauche */
.jalon{padding:0 0 0 3mm}
.jalon .trait{margin-left:0;margin-right:2mm}
.jalon .pastille{font-family:__TEXTE__}
.jalon .quand{font-family:__AR_LIBELLE__;font-size:7.6pt}
.jalon .quoi{font-size:11pt;line-height:1.5}
.jalon .combien{font-family:__AR_TEXTE__;font-size:14pt;line-height:1.45}
.jalon .combien .ltr{font-family:__TITRE__;font-size:1.07em}
.jalon .combien small .ltr{font-family:__TEXTE__;font-size:1em}
.jalon .combien small{font-family:__AR_TEXTE__;font-size:8.8pt}
.jalon .etat{font-family:__AR_LIBELLE__;font-size:7.6pt}
.jalon .note{font-size:8.8pt}

/* Tableaux : texte à droite, chiffres au bord gauche */
table{font-size:10pt;line-height:1.6}
th{font-family:__AR_LIBELLE__;font-size:7.6pt;text-align:right;
  padding:0 0 1.8mm 2.4mm}
td{padding:2.3mm 0 2.3mm 2.4mm}
td.n,th.n{text-align:left;padding-left:0;padding-right:0}
td small{font-size:8.8pt}
.duree{font-family:__AR_TEXTE__;font-weight:700;font-size:12.6pt;
  line-height:1.4}

/* Parties */
.partie{font-size:10pt;line-height:1.7}
.partie .lbl{font-family:__AR_LIBELLE__;font-size:7.6pt}
.partie .nom{font-family:__TITRE__;font-size:13.5pt}
.partie .ci-apres{font-size:9pt}

/* Articles : titre en marge à DROITE, colonne de lecture à gauche */
.article{padding:4mm 40mm 0 0}
.article .marge{left:auto;right:0}
.article .num{font-family:__AR_LIBELLE__;font-size:7.6pt}
.article h3{font-family:__AR_TEXTE__;font-weight:700;font-size:12.6pt;
  line-height:1.45}
.article .texte{font-size:11pt}
.article.plein{padding-right:0}
.article .texte li{padding-left:0;padding-right:4.4mm}
.article .texte li::before{left:auto;right:.4mm;top:3mm}

/* Encadrés : filet à droite */
.encadre{border-left:none;border-right:1.1mm solid __OR__;
  border-radius:2mm 0 0 2mm;font-size:10.4pt;line-height:1.7}
.encadre.net{border-right-color:__NAVY__}
.encadre.ok{border-right-color:__VERT__}
.encadre .lbl{font-family:__AR_LIBELLE__;font-size:7.6pt}
.grand{font-family:__AR_TEXTE__;font-weight:700;line-height:1.45}
.grand .ltr{font-family:__TITRE__;font-weight:400;font-size:1em}
.deux .chiffre{padding-right:0;padding-left:5mm}

/* Cases */
.case{font-size:10.6pt;line-height:1.65}
.case i{margin:1.4mm 0 0 2.8mm}

/* Signatures */
.fait-a{font-size:10.6pt}
.sig .cellule{padding-right:0;padding-left:2mm}
.sig .cellule + .cellule{padding-left:0;padding-right:2mm}
.sig .lbl{font-family:__AR_LIBELLE__;font-size:7.6pt}
.sig .qui{font-size:11pt}
.sig .ident{font-size:9pt}
.sig .mention{font-size:9pt;line-height:1.6}
.sig .preuve{font-size:8pt}
.sceau{font-family:__AR_LIBELLE__}

/* Conseils */
.conseil .lbl{font-family:__AR_LIBELLE__;font-size:7.6pt}
.conseil h3{font-family:__AR_TEXTE__;font-weight:700;font-size:12.6pt;
  line-height:1.45}
.conseil p{font-size:10.2pt;line-height:1.7}
.journee .rail div{font-family:__AR_LIBELLE__;font-size:7.6pt}
.journee .sous{font-size:8.2pt;line-height:1.5}

.petit{font-size:9pt;line-height:1.65}
/* Procès-verbaux : deux pages comme en français — plus serré */
body.proces h1{font-size:21pt;line-height:1.35}
body.proces .titre{padding:5.5mm 0 1.5mm}
body.proces .chapeau{font-size:10.4pt;line-height:1.6;margin-top:1.6mm}
body.proces h2{font-size:13.6pt;line-height:1.35;margin:4.6mm 0 2mm}
body.proces .intro{font-size:9.8pt;line-height:1.5;margin-bottom:2.6mm}
body.proces .carte{padding:2.6mm 4.2mm 2.8mm}
body.proces .carte .val{font-size:15pt;line-height:1.3}
body.proces .carte .det{font-size:9pt;line-height:1.45}
body.proces table{font-size:9.4pt;line-height:1.4}
body.proces td{padding-top:1.3mm;padding-bottom:1.3mm}
body.proces .case{font-size:10pt;line-height:1.5;margin-bottom:1.2mm}
body.proces .case i{margin-top:.9mm}
body.proces .encadre{font-size:9.8pt;line-height:1.5;padding:2.6mm 4.2mm;
  margin:2mm 0}
body.proces .grand{line-height:1.3}
body.proces .petit{font-size:8.6pt;line-height:1.5}
body.proces .jalon .tete{margin-bottom:1.6mm}
body.proces .jalon .quoi{font-size:10.4pt;line-height:1.35}
body.proces .jalon .combien{font-size:13.4pt;line-height:1.35;margin-top:.4mm}
body.proces .jalon .etat{margin-top:1mm}
body.proces .article{padding:2.4mm 40mm 0 0;margin-top:2.4mm}
body.proces .article .marge{top:2.4mm}
body.proces .article h3{font-size:12pt;line-height:1.35}
body.proces .article .texte{font-size:10pt;line-height:1.55}
body.proces .article .texte p{margin-bottom:1.4mm}
body.proces .fait-a{font-size:10pt;margin-bottom:2.4mm}
body.proces .sig .mention{line-height:1.45}
/* Clôture : le quitus et sa signature tiennent sur la première page */
body.cloture h1{font-size:24pt;line-height:1.35}
body.cloture .chapeau{font-size:11pt;line-height:1.6;margin-top:2mm}
body.cloture h2{line-height:1.35;margin:5mm 0 2.4mm}
body.cloture .intro{line-height:1.55;margin-bottom:2.8mm}
body.cloture .barre{margin-top:.9mm}
body.cloture .carte{padding:3.4mm 4.6mm 3.6mm}
body.cloture .carte .val{line-height:1.3}
body.cloture .carte .det{line-height:1.5}
body.cloture .encadre{line-height:1.6;padding:3mm 4.6mm}
body.cloture table{line-height:1.45}
body.cloture td{padding-top:1.2mm;padding-bottom:1.2mm}
body.cloture .fait-a{margin-bottom:2.4mm}
body.cloture .article{padding-top:2.6mm;margin-top:2.6mm}
body.cloture .article .marge{top:2.6mm}
body.cloture .article h3{font-size:12pt;line-height:1.35}
body.cloture .article .texte{font-size:10pt;line-height:1.55}
body.cloture .article .texte p{margin-bottom:1.4mm}
body.cloture .article .texte li{margin-bottom:.6mm}
body.cloture .duree{line-height:1.25}
body.cloture td small{line-height:1.35}
body.cloture .article.plein{padding-right:0}
body.cloture .conseil p{line-height:1.6}
"""

_REMPLACEMENTS = {
    '__NAVY_900__': NAVY_900, '__NAVY__': NAVY, '__OR__': OR,
    '__BRONZE__': BRONZE, '__ENCRE__': ENCRE, '__GRIS__': GRIS,
    '__FILET__': FILET, '__LAVIS_OR__': LAVIS_OR, '__LAVIS__': LAVIS,
    '__VERT_FOND__': VERT_FOND, '__VERT__': VERT, '__PAPIER__': PAPIER,
    '__TRAIT__': TRAIT,
    '__TITRE__': POLICE_TITRE, '__TEXTE__': POLICE_TEXTE,
    '__AR_TEXTE__': POLICE_AR_TEXTE, '__AR_LIBELLE__': POLICE_AR_LIBELLE,
    '__KHATAM__': _MOTIF_KHATAM,
}


def _remplir(feuille):
    for jeton, valeur in _REMPLACEMENTS.items():
        feuille = feuille.replace(jeton, valeur)
    return feuille


@functools.lru_cache(maxsize=2)
def css(langue='fr'):
    """La feuille complète (polices embarquées comprises), calculée une fois
    par langue. ``'ar'`` ajoute la feuille de droite à gauche."""
    feuille = _remplir(_CSS)
    if langue == 'ar':
        feuille += _remplir(_CSS_AR)
    return _polices() + feuille
