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


# ── N13 — Approvisionnement : besoin matériel par chantier ───────────────────
# Lecture seule sur installations.Installation (aucune migration installations).
# On dérive le besoin des LIGNES DU DEVIS source du chantier, on confronte au
# stock disponible (Produit.quantite_stock) et on signale les manques. Une
# action amont peut transformer ces manques en un BonCommandeFournisseur
# brouillon. Le prix d'achat reste INTERNE (jamais sur un document client).

def apply_inventory_count(*, company, user, motif, lignes):
    """N16 — inventaire : pose un comptage physique par produit et enregistre
    l'écart en MouvementStock (AJUSTEMENT). Renvoie {ajustes, inchanges,
    mouvements:[…]}. Le stock devient la quantité comptée ; rien n'est touché
    quand le comptage = stock actuel. Tout est scopé à la société."""
    from django.db import transaction
    from .models import Produit, MouvementStock

    motif = (motif or '').strip()
    result = {'ajustes': 0, 'inchanges': 0, 'mouvements': []}
    with transaction.atomic():
        for ligne in (lignes or []):
            pid = ligne.get('produit')
            try:
                compte = int(ligne.get('quantite_comptee'))
            except (TypeError, ValueError):
                continue
            if compte < 0:
                continue
            produit = Produit.objects.select_for_update().filter(
                id=pid, company=company).first()
            if produit is None:
                continue
            avant = produit.quantite_stock
            if compte == avant:
                result['inchanges'] += 1
                continue
            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT,
                quantite=compte, quantite_avant=avant, quantite_apres=compte,
                reference='INVENTAIRE',
                note=f'Inventaire — comptage {compte} (écart {compte - avant})'
                     + (f' · {motif}' if motif else ''),
                created_by=user)
            produit.quantite_stock = compte
            produit.save(update_fields=['quantite_stock'])
            result['ajustes'] += 1
            result['mouvements'].append({
                'produit': produit.id, 'avant': avant, 'apres': compte})
    logger.info('INVENTAIRE %d ajustement(s) par user=%s (company=%s)',
                result['ajustes'], getattr(user, 'username', '?'), company.id)
    return result


def compute_besoin_materiel(installation):
    """Agrège les besoins matériel d'un chantier depuis son devis source.

    Renvoie une liste de dicts triés par désignation :
      {produit, produit_id, sku, designation, requis, disponible,
       manque, fournisseur_id, fournisseur_nom}
    `manque` = max(requis - disponible, 0). Un manque > 0 = pénurie.

    Les lignes sans produit (libre) sont ignorées : on ne peut pas
    réapprovisionner un article qui n'est pas au catalogue.
    """
    devis = installation.devis
    if devis is None:
        return []
    besoins = {}
    for ligne in devis.lignes.select_related('produit', 'produit__fournisseur'):
        produit = ligne.produit
        if produit is None:
            continue
        try:
            requis = int(ligne.quantite)
        except (TypeError, ValueError):
            requis = int(float(ligne.quantite))
        entry = besoins.get(produit.id)
        if entry is None:
            besoins[produit.id] = {
                'produit': produit,
                'produit_id': produit.id,
                'sku': produit.sku or '',
                'designation': produit.nom,
                'requis': requis,
                'disponible': produit.quantite_stock,
                'fournisseur_id': produit.fournisseur_id,
                'fournisseur_nom': (produit.fournisseur.nom
                                    if produit.fournisseur_id else None),
            }
        else:
            entry['requis'] += requis
    out = []
    for entry in besoins.values():
        entry['manque'] = max(entry['requis'] - entry['disponible'], 0)
        out.append(entry)
    out.sort(key=lambda e: e['designation'].lower())
    return out


def draft_bcf_for_shortfall(installation, fournisseur, user, company):
    """Crée un BonCommandeFournisseur BROUILLON pour les manques du chantier.

    Une ligne BCF par produit en pénurie (quantité = le manque), au prix
    d'achat catalogue (interne). Renvoie (bon, lignes_count). Lève ValueError
    s'il n'y a aucun manque à commander.
    """
    from apps.ventes.utils.references import create_with_reference
    from .models import BonCommandeFournisseur, LigneBonCommandeFournisseur

    besoins = compute_besoin_materiel(installation)
    manquants = [b for b in besoins if b['manque'] > 0]
    if not manquants:
        raise ValueError('Aucun manque à commander pour ce chantier.')

    def _save(ref):
        bon = BonCommandeFournisseur.objects.create(
            company=company,
            reference=ref,
            fournisseur=fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON,
            note=(f'Besoin matériel — chantier {installation.reference}'),
            created_by=user,
        )
        for b in manquants:
            produit = b['produit']
            LigneBonCommandeFournisseur.objects.create(
                bon_commande=bon,
                produit=produit,
                quantite=b['manque'],
                prix_achat_unitaire=produit.prix_achat,
            )
        return bon

    bon = create_with_reference(BonCommandeFournisseur, 'BCF', company, _save)
    return bon, len(manquants)


def resolve_fournisseur(company, fournisseur_id, installation):
    """Choisit le fournisseur du brouillon : explicite, sinon celui du premier
    produit en pénurie, sinon None (le caller décide quoi en faire)."""
    from .models import Fournisseur
    if fournisseur_id:
        return Fournisseur.objects.filter(
            id=fournisseur_id, company=company).first()
    for b in compute_besoin_materiel(installation):
        if b['manque'] > 0 and b['fournisseur_id']:
            return Fournisseur.objects.filter(
                id=b['fournisseur_id'], company=company).first()
    return None
