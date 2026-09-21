"""NTAGR7 — Registre phytosanitaire ONSSA imprimable (PDF interne).

Rendu PDF INTERNE (WeasyPrint, via ``core.pdf.render_pdf``) listant, pour une
``CampagneCulturale``, chaque ``EtapeCampagne`` de type ``traitement`` dans
l'ordre chronologique avec les colonnes réglementaires ONSSA : produit (nom
commercial + matière active + n° AMM), dose appliquée, date, DAR (délai avant
récolte), date de récolte réelle, conformité DAR. JAMAIS le moteur
``/proposal`` (règle CLAUDE.md #4 — ce chemin ne rend QUE des devis client) :
ceci est un registre réglementaire, pas un devis.

Le nom commercial du produit est lu EXCLUSIVEMENT via
``apps.stock.selectors`` (jamais un import de ``apps.stock.models``)."""
import datetime
import html as _html

from core.pdf import render_pdf


def _esc(value):
    if value is None:
        return ''
    return _html.escape(str(value))


def _produit_nom(company, intrant):
    if intrant is None:
        return '—'
    from apps.stock.selectors import get_produit_scoped
    produit = get_produit_scoped(company, intrant.produit_id)
    return produit.nom if produit else f'Produit #{intrant.produit_id}'


def _conformite(etape, campagne):
    """Conformité DAR pour une ligne du registre — coché si aucune violation
    du délai avant récolte n'est détectable, croix sinon. Sans DAR défini ou
    sans date de récolte connue, la conformité n'est pas évaluable (« — »)."""
    intrant = etape.intrant
    if intrant is None or intrant.delai_avant_recolte_jours is None:
        return '—'
    candidates = [
        d for d in (campagne.date_recolte_prevue, campagne.date_recolte_reelle)
        if d is not None
    ]
    if not candidates:
        return '—'
    date_limite = etape.date + datetime.timedelta(
        days=intrant.delai_avant_recolte_jours)
    return '✓' if date_limite <= min(candidates) else '✗'


def render_registre_phyto_pdf(campagne):
    """Rend le registre phytosanitaire (bytes PDF) d'une campagne.

    Une campagne sans traitement produit un PDF propre avec un message
    « Aucun traitement enregistré » — jamais une erreur."""
    company = campagne.company
    traitements = list(
        campagne.etapes.filter(type_etape='traitement').order_by('date', 'id'))

    rows_html = ''
    for etape in traitements:
        intrant = etape.intrant
        dose = (
            f'{intrant.dose_reference_par_ha} /ha'
            if intrant and intrant.dose_reference_par_ha is not None else '—')
        dar = (
            f'{intrant.delai_avant_recolte_jours} j'
            if intrant and intrant.delai_avant_recolte_jours is not None else '—')
        rows_html += f"""
        <tr>
          <td>{_esc(etape.date.isoformat())}</td>
          <td>{_esc(_produit_nom(company, intrant))}</td>
          <td>{_esc(intrant.matiere_active if intrant else '')}</td>
          <td>{_esc(intrant.numero_amm if intrant else '')}</td>
          <td>{_esc(dose)}</td>
          <td>{_esc(dar)}</td>
          <td>{_esc(campagne.date_recolte_reelle.isoformat() if campagne.date_recolte_reelle else '—')}</td>
          <td class="center">{_esc(_conformite(etape, campagne))}</td>
        </tr>"""

    if traitements:
        body = f"""
        <table>
          <thead>
            <tr>
              <th>Date</th><th>Produit</th><th>Matière active</th>
              <th>N° AMM</th><th>Dose</th><th>DAR</th>
              <th>Récolte réelle</th><th>Conforme DAR</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>"""
    else:
        body = '<p>Aucun traitement enregistré pour cette campagne.</p>'

    html = f"""<!DOCTYPE html>
    <html lang="fr">
    <head>
    <meta charset="utf-8">
    <style>
      body {{ font-family: sans-serif; font-size: 11px; }}
      h1 {{ font-size: 16px; }}
      table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
      th, td {{ border: 1px solid #999; padding: 4px 6px; text-align: left; }}
      td.center {{ text-align: center; }}
    </style>
    </head>
    <body>
      <h1>Registre phytosanitaire — {_esc(campagne.culture)}</h1>
      <p>Parcelle : {_esc(campagne.parcelle.nom)} — Campagne #{campagne.pk}</p>
      {body}
    </body>
    </html>"""

    return render_pdf(html=html)
