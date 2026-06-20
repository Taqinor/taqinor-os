"""T8 — édition EN MASSE du catalogue produit (multi-sélection).

Toute la règle métier vit ici (les vues restent fines), bornée à la société de
l'utilisateur. Le PRIX D'ACHAT n'est JAMAIS modifié ni exposé (règle marges).
Les changements sont journalisés (audit logger).
"""
import logging
from decimal import Decimal, InvalidOperation, ROUND_CEILING

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


# ── N15 — Stock multi-emplacements (dépôt principal + camionnette …) ─────────
# Le total `Produit.quantite_stock` reste canonique et inchangé ; cette couche
# ventile ce total entre emplacements. L'emplacement PRINCIPAL détient le reste
# (total − somme des non principaux), donc tout le stock existant est par défaut
# au dépôt principal et le comportement actuel ne change pas.

def ensure_emplacements(company):
    """Crée le dépôt principal + la camionnette si la société n'a encore aucun
    emplacement (idempotent, additif). Renvoie l'emplacement principal."""
    from .models import EmplacementStock
    if company is None:
        return None
    qs = EmplacementStock.objects.filter(company=company)
    if not qs.exists():
        EmplacementStock.objects.create(
            company=company, nom='Dépôt principal', is_principal=True, ordre=0)
        EmplacementStock.objects.create(
            company=company, nom='Camionnette', is_principal=False, ordre=10)
    return qs.filter(is_principal=True).first()


def stock_breakdown(produit):
    """Ventilation du stock d'un produit par emplacement (non archivés).

    Renvoie [{emplacement_id, emplacement_nom, is_principal, quantite}] — le
    principal détient total − somme(non principaux)."""
    from .models import EmplacementStock
    company = produit.company
    ensure_emplacements(company)
    emplacements = list(EmplacementStock.objects.filter(
        company=company, archived=False))
    records = {se.emplacement_id: se.quantite
               for se in produit.stocks_emplacement.all()}
    autres = sum(records.get(e.id, 0)
                 for e in emplacements if not e.is_principal)
    out = []
    for e in emplacements:
        # ERR94 — le principal détient le reste (total − non principaux), mais
        # ne doit JAMAIS afficher une quantité négative : on le plafonne à 0
        # si le total est tombé sous l'allocation ventilée.
        qte = max(produit.quantite_stock - autres, 0) if e.is_principal \
            else records.get(e.id, 0)
        out.append({
            'emplacement_id': e.id,
            'emplacement_nom': e.nom,
            'is_principal': e.is_principal,
            'quantite': qte,
        })
    return out


def stock_breakdown_map(company):
    """Ventilation par emplacement pour TOUS les produits d'une société, en une
    passe (évite un N+1 quand la liste catalogue veut la répartition par produit).

    Renvoie {produit_id: [{emplacement_id, emplacement_nom, is_principal,
    quantite}]} — le principal détient total − somme(non principaux), comme
    `stock_breakdown` mais sans requête par produit."""
    from .models import EmplacementStock, Produit, StockEmplacement
    if company is None:
        return {}
    ensure_emplacements(company)
    emplacements = list(EmplacementStock.objects.filter(
        company=company, archived=False))
    # {produit_id: {emplacement_id: quantite}} pour les non principaux
    records = {}
    for se in StockEmplacement.objects.filter(
            produit__company=company, emplacement__archived=False):
        records.setdefault(se.produit_id, {})[se.emplacement_id] = se.quantite
    out = {}
    for p in Produit.objects.filter(company=company).only('id', 'quantite_stock'):
        rec = records.get(p.id, {})
        autres = sum(rec.get(e.id, 0) for e in emplacements if not e.is_principal)
        out[p.id] = [{
            'emplacement_id': e.id,
            'emplacement_nom': e.nom,
            'is_principal': e.is_principal,
            # ERR94 — principal plafonné à 0, jamais négatif (cf. stock_breakdown).
            'quantite': max(p.quantite_stock - autres, 0) if e.is_principal
            else rec.get(e.id, 0),
        } for e in emplacements]
    return out


