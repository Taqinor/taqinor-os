# flake8: noqa
"""quote_engine industriel — PAGE 2 (cashflow 15 ans, payback, TRI).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``i2-``.

Hypothèse PRUDENTE et HONNÊTE : économies maintenues CONSTANTES (aucune escalade
tarifaire inventée). Le cashflow est l'intégrale de ces économies nettes ; le TRI
est un VRAI calcul (bisection) sur ce flux, pas un chiffre inventé.
"""

_HORIZON = 15  # ans


def irr_flat(invest, annual_net, years=_HORIZON):
    """TRI (%) d'un flux [-invest, net, net, …] sur ``years`` ans (bisection).
    Renvoie None si dégénéré. Aucune constante inventée : pure arithmétique."""
    try:
        invest = float(invest)
        annual_net = float(annual_net)
    except (TypeError, ValueError):
        return None
    if invest <= 0 or annual_net <= 0 or years <= 0:
        return None

    def npv(r):
        total = -invest
        for t in range(1, years + 1):
            total += annual_net / ((1 + r) ** t)
        return total

    lo, hi = -0.9, 5.0
    if npv(lo) < 0:
        return None  # pas de racine positive dans la plage
    if npv(hi) > 0:
        return None  # TRI > 500 % (invraisemblable) → on n'affiche pas
    for _ in range(80):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1e-6:
            break
        if v > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2 * 100, 1)


def _flux_annuels(cumule, invest):
    """Flux ANNUELS déduits de la série CUMULÉE servie par le builder.

    ``pricing`` publie le cumul NET d'investissement (année 1 = −invest + f1) :
    le flux de chaque année est donc la différence avec l'année précédente,
    la première se lisant depuis ``−invest``. Aucune hypothèse locale."""
    flux, precedent = [], -float(invest or 0)
    for valeur in (cumule or []):
        try:
            v = float(valeur)
        except (TypeError, ValueError):
            return []
        flux.append(v - precedent)
        precedent = v
    return flux


