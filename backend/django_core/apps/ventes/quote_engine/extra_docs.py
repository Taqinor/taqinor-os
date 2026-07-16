# -*- coding: utf-8 -*-
"""Documents clients ADDITIFS rendus dans le MÊME langage visuel premium que le
devis — SANS toucher ni redessiner ``generate_devis_premium.py``.

Deux familles de documents, tous CLIENT-FACING (jamais de prix d'achat / marge) :

1. ``build_lettre_relance_html`` / ``render_lettre_relance_pdf`` — trois lettres
   de relance à ton croissant (1 courtois, 2 ferme, 3 mise en demeure) pour une
   facture en retard. Le CORPS s'adapte au niveau : si le ``FollowupLevel`` du
   niveau (J+7 doux → J+30 ferme) porte un ``message``, ce texte remplace le
   corps par défaut ; sinon le corps par défaut du ton est conservé (la mise en
   page premium ne change jamais — seul le texte des paragraphes varie).
2. ``build_fiche_remise_html`` / ``render_fiche_remise_pdf`` — fiche de remise /
   garantie après-vente sur UNE page pour un chantier.

Ces générateurs IMPORTENT les helpers visuels du moteur premium (logo, polices,
jetons de couleur, pied de page, rendu WeasyPrint) — ils ne le modifient jamais.
L'identité société (nom, adresse, ICE, logo, RC…) vient de
``parametres.CompanyProfile`` via ``apps.ventes.utils.pdf._company_context``, donc
chaque locataire imprime sa propre identité.
"""
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path

# Helpers visuels RÉUTILISÉS depuis le moteur premium (jamais modifié ici).
from .generate_devis_premium import (
    CA, CAL, CG1, CG2, CG4, CG7, CGR, CN,
    _DMSANS400, _DMSANS500, _DMSANS700, _DS400,
    _font_face, fmt,
)

BASE_DIR = Path(__file__).resolve().parent

# ── Polices + base CSS partagés (mêmes familles que le devis premium) ────────
_FONT_CSS = (
    _font_face("DM Serif Display", 400, "normal", _DS400)
    + _font_face("DM Sans", 400, "normal", _DMSANS400)
    + _font_face("DM Sans", 500, "normal", _DMSANS500)
    + _font_face("DM Sans", 700, "normal", _DMSANS700)
)

_PAGE_CSS = f"""
{_FONT_CSS}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
html{{background:#FFFFFF !important;}}
body{{font-family:'DM Sans',sans-serif;font-size:10pt;color:{CG7};
  background:#FFFFFF !important;
  -webkit-print-color-adjust:exact;print-color-adjust:exact;}}
@page{{size:A4;margin:0;background:#FFFFFF;}}
.page{{width:210mm;height:297mm;overflow:hidden;display:flex;
  flex-direction:column;background:#FFFFFF !important;}}
.serif{{font-family:'DM Serif Display',Georgia,serif;}}
.hdr{{background:{CN};padding:20px 30px;display:flex;align-items:center;
  justify-content:space-between;}}
.hdr-logo img{{height:42px;width:auto;object-fit:contain;display:block;}}
.hdr-meta{{text-align:right;color:#FFFFFF;font-size:8pt;line-height:1.5;}}
.hdr-meta .doc-kind{{color:{CA};font-weight:700;font-size:11pt;letter-spacing:.5px;}}
.body{{flex:1;padding:26px 34px 18px;display:flex;flex-direction:column;}}
.party{{display:flex;justify-content:space-between;gap:24px;margin-bottom:20px;}}
.party .blk{{font-size:9pt;line-height:1.5;color:{CG7};}}
.party .blk .lbl{{font-size:6.5pt;font-weight:700;letter-spacing:.6px;
  text-transform:uppercase;color:{CG4};margin-bottom:3px;}}
.party .blk strong{{color:{CN};font-size:10pt;}}
.title{{font-size:17pt;color:{CN};margin:6px 0 14px;font-weight:700;}}
.title.serif{{font-family:'DM Serif Display',Georgia,serif;}}
.lead{{font-size:9.5pt;line-height:1.6;color:{CG7};margin-bottom:12px;}}
.lead p{{margin-bottom:10px;}}
.callout{{background:{CG1};border-left:3px solid {CA};border-radius:6px;
  padding:12px 16px;margin:8px 0 14px;}}
.callout .row{{display:flex;justify-content:space-between;font-size:9.5pt;
  padding:2px 0;}}
.callout .row .v{{font-weight:700;color:{CN};}}
.callout .row.due .v{{color:{CA};font-size:11pt;}}
.tbl{{width:100%;border-collapse:collapse;font-size:8.5pt;margin:6px 0 12px;}}
.tbl th{{background:{CG1};color:{CG4};font-size:6.5pt;font-weight:700;
  text-transform:uppercase;letter-spacing:.5px;padding:6px 8px;
  border-bottom:1px solid {CG2};text-align:left;}}
.tbl td{{padding:5px 8px;border-bottom:1px solid {CG2}80;
  vertical-align:top;color:{CG7};}}
.tbl td.c{{text-align:center;}}
.gar td.g{{color:{CGR};font-weight:600;}}
.section-h{{font-size:7.5pt;font-weight:700;letter-spacing:.7px;
  text-transform:uppercase;color:{CA};margin:10px 0 6px;}}
.guidance li{{font-size:8.5pt;line-height:1.5;color:{CG7};
  margin:0 0 4px 16px;}}
.sign{{display:flex;justify-content:space-between;gap:30px;margin-top:auto;
  padding-top:14px;}}
.sign .box{{flex:1;font-size:8pt;color:{CG4};}}
.sign .box .line{{border-top:1px solid {CG2};margin-top:34px;padding-top:4px;}}
.stamp{{display:inline-block;background:{CAL};border:1px solid {CA};
  border-radius:6px;padding:5px 12px;font-size:8.5pt;font-weight:700;
  color:{CN};margin-bottom:10px;}}
.ftr{{background:{CN};padding:8px 30px 9px;flex-shrink:0;}}
.ftr-top{{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:4px;}}
.ftr-brand{{font-size:9pt;font-weight:800;color:{CA};letter-spacing:1px;}}
.ftr-contact{{font-size:7pt;color:#AAB;text-align:center;}}
.ftr-legal{{font-size:7pt;color:#889;text-align:center;font-style:italic;}}
"""