def transfer_stock(*, company, user, produit_id, source_id, destination_id,
                   quantite, note=''):
    """Transfère `quantite` d'un produit de l'emplacement source vers la
    destination. Crée un TransfertStock (le « transfer record »). Ne change
    JAMAIS le total `Produit.quantite_stock`. Lève ValueError si invalide."""
    from django.db import transaction
    from .models import (
        Produit, EmplacementStock, StockEmplacement, TransfertStock)

    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité doit être positive.')
    if str(source_id) == str(destination_id):
        raise ValueError('La source et la destination doivent être différentes.')

    with transaction.atomic():
        produit = Produit.objects.select_for_update().filter(
            id=produit_id, company=company).first()
        if produit is None:
            raise ValueError('Produit introuvable dans cette société.')
        ensure_emplacements(company)
        emps = {e.id: e for e in EmplacementStock.objects.filter(
            company=company, archived=False)}
        try:
            source = emps[int(source_id)]
            destination = emps[int(destination_id)]
        except (KeyError, TypeError, ValueError):
            raise ValueError('Emplacement introuvable dans cette société.')

        records = {se.emplacement_id: se for se in
                   produit.stocks_emplacement.select_for_update()}
        non_principal_sum = sum(
            se.quantite for eid, se in records.items()
            if eid in emps and not emps[eid].is_principal)

        def current_qty(emp):
            if emp.is_principal:
                return produit.quantite_stock - non_principal_sum
            se = records.get(emp.id)
            return se.quantite if se else 0

        if quantite > current_qty(source):
            raise ValueError(
                f'Quantité insuffisante à « {source.nom} » '
                f'({current_qty(source)} disponible).')

        if not source.is_principal:
            se, _ = StockEmplacement.objects.select_for_update().get_or_create(
                produit=produit, emplacement=source,
                defaults={'company': company, 'quantite': 0})
            se.quantite -= quantite
            se.save(update_fields=['quantite'])
        if not destination.is_principal:
            se, _ = StockEmplacement.objects.get_or_create(
                produit=produit, emplacement=destination,
                defaults={'company': company, 'quantite': 0})
            se.quantite += quantite
            se.save(update_fields=['quantite'])

        transfert = TransfertStock.objects.create(
            company=company, produit=produit, source=source,
            destination=destination, quantite=quantite,
            note=(note or '').strip(), created_by=user)
    logger.info('TRANSFERT %d × produit=%s %s→%s par user=%s (company=%s)',
                quantite, produit_id, source_id, destination_id,
                getattr(user, 'username', '?'), company.id)
    return transfert


# ── N17 — Listes de prix multi-fournisseurs par SKU ──────────────────────────
# Prix d'achat INTERNE par (produit, fournisseur) + date du dernier achat.
# Sert à proposer le fournisseur le moins cher en rédigeant un bon de commande.

def cheapest_prix_fournisseur(produit):
    """Renvoie le PrixFournisseur le moins cher (prix > 0) pour ce produit, ou
    None s'il n'existe aucun prix multi-fournisseur renseigné."""
    return (produit.prix_fournisseurs.filter(prix_achat__gt=0)
            .select_related('fournisseur').order_by('prix_achat').first())


def record_purchase_price(*, company, produit, fournisseur, prix_achat, date):
    """Upsert du prix d'achat (produit, fournisseur) + date du dernier achat.
    Appelé à la réception d'un BCF. INTERNE (jamais client-facing)."""
    from decimal import Decimal
    from .models import PrixFournisseur
    if fournisseur is None or produit is None:
        return None
    prix = _dec(prix_achat) or Decimal('0')
    obj, created = PrixFournisseur.objects.get_or_create(
        produit=produit, fournisseur=fournisseur,
        defaults={'company': company, 'prix_achat': prix,
                  'date_dernier_achat': date})
    if not created:
        obj.prix_achat = prix
        obj.date_dernier_achat = date
        if obj.company_id is None:
            obj.company = company
        obj.save(update_fields=['prix_achat', 'date_dernier_achat', 'company'])
    return obj


# ── N18 — Valorisation du stock par emplacement (coût moyen d'achat) ──────────
# Coût moyen pondéré issu de l'historique d'achat (réceptions de BCF) ; à défaut
# le prix d'achat catalogue. Valorisation = quantité par emplacement × coût
# moyen. INTERNE uniquement (les prix d'achat ne sont jamais client-facing).

