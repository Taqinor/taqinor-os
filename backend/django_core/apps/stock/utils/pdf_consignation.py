"""NTDST24 — Relevé de consignation imprimable (PDF simple).

Justificatif remis AU CLIENT : « voilà ce que vous avez en dépôt chez vous ».
Rendu par le WeasyPrint déjà en place pour les documents internes
(``apps.ventes.utils.pdf``) — **jamais** le moteur de devis vendorisé
(règle #4), qui ne rend que les devis clients.

WHITE-LABEL : l'en-tête vient du profil de la SOCIÉTÉ (``_company_context``),
aucune marque en dur. Le gabarit est construit ici, en Python (même pratique
que ``labels.py`` et ``pdf_cmr.py``) : cette lane ne possède pas le dossier de
gabarits partagé ``templates/pdf/``.
"""


def _esc(value):
    return (str(value if value is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


_LIBELLES_STATUT = {'declaree': 'Déclarée', 'facturee': 'Facturée'}


def render_releve_consignation_html(depot):
    """HTML du relevé (testable SANS WeasyPrint).

    Les lignes sont TRIÉES PAR DATE et le solde restant figure en PIED de
    tableau — c'est exactement ce que le critère d'acceptation exige.
    """
    from apps.ventes.utils.pdf import _company_context

    from ..services_consignation import releve_consignation

    ctx = _company_context(company=depot.company)
    releve = releve_consignation(depot)

    lignes_html = ''.join(
        f'<tr><td>{_esc(d["date"])}</td>'
        f'<td>Consommation déclarée</td>'
        f'<td class="num">{_esc(d["quantite"])}</td>'
        f'<td>{_esc(_LIBELLES_STATUT.get(d["statut"], d["statut"]))}</td>'
        f'<td class="mono">{_esc(d["document_reference"])}</td></tr>'
        for d in releve['declarations']
    )
    depot_html = (
        f'<tr><td>{_esc(releve["date_depot"])}</td>'
        f'<td>Mise en dépôt</td>'
        f'<td class="num">{_esc(releve["quantite_deposee"])}</td>'
        f'<td>—</td><td class="mono"></td></tr>')

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Relevé de consignation</title>
<style>
  @page {{ size: A4; margin: 15mm; }}
  body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt;
          color: #111; }}
  h1 {{ font-size: 15pt; margin: 0 0 1mm; }}
  .meta {{ font-size: 9pt; color: #555; margin: 0 0 6mm; }}
  .entete {{ margin-bottom: 6mm; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 4mm; }}
  th, td {{ border: 0.3mm solid #666; padding: 1.6mm 2mm; text-align: left; }}
  th {{ background: #eee; font-size: 8.5pt; text-transform: uppercase; }}
  .num {{ text-align: right; }}
  .mono {{ font-family: "Courier New", monospace; font-size: 9pt; }}
  tfoot td {{ font-weight: bold; background: #f5f5f5; }}
</style></head>
<body>
  <div class="entete">
    <div><strong>{_esc(ctx.get('entreprise_nom'))}</strong></div>
    <div>{_esc(ctx.get('entreprise_adresse'))}</div>
  </div>
  <h1>Relevé de stock en dépôt (consignation)</h1>
  <p class="meta">
    Produit : {_esc(releve['produit_nom'])} &mdash;
    Site : {_esc(releve['adresse_site']) or '&mdash;'} &mdash;
    Statut : {_esc(releve['statut'])}
  </p>

  <table>
    <thead><tr>
      <th>Date</th><th>Mouvement</th><th class="num">Quantité</th>
      <th>Statut</th><th>Document</th>
    </tr></thead>
    <tbody>{depot_html}{lignes_html}</tbody>
    <tfoot><tr>
      <td colspan="2">Solde restant en dépôt</td>
      <td class="num">{_esc(releve['quantite_restante'])}</td>
      <td colspan="2">
        déposé {_esc(releve['quantite_deposee'])} &middot;
        consommé {_esc(releve['quantite_consommee'])} &middot;
        facturé {_esc(releve['quantite_facturee'])}
      </td>
    </tr></tfoot>
  </table>
</body></html>"""


def generate_releve_consignation_pdf(depot):
    """Rend le relevé et renvoie les octets (jamais stocké)."""
    from apps.ventes.utils.pdf import _html_to_pdf
    return _html_to_pdf(render_releve_consignation_html(depot))