# ── Helpers ──────────────────────────────────────────────────────────────────
def _logo_block(ctx):
    """Logo de l'en-tête : logo SOCIÉTÉ (CompanyProfile) si fourni.

    SCA26 (fix règle-#4) — À DÉFAUT de logo société, on ne retombe PLUS sur le
    logo premium TAQINOR (qui affichait la marque du fondateur sur les documents
    d'un AUTRE locataire) : on rend un bloc NEUTRE (nom de la société stylé en
    blanc sur l'en-tête navy), ou rien si aucun nom n'est renseigné. Le fondateur
    conserve son rendu en téléversant son propre logo (CompanyProfile.logo_key).
    """
    uri = ctx.get("logo_uri")
    if uri:
        return (f'<img src="{escape(uri, quote=True)}" alt="logo" '
                f'style="height:42px;width:auto;object-fit:contain;'
                f'display:block;">')
    nom = escape(str(ctx.get("entreprise_nom") or "").strip())
    if not nom:
        return ""
    return (f'<div style="font-family:\'DM Sans\',sans-serif;font-size:15pt;'
            f'font-weight:800;color:#FFFFFF;letter-spacing:.5px;'
            f'line-height:1.1;">{nom}</div>')


def _fr_date(value):
    """Date au format JJ/MM/AAAA (str, date ou None)."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value)[:10]


def _company_lines(ctx):
    """Lignes d'identité société pour l'en-tête (adresse + coordonnées)."""
    parts = []
    if ctx.get("entreprise_adresse"):
        parts.append(escape(str(ctx["entreprise_adresse"]).replace("\n", " ")))
    contact = []
    if ctx.get("entreprise_telephone"):
        contact.append(escape(str(ctx["entreprise_telephone"])))
    if ctx.get("entreprise_email"):
        contact.append(escape(str(ctx["entreprise_email"])))
    if contact:
        parts.append(" · ".join(contact))
    return "<br>".join(parts)


def _legal_line(ctx):
    """Ligne d'identité légale du pied de page (RC/ICE/IF si présents)."""
    bits = []
    if ctx.get("entreprise_nom"):
        bits.append(escape(str(ctx["entreprise_nom"])))
    for label, key in (("RC", "entreprise_rc"), ("ICE", "entreprise_ice"),
                       ("IF", "entreprise_if"),
                       ("Patente", "entreprise_patente")):
        val = ctx.get(key)
        if val:
            bits.append(f"{label} {escape(str(val))}")
    return " · ".join(bits)


