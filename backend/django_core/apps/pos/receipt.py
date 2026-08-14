"""apps.pos.receipt — Ticket de caisse conforme (PDF 80 mm) — XPOS3.

Rendu WeasyPrint autonome (rouleau 80 mm) : identité vendeur complète (ICE,
IF, RC, patente, CNSS — art. 145 CGI), numéro séquentiel, lignes TTC,
décomposition TVA par taux, mode(s) de paiement, timbre fiscal si espèces,
mention renvoyant à la facture légale correspondante. JAMAIS de
``prix_achat``. Le HTML est construit en Python (pas de nouveau template
Django) pour rester autonome dans ``apps/pos``.

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()`` + import
paresseux) est déléguée au service partagé ``core.pdf.render_pdf`` ; le
GABARIT HTML ci-dessus reste STRICTEMENT identique, donc le rendu est
inchangé à l'octet près.
"""
from decimal import Decimal
from html import escape

from core.pdf import render_pdf


def _company_identity(company):
    """Identité légale du vendeur (art. 145 CGI) — lecture directe de
    ``parametres.CompanyProfile`` (app foundation, exempte de la règle de
    modularité cross-app)."""
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.get(company=company)
    return {
        'nom': profile.nom or '',
        'adresse': profile.adresse or '',
        'telephone': profile.telephone or '',
        'ice': getattr(profile, 'ice', '') or '',
        'if_fiscal': getattr(profile, 'identifiant_fiscal', '') or '',
        'rc': getattr(profile, 'rc', '') or '',
        'patente': getattr(profile, 'patente', '') or '',
        'cnss': getattr(profile, 'cnss', '') or '',
    }


def _tva_par_taux(vente):
    """Ventilation TVA par taux effectif des lignes de la vente (pur lecture,
    aucun prix d'achat)."""
    buckets = {}
    for ligne in vente.lignes.all():
        taux = ligne.taux_tva_effectif or Decimal('0')
        ht = ligne.total_ht
        montant_tva = ligne.total_ttc - ht
        b = buckets.setdefault(taux, {'ht': Decimal('0'), 'tva': Decimal('0')})
        b['ht'] += ht
        b['tva'] += montant_tva
    return buckets