def average_cost_with_source(produit):
    """Coût moyen d'achat pondéré + sa SOURCE.

    Renvoie (cout, source) où source vaut 'achats' (dérivé des réceptions de
    bons de commande fournisseur) ou 'catalogue' (repli sur prix_achat quand
    aucun achat reçu). INTERNE."""
    from .models import LigneBonCommandeFournisseur
    lignes = LigneBonCommandeFournisseur.objects.filter(
        produit=produit, quantite_recue__gt=0).values_list(
        'quantite_recue', 'prix_achat_unitaire')
    total_q, total_v = 0, Decimal('0')
    for q, pu in lignes:
        total_q += q
        total_v += q * (pu or Decimal('0'))
    if total_q:
        return (total_v / total_q).quantize(Decimal('0.01')), 'achats'
    return (produit.prix_achat or Decimal('0')), 'catalogue'


def average_cost(produit):
    """Coût moyen d'achat pondéré d'un produit, depuis l'historique des
    réceptions de bons de commande fournisseur ; repli sur le prix d'achat
    catalogue si aucun achat reçu. INTERNE."""
    return average_cost_with_source(produit)[0]


def stock_valuation_by_location(company):
    """Valorisation du stock par emplacement au coût moyen d'achat (N18).

    Renvoie {par_emplacement:[{emplacement_id, emplacement_nom, is_principal,
    quantite, valeur}], total, lignes:[{produit_id, sku, designation,
    emplacement_nom, quantite, cout_moyen, valeur}]}. INTERNE — ne jamais
    exposer dans un contexte client."""
    from .models import Produit, EmplacementStock
    ensure_emplacements(company)
    emplacements = list(EmplacementStock.objects.filter(
        company=company, archived=False))
    totals = {e.id: {'emplacement_id': e.id, 'emplacement_nom': e.nom,
                     'is_principal': e.is_principal, 'quantite': 0,
                     'valeur': Decimal('0')} for e in emplacements}
    lignes = []
    grand_total = Decimal('0')
    produits = (Produit.objects.filter(company=company, is_archived=False)
                .prefetch_related('stocks_emplacement'))
    for p in produits:
        cout, source = average_cost_with_source(p)
        for b in stock_breakdown(p):
            if b['quantite'] == 0:
                continue
            valeur = (cout * b['quantite']).quantize(Decimal('0.01'))
            t = totals.get(b['emplacement_id'])
            if t is not None:
                t['quantite'] += b['quantite']
                t['valeur'] += valeur
            grand_total += valeur
            lignes.append({
                'produit_id': p.id, 'sku': p.sku or '', 'designation': p.nom,
                'emplacement_nom': b['emplacement_nom'],
                'quantite': b['quantite'], 'cout_moyen': cout, 'valeur': valeur,
                'source': source,
            })
    lignes.sort(key=lambda x: (x['designation'].lower(), x['emplacement_nom']))
    return {'par_emplacement': list(totals.values()),
            'total': grand_total, 'lignes': lignes}


VALORISATION_EXPORT_HEADERS = [
    'Produit', 'SKU', 'Emplacement', 'Quantité',
    'Coût moyen (HT)', 'Valeur (HT)', 'Source du coût',
]
_SOURCE_LABELS = {'achats': 'Achats reçus', 'catalogue': 'Prix catalogue'}


def export_valorisation_xlsx(company):
    """Réponse .xlsx de la valorisation du stock (admin/INTERNE — jamais
    client-facing). Reprend les lignes de stock_valuation_by_location."""
    from apps.crm.exports import build_xlsx_response
    data = stock_valuation_by_location(company)
    rows = [[
        ligne['designation'], ligne['sku'], ligne['emplacement_nom'],
        ligne['quantite'], str(ligne['cout_moyen']), str(ligne['valeur']),
        _SOURCE_LABELS.get(ligne.get('source'), ''),
    ] for ligne in data['lignes']]
    return build_xlsx_response(
        'valorisation.xlsx', VALORISATION_EXPORT_HEADERS, rows,
        sheet_title='Valorisation')


# ── N19 — Retour fournisseur : validation = décrément de stock (SORTIE) ───────

