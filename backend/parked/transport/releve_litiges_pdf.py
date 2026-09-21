"""NTLOG31 — relevé mensuel des litiges transport, variante PDF (WeasyPrint
via `core.pdf.render_pdf`). Document NOUVEAU et DISTINCT du moteur
`/proposal` (règle CLAUDE.md #4 non concernée — usage interne, revue
mensuelle avec les transporteurs, jamais un devis client)."""
import html as _html

from core.pdf import render_pdf


def _esc(value):
    if value in (None, ''):
        return '—'
    return _html.escape(str(value))


def render_releve_litiges_pdf(litiges):
    """Rend le relevé (bytes PDF) d'une liste de `LitigeTransport` : une
    ligne par litige (ordre, transporteur, type, statut, montant contesté,
    montant résolu) + le total contesté en pied de tableau."""
    from . import selectors

    total_conteste = sum((litige.montant_conteste for litige in litiges), start=0)

    lignes_html = ''.join(
        f'<tr><td>{_esc(litige.ordre_transport.numero or litige.ordre_transport_id)}</td>'
        f'<td>{_esc(selectors.transporteur_nom_pour_ordre(litige.ordre_transport))}</td>'
        f'<td>{_esc(litige.get_type_litige_display())}</td>'
        f'<td>{_esc(litige.get_statut_display())}</td>'
        f'<td style="text-align:right;">{_esc(litige.montant_conteste)}</td>'
        f'<td style="text-align:right;">{_esc(litige.montant_resolu)}</td></tr>'
        for litige in litiges
    ) or '<tr><td colspan="6">Aucun litige sur la période.</td></tr>'

    html = f"""
    <html>
      <head><meta charset="utf-8"></head>
      <body style="font-family: sans-serif; font-size: 12px;">
        <h1>Relevé mensuel des litiges transport</h1>
        <table style="width:100%; border-collapse: collapse;">
          <thead>
            <tr>
              <th>Ordre</th><th>Transporteur</th><th>Type</th><th>Statut</th>
              <th>Montant contesté</th><th>Montant résolu</th>
            </tr>
          </thead>
          <tbody>{lignes_html}</tbody>
          <tfoot>
            <tr>
              <td colspan="4"><strong>Total contesté</strong></td>
              <td style="text-align:right;" colspan="2">
                <strong>{_esc(total_conteste)}</strong>
              </td>
            </tr>
          </tfoot>
        </table>
      </body>
    </html>
    """
    return render_pdf(html=html)
