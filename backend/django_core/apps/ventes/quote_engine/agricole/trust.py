# flake8: noqa
"""Agricole — PAGE 5 (trust + close: garanties, accompagnement subvention/ABH,
conditions, prochaines étapes, signature). Returns INNER HTML. Classes a5-*."""
from __future__ import annotations


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
    d = ctx["d"]; C = ctx["C"]; fonts = ctx["fonts"]
    navy = C["navy"]; gold = C["gold"]; green = C["green"]; water = C["water"]
    ink = C["ink"]; muted = C["muted"]; muted_2 = C["muted_2"]; line = C["line"]
    line_soft = C["line_soft"]; wash = C["wash"]; green_bg = C["green_bg"]
    f_display = fonts["display"]; f_serif = fonts["serif"]; f_sans = fonts["sans"]

    client_full = theme.titlecase_name(d.get("client_full") or d.get("client_name")) or "Le client"
    validity = d.get("validity_days", 30)
    site_url = d.get("site_url", "taqinor.ma")
    links = d.get("links", {}) or {}
    pay = d.get("payment_terms", {}) or {}
    acompte = pay.get("acompte", 30); materiel = pay.get("materiel", 60); solde = pay.get("solde", 10)
    tva_note = (d.get("tva_note", "") or "").strip()
    if tva_note.lower().startswith("tva"):
        tva_note = tva_note[3:].lstrip(" :·-").strip()
    show_subsidy = d.get("show_subsidy", True)
    accepte_nom = (d.get("accepte_par_nom", "") or "").strip()
    date_acc = (d.get("date_acceptation", "") or "").strip()

    l_real = links.get("realisations", site_url + "/realisations")
    l_avis = links.get("avis", site_url + "/avis")
    l_gar = links.get("garanties", site_url + "/garanties")
    l_sign = links.get("signer", site_url + "/signer")

    values = [
        "Ingénieurs spécialisés en pompage solaire & irrigation",
        "Pompes + variateurs VEICHI · panneaux premium certifiés",
        "Mise en service, formation et suivi du système",
    ]
    values_html = "".join(
        f'<div class="a5-val"><span class="a5-dot"></span><span>{v}</span></div>'
        for v in values)

    badges = [("25", "ans", "Panneaux (perf.)"), ("5", "ans", "Variateur"),
              ("2", "ans", "Pompe"), ("10", "ans", "Structure")]
    badges_html = "".join(
        f'<div class="a5-badge"><div class="a5-bn">{n}<span>{u}</span></div>'
        f'<div class="a5-bl">{l}</div></div>' for n, u, l in badges)

    trust_items = [("Nos réalisations", l_real), ("Avis clients", l_avis),
                   ("Garanties & certifications", l_gar)]
    trust_html = "".join(
        f'<a class="a5-trust-item" href="{_link(u)}"><span class="a5-tt">{t}</span>'
        f'<span class="a5-tu">{_disp(u)} ›</span></a>' for t, u in trust_items)

    acc_html = ""
    if show_subsidy:
        acc_html = ('<div class="a5-acc"><div class="a5-acc-t">Nous vous accompagnons</div>'
                    '<div class="a5-acc-s">Montage du dossier de <b>subvention FDA (30 %)</b> '
                    'auprès de la DPA/ORMVA, et orientation pour l\'<b>autorisation ABH</b> de '
                    'votre point d\'eau (forage/puits).</div></div>')

    paiement = (f"{acompte}% à la commande · {materiel}% à la réception du matériel "
                f"· {solde}% à la mise en service")
    conditions = [
        ("Validité de l'offre", f"{validity} jours"),
        ("Paiement", paiement),
        ("TVA", tva_note or "Selon barème en vigueur"),
        ("Délai d'installation", "selon site & forage"),
    ]
    cond_html = "".join(
        f'<div class="a5-cr"><span class="a5-ck">{k}</span><span class="a5-cv">{v}</span></div>'
        for k, v in conditions)

    steps = [("1", "Signature du devis", f"+ acompte {acompte}%"),
             ("2", "Visite technique", "forage & site"),
             ("3", "Installation", "pose & raccordement"),
             ("4", "Mise en service", "tests + formation")]
    steps_html = "".join(
        f'<div class="a5-step"><div class="a5-sn">{n}</div>'
        f'<div class="a5-st">{t}</div><div class="a5-ss">{s}</div></div>'
        for n, t, s in steps)

    stamp = ""
    if accepte_nom and date_acc:
        stamp = (f'<div class="a5-stamp">Accepté par <b>{theme.titlecase_name(accepte_nom)}</b> '
                 f'le {date_acc}</div>')

    css = f"""
<style>
.a5-root{{font-family:{f_sans};color:{ink};width:210mm;height:297mm;background:#fff;
  padding:14mm 14mm 0;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.a5-root *{{box-sizing:border-box;}}
.a5-kicker{{font-size:7pt;letter-spacing:2.4px;text-transform:uppercase;color:{gold};font-weight:700;}}
.a5-title{{font-family:{f_serif};font-weight:700;font-size:23pt;color:{navy};line-height:1.04;margin:3px 0 0;}}
.a5-values{{display:flex;gap:8px;margin:12px 0 14px;}}
.a5-val{{flex:1;display:flex;align-items:flex-start;gap:6px;background:{wash};
  border:1px solid {line_soft};border-radius:9px;padding:9px 10px;font-size:8.2pt;color:{ink};line-height:1.25;}}
.a5-dot{{width:7px;height:7px;min-width:7px;border-radius:50%;background:{gold};margin-top:3px;}}
.a5-h{{font-family:{f_serif};font-weight:700;font-size:11.5pt;color:{navy};margin:0 0 7px;}}
.a5-block{{margin-bottom:15px;}}
.a5-badges{{display:flex;gap:8px;}}
.a5-badge{{flex:1;text-align:center;border:1px solid {line};border-top:3px solid {gold};
  border-radius:10px;padding:11px 4px 10px;}}
.a5-bn{{font-family:{f_display};font-size:23pt;color:{navy};line-height:1;}}
.a5-bn span{{font-size:8pt;color:{gold};font-weight:700;margin-left:3px;}}
.a5-bl{{font-size:7.4pt;color:{muted};font-weight:600;margin-top:4px;}}
.a5-trust{{background:{navy};border-radius:11px;padding:13px 14px;display:flex;gap:10px;}}
.a5-trust-item{{flex:1;text-decoration:none;border-right:1px solid rgba(255,255,255,.14);padding-right:10px;}}
.a5-trust-item:last-child{{border-right:none;}}
.a5-tt{{display:block;color:#fff;font-size:8.6pt;font-weight:700;margin-bottom:2px;}}
.a5-tu{{display:block;color:{gold};font-size:7.8pt;font-weight:600;}}
.a5-acc{{margin-top:11px;border:1px solid #BFE6CB;border-left:4px solid {green};border-radius:11px;
  background:linear-gradient(100deg,{green_bg},#fff 72%);padding:10px 14px;}}
.a5-acc-t{{font-size:8.6pt;font-weight:700;color:{C['green_700']};}}
.a5-acc-s{{font-size:8pt;color:{ink};margin-top:3px;line-height:1.35;}} .a5-acc-s b{{color:{C['green_700']};}}
.a5-cols{{display:flex;gap:10px;}}
.a5-col{{flex:1;}}
.a5-card{{border:1px solid {line};border-radius:10px;background:#fff;padding:10px 12px;height:100%;}}
.a5-cr{{padding:7px 0;border-bottom:1px dashed {line_soft};}}
.a5-cr:last-child{{border-bottom:none;}}
.a5-ck{{display:block;font-size:7pt;letter-spacing:.1em;text-transform:uppercase;color:{muted_2};font-weight:700;margin-bottom:2px;}}
.a5-cv{{display:block;font-size:8.4pt;color:{ink};line-height:1.3;}}
.a5-steps{{display:flex;flex-direction:column;gap:9px;}}
.a5-step{{display:flex;align-items:baseline;gap:8px;}}
.a5-sn{{width:18px;min-width:18px;height:18px;border-radius:50%;background:{navy};color:#fff;
  font-size:8pt;font-weight:700;text-align:center;line-height:18px;}}
.a5-st{{font-size:8.6pt;color:{ink};font-weight:700;}}
.a5-ss{{font-size:8pt;color:{muted};margin-left:auto;}}
.a5-accord{{border:1.5px solid {navy};border-radius:12px;margin-top:4px;overflow:hidden;}}
.a5-accord-hd{{background:{navy};color:#fff;padding:9px 14px;display:flex;align-items:center;justify-content:space-between;}}
.a5-accord-ttl{{font-family:{f_serif};font-weight:700;font-size:11.5pt;}}
.a5-accord-bd{{display:flex;}}
.a5-sig{{flex:1;padding:13px 16px 16px;}}
.a5-sig:first-child{{border-right:1px dashed {line};}}
.a5-sig-who{{font-size:8.2pt;color:{navy};font-weight:700;text-transform:uppercase;letter-spacing:.06em;}}
.a5-sig-name{{font-size:9.2pt;color:{ink};font-weight:700;margin-top:1px;}}
.a5-sig-hint{{font-size:7.4pt;color:{muted};margin-top:2px;}}
.a5-sig-line{{border-bottom:1px solid {line};height:40px;margin-top:8px;}}
.a5-stamp{{font-size:7.8pt;color:{green};font-weight:700;padding:6px 16px 0;}}
.a5-cta{{margin-top:13px;background:{gold};border-radius:11px;padding:13px 18px;display:flex;
  align-items:center;justify-content:space-between;gap:18px;}}
.a5-cta-t{{color:{navy};font-size:11pt;font-weight:700;}}
.a5-cta-s{{color:{navy};font-size:8pt;opacity:.78;margin-top:1px;}}
.a5-cta-btn{{display:inline-block;margin-top:9px;background:{navy};color:#fff;font-size:9.5pt;
  font-weight:700;padding:8px 16px;border-radius:8px;text-decoration:none;}}
.a5-cta-btn span{{color:{gold};}}
</style>

<div class="a5-root">
  <div class="a5-kicker">Confiance & Engagement</div>
  <div class="a5-title">Pourquoi TAQINOR</div>
  <div class="a5-values">{values_html}</div>

  <div class="a5-block"><div class="a5-h">Nos garanties</div>
    <div class="a5-badges">{badges_html}</div></div>

  <div class="a5-block"><div class="a5-h">La preuve, en ligne</div>
    <div class="a5-trust">{trust_html}</div>
    {acc_html}
  </div>

  <div class="a5-cols a5-block">
    <div class="a5-col"><div class="a5-h">Conditions</div>
      <div class="a5-card">{cond_html}</div></div>
    <div class="a5-col"><div class="a5-h">Prochaines étapes</div>
      <div class="a5-card"><div class="a5-steps">{steps_html}</div></div></div>
  </div>

  <div class="a5-accord">
    <div class="a5-accord-hd"><div class="a5-accord-ttl">Bon pour accord</div>
      <div style="font-size:8pt;color:#dbe3f0;">Devis n° {d.get('ref','')}</div></div>
    <div class="a5-accord-bd">
      <div class="a5-sig"><div class="a5-sig-who">Le client</div>
        <div class="a5-sig-name">{client_full}</div>
        <div class="a5-sig-hint">Nom, date, mention « Bon pour accord » & signature</div>
        <div class="a5-sig-line"></div></div>
      <div class="a5-sig"><div class="a5-sig-who">TAQINOR</div>
        <div class="a5-sig-name">Cachet & signature</div>
        <div class="a5-sig-hint">Le devis fait foi dès réception de l'acompte</div>
        <div class="a5-sig-line"></div></div>
    </div>
    {stamp}
  </div>

  <div class="a5-cta">
    <div><div class="a5-cta-t">Prêt à passer au pompage solaire ?</div>
      <div class="a5-cta-s">Validez votre devis et lancez votre projet d'irrigation.</div>
      <a class="a5-cta-btn" href="{_link(l_sign)}">Signez en ligne <span>→</span> {_disp(l_sign)}</a></div>
  </div>
</div>
"""
    return css
