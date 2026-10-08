# flake8: noqa
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
from ..lecture_pure import nombre_ou_none
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
    return f"{valeur:.1f}".replace(".", ",")


def bloc_synthese(d, L, fmt, fmt_mad, bandeau, prefixe="i1"):
    """CIQ341 — l'encadré « Synthèse » : investissement sur la base dite
    (CIQ315), économie de l'année 1, retour, TRI avec son horizon, VAN
    seulement sur un taux DÉCLARÉ, financement s'il est servi, statut
    d'étude et points à confirmer (``bandeau``). Tout est LU dans
    ``synthese_ci`` — aucun calcul ici."""
    synthese = d.get("ind_synthese") or {}
    argent = synthese.get("argent") if isinstance(synthese, dict) else None
    base = _base_argent(argent)
    l_ht, l_ttc = L("ci_ht", "HT"), L("ci_ttc", "TTC")
    ht = (d.get("totaux_all") or {}).get("ht_net")
    invest = d.get("_invest_ttc") or 0
    if base == "ht" and ht is not None:
        inv = f"{fmt_mad(ht)}&nbsp;MAD {l_ht}"
    elif base == "deux" and ht is not None:
        inv = (f"{fmt_mad(invest)}&nbsp;MAD {l_ttc} ({L('ci_soit', 'soit')} "
               f"{fmt_mad(ht)}&nbsp;MAD {l_ht})")
    else:
        inv = f"{fmt_mad(invest)}&nbsp;MAD {l_ttc}"
    lignes = [(L("ci_ind_investissement", "Investissement"), inv)]
    if isinstance(argent, dict) and not d.get("ind_masquer_economies"):
        eco = d.get("ind_economies")
        if eco is not None:
            base_eco = d.get("ind_economie_base")
            if base_eco in ("HT", "TTC"):
                base_eco = L(f"ci_{base_eco.lower()}", base_eco)
            lignes.append((L("ci_ind_economie_an1", "Économie de l'année 1"),
                           f"{fmt(eco)}&nbsp;MAD"
                           + (f" {base_eco}" if base_eco else "")))
        payback = d.get("ind_payback")
        if payback is not None:
            lignes.append((L("ci_retour_estime", "Retour estimé"),
                           ci_couverture.ans(payback)
                           + L("ci_unite_ans", "&nbsp;ans")))
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
                             taux=f"{taux:g}".replace(".", ",")),
                           f"{fmt_mad(van)}&nbsp;MAD"))
        offre = argent.get("financement")
        if isinstance(offre, dict) and offre.get("echeance_mad") is not None:
            lignes.append((L("ci_ind_financement", "Financement"),
                           ci_blocs._txt(offre.get("libelle_client"))
                           or L("ci_offre_financement",
                                "Offre de financement")))
    else:
        motif_html = ci_couverture.ligne_non_chiffre(d, "ind", prefixe)
        lignes.append((L("ci_ind_rentabilite", "Rentabilité"),
                       motif_html))
    if not d.get("ind_sous_reserve"):
        lignes.append((L("ci_ind_statut", "Statut de l'étude"),
                       L("ci_ind_offre_ferme", "offre ferme")))
    rangees = "".join(
        f'<tr><td class="{prefixe}-sy-l">{lib}</td>'
        f'<td class="{prefixe}-sy-v">{val}</td></tr>'
        for lib, val in lignes)
    return (f'<div class="{prefixe}-sy">'
            f'<div class="{prefixe}-sy-t">{L("ci_ind_synthese", "Synthèse")}'
            f'</div><table class="{prefixe}-sy-tbl">{rangees}</table>'
            f'{bandeau}</div>')


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
    client_full = theme.titlecase_name(d.get("client_full") or d.get("client_name") or "Client")
    client_meta = theme.join_meta(d.get("client_addr", ""), (d.get("client_ville_libelle") or d.get("client_city", "")),
                                  d.get("client_phone", ""))
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
        suffixe = " — " + L("ci_ind_baseline_kwh", "kWh déclarés")
    else:
        # Sans source servie, la couverture ne prétend plus « 12 mois ».
        suffixe = ""

    # QJR119 — les factures manquantes ne se REMBOURRENT PLUS de zéros.
    # CIQ341 — des kWh SEULS (source « kWh déclarés ») n'ont pas de montant
    # en MAD : ni facture imprimée, ni « facture non communiquée ».
    bills = [float(b or 0) for b in (d.get("factures_mensuelles") or [])][:12]
    bills_ok = any(b > 0 for b in bills) and source != "kwh_declares"
    annual_bill = round(sum(bills)) if bills_ok else None
    avg_bill = round(annual_bill / 12) if annual_bill else None
    if bills_ok:
        while len(bills) < 12:
            bills.append(0.0)
        bmax = max(bills) or 1.0
        # Barres CSS (hauteurs en mm — déterministes, jamais de % en cellule).
        bar_cells = ""
        for i, b in enumerate(bills):
            h = round(b / bmax * 26.0, 1)
            bar_cells += (
                f'<td class="i1-bc"><div class="i1-bar" style="height:{h}mm">'
                f'</div><div class="i1-mn">{_MONTHS[i]}</div></td>')
        bars_html = f'<table class="i1-bars"><tr>{bar_cells}</tr></table>'
        libelle_facture = (
            L("ci_ind_facture_estimee", "Facture électrique estimée")
            if source == "mois_interpoles"
            else L("ci_ind_facture_actuelle", "Facture électrique actuelle"))
        bill_html = (
            f'<div class="i1-big">{fmt(annual_bill)}<span>&nbsp;'
            f'{L("ci_mad_an", "MAD/an")}</span></div>'
            + ancre("facture_annuelle_avant", fmt(annual_bill)) +
            f'<div class="i1-basel">{libelle_facture} · ≈ '
            f'{fmt(avg_bill)} {L("ci_mad_mois", "MAD/mois")}</div>'
            + ancre("facture_mensuelle_avant", fmt(avg_bill)))
    elif source == "kwh_declares":
        bars_html = ""
        bill_html = ""
    else:
        bars_html = ""
        bill_html = ('<div class="i1-basel">'
                     + L("ci_ind_facture_non_communiquee",
                         "Facture électrique actuelle non communiquée — "
                         "transmettez 12 mois de factures et la baseline se "
                         "chiffre.")
                     + '</div>')

    # QJR651 — la cellule KPI est commune (premium_base.kpi).
    def kpi(val, unit, label, fig=None):
        return premium_base.kpi(val, unit, label, fig, prefixe="i1")

    cellules = [kpi(kwc, "&nbsp;kWc",
                    L("ci_puissance_crete", "Puissance crête"),
                    "puissance_kwc")]
    cellules.extend(ci_couverture.tuiles_taux(d, "ind", kpi))
    # CIQ307 — tuiles d'argent lues sur ``synthese_ci.argent`` ; absentes ⇒
    # omises (jamais un « 0 », QJR119).
    cellules.extend(ci_couverture.tuiles_argent(d, "ind", kpi, fmt))
    kpis = '<td class="i1-kgap"></td>'.join(cellules)
    bandeau = ci_couverture.bandeau_reserve(d, "ind", "i1")
    methode_line = ci_couverture.ligne_methode(d, "ind", "i1")
    note_pointe = ci_couverture.note_pointe(d, "ind")

    # QXMT — la SOURCE du barème voyage avec le chiffre. CIQ341 — argent non
    # servi ⇒ son motif (pour un site MT : les 12 factures MT, jamais
    # « votre répartition horaire ») est dit UNE fois, dans la synthèse.
    if d.get("ind_masquer_economies") or d.get("ind_economies") is None:
        mt_line = ""
    elif d.get("ind_mt_mention"):
        mt_line = f'<div class="i1-mtsrc">{d["ind_mt_mention"]}</div>'
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
    conso_line = (L("ci_ind_conso", "Consommation ≈ {kwh} kWh/an",
                    kwh=fmt(round(conso))) if conso else "")
    prod_line = (L("ci_ind_production_estimee",
                   "Production estimée ≈ {kwh} kWh/an",
                   kwh=fmt(round(prod)))
                 + ancre("production_annuelle_kwh", fmt(round(prod)))
                 if prod else "")
    inst_type = d.get('inst_type', 'Industrielle')
    if inst_type == "Industrielle":
        inst_type = L("ci_ind_tag", "Industrielle")

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
.i1-title{{font-family:{f_display};font-size:24pt;line-height:1.05;margin-top:4px;}}
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
.i1-ku{{font-size:8.5pt;color:{muted};}}
.i1-kl{{font-size:7pt;color:{muted};margin-top:3px;letter-spacing:.3px;}}
/* QXMT — ligne SOURCE sous le bloc économies (petite, jamais un chiffre nu). */
.i1-mtsrc{{margin-top:5px;font-size:6.8pt;color:{muted};line-height:1.35;}}
{ci_couverture.css_bandeau("i1", gold, ink, muted)}
.i1-note{{margin-top:8px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:8px 14px;font-size:8pt;color:{ink};line-height:1.4;}}
.i1-note b{{color:{navy};}}
.i1-inv{{margin-top:8px;display:table;width:100%;border:1px solid {line};
  border-radius:12px;background:{wash};padding:9px 16px;}}