def _header(ctx, doc_kind, ref_line):
    return (
        f'<div class="hdr"><div class="hdr-logo">{_logo_block(ctx)}</div>'
        f'<div class="hdr-meta"><div class="doc-kind">{escape(doc_kind)}</div>'
        f'{ref_line}</div></div>'
    )


def _footer(ctx):
    contact = []
    if ctx.get("entreprise_email"):
        contact.append(escape(str(ctx["entreprise_email"])))
    if ctx.get("entreprise_telephone"):
        contact.append(escape(str(ctx["entreprise_telephone"])))
    contact_html = " &nbsp;·&nbsp; ".join(contact)
    legal = _legal_line(ctx)
    nom = escape(str(ctx.get("entreprise_nom", "")))
    return (
        f'<div class="ftr"><div class="ftr-top">'
        f'<div class="ftr-brand">{nom}</div>'
        f'<div class="ftr-contact">{contact_html}</div>'
        f'<div></div></div>'
        f'<div class="ftr-legal">{legal}</div></div>'
    )


def _party_block(ctx, client):
    """Bloc « émetteur » (société) ↔ « destinataire » (client)."""
    cl_nom = escape(f"{client.get('nom', '')} "
                    f"{client.get('prenom', '') or ''}".strip())
    cl_lines = []
    if client.get("adresse"):
        cl_lines.append(escape(str(client["adresse"]).replace("\n", " ")))
    if client.get("telephone"):
        cl_lines.append(escape(str(client["telephone"])))
    if client.get("email"):
        cl_lines.append(escape(str(client["email"])))
    cl_html = "<br>".join(cl_lines)
    return (
        f'<div class="party">'
        f'<div class="blk"><div class="lbl">Émetteur</div>'
        f'<strong>{escape(str(ctx.get("entreprise_nom", "")))}</strong><br>'
        f'{_company_lines(ctx)}</div>'
        f'<div class="blk" style="text-align:right;">'
        f'<div class="lbl">Destinataire</div>'
        f'<strong>{cl_nom}</strong>'
        f'{("<br>" + cl_html) if cl_html else ""}</div>'
        f'</div>'
    )


def _shell(ctx, doc_kind, ref_line, body_html, title):
    head = _header(ctx, doc_kind, ref_line)
    ftr = _footer(ctx)
    return (
        f'<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
        f'<title>{escape(title)}</title><style>{_PAGE_CSS}</style></head>'
        f'<body><div class="page">{head}'
        f'<div class="body">{body_html}</div>{ftr}</div></body></html>'
    )


def _render_pdf(html):
    """HTML → octets PDF (WeasyPrint, base_url = dossier du moteur pour les
    polices/assets locaux). Aucun appel réseau."""
    from weasyprint import HTML
    buf = BytesIO()
    HTML(string=html, base_url=f"file://{BASE_DIR}/").write_pdf(buf)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════════════
# 1) LETTRES DE RELANCE — trois tons croissants
# ═══════════════════════════════════════════════════════════════════════════
# Niveau → (marqueur de ton, titre, corps). Le marqueur de ton est imprimé en
# toutes lettres dans l'en-tête pour distinguer les trois lettres de façon
# robuste (et testable). Les corps montent en fermeté : courtois → ferme →
# mise en demeure.
RELANCE_TONES = {
    1: {
        "marker": "Relance amiable",
        "title": "Premier rappel — règlement de facture",
        "paras": [
            "Cher client, sauf erreur ou omission de notre part, la facture "
            "référencée ci-dessus demeure impayée à ce jour. Il s'agit "
            "probablement d'un simple oubli.",
            "Nous vous serions reconnaissants de bien vouloir procéder à son "
            "règlement dans les meilleurs délais. Si le paiement a déjà été "
            "effectué, nous vous prions de ne pas tenir compte de ce rappel.",
            "Nous restons à votre entière disposition pour toute question "
            "relative à cette facture et vous remercions de votre confiance.",
        ],
    },
    2: {
        "marker": "Relance ferme",
        "title": "Deuxième relance — facture échue",
        "paras": [
            "Malgré notre précédent rappel, nous constatons que la facture "
            "référencée ci-dessus reste impayée à ce jour. Le délai de "
            "règlement convenu est désormais dépassé.",
            "Nous vous demandons de régulariser cette situation sans délai. À "
            "défaut de paiement sous huitaine, nous serons contraints "
            "d'engager les démarches de recouvrement prévues.",
            "Nous vous invitons à nous contacter rapidement si un différend "
            "ou une difficulté justifie ce retard, afin de trouver ensemble "
            "une solution.",
        ],
    },
    3: {
        "marker": "Mise en demeure",
        "title": "Mise en demeure de payer",
        "paras": [
            "En dépit de nos relances successives restées sans effet, la "
            "facture référencée ci-dessus demeure intégralement impayée. Par "
            "la présente, nous vous mettons formellement en demeure de "
            "procéder à son règlement.",
            "Vous disposez d'un délai de QUINZE (15) JOURS à compter de la "
            "réception de la présente pour vous acquitter de la somme due. À "
            "défaut, nous nous réservons le droit d'engager toute procédure de "
            "recouvrement contentieux, sans nouvel avis, à vos frais et "
            "risques.",
            "La présente mise en demeure fait courir les intérêts de retard et "
            "vaut interpellation au sens de la loi. Nous vous invitons à "
            "donner à cette affaire toute l'attention qu'elle requiert.",
        ],
    },
}


