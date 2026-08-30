# flake8: noqa
"""Agricole — PAGE 4 (rentabilité: solaire vs butane vs diesel + payback +
20-ans + impact) then conditions · prochaines étapes · « Bon pour accord »
signature + CTA. Classes a4-*. Equal-height, stretched columns fill the page.
Persuasion blocks toggleable: show_fuel_comparison / show_environmental."""
from __future__ import annotations


def _yrs(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return str(int(f)) if f == int(f) else f"{f:.1f}".replace(".", ",")


def _validity_days(v):
    """QJR149 — nombre de jours de validité, ou None quand il est indéterminable.

    Aucun repli forfaitaire : la valeur vient du devis ou n'est pas publiée.
    """
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _link(url):
    url = (url or "").strip()
    if not url:
        return "#"
    return url if url.startswith(("http://", "https://")) else "https://" + url


def _disp(url):
    url = (url or "").strip()
    for pre in ("https://", "http://"):
        if url.startswith(pre):
            url = url[len(pre):]
    return url


def build(ctx) -> str:
    from . import theme
    from . import constants as K
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]; charts = ctx["charts"]

    navy = C["navy"]; navy_900 = C["navy_900"]; gold = C["gold"]; green = C["green"]
    green_bg = C["green_bg"]; green_700 = C["green_700"]; water = C["water"]
    water_bg = C["water_bg"]; ink = C["ink"]; muted = C["muted"]; muted_2 = C["muted_2"]
    line = C["line"]; line_soft = C["line_soft"]; wash = C["wash"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]

    has_water = d.get("has_water")
    show_fuel_flag = d.get("show_fuel_comparison", True)
    show_fuel = show_fuel_flag and has_water
    # Environmental + butane-subsidy figures are computed from the pump rating
    # (CV · heures · jours) and market prices, not from m³/jour — so they exist
    # even for a curve-less pump and can anchor the degraded page.
    show_env = d.get("show_environmental", True)
    payback = d.get("payback"); payback_butane = d.get("payback_butane")
    payback_diesel = d.get("payback_diesel")
    annual_saving = d.get("annual_saving") or 0
    savings_20y = d.get("savings_20y") or 0
    show_subsidy = d.get("show_subsidy", True)
    current_fuel = d.get("current_fuel") or "butane"
    fuel_lbl = {"butane": "butane", "diesel": "diesel"}.get(current_fuel, "carburant")
    co2_t = d.get("co2_t") or 0; trees = d.get("trees") or 0
    fuel_qty = d.get("fuel_qty_label") or ""
    b_sub = d.get("butane_12kg_subventionne") or 50
    b_reel = d.get("butane_12kg_reel") or 128

    client_full = theme.titlecase_name(d.get("client_full") or d.get("client_name")) or "Le client"
    # QJR149 — la validité vient du DEVIS (``validity_days`` / ``valid_until``
    # posés par le builder depuis ``date_validite``, sinon création + réglage
    # société ``quote_validity_days``), jamais d'un « 30 jours » codé ici.
    # ``renderer._augment`` pose TOUJOURS les deux clés (``setdefault(..., None)``),
    # donc le défaut ``30`` de ``d.get("validity_days", 30)`` n'était JAMAIS
    # atteint : un devis sans validité calculable imprimait « None jours » dans
    # les conditions ET « None jours de validité » dans la pastille d'appel à
    # l'action. Indéterminable ⇒ la ligne ET la pastille sont OMISES, exactement
    # comme la pastille de ``cover.py`` (correctif M7).
    validity = _validity_days(d.get("validity_days"))
    valid_until = (d.get("valid_until") or "").strip()
    pay = d.get("payment_terms", {}) or {}
    acompte = pay.get("acompte", 30); materiel = pay.get("materiel", 60); solde = pay.get("solde", 10)
    tva_note = (d.get("tva_note", "") or "").strip()
    if tva_note.lower().startswith("tva"):
        tva_note = tva_note[3:].lstrip(" :·-").strip()
    links = d.get("links", {}) or {}
    l_sign = links.get("signer", d.get("site_url", "taqinor.ma") + "/signer")
    accepte_nom = (d.get("accepte_par_nom", "") or "").strip()
    date_acc = (d.get("date_acceptation", "") or "").strip()

    # Butane-subsidy punch — a market-level truth (no client m³/jour needed), so
    # it anchors both the full and the degraded page. Gated on the fuel toggle.
    punch_html = (
        '<div class="a4-punch"><b>« Le butane est bon marché tant qu\'il est '
        'subventionné. Le solaire est bon marché pour toujours. »</b> La bonbonne '
        f'de 12 kg ({fmt(b_sub)} MAD) tend vers son vrai prix (~{fmt(b_reel)} MAD) '
        'à mesure que la subvention disparaît — votre facture de carburant va plus '
        'que doubler. Le solaire supprime ce coût et ce risque.</div>'
    ) if show_fuel_flag else ""
    env_html = _env_block(show_env, co2_t, trees, fuel_qty, C, fmt, fmt_dec)

    # ── rentabilité hero (number panel + fuel chart, equal height) ───────────
    # QJR151(a) — l'hypothèse qui produit le volume annuel pompé (donc la
    # facture carburant d'aujourd'hui, l'économie, le cumul 20 ans, le payback
    # et ce graphe) est ÉNONCÉE sous le graphe. Elle était jusqu'ici muette :
    # « estimations basées sur vos données » (page 1) ne dit pas qu'on suppose
    # N jours de pompage par an ni quel ratio pointe/moyenne est retenu, alors
    # qu'un pompage 5 jours/semaine fausse le chiffre d'un facteur ~1,5.
    hyp_days = d.get("pumping_days_per_year")
    hyp_ratio = d.get("peak_to_avg")
    hyp_html = ""
    if hyp_days and hyp_ratio:
        hyp_html = (
            f'<div class="a4-hyp">Hypothèse de calcul : <b>{fmt(hyp_days)} jours '
            f'de pompage par an</b>, à <b>{fmt(round(float(hyp_ratio) * 100))} %</b> '
            'du débit de pointe en moyenne annuelle. Dites-nous vos jours réels '
            'et nous recalculons.</div>')

    renta_html = ""
    if show_fuel and payback:
        pb_bits = []
        if payback_butane:
            pb_bits.append(f"butane <b>{_yrs(payback_butane)} ans</b>")
        if payback_diesel:
            pb_bits.append(f"diesel <b>{_yrs(payback_diesel)} ans</b>")
        twenty = (f'<div class="a4-stat a4-stat-hi"><span>≈ {fmt(savings_20y)} MAD</span>'
                  f'<small>économisés sur 20 ans</small></div>') if savings_20y else ""
        renta_html = f"""
  <div class="a4-renta">
    <div class="a4-card a4-num">
      <div class="a4-h">Rentabilité</div>
      <div class="a4-pb">{_yrs(payback)}<span> ans</span></div>
      <div class="a4-pb-sub">d'amortissement · {" · ".join(pb_bits)}</div>
      <div class="a4-stat"><span>≈ {fmt(annual_saving)} MAD/an</span>
        <small>de {fuel_lbl} économisé</small></div>
      {twenty}
    </div>
    <div class="a4-card a4-fuel">
      <div class="a4-h">Solaire vs butane vs diesel</div>
      <div class="a4-cap">Coût annuel du carburant pour pomper le même volume d'eau</div>
      <img class="a4-fuelimg" src="{charts['fuel']}" alt="Comparatif carburant">
      {hyp_html}
    </div>
  </div>
  <div class="a4-msg">{punch_html}{env_html}</div>
"""
    else:
        # Degraded path — a curve-less (priced) pump has no m³/jour, so we invent
        # NO water/fuel numbers. We still fill the page with the qualitative value
        # of solar pumping + the market figures that legitimately exist.
        # Q3 (fondateur, 20/08/2026) — plus de "coût net après subvention" (le
        # plafond FDA n'est pas confirmable) : mention qualitative, mot pour mot.
        net_line = (f'<div class="a4-qnet">{K.FDA_QUALITATIVE_NOTE}</div>'
                    ) if show_subsidy else ""
        # QJR153 — la ligne « Garanties longues » répliquait les mêmes durées
        # forfaitaires (25/10/5 ans) que la page 3 : elle se DÉRIVE désormais
        # des lignes du devis, et sans aucune garantie au devis elle reste
        # qualitative plutôt que d'annoncer des durées inventées.
        _gar = theme.garanties_du_devis(d)
        _gar_txt = (" · ".join(f"{lbl} {n} {u}" for n, u, lbl in _gar) + "."
                    ) if _gar else ("Garantie constructeur sur chaque "
                                    "composant, détaillée au devis.")
        whys = [
            ("Indépendance énergétique",
             "Votre énergie vient du soleil, pas du marché du carburant."),
            ("Coût de l'eau stable",
             "Pas de facture de carburant qui grimpe d'année en année."),
            ("Zéro entretien carburant",
             "Pas de bonbonnes à transporter, pas de moteur thermique à réviser."),
            ("Garanties longues" if _gar else "Garanties",
             _gar_txt),
        ]
        why_html = "".join(
            f'<div class="a4-why-i"><b>{t}</b><span>{s}</span></div>' for t, s in whys)
        renta_html = f"""
  <div class="a4-renta">
    <div class="a4-card a4-num a4-qnum">
      <div class="a4-h">Zéro carburant</div>
      <div class="a4-q0"><b>0</b><i>carburant</i></div>
      <div class="a4-qsub">Le soleil fait tourner votre pompe — l'eau que vous
        pompez devient gratuite. Plus de bonbonnes à transporter, plus de gasoil
        à acheter, plus de panne sèche en pleine saison.</div>
      {net_line}
    </div>
    <div class="a4-card a4-fuel a4-why">
      <div class="a4-h">Ce que vous y gagnez</div>
      {why_html}
    </div>
  </div>
  <div class="a4-msg">{punch_html}{env_html}</div>
"""

    # ── closing: conditions · étapes · signature (3 equal-height cols) ────────
    paiement = f"{acompte}% commande · {materiel}% matériel · {solde}% service"
    conditions = []
    if validity is not None:
        conditions.append(("Validité", f"{validity} jours"))
    elif valid_until:
        conditions.append(("Validité", f"Jusqu'au {valid_until}"))
    conditions += [("Paiement", paiement),
                   ("TVA", tva_note or "Selon barème"), ("Délai", "selon site & forage"),
                   ("Point d'eau", "Forage/puits avec autorisation ABH valide — "
                    "nous vous orientons pour la démarche")]
    # QRES66 (fondateur, 18/08/2026) — la ligne de conditions « Financement »
    # (CAM Saquii Solaire + FDA) est SUPPRIMÉE. Ne pas la réintroduire.
    cond_html = "".join(
        f'<div class="a4-cr"><span class="a4-ck">{k}</span><span class="a4-cv">{v}</span></div>'
        for k, v in conditions)
    steps = [("1", "Signature", f"+ acompte {acompte}%"), ("2", "Visite technique", "forage & site"),
             ("3", "Installation", "pose & raccordement"), ("4", "Mise en service", "tests + formation")]
    steps_html = "".join(
        f'<div class="a4-step"><span class="a4-sn">{n}</span>'
        f'<span class="a4-stx"><b class="a4-stt">{t}</b>'
        f'<span class="a4-sts">{s}</span></span></div>'
        for n, t, s in steps)
    stamp = (f'<div class="a4-stamp">Accepté par <b>{theme.titlecase_name(accepte_nom)}</b> '
             f'le {date_acc}</div>') if (accepte_nom and date_acc) else ""
    # QJR149 — pastille de validité OMISE quand le nombre de jours est
    # indéterminable (elle imprimait « None jours de validité »).
    cta_validity = (f'<div class="a4-cta-r"><b>{validity}</b>'
                    f'<span>jours de validité</span></div>'
                    ) if validity is not None else ""

    css = f"""
<style>
.a4-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;background:#fff;
  padding:14mm 14mm 0;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a4-root *{{box-sizing:border-box;}}
.a4-kicker{{font-size:7pt;letter-spacing:2.4px;text-transform:uppercase;color:{gold};font-weight:700;}}
.a4-title{{font-family:{f_serif};font-weight:700;font-size:23pt;color:{navy};line-height:1.04;margin:3px 0 14px;}}
.a4-h{{font-family:{f_serif};font-weight:700;font-size:11.5pt;color:{navy};margin-bottom:5px;}}
.a4-cap{{font-size:7.4pt;color:{muted};margin-bottom:5px;line-height:1.3;}}
.a4-card{{border:1px solid {line};border-radius:12px;background:#fff;padding:14px 16px;}}
/* rentabilité */
.a4-renta{{display:flex;gap:12px;align-items:stretch;}}
.a4-num{{flex:0 0 62mm;display:flex;flex-direction:column;border-top:3px solid {green};}}
.a4-fuel{{flex:1 1 0;min-width:0;}}
.a4-pb{{font-family:{f_display};font-size:38pt;color:{green};line-height:.85;letter-spacing:-1px;}}
.a4-pb span{{font-size:15pt;color:{muted};margin-left:4px;}}
.a4-pb-sub{{font-size:8pt;color:{muted};margin:5px 0 9px;}} .a4-pb-sub b{{color:{navy};}}
.a4-stat{{border-top:1px dashed {line};padding-top:8px;margin-top:auto;}}
.a4-stat span{{display:block;font-family:{f_display};font-size:14pt;color:{navy};line-height:1;}}
.a4-stat small{{font-size:7.6pt;color:{muted};}}
.a4-stat-hi{{margin-top:8px;}} .a4-stat-hi span{{color:{gold};font-size:16pt;}}
/* Fixed height: WeasyPrint collapses a width:100%/height:auto <img> to 0 inside
   a flex column. Explicit height + object-fit keeps the chart visible & sharp. */
.a4-fuelimg{{display:block;width:100%;height:30mm;object-fit:contain;
  object-position:left bottom;margin-top:10px;}}
/* QJR151(a) — hypothèse de calcul, sous le graphe. La hauteur du graphe passe
   de 34 à 30 mm pour absorber cette ligne : la carte garde sa hauteur, donc la
   page 4 garde sa mise en page (la .page clippe à 297 mm). */
.a4-hyp{{margin-top:6px;font-size:6.8pt;color:{muted_2};line-height:1.3;}}
.a4-hyp b{{color:{muted};font-weight:700;}}
/* punch + env */
.a4-msg{{display:flex;gap:12px;margin-top:14px;align-items:stretch;}}
.a4-punch{{flex:1 1 0;border-left:4px solid {gold};background:{wash};border-radius:8px;
  padding:10px 14px;font-size:8pt;color:{ink};line-height:1.4;}} .a4-punch b{{color:{navy};}}
.a4-env{{flex:0 0 58mm;display:flex;align-items:flex-start;gap:9px;border:1px solid {green_bg};
  border-left:4px solid {green};border-radius:10px;background:linear-gradient(160deg,{green_bg},#fff 78%);
  padding:10px 13px;font-size:7.8pt;color:{ink};line-height:1.35;}} .a4-env b{{color:{green};}}
.a4-env svg{{width:18px;height:18px;flex-shrink:0;margin-top:1px;}}
/* closing 3 cols */
.a4-close{{display:flex;gap:12px;margin-top:16px;align-items:stretch;}}
.a4-col{{flex:1 1 0;min-width:0;display:flex;flex-direction:column;}}
.a4-col .a4-h{{font-size:10.5pt;}}
.a4-box{{border:1px solid {line};border-radius:12px;background:#fff;padding:12px 14px;flex:1 1 auto;min-height:54mm;}}
.a4-cr{{padding:6px 0;border-bottom:1px dashed {line_soft};}} .a4-cr:last-child{{border-bottom:none;}}
.a4-ck{{display:block;font-size:6.6pt;letter-spacing:.1em;text-transform:uppercase;color:{muted_2};font-weight:700;}}
.a4-cv{{display:block;font-size:8.2pt;color:{ink};margin-top:1px;line-height:1.3;}}
.a4-step{{display:flex;align-items:flex-start;padding:7px 0;border-bottom:1px dashed {line_soft};}}
.a4-step:last-child{{border-bottom:none;}}
.a4-sn{{width:16px;min-width:16px;height:16px;border-radius:50%;background:{navy};color:#fff;
  font-size:7.5pt;font-weight:700;text-align:center;line-height:16px;margin-right:9px;}}
.a4-stx{{display:block;}}
.a4-stt{{display:block;font-size:8.4pt;color:{ink};font-weight:700;}}
.a4-sts{{display:block;font-size:7.4pt;color:{muted};margin-top:1px;line-height:1.3;}}
/* degraded (curve-less pump) value block */
.a4-qnum{{border-top:3px solid {gold};}}
.a4-q0{{white-space:nowrap;line-height:1;margin:2px 0 9px;}}
.a4-q0 b{{font-family:{f_display};font-weight:400;font-size:40pt;color:{gold};}}
.a4-q0 i{{font-style:normal;font-size:11pt;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;color:{gold};margin-left:9px;}}
.a4-qsub{{font-size:8.4pt;color:{ink};line-height:1.45;}}
.a4-qnet{{margin-top:auto;border-top:1px dashed {line};padding-top:8px;font-size:8pt;color:{ink};line-height:1.35;}}
.a4-why-i{{padding:7px 0;border-bottom:1px dashed {line_soft};}}
.a4-why-i:last-child{{border-bottom:none;}}
.a4-why-i b{{display:block;font-size:8.6pt;color:{navy};font-weight:700;}}
.a4-why-i span{{display:block;font-size:7.8pt;color:{muted};margin-top:1px;line-height:1.3;}}
.a4-acc{{border:1.5px solid {navy};border-radius:12px;overflow:hidden;min-height:52mm;}}
.a4-acc-hd{{background:{navy};color:#fff;padding:7px 12px;font-family:{f_serif};font-weight:700;font-size:10.5pt;}}
.a4-sig{{padding:11px 14px 6px;}}
.a4-sig-who{{font-size:7.4pt;color:{navy};font-weight:700;text-transform:uppercase;letter-spacing:.05em;}}
.a4-sig-name{{font-size:8.6pt;color:{ink};font-weight:700;margin-top:1px;}}
/* one clean signing line per signer, with room to sign above it (block layout —
   WeasyPrint did not fill a nested flex column, which collapsed the card) */
.a4-sig-line{{height:1px;background:{muted_2};margin-top:44px;}}
.a4-stamp{{font-size:7.4pt;color:{green};font-weight:700;padding:6px 13px 0;}}
/* CTA */
.a4-cta{{margin-top:16px;background:{gold};border-radius:12px;padding:15px 18px;display:flex;
  align-items:center;justify-content:space-between;gap:16px;}}
.a4-cta-t{{color:{navy_900};font-size:11.5pt;font-weight:700;}}
.a4-cta-s{{color:{navy_900};font-size:8pt;opacity:.8;margin-top:1px;}}
.a4-cta-btn{{display:inline-block;margin-top:9px;background:{navy};color:#fff;font-size:9.5pt;
  font-weight:700;padding:9px 17px;border-radius:8px;text-decoration:none;}}
.a4-cta-btn span{{color:{gold};}}
.a4-cta-r{{flex:0 0 auto;text-align:center;background:{navy};color:#fff;border-radius:10px;
  padding:10px 16px;}}
.a4-cta-r b{{display:block;font-family:{f_display};font-size:17pt;color:#fff;line-height:1;}}
.a4-cta-r span{{display:block;font-size:7pt;color:{gold};letter-spacing:.1em;text-transform:uppercase;margin-top:3px;}}
.a4-note{{margin-top:11px;font-size:8pt;color:{muted_2};font-style:italic;line-height:1.35;}}
</style>
"""
    html = f"""{css}
<div class="a4-root">
  <div class="a4-kicker">Rentabilité & engagement</div>
  <div class="a4-title">Ce que le solaire vous fait gagner</div>
  {renta_html}
  <div class="a4-close">
    <div class="a4-col"><div class="a4-h">Conditions</div>
      <div class="a4-box">{cond_html}</div></div>
    <div class="a4-col"><div class="a4-h">Prochaines étapes</div>
      <div class="a4-box">{steps_html}</div></div>
    <div class="a4-col"><div class="a4-h">Bon pour accord</div>
      <div class="a4-acc">
        <div class="a4-acc-hd">Devis n° {d.get('ref','')}</div>
        <div class="a4-sig"><div class="a4-sig-who">Le client</div>
          <div class="a4-sig-name">{client_full}</div><div class="a4-sig-line"></div></div>
        <div class="a4-sig"><div class="a4-sig-who">TAQINOR</div>
          <div class="a4-sig-name">Cachet & signature</div><div class="a4-sig-line"></div></div>
        {stamp}
      </div></div>
  </div>
  <div class="a4-cta">
    <div><div class="a4-cta-t">Prêt à passer au pompage solaire ?</div>
      <div class="a4-cta-s">Validez votre devis et lancez votre projet d'irrigation.</div>
      <a class="a4-cta-btn" href="{_link(l_sign)}">Signez en ligne <span>→</span> {_disp(l_sign)}</a></div>
    {cta_validity}
  </div>
</div>
"""
    return html


