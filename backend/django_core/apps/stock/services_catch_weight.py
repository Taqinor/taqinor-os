"""NTWMS37 — Services du relevé à unité variable (catch-weight).

Deux fonctions, aucune ailleurs :
  * ``enregistrer_pesee_ligne_reception`` — saisit/corrige le relevé tant que
    la réception est en brouillon ;
  * ``quantite_valorisable_ligne`` / ``valeur_ligne_reception`` — la quantité
    et le montant à VALORISER : le relevé réel quand il fait foi, la quantité
    nominale sinon. C'est le seul point où la nuance entre « commandé » et
    « reçu réel » entre dans le calcul.

Le flux de réception standard n'est PAS modifié : le nombre d'unités
physiques entrées en stock (``MouvementStock``) reste celui de la ligne — un
touret reste un touret même s'il pèse 98,4 m au lieu de 100.
"""
from decimal import Decimal


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
