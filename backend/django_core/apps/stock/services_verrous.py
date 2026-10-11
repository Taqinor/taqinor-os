"""ENF15 — corps VERROUILLÉS de deux écritures stock lues puis réécrites.

``imputer_avoir_fournisseur`` et ``resoudre_exception_facture`` (apps/stock/
services.py) délèguent ici : l'objet est RELU sous ``select_for_update()`` dans
une transaction, de sorte que deux requêtes concurrentes ne consomment plus
deux fois le même avoir et ne passent plus toutes deux le même contrôle de
statut. L'instance de l'appelant est rafraîchie avant retour.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone


def imputer_avoir_sous_verrou(avoir, facture, montant):
    from .models import AvoirFournisseur, ImputationAvoirFournisseur
    from .services import recompute_facture_fournisseur_statut

    with transaction.atomic():
        verrou = AvoirFournisseur.objects.select_for_update().get(pk=avoir.pk)
        if verrou.fournisseur_id != facture.fournisseur_id:
            raise ValueError(
                "L'avoir et la facture doivent appartenir au même fournisseur.")
        if verrou.statut not in (
                AvoirFournisseur.Statut.VALIDE, AvoirFournisseur.Statut.IMPUTE):
            raise ValueError('Seul un avoir validé peut être imputé.')

        plafond = min(verrou.montant_disponible, facture.solde_du)
        montant_impute = Decimal(str(montant)) if montant is not None else plafond
        montant_impute = min(montant_impute, plafond)
        if montant_impute <= 0:
            raise ValueError("Rien à imputer (avoir épuisé ou facture soldée).")

        imputation = ImputationAvoirFournisseur.objects.create(
            company=verrou.company, avoir=verrou, facture=facture,
            montant=montant_impute)
        verrou.montant_impute = (
            verrou.montant_impute or Decimal('0')) + montant_impute
        verrou.statut = (AvoirFournisseur.Statut.IMPUTE
                         if verrou.montant_disponible <= 0
                         else AvoirFournisseur.Statut.VALIDE)
        verrou.save(update_fields=['montant_impute', 'statut'])
        # ASTK102 — le statut de la facture suit son solde (avoir = règlement).
        recompute_facture_fournisseur_statut(facture)
    avoir.montant_impute = verrou.montant_impute
    avoir.statut = verrou.statut
    return imputation


def resoudre_exception_sous_verrou(facture, user, commentaire=''):
    from .models import FactureFournisseur

    champs = ['statut_controle', 'resolu_par', 'resolu_le', 'motif_ecart']
    with transaction.atomic():
        verrou = FactureFournisseur.objects.select_for_update().get(
            pk=facture.pk)
        if verrou.statut_controle != FactureFournisseur.StatutControle.EXCEPTION:
            raise ValueError("Cette facture n'est pas en exception.")
        verrou.statut_controle = FactureFournisseur.StatutControle.RESOLUE
        verrou.resolu_par = user
        verrou.resolu_le = timezone.now()
        if commentaire:
            verrou.motif_ecart = (
                (verrou.motif_ecart or '') + f'\nRésolution : {commentaire}')
        verrou.save(update_fields=champs)
    facture.refresh_from_db(fields=champs)
    return facture
