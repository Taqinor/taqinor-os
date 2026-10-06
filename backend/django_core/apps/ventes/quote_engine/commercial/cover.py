# flake8: noqa
"""quote_engine commercial — PAGE 1 (cover catégorie-aware).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``c1c-``.
"""
from . import categories
# QA-FIGURES — ancres ``data-figure`` masquées À CÔTÉ des chiffres client
# (aucune chaîne existante ne change) — voir ``quote_engine/figures.py``.
from ..figures import ancre
# QJR651 — kwc_str et la cellule KPI : harnais premium commun.
from .. import premium_base
# CIQ307 — bandeau, méthode, tuiles d'argent : lus sur ``synthese_ci``.
from ..ci import couverture as ci_couverture
# CIQ309 — bloc client entreprise (raison sociale, ICE, RC, IF, interlocuteur).
from ..ci import blocs as ci_blocs


def build(ctx):
    d = ctx["d"]

    # CIQ333 — libellés STRUCTURELS dans la langue du document.
    def L(cle, fr, **valeurs):
        return ci_blocs.libelle(d, cle, fr, **valeurs)

    C = ctx["C"]
    fmt = ctx["fmt"]
    # ERR-QJR614-CI-INVESTISSEMENT-DIRHAM-VS-CENTIME — l'investissement TTC
    # s'imprime au centime, la même chaîne que le Total TTC page 2.
    fmt_mad = ctx.get("fmt_mad") or fmt
    fonts = ctx["fonts"]
    logo_dark = ctx["logo_dark"]
    theme = ctx["theme"]
    ident = ctx.get("ident") or {}
    brand = ident.get("brand_name") or "TAQINOR"

    navy, navy_900, gold, green, green_bg, ink, muted, muted_2, line, paper, wash = premium_base.couleurs(
        C, "navy navy_900 gold green green_bg ink muted muted_2 line paper wash")

    f_display, f_serif, f_sans = premium_base.polices(fonts)

    ref = d["ref"]
    date = d["date"]
    # QJR628 — correction après envoi / révision : le builder décide.
    marques_correction = "".join(
        f'<div class="c1c-hd">{m}</div>'
        for m in theme.marques_correction(d))
    client_full = theme.titlecase_name(d.get("client_full") or d.get("client_name") or "Client")
    client_meta = theme.join_meta(d.get("client_addr", ""), (d.get("client_ville_libelle") or d.get("client_city", "")),
                                  d.get("client_phone", ""))
    # M7 (audit du 19/08/2026) — pastille de validité : la VRAIE date
    # d'échéance du devis (``valid_until``, posée par le builder depuis
    # ``date_validite`` ou le réglage société ``quote_validity_days``).
    # Indéterminable ⇒ pastille OMISE : le portail client affichait la
    # vraie date, le PDF un « 30 jours » codé en dur.

    _vu = (d.get("valid_until") or "").strip()
    validity_pill = (
        '<div class="c1c-pill">'
        + L("ci_valable_jusqu", "Valable jusqu&#8217;au {date}", date=_vu)
        + '</div>' if _vu else "")

    cat = d.get("com_category")
    # CIQ330 — libellé et accroche lus sur ``synthese_ci['categorie']``.
    meta = categories.meta(cat, (d.get("com_synthese") or {}).get("categorie"))
    icon = meta["icon"]
    cat_label = meta["label"]
    accroche = meta["accroche"]

    kwc = premium_base.kwc_str(d.get("com_kwc"))
    invest = d.get("_invest_ttc") or 0

    # QJR651 — la cellule KPI est commune (premium_base.kpi) ; seul
    # le préfixe de classes CSS diffère d'un marché à l'autre.
    def kpi(val, unit, label, fig=None):
        return premium_base.kpi(val, unit, label, fig, prefixe="c1c")

    cellules = [kpi(kwc, "&nbsp;kWc",
                    L("ci_puissance_crete", "Puissance crête"),
                    "puissance_kwc")]
    # CIQ331 — la production annuelle du moteur C&I (``synthese_ci``), ancrée
    # pour la parité avec /proposition ; non servie ⇒ tuile omise.
    production = d.get("com_production")
    if production is not None:
        cellules.append(kpi(fmt(round(production)),
                            L("ci_unite_kwh_an", "&nbsp;kWh/an"),
                            L("ci_production_annuelle", "Production annuelle"),
                            "production_annuelle_kwh"))
    cellules.extend(ci_couverture.tuiles_taux(d, "com", kpi))
    # QXMT — dossier MT sans économies d'étude : la vignette est OMISE, pas
    # remplie d'un « 0 » ni d'un chiffre calculé au barème BASSE TENSION.
    # QJR119 — l'omission couvre aussi « valeur non chiffrable » : le garde ne
    # testait que le cas MT et laissait imprimer « 0 MAD — Économies / an ».
    # CIQ307 — tuiles d'argent lues sur ``synthese_ci.argent`` : « estimées »,
    # base HT/TTC dite, payback du flux ; absentes ⇒ omises.
    kpis = '<td class="c1c-kgap"></td>'.join(cellules)
    # CIQ331 — l'argent sur sa propre rangée (économie de l'année 1, retour du
    # flux) : lu sur ``synthese_ci.argent``, absent ⇒ rangée omise.
    argent = ci_couverture.tuiles_argent(d, "com", kpi, fmt)
    kpis_argent = ('<table class="c1c-kpirow" style="margin-top:9px;"><tr>'
                   + '<td class="c1c-kgap"></td>'.join(argent)
                   + '</tr></table>') if argent else ""
    bandeau = ci_couverture.bandeau_reserve(d, "com", "c1c")
    methode_line = ci_couverture.ligne_methode(d, "com", "c1c")
    note_pointe = ci_couverture.note_pointe(d, "com")

    # QXMT — la SOURCE du barème voyage avec le chiffre, ou l'explication de
    # son absence. Vide hors dossier MT.
    # CIQ331 — argent non servi ⇒ son motif (« ce qu'il nous manque »),
    # jamais une tuile à « 0 » ni « votre répartition horaire ».
    if d.get("com_masquer_economies") or (
            d.get("com_motif_argent") and d.get("com_economies") is None):
        mt_line = ci_couverture.ligne_non_chiffre(d, "com", "c1c")
    elif d.get("com_mt_mention"):
        mt_line = f'<div class="c1c-mtsrc">{d["com_mt_mention"]}</div>'
    else:
        mt_line = ""

    css = f"""
<style>
.c1c-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;
  position:relative;background:{paper};-weasy-hyphens:none;}}
.c1c-root *{{box-sizing:border-box;}}
.c1c-serif{{font-family:{f_display};}}
.c1c-hero{{background:{navy_900};padding:11mm 14mm 9mm 14mm;border-bottom:3px solid {gold};}}
.c1c-htop{{display:table;width:100%;}}
.c1c-hlogo{{display:table-cell;vertical-align:middle;}}
.c1c-hlogo img{{height:9mm;width:auto;}}
.c1c-hmeta{{display:table-cell;vertical-align:middle;text-align:right;color:#fff;}}
.c1c-rl{{font-size:6.5pt;letter-spacing:1.6px;text-transform:uppercase;color:{muted_2};}}
.c1c-rv{{font-size:12pt;font-weight:700;color:#fff;}}
.c1c-hd{{font-size:8pt;color:rgba(255,255,255,.72);margin-top:2px;}}
.c1c-pill{{display:inline-block;margin-top:5px;background:{gold};color:{navy_900};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:700;}}
.c1c-hbody{{margin-top:8mm;color:#fff;}}
.c1c-catrow{{display:table;}}
.c1c-caticon{{display:table-cell;vertical-align:middle;font-size:24pt;padding-right:10px;}}
.c1c-catlab{{display:table-cell;vertical-align:middle;}}
.c1c-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{gold};font-weight:700;}}
.c1c-title{{font-family:{f_display};font-size:23pt;line-height:1.05;margin-top:3px;}}
.c1c-acc{{font-size:10.5pt;color:rgba(255,255,255,.88);margin-top:8px;max-width:150mm;}}
.c1c-client{{padding:6mm 14mm 0 14mm;font-size:8.5pt;color:{muted};}}
.c1c-client b{{color:{ink};}}
.c1c-tag{{display:inline-block;margin-left:8px;background:{wash};border:1px solid {line};
  border-radius:20px;padding:2px 10px;font-size:7pt;font-weight:600;color:{navy};}}
.c1c-wrap{{padding:6mm 14mm 0 14mm;}}
.c1c-kpirow{{display:table;width:100%;border-spacing:0;}}
.c1c-kpi{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-left:4px solid {gold};border-radius:12px;padding:12px 14px;background:#fff;}}
.c1c-kgap{{display:table-cell;width:11px;}}
.c1c-kv{{font-family:{f_display};font-size:18pt;color:{navy};line-height:1;}}
.c1c-ku{{font-size:9pt;color:{muted};}}
.c1c-kl{{font-size:7pt;color:{muted};margin-top:3px;letter-spacing:.3px;}}
/* QXMT — ligne SOURCE sous le bloc économies (petite, jamais un chiffre nu). */
.c1c-mtsrc{{margin-top:6px;font-size:6.8pt;color:{muted};line-height:1.35;}}
{ci_couverture.css_bandeau("c1c", gold, ink, muted)}
.c1c-note{{margin-top:12px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:10px 14px;font-size:8.5pt;color:{ink};line-height:1.45;}}
.c1c-note b{{color:{navy};}}
.c1c-inv{{margin-top:12px;display:table;width:100%;border:1px solid {line};
  border-radius:12px;background:{wash};padding:11px 16px;}}
.c1c-inv-l{{display:table-cell;vertical-align:middle;font-size:8.5pt;color:{muted};}}
.c1c-inv-v{{display:table-cell;vertical-align:middle;text-align:right;
  font-family:{f_display};font-size:20pt;color:{navy};}}
.c1c-inv-v span{{font-size:10pt;color:{muted};}}
</style>
"""

    # CIQ315 — investissement sur la base de ``synthese_ci.argent.base``
    # (HT si TVA récupérable déclarée, HT et TTC si inconnue, TTC sinon).
    note_autoconso = L(
        "ci_note_autoconso_commercial",
        "L'installation vise l'<b>autoconsommation</b> : la valeur porte "
        "d'abord sur\n      la consommation de <b>journée</b> de votre "
        "établissement.")
    inv_html = ci_couverture.bloc_investissement(
        d, d.get("com_synthese") or {}, "c1c", fmt_mad, ancre, invest=invest)

    html = f"""{css}
<div class="c1c-root">
  <div class="c1c-hero">
    <div class="c1c-htop">
      <div class="c1c-hlogo"><img src="data:image/png;base64,{logo_dark}" alt="{brand}"></div>
      <div class="c1c-hmeta">
        <div class="c1c-rl">{L("ci_ref_devis", "Réf. devis")}</div>
        <div class="c1c-rv">{ref}</div>
        <div class="c1c-hd">{date}</div>
        {marques_correction}
        {validity_pill}
      </div>
    </div>
    <div class="c1c-hbody">
      <div class="c1c-kicker">{L("ci_kicker_commercial", "Proposition — Autoconsommation solaire commerciale")}</div>
      <div class="c1c-catrow">
        <div class="c1c-caticon">{icon}</div>
        <div class="c1c-catlab"><div class="c1c-serif c1c-title">{cat_label}</div></div>
      </div>
      <div class="c1c-acc">{accroche}</div>
    </div>
  </div>

  <div class="c1c-client">
    <b>{client_full}</b>
    {f'&nbsp;·&nbsp;{client_meta}' if client_meta else ''}
    <span class="c1c-tag">{cat_label}</span>{ci_blocs.bloc_client((d.get("com_synthese") or {}).get("entreprise_client"), "c1c", d.get("client_full") or d.get("client_name"), doc=d)}
  </div>

  <div class="c1c-wrap">
    {bandeau}
    <table class="c1c-kpirow"><tr>{kpis}</tr></table>{kpis_argent}
    {methode_line}
    {mt_line}
    <div class="c1c-note">
      {note_autoconso} {note_pointe}
    </div>{inv_html}
  </div>
</div>
"""
    return html