def _facture_resume(facture):
    """Résumé chiffré d'une facture pour la lettre (aucun prix d'achat)."""
    return {
        "reference": facture.reference,
        "date_emission": _fr_date(getattr(facture, "date_emission", None)),
        "date_echeance": _fr_date(getattr(facture, "date_echeance", None)),
        "total_ttc": facture.total_ttc,
        "montant_du": facture.montant_du,
        "jours_retard": facture.jours_retard,
    }


def _custom_message_paras(message, resume):
    """Découpe un message de niveau (``FollowupLevel.message``) en paragraphes.

    Le message configuré par l'admin escalade le ton selon le niveau (J+7 doux →
    J+30 ferme). On respecte ses sauts de ligne (un paragraphe par ligne non
    vide) et on résout le gabarit ``{reference}`` avec la référence de la
    facture. Retourne ``None`` quand aucun message spécifique n'est fourni —
    l'appelant retombe alors sur le corps par défaut (comportement historique).
    """
    if not message or not str(message).strip():
        return None
    try:
        text = str(message).format(reference=resume.get("reference", ""))
    except (KeyError, IndexError, ValueError):
        # Gabarit malformé : on imprime le message tel quel, sans planter.
        text = str(message)
    return [block.strip() for block in text.splitlines() if block.strip()]


def build_lettre_relance_html(ctx, client, resume, niveau, message=None):
    """HTML de la lettre de relance de niveau ``niveau`` (1/2/3).

    Si ``message`` (texte du ``FollowupLevel`` du niveau) est fourni et non vide,
    son contenu remplace le CORPS par défaut — la lettre s'adapte ainsi au niveau
    (ton doux J+7 → ferme J+30). Sinon, le corps par défaut du ton est conservé
    (comportement historique). La MISE EN PAGE premium reste identique : seul le
    texte des paragraphes change.
    """
    niveau = int(niveau)
    tone = RELANCE_TONES.get(niveau, RELANCE_TONES[1])
    ref_line = (f"Facture {escape(str(resume['reference']))}<br>"
                f"Le {escape(_fr_date(date.today()))}")
    custom_paras = _custom_message_paras(message, resume)
    body_paras = custom_paras if custom_paras else tone["paras"]
    paras = "".join(f"<p>{escape(p)}</p>" for p in body_paras)
    jr = resume.get("jours_retard") or 0
    retard_txt = f"{jr} jour(s)" if jr else "échéance dépassée"
    callout = (
        f'<div class="callout">'
        f'<div class="row"><span>Facture</span>'
        f'<span class="v">{escape(str(resume["reference"]))}</span></div>'
        f'<div class="row"><span>Date d\'échéance</span>'
        f'<span class="v">{escape(resume["date_echeance"] or "—")}</span></div>'
        f'<div class="row"><span>Retard</span>'
        f'<span class="v">{escape(retard_txt)}</span></div>'
        f'<div class="row due"><span>Montant restant dû</span>'
        f'<span class="v">{escape(fmt(resume["montant_du"]))}</span></div>'
        f'</div>'
    )
    body = (
        _party_block(ctx, client)
        + f'<div class="title serif">{escape(tone["title"])}</div>'
        + f'<div class="lead">{paras}</div>'
        + callout
        + '<div class="lead"><p>Veuillez agréer, cher client, l\'expression '
          'de nos salutations distinguées.</p></div>'
        + '<div class="sign"><div class="box">Le client<div class="line">'
          'Signature</div></div>'
          f'<div class="box" style="text-align:right;">'
          f'{escape(str(ctx.get("entreprise_nom", "")))}'
          '<div class="line">Le service recouvrement</div></div></div>'
    )
    title = f"Relance {resume['reference']} — niveau {niveau}"
    return _shell(ctx, tone["marker"], ref_line, body, title)


