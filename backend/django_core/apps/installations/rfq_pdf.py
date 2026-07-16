"""XPUR20 — PDF de la demande de prix (RFQ) envoyée aux fournisseurs consultés.

Le PDF liste UNIQUEMENT produits/quantités/date limite de réponse — JAMAIS un
prix interne (achat ou vente) : c'est un document CONSULTATIF envoyé à
l'extérieur. Rendu en Python string + WeasyPrint (même patron léger que
``apps.qhse.services.rendre_analyse_ncr_pdf`` — pas de nouveau fichier
template Django enregistré).

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()``) est
déléguée au service partagé ``core.pdf.render_pdf`` ; le GABARIT HTML
ci-dessous reste STRICTEMENT identique, donc le rendu est inchangé à l'octet
près."""
from django.utils.html import escape

from apps.ventes.utils.pdf import _company_context
from core.pdf import render_pdf


def _lignes_html(rfq):
    demande = getattr(rfq, 'demande', None)
    if demande is None:
        return '<p>Voir pièces jointes / cahier des charges.</p>'
    rows = []
    for ligne in demande.lignes.all():
        designation = escape(ligne.designation or '')
        quantite = ligne.quantite
        rows.append(
            f'<tr><td>{designation}</td><td>{quantite}</td></tr>')
    if not rows:
        return '<p>Voir pièces jointes / cahier des charges.</p>'
    return (
        '<table style="width:100%;border-collapse:collapse;">'
        '<thead><tr><th style="text-align:left;">Désignation</th>'
        '<th style="text-align:left;">Quantité</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
    )


def rfq_pdf_bytes(rfq):
    """XPUR20 — PDF RFQ (produits/quantités/date limite), AUCUN prix interne."""
    ctx = _company_context(rfq.company)
    date_limite = (rfq.date_limite_reponse.strftime('%d/%m/%Y')
                   if rfq.date_limite_reponse else 'Non précisée')
    html = f"""
    <html><head><meta charset="utf-8"><style>
      body {{ font-family: sans-serif; font-size: 12px; color: #222; }}
      h1 {{ color: {escape(ctx.get('couleur_principale') or '#1c3d5a')}; }}
      table {{ margin-top: 12px; }}
      th, td {{ border-bottom: 1px solid #ddd; padding: 6px 4px; }}
    </style></head>
    <body>
      <h1>{escape(ctx.get('entreprise_nom') or '')}</h1>
      <h2>Demande de prix — {escape(rfq.reference)}</h2>
      <p><strong>Objet :</strong> {escape(rfq.objet)}</p>
      <p><strong>Date limite de réponse :</strong> {escape(date_limite)}</p>
      {_lignes_html(rfq)}
      <p style="margin-top:24px;">Merci de nous transmettre votre meilleure
      offre (montant HT, délai, validité) avant la date limite ci-dessus.</p>
    </body></html>
    """
    return render_pdf(html=html)
