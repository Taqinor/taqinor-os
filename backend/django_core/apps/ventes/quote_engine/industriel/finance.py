# flake8: noqa
"""quote_engine industriel — PAGE 3 (rentabilité : jalons 5/10/15/20/25,
courbe du cumul sur tout l'horizon, TRI avec son horizon, payback ancré).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``i2-``.

CIQ342 (D-CIQ-10) — la page REND ``synthese_ci['argent']`` tel que servi
(bloc ``economie_ci`` du moteur C&I, CIQ3/CIQ304) : flux 25 ans de la base
principale, jalons, indicateurs (TRI + horizon, retour), revente « hors
cashflow » (le moteur ne l'additionne jamais au flux), O&M déduite
SEULEMENT si l'option est chiffrée, hypothèses du moteur, pied de page sur la
base servie (CIQ315). Plus AUCUNE arithmétique privée : ni solveur de TRI,
ni troncature à 15 ans, ni flux reconstruit. Sans série servie, le motif.
Rendu seul — aucun statut touché (règle #4).
"""
from ..ci import blocs as ci_blocs
from ..ci import couverture as ci_couverture
from ..figures import ancre
from ..lecture_pure import nombre_ou_none

#: Années des jalons (D-CIQ-10) — l'ordre d'impression, pas un calcul.
JALONS_ANS = (5, 10, 15, 20, 25)

#: Hypothèses du flux servi (``flux_*.hypotheses[].cle``) → libellé imprimé.
LIBELLES_HYPOTHESES = {
    "investissement_mad": ("ci_ind_h_investissement", "Investissement"),
    "economie_annee1_mad": ("ci_ind_h_economie", "Économie de l'année 1"),
    "production_annee1_kwh": ("ci_ind_h_production",
                              "Production de l'année 1"),
    "horizon_ans": ("ci_ind_h_horizon", "Horizon"),
    "taux_actualisation_pct": ("ci_ind_h_taux", "Taux d'actualisation"),
    "indexation_pct": ("ci_ind_h_indexation", "Indexation du tarif"),
    "degradation_pct": ("ci_ind_h_degradation", "Dégradation des panneaux"),
}
UNITES_HYPOTHESES = {
    "investissement_mad": "MAD", "economie_annee1_mad": "MAD",
    "production_annee1_kwh": "kWh", "horizon_ans": None,
    "taux_actualisation_pct": "%", "indexation_pct": "% / an",
    "degradation_pct": "% / an",
}

_num = nombre_ou_none


def flux_principal(argent):
    """``(clé, bloc)`` du flux de la base principale servie (``flux_ttc``
    en base TTC, ``flux_ht`` sinon — la règle du moteur ``economie_ci``)."""
    if not isinstance(argent, dict):
        return None, {}
    cle = "flux_ttc" if argent.get("base") == "ttc" else "flux_ht"
    bloc = argent.get(cle)
    return cle, bloc if isinstance(bloc, dict) else {}


def _cumuls(jalons):
    return {j.get("annee"): _num(j.get("cumul_mad")) for j in jalons or []
            if isinstance(j, dict)}


def _courbe(flux, couleurs):
    """Courbe du cumul net, une barre par année sur TOUT l'horizon servi
    (au-dessus de l'axe : positif ; en dessous : négatif). Seule la HAUTEUR
    des barres est mise à l'échelle — aucun montant n'est calculé."""
    points = [(_num(f.get("annee")), _num(f.get("cumul_mad")))
              for f in flux if isinstance(f, dict)]
    points = [(a, c) for a, c in points if a is not None and c is not None]
    if len(points) < 2:
        return ""
    echelle = max(abs(c) for _a, c in points) or 1.0
    haut, bas = "", ""
    for annee, cumul in points:
        h = round(abs(cumul) / echelle * 22.0, 1)
        if cumul >= 0:
            haut += (f'<td class="i2-cb"><div class="i2-bp" '
                     f'style="height:{h}mm"></div></td>')
            bas += '<td class="i2-ct"></td>'
        else:
            haut += '<td class="i2-cb"></td>'
            bas += (f'<td class="i2-ct"><div class="i2-bn" '
                    f'style="height:{h}mm"></div></td>')
    etiquettes = "".join(
        f'<td class="i2-ca">{int(a) if a in (0,) + JALONS_ANS else ""}</td>'
        for a, _c in points)
    return (f'<table class="i2-courbe"><tr>{haut}</tr>'
            f'<tr class="i2-axe">{bas}</tr><tr>{etiquettes}</tr></table>')


