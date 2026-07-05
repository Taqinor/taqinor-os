"""PDF du bon de commande FOURNISSEUR (N12) — INTERNE.

Réutilise l'approche WeasyPrint des factures (Jinja2 → HTML → PDF). Ce
document est destiné au fournisseur : il affiche légitimement les PRIX
D'ACHAT, car c'est le prix qu'on paie au fournisseur. Il ne doit JAMAIS être
exposé comme document client.
"""
from apps.ventes.utils.pdf import _company_context, _render_html, _html_to_pdf


def build_bcf_context(bon_commande):
    """Contexte de rendu pour le PDF fournisseur."""
    from ..models import PrixFournisseur

    context = _company_context(company=bon_commande.company)
    context['bc'] = bon_commande
    lignes = list(bon_commande.lignes.select_related('produit').all())
    context['lignes'] = lignes
    context['total_achat'] = bon_commande.total_achat

    # XPUR14 — code article fournisseur (imprimé sur le PDF pour éviter les
    # erreurs de préparation côté fournisseur). Best-effort : absent =
    # colonne vide (comportement historique inchangé).
    produit_ids = [ligne.produit_id for ligne in lignes if ligne.produit_id]
    refs = {}
    if produit_ids and bon_commande.fournisseur_id:
        refs = dict(
            PrixFournisseur.objects.filter(
                produit_id__in=produit_ids,
                fournisseur_id=bon_commande.fournisseur_id,
            ).exclude(ref_produit_fournisseur='')
            .values_list('produit_id', 'ref_produit_fournisseur'))
    context['ref_produit_fournisseur'] = {
        ligne.id: refs.get(ligne.produit_id, '') for ligne in lignes
    }
    # ZPUR8 — champs « Other Information » imprimés sur le PDF BCF (acheteur,
    # réf. fournisseur, incoterm/conditions de paiement, note de bas de
    # page). Vide = comportement historique inchangé (rien à afficher).
    acheteur_nom = ''
    if bon_commande.acheteur_id:
        acheteur = bon_commande.acheteur
        acheteur_nom = acheteur.get_full_name() or acheteur.username
    context['acheteur_nom'] = acheteur_nom
    context['ref_fournisseur'] = bon_commande.ref_fournisseur or ''
    context['incoterm'] = bon_commande.incoterm or ''
    context['conditions_paiement'] = bon_commande.conditions_paiement or ''
    context['note_bas_page'] = bon_commande.note_bas_page or ''
    return context


def generate_bcf_pdf(bon_commande):
    """Rend le PDF fournisseur et renvoie les octets (non stocké)."""
    context = build_bcf_context(bon_commande)
    html = _render_html('bon_commande_fournisseur.html', context)
    return _html_to_pdf(html)