def _level_message_for(facture, niveau):
    """Texte du ``FollowupLevel`` (du niveau demandé) configuré pour la société
    de la facture, ou ``None``. Mappe le niveau 1/2/3 sur le n-ième seuil de
    relance trié par délai (J+7 → J+15 → J+30). Lecture seule, jamais d'erreur
    bloquante : si aucun niveau n'est configuré on retombe sur le corps par
    défaut (comportement historique)."""
    try:
        from apps.ventes.models import FollowupLevel
        levels = list(
            FollowupLevel.objects.filter(company=facture.company)
            .order_by("delai_jours", "ordre"))
    except Exception:
        return None
    idx = int(niveau) - 1
    if 0 <= idx < len(levels):
        return levels[idx].message or None
    return None


def render_lettre_relance_pdf(facture, niveau, message=None):
    """Octets PDF de la lettre de relance premium pour ``facture`` au niveau
    ``niveau`` (1/2/3). Identité société résolue depuis CompanyProfile.

    Le corps escalade avec le niveau via ``FollowupLevel.message`` : si un
    ``message`` est passé explicitement il prime ; sinon on résout celui du
    niveau pour la société. À défaut de message configuré, le corps par défaut
    du ton est conservé (comportement historique)."""
    from apps.ventes.utils.pdf import _company_context
    ctx = _company_context(company=facture.company)
    client = facture.client
    client_block = {
        "nom": client.nom,
        "prenom": getattr(client, "prenom", "") or "",
        "email": getattr(client, "email", "") or "",
        "telephone": getattr(client, "telephone", "") or "",
        "adresse": getattr(client, "adresse", "") or "",
    }
    resume = _facture_resume(facture)
    if message is None:
        message = _level_message_for(facture, niveau)
    html = build_lettre_relance_html(ctx, client_block, resume, niveau, message)
    return _render_pdf(html)


# ═══════════════════════════════════════════════════════════════════════════
# 2) FICHE DE REMISE / GARANTIE APRÈS-VENTE — une page
# ═══════════════════════════════════════════════════════════════════════════
DEFAULT_GARANTIE = "Garantie selon conditions constructeur."

OPERATING_GUIDANCE = [
    "Vérifiez chaque mois que les modules ne sont pas ombragés ni encrassés "
    "(poussière, feuilles, fientes).",
    "Nettoyez les panneaux à l'eau claire avec une raclette douce, tôt le "
    "matin ou en fin de journée — jamais sur verre chaud en plein soleil.",
    "Surveillez la production via l'onduleur / l'application : signalez toute "
    "baisse anormale.",
    "Ne couvrez jamais les grilles de ventilation de l'onduleur ; gardez le "
    "local technique propre et sec.",
    "Faites contrôler l'installation par un technicien qualifié au moins une "
    "fois par an (serrages, protections, mise à la terre).",
    "En cas d'anomalie (coupure, fumée, odeur, bruit), coupez au sectionneur "
    "et contactez le service après-vente.",
]


def _chantier_composants(chantier):
    """Composants installés (désignation + quantité + marque + garantie texte).

    Lecture STRICTEMENT publique : ``prix_achat`` n'est jamais lu — impossible
    de le faire fuiter dans un document client.
    """
    devis = getattr(chantier, "devis", None)
    if devis is None:
        return []
    out = []
    for ligne in devis.lignes.select_related("produit").all():
        produit = ligne.produit
        garantie = ((getattr(produit, "garantie", None) or "").strip()
                    if produit else "")
        marque = ((getattr(produit, "marque", None) or "").strip()
                  if produit else "")
        out.append({
            "designation": ligne.designation,
            "quantite": ligne.quantite,
            "marque": marque,
            "garantie": garantie or DEFAULT_GARANTIE,
        })
    return out


