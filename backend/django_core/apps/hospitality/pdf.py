"""NTHOT5 — Fiche de police marocaine, PDF interne (check-in).

JAMAIS ``/proposal`` (rule #4, CLAUDE.md — réservé au moteur devis ventes) :
document opérationnel interne transmis aux autorités, rendu via le service
PDF partagé ``core.pdf.render_pdf`` (WeasyPrint mutualisé, ARC11) — jamais un
appel direct à WeasyPrint depuis cette app.
"""
from html import escape

from core.pdf import render_pdf


def render_fiche_police_html(reservation):
    """Construit le HTML de la fiche de police pour TOUS les occupants
    (une fiche par occupant) d'une réservation ayant fait l'objet d'un
    check-in."""
    fiches = reservation.fiches_client.all()
    chambre = reservation.chambre

    lignes = ''.join(
        f"""
        <tr>
          <td>{escape(f.nom_complet)}</td>
          <td>{escape(f.nationalite)}</td>
          <td>{escape(f.get_type_piece_display())}</td>
          <td>{escape(f.numero_piece)}</td>
          <td>{escape(str(f.date_naissance))}</td>
        </tr>"""
        for f in fiches
    )

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 12px; color: #222; margin: 40px; }}
  h1 {{ font-size: 18px; text-align: center; }}
  .meta {{ margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #999; padding: 6px; text-align: left; }}
  th {{ background: #eee; }}
</style></head><body>
  <h1>Fiche de police — établissement hôtelier</h1>
  <div class="meta">
    <p>Réservation #{reservation.pk} — chambre
    {escape(chambre.numero) if chambre else 'non assignée'}</p>
    <p>Arrivée : {escape(str(reservation.date_arrivee))} —
    Départ : {escape(str(reservation.date_depart))}</p>
  </div>
  <table>
    <thead>
      <tr>
        <th>Nom complet</th><th>Nationalité</th><th>Pièce</th>
        <th>N° pièce</th><th>Date de naissance</th>
      </tr>
    </thead>
    <tbody>{lignes}</tbody>
  </table>
</body></html>"""


def render_fiche_police_pdf(reservation):
    """Fiche de police → octets PDF (NTHOT5)."""
    return render_pdf(html=render_fiche_police_html(reservation))
