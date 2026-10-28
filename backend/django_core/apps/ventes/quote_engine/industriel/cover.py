# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""quote_engine industriel — PAGE 1 (CFO cover : synthèse de direction,
baseline énergétique titrée par sa source + KPIs).

``build(ctx) -> str`` returns the INNER HTML of one A4 page. NO page wrapper, NO
footer (the harness paints the footer). CSS tables only (never flex — WeasyPrint;
see quote_engine/RENDERING_NOTES.md). Classes prefixed ``i1-``.

CIQ341 — un encadré « Synthèse » autonome (à transmettre à un comité), lu
dans ``synthese_ci`` ; une baseline titrée par la SOURCE servie (« 12
factures », « mois interpolés — estimation », « kWh déclarés ») ; pour un
site MT, la phrase « la puissance souscrite et la prime fixe ne changent
pas » (CIQ305) et, s'il manque des données, la demande des 12 factures MT.
Aucune promesse d'écrêtage, aucun chiffre de cos φ. Rendu seul (règle #4).
"""

# QA-FIGURES — ancres ``data-figure`` masquées À CÔTÉ des chiffres client
# (aucune chaîne existante ne change) — voir ``quote_engine/figures.py``.
from ..figures import ancre
# CIQ307 — bandeau, méthode, tuiles d'argent : lus sur ``synthese_ci``.
from ..ci import couverture as ci_couverture
# CIQ309 — bloc client entreprise (raison sociale, ICE, RC, IF, interlocuteur).
from ..ci import blocs as ci_blocs
from ..ci.mentions import texte
from ..ci.graphiques import cede
# CPDF3 — les deux options côte à côte (devis « sans / avec batterie »).
from ..ci import options_cote
from ..lecture_pure import nombre_ou_none
from ..montants import decimale
# QJR651 — kwc_str et la cellule KPI : harnais premium commun.
from .. import premium_base

_MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]

#: Clés de consommation du moteur C&I (mêmes que ``ci/synthese``).
_CLES_CONSO = ("kwh_mensuels", "consommation", "factures_mad")


def _nb_factures_reelles(d):
    """Le nombre de mois RELEVÉS d'une baseline interpolée (12 − mois
    interpolés), quand le moteur le dit ; sinon None (jamais deviné)."""
    etude_ci = (d.get("etude") or {}).get("etude_ci") or {}
    entrees = etude_ci.get("entrees_resolues") or {}
    for cle in _CLES_CONSO:
        entree = entrees.get(cle)
        if not isinstance(entree, dict):
            continue
        interpoles = entree.get("mois_interpoles") or entree.get("interpoles")
        if isinstance(interpoles, (list, tuple)):
            return max(0, 12 - len(interpoles))
        return None
    return None


def _base_argent(argent):
    return argent.get("base") if isinstance(argent, dict) else None


def _taux_declare(argent):
    """Le taux d'actualisation DÉCLARÉ par le client (hypothèse du flux
    servi), ou None — jamais un taux par défaut (D-CIQ-10)."""
    for cle in ("flux_ht", "flux_ttc"):
        flux = argent.get(cle) if isinstance(argent, dict) else None
        for h in (flux or {}).get("hypotheses") or []:
            if isinstance(h, dict) and \
                    h.get("cle") == "taux_actualisation_pct":
                return nombre_ou_none(h.get("valeur"))
    return None


def _pct_txt(valeur):
    """« 39,8 » — un pourcentage servi, au dixième pour l'affichage."""
    return decimale(f"{valeur:.1f}")


