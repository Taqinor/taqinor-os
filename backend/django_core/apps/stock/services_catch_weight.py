"""NTWMS37 — Services du relevé à unité variable (catch-weight).

  * ``enregistrer_pesee_ligne_reception`` — saisit/corrige le relevé tant que
    la réception est en brouillon ;
  * ``quantite_valorisable_ligne`` / ``valeur_ligne_reception`` — la quantité
    et le montant à VALORISER : le relevé réel quand il fait foi, la quantité
    nominale sinon. C'est le seul point où la nuance entre « commandé » et
    « reçu réel » entre dans le calcul ;
  * ``ecart_pesee_reception`` / ``rapprocher_pesee_reception`` (AUD226) — le
    rapprochement EXPLICITE du relevé avec le stock canonique.

Le flux de réception standard n'est PAS modifié : le nombre d'unités
physiques entrées en stock (``MouvementStock``) reste celui de la ligne — un
touret reste un touret même s'il pèse 98,4 m au lieu de 100.

AUD226 — CE QUE LE RELEVÉ FAIT, ET CE QU'IL NE FAIT PAS
-------------------------------------------------------
L'audit R2 constatait que la quantité et la valeur pesées étaient
DISPLAY-ONLY : hors de ce module, seul l'endpoint d'affichage
(``stock/views/catch_weight.py``) les lisait — ni ``quantite_stock`` ni le coût
moyen ne les voyaient jamais. Le relevé était donc un chiffre mort sur un écran.

L'option « appliquer l'écart automatiquement à la confirmation » a été écartée
pour DEUX raisons de structure, pas par facilité :

  1. ``Produit.quantite_stock`` et ``LigneBonCommandeFournisseur.quantite_recue``
     sont des ENTIERS d'unités physiques ; ``PeseeLigneReception.quantite_reelle``
     est un décimal à 3 décimales dans une unité de MESURE (kg/m/l). Écrire 98,4
     dans un compteur de tourets n'a pas de sens, et l'y arrondir en silence
     rendrait le stock faux d'une autre façon ;
  2. rabattre ``quantite_recue`` sur le relevé laisserait le BCF éternellement
     « partiellement reçu » pour une livraison catch-weight parfaitement normale.

Le relevé reste donc INFORMATIF (valorisation + litige fournisseur), et l'écart
constaté se solde par une action EXPLICITE de rapprochement — un ajustement N16
tracé (``rapprocher_pesee_reception``), jamais une écriture silencieuse.
"""
from decimal import Decimal, ROUND_HALF_UP


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def pesee_de_ligne(ligne_reception):
    """Le relevé de cette ligne, ou ``None``."""
    from .models import PeseeLigneReception
    return PeseeLigneReception.objects.filter(
        ligne_reception=ligne_reception).first()


def enregistrer_pesee_ligne_reception(*, ligne_reception, user,
                                      unite_variable=True,
                                      quantite_reelle=None,
                                      unite_mesure='kg', note=''):
    """Saisit le relevé réel d'une ligne de réception.

    Refuse une réception déjà CONFIRMÉE (le relevé a servi à valoriser : le
    rejouer réécrirait le passé) et une quantité négative.
    """
    from django.db import transaction

    from .models import PeseeLigneReception, ReceptionFournisseur

    reception = ligne_reception.reception
    if reception.statut == ReceptionFournisseur.Statut.CONFIRME:
        raise ValueError(
            'Cette réception est confirmée : son relevé de quantité réelle ne '
            'peut plus être modifié.')

    valeur = None
    if quantite_reelle not in (None, ''):
        valeur = _dec(quantite_reelle)
        if valeur < 0:
            raise ValueError('La quantité relevée ne peut pas être négative.')

    unites = {c for c, _ in PeseeLigneReception.UniteMesure.choices}
    if unite_mesure not in unites:
        raise ValueError('Unité de mesure invalide.')

    with transaction.atomic():
        pesee = pesee_de_ligne(ligne_reception)
        if pesee is None:
            pesee = PeseeLigneReception(
                company=reception.company, ligne_reception=ligne_reception)
        pesee.unite_variable = bool(unite_variable)
        pesee.quantite_reelle = valeur
        pesee.unite_mesure = unite_mesure
        pesee.note = (note or '').strip()
        pesee.releve_par = user
        pesee.save()
    return pesee


def quantite_valorisable_ligne(ligne_reception):
    """Quantité qui fait foi pour la VALORISATION de cette ligne.

    Relevé réel quand il est renseigné sur une ligne déclarée variable ;
    quantité nominale de la ligne sinon (comportement historique).
    """
    pesee = pesee_de_ligne(ligne_reception)
    if pesee is not None and pesee.est_renseignee:
        return pesee.quantite_reelle
    return _dec(ligne_reception.quantite)


