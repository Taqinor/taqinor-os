"""NTDST3 — Services de la consignation client (dépôt-vente).

Deux écritures, et deux seulement :
  * ``creer_depot_consignation`` — sort la marchandise du dépôt principal
    (``MouvementStock`` SORTIE motivé « consignation ») SANS créer de facture ;
  * ``declarer_consommation`` — enregistre ce que le client a consommé, sans
    JAMAIS retoucher le stock (la marchandise est déjà partie).

C'est cette asymétrie qui évite le double décrément — l'erreur classique du
dépôt-vente.
"""
import logging

logger = logging.getLogger(__name__)

MOTIF_SORTIE = 'consignation'


def _parametres_negoce(company):
    """``ParametresNegoce`` de la société (NTDST30), ou ``None`` s'il n'a pas
    encore été créé — l'absence n'est jamais bloquante."""
    from .models import ParametresNegoce
    return ParametresNegoce.objects.filter(company=company).first()


def consignation_activee(company):
    """Vrai si la consignation est active pour cette société.

    DÉFAUT ACTIF quand aucun paramétrage n'existe : le lot est additif, il
    n'éteint rien silencieusement (NTDST30/NTDST31).
    """
    params = _parametres_negoce(company)
    return True if params is None else bool(params.consignation_activee)


def creer_depot_consignation(*, company, user, client_id, produit_id,
                             quantite, date_depot, adresse_site='',
                             emplacement_id=None, note=''):
    """Dépose de la marchandise chez un client.

    Décrémente le dépôt principal via un ``MouvementStock`` SORTIE référencé
    « CONSIGNATION » — jamais un chemin de sortie parallèle — et NE crée
    AUCUNE facture (c'est tout le principe du dépôt-vente).
    """
    from django.db import transaction

    from .models import (
        DepotConsignation, EmplacementStock, MouvementStock, Produit,
    )
    from .services import check_negative_stock_guard

    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité déposée doit être positive.')
    if not date_depot:
        raise ValueError('La date de dépôt est obligatoire.')

    emplacement = None
    if emplacement_id:
        emplacement = EmplacementStock.objects.filter(
            id=emplacement_id, company=company).first()

    with transaction.atomic():
        produit = (Produit.objects.select_for_update()
                   .filter(id=produit_id, company=company).first())
        if produit is None:
            raise ValueError('Produit introuvable dans cette société.')

        qte_avant = produit.quantite_stock
        qte_apres = qte_avant - quantite
        check_negative_stock_guard(company, qte_avant, qte_apres)

        depot = DepotConsignation.objects.create(
            company=company, client_id=client_id, produit=produit,
            quantite_deposee=quantite, date_depot=date_depot,
            adresse_site=(adresse_site or '').strip()[:255],
            emplacement_source=emplacement, note=(note or '').strip(),
            cree_par=user)

        MouvementStock.objects.create(
            company=company, produit=produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=quantite, quantite_avant=qte_avant,
            quantite_apres=qte_apres,
            reference=f'CONSIGNATION-{depot.id}',
            note=f'Mise en consignation chez le client {client_id} '
                 f'({MOTIF_SORTIE}).',
            created_by=user)
        produit.quantite_stock = qte_apres
        produit.save(update_fields=['quantite_stock'])

    logger.info('NTDST3 depot de consignation %s (%d x produit=%s)',
                depot.id, quantite, produit.id)
    return depot


def declarer_consommation(*, depot, user, quantite, date_declaration,
                          note=''):
    """Enregistre une consommation déclarée par le client.

    NE TOUCHE PAS AU STOCK : la marchandise a quitté le dépôt à la création du
    dépôt de consignation. Refuse une quantité nulle/négative ou supérieure au
    restant, et un dépôt CLOS.
    """
    from django.db import transaction

    from .models import DeclarationConsommation, DepotConsignation

    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité consommée doit être positive.')
    if not date_declaration:
        raise ValueError('La date de déclaration est obligatoire.')

    with transaction.atomic():
        depot = (DepotConsignation.objects.select_for_update()
                 .get(pk=depot.pk))
        if depot.statut == DepotConsignation.Statut.CLOS:
            raise ValueError('Ce dépôt de consignation est clos.')
        if quantite > depot.quantite_restante:
            raise ValueError(
                f'Quantité supérieure au restant en dépôt '
                f'({depot.quantite_restante}).')

        declaration = DeclarationConsommation.objects.create(
            company=depot.company, depot=depot, quantite=quantite,
            date_declaration=date_declaration, declaree_par=user,
            note=(note or '').strip())
        depot.quantite_consommee_declaree += quantite
        champs = ['quantite_consommee_declaree']
        if depot.quantite_restante == 0:
            depot.statut = DepotConsignation.Statut.CLOS
            champs.append('statut')
        depot.save(update_fields=champs)
    return declaration


def releve_consignation(depot):
    """Relevé cumulé d'un dépôt : déposé / consommé / facturé / restant, avec
    le détail des déclarations triées par date (LECTURE SEULE)."""
    from .models import DeclarationConsommation

    declarations = list(depot.declarations.order_by('date_declaration', 'id'))
    facture = sum(
        d.quantite for d in declarations
        if d.statut == DeclarationConsommation.Statut.FACTUREE)
    return {
        'depot_id': depot.id,
        'client_id': depot.client_id,
        'produit_id': depot.produit_id,
        'produit_nom': getattr(depot.produit, 'nom', ''),
        'date_depot': depot.date_depot.isoformat(),
        'adresse_site': depot.adresse_site,
        'statut': depot.statut,
        'quantite_deposee': depot.quantite_deposee,
        'quantite_consommee': depot.quantite_consommee_declaree,
        'quantite_facturee': facture,
        'quantite_restante': depot.quantite_restante,
        'declarations': [{
            'id': d.id,
            'date': d.date_declaration.isoformat(),
            'quantite': d.quantite,
            'statut': d.statut,
            'document_reference': d.document_reference,
        } for d in declarations],
    }