def _valeur_hypothese(h, fmt, L):
    valeur = h.get("valeur")
    cle = h.get("cle")
    if valeur is None:
        return None
    unite = UNITES_HYPOTHESES.get(cle)
    if isinstance(valeur, (int, float)):
        if cle == "horizon_ans":
            return L("ci_ind_n_ans", "{n} ans", n=f"{valeur:g}")
        texte = fmt(valeur) if unite in ("MAD", "kWh") else \
            f"{valeur:g}".replace(".", ",")
        return f"{texte}&nbsp;{unite}" if unite else texte
    return ci_blocs._txt(valeur)


def _hypotheses(argent, flux, fmt, fmt_mad, L):
    """Les hypothèses DU MOTEUR (flux servi, valorisation, tarif,
    remplacements), chacune avec sa source — aucune n'est écrite ici."""
    lignes = []
    for h in flux.get("hypotheses") or []:
        if not isinstance(h, dict) or h.get("cle") not in LIBELLES_HYPOTHESES:
            continue
        valeur = _valeur_hypothese(h, fmt, L)
        if valeur is None:
            continue
        cat, fr = LIBELLES_HYPOTHESES[h["cle"]]
        source = ci_blocs._txt(h.get("source"))
        lignes.append(f"{L(cat, fr)}&#160;: {valeur}"
                      + (f" — {source}" if source else ""))
    for h in argent.get("hypotheses") or []:
        if isinstance(h, dict) and h.get("valeur"):
            source = ci_blocs._txt(h.get("source"))
            lignes.append(ci_blocs._txt(h.get("valeur"))
                          + (f" — {source}" if source else ""))
    for r in argent.get("remplacements") or []:
        if not isinstance(r, dict) or r.get("annee") is None:
            continue
        montant = r.get("montant_ttc_mad")
        lignes.append(
            L("ci_ind_remplacement", "Remplacement {composant} en année {annee}",
              composant=ci_blocs._txt(r.get("composant")),
              annee=f"{r['annee']:g}" if isinstance(r["annee"], (int, float))
              else r["annee"])
            + (f"&#160;: {fmt_mad(montant)}&nbsp;MAD {L('ci_ttc', 'TTC')}"
               if montant is not None else "")
            + (f" — {ci_blocs._txt(r.get('motif'))}" if r.get("motif") else ""))
    return lignes


def _ligne_om(argent, fmt_mad, L):
    """CIQ342 — l'O&M n'est dite DÉDUITE que si l'option est chiffrée
    (``argent.om`` souscrite avec un montant) ; proposée ou à chiffrer ⇒
    « non déduite » ; absente du devis ⇒ rien (D-CIQ-12)."""
    om = argent.get("om") if isinstance(argent, dict) else None
    if not isinstance(om, dict):
        return ""
    montant = _num(om.get("montant_mad_an"))
    if om.get("statut") == "souscrit" and montant:
        return L("ci_ind_om_deduite", "O&amp;M déduite du flux : {montant} MAD/an",
                 montant=fmt_mad(montant))
    if om.get("statut") in ("propose", "tarif_a_renseigner"):
        return L("ci_ind_om_non_deduite",
                 "O&amp;M proposée, non déduite de ces montants")
    return ""


def _ligne_revente(argent, fmt, L, langue):
    """Revente 82-21 (MT seulement) telle que servie : le moteur ne
    l'additionne JAMAIS au flux — elle est dite « hors cashflow », avec sa
    mention (CIQ305). Jamais « le surplus n'est pas rémunéré » à côté."""
    revente = argent.get("revente") if isinstance(argent, dict) else None
    if not isinstance(revente, dict) or revente.get("statut") != "calculee":
        return ""
    valeur = _num(revente.get("valeur_mad_an"))
    if not valeur:
        return ""
    mentions = [m for m in revente.get("mentions") or [] if m]
    mention = (f' <span class="i2-mini">{" ".join(mentions)}</span>'
               if mentions else "")
    return (f'<div class="i2-inj"><b>+ {fmt(valeur)} '
            f'{L("ci_mad_an", "MAD/an")}</b> — '
            + L("ci_ind_revente_hors_cashflow",
                "revente du surplus, hors cashflow (non comptée dans le "
                "retour ni le TRI).")
            + f'{mention}</div>')


