"""T8 — édition EN MASSE du catalogue produit (multi-sélection).

Toute la règle métier vit ici (les vues restent fines), bornée à la société de
l'utilisateur. Le PRIX D'ACHAT n'est JAMAIS modifié ni exposé (règle marges).
Les changements sont journalisés (audit logger).
"""
import logging
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from django.db import models

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
    aucun achat reçu). INTERNE.

    FG67/DC38 — le coût intègre les FRAIS ANNEXES (fret/douane/TVA import/
    transit) de chaque ligne via le coût débarqué unitaire : aucun champ de
    coût parallèle, les frais sont repliés dans CE même coût moyen. Une ligne
    sans frais annexes (0) garde exactement le comportement historique."""
    from .models import LigneBonCommandeFournisseur
    lignes = LigneBonCommandeFournisseur.objects.filter(
        produit=produit, quantite_recue__gt=0).values_list(
        'quantite_recue', 'prix_achat_unitaire', 'quantite', 'frais_annexes')
    total_q, total_v = 0, Decimal('0')
    for q_recue, pu, q_ligne, frais in lignes:
        pu = pu or Decimal('0')
        frais = frais or Decimal('0')
        # Coût débarqué unitaire : frais annexes répartis sur la quantité
        # COMMANDÉE de la ligne (q_ligne), valorisés sur la quantité REÇUE.
        if q_ligne and frais:
            pu = pu + (frais / Decimal(str(q_ligne)))
        total_q += q_recue
        total_v += q_recue * pu
    if total_q:
        return (total_v / total_q).quantize(Decimal('0.01')), 'achats'
    return (produit.prix_achat or Decimal('0')), 'catalogue'


def average_cost(produit):
    """Coût moyen d'achat pondéré d'un produit, depuis l'historique des
    réceptions de bons de commande fournisseur ; repli sur le prix d'achat
    catalogue si aucun achat reçu. INTERNE."""
    return average_cost_with_source(produit)[0]


# ── FG67 — Méthode de valorisation : coût moyen pondéré (défaut) ou FIFO ──────
# La méthode est un réglage société (CompanyProfile.stock_valuation_method,
# 'wavg' par défaut). Le toggle CHAMP vit dans `parametres` (foundation) ; ce
# module le LIT prudemment via getattr et retombe sur 'wavg' si le champ
# n'existe pas encore — on ne crée aucun champ hors de stock. INTERNE.

VALUATION_WAVG = 'wavg'
VALUATION_FIFO = 'fifo'


def stock_valuation_method(company):
    """Méthode de valorisation choisie par la société : 'wavg' (coût moyen
    pondéré, défaut) ou 'fifo'. Lit CompanyProfile.stock_valuation_method si
    présent (couche parametres), repli prudent sur 'wavg' sinon. Lecture seule."""
    if company is None:
        return VALUATION_WAVG
    try:
        from apps.parametres.models_company import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # parametres absent / champ pas encore migré
        profile = None
    method = getattr(profile, 'stock_valuation_method', None)
    return method if method in (VALUATION_WAVG, VALUATION_FIFO) else VALUATION_WAVG


def fifo_cost_with_source(produit):
    """Coût FIFO unitaire d'un produit + sa SOURCE (FG67).

    FIFO : le stock restant est valorisé aux coûts d'achat débarqués des
    réceptions les PLUS RÉCENTES (les premières entrées sont consommées en
    premier ; il reste donc les dernières). On reconstitue le coût unitaire des
    `quantite_stock` dernières unités reçues. Repli sur le prix d'achat
    catalogue ('catalogue') si aucune réception. INTERNE — jamais client-facing.

    Renvoie (cout_unitaire_moyen_des_couches_restantes, source)."""
    from .models import LigneBonCommandeFournisseur
    # Couches d'entrée, de la plus récente à la plus ancienne (FIFO -> il reste
    # les dernières entrées). On valorise au coût débarqué unitaire.
    lignes = (LigneBonCommandeFournisseur.objects
              .filter(produit=produit, quantite_recue__gt=0)
              .order_by('-bon_commande__date_creation', '-id'))
    restant = produit.quantite_stock or 0
    if restant <= 0:
        return (produit.prix_achat or Decimal('0')), 'catalogue'
    pris_q, pris_v = 0, Decimal('0')
    for ligne in lignes:
        if restant <= 0:
            break
        couche_q = min(ligne.quantite_recue, restant)
        pris_q += couche_q
        pris_v += couche_q * ligne.cout_unitaire_debarque
        restant -= couche_q
    if pris_q == 0:
        return (produit.prix_achat or Decimal('0')), 'catalogue'
    cout = (pris_v / pris_q).quantize(Decimal('0.01'))
    return cout, 'achats'


def valuation_cost_with_source(produit, method=None):
    """Coût unitaire de valorisation d'un produit selon la méthode société
    (FG67). 'wavg' -> coût moyen pondéré débarqué ; 'fifo' -> couches FIFO
    restantes. Si `method` n'est pas fourni, on lit le réglage société.
    Renvoie (cout, source). INTERNE."""
    if method is None:
        method = stock_valuation_method(produit.company)
    if method == VALUATION_FIFO:
        return fifo_cost_with_source(produit)
    return average_cost_with_source(produit)


# ── DC28 — UN seul résolveur du coût d'achat courant ─────────────────────────
# Précédence DOCUMENTÉE, une seule porte d'entrée pour marge / auto-fill /
# job-costing (ils lisent CET accesseur, jamais Produit.prix_achat en direct) :
#
#   1. accord de prix fournisseur actif (modèle à venir : aucun accord
#      n'existe encore au catalogue → étape inerte aujourd'hui, point
#      d'extension réservé) ;
#   2. PrixFournisseur — le DERNIER PAYÉ (date_dernier_achat la plus récente,
#      prix > 0) chez n'importe quel fournisseur de ce produit ;
#   3. repli : Produit.prix_achat (prix d'achat catalogue).
#
# INTERNE — jamais client-facing (règle marges). Renvoie (cout, source) où
# source ∈ {'accord', 'prix_fournisseur', 'catalogue'}.

def cout_achat_courant_with_source(produit):
    """Coût d'achat courant d'un produit + sa SOURCE, selon la précédence DC28.

    Renvoie ``(Decimal, source)`` avec ``source`` ∈ {'accord',
    'prix_fournisseur', 'catalogue'}. Accesseur UNIQUE — marge / auto-fill /
    job-costing passent par ici. INTERNE."""
    # 1. Accord de prix actif — point d'extension réservé (aucun modèle d'accord
    #    n'existe encore ; quand il arrivera, le brancher ici en priorité).
    # 2. PrixFournisseur : dernier payé (date la plus récente), prix > 0.
    dernier = (produit.prix_fournisseurs
               .filter(prix_achat__gt=0)
               .order_by('-date_dernier_achat', '-id')
               .first())
    if dernier is not None:
        return (Decimal(str(dernier.prix_achat)), 'prix_fournisseur')
    # 3. Repli catalogue.
    return (produit.prix_achat or Decimal('0'), 'catalogue')


def cout_achat_courant(produit):
    """Coût d'achat courant d'un produit (Decimal), selon la précédence DC28.
    Accesseur UNIQUE pour marge / auto-fill / job-costing. INTERNE."""
    return cout_achat_courant_with_source(produit)[0]


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
    # FG67 — méthode société (coût moyen pondéré débarqué ou FIFO), résolue une
    # seule fois pour toute la passe.
    method = stock_valuation_method(company)
    produits = (Produit.objects.filter(company=company, is_archived=False)
                .prefetch_related('stocks_emplacement'))
    for p in produits:
        cout, source = valuation_cost_with_source(p, method=method)
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


# ── DC34 — Référentiel sous-traitant UNIFIÉ + AP par la chaîne standard ──────
# Écritures cross-app : les autres apps (installations) créent/mettent à jour un
# sous-traitant (Fournisseur type=service + SousTraitantProfile) et ses comptes à
# payer (FactureFournisseur/PaiementFournisseur) à travers ces services, jamais
# en important apps.stock.models directement. La société est TOUJOURS posée côté
# serveur (jamais lue du corps) et le profil hérite de la société du fournisseur.

def create_sous_traitant(*, company, user=None, nom, metier='autre',
                         contact_personne=None, email=None, telephone=None,
                         adresse=None, ice=None, identifiant_fiscal=None,
                         rc=None, rib=None, actif=True, note=None):
    """DC34 — crée un sous-traitant = Fournisseur(type='service') + son
    SousTraitantProfile. Société posée serveur (fournisseur ET profil).
    Renvoie le Fournisseur créé."""
    from .models import Fournisseur, SousTraitantProfile
    fournisseur = Fournisseur.objects.create(
        company=company, nom=nom, type=Fournisseur.Type.SERVICE,
        contact_personne=contact_personne, email=email or None,
        telephone=telephone, adresse=adresse, ice=ice,
        identifiant_fiscal=identifiant_fiscal, rc=rc, rib=rib)
    SousTraitantProfile.objects.create(
        company=company, fournisseur=fournisseur, metier=metier,
        actif=actif, note=note, created_by=user)
    return fournisseur


def update_sous_traitant(*, fournisseur, metier=None, actif=None, note=None,
                         **identity):
    """DC34 — met à jour un sous-traitant : champs d'identité sur le
    Fournisseur, champs propres (métier/actif/note) sur le profil satellite
    (créé s'il manque). Renvoie le Fournisseur."""
    from .models import SousTraitantProfile
    id_fields = []
    for champ in ('nom', 'contact_personne', 'email', 'telephone', 'adresse',
                  'ice', 'identifiant_fiscal', 'rc', 'rib'):
        if champ in identity and identity[champ] is not None:
            setattr(fournisseur, champ, identity[champ])
            id_fields.append(champ)
    if id_fields:
        fournisseur.save(update_fields=id_fields)
    profil, _ = SousTraitantProfile.objects.get_or_create(
        fournisseur=fournisseur,
        defaults={'company': fournisseur.company})
    prof_fields = []
    if metier is not None:
        profil.metier = metier
        prof_fields.append('metier')
    if actif is not None:
        profil.actif = actif
        prof_fields.append('actif')
    if note is not None:
        profil.note = note
        prof_fields.append('note')
    if prof_fields:
        prof_fields.append('date_modification')
        profil.save(update_fields=prof_fields)
    return fournisseur


def create_facture_sous_traitant(*, company, user=None, fournisseur,
                                 ref_fournisseur=None, date_facture=None,
                                 date_echeance=None, montant_ht=0,
                                 montant_tva=0, montant_ttc=0, note=None):
    """DC34 — crée une facture ENTRANTE de sous-traitant via la chaîne AP
    standard (FactureFournisseur), jamais un modèle parallèle. Référence
    anti-collision (préfixe FF), société + créateur posés serveur. Renvoie la
    FactureFournisseur."""
    from decimal import Decimal
    from apps.ventes.utils.references import create_with_reference
    from .models import FactureFournisseur

    def _save(reference):
        return FactureFournisseur.objects.create(
            company=company, reference=reference, fournisseur=fournisseur,
            ref_fournisseur=ref_fournisseur, date_facture=date_facture,
            date_echeance=date_echeance,
            montant_ht=montant_ht or Decimal('0'),
            montant_tva=montant_tva or Decimal('0'),
            montant_ttc=montant_ttc or Decimal('0'),
            statut=FactureFournisseur.Statut.A_PAYER, note=note,
            created_by=user)

    return create_with_reference(FactureFournisseur, 'FF', company, _save)


def add_paiement_sous_traitant(*, company, user=None, facture, montant,
                               date_paiement=None, mode='virement', note=None):
    """DC34 — impute un règlement sur une facture sous-traitant via la chaîne AP
    standard (PaiementFournisseur) et recalcule le statut de la facture. On
    n'impute jamais plus que le solde dû. Renvoie le PaiementFournisseur."""
    from decimal import Decimal, InvalidOperation
    from django.db import transaction
    from .models import PaiementFournisseur

    try:
        montant_dec = Decimal(str(montant))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Montant de paiement invalide.')
    if montant_dec <= 0:
        raise ValueError('Le montant du paiement doit être positif.')
    if montant_dec > facture.solde_du:
        raise ValueError('Le paiement dépasse le reste à payer.')
    with transaction.atomic():
        paiement = PaiementFournisseur.objects.create(
            company=company, facture=facture, montant=montant_dec,
            date_paiement=date_paiement, mode=mode, note=note,
            created_by=user)
        facture.refresh_from_db()
        recompute_facture_fournisseur_statut(facture)
    return paiement


def delete_paiement_sous_traitant(paiement):
    """DC34 — supprime un règlement sous-traitant et recalcule le statut de sa
    facture (chaîne AP standard)."""
    from django.db import transaction
    facture = paiement.facture
    with transaction.atomic():
        paiement.delete()
        facture.refresh_from_db()
        recompute_facture_fournisseur_statut(facture)


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
    from apps.installations.selectors import reserved_quantity_for_produit
    return reserved_quantity_for_produit(produit)


def reserved_quantities(company):
    """Map {produit_id: quantité réservée active} pour toute la société — un
    seul agrégat (évite un N+1 sur la liste produits). Lecture seule."""
    from apps.installations.selectors import reserved_quantities_for_company
    return reserved_quantities_for_company(company)


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
    from apps.installations.selectors import own_reservation_map
    return own_reservation_map(installation)


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


# ── Point d'entrée cross-app : mouvement de stock + maj du produit ───────────
# Les autres apps (ventes, installations, sav) décrémentent/incrémentent le
# stock à travers ce service plutôt qu'en créant `MouvementStock` directement et
# en sauvant `Produit` à la main (voir CLAUDE.md, règle de modularité). L'appelant
# garde sa propre logique de garde (refresh_from_db, plancher zéro, etc.) et passe
# les quantités déjà calculées : le service ne fait que l'écriture, à l'identique.

def record_stock_movement(*, company, produit, type_mouvement, quantite,
                          quantite_avant, quantite_apres, reference, note,
                          created_by, save_produit=True):
    """Crée UN MouvementStock et (par défaut) cale `produit.quantite_stock` sur
    `quantite_apres`. Renvoie le mouvement créé. Écriture identique au
    `MouvementStock.objects.create(...) + produit.save(update_fields=...)` que les
    appelants faisaient inline. À utiliser dans la transaction de l'appelant."""
    from .models import MouvementStock
    mouvement = MouvementStock.objects.create(
        company=company,
        produit=produit,
        type_mouvement=type_mouvement,
        quantite=quantite,
        quantite_avant=quantite_avant,
        quantite_apres=quantite_apres,
        reference=reference,
        note=note,
        created_by=created_by,
    )
    if save_produit:
        produit.quantite_stock = quantite_apres
        produit.save(update_fields=['quantite_stock'])
    return mouvement


def mouvement_type_sortie():
    """Valeur enum SORTIE (sans importer le modèle côté appelant)."""
    from .models import MouvementStock
    return MouvementStock.TypeMouvement.SORTIE


def mouvement_type_entree():
    """Valeur enum ENTREE (sans importer le modèle côté appelant)."""
    from .models import MouvementStock
    return MouvementStock.TypeMouvement.ENTREE


def mouvement_type_rebut():
    """XMFG11 — valeur enum REBUT (sans importer le modèle côté appelant)."""
    from .models import MouvementStock
    return MouvementStock.TypeMouvement.REBUT


def declarer_rebut(*, company, produit, quantite, motif, reference, note,
                   user):
    """XMFG11 — déclare un rebut de production : SORTIE typée REBUT, motivée,
    rattachée à un document source (``reference``, ex. un ordre d'assemblage).
    ``motif`` doit être une valeur de ``MouvementStock.MotifRebut``. Lève
    ValueError si la quantité est invalide."""
    from django.db import transaction
    from .models import MouvementStock, Produit

    if quantite is None or quantite <= 0:
        raise ValueError('La quantité de rebut doit être positive.')
    valeurs_motif = {c for c, _ in MouvementStock.MotifRebut.choices}
    if motif not in valeurs_motif:
        raise ValueError('Motif de rebut invalide.')

    with transaction.atomic():
        p = Produit.objects.select_for_update().get(id=produit.id)
        avant = p.quantite_stock
        qte_sortie = min(quantite, avant) if avant > 0 else 0
        apres = avant - qte_sortie
        mouvement = MouvementStock.objects.create(
            company=company, produit=p,
            type_mouvement=MouvementStock.TypeMouvement.REBUT,
            quantite=qte_sortie, quantite_avant=avant, quantite_apres=apres,
            reference=reference, note=note, motif_rebut=motif,
            created_by=user)
        p.quantite_stock = apres
        p.save(update_fields=['quantite_stock'])
    return mouvement


def rapport_rebuts(company, *, date_debut=None, date_fin=None):
    """XMFG11 — mini-rapport rebuts agrégé par produit sur une période
    (bornes optionnelles). Renvoie une liste de dicts {produit_id, produit_nom,
    quantite_totale, motifs: {motif: quantite}}, triée par quantité totale
    décroissante. INTERNE."""
    from .models import MouvementStock

    qs = MouvementStock.objects.filter(
        company=company, type_mouvement=MouvementStock.TypeMouvement.REBUT)
    if date_debut is not None:
        qs = qs.filter(date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date__lte=date_fin)

    par_produit = {}
    for mvt in qs.select_related('produit'):
        entry = par_produit.setdefault(mvt.produit_id, {
            'produit_id': mvt.produit_id,
            'produit_nom': mvt.produit.nom,
            'quantite_totale': 0,
            'motifs': {},
        })
        entry['quantite_totale'] += mvt.quantite
        motif = mvt.motif_rebut or 'autre'
        entry['motifs'][motif] = entry['motifs'].get(motif, 0) + mvt.quantite
    return sorted(
        par_produit.values(), key=lambda e: -e['quantite_totale'])


def sortie_exists_for_reference(company, reference):
    """True si un mouvement SORTIE référence déjà ``reference`` pour la société.

    Sert de garde anti-double-comptage (U9) : les apps appelantes (ventes)
    vérifient via ce service — sans importer le modèle MouvementStock — qu'un
    stock n'a pas déjà été réservé/consommé pour un même document (devis),
    qu'il vienne du chemin bon-commande (livraison) ou de la facturation
    directe par échéancier."""
    from .models import MouvementStock
    if not reference:
        return False
    return MouvementStock.objects.filter(
        company=company,
        type_mouvement=MouvementStock.TypeMouvement.SORTIE,
        reference=reference,
    ).exists()


# ── FG54 — Réapprovisionnement auto ──────────────────────────────────────────

def produits_a_reapprovisionner(company):
    """Retourne les produits dont le stock est <= seuil_alerte, groupés par
    fournisseur le moins cher (PrixFournisseur). INTERNE.

    Chaque item : {produit_id, nom, quantite_stock, seuil_alerte,
    quantite_suggere, fournisseur_id, fournisseur_nom, prix_achat,
    action, kit_id}. ``action`` = 'assembler' (kit_id renseigné) quand le
    produit sous seuil est le ``produit_compose`` d'un kit ACTIF
    (`installations.Kit`, XMFG3) — la suggestion devient « assembler N »
    plutôt qu'un bon de commande fournisseur ; sinon 'acheter'.
    """
    from .models import Produit, PrixFournisseur
    from apps.installations.selectors import kit_map_for_produits_composes

    qs = (Produit.objects
          .filter(company=company, is_archived=False)
          .exclude(seuil_alerte=0)
          .filter(quantite_stock__lte=models.F('seuil_alerte'))
          .prefetch_related('prix_fournisseurs__fournisseur'))

    produits = list(qs)
    kit_map = kit_map_for_produits_composes(
        company, [p.id for p in produits])

    result = []
    for p in produits:
        # Fournisseur le moins cher parmi les prix enregistrés.
        best = (PrixFournisseur.objects
                .filter(company=company, produit=p)
                .select_related('fournisseur')
                .order_by('prix_achat')
                .first())
        qte_suggere = p.quantite_reappro_cible if p.quantite_reappro_cible else (p.seuil_alerte * 2)
        kit_id = kit_map.get(p.id)
        result.append({
            'produit_id': p.id,
            'nom': p.nom,
            'sku': p.sku,
            'quantite_stock': p.quantite_stock,
            'seuil_alerte': p.seuil_alerte,
            'quantite_suggere': qte_suggere,
            'fournisseur_id': best.fournisseur_id if best else None,
            'fournisseur_nom': best.fournisseur.nom if best else None,
            'prix_achat': str(best.prix_achat) if best else None,
            'action': 'assembler' if kit_id else 'acheter',
            'kit_id': kit_id,
        })
    return result


def generer_bcf_reappro(company, user, fournisseur_id):
    """Génère un BCF BROUILLON pour tous les produits sous seuil, chez le
    fournisseur donné (ou les moins chers si non précisé). Renvoie
    {bon_commande_id, reference, nb_lignes}. Lève ValueError si rien à faire."""
    from apps.ventes.utils.references import create_with_reference
    from .models import BonCommandeFournisseur, LigneBonCommandeFournisseur, Fournisseur

    besoins = produits_a_reapprovisionner(company)
    if fournisseur_id:
        fournisseur = Fournisseur.objects.filter(
            id=fournisseur_id, company=company).first()
        if not fournisseur:
            raise ValueError("Fournisseur introuvable.")
        lignes = [(b['produit_id'], b['quantite_suggere'], b['prix_achat'])
                  for b in besoins]
    else:
        # Filtre sur les besoins qui ont un fournisseur
        fournisseur_id_premier = next(
            (b['fournisseur_id'] for b in besoins if b['fournisseur_id']), None)
        if not fournisseur_id_premier:
            raise ValueError("Aucun fournisseur associé aux produits à réapprovisionner.")
        fournisseur = Fournisseur.objects.get(id=fournisseur_id_premier, company=company)
        lignes = [(b['produit_id'], b['quantite_suggere'], b['prix_achat'])
                  for b in besoins if b['fournisseur_id'] == fournisseur_id_premier]

    if not lignes:
        raise ValueError("Aucun produit à réapprovisionner.")

    from .models import Produit
    lignes_produits = [
        (Produit.objects.get(id=pid, company=company), qte, prix)
        for pid, qte, prix in lignes
    ]

    created_bon = {}

    def _save(ref):
        bon = BonCommandeFournisseur.objects.create(
            company=company, reference=ref, fournisseur=fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON,
            note='Réapprovisionnement automatique (stock < seuil)',
            created_by=user)
        for produit, qte, prix in lignes_produits:
            LigneBonCommandeFournisseur.objects.create(
                bon_commande=bon, produit=produit,
                quantite=qte,
                prix_achat_unitaire=Decimal(prix) if prix else Decimal('0'))
        created_bon['bon'] = bon
        return bon

    create_with_reference(BonCommandeFournisseur, 'BCF', company, _save)
    bon = created_bon['bon']
    return {'bon_commande_id': bon.id, 'reference': bon.reference,
            'nb_lignes': len(lignes_produits)}


# ── FG55 — PDF facture fournisseur ────────────────────────────────────────────

def generate_facture_fournisseur_pdf(facture):
    """Génère le PDF d'une facture fournisseur (INTERNE). Utilise WeasyPrint."""
    from apps.ventes.utils.pdf import _company_context, _render_html, _html_to_pdf
    context = _company_context(company=facture.company)
    context['facture'] = facture
    context['fournisseur'] = facture.fournisseur
    context['lignes'] = list(facture.lignes.select_related('produit').all())
    context['paiements'] = list(facture.paiements.all())
    context['solde_du'] = facture.solde_du
    context['total_paye'] = facture.total_paye
    html = _render_html('facture_fournisseur.html', context)
    return _html_to_pdf(html)


# ── FG56 — Facturer une réception ────────────────────────────────────────────

def facturer_reception(company, user, reception):
    """Crée une FactureFournisseur à partir d'une réception confirmée.

    Construit les lignes HT à partir de LigneReceptionFournisseur ×
    prix_achat_unitaire de la ligne BCF, calcule HT/TVA/TTC (TVA 20 %).
    Lance ValueError si déjà facturée ou si la réception n'est pas confirmée.
    """
    from decimal import Decimal
    from apps.ventes.utils.references import create_with_reference
    from .models import FactureFournisseur, LigneFactureFournisseur

    if reception.statut != 'confirme':
        raise ValueError("Seule une réception confirmée peut être facturée.")

    # Garde idempotence : si une FF porte déjà ce bon de commande et la même
    # réception (on lie via note), on refuse.
    if FactureFournisseur.objects.filter(
            company=company,
            bon_commande=reception.bon_commande,
            note__startswith=f'Facture réception {reception.reference}').exists():
        raise ValueError(
            f"Cette réception ({reception.reference}) est déjà facturée.")

    taux_tva = Decimal('20')
    montant_ht = Decimal('0')
    lignes_data = []
    for ligne in reception.lignes.select_related('produit', 'ligne_commande').all():
        pu = ligne.ligne_commande.prix_achat_unitaire if ligne.ligne_commande else Decimal('0')
        total = Decimal(str(ligne.quantite)) * pu
        montant_ht += total
        lignes_data.append((ligne.produit.nom if ligne.produit else 'Produit',
                            ligne.quantite, pu))

    montant_tva = (montant_ht * taux_tva / Decimal('100')).quantize(Decimal('0.01'))
    montant_ttc = montant_ht + montant_tva

    created = {}

    def _save(ref):
        ff = FactureFournisseur.objects.create(
            company=company, reference=ref,
            fournisseur=reception.bon_commande.fournisseur,
            bon_commande=reception.bon_commande,
            montant_ht=montant_ht, montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            statut=FactureFournisseur.Statut.A_PAYER,
            note=f'Facture réception {reception.reference}',
            created_by=user)
        for designation, qte, pu in lignes_data:
            LigneFactureFournisseur.objects.create(
                facture=ff, designation=designation,
                quantite=qte, prix_unitaire_ht=pu)
        created['ff'] = ff
        return ff

    create_with_reference(FactureFournisseur, 'FF', company, _save)
    return created['ff']


# ── DC38 — Landed cost (FG316) replié dans le coût moyen pondéré ─────────────
# Le coût débarqué d'un dossier d'import (fret/douane/TVA import/transit) est
# écrit dans le champ EXISTANT `LigneBonCommandeFournisseur.frais_annexes` —
# celui que `average_cost_with_source` (FG67) intègre déjà — plutôt que dans un
# champ de coût d'achat PARALLÈLE. `installations` (qui possède le dossier
# d'import et string-FK stock) appelle ce setter ; stock n'importe jamais
# installations (sens de dépendance préservé).

def definir_frais_annexes_ligne_bcf(company, bon_commande_id, produit_id,
                                    frais_annexes):
    """DC38 — pose les frais annexes (coût débarqué) sur la/les ligne(s) de BCF
    d'un produit donné, dans la société. Setter STOCK pur (aucun import
    installations). Si plusieurs lignes portent le même produit sur ce BCF, le
    montant est réparti à parts égales pour que la somme sur les lignes reste
    exacte dans le coût moyen. Renvoie le nombre de lignes mises à jour."""
    from decimal import Decimal
    from .models import LigneBonCommandeFournisseur

    if not bon_commande_id or not produit_id:
        return 0
    lignes = list(LigneBonCommandeFournisseur.objects.filter(
        bon_commande_id=bon_commande_id,
        bon_commande__company=company,
        produit_id=produit_id))
    if not lignes:
        return 0
    total = Decimal(str(frais_annexes or 0))
    part = (total / Decimal(len(lignes))).quantize(Decimal('0.01'))
    for ligne in lignes:
        ligne.frais_annexes = part
        ligne.save(update_fields=['frais_annexes'])
    return len(lignes)


# ── FG57 — Rotation / dead-stock ─────────────────────────────────────────────

def rotation_report(company, jours=180):
    """Rapport de rotation des produits (dead-stock / immobile).

    Retourne une liste de dicts avec : produit_id, nom, sku, quantite_stock,
    valeur_stock (prix_achat × qte, INTERNE), derniere_sortie (date ou null),
    jours_sans_mouvement (int ou null), bucket ('actif'|'ralenti'|'immobile').
    Admin-only ; prix d'achat interne jamais client-facing.
    """
    from django.utils import timezone
    from .models import Produit, MouvementStock

    today = timezone.now().date()
    produits = (Produit.objects
                .filter(company=company, is_archived=False, quantite_stock__gt=0)
                .only('id', 'nom', 'sku', 'quantite_stock', 'prix_achat'))

    result = []
    for p in produits:
        derniere = (MouvementStock.objects
                    .filter(company=company, produit=p,
                            type_mouvement='sortie')
                    .order_by('-date')
                    .values_list('date', flat=True)
                    .first())
        jours_sans = None
        if derniere:
            jours_sans = (today - derniere.date()).days

        if derniere is None:
            bucket = 'immobile'
        elif jours_sans > jours:
            bucket = 'ralenti'
        else:
            bucket = 'actif'

        result.append({
            'produit_id': p.id,
            'nom': p.nom,
            'sku': p.sku,
            'quantite_stock': p.quantite_stock,
            'valeur_stock': str(p.prix_achat * p.quantite_stock),
            'derniere_sortie': derniere.date().isoformat() if derniere else None,
            'jours_sans_mouvement': jours_sans,
            'bucket': bucket,
        })
    # Trier : immobiles en premier, puis ralentis, puis actifs
    order = {'immobile': 0, 'ralenti': 1, 'actif': 2}
    result.sort(key=lambda x: (order[x['bucket']],
                               -(x['jours_sans_mouvement'] or 999999)))
    return result


# ── FG60 — Export xlsx mouvements ─────────────────────────────────────────────

def export_mouvements_xlsx(company, qs):
    """Export Excel de la liste filtrée des mouvements de stock (INTERNE).
    Prix d'achat jamais inclus."""
    from apps.crm.exports import build_xlsx_response
    headers = ['Référence', 'Type', 'Produit', 'Quantité',
               'Avant', 'Après', 'Note', 'Créé par', 'Date']
    rows = []
    for m in qs.select_related('produit', 'created_by'):
        rows.append([
            m.reference or '',
            m.get_type_mouvement_display(),
            m.produit.nom,
            m.quantite,
            m.quantite_avant,
            m.quantite_apres,
            m.note or '',
            m.created_by.username if m.created_by else '',
            m.date.strftime('%d/%m/%Y %H:%M') if m.date else '',
        ])
    return build_xlsx_response('mouvements-stock.xlsx', headers, rows,
                               sheet_title='Mouvements')


# ── FG58 — Comparaison fournisseurs ───────────────────────────────────────────

def comparer_fournisseurs(company, produit):
    """Retourne la liste des prix multi-fournisseurs d'un produit, triée du
    moins cher au plus cher. INTERNE — prix d'achat jamais client-facing."""
    from .models import PrixFournisseur
    qs = (PrixFournisseur.objects
          .filter(company=company, produit=produit)
          .select_related('fournisseur')
          .order_by('prix_achat'))
    return [
        {
            'fournisseur_id': pf.fournisseur_id,
            'fournisseur_nom': pf.fournisseur.nom,
            'prix_achat': str(pf.prix_achat),
            'date_dernier_achat': pf.date_dernier_achat.isoformat()
            if pf.date_dernier_achat else None,
        }
        for pf in qs
    ]


# ── FG59 — Scorecard performance fournisseur ─────────────────────────────────

def supplier_performance(company, fournisseur):
    """Scorecard performance fournisseur : délai moyen, taux de remplissage,
    taux de retour, dépenses totales. INTERNE."""
    from decimal import Decimal
    from .models import BonCommandeFournisseur, RetourFournisseur

    bons = (BonCommandeFournisseur.objects
            .filter(company=company, fournisseur=fournisseur)
            .exclude(statut=BonCommandeFournisseur.Statut.ANNULE)
            .prefetch_related('receptions', 'lignes'))

    nb_bons = bons.count()
    total_achats = Decimal('0')
    lead_times = []
    fill_rates = []

    for bc in bons:
        # Dépense totale HT (prix d'achat interne)
        total_achats += bc.total_achat or Decimal('0')

        # Délai de livraison = date_reception - date_commande (en jours)
        if bc.date_commande:
            for rec in bc.receptions.filter(statut='confirme'):
                if rec.date_reception:
                    delta = (rec.date_reception - bc.date_commande).days
                    if delta >= 0:
                        lead_times.append(delta)

        # Taux de remplissage = qte reçue / qte commandée
        total_cmd = sum(lig.quantite for lig in bc.lignes.all())
        total_recu = sum(lig.quantite_recue for lig in bc.lignes.all())
        if total_cmd > 0:
            fill_rates.append(total_recu / total_cmd * 100)

    # Taux de retour
    nb_retours = RetourFournisseur.objects.filter(
        company=company, fournisseur=fournisseur,
        statut='valide').count()

    return {
        'fournisseur_id': fournisseur.id,
        'fournisseur_nom': fournisseur.nom,
        'nb_bons': nb_bons,
        'avg_lead_time_days': round(sum(lead_times) / len(lead_times), 1) if lead_times else None,
        'fill_rate_pct': round(sum(fill_rates) / len(fill_rates), 1) if fill_rates else None,
        'nb_retours': nb_retours,
        'return_rate_pct': round(nb_retours / nb_bons * 100, 1) if nb_bons else None,
        'total_achats_ht': str(total_achats),
    }


# ── FG62 — Réapprovisionnement par emplacement ───────────────────────────────

def suggestions_reappro_emplacement(company):
    """Retourne les lignes StockEmplacement dont la quantité < seuil_min,
    avec une suggestion de transfert depuis le dépôt principal.
    INTERNE — admin uniquement."""
    from .models import StockEmplacement, EmplacementStock

    qs = (StockEmplacement.objects
          .filter(company=company)
          .filter(seuil_min__isnull=False)
          .filter(quantite__lt=models.F('seuil_min'))
          .select_related('produit', 'emplacement'))

    principal = EmplacementStock.objects.filter(
        company=company, is_principal=True).first()

    result = []
    for se in qs:
        qte_a_transferer = (se.seuil_min or 0) - se.quantite
        result.append({
            'produit_id': se.produit_id,
            'produit_nom': se.produit.nom,
            'emplacement_id': se.emplacement_id,
            'emplacement_nom': se.emplacement.nom,
            'quantite_actuelle': se.quantite,
            'seuil_min': se.seuil_min,
            'seuil_max': se.seuil_max,
            'qte_suggere_transfert': qte_a_transferer,
            'source_id': principal.id if principal else None,
            'source_nom': principal.nom if principal else None,
        })
    return result


# ── FG63 — Session d'inventaire ───────────────────────────────────────────────

def valider_inventaire_session(session, user):
    """Valide une session d'inventaire : émet les ajustements de stock pour
    chaque ligne en écart. Idempotent : une session déjà validée lève ValueError.
    Retourne {ajustes, inchanges}."""
    from django.db import transaction
    from .models import MouvementStock, InventaireSession

    if session.statut == InventaireSession.Statut.VALIDE:
        raise ValueError("Cette session d'inventaire est déjà validée.")
    if session.statut == InventaireSession.Statut.ANNULE:
        raise ValueError("Cette session d'inventaire est annulée.")

    ajustes, inchanges = 0, 0

    with transaction.atomic():
        for ligne in session.lignes.select_related('produit').all():
            ecart = ligne.quantite_comptee - ligne.quantite_theorique
            if ecart == 0:
                inchanges += 1
                continue

            # Ajustement : on pose la nouvelle valeur directement.
            produit = ligne.produit
            # Verrou anti-concurrence
            from .models import Produit
            produit = Produit.objects.select_for_update().get(pk=produit.pk)
            qte_avant = produit.quantite_stock
            qte_apres = ligne.quantite_comptee  # on remplace par le comptage

            MouvementStock.objects.create(
                company=session.company,
                produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT,
                quantite=abs(ecart),
                quantite_avant=qte_avant,
                quantite_apres=qte_apres,
                reference=session.reference,
                note=f'Inventaire {session.reference} — écart {ecart:+d}',
                created_by=user)

            produit.quantite_stock = qte_apres
            produit.save(update_fields=['quantite_stock'])
            ajustes += 1

        session.statut = InventaireSession.Statut.VALIDE
        session.save(update_fields=['statut'])

    return {'ajustes': ajustes, 'inchanges': inchanges}


# ── FG64 — Rapport expiry ─────────────────────────────────────────────────────

def produits_expirant_bientot(company, jours=90):
    """Retourne les produits dont au moins une ligne de réception a une
    date_peremption dans les `jours` prochains. Admin-only, INTERNE."""
    from django.utils import timezone
    import datetime
    from .models import LigneReceptionFournisseur

    today = timezone.now().date()
    limite = today + datetime.timedelta(days=jours)

    qs = (LigneReceptionFournisseur.objects
          .filter(
              reception__company=company,
              date_peremption__isnull=False,
              date_peremption__lte=limite,
              date_peremption__gte=today)
          .select_related('produit', 'reception'))

    # Déduplique par produit (garde la date de péremption la plus proche)
    seen = {}
    for ligne in qs.order_by('date_peremption'):
        pid = ligne.produit_id
        if pid not in seen:
            seen[pid] = {
                'produit_id': pid,
                'produit_nom': ligne.produit.nom,
                'date_peremption': ligne.date_peremption.isoformat(),
                'numero_lot': ligne.numero_lot,
                'quantite': ligne.quantite,
                'reception_ref': ligne.reception.reference,
                'jours_restants': (ligne.date_peremption - today).days,
            }
    return list(seen.values())


# ── FG65 — Prévisions de demande ─────────────────────────────────────────────

def previsions_reappro(company, nb_mois=6):
    """Calcule la consommation mensuelle moyenne par SKU (SORTIE sur les
    `nb_mois` derniers mois) et propose une quantité de réapprovisionnement.
    Retourne une liste de dicts par produit avec sortie > 0. Admin-only."""
    from django.utils import timezone
    import datetime
    from .models import MouvementStock, Produit

    today = timezone.now().date()
    debut = today - datetime.timedelta(days=30 * nb_mois)

    # Agréger les sorties par produit
    from django.db.models import Sum
    sorties = (MouvementStock.objects
               .filter(company=company, type_mouvement='sortie',
                       date__date__gte=debut)
               .values('produit_id')
               .annotate(total=Sum('quantite')))

    sorties_map = {s['produit_id']: s['total'] for s in sorties}
    if not sorties_map:
        return []

    produits = Produit.objects.filter(
        company=company, id__in=list(sorties_map.keys()),
        is_archived=False).only('id', 'nom', 'sku', 'quantite_stock',
                                'seuil_alerte', 'quantite_reappro_cible')
    result = []
    for p in produits:
        total_sorties = sorties_map[p.id]
        conso_moy = total_sorties / nb_mois  # par mois
        # Quantité suggérée = conso 2 mois (stock de sécurité) ou cible si définie
        qte_suggeree = (p.quantite_reappro_cible
                        if p.quantite_reappro_cible
                        else max(round(conso_moy * 2), p.seuil_alerte * 2 if p.seuil_alerte else 1))
        result.append({
            'produit_id': p.id,
            'nom': p.nom,
            'sku': p.sku,
            'total_sorties': total_sorties,
            'consommation_mensuelle_moy': round(conso_moy, 2),
            'quantite_stock': p.quantite_stock,
            'quantite_suggeree': qte_suggeree,
        })
    result.sort(key=lambda x: -x['consommation_mensuelle_moy'])
    return result


# ── FG66 / DC36 — Explosion d'un kit (BOM) en lignes composant ────────────────
# DC36 : aucun prix / marque / TVA n'est stocké sur le kit — l'explosion lit ces
# attributs sur le Produit composant au moment de l'insertion. Point d'entrée
# cross-app : `ventes` insère un kit dans un devis en appelant CE service (puis
# crée ses propres lignes de devis), jamais en important le modèle stock.

def exploser_kit(kit, quantite_kit=1):
    """Explose un kit en ses lignes composant pour ``quantite_kit`` unités.

    Renvoie une liste de dicts triés par désignation :
      {produit_id, sku, designation, quantite, prix_vente_unitaire, tva,
       marque, disponible}
    où ``quantite`` = quantité du composant × ``quantite_kit``. Le PRIX, la TVA
    et la MARQUE proviennent du ``Produit`` (DC36 — jamais stockés sur le kit).
    ``prix_vente_unitaire`` est le prix de vente catalogue (client-facing OK).
    Le prix d'ACHAT n'est jamais exposé ici. INTERNE/écran ; côté ventes c'est
    cette liste qui devient des lignes de devis."""
    from decimal import Decimal, InvalidOperation
    try:
        facteur = Decimal(str(quantite_kit))
    except (InvalidOperation, TypeError, ValueError):
        facteur = Decimal('1')
    out = []
    composants = (kit.composants
                  .select_related('produit')
                  .order_by('produit__nom'))
    for c in composants:
        p = c.produit
        qte = (c.quantite or Decimal('0')) * facteur
        out.append({
            'produit_id': p.id,
            'sku': p.sku or '',
            'designation': p.nom,
            'quantite': qte,
            # DC36 — prix / TVA / marque lus sur le composant, jamais sur le kit.
            'prix_vente_unitaire': p.prix_vente,
            'tva': p.tva,
            'marque': p.marque,
            'disponible': p.quantite_stock,
        })
    return out


def exploser_kit_par_id(company, kit_id, quantite_kit=1):
    """Variante scopée société : explose le kit ``kit_id`` de ``company`` (ou
    None si introuvable / archivé). Point d'entrée cross-app pour `ventes`."""
    from .models import KitProduit
    kit = KitProduit.objects.filter(
        id=kit_id, company=company, is_archived=False).first()
    if kit is None:
        return None
    return exploser_kit(kit, quantite_kit)


# ── XMFG1 — Backflush : clôture d'un ordre d'assemblage (installations) ──────
# `installations.OrdreAssemblage.terminer` appelle CE service (jamais de
# MouvementStock créé côté installations) : une SORTIE par composant (quantité
# BOM × quantite_produite) + une ENTREE du composite. Idempotent via le drapeau
# `stock_mouvemente` posé par l'appelant dans la MÊME transaction atomique.

def consommer_et_produire_assemblage(*, company, kit, composants, produit_compose,
                                     quantite_produite, reference, user,
                                     emplacement_source=None,
                                     emplacement_destination=None,
                                     per_unit=True):
    """Consomme les composants d'un kit et produit le composite (ENTREE, qté
    ``quantite_produite``). ``composants`` est un itérable d'objets avec
    ``.produit`` et ``.quantite``. Si ``per_unit`` (défaut, la BOM du kit),
    ``.quantite`` est PAR UNITÉ et la sortie = ``.quantite`` × ``quantite_produite``
    (tolérance sur/sous-production XMFG1). Si ``per_unit=False`` (lignes d'ordre
    personnalisées — XMFG6), ``.quantite`` est déjà le TOTAL à consommer, utilisé
    tel quel. Ventile sur les emplacements fournis (StockEmplacement, N15) en
    plus du total canonique. Lève ValueError si ``produit_compose`` est None
    (kit non finalisable) — l'appelant refuse `terminer` dans ce cas."""
    from django.db import transaction
    from .models import Produit, StockEmplacement

    if produit_compose is None:
        raise ValueError(
            "Le kit n'a pas de produit composite (produit_compose) : "
            "impossible de clôturer l'ordre.")

    with transaction.atomic():
        mouvements = []
        for ligne in composants:
            comp_produit = ligne.produit
            if comp_produit is None:
                continue
            qte_conso = ((ligne.quantite or 0) * quantite_produite if per_unit
                         else (ligne.quantite or 0))
            if qte_conso <= 0:
                continue
            p = Produit.objects.select_for_update().get(id=comp_produit.id)
            avant = p.quantite_stock
            apres = avant - qte_conso
            mvt = record_stock_movement(
                company=company, produit=p,
                type_mouvement=mouvement_type_sortie(),
                quantite=qte_conso, quantite_avant=avant,
                quantite_apres=apres, reference=reference,
                note=f'Assemblage {reference} — composant kit {kit.id}',
                created_by=user)
            mouvements.append(mvt)
            if emplacement_source is not None and \
                    not emplacement_source.is_principal:
                se, _ = StockEmplacement.objects.select_for_update().get_or_create(
                    produit=p, emplacement=emplacement_source,
                    defaults={'company': company, 'quantite': 0})
                se.quantite = max(se.quantite - qte_conso, 0)
                se.save(update_fields=['quantite'])

        composite = Produit.objects.select_for_update().get(id=produit_compose.id)
        avant_c = composite.quantite_stock
        apres_c = avant_c + quantite_produite
        mvt_entree = record_stock_movement(
            company=company, produit=composite,
            type_mouvement=mouvement_type_entree(),
            quantite=quantite_produite, quantite_avant=avant_c,
            quantite_apres=apres_c, reference=reference,
            note=f'Assemblage {reference} — composite kit {kit.id}',
            created_by=user)
        mouvements.append(mvt_entree)
        if emplacement_destination is not None and \
                not emplacement_destination.is_principal:
            se, _ = StockEmplacement.objects.select_for_update().get_or_create(
                produit=composite, emplacement=emplacement_destination,
                defaults={'company': company, 'quantite': 0})
            se.quantite += quantite_produite
            se.save(update_fields=['quantite'])

    return mouvements


# ── XMFG12 — Démontage (unbuild) : composite → composants ────────────────────
# Chemin INVERSE de XMFG1 : `installations.OrdreDemontage.terminer` appelle CE
# service pour un composite de retour (annulation, kit démo cannibalisé) —
# SORTIE du composite + ENTREE de chaque composant selon les quantités
# RÉCUPÉRÉES (éditables ligne à ligne, jamais la BOM brute).

def demonter_composite(*, company, kit, quantite_demontee, lignes_recuperation,
                       produit_compose, reference, user,
                       emplacement_source=None, emplacement_destination=None):
    """Sort le composite (`quantite_demontee` unités) et restocke chaque
    composant selon ``lignes_recuperation`` — itérable d'objets avec
    ``.produit`` et ``.quantite_recuperee`` (déjà le TOTAL récupéré, PAS par
    unité). Les composants cassés (récupéré < attendu) ne sont PAS restockés
    ici — l'appelant les déclare en rebut (XMFG11) séparément. Lève ValueError
    si ``produit_compose`` est None."""
    from django.db import transaction
    from .models import Produit, StockEmplacement

    if produit_compose is None:
        raise ValueError(
            "Le kit n'a pas de produit composite (produit_compose) : "
            "démontage impossible.")

    with transaction.atomic():
        mouvements = []
        composite = Produit.objects.select_for_update().get(id=produit_compose.id)
        avant_c = composite.quantite_stock
        qte_sortie = min(quantite_demontee, avant_c) if avant_c > 0 else 0
        apres_c = avant_c - qte_sortie
        mvt_sortie = record_stock_movement(
            company=company, produit=composite,
            type_mouvement=mouvement_type_sortie(),
            quantite=qte_sortie, quantite_avant=avant_c, quantite_apres=apres_c,
            reference=reference,
            note=f'Démontage {reference} — composite kit {kit.id}',
            created_by=user)
        mouvements.append(mvt_sortie)
        if emplacement_source is not None and not emplacement_source.is_principal:
            se, _ = StockEmplacement.objects.select_for_update().get_or_create(
                produit=composite, emplacement=emplacement_source,
                defaults={'company': company, 'quantite': 0})
            se.quantite = max(se.quantite - qte_sortie, 0)
            se.save(update_fields=['quantite'])

        for ligne in lignes_recuperation:
            comp_produit = ligne.produit
            if comp_produit is None:
                continue
            qte_recup = ligne.quantite_recuperee or 0
            if qte_recup <= 0:
                continue
            p = Produit.objects.select_for_update().get(id=comp_produit.id)
            avant = p.quantite_stock
            apres = avant + qte_recup
            mvt = record_stock_movement(
                company=company, produit=p,
                type_mouvement=mouvement_type_entree(),
                quantite=qte_recup, quantite_avant=avant, quantite_apres=apres,
                reference=reference,
                note=f'Démontage {reference} — composant récupéré kit {kit.id}',
                created_by=user)
            mouvements.append(mvt)
            if emplacement_destination is not None and \
                    not emplacement_destination.is_principal:
                se, _ = StockEmplacement.objects.select_for_update().get_or_create(
                    produit=p, emplacement=emplacement_destination,
                    defaults={'company': company, 'quantite': 0})
                se.quantite += qte_recup
                se.save(update_fields=['quantite'])

    return mouvements
