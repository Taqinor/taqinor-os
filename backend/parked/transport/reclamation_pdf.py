"""NTLOG19 — réclamation transporteur chiffrée (PDF interne, WeasyPrint via
`core.pdf.render_pdf`).

Document NOUVEAU et DISTINCT du moteur `/proposal` (règle CLAUDE.md #4 — ce
chemin ne rend QUE des devis client) : ceci est une pièce de réclamation
adressée à un transporteur, jamais une pièce client-facing de vente.
"""
import html as _html

from core.pdf import render_pdf


def _esc(value):
    if value in (None, ''):
        return '—'
    return _html.escape(str(value))


def render_reclamation_transporteur_pdf(litige):
    """Rend la réclamation transporteur (bytes PDF) d'un `LitigeTransport` :
    référence de l'ordre, nature du litige, préjudice chiffré, et la liste
    des pièces jointes (photos de réserve) référencées."""
    ordre = litige.ordre_transport
    from apps.records.models import Attachment

    reserve_ids = list(litige.reserves.values_list('id', flat=True))
    pieces = []
    if reserve_ids:
        from django.contrib.contenttypes.models import ContentType

        from .models import ReserveReception
        ct = ContentType.objects.get_for_model(ReserveReception)
        pieces = list(
            Attachment.objects.filter(
                content_type=ct, object_id__in=reserve_ids)
            .values_list('filename', flat=True))

    pieces_html = ''.join(f'<li>{_esc(p)}</li>' for p in pieces) or (
        '<li>Aucune pièce jointe.</li>')

    html = f"""
    <html>
      <head><meta charset="utf-8"></head>
      <body style="font-family: sans-serif; font-size: 12px;">
        <h1>Réclamation transporteur</h1>
        <table style="width:100%; border-collapse: collapse;">
          <tr><td><strong>Ordre de transport</strong></td>
              <td>{_esc(ordre.numero)}</td></tr>
          <tr><td><strong>Nature du litige</strong></td>
              <td>{_esc(litige.get_type_litige_display())}</td></tr>
          <tr><td><strong>Description</strong></td>
              <td>{_esc(litige.description)}</td></tr>
          <tr><td><strong>Montant contesté</strong></td>
              <td>{_esc(litige.montant_conteste)}</td></tr>
        </table>
        <h2>Pièces jointes référencées</h2>
        <ul>{pieces_html}</ul>
      </body>
    </html>
    """
    return render_pdf(html=html)
