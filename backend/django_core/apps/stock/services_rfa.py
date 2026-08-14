"""NTDST5 — Calcul et matérialisation d'une remise arrière fournisseur.

``calculer_rfa_fournisseur`` LIT (CA d'achat RÉCEPTIONNÉ sur la période, puis
seuil et taux) ; ``generer_avoir_rfa`` ÉCRIT l'``AvoirFournisseur``
correspondant, UNE SEULE FOIS par accord.

Le CA retenu est celui des lignes RÉELLEMENT REÇUES (``quantite_recue`` ×
prix d'achat unitaire) sur des BCF non annulés dont la date de commande tombe
dans la période : une commande passée mais jamais livrée ne donne droit à
aucune remise.
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def ca_achat_periode(company, fournisseur, debut, fin):
    """CA d'achat HT RÉCEPTIONNÉ chez ce fournisseur sur la période."""
    from .models import BonCommandeFournisseur

    total = Decimal('0')
    bons = (BonCommandeFournisseur.objects
            .filter(company=company, fournisseur=fournisseur,
                    date_commande__gte=debut, date_commande__lte=fin)
            .exclude(statut=BonCommandeFournisseur.Statut.ANNULE)
            .prefetch_related('lignes'))
    for bc in bons:
        for ligne in bc.lignes.all():
            total += (_dec(ligne.quantite_recue)
                      * _dec(ligne.prix_achat_unitaire))
    return total.quantize(Decimal('0.01'))


def calculer_rfa_fournisseur(accord):
    """Montant de remise dû par cet accord — LECTURE SEULE.

    Renvoie ``{ca_achat, seuil_atteint, progression_pct, montant_du,
    avoir_deja_genere}``. ``montant_du`` vaut 0 tant que le seuil n'est pas
    atteint : on ne verse jamais une remise partielle non contractuelle.
    """
    company = accord.company
    ca = ca_achat_periode(company, accord.fournisseur,
                          accord.periode_debut, accord.periode_fin)
    seuil = _dec(accord.seuil_ca_achat)
    atteint = ca >= seuil

    progression = Decimal('100') if seuil <= 0 else (
        (ca / seuil * Decimal('100')).quantize(Decimal('0.01')))

    montant = Decimal('0')
    if atteint:
        if accord.montant_fixe is not None:
            montant = _dec(accord.montant_fixe)
        elif accord.taux_pct is not None:
            montant = (ca * _dec(accord.taux_pct)
                       / Decimal('100')).quantize(Decimal('0.01'))
    return {
        'accord_id': accord.id,
        'fournisseur_id': accord.fournisseur_id,
        'periode_debut': accord.periode_debut.isoformat(),
        'periode_fin': accord.periode_fin.isoformat(),
        'ca_achat': str(ca),
        'seuil_ca_achat': str(seuil),
        'seuil_atteint': atteint,
        'progression_pct': str(min(progression, Decimal('100'))),
        'montant_du': str(montant.quantize(Decimal('0.01'))),
        'avoir_deja_genere': accord.avoir_deja_genere,
    }


def generer_avoir_rfa(accord, user):
    """Crée l'``AvoirFournisseur`` BROUILLON de la remise due.

    Refus (``ValueError``) si : un avoir a DÉJÀ été généré pour cet accord
    (idempotence — c'est le critère d'acceptation), le seuil n'est pas
    atteint, ou le montant calculé est nul.
    """
    from django.db import transaction

    from apps.ventes.utils.references import create_with_reference

    from .models import AvoirFournisseur

    if accord.avoir_deja_genere:
        raise ValueError(
            'Un avoir a déjà été généré pour cet accord et cette période.')

    calcul = calculer_rfa_fournisseur(accord)
    if not calcul['seuil_atteint']:
        raise ValueError(
            "Le seuil de CA d'achat de cet accord n'est pas atteint.")
    montant = _dec(calcul['montant_du'])
    if montant <= 0:
        raise ValueError('Le montant de remise calculé est nul.')

    with transaction.atomic():
        def _creer(reference):
            return AvoirFournisseur.objects.create(
                company=accord.company, reference=reference,
                fournisseur=accord.fournisseur,
                montant_ht=montant, montant_tva=Decimal('0'),
                montant_ttc=montant,
                statut=AvoirFournisseur.Statut.BROUILLON,
                created_by=user,
                note=(f'NTDST5 — remise arrière {accord.periode_debut} → '
                      f'{accord.periode_fin} (CA {calcul["ca_achat"]} MAD).'))

        avoir = create_with_reference(
            AvoirFournisseur, 'AVF', accord.company, _creer)
        accord.avoir_genere = avoir
        accord.save(update_fields=['avoir_genere'])

    logger.info('NTDST5 avoir RFA %s genere pour accord=%s',
                avoir.reference, accord.id)
    return avoir


def progression_seuil_rfa(accord):
    """Progression (%) vers le seuil, pour l'alerte NTDST19/NTDST32."""
    return calculer_rfa_fournisseur(accord)['progression_pct']