def apply_retour_fournisseur(retour, user):
    """Valide un retour fournisseur : décrémente le stock (MouvementStock
    SORTIE) pour chaque ligne, puis passe le retour à « validé ». Lève
    ValueError si le retour n'est pas en brouillon ou est vide. INTERNE."""
    from django.db import transaction
    from .models import Produit, RetourFournisseur, MouvementStock
    if retour.statut != RetourFournisseur.Statut.BROUILLON:
        raise ValueError('Seul un retour en brouillon peut être validé.')
    lignes = list(retour.lignes.select_related('produit'))
    if not lignes:
        raise ValueError('Le retour ne contient aucune ligne.')
    with transaction.atomic():
        for ligne in lignes:
            # ERR24 — verrou de ligne produit dans la transaction pour que des
            # retours concurrents du même produit ne perdent pas de décrément.
            produit = (Produit.objects.select_for_update()
                       .get(pk=ligne.produit_id))
            qte_avant = produit.quantite_stock
            qte_apres = qte_avant - ligne.quantite
            MouvementStock.objects.create(
                company=retour.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=ligne.quantite, quantite_avant=qte_avant,
                quantite_apres=qte_apres, reference=retour.reference,
                note=f'Retour fournisseur {retour.reference}'
                     + (f' — {ligne.motif}' if ligne.motif else ''),
                created_by=user)
            produit.quantite_stock = qte_apres
            produit.save(update_fields=['quantite_stock'])
        retour.statut = RetourFournisseur.Statut.VALIDE
        retour.save(update_fields=['statut'])
    return retour


# ── G5 — Réception fournisseur (goods-in) : confirmation = ENTRÉE de stock ────
# La confirmation d'une réception incrémente le stock (MouvementStock ENTREE)
# pour chaque ligne reçue, avance `quantite_recue` sur la ligne de BCF et fait
# évoluer le statut du BCF vers reçu/partiellement reçu via ses quantités reçues
# existantes (`est_entierement_recu`). IDEMPOTENTE : une réception déjà confirmée
# ne re-crée jamais de mouvement. Mêmes règles que l'action `recevoir` du BCF.

def confirm_reception_fournisseur(reception, user):
    """Confirme une réception fournisseur : crée un MouvementStock ENTREE par
    ligne reçue, incrémente le stock + `quantite_recue` du BCF, puis avance le
    statut du BCF (reçu si entièrement reçu). Lève ValueError si la réception
    n'est pas en brouillon ou est vide. INTERNE."""
    from django.db import transaction
    from django.utils import timezone
    from .models import (
        ReceptionFournisseur, BonCommandeFournisseur, MouvementStock,
    )
    if reception.statut != ReceptionFournisseur.Statut.BROUILLON:
        # Idempotence : une réception déjà confirmée/annulée ne touche pas le
        # stock une seconde fois.
        raise ValueError(
            'Seule une réception en brouillon peut être confirmée.')
    lignes = list(reception.lignes.select_related('ligne_commande', 'produit'))
    if not lignes:
        raise ValueError('La réception ne contient aucune ligne.')

    today = timezone.now().date()
    bc = reception.bon_commande
    with transaction.atomic():
        for ligne in lignes:
            qte = int(ligne.quantite or 0)
            if qte <= 0:
                continue
            # Plafonne au reste dû de la ligne de commande (jamais plus que
            # commandé — protège contre une saisie incohérente, idempotence).
            ligne_cmd = ligne.ligne_commande
            ligne_cmd.refresh_from_db()
            qte = min(qte, ligne_cmd.quantite_restante)
            if qte <= 0:
                continue
            produit = ligne.produit
            produit.refresh_from_db()
            qte_avant = produit.quantite_stock
            qte_apres = qte_avant + qte
            MouvementStock.objects.create(
                company=reception.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=qte, quantite_avant=qte_avant,
                quantite_apres=qte_apres, reference=reception.reference,
                note=f'Réception {reception.reference}'
                     + (f' (BCF {bc.reference})' if bc else ''),
                created_by=user)
            produit.quantite_stock = qte_apres
            produit.save(update_fields=['quantite_stock'])
            ligne_cmd.quantite_recue += qte
            ligne_cmd.save(update_fields=['quantite_recue'])
            # N17 — mémorise le prix d'achat (interne) chez ce fournisseur.
            if bc is not None:
                record_purchase_price(
                    company=reception.company, produit=produit,
                    fournisseur=bc.fournisseur,
                    prix_achat=ligne_cmd.prix_achat_unitaire, date=today)
        reception.statut = ReceptionFournisseur.Statut.CONFIRME
        reception.recu_par = reception.recu_par or user
        reception.save(update_fields=['statut', 'recu_par'])
        # Avance le statut du BCF selon ses quantités reçues existantes.
        if bc is not None:
            bc.refresh_from_db()
            if bc.statut not in (
                BonCommandeFournisseur.Statut.ANNULE,
                BonCommandeFournisseur.Statut.RECU,
            ):
                if bc.est_entierement_recu:
                    bc.statut = BonCommandeFournisseur.Statut.RECU
                else:
                    # Une réception partielle confirmée laisse un BCF brouillon
                    # passer à « envoyé » (commande engagée, partiellement reçue).
                    bc.statut = BonCommandeFournisseur.Statut.ENVOYE
                bc.save(update_fields=['statut'])
    return reception


