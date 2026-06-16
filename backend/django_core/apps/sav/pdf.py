"""
Rapports PDF SAV (FRANÇAIS) — rendus à la volée via WeasyPrint, EXACTEMENT le
même pipeline que les factures (apps/ventes/utils/pdf : branding société +
Jinja/Django template + WeasyPrint). On NE stocke pas ces rapports (pas de clé
MinIO) : ils sont générés et streamés à la demande.

CÔTÉ CLIENT : aucun prix d'achat, aucune marge — jamais. Les pièces n'affichent
que désignation/marque/quantité.

  * rapport_intervention_pdf(ticket)  — N45 : panne, diagnostic, travail,
    pièces, bloc signature client.
  * rapport_maintenance_pdf(contrat[, ticket]) — N47 : compte rendu de visite
    préventive.
"""
from apps.ventes.utils.pdf import (
    _company_context, _render_html, _html_to_pdf,
)


def _interventions_payload(ticket):
    """Comptes rendus des interventions liées (diagnostic + travail réalisé)."""
    rows = []
    for itv in ticket.interventions.all():
        rows.append({
            'type': itv.get_type_intervention_display(),
            'date': itv.date_realisee or itv.date_prevue,
            'technicien': getattr(itv.technicien, 'username', None),
            'compte_rendu': itv.compte_rendu or '',
        })
    return rows


def _pieces_payload(ticket):
    """Pièces consommées — JAMAIS de prix d'achat ni de marge côté client."""
    rows = []
    for p in ticket.pieces.select_related('produit').all():
        produit = p.produit
        rows.append({
            'designation': produit.nom if produit else '—',
            'marque': (produit.marque or '') if produit else '',
            'quantite': p.quantite,
        })
    return rows


def rapport_intervention_pdf(ticket):
    """Génère le PDF du rapport d'intervention (N45). Renvoie des octets PDF."""
    context = _company_context(company=ticket.company)
    client = ticket.client
    context.update({
        'ticket': ticket,
        'client_nom': (f"{client.nom} {client.prenom or ''}".strip()
                       if client else ''),
        'client': client,
        'installation_reference': (ticket.installation.reference
                                   if ticket.installation else ''),
        'equipement': ticket.equipement,
        'interventions': _interventions_payload(ticket),
        'pieces': _pieces_payload(ticket),
    })
    html = _render_html('sav_intervention.html', context)
    return _html_to_pdf(html)


def rapport_maintenance_pdf(contrat, ticket=None):
    """Génère le PDF du rapport de maintenance préventive (N47)."""
    context = _company_context(company=contrat.company)
    client = contrat.client
    pieces = _pieces_payload(ticket) if ticket is not None else []
    interventions = _interventions_payload(ticket) if ticket is not None else []
    context.update({
        'contrat': contrat,
        'ticket': ticket,
        'client_nom': (f"{client.nom} {client.prenom or ''}".strip()
                       if client else ''),
        'installation_reference': (contrat.installation.reference
                                   if contrat.installation else ''),
        'pieces': pieces,
        'interventions': interventions,
    })
    html = _render_html('sav_maintenance.html', context)
    return _html_to_pdf(html)
