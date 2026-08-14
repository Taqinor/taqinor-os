"""NTMFG19 — Étiquette/fiche suiveuse d'Ordre de Fabrication (traveler)
imprimable.

L'atelier papier a besoin d'un document qui ACCOMPAGNE le lot physique
(traveler/router card classique MRP II), distinct du bon d'assemblage
kitting (`installations.assembly_pdf`, spécifique à `OrdreAssemblage`).

Rendu à la volée via le MÊME pipeline que les autres PDF internes
(`apps.ventes.utils.pdf` : identité société + template Jinja2 + WeasyPrint).
Non stocké. STRICTEMENT INTERNE : AUCUN prix — ni `Produit.prix_achat`, ni
`PosteDeCharge.cout_horaire`, ni aucun coût (même règle que `assembly_pdf`,
DC28)."""
from apps.ventes.utils.pdf import _company_context, _html_to_pdf, _render_html

from .services import temps_operation_min


def _operations_payload(of):
    """Séquence d'opérations dans l'ordre de la gamme — poste + temps
    STANDARD prévu (jamais un coût), zone d'émargement (fait par/quand,
    quantité bonne/rebut)."""
    out = []
    for op in of.operations.select_related('poste_charge', 'operation_gamme').all():
        temps_prevu = (
            temps_operation_min(op.operation_gamme, of.quantite)
            if op.operation_gamme_id else None)
        out.append({
            'ordre': op.ordre,
            'libelle': op.libelle,
            'poste_nom': op.poste_charge.nom if op.poste_charge_id else '—',
            'temps_prevu_min': temps_prevu,
            'statut': op.get_statut_display(),
        })
    return out


def traveler_pdf(of):
    """Génère le traveler (PDF, octets) d'un `OrdreFabrication`. STRICTEMENT
    INTERNE : ne rend jamais un prix ni un coût."""
    context = _company_context(company=of.company)
    context.update({
        'reference': f'OF-{of.id}',
        'produit_nom': of.produit.nom if of.produit_id else '—',
        'quantite': of.quantite,
        'date_prevue': of.date_debut_planifiee,
        'statut': of.get_statut_display(),
        'est_prototype': of.est_prototype,
        'operations': _operations_payload(of),
    })
    html = _render_html('mrp_traveler.html', context)
    return _html_to_pdf(html)
