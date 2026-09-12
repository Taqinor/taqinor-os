"""NTPRT30 — Relevé de commissions du PARTENAIRE, en PDF.

Document INTERNE-LÉGER au sens de la règle #4 : ce n'est PAS un devis client,
donc il ne passe pas — et ne doit jamais passer — par le moteur premium
``apps/ventes/quote_engine``. Il emprunte le service PDF partagé
``core.pdf.render_pdf`` (ARC11), le chemin recommandé pour tout nouveau PDF
hors devis : aucun import direct de WeasyPrint ici.

Le contenu est le relevé rendu à l'écran, À L'IDENTIQUE : mêmes lignes, mêmes
sous-totaux, même total — la source unique est
``apps.crm.selectors.releve_commissions_partenaire`` (jamais un second calcul
recopié dans le gabarit, qui divergerait le jour où la règle change).
"""
import html as _html


def _esc(valeur):
    """Échappe le texte injecté dans le gabarit (noms, statuts, dates)."""
    return '' if valeur is None else _html.escape(str(valeur))


def _mad(valeur):
    """Montant MAD tel qu'il sort du sélecteur (aucun recalcul ici)."""
    return f'{_esc(valeur)} MAD'


def _periode(releve):
    debut, fin = releve.get('debut'), releve.get('fin')
    if debut and fin:
        return f'Période du {_esc(debut)} au {_esc(fin)}'
    if debut:
        return f'Période à partir du {_esc(debut)}'
    if fin:
        return f"Période jusqu'au {_esc(fin)}"
    return 'Depuis l’ouverture de votre partenariat'


def render_releve_commissions_pdf(releve, societe=''):
    """Relevé de commissions → octets PDF.

    ``releve`` est le dict renvoyé par
    ``crm.selectors.releve_commissions_partenaire``. ``societe`` est le nom
    affiché de la marque du portail (NTPRT19) — vide, l'en-tête se réduit au
    titre plutôt que d'afficher une marque inventée.
    """
    from core.pdf import render_pdf

    lignes = releve.get('lignes') or []
    corps = ''.join(f'''
          <tr>
            <td>{_esc((ligne.get('date_creation') or '')[:10])}</td>
            <td>{_esc(ligne.get('devis_id') or '—')}</td>
            <td class="n">{_mad(ligne.get('base_ht'))}</td>
            <td class="n">{_esc(ligne.get('taux'))} %</td>
            <td class="n">{_mad(ligne.get('montant'))}</td>
            <td>{_esc(ligne.get('statut_display'))}</td>
          </tr>''' for ligne in lignes)
    if not corps:
        corps = ('<tr><td colspan="6">Aucune commission sur cette '
                 'période.</td></tr>')

    totaux = releve.get('totaux') or {}
    entete_societe = (f'<p class="societe">{_esc(societe)}</p>'
                      if societe else '')

    html = f'''<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><style>
  body {{ font-family: sans-serif; font-size: 11px; }}
  h1 {{ font-size: 16px; margin-bottom: 2px; }}
  .societe {{ margin: 0 0 8px; color: #555; }}
  .periode {{ margin: 0 0 12px; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; text-align: left; }}
  th {{ background: #f2f2f2; }}
  td.n, th.n {{ text-align: right; }}
  tfoot td {{ font-weight: bold; }}
</style></head>
<body>
  <h1>Relevé de commissions — {_esc(releve.get('partenaire_nom'))}</h1>
  {entete_societe}
  <p class="periode">{_periode(releve)}</p>
  <table>
    <thead>
      <tr>
        <th>Date</th><th>Devis</th><th class="n">Base HT</th>
        <th class="n">Taux</th><th class="n">Commission</th><th>Statut</th>
      </tr>
    </thead>
    <tbody>{corps}</tbody>
    <tfoot>
      <tr>
        <td colspan="4">Dues</td>
        <td class="n">{_mad(totaux.get('due'))}</td><td></td>
      </tr>
      <tr>
        <td colspan="4">Payées</td>
        <td class="n">{_mad(totaux.get('payee'))}</td><td></td>
      </tr>
      <tr>
        <td colspan="4">Annulées</td>
        <td class="n">{_mad(totaux.get('annulee'))}</td><td></td>
      </tr>
      <tr>
        <td colspan="4">Total du relevé</td>
        <td class="n">{_mad(totaux.get('total'))}</td><td></td>
      </tr>
    </tfoot>
  </table>
</body>
</html>'''
    return render_pdf(html=html)
