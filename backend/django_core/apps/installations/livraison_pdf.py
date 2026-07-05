"""ZSTK4 — Bon de livraison imprimable depuis une Livraison planifiée
(packing/delivery slip, client-facing).

Le BL PDF existant (N22) part d'un devis/chantier ; la `Livraison` planifiée
(FG329) n'avait AUCUN document imprimable. Rendu à la volée via le MÊME
pipeline que les autres PDF (apps.ventes.utils.pdf : identité société +
template Jinja2 + WeasyPrint). Non stocké : généré et streamé à la demande.

CLIENT-FACING : AUCUN coût de transport interne ni prix d'achat — jamais."""
from apps.ventes.utils.pdf import _company_context, _html_to_pdf, _render_html


def _lignes_payload(livraison):
    """Articles de la livraison — désignation + quantité SEULEMENT, jamais un
    coût interne."""
    return [
        {
            'designation': ligne.designation or (
                ligne.produit.nom if ligne.produit_id else '—'),
            'quantite': ligne.quantite,
        }
        for ligne in livraison.lignes.select_related('produit').all()
    ]


def bon_livraison_pdf(livraison):
    """Génère le bon de livraison (PDF, octets) d'une `Livraison` planifiée.
    Client-facing : ne rend jamais le coût de transport interne ni un prix
    d'achat."""
    inst = livraison.installation
    client = getattr(inst, 'client', None) if inst else None
    context = _company_context(company=livraison.company)
    context.update({
        'livraison': livraison,
        'reference': livraison.reference,
        'chantier_reference': inst.reference if inst else '',
        'client_nom': (f"{client.nom} {client.prenom or ''}".strip()
                       if client else ''),
        'site_ville': getattr(inst, 'site_ville', '') or '' if inst else '',
        'site_adresse': getattr(inst, 'site_adresse', '') or '' if inst else '',
        'transporteur_nom': (
            livraison.transporteur.nom if livraison.transporteur_id
            else livraison.transporteur_nom or ''),
        'date_prevue': livraison.date_prevue,
        'numero_suivi': livraison.numero_suivi or '',
        'statut': livraison.get_statut_display(),
        'lignes': _lignes_payload(livraison),
    })
    html = _render_html('bon_livraison.html', context)
    return _html_to_pdf(html)