# ── G5 — Facture fournisseur / comptes à payer (AP) ──────────────────────────
# Le solde dû d'une facture = TTC − Σ paiements. Le statut de règlement est
# RECALCULÉ après chaque paiement (à payer / partiellement payée / payée). Les
# montants d'achat sont INTERNES (jamais client-facing).

def recompute_facture_fournisseur_statut(facture):
    """Recalcule le statut de règlement d'une facture fournisseur depuis ses
    paiements et le persiste. À payer si rien réglé, payée si le solde ≤ 0,
    sinon partiellement payée."""
    from decimal import Decimal
    from .models import FactureFournisseur
    paye = facture.total_paye
    ttc = facture.montant_ttc or Decimal('0')
    if paye <= Decimal('0'):
        statut = FactureFournisseur.Statut.A_PAYER
    elif paye >= ttc:
        statut = FactureFournisseur.Statut.PAYEE
    else:
        statut = FactureFournisseur.Statut.PARTIELLEMENT_PAYEE
    if facture.statut != statut:
        facture.statut = statut
        facture.save(update_fields=['statut'])
    return statut


# ── N14 — Réservé vs disponible : engagé-mais-non-consommé ───────────────────
# Une réservation de chantier (installations.StockReservation) ENGAGE le stock
# d'un SKU sans le décrémenter. Le « disponible » d'un produit en tient compte :
#   disponible = quantite_stock − somme(réservations actives non consommées).
# Les vues stock + alertes de stock bas s'appuient sur le disponible (N14). Le
# modèle de réservation vit dans installations (qui dépend déjà de stock) ; on
# l'importe PARESSEUSEMENT pour éviter toute dépendance d'app circulaire.

def reserved_quantity(produit):
    """Quantité de ce produit ENGAGÉE par des réservations de chantier actives
    et non encore consommées (0 si aucune). Lecture seule."""
    from django.db.models import Sum
    from apps.installations.models import StockReservation
    agg = (StockReservation.objects
           .filter(produit=produit, active=True, consomme=False)
           .aggregate(total=Sum('quantite')))
    return agg['total'] or 0


def reserved_quantities(company):
    """Map {produit_id: quantité réservée active} pour toute la société — un
    seul agrégat (évite un N+1 sur la liste produits). Lecture seule."""
    from django.db.models import Sum
    from apps.installations.models import StockReservation
    rows = (StockReservation.objects
            .filter(company=company, active=True, consomme=False)
            .values('produit_id')
            .annotate(total=Sum('quantite')))
    return {r['produit_id']: (r['total'] or 0) for r in rows}


def available_quantity(produit, reserved=None):
    """Disponible = stock total − réservé (engagé-mais-non-consommé). `reserved`
    peut être fourni (depuis `reserved_quantities`) pour éviter une requête."""
    if reserved is None:
        reserved = reserved_quantity(produit)
    return produit.quantite_stock - reserved


def _own_reservation_map(installation):
    """Map {produit_id: quantité} des réservations actives non consommées
    propres à CE chantier (pour ne pas les décompter de son propre disponible).
    """
    from apps.installations.models import StockReservation
    rows = (StockReservation.objects
            .filter(installation=installation, active=True, consomme=False)
            .values_list('produit_id', 'quantite'))
    return {pid: qte for pid, qte in rows}