def _pied_investissement(d, argent, fmt_mad, L):
    """CIQ315 — l'investissement du pied de page sur la base SERVIE."""
    base = argent.get("base") if isinstance(argent, dict) else None
    ht = (d.get("totaux_all") or {}).get("ht_net")
    ttc = d.get("_invest_ttc") or 0
    l_ht, l_ttc = L("ci_ht", "HT"), L("ci_ttc", "TTC")
    if base == "ht" and ht is not None:
        return (L("ci_invest_ht", "Investissement HT (clé en main)")
                + f" : <b>{fmt_mad(ht)} MAD {l_ht}</b>")
    if base == "deux" and ht is not None:
        return (L("ci_invest", "Investissement (clé en main)")
                + f" : <b>{fmt_mad(ttc)} MAD {l_ttc}</b> "
                  f"({L('ci_soit', 'soit')} {fmt_mad(ht)} MAD {l_ht})")
    return (L("ci_invest_ttc", "Investissement (TTC, clé en main)")
            + f" : <b>{fmt_mad(ttc)} MAD</b>")


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fmt_mad = ctx.get("fmt_mad") or fmt
    fonts = ctx["fonts"]

    def L(cle, fr, **valeurs):
        return ci_blocs.libelle(d, cle, fr, **valeurs)

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
    blue = C.get("blue", "#2C5F8A")

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    synthese = d.get("ind_synthese") or {}
    argent = synthese.get("argent") if isinstance(synthese, dict) else None
    argent = argent if isinstance(argent, dict) else {}
    _cle, flux = flux_principal(argent)
    lignes_flux = [f for f in flux.get("flux") or [] if isinstance(f, dict)]
    indicateurs = argent.get("indicateurs") or {}
    horizon = _num(indicateurs.get("tri_horizon_ans")) or \
        _num(flux.get("horizon_ans"))
    chiffrable = (bool(lignes_flux) and not d.get("ind_masquer_economies")
                  and horizon is not None)
    horizon_txt = f"{horizon:g}" if horizon else "25"
    base_txt = {"ttc": L("ci_ttc", "TTC")}.get(argent.get("base"),
                                               L("ci_ht", "HT"))

    css = f"""
<style>
.i2-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.i2-root *{{box-sizing:border-box;}}
.i2-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.i2-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.i2-lead{{font-size:8.5pt;color:{muted};margin-top:4px;}}
.i2-kpis{{width:100%;margin-top:10px;border-spacing:0;border-collapse:separate;}}
.i2-kpi{{vertical-align:top;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;padding:11px 14px;background:#fff;}}
.i2-kgap{{width:12px;}}
.i2-kv{{font-family:{f_display};font-size:19pt;color:{navy};line-height:1;}}
.i2-kl{{font-size:7.5pt;color:{muted};margin-top:4px;}}
.i2-inj{{margin-top:10px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:{green_bg};padding:8px 14px;font-size:8pt;color:{ink};}}
.i2-inj b{{color:{green};}}
.i2-mini{{color:{muted};font-size:7pt;}}
.i2-cfhead{{margin-top:12px;font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};}}
.i2-tbl{{width:100%;border-collapse:collapse;margin-top:6px;font-size:8pt;}}
.i2-tbl th{{text-align:left;color:{muted};font-size:7pt;text-transform:uppercase;
  letter-spacing:.4px;padding:5px 8px;border-bottom:1px solid {line};}}
.i2-tbl th.i2-r,.i2-tbl td.i2-c{{text-align:right;}}
.i2-tbl td{{padding:4px 8px;border-bottom:1px solid {line_soft};}}
.i2-c{{font-weight:700;}}
.i2-pos{{color:{green};}}
.i2-neg{{color:{muted_2};}}
.i2-courbe{{width:100%;border-collapse:collapse;margin-top:8px;table-layout:fixed;}}
.i2-cb{{height:22mm;vertical-align:bottom;padding:0 1px;}}
.i2-ct{{height:12mm;vertical-align:top;padding:0 1px;}}
.i2-axe td{{border-top:1px solid {muted_2};}}
.i2-bp{{background:{green};border-radius:2px 2px 0 0;}}
.i2-bn{{background:{muted_2};border-radius:0 0 2px 2px;max-height:12mm;}}
.i2-ca{{font-size:6pt;color:{muted};text-align:center;}}
.i2-foot{{margin-top:9px;font-size:7.5pt;color:{muted};line-height:1.4;}}
.i2-foot b{{color:{navy};}}
.i2-mt{{margin-top:13px;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;background:{wash};padding:13px 16px;}}
.i2-mt-t{{font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};}}
.i2-mt-b{{margin-top:6px;font-size:8.5pt;color:{ink};line-height:1.45;}}
.i2-mt-b b{{color:{navy};}}
.i2-hyp{{margin-top:8px;border:1px solid {line_soft};border-radius:10px;
  background:{wash};padding:8px 12px;}}
.i2-hyp-t{{font-size:8pt;font-weight:700;color:{navy};}}
.i2-hyp-i{{font-size:6.8pt;color:{muted};line-height:1.3;margin-top:3px;
  padding-left:10px;position:relative;}}
.i2-hyp-i:before{{content:'';position:absolute;left:0;top:4px;width:4px;
  height:4px;border-radius:50%;background:{blue};}}
</style>
"""

    pied = _pied_investissement(d, argent, fmt_mad, L)
    if not chiffrable:
        # QJR119 / QXMT — sans série servie, le MOTIF remplace le corps
        # chiffré (jamais une table de zéros) : la page ne peut que
        # raccourcir. CIQ341 — un site MT demande ses 12 factures MT.
        motif = ci_couverture.ligne_non_chiffre(d, "ind", "i2")
        if ci_couverture._argent_mt(d, "ind"):
            corps_txt = L(
                "ci_ind_motif_mt",
                "Votre installation est raccordée en <b>MOYENNE TENSION</b> : "
                "ses économies se chiffrent sur le barème MT par poste "
                "horaire, pas sur le barème basse tension. Nous préférons ne "
                "rien afficher plutôt qu'un chiffre qui n'est pas le vôtre.")
        else:
            corps_txt = L(
                "ci_ind_motif_bt",
                "Les <b>économies annuelles</b> de cette installation n'ont "
                "pas encore été calculées sur vos données. Nous préférons ne "
                "rien afficher plutôt qu'un cashflow, un point mort ou un TRI "
                "qui ne reposeraient sur aucune mesure.")
        corps = f"""
  <div class="i2-mt">
    <div class="i2-mt-t">{L("ci_ind_non_chiffre_titre", "Rentabilité non chiffrée sur ce dossier")}</div>
    <div class="i2-mt-b">{corps_txt}</div>
    {motif}
  </div>
  <div class="i2-foot">{pied}.</div>"""
        lead_txt = L("ci_ind_lead_non_chiffre",
                     "Aucune rentabilité n'est publiée tant qu'elle n'est pas "
                     "calculée sur vos données.")
    else:
        economie = d.get("ind_economies")
        base_eco = d.get("ind_economie_base")
        if base_eco in ("HT", "TTC"):
            base_eco = L(f"ci_{base_eco.lower()}", base_eco)
        payback = _num(indicateurs.get("retour_ans"))
        tri = _num(indicateurs.get("tri_pct"))
        tri_txt = f"{tri:.1f}".replace(".", ",") if tri is not None else None

        def kpi(valeur, unite, libelle, cle_fig=None, texte_fig=None):
            a = ancre(cle_fig, texte_fig) if cle_fig else ""
            return (f'<td class="i2-kpi"><div class="i2-kv">{valeur}'
                    f'<span class="i2-kl">{unite}</span></div>{a}'
                    f'<div class="i2-kl">{libelle}</div></td>')

        cellules = []
        if economie is not None:
            cellules.append(kpi(
                fmt(economie), "&nbsp;MAD",
                L("ci_ind_economie_an1", "Économie de l'année 1")
                + (f" ({base_eco})" if base_eco else ""),
                "economie_annuelle", fmt(economie)))
        if payback is not None:
            cellules.append(kpi(
                ci_couverture.ans(payback), L("ci_unite_ans", "&nbsp;ans"),
                L("ci_ind_retour_flux", "Retour (même flux)"),
                "payback_ans", ci_couverture.ans(payback)))
        if tri_txt is not None:
            cellules.append(kpi(
                tri_txt, "&nbsp;%",
                L("ci_ind_tri_sur", "TRI sur {n} ans", n=horizon_txt),
                "tri_pct", tri_txt))
        kpis = ('<table class="i2-kpis"><tr>'
                + '<td class="i2-kgap"></td>'.join(cellules)
                + '</tr></table>') if cellules else ""

        jalons = _cumuls(argent.get("jalons"))
        jalons_ttc = (_cumuls(argent.get("jalons_ttc"))
                      if argent.get("base") == "deux" else {})
        entete_ttc = (f'<th class="i2-r">{L("ci_ind_cumul_net", "Cumul net")} '
                      f'({L("ci_ttc", "TTC")})</th>' if jalons_ttc else "")
        rangees = ""
        for annee in JALONS_ANS:
            cumul = jalons.get(annee)
            if cumul is None:
                continue
            txt = fmt_mad(cumul)
            fig = ancre("cumul_net_25_ans_mad", txt) if annee == 25 else ""
            cls = "i2-pos" if cumul >= 0 else "i2-neg"
            ttc_td = ""
            if jalons_ttc:
                cumul_ttc = jalons_ttc.get(annee)
                ttc_td = (f'<td class="i2-c {cls}">{fmt_mad(cumul_ttc)}</td>'
                          if cumul_ttc is not None else '<td></td>')
            rangees += (
                f'<tr><td>{L("ci_ind_annee", "Année {n}", n=annee)}</td>'
                f'<td class="i2-c {cls}">{txt}{fig}</td>{ttc_td}</tr>')
        table = (
            f'<table class="i2-tbl"><tr><th>{L("ci_ind_jalon", "Jalon")}</th>'
            f'<th class="i2-r">{L("ci_ind_cumul_net", "Cumul net")} '
            f'({base_txt})</th>{entete_ttc}</tr>{rangees}</table>'
            if rangees else "")
        courbe = _courbe(lignes_flux, None)
        lignes_hyp = _hypotheses(argent, flux, fmt, fmt_mad, L)
        hypotheses_html = (
            f'<div class="i2-hyp"><div class="i2-hyp-t">'
            f'{L("ci_ind_hypotheses", "Hypothèses du moteur")}</div>'
            + "".join(f'<div class="i2-hyp-i">{h}</div>' for h in lignes_hyp)
            + '</div>') if lignes_hyp else ""
        om_txt = _ligne_om(argent, fmt_mad, L)
        revente_html = _ligne_revente(argent, fmt, L, ci_blocs.langue(d))
        mt_source = (f'<br><span class="i2-mini">{d["ind_mt_mention"]}</span>'
                     if d.get("ind_mt_mention") else "")
        corps = f"""
  {kpis}
  {revente_html}
  <div class="i2-cfhead">{L("ci_ind_cumul_titre", "Cumul net de l'investissement ({base})", base=base_txt)}</div>
  {courbe}
  {table}
  {hypotheses_html}
  <div class="i2-foot">
    {(om_txt + '. ') if om_txt else ''}{pied}.
    {L("ci_ind_methode_tri", "TRI et retour lus sur le flux servi par le moteur C&amp;I (méthode actuarielle) ; chiffres indicatifs.")}
    {mt_source}
  </div>"""
        lead_txt = L("ci_ind_lead",
                     "Projection du moteur C&amp;I sur {n} ans : flux, retour "
                     "et TRI tirés de la même série ; hypothèses détaillées "
                     "ci-dessous.", n=horizon_txt)

    html = f"""{css}
<div class="i2-root">
  <div class="i2-kicker">{L("ci_ind_analyse_financiere", "Analyse financière")}</div>
  <div class="i2-sec">{L("ci_ind_rentabilite_sur", "Rentabilité sur {n} ans", n=horizon_txt)}</div>
  <div class="i2-lead">{lead_txt}</div>
{corps}
</div>
"""
    return html
