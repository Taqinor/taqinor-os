# flake8: noqa
"""Page 3 — CONFIANCE & ENGAGEMENT (trust + close).

v2 PROTOTYPE page module. Renders the INNER HTML of one A4 page (no .page
wrapper, no footer — the render harness paints those). Returns a single string
with a page-scoped <style> block; every class is prefixed `p3-`.

Design intent: add real trust / social-proof WITHOUT bulking the page — the
proof lives on taqinor.ma and we LINK to it (réalisations, avis, garanties)
rather than stuffing the PDF. We never invent statistics. The page closes with
the conditions, the next steps, and a clean "Bon pour accord" signature block
plus a strong "Signez en ligne" call to action.
"""
from __future__ import annotations


def _link(url: str) -> str:
    """Normalise a bare 'taqinor.ma/...' link into an href."""
    url = (url or "").strip()
    if not url:
        return "#"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url


def _disp(url: str) -> str:
    """Display form of a link (strip scheme, keep host/path)."""
    url = (url or "").strip()
    for pre in ("https://", "http://"):
        if url.startswith(pre):
            url = url[len(pre):]
    return url


def _qr_data_uri(url: str, dark: str) -> str:
    """Premium scannable QR (rounded navy modules + centre TAQINOR logo) as a
    PNG data-URI. Uses `qrcode[pil]` (free, BSD-licensed, no API/cost). Error
    correction H keeps it scannable WITH the centre logo. Returns '' if the lib
    or URL is unavailable, so the textual 'Signez en ligne' link always remains."""
    target = _link(url)
    if not target or target == "#":
        return ""
    try:
        import base64
        import io
        import qrcode
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
        from qrcode.image.styles.colormasks import SolidFillColorMask
        from . import theme
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=16, border=2)
        qr.add_data(target)
        qr.make(fit=True)
        kw = dict(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            color_mask=SolidFillColorMask(front_color=(26, 43, 74),
                                          back_color=(255, 255, 255)))
        logo = theme._LIVE_ASSETS / "logo.png"
        if logo.exists():
            kw["embeded_image_path"] = str(logo)
        img = qr.make_image(**kw)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(
            buf.getvalue()).decode()
    except Exception:
        return ""