def build_fiche_remise_html(ctx, client, chantier_info, composants):
    """HTML de la fiche de remise / garantie après-vente (une page)."""
    ref = chantier_info.get("reference", "")
    ref_line = (f"Chantier {escape(str(ref))}<br>"
                f"Le {escape(_fr_date(date.today()))}")

    # Bandeau système (aucun prix).
    sys_rows = []
    if chantier_info.get("puissance_kwc") is not None:
        sys_rows.append(("Puissance installée",
                         f"{chantier_info['puissance_kwc']} kWc"))
    if chantier_info.get("type_installation"):
        sys_rows.append(("Type", chantier_info["type_installation"]))
    if chantier_info.get("raccordement"):
        sys_rows.append(("Raccordement", chantier_info["raccordement"]))
    site = ", ".join(p for p in (chantier_info.get("site_adresse"),
                                 chantier_info.get("site_ville")) if p)
    if site:
        sys_rows.append(("Site", site))
    if chantier_info.get("date_mise_en_service"):
        sys_rows.append(("Mise en service",
                         chantier_info["date_mise_en_service"]))
    if chantier_info.get("date_reception"):
        sys_rows.append(("Réception", chantier_info["date_reception"]))
    sys_html = "".join(
        f'<div class="row"><span>{escape(str(k))}</span>'
        f'<span class="v">{escape(str(v))}</span></div>'
        for k, v in sys_rows)
    callout = f'<div class="callout">{sys_html}</div>' if sys_html else ""

    # Tableau composants + garanties.
    if composants:
        rows = "".join(
            f'<tr><td>{escape(str(c["designation"]))}'
            f'{(" — " + escape(str(c["marque"]))) if c.get("marque") else ""}'
            f'</td><td class="c">{escape(str(c["quantite"]))}</td>'
            f'<td class="g">{escape(str(c["garantie"]))}</td></tr>'
            for c in composants)
        table = (
            '<div class="section-h">Équipements installés &amp; garanties</div>'
            '<table class="tbl gar"><thead><tr>'
            '<th>Désignation</th><th>Qté</th><th>Garantie</th>'
            '</tr></thead><tbody>' + rows + '</tbody></table>')
    else:
        table = ('<div class="section-h">Équipements installés &amp; '
                 'garanties</div>'
                 '<div class="lead"><p>Le détail des équipements est annexé au '
                 'dossier de remise du chantier.</p></div>')

    guidance = "".join(f"<li>{escape(g)}</li>" for g in OPERATING_GUIDANCE)

    body = (
        _party_block(ctx, client)
        + '<div class="title serif">Fiche de remise &amp; garantie '
          'après-vente</div>'
        + '<div class="lead"><p>Nous vous remettons votre installation '
          'photovoltaïque, mise en service et contrôlée. Ce document récapitule '
          'votre système, les garanties applicables et les bonnes pratiques '
          'd\'exploitation.</p></div>'
        + callout
        + table
        + '<div class="section-h">Exploitation &amp; entretien</div>'
          f'<ul class="guidance">{guidance}</ul>'
        + '<div class="sign"><div class="box">Remis au client le '
          f'{escape(_fr_date(date.today()))}<div class="line">Signature du '
          'client</div></div>'
          f'<div class="box" style="text-align:right;">'
          f'{escape(str(ctx.get("entreprise_nom", "")))}'
          '<div class="line">Le technicien responsable</div></div></div>'
    )
    title = f"Fiche de remise — {ref}"
    return _shell(ctx, "Fiche de remise / garantie", ref_line, body, title)


def render_fiche_remise_pdf(chantier):
    """Octets PDF de la fiche de remise / garantie premium pour ``chantier``."""
    from apps.ventes.utils.pdf import _company_context
    ctx = _company_context(company=chantier.company)
    client = chantier.client
    client_block = {
        "nom": client.nom if client else "",
        "prenom": (getattr(client, "prenom", "") or "") if client else "",
        "email": (getattr(client, "email", "") or "") if client else "",
        "telephone": (getattr(client, "telephone", "") or "") if client else "",
        "adresse": (getattr(client, "adresse", "") or "") if client else "",
    }
    type_label = (chantier.get_type_installation_display()
                  if getattr(chantier, "type_installation", None) else None)
    info = {
        "reference": chantier.reference,
        "puissance_kwc": chantier.puissance_installee_kwc,
        "type_installation": type_label,
        "raccordement": (chantier.get_raccordement_display()
                         if getattr(chantier, "raccordement", None) else None),
        "site_adresse": chantier.site_adresse,
        "site_ville": chantier.site_ville,
        "date_mise_en_service": _fr_date(chantier.date_mise_en_service),
        "date_reception": _fr_date(chantier.date_reception),
    }
    composants = _chantier_composants(chantier)
    html = build_fiche_remise_html(ctx, client_block, info, composants)
    return _render_pdf(html)
