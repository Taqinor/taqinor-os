# flake8: noqa
"""quote_engine industriel — PAGE 4 (échéancier en N jalons + décarbonation
+ garanties + conditions + signature).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``i3-``.

CIQ344 — les tranches suivent ``synthese_ci['echeancier']`` (N jalons ; défaut
industriel 30/40/20/10 : commande, livraison, mise en service, réception
définitive — D-CIQ-13), montants au centime dont la somme égale le total.
Le bloc décarbonation lit ``synthese_ci['decarbonation']`` : la phrase CBAM
n'apparaît que pour un exportateur UE DÉCLARÉ de ciment ou d'engrais
(Règlement (UE) 2023/956, annexe II), sinon la phrase générique ; jamais
« traçabilité », jamais un tonnage de CO₂. ISO 50001 : une phrase
qualitative, sans promesse de conformité. Rendu seul (règle #4).
"""


# CIQ310 — bande légale du vendeur (RC, ICE, capital) : UNE fonction
# partagée avec le résidentiel.
from ..premium_base import bande_legale
# CIQ311 — blocs C&I communs (conditions, Bon pour accord, échéancier).
from ..ci import blocs as ci_blocs
from .. import premium_base
from ..ci.mentions import TEXTES_DECARBONATION, texte


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]

    # CIQ345 — libellés STRUCTURELS dans la langue du document.
    def L(cle, fr, **valeurs):
        return ci_blocs.libelle(d, cle, fr, **valeurs)

    langue = ci_blocs.langue(d)
    fonts = ctx["fonts"]
    theme = ctx["theme"]
    ident = ctx.get("ident") or {}
    brand = ident.get("brand_name") or "TAQINOR"

    navy, gold, green, green_bg, ink, muted, muted_2, line, line_soft, wash, blue = premium_base.couleurs(
        C, "navy gold green green_bg ink muted muted_2 line line_soft wash blue")

    f_display, f_serif, f_sans = premium_base.polices(fonts)

    synthese = d.get("ind_synthese") or {}

    # ── CIQ344 — ÉCHÉANCIER EN N JALONS (``synthese_ci['echeancier']``) ─────
    # QJR146 (f) — aucun barème reconstruit ici : sans jalon servi, le bloc
    # est OMIS (jamais des conditions de paiement que personne n'a décidées).
    tranches_html = ci_blocs.bloc_echeancier(
        synthese, "i3", navy, ink, line, doc=d)

    # ── CIQ344 — DÉCARBONATION (``synthese_ci['decarbonation']``) ──────────
    decarbonation = synthese.get("decarbonation")
    decarbonation = decarbonation if isinstance(decarbonation, dict) else {}
    cbam = bool(decarbonation.get("cbam"))
    textes_decarbo = decarbonation.get("textes") or TEXTES_DECARBONATION
    titre_decarbo = (
        L("ci_ind_cbam_titre", "CBAM — ajustement carbone aux frontières (UE)")
        if cbam else L("ci_ind_bilan_carbone_titre",
                       "Bilan carbone de votre électricité"))

    # QJR118 — les DURÉES de garantie se dérivent de la composition réelle du
    # devis (source unique ``residential.theme.warranties_for``) ; aucune
    # durée traçable ⇒ la bande entière s'OMET.
    _warranties = [w for w in (theme.warranties_for(d) or [])
                   if w and str(w[0]).strip()]
    if _warranties:
        _cells = "".join(
            f'<div class="i3-warr-c">'
            f'<div class="i3-warr-v">{theme._esc(str(n))} {ci_blocs.textes_garantie(d, u, label)[0]}</div>'
            f'<div class="i3-warr-l">{ci_blocs.textes_garantie(d, u, label)[1]}</div></div>'
            for n, u, label, _sub in _warranties)
        warranties_html = f"""
  <div class="i3-warr">
    <div class="i3-blk-t">{L("ci_garanties", "Garanties")}</div>
    <div class="i3-warr-row" style="margin-top:6px;">
      {_cells}
    </div>
    <div class="i3-warr-l" style="margin-top:5px;">{ci_blocs.legende_garanties(d)}</div>
  </div>
"""
    else:
        warranties_html = ""

    # CIQ311 — « Conditions » (CGV gelées à l'envoi, note TVA) et textes
    # « Bon pour accord » éditables, lus par la même voie que le legacy.
    bpa_titre, bpa_mention = ci_blocs.textes_bpa(d)
    conditions_html = ci_blocs.bloc_conditions(d, "i3", navy, ink)
    # CIQ320 — « Bon pour accord — pour la société ».
    acceptation_html = ci_blocs.bloc_acceptation(d, "i3", ink, line)
    # CIQ314 — seulement les services que le devis porte (jamais une
    # « supervision temps réel » sans ligne derrière).
    services_html = ci_blocs.bloc_services(synthese, "i3", navy, ink, doc=d)
    accepte_nom = (d.get("accepte_par_nom") or "").strip()
    date_accept = (d.get("date_acceptation") or "").strip()
    if accepte_nom and date_accept:
        # QJR154 — ``builder.echapper_textes_client`` échappe déjà
        # ``accepte_par_nom`` : jamais ré-échappé ici.
        sign_client = (f'<div class="i3-sign-name">{accepte_nom}</div>'
                       f'<div class="i3-sign-date">'
                       f'{L("ci_le_date", "Le {date}", date=date_accept)}</div>')
    else:
        sign_client = f'<div class="i3-sign-blank">{bpa_mention}</div>'

    css = f"""
<style>
.i3-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.i3-root *{{box-sizing:border-box;}}
.i3-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.i3-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.i3-h2{{font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};margin-top:12px;}}
.i3-two{{width:100%;margin-top:6px;border-collapse:separate;border-spacing:0;}}
.i3-col{{vertical-align:top;width:48.5%;}}
.i3-cgap{{width:3%;}}
.i3-blk{{border:1px solid {line};border-radius:12px;padding:9px 12px;background:#fff;}}
.i3-blk-t{{font-size:8.5pt;font-weight:700;color:{navy};}}
.i3-li{{font-size:7.8pt;color:{ink};line-height:1.4;margin-top:4px;padding-left:12px;position:relative;}}
.i3-li:before{{content:'';position:absolute;left:0;top:5px;width:6px;height:6px;
  border-radius:50%;background:{green};}}
.i3-li b{{color:{navy};}}

.i3-warr{{margin-top:12px;border:1px solid {line};border-radius:12px;background:{wash};
  padding:9px 14px;}}
.i3-warr-row{{display:table;width:100%;border-spacing:0;}}
.i3-warr-c{{display:table-cell;vertical-align:top;text-align:center;padding:0 6px;}}
.i3-warr-v{{font-family:{f_display};font-size:15pt;color:{green};line-height:1;}}
.i3-warr-l{{font-size:7pt;color:{muted};margin-top:3px;}}

.i3-sign{{margin-top:14px;display:table;width:100%;border-spacing:0;}}
.i3-sign-c{{display:table-cell;vertical-align:top;width:50%;border:1px solid {line};
  border-radius:12px;padding:12px 14px;}}
.i3-sign-gap{{display:table-cell;width:12px;}}
.i3-sign-h{{font-size:7.5pt;letter-spacing:1.4px;text-transform:uppercase;
  color:{muted};font-weight:700;}}
.i3-sign-box{{margin-top:8px;height:20mm;border:1px dashed {line};border-radius:8px;
  background:{wash};}}
.i3-sign-name{{margin-top:8px;font-size:11pt;color:{navy};font-weight:700;}}
.i3-sign-date{{font-size:8pt;color:{muted};margin-top:2px;}}
.i3-sign-blank{{margin-top:8px;font-size:8pt;color:{muted_2};font-style:italic;}}
.i3-sign-co{{font-size:8pt;color:{muted};margin-top:8px;}}
.i3-sign-co b{{color:{navy};}}
</style>
"""

    # AMOT38 (C-AMOT-047) — les clauses/CGV gelées (QJR668) sont imprimées
    # UNE fois, sur la page équipements (``commercial/equip``, partagée par
    # l'industriel) ; plus de second bloc ici.

    html = f"""{css}
<div class="i3-root">
  <div class="i3-kicker">{L("ci_ind_deploiement", "Déploiement &amp; conditions")}</div>
  {tranches_html}

  <div class="i3-h2">{L("ci_ind_valeur_entreprise", "Valeur pour l'entreprise")}</div>
  <table class="i3-two"><tr>
    <td class="i3-col"><div class="i3-blk">
      <div class="i3-blk-t">{L("ci_ind_iso_titre", "ISO 50001 — management de l'énergie")}</div>
      <div class="i3-li">{L("ci_ind_iso_texte", "Les données de production et de consommation peuvent alimenter votre <b>revue énergétique</b> — sans promesse de conformité à la norme.")}</div>
    </div></td>
    <td class="i3-cgap"></td>
    <td class="i3-col"><div class="i3-blk">
      <div class="i3-blk-t">{titre_decarbo}</div>
      <div class="i3-li">{texte(textes_decarbo, langue)}</div>
    </div></td>
  </tr></table>

  {warranties_html}{services_html}

  {conditions_html}

  <div class="i3-sign">
    <div class="i3-sign-c">
      {acceptation_html}{sign_client if (accepte_nom and date_accept) else ''}
    </div>
    <div class="i3-sign-gap"></div>
    <div class="i3-sign-c">
      <div class="i3-sign-h">{L("ci_pour", "Pour {marque}", marque=brand)}</div>
      <div class="i3-sign-box"></div>
      <div class="i3-sign-co"><b>{brand}</b> &nbsp;·&nbsp; {ident.get('email','')} &nbsp;·&nbsp; {ident.get('phone','')}</div>
    </div>
  </div>
  <div class="i3-legal" style="margin-top:10px;font-size:6.8pt;color:{muted};line-height:1.4;">{bande_legale(d, ident)}</div>
</div>
"""
    return html
