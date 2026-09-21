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


# ── NTHOT19 — BEO (Banquet Event Order) ──────────────────────────────────────
# Document opérationnel interne (cuisine/salle), JAMAIS le moteur ``/proposal``
# (rule #4). Régénéré à la demande depuis l'état COURANT de l'événement — se
# régénère automatiquement si les détails changent (aucune donnée figée).

def render_beo_html(evenement):
    """Construit le HTML du BEO — horaire, plan de salle, menu (NTHOT13),
    contact client, notes cuisine/service (descriptions des recettes/salle)."""
    salle = evenement.salle
    client = evenement.client
    menu = list(evenement.menu_recettes.all())

    menu_rows = ''.join(
        f"""
        <tr>
          <td>{escape(r.get_categorie_menu_display())}</td>
          <td>{escape(r.nom_plat)}</td>
          <td>{escape(', '.join(r.allergenes) or '—')}</td>
        </tr>"""
        for r in menu
    )
    notes_cuisine = ''.join(
        f'<li><strong>{escape(r.nom_plat)}</strong> — '
        f'{escape(r.description) if r.description else "Aucune note."}</li>'
        for r in menu
    )
    contact = ''
    if client is not None:
        contact = (
            f"{escape(client.nom)}"
            + (f' — {escape(client.telephone)}' if client.telephone else '')
            + (f' — {escape(client.email)}' if client.email else ''))
    elif evenement.lead_id:
        contact = 'Contact via lead (non encore résolu en client CRM).'

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 12px; color: #222; margin: 40px; }}
  h1 {{ font-size: 18px; text-align: center; }}
  h2 {{ font-size: 13px; margin-top: 18px; border-bottom: 1px solid #ccc; padding-bottom: 2px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  th, td {{ border: 1px solid #999; padding: 6px; text-align: left; }}
  th {{ background: #eee; }}
  .meta p {{ margin: 2px 0; }}
</style></head><body>
  <h1>Banquet Event Order — {escape(evenement.nom_evenement)}</h1>

  <h2>Horaire détaillé</h2>
  <div class="meta">
    <p>Début : {escape(str(evenement.date_debut))}</p>
    <p>Fin : {escape(str(evenement.date_fin))}</p>
    <p>Convives : {evenement.nb_convives}</p>
  </div>

  <h2>Plan de salle</h2>
  <div class="meta">
    <p>Salle : {escape(salle.nom) if salle else 'Non assignée'}</p>
    {f'<p>Capacité : {salle.capacite_max}</p>' if salle else ''}
    {f'<p>Aménagements : {escape(", ".join(salle.types_amenagement_disponibles) or "—")}</p>' if salle else ''}
  </div>

  <h2>Menu choisi</h2>
  <table>
    <thead><tr><th>Catégorie</th><th>Plat</th><th>Allergènes</th></tr></thead>
    <tbody>{menu_rows or '<tr><td colspan="3">Aucun plat sélectionné.</td></tr>'}</tbody>
  </table>

  <h2>Prestations annexes</h2>
  <div class="meta">
    <p>{escape(salle.description) if salle and salle.description else 'Aucune prestation annexe renseignée.'}</p>
  </div>

  <h2>Contact client</h2>
  <div class="meta">
    <p>{contact or 'Aucun contact résolu.'}</p>
  </div>

  <h2>Notes cuisine / service</h2>
  <ul>{notes_cuisine or '<li>Aucune note.</li>'}</ul>
</body></html>"""


def render_beo_pdf(evenement):
    """BEO → octets PDF (NTHOT19)."""
    return render_pdf(html=render_beo_html(evenement))