.i1-inv-l{{display:table-cell;vertical-align:middle;font-size:8.5pt;color:{muted};}}
.i1-inv-v{{display:table-cell;vertical-align:middle;text-align:right;
  font-family:{f_display};font-size:17pt;color:{navy};}}
.i1-inv-v span{{font-size:10pt;color:{muted};}}
</style>
"""

    # CIQ315 — investissement sur la base de ``synthese_ci.argent.base``.
    inv_html = ci_couverture.bloc_investissement(
        d, d.get("ind_synthese") or {}, "i1", fmt_mad, ancre, invest=invest_centimes)
    synthese_html = bloc_synthese(d, L, fmt, fmt_mad, bandeau)
    note_autoconso = L(
        "ci_ind_note_autoconso",
        "L'installation vise l'<b>autoconsommation</b> : la valeur porte "
        "d'abord sur\n      les <b>heures pleines</b> (production en journée).")
    baseline_titre = L("ci_ind_baseline", "Baseline énergétique") + suffixe
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
      <div class="i1-serif i1-title">{L("ci_ind_titre", "Réduire votre coût de l'énergie")}</div>
      <div class="i1-sub">{L("ci_ind_sous_titre", "Analyse de rentabilité (CFO) — baseline, cashflow et payback.")}</div>
    </div>
  </div>

  <div class="i1-client">
    <b>{client_full}</b>
    {f'&nbsp;·&nbsp;{client_meta}' if client_meta else ''}
    <span class="i1-tag">{inst_type}</span>{ci_blocs.bloc_client((d.get('ind_synthese') or {}).get('entreprise_client'), 'i1', d.get('client_full') or d.get('client_name'), doc=d)}
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

    {inv_html}
  </div>
</div>
"""
    return html
