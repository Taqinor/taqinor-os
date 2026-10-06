# flake8: noqa
"""quote_engine commercial — PAGE 3 (confiance + étapes + signature).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``c3-``.
"""


# CIQ310 — bande légale du vendeur (RC, ICE, capital) : UNE fonction
# partagée avec le résidentiel.
from ..premium_base import bande_legale
# CIQ311 — blocs C&I communs (conditions, Bon pour accord).
from ..ci import blocs as ci_blocs


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    theme = ctx["theme"]
    ident = ctx.get("ident") or {}
    brand = ident.get("brand_name") or "TAQINOR"

    navy = C["navy"]
    gold = C["gold"]
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    ink = C.get("ink", "#1F2937")
    muted = C.get("muted", "#6B7280")
    muted_2 = C.get("muted_2", "#9BA3AE")
    line = C.get("line", "#E5E7EB")
    line_soft = C.get("line_soft", "#EFF1F4")
    wash = C.get("wash", "#F7F9FC")

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    # CIQ333 — libellés STRUCTURELS dans la langue du document.
    def L(cle, fr, **valeurs):
        return ci_blocs.libelle(d, cle, fr, **valeurs)

    steps = [
        ("1", L("ci_etape_etude_t", "Étude &amp; validation"),
         L("ci_etape_etude_s", "Dimensionnement, visite technique et validation du projet.")),
        ("2", L("ci_etape_installation_t", "Installation"),
         L("ci_etape_installation_s", "Pose des équipements par nos équipes, sans interrompre votre activité.")),
        ("3", L("ci_etape_mes_t", "Mise en service"),
         L("ci_etape_mes_s", "Raccordement, tests et réception — votre production démarre.")),
    ]
    steps_cells = ""
    for i, (n, t, s) in enumerate(steps):
        gap = '<td class="c3-sgap"></td>' if i < len(steps) - 1 else ""
        steps_cells += (
            f'<td class="c3-step"><div class="c3-step-n">{n}</div>'
            f'<div class="c3-step-t">{t}</div>'
            f'<div class="c3-step-s">{s}</div></td>{gap}')

    # QJR118 — mêmes garanties que les paquets résidentiel et industriel :
    # DÉRIVÉES de la composition réelle par ``residential.theme.warranties_for``
    # (source unique QRES5), jamais des durées littérales. Les trois cellules
    # codées en dur contredisaient la source (25 vs 30 ans de performance,
    # 5-10 vs 10 ans d'onduleur) et surévaluaient de 5× l'engagement de pose
    # (10 ans imprimés pour 2 ans réels). Aucune durée traçable ⇒ omission.
    _warranties = [w for w in (theme.warranties_for(d) or [])
                   if w and str(w[0]).strip()]
    if _warranties:
        _cells = "".join(
            f'<div class="c3-warr-c">'
            f'<div class="c3-warr-v">{theme._esc(str(n))} {ci_blocs.textes_garantie(d, u, label)[0]}</div>'
            f'<div class="c3-warr-l">{ci_blocs.textes_garantie(d, u, label)[1]}</div></div>'
            for n, u, label, _sub in _warranties)
        warranties_html = f"""
  <div class="c3-h2">{L("ci_garanties", "Garanties")}</div>
  <div class="c3-warr">
    <div class="c3-warr-row">
      {_cells}
    </div>
    <div class="c3-warr-l" style="margin-top:6px;">{ci_blocs.legende_garanties(d)}</div>
  </div>
"""
    else:
        warranties_html = ""

    # CIQ311 — « Conditions » (CGV gelées à l'envoi, note TVA) et textes
    # « Bon pour accord » éditables, lus par la même voie que le legacy.
    bpa_titre, bpa_mention = ci_blocs.textes_bpa(d)
    conditions_html = ci_blocs.bloc_conditions(d, "c3", navy, ink)
    # CIQ320 — « Bon pour accord — pour la société » : raison sociale,
    # signataire, ICE, date, cadres Signature et Cachet ; valeurs de
    # ``signature_entreprise`` sur la copie signée.
    acceptation_html = ci_blocs.bloc_acceptation(d, "c3", ink, line)
    # CIQ314 — seulement les services que le devis porte (O&M nommée,
    # délai saisi) : plus d'étape « supervision », ni de « performance
    # garantie », ni de cellule O&M sans ligne derrière.
    services_html = ci_blocs.bloc_services(
        d.get("com_synthese") or {}, "c3", navy, ink, doc=d)
    # CIQ331 — échéancier en N jalons (``synthese_ci['echeancier']``,
    # montants au centime) puis l'offre de financement (CIQ318) si servie.
    echeancier_html = ci_blocs.bloc_echeancier(
        d.get("com_synthese") or {}, "c3", navy, ink, line, doc=d)
    financement_html = ci_blocs.bloc_financement(
        d.get("com_synthese") or {}, "c3", navy, ink, doc=d)
    accepte_nom = (d.get("accepte_par_nom") or "").strip()
    date_accept = (d.get("date_acceptation") or "").strip()
    if accepte_nom and date_accept:
        # QJR154 — UNE SEULE VÉRITÉ : ``builder.echapper_textes_client`` échappe
        # désormais ``accepte_par_nom`` pour les quatre renderers « maison ».
        # Ré-échapper ici sortait « &amp;amp; » sur un nom porteur d'un « & ».
        sign_client = (f'<div class="c3-sign-name">{accepte_nom}</div>'
                       f'<div class="c3-sign-date">{L("ci_le_date", "Le {date}", date=date_accept)}</div>')
    else:
        sign_client = f'<div class="c3-sign-blank">{bpa_mention}</div>'

    css = f"""
<style>
.c3-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.c3-root *{{box-sizing:border-box;}}
.c3-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.c3-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.c3-steprow{{display:table;width:100%;margin-top:10px;border-spacing:0;}}
.c3-step{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-top:4px solid {gold};border-radius:12px;padding:11px 12px;background:{wash};}}
.c3-sgap{{display:table-cell;width:9px;}}
.c3-step-n{{font-family:{f_display};font-size:19pt;color:{gold};line-height:1;}}
.c3-step-t{{font-size:8.5pt;font-weight:700;color:{navy};margin-top:4px;}}
.c3-step-s{{font-size:7pt;color:{muted};margin-top:4px;line-height:1.35;}}
.c3-h2{{font-family:{f_serif};font-weight:700;font-size:13pt;color:{navy};margin-top:16px;}}
.c3-warr{{margin-top:8px;border:1px solid {line};border-radius:12px;background:{wash};padding:11px 14px;}}
.c3-warr-row{{display:table;width:100%;border-spacing:0;}}
.c3-warr-c{{display:table-cell;vertical-align:top;text-align:center;padding:0 6px;}}
.c3-warr-v{{font-family:{f_display};font-size:16pt;color:{green};line-height:1;}}
.c3-warr-l{{font-size:7pt;color:{muted};margin-top:3px;}}
.c3-trust{{margin-top:14px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:10px 14px;font-size:8.5pt;color:{ink};line-height:1.45;}}
.c3-trust b{{color:{navy};}}
.c3-sign{{margin-top:16px;display:table;width:100%;border-spacing:0;}}
.c3-sign-c{{display:table-cell;vertical-align:top;width:50%;border:1px solid {line};
  border-radius:12px;padding:12px 14px;}}
.c3-sign-gap{{display:table-cell;width:12px;}}
.c3-sign-h{{font-size:7.5pt;letter-spacing:1.4px;text-transform:uppercase;
  color:{muted};font-weight:700;}}
.c3-sign-box{{margin-top:8px;height:20mm;border:1px dashed {line};border-radius:8px;background:{wash};}}
.c3-sign-name{{margin-top:8px;font-size:11pt;color:{navy};font-weight:700;}}
.c3-sign-date{{font-size:8pt;color:{muted};margin-top:2px;}}
.c3-sign-blank{{margin-top:8px;font-size:8pt;color:{muted_2};font-style:italic;}}
.c3-sign-co{{font-size:8pt;color:{muted};margin-top:8px;}}
.c3-sign-co b{{color:{navy};}}
</style>
"""

    html = f"""{css}
<div class="c3-root">
  <div class="c3-kicker">{L("ci_kicker_etapes", "Votre projet, étape par étape")}</div>
  <div class="c3-sec">{L("ci_comment_nous_procedons", "Comment nous procédons")}</div>
  <table class="c3-steprow"><tr>{steps_cells}</tr></table>

  {warranties_html}

  {echeancier_html}{financement_html}

  {services_html}

  {conditions_html}

  <div class="c3-sign">
    <div class="c3-sign-c">
      {acceptation_html}{sign_client if (accepte_nom and date_accept) else ''}
    </div>
    <div class="c3-sign-gap"></div>
    <div class="c3-sign-c">
      <div class="c3-sign-h">{L("ci_pour", "Pour {marque}", marque=brand)}</div>
      <div class="c3-sign-box"></div>
      <div class="c3-sign-co"><b>{brand}</b> &nbsp;·&nbsp; {ident.get('email','')} &nbsp;·&nbsp; {ident.get('phone','')}</div>
    </div>
  </div>
  <div class="c3-legal" style="margin-top:10px;font-size:6.8pt;color:{muted};line-height:1.4;">{bande_legale(d, ident)}</div>
</div>
"""
    return html