def bloc_synthese(d, L, fmt, fmt_mad, bandeau, prefixe="i1"):
    """CIQ341 — l'encadré « Synthèse » : TRI avec son horizon, VAN
    seulement sur un taux DÉCLARÉ, financement s'il est servi, statut
    d'étude et points à confirmer (``bandeau``). Tout est LU dans
    ``synthese_ci`` — aucun calcul ici.

    CPDF — un chiffre, une fois par page : l'investissement est dit par son
    bloc (CIQ315), l'économie et le retour par leurs tuiles (ou par les
    cartes d'options) ; l'encadré ne les répète plus."""
    synthese = d.get("ind_synthese") or {}
    argent = synthese.get("argent") if isinstance(synthese, dict) else None
    lignes = []
    if isinstance(argent, dict) and not d.get("ind_masquer_economies"):
        indicateurs = argent.get("indicateurs") or {}
        tri = nombre_ou_none(indicateurs.get("tri_pct"))
        horizon = nombre_ou_none(indicateurs.get("tri_horizon_ans"))
        if tri is not None and horizon:
            lignes.append((L("ci_ind_tri_sur", "TRI sur {n} ans",
                             n=f"{horizon:g}"), f"{_pct_txt(tri)}&nbsp;%"))
        van = nombre_ou_none(indicateurs.get("van_mad"))
        taux = _taux_declare(argent)
        if van is not None and taux is not None:
            lignes.append((L("ci_ind_van", "VAN au taux déclaré de {taux} %",
                             taux=decimale(f"{taux:g}")),
                           f"{fmt_mad(van)}&nbsp;MAD"))
        offre = argent.get("financement")
        if isinstance(offre, dict) and offre.get("echeance_mad") is not None:
            lignes.append((L("ci_ind_financement", "Financement"),
                           ci_blocs._txt(offre.get("libelle_client"))
                           or L("ci_offre_financement",
                                "Offre de financement")))
    else:
        motif_html = ci_couverture.ligne_non_chiffre(d, "ind", prefixe)
        if motif_html:
            lignes.append((L("ci_ind_rentabilite", "Rentabilité"),
                           motif_html))
    # Décision fondateur 26/10/2026 — le devis C&I entier est préliminaire :
    # plus jamais de rangée « Statut de l'étude : prix ferme » (ex-AMOT80).
    rangees = "".join(
        f'<tr><td class="{prefixe}-sy-l">{lib}</td>'
        f'<td class="{prefixe}-sy-v">{val}</td></tr>'
        for lib, val in lignes)
    return (f'<div class="{prefixe}-sy">'
            f'<div class="{prefixe}-sy-t">{L("ci_ind_synthese", "Synthèse")}'
            f'</div><table class="{prefixe}-sy-tbl">{rangees}</table>'
            f'{bandeau}</div>')


