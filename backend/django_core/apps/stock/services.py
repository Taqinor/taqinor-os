"""T8 — édition EN MASSE du catalogue produit (multi-sélection).

Toute la règle métier vit ici (les vues restent fines), bornée à la société de
l'utilisateur. Le PRIX D'ACHAT n'est JAMAIS modifié ni exposé (règle marges).
Les changements sont journalisés (audit logger).
"""
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger('stock.audit')

BULK_ACTIONS = {'set_price', 'set_warranty', 'set_category', 'set_brand'}


def _dec(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def apply_product_bulk(*, company, user, ids, op, params):
    """Applique une action en masse à une sélection de produits de la société.

    Renvoie {ok, updated, skipped:[{id,nom,reason}]}. Le prix d'achat reste
    intouché en toutes circonstances."""
    from .models import Produit, Categorie

    if op not in BULK_ACTIONS:
        raise ValueError("Action en masse inconnue.")

    produits = list(Produit.objects.filter(company=company, id__in=ids))
    updated, skipped = 0, []

    def skip(p, reason):
        skipped.append({'id': p.id, 'nom': p.nom, 'reason': reason})

    # Pré-validation par action.
    categorie = None
    if op == 'set_price':
        mode = params.get('mode')
        valeur = _dec(params.get('valeur'))
        if mode not in ('percent', 'fixed') or valeur is None:
            raise ValueError("Prix invalide (mode percent/fixed + valeur requise).")
    elif op == 'set_category':
        cid = params.get('categorie_id')
        categorie = Categorie.objects.filter(id=cid, company=company).first()
        if cid not in (None, '', 'null') and categorie is None:
            raise ValueError("Catégorie introuvable dans cette société.")

    for p in produits:
        if op == 'set_price':
            if mode == 'percent':
                new_price = (p.prix_vente or Decimal('0')) * (Decimal('1') + valeur / Decimal('100'))
            else:
                new_price = valeur
            if new_price < 0:
                skip(p, "prix négatif refusé")
                continue
            p.prix_vente = new_price.quantize(Decimal('0.01'))
            p.save(update_fields=['prix_vente'])  # prix_achat JAMAIS touché
            updated += 1

        elif op == 'set_warranty':
            fields = []
            if 'garantie_mois' in params and params['garantie_mois'] not in ('', None):
                p.garantie_mois = int(params['garantie_mois'])
                fields.append('garantie_mois')
            if ('garantie_production_mois' in params
                    and params['garantie_production_mois'] not in ('', None)):
                p.garantie_production_mois = int(params['garantie_production_mois'])
                fields.append('garantie_production_mois')
            if not fields:
                skip(p, "aucune durée fournie")
                continue
            p.save(update_fields=fields)
            updated += 1

        elif op == 'set_category':
            p.categorie = categorie
            p.save(update_fields=['categorie'])
            updated += 1

        elif op == 'set_brand':
            p.marque = (params.get('marque') or '').strip() or None
            p.save(update_fields=['marque'])
            updated += 1

    logger.info('BULK %s sur %d produit(s) par user=%s (company=%s)',
                op, updated, getattr(user, 'username', '?'), company.id)
    return {'ok': True, 'updated': updated, 'skipped': skipped,
            'total': len(produits)}


# ── Export Excel d'une sélection de produits ────────────────────────────────
PRODUCT_EXPORT_HEADERS = [
    'Nom', 'SKU', 'Marque', 'Catégorie', 'Prix vente HT', 'Quantité',
    'Seuil alerte', 'Garantie (mois)', 'Garantie production (mois)',
]


def export_products_xlsx(produits):
    """Réponse .xlsx pour une sélection de produits (prix d'achat EXCLU)."""
    from apps.crm.exports import build_xlsx_response
    rows = [[
        p.nom, p.sku or '', p.marque or '',
        getattr(p.categorie, 'nom', '') or '',
        str(p.prix_vente), p.quantite_stock, p.seuil_alerte,
        p.garantie_mois or '', p.garantie_production_mois or '',
    ] for p in produits]
    return build_xlsx_response(
        'produits.xlsx', PRODUCT_EXPORT_HEADERS, rows, sheet_title='Produits')