def is_low_stock_available(produit, reserved=None):
    """Alerte de stock bas N14 : compare le DISPONIBLE (et non le stock brut) au
    seuil d'alerte. Un seuil ≤ 0 désactive l'alerte (comportement historique)."""
    if produit.seuil_alerte is None or produit.seuil_alerte <= 0:
        return False
    return available_quantity(produit, reserved) <= produit.seuil_alerte


def compute_besoin_materiel(installation):
    """Agrège les besoins matériel d'un chantier depuis son devis source.

    Renvoie une liste de dicts triés par désignation :
      {produit, produit_id, sku, designation, requis, disponible,
       reserve, manque, fournisseur_id, fournisseur_nom,
       fournisseur_min_id, fournisseur_min_nom, prix_achat_min}
    `disponible` = stock total − réservé (engagé non consommé). `manque` =
    max(requis − disponible, 0). Un manque > 0 = pénurie.
    `fournisseur_min_*` = fournisseur le moins cher (N17), s'il existe.

    Les lignes sans produit (libre) sont ignorées : on ne peut pas
    réapprovisionner un article qui n'est pas au catalogue.
    """
    devis = installation.devis
    if devis is None:
        return []
    # N14 — réservations actives de la société, et la part réservée par CE
    # chantier (pour ne pas la décompter deux fois de son propre disponible).
    reserved_all = reserved_quantities(installation.company)
    own_reserved = _own_reservation_map(installation)
    besoins = {}
    for ligne in devis.lignes.select_related('produit', 'produit__fournisseur'):
        produit = ligne.produit
        if produit is None:
            continue
        # ERR54 — une ligne fractionnaire (ex. 2,5 unités) exige un APPRO ARRONDI
        # AU SUPÉRIEUR (3, pas 2) : un int() tronquait et sous-commandait.
        try:
            requis = int(_dec(ligne.quantite).to_integral_value(rounding=ROUND_CEILING))
        except (AttributeError, InvalidOperation, TypeError, ValueError):
            requis = 0
        entry = besoins.get(produit.id)
        if entry is None:
            # Disponible pour CE chantier = stock total − réservé par les AUTRES
            # chantiers (engagé non consommé) ; sa propre réservation n'est pas
            # soustraite (sinon le besoin serait compté deux fois).
            reserve_autres = max(
                reserved_all.get(produit.id, 0)
                - own_reserved.get(produit.id, 0), 0)
            besoins[produit.id] = {
                'produit': produit,
                'produit_id': produit.id,
                'sku': produit.sku or '',
                'designation': produit.nom,
                'requis': requis,
                'disponible': produit.quantite_stock - reserve_autres,
                'reserve': reserved_all.get(produit.id, 0),
                'fournisseur_id': produit.fournisseur_id,
                'fournisseur_nom': (produit.fournisseur.nom
                                    if produit.fournisseur_id else None),
            }
        else:
            entry['requis'] += requis
    out = []
    for entry in besoins.values():
        entry['manque'] = max(entry['requis'] - entry['disponible'], 0)
        # N17 — fournisseur le moins cher (si une liste de prix existe).
        cheapest = cheapest_prix_fournisseur(entry['produit'])
        if cheapest is not None:
            entry['fournisseur_min_id'] = cheapest.fournisseur_id
            entry['fournisseur_min_nom'] = cheapest.fournisseur.nom
            entry['prix_achat_min'] = cheapest.prix_achat
        else:
            entry['fournisseur_min_id'] = None
            entry['fournisseur_min_nom'] = None
            entry['prix_achat_min'] = None
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
    """Choisit le fournisseur du brouillon : explicite, sinon (N17) le
    fournisseur le moins cher du premier produit en pénurie, sinon le
    fournisseur catalogue de ce produit, sinon None."""
    from .models import Fournisseur
    if fournisseur_id:
        return Fournisseur.objects.filter(
            id=fournisseur_id, company=company).first()
    for b in compute_besoin_materiel(installation):
        if b['manque'] <= 0:
            continue
        cible = b.get('fournisseur_min_id') or b.get('fournisseur_id')
        if cible:
            return Fournisseur.objects.filter(
                id=cible, company=company).first()
    return None
