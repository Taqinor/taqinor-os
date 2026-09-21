"""NTLOG29 — bordereau d'expédition (packing list transport) PDF interne,
WeasyPrint via `core.pdf.render_pdf`.

Document NOUVEAU et DISTINCT du moteur `/proposal` (règle CLAUDE.md #4 — non
concernée : ceci ne rend jamais un devis client, seulement un document
d'accompagnement papier interne pour le chauffeur — mêmes garanties que
`reclamation_pdf.py`, NTLOG19)."""
import html as _html
from decimal import Decimal

from core.pdf import render_pdf


def _esc(value):
    if value in (None, ''):
        return '—'
    return _html.escape(str(value))


def _transporteur_affecte(ordre):
    from .models import OrdreTransport

    if ordre.mode_transport == OrdreTransport.ModeTransport.FLOTTE_PROPRE:
        return str(ordre.conducteur) if ordre.conducteur_id else '—'
    from . import selectors

    return selectors.transporteur_nom_pour_ordre(ordre) or '—'


def render_bordereau_expedition_pdf(ordre):
    """Rend le bordereau (bytes PDF) d'un `OrdreTransport` : ses lignes
    (désignation/quantité/poids/volume), expéditeur/destinataire,
    transporteur affecté (ou conducteur si flotte propre), cases signature
    enlèvement/livraison. Reprend EXACTEMENT les lignes/poids/volume total
    affichés à l'écran (`OrdreTransportSerializer.poids_total_kg`/
    `volume_total_m3`, mêmes accumulateurs)."""
    lignes = list(ordre.lignes.all())
    poids_total = sum((ligne.poids_kg for ligne in lignes), Decimal('0'))
    volume_total = sum((ligne.volume_m3 for ligne in lignes), Decimal('0'))

    lignes_html = ''.join(
        f'<tr><td>{_esc(ligne.designation)}</td>'
        f'<td style="text-align:right;">{_esc(ligne.quantite)} {_esc(ligne.unite)}</td>'
        f'<td style="text-align:right;">{_esc(ligne.poids_kg)} kg</td>'
        f'<td style="text-align:right;">{_esc(ligne.volume_m3)} m³</td></tr>'
        for ligne in lignes
    ) or '<tr><td colspan="4">Aucune ligne.</td></tr>'

    html = f"""
    <html>
      <head><meta charset="utf-8"></head>
      <body style="font-family: sans-serif; font-size: 12px;">
        <h1>Bordereau d'expédition</h1>
        <table style="width:100%; border-collapse: collapse;">
          <tr><td><strong>Ordre de transport</strong></td>
              <td>{_esc(ordre.numero)}</td></tr>
          <tr><td><strong>Expéditeur</strong></td>
              <td>{_esc(ordre.expediteur_nom)} — {_esc(ordre.expediteur_adresse)}</td></tr>
          <tr><td><strong>Destinataire</strong></td>
              <td>{_esc(ordre.destinataire_nom)} — {_esc(ordre.destinataire_adresse)}</td></tr>
          <tr><td><strong>Transporteur affecté</strong></td>
              <td>{_esc(_transporteur_affecte(ordre))}</td></tr>
        </table>

        <h2>Marchandises</h2>
        <table style="width:100%; border-collapse: collapse;">
          <thead>
            <tr><th>Désignation</th><th>Quantité</th><th>Poids</th><th>Volume</th></tr>
          </thead>
          <tbody>{lignes_html}</tbody>
          <tfoot>
            <tr>
              <td colspan="2"><strong>Total</strong></td>
              <td style="text-align:right;"><strong>{_esc(poids_total)} kg</strong></td>
              <td style="text-align:right;"><strong>{_esc(volume_total)} m³</strong></td>
            </tr>
          </tfoot>
        </table>

        <h2>Signatures</h2>
        <table style="width:100%; border-collapse: collapse;">
          <tr>
            <td style="width:50%; height:80px; vertical-align: top; border: 1px solid #999;">
              Enlèvement — signature/date
            </td>
            <td style="width:50%; height:80px; vertical-align: top; border: 1px solid #999;">
              Livraison — signature/date
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    return render_pdf(html=html)
