"""PDF du bon de commande FOURNISSEUR (N12) — INTERNE.

Réutilise l'approche WeasyPrint des factures (Jinja2 → HTML → PDF). Ce
document est destiné au fournisseur : il affiche légitimement les PRIX
D'ACHAT, car c'est le prix qu'on paie au fournisseur. Il ne doit JAMAIS être
exposé comme document client.
"""
from apps.ventes.utils.pdf import _company_context, _render_html, _html_to_pdf


def build_bcf_context(bon_commande):
    """Contexte de rendu pour le PDF fournisseur."""
    context = _company_context(company=bon_commande.company)
    context['bc'] = bon_commande
    context['lignes'] = list(
        bon_commande.lignes.select_related('produit').all())
    context['total_achat'] = bon_commande.total_achat
    return context


def generate_bcf_pdf(bon_commande):
    """Rend le PDF fournisseur et renvoie les octets (non stocké)."""
    context = build_bcf_context(bon_commande)
    html = _render_html('bon_commande_fournisseur.html', context)
    return _html_to_pdf(html)