def receipt_html(vente, *, paiements=None, timbre=None):
    """Construit le HTML du ticket de caisse 80 mm pour une ``VenteComptoir``
    validée. ``paiements`` : itérable de ``ventes.Paiement`` (ou dicts avec
    ``mode``/``montant``) ; ``timbre`` : instance ``TimbreFiscal`` ou None.
    """
    identite = _company_identity(vente.company)
    lignes_html = []
    for ligne in vente.lignes.all():
        lignes_html.append(
            f'<tr><td>{escape(ligne.designation)}</td>'
            f'<td class="num">{ligne.quantite}</td>'
            f'<td class="num">{ligne.prix_unitaire_ttc}</td>'
            f'<td class="num">{ligne.total_ttc:.2f}</td></tr>'
        )

    tva_html = []
    for taux, agg in sorted(_tva_par_taux(vente).items()):
        tva_html.append(
            f'<tr><td>TVA {taux}%</td>'
            f'<td class="num">{agg["tva"]:.2f}</td></tr>')

    paiements_html = []
    for p in (paiements or []):
        mode = getattr(p, 'mode', None) or (p.get('mode') if isinstance(p, dict) else '')
        montant = getattr(p, 'montant', None) if not isinstance(p, dict) else p.get('montant')
        paiements_html.append(
            f'<tr><td>{escape(str(mode))}</td>'
            f'<td class="num">{Decimal(montant or 0):.2f}</td></tr>')

    timbre_html = ''
    if timbre is not None:
        timbre_html = (
            f'<p class="timbre">Droit de timbre : '
            f'{timbre.montant:.2f} MAD</p>')

    facture_ref = vente.facture.reference if vente.facture_id else ''
    mention = (
        f'Ticket de caisse — la facture correspondante {facture_ref} '
        'est disponible.' if facture_ref else 'Ticket de caisse.')

    return f"""
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{ size: 80mm auto; margin: 3mm; }}
  body {{ font-family: monospace; font-size: 10px; width: 74mm; }}
  h1 {{ font-size: 12px; text-align: center; margin: 2px 0; }}
  .identite {{ text-align: center; font-size: 9px; margin-bottom: 4px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 1px 0; }}
  .num {{ text-align: right; }}
  .mention {{ margin-top: 6px; font-size: 8px; text-align: center; }}
  .timbre {{ font-size: 9px; text-align: center; }}
  hr {{ border: none; border-top: 1px dashed #000; }}
</style>
</head>
<body>
  <h1>{escape(identite['nom'])}</h1>
  <div class="identite">
    {escape(identite['adresse'])}<br>
    Tél : {escape(identite['telephone'])}<br>
    ICE : {escape(identite['ice'])} — IF : {escape(identite['if_fiscal'])}<br>
    RC : {escape(identite['rc'])} — Patente : {escape(identite['patente'])}<br>
    CNSS : {escape(identite['cnss'])}
  </div>
  <hr>
  <p>Ticket n° {escape(vente.reference)}</p>
  <table>
    <tr><td>Désignation</td><td class="num">Qté</td>
        <td class="num">PU</td><td class="num">Total</td></tr>
    {''.join(lignes_html)}
  </table>
  <hr>
  <table>{''.join(tva_html)}</table>
  <p><strong>Total TTC : {vente.total_ttc:.2f} MAD</strong></p>
  <hr>
  <p>Règlement(s) :</p>
  <table>{''.join(paiements_html)}</table>
  {timbre_html}
  <hr>
  <p class="mention">{escape(mention)}</p>
</body>
</html>
"""


def receipt_pdf(vente, *, paiements=None, timbre=None):
    """Génère le PDF du ticket de caisse (octets) via ``core.pdf.render_pdf``
    (ARC12 — plomberie WeasyPrint centralisée)."""
    html = receipt_html(vente, paiements=paiements, timbre=timbre)
    return render_pdf(html=html)


# ── NTRET2 — Rapport Z officiel (PDF, numéroté séquentiellement) ────────────

def rapport_z_html(session, data):
    """HTML du rapport Z officiel : identité vendeur, numéro séquentiel
    (jamais count()+1 — ``core.numbering``), totaux par mode de paiement,
    nombre de ventes. ``data`` = l'agrégat renvoyé par
    ``services.generer_rapport_z``/``services.rapport_x`` (avec ou sans la
    clé ``numero_rapport_z`` — la vue passe le numéro déjà posé sur la
    session dans les deux cas)."""
    identite = _company_identity(session.company)
    lignes_mode = []
    for mode, agg in sorted((data.get('par_mode') or {}).items()):
        lignes_mode.append(
            f'<tr><td>{escape(str(mode))}</td>'
            f'<td class="num">{agg["nb"]}</td>'
            f'<td class="num">{Decimal(agg["total"] or 0):.2f}</td></tr>')

    numero = session.numero_rapport_z or data.get('numero_rapport_z') or ''
    date_cloture = (
        session.date_cloture.strftime('%d/%m/%Y %H:%M')
        if session.date_cloture else '')

    return f"""
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{ size: 80mm auto; margin: 3mm; }}
  body {{ font-family: monospace; font-size: 10px; width: 74mm; }}
  h1 {{ font-size: 12px; text-align: center; margin: 2px 0; }}
  .identite {{ text-align: center; font-size: 9px; margin-bottom: 4px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 1px 0; }}
  .num {{ text-align: right; }}
  hr {{ border: none; border-top: 1px dashed #000; }}
</style>
</head>
<body>
  <h1>{escape(identite['nom'])}</h1>
  <div class="identite">
    {escape(identite['adresse'])}<br>
    ICE : {escape(identite['ice'])} — IF : {escape(identite['if_fiscal'])}
  </div>
  <hr>
  <p><strong>Rapport Z n° {escape(str(numero))}</strong></p>
  <p>Session #{session.pk} — clôturée le {escape(date_cloture)}</p>
  <hr>
  <table>
    <tr><td>Mode</td><td class="num">Nb</td><td class="num">Total</td></tr>
    {''.join(lignes_mode)}
  </table>
  <hr>
  <p><strong>Total : {Decimal(data.get('total') or 0):.2f} MAD</strong></p>
  <p>Nombre de ventes : {data.get('nb_ventes', 0)}</p>
</body>
</html>
"""