def _factures(d, L, fmt, source):
    """``(barres, montant)`` de la facture électrique servie (12 mois) —
    QJR119 : les factures manquantes ne se REMBOURRENT PLUS de zéros ;
    CIQ341 : des kWh SEULS (source « kWh déclarés ») n'ont pas de montant en
    MAD (ni facture imprimée, ni « facture non communiquée »)."""
    bills = [float(b or 0) for b in (d.get("factures_mensuelles") or [])][:12]
    if source == "kwh_declares" or not any(b > 0 for b in bills):
        return "", ("" if source == "kwh_declares" else (
            '<div class="i1-basel">'
            + L("ci_ind_facture_non_communiquee_client",
                "Facture électrique actuelle non communiquée — transmettez "
                "12 mois de factures et votre consommation de référence se "
                "chiffre.") + '</div>'))
    annual_bill = round(sum(bills))
    avg_bill = round(annual_bill / 12) if annual_bill else None
    bills += [0.0] * (12 - len(bills))
    bmax = max(bills) or 1.0
    # Barres CSS (hauteurs en mm — déterministes, jamais de % en cellule).
    bar_cells = "".join(
        f'<td class="i1-bc"><div class="i1-bar" style="height:'
        f'{round(b / bmax * 26.0, 1)}mm"></div><div class="i1-mn">'
        f'{_MONTHS[i]}</div></td>' for i, b in enumerate(bills))
    libelle_facture = (
        L("ci_ind_facture_estimee", "Facture électrique estimée")
        if source == "mois_interpoles"
        else L("ci_ind_facture_actuelle", "Facture électrique actuelle"))
    return (f'<table class="i1-bars"><tr>{bar_cells}</tr></table>',
            f'<div class="i1-big">{fmt(annual_bill)}<span>&nbsp;'
            f'{L("ci_mad_an", "MAD/an")}</span></div>'
            + ancre("facture_annuelle_avant", fmt(annual_bill)) +
            f'<div class="i1-basel">{libelle_facture} · '
            f'{fmt(avg_bill)} {L("ci_mad_mois", "MAD/mois")}</div>'
            + ancre("facture_mensuelle_avant", fmt(avg_bill)))


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    logo_dark = ctx["logo_dark"]
    theme = ctx["theme"]
    ident = ctx.get("ident") or {}
    brand = ident.get("brand_name") or "TAQINOR"

    # CIQ333 / CIQ345 — libellés STRUCTURELS dans la langue du document.
    def L(cle, fr, **valeurs):
        return ci_blocs.libelle(d, cle, fr, **valeurs)

    navy, navy_900, gold, green, green_bg, ink, muted, muted_2, line, paper, wash, blue = premium_base.couleurs(
        C, "navy navy_900 gold green green_bg ink muted muted_2 line paper wash blue")

    f_display, f_serif, f_sans = premium_base.polices(fonts)

    ref = d["ref"]
    date = d["date"]
    # QJR628 — correction après envoi / révision : le builder décide.
    marques_correction = "".join(
        f'<div class="i1-hd">{m}</div>'
        for m in theme.marques_correction(d))
    client_full, client_meta = ci_couverture.identite_client(d)
    # M7 (audit du 19/08/2026) — pastille de validité : la VRAIE date
    # d'échéance du devis ; indéterminable ⇒ pastille OMISE.
    _vu = (d.get("valid_until") or "").strip()
    validity_pill = (
        '<div class="i1-pill">'
        + L("ci_valable_jusqu", "Valable jusqu&#8217;au {date}", date=_vu)
        + '</div>' if _vu else "")

    kwc = premium_base.kwc_str(d.get("ind_kwc"))
    prod = d.get("ind_prod")
    conso = d.get("ind_conso")
    invest = d.get("_invest_ttc") or 0
    # QJR614 — l'investissement TTC s'imprime au centime : on relit le
    # montant NON arrondi (display_total, sinon totaux_all.ttc).
    fmt_mad = ctx.get("fmt_mad") or fmt
    invest_centimes = invest
    for _src in (d.get("display_total"),
                 (d.get("totaux_all") or {}).get("ttc")):
        try:
            _v = float(_src)
        except (TypeError, ValueError):
            continue
        if _v > 0:
            invest_centimes = _v
            break

    # CIQ341 — la SOURCE de la baseline, servie par ``synthese_ci``.
    baseline = (d.get("ind_synthese") or {}).get("baseline") or {}
    source = baseline.get("source")
    if source == "factures":
        suffixe = " — " + L("ci_ind_baseline_factures", "12 factures")
    elif source == "mois_interpoles":
        n = _nb_factures_reelles(d)
        suffixe = " — " + (
            L("ci_ind_baseline_interpoles",
              "{n} factures, mois interpolés — estimation", n=n)
            if n else L("ci_ind_baseline_interpoles_sans_n",
                        "mois interpolés — estimation"))
    elif source == "kwh_declares":
        suffixe = " — " + L("ci_ind_source_kwh_declares",
                            "d'après vos kWh déclarés")
    else:
        # Sans source servie, la couverture ne prétend plus « 12 mois ».
        suffixe = ""

    bars_html, bill_html = _factures(d, L, fmt, source)

    # QJR651 — la cellule KPI est commune (premium_base.kpi).
    def kpi(val, unit, label, fig=None):
        return premium_base.kpi(val, unit, label, fig, prefixe="i1")

    # AMOT84 — l'unité dans la langue du document (« kWp » en anglais,
    # comme le titre) ; « &nbsp;kWc » en français, octet pour octet.
    # CPDF3 — devis à deux options : la puissance, l'argent et la part
    # couverte de CHAQUE option sont dits par sa carte (un chiffre, une fois).
    deux_options = options_cote.deux_options(d, "ind")
    cellules = [] if deux_options else [
        kpi(kwc, L("res_unite_kwc", "&nbsp;kWc"),
            L("ci_puissance_crete", "Puissance crête"), "puissance_kwc")]
    cellules.extend(ci_couverture.tuiles_taux(
        d, "ind", kpi, couverture_tuile=not deux_options))
    # CIQ307 — tuiles d'argent lues sur ``synthese_ci.argent`` ; absentes ⇒
    # omises (jamais un « 0 », QJR119).
    if not deux_options:
        cellules.extend(ci_couverture.tuiles_argent(d, "ind", kpi, fmt))
    kpis = '<td class="i1-kgap"></td>'.join(cellules)
    bandeau = ci_couverture.bandeau_reserve(d, "ind", "i1")
    # AMOT80 — le sous-titre « cashflow et payback » seulement sur un flux.
    from .finance import flux_principal
    sous_titre = L("ci_ind_sous_titre_client", "Analyse de rentabilité : "
                   "votre consommation, vos flux annuels et le délai de "
                   "retour.") if flux_principal(
        (d.get("ind_synthese") or {}).get("argent"))[1].get("flux") else ""
    # AMOT89 — le surplus chiffré (kWh du bilan) sous la ligne de méthode.
    methode_line = (ci_couverture.ligne_methode(d, "ind", "i1")
                    + ci_couverture.ligne_surplus(d, "ind", "i1"))
    note_pointe = ci_couverture.note_pointe(d, "ind")

    # QXMT — la SOURCE du barème voyage avec le chiffre. CIQ341 — argent non
    # servi ⇒ son motif (pour un site MT : les 12 factures MT, jamais
    # « votre répartition horaire ») est dit UNE fois, dans la synthèse.
    if d.get("ind_masquer_economies") or d.get("ind_economies") is None:
        mt_line = ""
    elif d.get("ind_mt_mention"):
        mt_line = (f'<div class="i1-mtsrc">'
                   f'{ci_couverture.mention_client(d["ind_mt_mention"])}</div>')
    else:
        mt_line = ""
    # CIQ341 — site MT (ou puissance souscrite déclarée) : la centrale réduit
    # l'énergie achetée ; puissance souscrite et prime fixe inchangées
    # (CIQ305, ``synthese_ci['hypotheses']``). Aucune promesse d'écrêtage.
    _puissance = next(
        (h for h in (d.get("ind_synthese") or {}).get("hypotheses") or []
         if isinstance(h, dict) and h.get("cle") == "puissance_souscrite"),
        None)
    puissance_line = (
        f'<div class="i1-mtsrc">'
        f'{texte(_puissance.get("textes") or {}, ci_blocs.langue(d))}</div>'
        if _puissance and (_puissance.get("textes") or {}).get("fr") else "")

    # AMOT41 — ``ind_conso`` = la consommation du MOTEUR (Σ 12 mois) ; sans
    # baseline moteur, la ligne est OMISE (une seule consommation par page).
    # CPDF5 — sans « ≈ » ni « estimée » : les kWh servis par le moteur.
    conso_line = (L("ci_cpdf_conso", "Consommation : {kwh}&#160;kWh/an",
                    kwh=fmt(round(conso))) if conso else "")
    prod_line = (L("ci_cpdf_production", "Production : {kwh}&#160;kWh/an",
                   kwh=fmt(round(prod)))
                 + ancre("production_annuelle_kwh", fmt(round(prod)))
                 if prod else "")
    # AMOT92 — les prochaines étapes et le QR, sur une ligne ; cédables au
    # rendu adaptatif (la couverture industrielle est la plus dense).
    etapes = ("" if cede(d, "etapes") else
              '<div data-graphique="etapes" style="margin-top:8px;">'
              + ci_couverture.bloc_etapes(d, "i1", (navy, muted, gold),
                                          en_ligne=True) + '</div>')

    css = f"""
<style>
.i1-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;
  position:relative;background:{paper};-weasy-hyphens:none;}}
.i1-root *{{box-sizing:border-box;}}
.i1-serif{{font-family:{f_display};}}
.i1-hero{{background:{navy_900};padding:9mm 14mm 7mm 14mm;border-bottom:3px solid {gold};}}
.i1-htop{{display:table;width:100%;}}
.i1-hlogo{{display:table-cell;vertical-align:middle;}}
.i1-hlogo img{{height:9mm;width:auto;}}
.i1-hmeta{{display:table-cell;vertical-align:middle;text-align:right;color:#fff;}}
.i1-rl{{font-size:6.5pt;letter-spacing:1.6px;text-transform:uppercase;color:{muted_2};}}
.i1-rv{{font-size:12pt;font-weight:700;color:#fff;}}
.i1-hd{{font-size:8pt;color:rgba(255,255,255,.72);margin-top:2px;}}
.i1-pill{{display:inline-block;margin-top:5px;background:{gold};color:{navy_900};
  border-radius:20px;padding:3px 11px;font-size:7pt;font-weight:700;}}
.i1-hbody{{margin-top:6mm;color:#fff;}}
.i1-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{gold};font-weight:700;}}
.i1-title{{font-family:{f_display};font-size:19pt;line-height:1.1;margin-top:4px;}}
.i1-sub{{font-size:10pt;color:rgba(255,255,255,.85);margin-top:5px;}}
.i1-client{{padding:5mm 14mm 0 14mm;font-size:8.5pt;color:{muted};}}
.i1-client b{{color:{ink};}}
.i1-tag{{display:inline-block;margin-left:8px;background:{wash};border:1px solid {line};
  border-radius:20px;padding:2px 10px;font-size:7pt;font-weight:600;color:{navy};}}
.i1-wrap{{padding:4mm 14mm 0 14mm;}}
.i1-sy{{border:1px solid {line};border-left:4px solid {navy};border-radius:12px;
  background:{wash};padding:8px 14px;}}
.i1-sy-t{{font-family:{f_serif};font-weight:700;font-size:11pt;color:{navy};}}
.i1-sy-tbl{{width:100%;border-collapse:collapse;margin-top:3px;font-size:8pt;}}
.i1-sy-tbl td{{padding:1.5px 0;vertical-align:top;}}
.i1-sy-l{{color:{muted};width:42%;}}
.i1-sy-v{{color:{ink};font-weight:700;}}
.i1-sy-v .i1-mtsrc{{font-weight:400;margin-top:0;}}
.i1-sy .i1-reserve{{margin:6px 0 0 0;}}
.i1-sec{{font-family:{f_serif};font-weight:700;font-size:13pt;color:{navy};margin-top:9px;}}
.i1-card{{border:1px solid {line};border-radius:14px;background:#fff;padding:10px 16px;margin-top:6px;}}
.i1-baserow{{display:table;width:100%;}}
.i1-basecell{{display:table-cell;vertical-align:middle;}}
.i1-big{{font-family:{f_display};font-size:24pt;color:{navy};line-height:1;}}
.i1-big span{{font-size:11pt;color:{muted};}}
.i1-basel{{font-size:8pt;color:{muted};margin-top:3px;}}
.i1-bars{{width:100%;height:30mm;border-spacing:3px 0;margin-top:6px;}}
.i1-bc{{vertical-align:bottom;text-align:center;}}
.i1-bar{{width:100%;background:linear-gradient(180deg,{blue},{navy});border-radius:3px 3px 0 0;}}
.i1-mn{{font-size:6pt;color:{muted_2};margin-top:2px;}}
.i1-kpirow{{width:100%;margin-top:9px;border-spacing:0;border-collapse:separate;}}
.i1-kpi{{vertical-align:top;border:1px solid {line};
  border-left:4px solid {gold};border-radius:12px;padding:9px 12px;background:#fff;}}
.i1-kgap{{width:9px;}}
.i1-kv{{font-family:{f_display};font-size:15pt;color:{navy};line-height:1;}}
.i1-ku{{font-size:8.5pt;color:{muted};white-space:nowrap;}}
.i1-kl{{font-size:7pt;color:{muted};margin-top:3px;letter-spacing:.3px;}}
/* QXMT — ligne SOURCE sous le bloc économies (petite, jamais un chiffre nu). */
.i1-mtsrc{{margin-top:5px;font-size:6.8pt;color:{muted};line-height:1.35;}}
{ci_couverture.css_bandeau("i1", gold, ink, muted)}
.i1-note{{margin-top:8px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:8px 14px;font-size:8pt;color:{ink};line-height:1.4;}}
.i1-note b{{color:{navy};}}
{ci_couverture.css_investissement("i1", (line, wash, muted, navy, ink), f_display, 17, 8, "9px 16px")}
{options_cote.css_options("i1", (line, wash, muted, navy, ink, gold), 8)}
</style>
"""

    # CIQ315 — investissement sur la base de ``synthese_ci.argent.base``.
    # CPDF3 — deux options : les deux cartes REMPLACENT le bloc
    # investissement (jamais ajoutées par-dessus).
    inv_html = (options_cote.cartes_options(d, "ind", "i1", fmt, fmt_mad,
                                            invest_centimes)
                if deux_options else ci_couverture.bloc_investissement(
                    d, d.get("ind_synthese") or {}, "i1", fmt_mad, ancre,
                    invest=invest_centimes))
    synthese_html = bloc_synthese(d, L, fmt, fmt_mad, bandeau)
    note_autoconso = L(
        "ci_ind_note_autoconso",
        "L'installation vise l'<b>autoconsommation</b> : la valeur porte "
        "d'abord sur\n      les <b>heures pleines</b> (production en journée).")
    baseline_titre = L("ci_ind_conso_prod_titre",
                       "Votre consommation et votre production") + suffixe
    conso_prod = ' · '.join(x for x in (conso_line, prod_line) if x)

    html = f"""{css}
<div class="i1-root">
  <div class="i1-hero">
    <div class="i1-htop">
      <div class="i1-hlogo"><img src="data:image/png;base64,{logo_dark}" alt="{brand}"></div>
      <div class="i1-hmeta">
        <div class="i1-rl">{L("ci_ref_devis", "Réf. devis")}</div>
        <div class="i1-rv">{ref}</div>
        <div class="i1-hd">{date}</div>
        {marques_correction}
        {validity_pill}
      </div>
    </div>
    <div class="i1-hbody">
      <div class="i1-kicker">{L("ci_ind_kicker", "Proposition — Autoconsommation solaire industrielle")}</div>
      <div class="i1-serif i1-title">{ci_couverture.titre_projet(d, "ind", kwc, client_full)}</div>
      <div class="i1-sub">{L("ci_ind_titre", "Réduire votre coût de l'énergie")}{(' — ' + sous_titre) if sous_titre else ''}</div>
    </div>
  </div>

  <div class="i1-client">
    {ci_couverture.ligne_client(d, "ind", client_full, client_meta, "i1")}
  </div>

  <div class="i1-wrap">
    {synthese_html}

    <div class="i1-sec">{baseline_titre}</div>
    <div class="i1-card">
      <div class="i1-baserow">
        <div class="i1-basecell">
          {bill_html}
          <div class="i1-basel">{conso_prod}</div>
        </div>
      </div>
      {bars_html}
    </div>

    <table class="i1-kpirow"><tr>{kpis}</tr></table>
    {methode_line}
    {mt_line}
    {puissance_line}

    <div class="i1-note">
      {note_autoconso} {note_pointe}
    </div>

    {inv_html}{etapes}
  </div>
</div>
"""
    return html
