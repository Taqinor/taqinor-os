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


def build(ctx) -> str:
    d = ctx["d"]
    C = ctx["C"]

    client_full = d.get("client_full") or d.get("client_name") or "Le client"
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
    l_avis = links.get("avis", site_url + "/avis")
    l_gar = links.get("garanties", site_url + "/garanties")
    l_sign = links.get("signer", site_url + "/signer")

    # ── Value points (no invented numbers) ──────────────────────────────────
    values = [
        "Ingénieurs spécialisés en énergie solaire",
        "Équipements premium certifiés — Canadian Solar · Huawei · Deye",
        "Suivi de production en temps réel 24/7",
    ]
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
    trust_items = [
        ("Nos réalisations", l_real),
        ("Avis clients vérifiés", l_avis),
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
        ("Tarifs de référence", "barème ONEE / SRM"),
    ]
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

    return f"""
<style>
.p3-wrap {{ padding:15mm 14mm 0 14mm; }}
.p3-kicker {{ font-size:8.5pt; letter-spacing:.22em; text-transform:uppercase;
  color:{C['gold']}; font-weight:700; }}
.p3-title {{ font-family:{ctx['fonts']['serif']}; font-weight:700;
  font-size:22pt; color:{C['navy']}; line-height:1.05; margin:3px 0 0; }}

/* Value points row */
.p3-values {{ display:flex; gap:8px; margin:12px 0 15px; }}
.p3-val {{ flex:1; display:flex; align-items:flex-start; gap:6px;
  background:{C['wash']}; border:1px solid {C['line_soft']}; border-radius:9px;
  padding:9px 10px; }}
.p3-dot {{ width:7px; height:7px; min-width:7px; border-radius:50%;
  background:{C['gold']}; margin-top:3px; }}
.p3-val-t {{ font-size:8.4pt; color:{C['ink']}; font-weight:500; line-height:1.25; }}

/* Section heading */
.p3-h {{ font-family:{ctx['fonts']['serif']}; font-weight:700; font-size:11.5pt;
  color:{C['navy']}; margin:0 0 7px; }}
.p3-block {{ margin-bottom:15px; }}

/* Garantie badges */
.p3-badges {{ display:flex; gap:8px; }}
.p3-badge {{ flex:1; text-align:center; border:1px solid {C['line']};
  border-top:3px solid {C['gold']}; border-radius:10px; padding:11px 4px 10px;
  background:{C['paper']}; }}
.p3-badge-n {{ font-family:{ctx['fonts']['display']}; font-size:25pt;
  color:{C['navy']}; line-height:1; }}
.p3-badge-u {{ font-family:{ctx['fonts']['sans']}; font-size:8pt;
  color:{C['gold']}; font-weight:700; margin-left:3px; }}
.p3-badge-l {{ font-size:7.6pt; color:{C['muted']}; font-weight:600;
  margin-top:4px; letter-spacing:.02em; }}

/* Trust strip (navy band, links out) */
.p3-trust {{ background:{C['navy']}; border-radius:11px; padding:13px 14px;
  display:flex; gap:10px; }}
.p3-trust-item {{ flex:1; text-decoration:none; display:block;
  border-right:1px solid rgba(255,255,255,.14); padding-right:10px; }}
.p3-trust-item:last-child {{ border-right:none; padding-right:0; }}
.p3-trust-t {{ display:block; color:#fff; font-size:8.6pt; font-weight:700;
  margin-bottom:2px; }}
.p3-trust-u {{ display:block; color:{C['gold']}; font-size:7.8pt;
  font-weight:600; }}

/* Conditions + steps side by side */
.p3-cols {{ display:flex; gap:10px; }}
.p3-col {{ flex:1; }}
.p3-card {{ border:1px solid {C['line']}; border-radius:10px;
  background:{C['paper']}; padding:10px 12px; height:100%; }}
.p3-cond-row {{ display:flex; gap:10px;
  padding:5px 0; border-bottom:1px dashed {C['line_soft']}; }}
.p3-cond-row:last-child {{ border-bottom:none; }}
.p3-cond-k {{ flex:0 0 38mm; font-size:8pt; color:{C['muted']}; font-weight:600;
  line-height:1.25; padding-right:8px; }}
.p3-cond-v {{ flex:1 1 0; min-width:0; font-size:8pt; color:{C['ink']};
  font-weight:500; text-align:right; line-height:1.25; }}

.p3-steps {{ display:flex; flex-direction:column; gap:9px; }}
.p3-step {{ display:flex; align-items:baseline; gap:8px; }}
.p3-step-n {{ width:18px; min-width:18px; height:18px; border-radius:50%;
  background:{C['navy']}; color:#fff; font-size:8pt; font-weight:700;
  text-align:center; line-height:18px; }}
.p3-step-t {{ font-size:8.6pt; color:{C['ink']}; font-weight:700; }}
.p3-step-s {{ font-size:8pt; color:{C['muted']}; margin-left:auto; }}

/* Bon pour accord */
.p3-accord {{ border:1.5px solid {C['navy']}; border-radius:12px;
  margin-top:4px; overflow:hidden; }}
.p3-accord-hd {{ background:{C['navy']}; color:#fff; padding:9px 14px;
  display:flex; align-items:center; justify-content:space-between; }}
.p3-accord-ttl {{ font-family:{ctx['fonts']['serif']}; font-weight:700;
  font-size:11.5pt; letter-spacing:.02em; }}
.p3-accord-opt {{ font-size:8.2pt; color:#dbe3f0; }}
.p3-box {{ display:inline-block; width:9px; height:9px; border:1.4px solid #fff;
  border-radius:2px; margin:0 4px 0 10px; vertical-align:-1px; }}
.p3-accord-bd {{ display:flex; }}
.p3-sig {{ flex:1; padding:13px 16px 16px; }}
.p3-sig:first-child {{ border-right:1px dashed {C['line']}; }}
.p3-sig-who {{ font-size:8.2pt; color:{C['navy']}; font-weight:700;
  text-transform:uppercase; letter-spacing:.06em; }}
.p3-sig-name {{ font-size:9.2pt; color:{C['ink']}; font-weight:700;
  margin-top:1px; }}
.p3-sig-hint {{ font-size:7.4pt; color:{C['muted']}; margin-top:2px; }}
.p3-sig-line {{ border-bottom:1px solid {C['line']}; height:42px; margin-top:8px; }}

/* CTA */
.p3-cta {{ margin-top:14px; background:{C['gold']}; border-radius:11px;
  padding:13px 18px; display:flex; align-items:center;
  justify-content:space-between; }}
.p3-cta-t {{ color:{C['navy']}; font-size:10.5pt; font-weight:700; }}
.p3-cta-s {{ color:{C['navy']}; font-size:8pt; opacity:.78; margin-top:1px; }}
.p3-cta-btn {{ background:{C['navy']}; color:#fff; font-size:9.5pt;
  font-weight:700; padding:8px 16px; border-radius:8px; white-space:nowrap;
  text-decoration:none; }}
.p3-cta-btn span {{ color:{C['gold']}; }}
</style>

<div class="p3-wrap">
  <div class="p3-kicker">Confiance &amp; Engagement</div>
  <div class="p3-title">Pourquoi TAQINOR</div>

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
      <div class="p3-accord-opt">Option choisie :
        <span class="p3-box"></span> Sans batterie
        <span class="p3-box"></span> Avec batterie</div>
    </div>
    <div class="p3-accord-bd">
      <div class="p3-sig">
        <div class="p3-sig-who">Le client</div>
        <div class="p3-sig-name">{client_full}</div>
        <div class="p3-sig-hint">Nom, date, mention « Bon pour accord » &amp; signature</div>
        <div class="p3-sig-line"></div>
      </div>
      <div class="p3-sig">
        <div class="p3-sig-who">TAQINOR</div>
        <div class="p3-sig-name">Cachet &amp; signature</div>
        <div class="p3-sig-hint">Le devis fait foi dès réception de l'acompte</div>
        <div class="p3-sig-line"></div>
      </div>
    </div>
  </div>

  <div class="p3-cta">
    <div>
      <div class="p3-cta-t">Prêt à passer au solaire ?</div>
      <div class="p3-cta-s">Validez votre devis en quelques clics, sans vous déplacer.</div>
    </div>
    <a class="p3-cta-btn" href="{_link(l_sign)}">Signez en ligne <span>&rarr;</span> {_disp(l_sign)}</a>
  </div>
</div>
"""