def rapport_z_pdf(session, data):
    """Génère le PDF du rapport Z officiel (octets) via
    ``core.pdf.render_pdf`` — même plomberie mutualisée que le ticket."""
    html = rapport_z_html(session, data)
    return render_pdf(html=html)


# ── NTRET5 — Reçu d'arrhes (distinct du ticket final) ───────────────────────

def receipt_arrhes_html(vente, *, solde_restant=None):
    """HTML du « Reçu d'arrhes » (NTRET5) : DISTINCT du ticket de caisse
    final (``receipt_html``) — montre les lignes réservées, le montant des
    arrhes encaissé, et le solde restant dû avant remise de la marchandise.
    N'affiche PAS de TVA détaillée par taux (ce n'est pas encore la vente
    soldée) ni de prix d'achat."""
    identite = _company_identity(vente.company)
    lignes_html = []
    for ligne in vente.lignes.all():
        lignes_html.append(
            f'<tr><td>{escape(ligne.designation)}</td>'
            f'<td class="num">{ligne.quantite}</td>'
            f'<td class="num">{ligne.total_ttc:.2f}</td></tr>'
        )
    total_ttc = vente.total_ttc
    montant_arrhes = vente.montant_arrhes or Decimal('0')
    solde = (
        solde_restant if solde_restant is not None
        else total_ttc - montant_arrhes)

    return f"""
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{ size: 80mm auto; margin: 3mm; }}
  body {{ font-family: monospace; font-size: 10px; width: 74mm; }}
  h1 {{ font-size: 12px; text-align: center; margin: 2px 0; }}
  .identite {{ text-align: center; font-size: 9px; margin-bottom: 4px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 1px 0; }}
  .num {{ text-align: right; }}
  .mention {{ margin-top: 6px; font-size: 8px; text-align: center; }}
  hr {{ border: none; border-top: 1px dashed #000; }}
</style>
</head>
<body>
  <h1>{escape(identite['nom'])}</h1>
  <div class="identite">
    {escape(identite['adresse'])}<br>
    ICE : {escape(identite['ice'])} — IF : {escape(identite['if_fiscal'])}
  </div>
  <hr>
  <p><strong>Reçu d'arrhes — {escape(vente.reference)}</strong></p>
  <table>
    <tr><td>Désignation</td><td class="num">Qté</td><td class="num">Total</td></tr>
    {''.join(lignes_html)}
  </table>
  <hr>
  <p>Total de la commande : {total_ttc:.2f} MAD</p>
  <p><strong>Arrhes encaissées : {montant_arrhes:.2f} MAD</strong></p>
  <p><strong>Solde restant dû : {solde:.2f} MAD</strong></p>
  <hr>
  <p class="mention">
    Marchandise remise UNIQUEMENT après règlement du solde.
    Ce reçu n'est pas le ticket de caisse final.
  </p>
</body>
</html>
"""


def receipt_arrhes_pdf(vente, *, solde_restant=None):
    """Génère le PDF du reçu d'arrhes (octets) via ``core.pdf.render_pdf``."""
    html = receipt_arrhes_html(vente, solde_restant=solde_restant)
    return render_pdf(html=html)