def build(ctx) -> str:
    from . import theme

    d = ctx["d"]
    C = ctx["C"]
    # QX4 — identité société (multi-tenant) : marque, bande légale et bloc
    # signature dérivent de l'identité résolue ; repli sur les littéraux
    # Taqinor historiques (byte-identique sans profil enrichi).
    ident = ctx.get("ident") or theme.company_identity(d)
    brand = ident.get("brand_name") or "TAQINOR"

    client_full = (theme.titlecase_name(
        d.get("client_full") or d.get("client_name")) or "Le client")
    validity_days = d.get("validity_days", 30)
    site_url = d.get("site_url", "taqinor.ma")
    links = d.get("links", {}) or {}
    pay = d.get("payment_terms", {}) or {}
    acompte = pay.get("acompte", 30)
    materiel = pay.get("materiel", 60)
    solde = pay.get("solde", 10)
    tva_note = (d.get("tva_note", "") or "").strip()
    # The builder's note already starts with "TVA :"; drop it so it doesn't
    # double the "TVA" key in the conditions table.
    low = tva_note.lower()
    if low.startswith("tva"):
        tva_note = tva_note[3:].lstrip(" :·-").strip()

    l_real = links.get("realisations", site_url + "/realisations")
    # QK5 — /avis n'existe pas sur taqinor.ma : repli sur /realisations (page
    # réelle des réalisations clients), jamais un lien 404 sur un PDF client.
    l_avis = links.get("avis", site_url + "/realisations")
    l_gar = links.get("garanties", site_url + "/garanties")
    l_sign = links.get("signer", site_url + "/signer")

    # ── QX7e — puces de valeur : les marques d'équipement viennent des VRAIES
    # lignes du devis (item['marque']), jamais d'une liste boilerplate. Repli
    # « équipements certifiés IEC » quand aucune marque n'est portée par les
    # lignes. Les figures marketing (« Pourquoi … ») sont un texte éditable par
    # la société via doc_texts.trust_values (repli sur les puces par défaut).
    _seen, _brands = set(), []
    for _it in (d.get("avec_items") or []) + (d.get("sans_items") or []):
        _m = (_it.get("marque") or "").strip()
        if _m and _m.lower() not in _seen:
            _seen.add(_m.lower())
            _brands.append(_m)
    _brand_line = (
        "Équipements premium certifiés — " + " · ".join(_brands[:4])
        if _brands else "Équipements premium certifiés IEC")
    values = [
        "Ingénieurs spécialisés en énergie solaire",
        _brand_line,
        "Suivi de production en temps réel 24/7",
    ]
    # Texte éditable par la société (doc_texts.trust_values) : liste de puces qui
    # remplace la valeur par défaut ci-dessus quand elle est renseignée.
    _doc_texts = d.get("doc_texts") or {}
    _tv = _doc_texts.get("trust_values")
    if isinstance(_tv, (list, tuple)) and any(str(x).strip() for x in _tv):
        values = [str(x).strip() for x in _tv if str(x).strip()]
    values_html = "".join(
        f'<div class="p3-val"><span class="p3-dot"></span>'
        f'<span class="p3-val-t">{v}</span></div>'
        for v in values
    )

    # ── Garantie badges ─────────────────────────────────────────────────────
    badges = [
        ("10", "ans", "Onduleur"),
        ("12", "ans", "Panneaux (produit)"),
        ("20", "ans", "Structure"),
        ("30", "ans", "Performance 87,4 %"),
    ]
    badges_html = "".join(
        f'<div class="p3-badge"><div class="p3-badge-n">{n}'
        f'<span class="p3-badge-u">{u}</span></div>'
        f'<div class="p3-badge-l">{label}</div></div>'
        for n, u, label in badges
    )

    # ── Trust strip — LINK out, don't dump ──────────────────────────────────
    # QK5 — le libellé « avis clients » renvoie désormais vers /realisations
    # (page réelle des réalisations clients) : on ne fabrique jamais d'avis, on
    # renvoie vers des projets vérifiables. Libellé aligné sur la destination.
    trust_items = [
        ("Nos réalisations", l_real),
        ("Avis & réalisations clients", l_avis),
        ("Garanties &amp; certifications", l_gar),
    ]
    trust_html = "".join(
        f'<a class="p3-trust-item" href="{_link(url)}">'
        f'<span class="p3-trust-t">{title}</span>'
        f'<span class="p3-trust-u">{_disp(url)} &rsaquo;</span></a>'
        for title, url in trust_items
    )

    # ── Conditions (compact) ────────────────────────────────────────────────
    paiement = (f"{acompte}% à la commande &middot; {materiel}% à la réception "
                f"du matériel &middot; {solde}% à la mise en service")
    conditions = [
        ("Validité de l'offre", f"{validity_days} jours"),
        ("Paiement", paiement),
        ("TVA", tva_note or "Selon barème en vigueur"),
        ("Délai d'installation", "7 à 14 jours ouvrés"),
    ]
    # QF3 — « Comment nous calculons vos économies » : méthode + exemple chiffré
    # compact, ajoutés comme une ligne de conditions (aucune hauteur de bloc en
    # plus, la page reste à 3 pages). Le texte vient du builder (une source).
    sm = d.get("savings_method") or {}
    sm_line = (sm.get("ligne_methode") or "").strip()
    sm_ex = (sm.get("exemple") or "").strip()
    sm_approx = " (approximatif)" if sm.get("approximatif") else ""
    if sm_line:
        _v = sm_line
        if sm_ex:
            _v += f' <b>{sm_ex}{sm_approx}</b>'
        conditions.append(("Comment nous calculons vos économies", _v))
    # QK4 — « Nos hypothèses » : les hypothèses derrière les économies (tarif,
    # source du barème, autoconsommation-first loi 82-21, base de production),
    # ajoutées comme une ligne de conditions (aucune hauteur de bloc en plus,
    # la page reste à 3 pages). Le texte vient du builder (une source).
    hyp = d.get("hypotheses") or {}
    hyp_items = [str(i).strip() for i in (hyp.get("items") or []) if str(i).strip()]
    if hyp_items:
        conditions.append(
            (hyp.get("titre") or "Nos hypothèses",
             " &middot; ".join(hyp_items)))
    # QK3 — financement (indicatif) : mensualité + programme, ajouté comme ligne
    # de conditions (aucune hauteur de bloc en plus → la page reste à 3 pages).
    # Le bloc vient du builder (QJ12) ; jamais de prix d'achat/marge.
    fin = d.get("financing") or {}
    fin_credit = fin.get("credit") or {}
    if fin.get("indicatif") and fin_credit.get("mensualite"):
        _mens = int(round(fin_credit["mensualite"]))
        _duree_ans = round((fin_credit.get("duree_mois") or 0) / 12)
        _prog = fin_credit.get("programme_nom") or "crédit vert"
        _fin_v = (
            f"À partir de ≈ {_mens:,}".replace(",", " ")
            + f" MAD/mois sur {_duree_ans} ans ({_prog}) — indicatif, à "
            "confirmer avec votre banque.")
        conditions.append(("Financement possible", _fin_v))
    # QG7 — contact du conseiller (créateur du devis) : nom + tél, ajouté comme
    # ligne de conditions (données seulement). Repli société géré côté builder.
    seller = d.get("seller") or {}
    _s_nom = (seller.get("nom") or "").strip()
    if _s_nom:
        _s_tel = (seller.get("telephone") or "").strip()
        _s_v = _s_nom + (f" &middot; {_s_tel}" if _s_tel else "")
        conditions.append(("Votre conseiller", _s_v))
    cond_html = "".join(
        f'<div class="p3-cond-row"><span class="p3-cond-k">{k}</span>'
        f'<span class="p3-cond-v">{v}</span></div>'
        for k, v in conditions
    )

    # ── Next steps ──────────────────────────────────────────────────────────
    steps = [
        ("1", "Signature du devis", f"+ acompte {acompte}%"),
        ("2", "Visite technique", "sous 48–72 h"),
        ("3", "Installation", "7–14 jours"),
        ("4", "Mise en service", "tests + formation"),
    ]
    steps_html = "".join(
        f'<div class="p3-step"><div class="p3-step-n">{n}</div>'
        f'<div class="p3-step-t">{t}</div>'
        f'<div class="p3-step-s">{s}</div></div>'
        for n, t, s in steps
    )

    # QX5 — « Option choisie » : deux cases seulement pour un vrai devis à deux
    # options ; mono-option → on nomme l'unique option (aucune case fantôme).
    _deux = bool(d.get("deux_options", True))
    _avec_ok = bool(d.get("avec_ok", True))
    if _deux:
        accord_opt_html = (
            'Option choisie :'
            '<span class="p3-box"></span> Sans batterie'
            '<span class="p3-box"></span> Avec batterie')
    else:
        accord_opt_html = ("Avec batterie" if _avec_ok else "Sans batterie")

    # Scan-to-sign QR (degrades to the text link if qrcode is unavailable).
    qr_uri = _qr_data_uri(l_sign, C["navy"])
    qr_html = (
        f'<div class="p3-cta-qr">'
        f'<img src="{qr_uri}" alt="QR — signer en ligne">'
        f'<span class="p3-cta-qr-t">Scannez pour signer</span></div>'
        if qr_uri else "")

    # Legal identifier band — real company data (RC/ICE/capital from taqinor.ma).
    # SCA27 (fix règle-#4-permis) — pour un TENANT (profil au nom non-TAQINOR),
    # la bande se compose de SES identifiants (nom/RC/ICE/email/téléphone/site,
    # champs absents omis — capital et gérant n'ont pas de champ profil). Le
    # littéral fondateur reste le repli byte-identique (profil vide OU marque
    # TAQINOR — même sémantique par-la-donnée que _footer_brand/DC1).
    from html import escape as _esc
    ent = d.get("entreprise") or {}
    ent_nom = (ent.get("nom") or "").strip()
    if ent_nom and "TAQINOR" not in ent_nom.upper():
        parts = [f"<b>{_esc(ent_nom)}</b>"]
        if (ent.get("rc") or "").strip():
            parts.append("RC " + _esc(ent["rc"].strip()))
        if (ent.get("ice") or "").strip():
            parts.append("ICE " + _esc(ent["ice"].strip()))
        if (ent.get("email") or "").strip():
            parts.append(_esc(ent["email"].strip()))
        if (ent.get("telephone") or "").strip():
            parts.append(_esc(ent["telephone"].strip()))
        _site_tenant = (d.get("site_url") or "").strip()
        if _site_tenant and "taqinor" not in _site_tenant.lower():
            parts.append(_esc(_site_tenant))
        legal = " &middot; ".join(parts)
    else:
        legal = (
            '<b>TAQINOR Solutions SARLAU</b> au capital de 100 000,00 MAD'
            ' &middot; RC 691213 — Tribunal de Commerce de Casablanca'
            ' &middot; ICE 003799642000067 &middot; Gérant : M. Reda Kasri'
            ' &middot; contact@taqinor.com &middot; +212 6 61 85 04 10'
            ' &middot; taqinor.ma'
        )

    return f"""
<style>
/* Page-3 vertical rhythm — the wrap reserves a generous bottom band so the
   composition breathes evenly top-to-bottom and the legal fine print lands as
   an intentional margin ~8mm above the fixed 13mm footer (no awkward void). */
.p3-wrap {{ padding:13mm 14mm 0 14mm; }}
.p3-kicker {{ font-size:8.5pt; letter-spacing:.24em; text-transform:uppercase;
  color:{C['gold']}; font-weight:700; }}
.p3-title {{ font-family:{ctx['fonts']['serif']}; font-weight:700;
  font-size:26pt; color:{C['navy']}; line-height:1.04; margin:4px 0 0;
  letter-spacing:-.3px; }}

/* Value points row */
.p3-values {{ display:flex; gap:9px; margin:12px 0 14px; }}
.p3-val {{ flex:1; display:flex; align-items:flex-start; gap:7px;
  background:{C['wash']}; border:1px solid {C['line_soft']}; border-radius:10px;
  padding:11px 12px; }}
.p3-dot {{ width:7px; height:7px; min-width:7px; border-radius:50%;
  background:{C['gold']}; margin-top:3px; }}
.p3-val-t {{ font-size:8.5pt; color:{C['ink']}; font-weight:500; line-height:1.3; }}

/* Section heading */
.p3-h {{ font-family:{ctx['fonts']['serif']}; font-weight:700; font-size:12pt;
  color:{C['navy']}; margin:0 0 8px; }}
.p3-block {{ margin-bottom:14px; }}

/* Garantie badges */
.p3-badges {{ display:flex; gap:9px; }}
.p3-badge {{ flex:1; text-align:center; border:1px solid {C['line']};
  border-top:3px solid {C['gold']}; border-radius:11px; padding:14px 4px 12px;
  background:{C['paper']}; }}
.p3-badge-n {{ font-family:{ctx['fonts']['display']}; font-size:26pt;
  color:{C['navy']}; line-height:1; }}
.p3-badge-u {{ font-family:{ctx['fonts']['sans']}; font-size:8pt;
  color:{C['gold']}; font-weight:700; margin-left:3px; }}
.p3-badge-l {{ font-size:7.6pt; color:{C['muted']}; font-weight:600;
  margin-top:6px; letter-spacing:.02em; }}

/* Trust strip (navy band, links out) */
.p3-trust {{ background:{C['navy']}; border-radius:12px; padding:15px 16px;
  display:flex; gap:12px; }}
.p3-trust-item {{ flex:1; text-decoration:none; display:block;
  border-right:1px solid rgba(255,255,255,.14); padding-right:12px; }}
.p3-trust-item:last-child {{ border-right:none; padding-right:0; }}
.p3-trust-t {{ display:block; color:#fff; font-size:8.7pt; font-weight:700;
  margin-bottom:3px; }}
.p3-trust-u {{ display:block; color:{C['gold']}; font-size:7.8pt;
  font-weight:600; }}

/* Conditions + steps side by side */
.p3-cols {{ display:flex; gap:12px; align-items:flex-start; }}
.p3-col {{ flex:1; }}
.p3-card {{ border:1px solid {C['line']}; border-radius:11px;
  background:{C['paper']}; padding:12px 14px; }}
.p3-cond-row {{ padding:7px 0; border-bottom:1px dashed {C['line_soft']}; }}
.p3-cond-row:last-child {{ border-bottom:none; padding-bottom:1px; }}
.p3-cond-row:first-child {{ padding-top:1px; }}
.p3-cond-k {{ display:block; font-size:7pt; letter-spacing:.1em;
  text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
  margin-bottom:2px; }}
.p3-cond-v {{ display:block; font-size:8.4pt; color:{C['ink']};
  font-weight:500; line-height:1.3; }}

/* Steps mirror the Conditions rhythm (padded rows + dashed dividers) AND the 4
   rows flex-divide the card's full height, so the two cards are equal height
   with the steps evenly filling — no floating dots, no void, bottoms aligned. */
.p3-steps {{ display:block; }}
.p3-step {{ display:flex; align-items:center; padding:15px 0;
  border-bottom:1px dashed {C['line_soft']}; }}
.p3-step:first-child {{ padding-top:2px; }}
.p3-step:last-child {{ border-bottom:none; padding-bottom:2px; }}
.p3-step-n {{ width:20px; min-width:20px; height:20px; border-radius:50%;
  background:{C['navy']}; color:#fff; font-size:8pt; font-weight:700;
  text-align:center; line-height:20px; margin-right:12px; }}
.p3-step-t {{ font-size:8.7pt; color:{C['ink']}; font-weight:700; }}
.p3-step-s {{ font-size:8pt; color:{C['muted']}; margin-left:auto;
  padding-left:8px; }}

/* Bon pour accord */
.p3-accord {{ border:1.5px solid {C['navy']}; border-radius:13px;
  margin-bottom:13px; overflow:hidden; }}
.p3-accord-hd {{ background:{C['navy']}; color:#fff; padding:11px 16px;
  display:flex; align-items:center; justify-content:space-between; }}
.p3-accord-ttl {{ font-family:{ctx['fonts']['serif']}; font-weight:700;
  font-size:11.5pt; letter-spacing:.02em; }}
.p3-accord-opt {{ font-size:8.2pt; color:#dbe3f0; }}
.p3-box {{ display:inline-block; width:9px; height:9px; border:1.4px solid #fff;
  border-radius:2px; margin:0 4px 0 10px; vertical-align:-1px; }}
.p3-accord-bd {{ display:flex; }}
.p3-sig {{ flex:1; padding:13px 18px 15px; }}
.p3-sig:first-child {{ border-right:1px dashed {C['line']}; }}
.p3-sig-who {{ font-size:8.2pt; color:{C['navy']}; font-weight:700;
  text-transform:uppercase; letter-spacing:.06em; }}
.p3-sig-name {{ font-size:9.2pt; color:{C['ink']}; font-weight:700;
  margin-top:2px; }}
.p3-sig-hint {{ font-size:7.4pt; color:{C['muted']}; margin-top:3px; }}
.p3-sig-line {{ border-bottom:1px solid {C['line']}; height:34px; margin-top:8px; }}

/* CTA — gold close band with scan-to-sign QR */
.p3-cta {{ background:{C['gold']}; border-radius:12px;
  padding:15px 20px; display:flex; align-items:center; gap:18px;
  justify-content:space-between; }}
.p3-cta-l {{ flex:1 1 auto; min-width:0; }}
.p3-cta-t {{ color:{C['navy']}; font-size:11.5pt; font-weight:700;
  letter-spacing:-.1px; }}
.p3-cta-s {{ color:{C['navy']}; font-size:8pt; opacity:.78; margin-top:2px; }}
.p3-cta-btn {{ display:inline-block; margin-top:11px; background:{C['navy']};
  color:#fff; font-size:9.5pt; font-weight:700; padding:9px 17px;
  border-radius:9px; white-space:nowrap; text-decoration:none; }}
.p3-cta-btn span {{ color:{C['gold']}; }}
.p3-cta-qr {{ flex:0 0 auto; display:flex; flex-direction:column;
  align-items:center; padding-left:18px;
  border-left:1.5px solid rgba(26,43,74,.22); }}
.p3-cta-qr img {{ flex:0 0 auto; width:20mm; height:20mm; display:block;
  background:#fff; border-radius:9px; padding:5px; margin:0 0 6px 0; }}
.p3-cta-qr-t {{ flex:0 0 auto; font-size:7.8pt; font-weight:700;
  color:{C['navy']}; line-height:1.25; letter-spacing:.01em;
  text-align:center; white-space:nowrap; }}

/* Legal identifier band — refined fine print, intentional margin above footer */
.p3-legal {{ margin-top:13px; padding-top:8px; border-top:1px solid {C['line']};
  font-size:6.7pt; color:{C['muted_2']}; text-align:center; line-height:1.6;
  letter-spacing:.015em; }}
.p3-legal b {{ color:{C['navy']}; font-weight:700; }}
</style>

<div class="p3-wrap">
  <div class="p3-kicker">Confiance &amp; Engagement</div>
  <div class="p3-title">Pourquoi {brand}</div>

  <div class="p3-values">{values_html}</div>

  <div class="p3-block">
    <div class="p3-h">Nos garanties</div>
    <div class="p3-badges">{badges_html}</div>
  </div>

  <div class="p3-block">
    <div class="p3-h">La preuve, en ligne</div>
    <div class="p3-trust">{trust_html}</div>
  </div>

  <div class="p3-cols p3-block">
    <div class="p3-col">
      <div class="p3-h">Conditions</div>
      <div class="p3-card">{cond_html}</div>
    </div>
    <div class="p3-col">
      <div class="p3-h">Prochaines étapes</div>
      <div class="p3-card"><div class="p3-steps">{steps_html}</div></div>
    </div>
  </div>

  <div class="p3-accord">
    <div class="p3-accord-hd">
      <div class="p3-accord-ttl">Bon pour accord</div>
      <div class="p3-accord-opt">{accord_opt_html}</div>
    </div>
    <div class="p3-accord-bd">
      <div class="p3-sig">
        <div class="p3-sig-who">Le client</div>
        <div class="p3-sig-name">{client_full}</div>
        <div class="p3-sig-hint">Nom, date, mention « Bon pour accord » &amp; signature</div>
        <div class="p3-sig-line"></div>
      </div>
      <div class="p3-sig">
        <div class="p3-sig-who">{brand}</div>
        <div class="p3-sig-name">Cachet &amp; signature</div>
        <div class="p3-sig-hint">Le devis fait foi dès réception de l'acompte</div>
        <div class="p3-sig-line"></div>
      </div>
    </div>
  </div>

  <div class="p3-cta">
    <div class="p3-cta-l">
      <div class="p3-cta-t">Prêt à passer au solaire ?</div>
      <div class="p3-cta-s">Validez votre devis en quelques clics, sans vous déplacer.</div>
      <a class="p3-cta-btn" href="{_link(l_sign)}">Signez en ligne <span>&rarr;</span> {_disp(l_sign)}</a>
    </div>
    {qr_html}
  </div>

  <div class="p3-legal">{legal}</div>
</div>
"""
