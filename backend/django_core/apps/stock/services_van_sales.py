"""NTDST14 — Chargement / déchargement du stock embarqué d'un véhicule.

``charger_vehicule`` décrémente le dépôt principal (``MouvementStock`` SORTIE
motivée « chargement véhicule ») et incrémente ``StockVehicule`` ;
``decharger_vehicule`` fait l'INVERSE en fin de tournée pour le reliquat non
vendu.

GARDE MÉTIER : le déchargement ne peut jamais rendre plus que ce qui est
réellement embarqué (sinon on créerait du stock à partir de rien).
"""
import logging

logger = logging.getLogger(__name__)


def van_sales_active(company):
    """Vrai si les tournées de vente sont actives pour cette société.

    DÉFAUT ACTIF sans paramétrage : le lot est additif (NTDST30/NTDST31).
    """
    from .models import ParametresNegoce
    params = ParametresNegoce.objects.filter(company=company).first()
    return True if params is None else bool(params.van_sales_active)


def stock_embarque(company, actif_flotte_id):
    """Contenu actuel d'un véhicule (LECTURE SEULE)."""
    from .models import StockVehicule

    lignes = (StockVehicule.objects
              .filter(company=company, actif_flotte_id=actif_flotte_id,
                      quantite_embarquee__gt=0)
              .select_related('produit')
              .order_by('produit__nom', 'produit_id'))
    return [{
        'id': ligne.id,
        'produit': ligne.produit_id,
        'produit_nom': ligne.produit.nom,
        'sku': ligne.produit.sku or '',
        'quantite_embarquee': ligne.quantite_embarquee,
    } for ligne in lignes]


def _normaliser_lignes(lignes):
    normalisees = []
    for brute in (lignes or []):
        produit_id = brute.get('produit') if isinstance(brute, dict) else None
        quantite = brute.get('quantite') if isinstance(brute, dict) else None
        try:
            quantite = int(quantite)
        except (TypeError, ValueError):
            raise ValueError('Quantité de ligne invalide.')
        if not produit_id or quantite <= 0:
            raise ValueError(
                'Chaque ligne exige un produit et une quantité positive.')
        normalisees.append((produit_id, quantite))
    if not normalisees:
        raise ValueError('Aucune ligne à traiter.')
    return normalisees


def charger_vehicule(*, company, user, actif_flotte_id, lignes):
    """Charge des produits dans un véhicule.

    Décrémente le dépôt principal et n'affecte AUCUN autre emplacement.
    """
    from django.db import transaction

    from .models import MouvementStock, Produit, StockVehicule
    from .services import check_negative_stock_guard

    normalisees = _normaliser_lignes(lignes)
    resultats = []
    with transaction.atomic():
        for produit_id, quantite in normalisees:
            produit = (Produit.objects.select_for_update()
                       .filter(id=produit_id, company=company).first())
            if produit is None:
                raise ValueError('Produit introuvable dans cette société.')
            qte_avant = produit.quantite_stock
            qte_apres = qte_avant - quantite
            check_negative_stock_guard(company, qte_avant, qte_apres)

            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=quantite, quantite_avant=qte_avant,
                quantite_apres=qte_apres,
                reference=f'VAN-CHARGE-{actif_flotte_id}',
                note='Chargement véhicule (tournée de vente).',
                created_by=user)
            produit.quantite_stock = qte_apres
            produit.save(update_fields=['quantite_stock'])

            ligne, _ = StockVehicule.objects.select_for_update().get_or_create(
                company=company, actif_flotte_id=actif_flotte_id,
                produit=produit, defaults={'quantite_embarquee': 0})
            ligne.quantite_embarquee += quantite
            ligne.save(update_fields=['quantite_embarquee'])
            resultats.append(ligne)
    logger.info('NTDST14 chargement vehicule=%s lignes=%d',
                actif_flotte_id, len(resultats))
    return resultats


def decharger_vehicule(*, company, user, actif_flotte_id, lignes):
    """Rend au dépôt principal le reliquat non vendu d'une tournée."""
    from django.db import transaction

    from .models import MouvementStock, Produit, StockVehicule

    normalisees = _normaliser_lignes(lignes)
    resultats = []
    with transaction.atomic():
        for produit_id, quantite in normalisees:
            ligne = (StockVehicule.objects.select_for_update()
                     .filter(company=company, actif_flotte_id=actif_flotte_id,
                             produit_id=produit_id).first())
            if ligne is None or ligne.quantite_embarquee < quantite:
                embarque = ligne.quantite_embarquee if ligne else 0
                raise ValueError(
                    f'Quantité supérieure au stock embarqué ({embarque}).')

            produit = (Produit.objects.select_for_update()
                       .filter(id=produit_id, company=company).first())
            if produit is None:
                raise ValueError('Produit introuvable dans cette société.')

            qte_avant = produit.quantite_stock
            qte_apres = qte_avant + quantite
            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=quantite, quantite_avant=qte_avant,
                quantite_apres=qte_apres,
                reference=f'VAN-DECHARGE-{actif_flotte_id}',
                note='Déchargement véhicule (reliquat de tournée).',
                created_by=user)
            produit.quantite_stock = qte_apres
            produit.save(update_fields=['quantite_stock'])

            ligne.quantite_embarquee -= quantite
            ligne.save(update_fields=['quantite_embarquee'])
            resultats.append(ligne)
    logger.info('NTDST14 dechargement vehicule=%s lignes=%d',
                actif_flotte_id, len(resultats))
    return resultats
