"""Rapport PDF d'intervention SAV (N45) — rendu à la volée via WeasyPrint,
EXACTEMENT le même pipeline que les factures (apps/ventes/utils/pdf : branding
société + template Jinja2 + WeasyPrint). On ne stocke pas ce rapport : il est
généré et streamé à la demande.

CÔTÉ CLIENT : aucun prix d'achat, aucune marge — jamais. Les pièces (si le
modèle en porte un jour) n'affichent que désignation/marque/quantité.
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
    """Pièces consommées — JAMAIS de prix d'achat ni de marge côté client.

    Lecture DÉFENSIVE : le modèle Ticket ne porte pas (encore) de pièces ; on
    lit `ticket.pieces` si la relation existe, sinon liste vide."""
    manager = getattr(ticket, 'pieces', None)
    if manager is None:
        return []
    try:
        rows_qs = manager.select_related('produit').all()
    except Exception:
        try:
            rows_qs = manager.all()
        except Exception:
            return []
    rows = []
    for p in rows_qs:
        produit = getattr(p, 'produit', None)
        rows.append({
            'designation': produit.nom if produit else '—',
            'marque': (produit.marque or '') if produit else '',
            'quantite': getattr(p, 'quantite', None),
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


def rapport_maintenance_pdf(contrat, visite_date=None):
    """N47 — rapport court de visite de maintenance (PDF, à la demande).

    Client-facing : aucun prix d'achat ni marge. ``visite_date`` est la date
    de la visite (par défaut la dernière visite enregistrée du contrat)."""
    context = _company_context(company=contrat.company)
    client = contrat.client
    periodicite_label = dict(
        contrat.Periodicite.choices).get(contrat.periodicite,
                                         contrat.periodicite)
    context.update({
        'contrat': contrat,
        'client': client,
        'client_nom': (f"{client.nom} {client.prenom or ''}".strip()
                       if client else ''),
        'installation_reference': (contrat.installation.reference
                                   if contrat.installation_id else ''),
        'visite_date': visite_date or contrat.derniere_visite,
        'periodicite_label': periodicite_label,
        'prochaine_visite': contrat.prochaine_visite(),
        'date_renouvellement': contrat.date_renouvellement,
    })
    html = _render_html('maintenance.html', context)
    return _html_to_pdf(html)