def irr_series(invest, flux, _bornes=(-0.9, 5.0)):
    """TRI (%) d'un flux [-invest, f1, f2, …] RÉEL (bisection).

    Même méthode que ``irr_flat``, mais sur les flux effectivement imprimés
    (dégradation panneau et provision de remplacement onduleur comprises) —
    plus un flux constant qui ne décrit aucune des lignes de la table."""
    try:
        invest = float(invest)
        flux = [float(f) for f in (flux or [])]
    except (TypeError, ValueError):
        return None
    if invest <= 0 or not flux or sum(flux) <= invest:
        return None

    def npv(r):
        return -invest + sum(f / ((1 + r) ** t)
                             for t, f in enumerate(flux, start=1))

    lo, hi = _bornes
    if npv(lo) < 0 or npv(hi) > 0:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        v = npv(mid)
        if abs(v) < 1e-6:
            break
        if v > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2 * 100, 1)


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]

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

    invest = d.get("_invest_ttc") or 0
    om = d.get("ind_om_annuel")
    injection = d.get("ind_injection_dh")

    # ── QJR120 — LE CASHFLOW AFFICHÉ EST LE CASHFLOW CANONIQUE ──────────────
    # Le renderer sert la série CUMULÉE de ``pricing.compute_cashflow_payback``
    # pour la branche dont le PRIX est rendu (voir ``renderer._augment``). Elle
    # porte la dégradation panneau et la provision de remplacement onduleur —
    # que la droite plate « t × économie − investissement » ignorait, alors que
    # l'année 12 du remplacement tombe DANS les 15 années imprimées.
    # QJR119 — sans série chiffrable, la page bascule sur son motif d'omission
    # (jamais une table de 15 lignes à « 0 » ni un « Point mort > 15 ans »
    # d'apparence calculée).
    serie = d.get("ind_cashflow") or []
    flux = _flux_annuels(serie, invest)
    chiffrable = len(flux) >= 2 and invest > 0
    horizon = min(_HORIZON, len(flux)) if chiffrable else 0

    # Table cashflow — les cumulés SERVIS, pas un modèle local.
    rows = ""
    breakeven = None
    payback = None
    for t in range(1, horizon + 1):
        cumul = round(serie[t - 1])
        precedent = serie[t - 2] if t > 1 else -float(invest)
        if breakeven is None and cumul >= 0:
            breakeven = t
            # QJR120 (c) — le payback sort du MÊME flux que le point mort
            # (croisement à zéro interpolé dans l'année), plus d'un ratio
            # année-1 calculé sur une AUTRE option et une économie brute.
            span = serie[t - 1] - precedent
            payback = round((t - 1) + ((0 - precedent) / span if span else 0), 1)
        cls = "i2-pos" if cumul >= 0 else "i2-neg"
        star = ' class="i2-be"' if t == breakeven else ""
        rows += (
            f'<tr{star}><td class="i2-y">Année {t}</td>'
            f'<td class="i2-e">{fmt(round(flux[t - 1]))}</td>'
            f'<td class="i2-c {cls}">{fmt(cumul)}</td></tr>')

    # TRI sur le MÊME flux et le MÊME horizon que la table (méthode actuarielle).
    tri = irr_series(invest, flux[:horizon]) if chiffrable else None
    # Économie de l'ANNÉE 1 du flux servi — jamais une moyenne inventée.
    eco_an1 = round(flux[0]) if chiffrable else None

    # QJR119 — le payback n'est imprimé que s'il EXISTE ; QJR120 — et il vient
    # désormais du croisement à zéro de la courbe imprimée juste dessous.
    payback_txt = (f"{payback:.1f}".replace(".", ",") + " ans"
                   if isinstance(payback, (int, float)) and payback > 0
                   else None)
    payback_phrase = (f"<b>Payback</b> (retour d'investissement) ≈ "
                      f"{payback_txt} — c'est le croisement à zéro de la "
                      f"courbe ci-dessus. " if payback_txt else "")
    tri_txt = (f"{tri:.1f}".replace(".", ",") + " %"
               if isinstance(tri, (int, float)) else "—")
    be_txt = (f"Année {breakeven}" if breakeven else f"> {horizon or _HORIZON} ans")

    # QJR120 (a) — LES HYPOTHÈSES DU MODÈLE SONT DÉCLARÉES, pas seulement
    # appliquées : ``pricing.cashflow_assumptions`` les rédige (dégradation,
    # provision onduleur et son montant réel, rendement batterie, tarif
    # constant) et le renderer les sert. Absentes ⇒ bloc omis.
    _notes = ((d.get("ind_cashflow_hypotheses") or {}).get("notes")
              if chiffrable else None)
    hypotheses_html = ""
    if _notes:
        hypotheses_html = (
            '<div class="i2-hyp"><div class="i2-hyp-t">Nos hypothèses</div>'
            + "".join(f'<div class="i2-hyp-i">{n}</div>' for n in _notes)
            + '</div>')

    # Ligne injection 82-21 — rendue UNIQUEMENT si l'étude la porte (QX50).
    injection_row = ""
    if injection:
        injection_row = (
            f'<div class="i2-inj">'
            f'<b>+ {fmt(round(injection))} MAD/an</b> — surplus injecté (loi 82-21, '
            f'net des frais réseau, plafond 20 % de la production). '
            f'<span class="i2-mini">Tarif ANRE 03/2026-02/2027, plafond en révision.</span>'
            f'</div>')

    # QJR120 (b) — « inclus dans les économies nettes » était affirmé sur TOUT
    # devis, alors qu'aucun producteur d'``om_annuel`` n'existe dans le dépôt :
    # les montants ci-dessus ne déduisent RIEN. Le document le DIT.
    om_txt = (f"O&amp;M déduit : {fmt(round(om))} MAD/an" if om
              else ("O&amp;M (nettoyage, supervision) <b>non déduit</b> de ces "
                    "montants — chiffré séparément"))

    # QXMT — chapô + ligne SOURCE du barème MT (jamais un chiffre nu).
    # QJR119 — troisième chapô : économies non chiffrables (hors MT). Le chapô
    # « Hypothèse prudente » qualifiait un modèle qui n'avait aucune donnée.
    if d.get("ind_masquer_economies"):
        lead_txt = ("Le barème applicable à ce dossier est un barème MOYENNE "
                    "TENSION : aucun chiffre n'est repris du barème basse "
                    "tension.")
    elif not chiffrable:
        lead_txt = ("Les économies annuelles de ce dossier ne sont pas encore "
                    "chiffrées : aucune rentabilité n'est publiée tant qu'elle "
                    "n'est pas calculée sur vos données.")
    else:
        # QJR120 — le chapô décrit le modèle RÉELLEMENT appliqué (celui de
        # ``pricing``), pas une droite plate qualifiée de « prudente » : les
        # hypothèses détaillées sont rendues sous la table.
        lead_txt = ("Projection au modèle de référence : dégradation panneau "
                    "et provision de remplacement onduleur intégrées, aucune "
                    "hausse du tarif électrique supposée (toute hausse réelle "
                    "améliore le résultat). Hypothèses détaillées ci-dessous.")
    mt_source = (f'<br><span class="i2-mini">{d["ind_mt_mention"]}</span>'
                 if d.get("ind_mt_mention") else "")

    css = f"""
<style>
.i2-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.i2-root *{{box-sizing:border-box;}}
.i2-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.i2-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.i2-lead{{font-size:8.5pt;color:{muted};margin-top:4px;}}
.i2-kpis{{display:table;width:100%;margin-top:11px;border-spacing:0;}}
.i2-kpi{{display:table-cell;vertical-align:top;border:1px solid {line};
  border-radius:12px;padding:12px 14px;background:{wash};}}
.i2-kgap{{display:table-cell;width:12px;}}
.i2-kpi.i2-hi{{border-left:4px solid {gold};background:#fff;}}
.i2-kv{{font-family:{f_display};font-size:20pt;color:{navy};line-height:1;}}
.i2-kl{{font-size:7.5pt;color:{muted};margin-top:4px;}}
.i2-inj{{margin-top:11px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:{green_bg};padding:9px 14px;font-size:8pt;color:{ink};}}
.i2-inj b{{color:{green};}}
.i2-mini{{color:{muted};font-size:7pt;}}
.i2-cfhead{{margin-top:13px;font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};}}
.i2-tbl{{width:100%;border-collapse:collapse;margin-top:7px;font-size:8pt;}}
.i2-tbl th{{text-align:left;color:{muted};font-size:7pt;text-transform:uppercase;
  letter-spacing:.4px;padding:5px 8px;border-bottom:1px solid {line};}}
.i2-tbl th.i2-r,.i2-tbl td.i2-e,.i2-tbl td.i2-c{{text-align:right;}}
.i2-tbl td{{padding:4px 8px;border-bottom:1px solid {line_soft};}}
.i2-y{{color:{ink};}}
.i2-e{{color:{muted};}}
.i2-c{{font-weight:700;}}
.i2-pos{{color:{green};}}
.i2-neg{{color:{muted_2};}}
.i2-be td{{background:{green_bg};}}
.i2-be .i2-y{{font-weight:700;color:{navy};}}
.i2-foot{{margin-top:10px;font-size:7.5pt;color:{muted};line-height:1.4;}}
.i2-foot b{{color:{navy};}}
/* QXMT — corps de remplacement quand la rentabilité n'est pas chiffrable au
   barème du dossier (raccordement MT sans répartition horaire). */
.i2-mt{{margin-top:13px;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;background:{wash};padding:13px 16px;}}
.i2-mt-t{{font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};}}
.i2-mt-b{{margin-top:6px;font-size:8.5pt;color:{ink};line-height:1.45;}}
.i2-mt-b b{{color:{navy};}}
/* QJR120 — hypothèses DÉCLARÉES du modèle de cashflow (source : pricing). */
.i2-hyp{{margin-top:9px;border:1px solid {line_soft};border-radius:10px;
  background:{wash};padding:9px 12px;}}
.i2-hyp-t{{font-size:8pt;font-weight:700;color:{navy};}}
.i2-hyp-i{{font-size:7pt;color:{muted};line-height:1.35;margin-top:4px;
  padding-left:10px;position:relative;}}
.i2-hyp-i:before{{content:'';position:absolute;left:0;top:4px;width:4px;
  height:4px;border-radius:50%;background:{blue};}}
</style>
"""

    # QXMT — DOSSIER MT SANS ÉCONOMIES D'ÉTUDE : cette page EST le bloc
    # ROI/économies. Plutôt que d'imprimer un cashflow, un point mort, un TRI et
    # un payback tous dérivés du tarif BASSE TENSION de l'ONEE — c.-à-d. des
    # chiffres qui ne sont pas ceux du dossier — le corps chiffré est REMPLACÉ
    # par le motif de l'omission et le geste qui la lève. La page reste (le
    # nombre de pages ne bouge pas) et ne peut que RACCOURCIR : aucun risque de
    # débordement.
    if d.get("ind_masquer_economies"):
        corps = f"""
  <div class="i2-mt">
    <div class="i2-mt-t">Rentabilité non chiffrée sur ce dossier</div>
    <div class="i2-mt-b">
      Votre installation est raccordée en <b>MOYENNE TENSION</b>. Les économies
      et le retour sur investissement d'un dossier MT se calculent sur le barème
      MT par poste horaire (pointe / heures pleines / heures creuses) — pas sur
      le barème basse tension. Nous préférons ne rien afficher plutôt que
      d'afficher un chiffre qui n'est pas le vôtre.
      <br><br>
      <b>Ce qu'il nous manque :</b> votre répartition horaire de consommation
      (ou 12 mois de factures MT). Avec elle, nous chiffrons économies, point
      mort, TRI et payback sur VOTRE barème, et cette page se remplit.
    </div>
  </div>
  <div class="i2-foot">
    {om_txt}. Investissement (TTC, clé en main) : <b>{fmt(round(invest))} MAD</b>.
    Chiffres indicatifs, hors financement.
  </div>"""
    elif not chiffrable:
        # QJR119 — économies absentes de l'étude (hors MT) : même traitement
        # que le dossier MT — le motif de l'omission remplace le corps chiffré,
        # jamais une table de zéros. La page RACCOURCIT (pagination stable).
        corps = f"""
  <div class="i2-mt">
    <div class="i2-mt-t">Rentabilité non chiffrée sur ce dossier</div>
    <div class="i2-mt-b">
      Les <b>économies annuelles</b> de cette installation n'ont pas encore été
      calculées sur vos données. Nous préférons ne rien afficher plutôt que
      d'afficher un cashflow, un point mort ou un TRI qui ne reposeraient sur
      aucune mesure.
      <br><br>
      <b>Ce qu'il nous manque :</b> votre consommation réelle (12 mois de
      factures ou votre profil horaire). Avec elle, nous chiffrons économies,
      point mort, TRI et payback, et cette page se remplit.
    </div>
  </div>
  <div class="i2-foot">
    Investissement (TTC, clé en main) : <b>{fmt(round(invest))} MAD</b>.
    Chiffres indicatifs, hors financement.
  </div>"""
    else:
        corps = f"""
  <div class="i2-kpis">
    <div class="i2-kpi i2-hi"><div class="i2-kv">{fmt(eco_an1)}</div>
      <div class="i2-kl">Économie année 1 (MAD, hors O&amp;M)</div></div>
    <div class="i2-kgap"></div>
    <div class="i2-kpi i2-hi"><div class="i2-kv">{be_txt}</div>
      <div class="i2-kl">Point mort (cumul ≥ 0)</div></div>
    <div class="i2-kgap"></div>
    <div class="i2-kpi i2-hi"><div class="i2-kv">{tri_txt}</div>
      <div class="i2-kl">TRI sur {horizon} ans</div></div>
  </div>

  {injection_row}

  <div class="i2-cfhead">Cashflow cumulé</div>
  <table class="i2-tbl">
    <tr><th>Période</th><th class="i2-r">Économie de l'année</th><th class="i2-r">Cumul net (MAD)</th></tr>
    {rows}
  </table>
  {hypotheses_html}

  <div class="i2-foot">
    {payback_phrase}{om_txt}.
    Le TRI est calculé sur le flux d'économies ci-dessus (méthode actuarielle) ;
    aucune escalade tarifaire n'est supposée. Chiffres indicatifs, hors financement.
    {mt_source}
  </div>"""

    html = f"""{css}
<div class="i2-root">
  <div class="i2-kicker">Analyse financière</div>
  <div class="i2-sec">Rentabilité sur {horizon or _HORIZON} ans</div>
  <div class="i2-lead">{lead_txt}</div>
{corps}
</div>
"""
    return html