def valeur_ligne_reception(ligne_reception):
    """Montant d'achat de la ligne à la quantité qui fait foi.

    INTERNE (prix d'achat) — jamais client-facing.
    """
    ligne_cmd = ligne_reception.ligne_commande
    prix = _dec(getattr(ligne_cmd, 'prix_achat_unitaire', 0))
    return (quantite_valorisable_ligne(ligne_reception) * prix)


def ecart_pesee_ligne(ligne_reception):
    """Écart (relevé − nominal) d'une ligne variable ; ``None`` sans relevé.

    Positif = on a reçu PLUS que commandé, négatif = moins.
    """
    pesee = pesee_de_ligne(ligne_reception)
    if pesee is None or not pesee.est_renseignee:
        return None
    return pesee.quantite_reelle - _dec(ligne_reception.quantite)


#: Référence portée par l'ajustement de rapprochement (AUD226) — sert aussi de
#: garde d'idempotence : un rapprochement déjà posé n'est jamais rejoué.
PREFIXE_REFERENCE_RAPPROCHEMENT = 'PESEE'


def reference_rapprochement(reception):
    """Référence du mouvement d'ajustement de rapprochement d'une réception."""
    return f'{PREFIXE_REFERENCE_RAPPROCHEMENT}-{reception.reference}'


def ecart_pesee_reception(reception):
    """AUD226 — écarts de pesée EXPLOITABLES d'une réception confirmée.

    Renvoie ``[{ligne_reception, produit, quantite_nominale, quantite_reelle,
    ecart, ecart_entier}]`` pour les seules lignes portant un relevé qui fait
    foi ET rattachées à un produit stocké. ``ecart_entier`` est l'écart arrondi
    au plus proche entier d'unité physique : c'est LUI qui peut être passé au
    stock canonique (le stock compte des unités, pas des kilogrammes) ; un
    écart de pesée qui s'arrondit à 0 ne justifie aucun ajustement.
    LECTURE SEULE."""
    lignes = []
    for ligne in reception.lignes.select_related('produit',
                                                 'ligne_commande').all():
        if ligne.produit_id is None:
            continue
        ecart = ecart_pesee_ligne(ligne)
        if ecart is None:
            continue
        ecart_entier = int(ecart.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        lignes.append({
            'ligne_reception': ligne.id,
            'produit': ligne.produit,
            'quantite_nominale': ligne.quantite,
            'quantite_reelle': quantite_valorisable_ligne(ligne),
            'ecart': ecart,
            'ecart_entier': ecart_entier,
        })
    return lignes


def rapprocher_pesee_reception(*, reception, user=None, note=None):
    """AUD226 — solde les écarts de pesée d'une réception CONFIRMÉE par un
    ajustement de stock N16 tracé, produit par produit.

    Le relevé catch-weight est informatif : il ne bouge jamais le stock tout
    seul (voir l'en-tête du module). Cette action est le point de passage
    EXPLICITE qui le rapproche du stock canonique — un ``MouvementStock``
    AJUSTEMENT par produit, posé via ``record_stock_movement`` (donc miroir
    comptable et alerte seuil-bas inclus), référencé ``PESEE-<réception>``.

    IDEMPOTENTE : un rapprochement déjà posé pour cette réception n'est jamais
    rejoué. Renvoie ``{ajustes, inchanges, mouvements:[…]}``.
    """
    from django.db import transaction

    from .models import MouvementStock, Produit, ReceptionFournisseur
    from .services import record_stock_movement

    if reception.statut != ReceptionFournisseur.Statut.CONFIRME:
        raise ValueError(
            'Le rapprochement de pesée ne concerne qu\'une réception '
            'confirmée.')

    reference = reference_rapprochement(reception)
    if MouvementStock.objects.filter(
            company=reception.company, reference=reference).exists():
        raise ValueError(
            'Les écarts de pesée de cette réception ont déjà été rapprochés.')

    result = {'ajustes': 0, 'inchanges': 0, 'mouvements': []}
    with transaction.atomic():
        for ligne in ecart_pesee_reception(reception):
            ecart = ligne['ecart_entier']
            if ecart == 0:
                result['inchanges'] += 1
                continue
            produit = Produit.objects.select_for_update().get(
                pk=ligne['produit'].pk)
            avant = produit.quantite_stock
            apres = max(avant + ecart, 0)
            record_stock_movement(
                company=reception.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT,
                quantite=abs(apres - avant),
                quantite_avant=avant, quantite_apres=apres,
                reference=reference,
                note=(f'Rapprochement de pesée {reception.reference} — '
                      f'relevé {ligne["quantite_reelle"]} pour '
                      f'{ligne["quantite_nominale"]} nominal '
                      f'(écart {ligne["ecart"]})'
                      + (f' · {note}' if note else '')),
                created_by=user)
            result['ajustes'] += 1
            result['mouvements'].append({
                'produit': produit.id, 'avant': avant, 'apres': apres})
    return result