def _env_block(show_env, co2_t, trees, fuel_qty, C, fmt, fmt_dec):
    """CO2SRC (règle « chiffres vérifiés », 2026-08-26) — L'ÉQUIVALENCE EN
    ARBRES EST RETIRÉE de ce bandeau, comme du PDF résidentiel (cover.py +
    options.py) : 22 kg de CO₂ absorbés par arbre et par an est un ordre de
    grandeur de vulgarisation que rien ne source (l'absorption varie d'un
    facteur 5 selon l'essence, l'âge et le climat). Ce qui RESTE est un calcul
    bottom-up : le carburant réellement évité et son CO₂ (facteurs
    gasoil/butane de ``agricole.constants``). ``trees`` reste passé par les
    appelants (donnée interne d'``economics``) mais n'est PLUS imprimé — la
    condition d'affichage ne le regarde donc plus non plus.

    PÉRIMÈTRE de ce changement : les trois surfaces PDF. Le site a fait le même
    retrait de son côté dans le même lot (``apps/web`` n'exporte plus
    ``CO2_KG_PER_TREE_YEAR``), donc plus aucune surface client ne l'imprime."""
    if not (show_env and co2_t):
        return ""
    green = C["green"]
    return (f'<div class="a4-env"><svg viewBox="0 0 24 24" fill="none">'
            f'<path d="M12 21c5-1 8-5 8-11V5l-5 1c-5 1-8 4-8 9 0 .7.1 1.4.3 2" stroke="{green}" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M7 21c0-4 2-7 6-9" stroke="{green}" stroke-width="1.7" stroke-linecap="round"/></svg>'
            f'<div>≈ <b>{fuel_qty}</b> évitées/an · ≈ <b>{fmt_dec(co2_t)} t CO<sub>2</sub></b>'
            f'</div></div>')
