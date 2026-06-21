# flake8: noqa
"""Agricole — PAGE 4 (rentabilité: solaire vs butane vs diesel + payback +
impact) then conditions + « Bon pour accord » signature + CTA. Classes a4-*.
Persuasion blocks toggleable: show_fuel_comparison / show_environmental."""
from __future__ import annotations


def _yrs(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    return str(int(f)) if f == int(f) else f"{f:.1f}".replace(".", ",")


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
    d = ctx["d"]; C = ctx["C"]; fmt = ctx["fmt"]; fmt_dec = ctx["fmt_dec"]
    fonts = ctx["fonts"]; charts = ctx["charts"]

    navy = C["navy"]; gold = C["gold"]; green = C["green"]; green_bg = C["green_bg"]
    water = C["water"]; ink = C["ink"]; muted = C["muted"]; muted_2 = C["muted_2"]
    line = C["line"]; line_soft = C["line_soft"]; wash = C["wash"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]

    has_water = d.get("has_water")
    show_fuel = d.get("show_fuel_comparison", True) and has_water
    show_env = d.get("show_environmental", True) and has_water
    payback = d.get("payback"); payback_butane = d.get("payback_butane")
    payback_diesel = d.get("payback_diesel")
    co2_t = d.get("co2_t") or 0; trees = d.get("trees") or 0
    fuel_qty = d.get("fuel_qty_label") or ""
    b_sub = d.get("butane_12kg_subventionne") or 50
    b_reel = d.get("butane_12kg_reel") or 128

    client_full = theme.titlecase_name(d.get("client_full") or d.get("client_name")) or "Le client"
    validity = d.get("validity_days", 30)
    pay = d.get("payment_terms", {}) or {}
    acompte = pay.get("acompte", 30); materiel = pay.get("materiel", 60); solde = pay.get("solde", 10)
    tva_note = (d.get("tva_note", "") or "").strip()
    if tva_note.lower().startswith("tva"):
        tva_note = tva_note[3:].lstrip(" :·-").strip()
    links = d.get("links", {}) or {}
    l_sign = links.get("signer", d.get("site_url", "taqinor.ma") + "/signer")
    accepte_nom = (d.get("accepte_par_nom", "") or "").strip()
    date_acc = (d.get("date_acceptation", "") or "").strip()

    # ── rentabilité block ────────────────────────────────────────────────────
    renta_html = ""
    if show_fuel and payback:
        pb_bits = []
        if payback_butane:
            pb_bits.append(f"vs butane <b>{_yrs(payback_butane)} ans</b>")
        if payback_diesel:
            pb_bits.append(f"vs diesel <b>{_yrs(payback_diesel)} ans</b>")
        env_line = ""
        if show_env and co2_t and trees:
            env_line = (f'<div class="a4-env">En passant au solaire : ≈ <b>{fuel_qty}</b> évitées/an, '
                        f'soit ≈ <b>{fmt_dec(co2_t)} t CO₂</b> (≈ {fmt(trees)} arbres).</div>')
        renta_html = f"""
  <div class="a4-renta">
    <div class="a4-renta-l">
      <div class="a4-h">Rentabilité</div>
      <div class="a4-pb">{_yrs(payback)} <span>ans</span></div>
      <div class="a4-pb-sub">d'amortissement · {" · ".join(pb_bits)}</div>
      <img class="a4-pbimg" src="{charts['payback']}" alt="Gain cumulé">
    </div>
    <div class="a4-renta-r">
      <div class="a4-h">Solaire vs butane vs diesel</div>
      <div class="a4-cap">Coût annuel du carburant — même volume d'eau</div>
      <img class="a4-fuelimg" src="{charts['fuel']}" alt="Comparatif carburant">
    </div>
  </div>
  <div class="a4-punch"><b>« Le butane est bon marché tant qu'il est subventionné.
    Le solaire est bon marché pour toujours. »</b> La bonbonne de 12 kg ({fmt(b_sub)} MAD)
    tend vers son vrai prix (~{fmt(b_reel)} MAD) à mesure que la subvention disparaît —
    votre facture de pompage va plus que doubler. Le solaire supprime ce coût et ce risque.</div>
  {env_line}
"""
    elif not has_water:
        renta_html = ('<div class="a4-note">Le comparatif carburant et la rentabilité '
                      's\'affichent dès qu\'un débit issu d\'une courbe pompe (m³/jour) est renseigné.</div>')

    # ── conditions + signature ───────────────────────────────────────────────
    paiement = f"{acompte}% commande · {materiel}% matériel · {solde}% mise en service"
    conditions = [("Validité", f"{validity} jours"), ("Paiement", paiement),
                  ("TVA", tva_note or "Selon barème en vigueur"),
                  ("Délai", "selon site & forage")]
    cond_html = "".join(
        f'<div class="a4-cr"><span class="a4-ck">{k}</span><span class="a4-cv">{v}</span></div>'
        for k, v in conditions)
    stamp = ""
    if accepte_nom and date_acc:
        stamp = (f'<div class="a4-stamp">Accepté par <b>{theme.titlecase_name(accepte_nom)}</b> '
                 f'le {date_acc}</div>')

    css = f"""
<style>
.a4-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;background:#fff;
  padding:14mm 14mm 0;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a4-root *{{box-sizing:border-box;}}
.a4-kicker{{font-size:7pt;letter-spacing:2.4px;text-transform:uppercase;color:{gold};font-weight:700;}}
.a4-title{{font-family:{f_serif};font-weight:700;font-size:23pt;color:{navy};line-height:1.04;margin:3px 0 8px;}}
.a4-h{{font-family:{f_serif};font-weight:700;font-size:11pt;color:{navy};margin-bottom:5px;}}
.a4-cap{{font-size:7.4pt;color:{muted};margin-bottom:3px;}}
.a4-renta{{display:flex;gap:12px;align-items:stretch;}}
.a4-renta-l{{flex:0 0 64mm;border:1px solid {line};border-radius:12px;padding:11px 14px;}}
.a4-renta-r{{flex:1 1 0;min-width:0;border:1px solid {line};border-radius:12px;padding:11px 14px;}}
.a4-pb{{font-family:{f_display};font-size:30pt;color:{green};line-height:.9;}}
.a4-pb span{{font-size:13pt;color:{muted};}}
.a4-pb-sub{{font-size:8pt;color:{muted};margin:4px 0 4px;}} .a4-pb-sub b{{color:{navy};}}
.a4-pbimg{{width:100%;height:auto;display:block;margin-top:2px;}}
.a4-fuelimg{{width:100%;height:auto;display:block;}}
.a4-punch{{margin-top:10px;border-left:4px solid {gold};background:{wash};border-radius:8px;
  padding:9px 13px;font-size:8pt;color:{ink};line-height:1.4;}} .a4-punch b{{color:{navy};}}
.a4-env{{display:flex;align-items:center;gap:8px;margin-top:9px;border:1px solid {green_bg};
  border-left:4px solid {green};border-radius:10px;background:linear-gradient(100deg,{green_bg},#fff 72%);
  padding:8px 13px;font-size:8.2pt;color:{ink};}} .a4-env b{{color:{green};}}
.a4-cols{{display:flex;gap:12px;margin-top:13px;align-items:stretch;}}
.a4-col{{flex:1 1 0;min-width:0;}}
.a4-card{{border:1px solid {line};border-radius:12px;background:#fff;padding:11px 14px;height:100%;}}
.a4-cr{{padding:6px 0;border-bottom:1px dashed {line_soft};}} .a4-cr:last-child{{border-bottom:none;}}
.a4-ck{{display:block;font-size:6.8pt;letter-spacing:.1em;text-transform:uppercase;color:{muted_2};font-weight:700;}}
.a4-cv{{display:block;font-size:8.4pt;color:{ink};margin-top:1px;line-height:1.3;}}
.a4-accord{{border:1.5px solid {navy};border-radius:12px;overflow:hidden;height:100%;}}
.a4-accord-hd{{background:{navy};color:#fff;padding:8px 13px;display:flex;align-items:center;justify-content:space-between;}}
.a4-accord-ttl{{font-family:{f_serif};font-weight:700;font-size:11pt;}}
.a4-accord-rf{{font-size:7.6pt;color:#dbe3f0;}}
.a4-sig{{padding:10px 14px 12px;}}
.a4-sig-who{{font-size:7.8pt;color:{navy};font-weight:700;text-transform:uppercase;letter-spacing:.06em;}}
.a4-sig-name{{font-size:9pt;color:{ink};font-weight:700;margin-top:1px;}}
.a4-sig-hint{{font-size:7pt;color:{muted};margin-top:1px;}}
.a4-sig-line{{border-bottom:1px solid {line};height:30px;margin-top:6px;}}
.a4-sig-2{{display:flex;gap:0;}} .a4-sig-2 .a4-sig{{flex:1;}}
.a4-sig-2 .a4-sig:first-child{{border-right:1px dashed {line};}}
.a4-stamp{{font-size:7.6pt;color:{green};font-weight:700;padding:0 14px 8px;}}
.a4-cta{{margin-top:12px;background:{gold};border-radius:11px;padding:12px 18px;display:flex;
  align-items:center;justify-content:space-between;gap:16px;}}
.a4-cta-t{{color:{navy};font-size:11pt;font-weight:700;}}
.a4-cta-s{{color:{navy};font-size:8pt;opacity:.78;margin-top:1px;}}
.a4-cta-btn{{display:inline-block;margin-top:8px;background:{navy};color:#fff;font-size:9.5pt;
  font-weight:700;padding:8px 16px;border-radius:8px;text-decoration:none;}}
.a4-cta-btn span{{color:{gold};}}
.a4-note{{margin-top:11px;font-size:8pt;color:{muted_2};font-style:italic;line-height:1.35;}}
</style>
"""
    html = f"""{css}
<div class="a4-root">
  <div class="a4-kicker">Rentabilité & engagement</div>
  <div class="a4-title">Ce que le solaire vous fait gagner</div>
  {renta_html}
  <div class="a4-cols">
    <div class="a4-col"><div class="a4-h">Conditions</div>
      <div class="a4-card">{cond_html}</div></div>
    <div class="a4-col">
      <div class="a4-accord">
        <div class="a4-accord-hd"><div class="a4-accord-ttl">Bon pour accord</div>
          <div class="a4-accord-rf">Devis n° {d.get('ref','')}</div></div>
        <div class="a4-sig-2">
          <div class="a4-sig"><div class="a4-sig-who">Le client</div>
            <div class="a4-sig-name">{client_full}</div>
            <div class="a4-sig-hint">Nom, date & « Bon pour accord »</div>
            <div class="a4-sig-line"></div></div>
          <div class="a4-sig"><div class="a4-sig-who">TAQINOR</div>
            <div class="a4-sig-name">Cachet & signature</div>
            <div class="a4-sig-hint">Fait foi dès l'acompte</div>
            <div class="a4-sig-line"></div></div>
        </div>
        {stamp}
      </div>
    </div>
  </div>
  <div class="a4-cta">
    <div><div class="a4-cta-t">Prêt à passer au pompage solaire ?</div>
      <div class="a4-cta-s">Validez votre devis et lancez votre projet d'irrigation.</div>
      <a class="a4-cta-btn" href="{_link(l_sign)}">Signez en ligne <span>→</span> {_disp(l_sign)}</a></div>
  </div>
</div>
"""
    return html
