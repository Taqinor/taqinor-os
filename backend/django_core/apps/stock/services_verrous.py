"""ENF15 — corps VERROUILLÉS de deux écritures stock lues puis réécrites.

``imputer_avoir_fournisseur`` et ``resoudre_exception_facture`` (apps/stock/
services.py) délèguent ici : l'objet est RELU sous ``select_for_update()`` dans
une transaction, de sorte que deux requêtes concurrentes ne consomment plus
deux fois le même avoir et ne passent plus toutes deux le même contrôle de
statut. L'instance de l'appelant est rafraîchie avant retour.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone


def imputer_avoir_sous_verrou(avoir, facture, montant):
    from .models import (
        AvoirFournisseur, FactureFournisseur, ImputationAvoirFournisseur,
    )
    from .services import recompute_facture_fournisseur_statut

    with transaction.atomic():
        # AAPV27 — facture PUIS avoir (ordre de la porte paiement), solde relu
        # sous le verrou de la facture.
        facture = FactureFournisseur.objects.select_for_update().get(pk=facture.pk)
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
        from .services import poser_ras_au_solde
        poser_ras_au_solde(imputation)  # AAPV5 (D-AAPV-2)
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


def refuser_reglement_identique(facture, montant, date_paiement, confirmer):
    """ACNC74 (D-ACNC-1, jumeau fournisseur d'ACNC4) — même montant, même jour (date ou création),
    facture verrouillée, après la garde de solde ⇒ 409 ``paiement_similaire`` sauf confirmation."""
    if confirmer in (True, 'true', '1'):
        return
    from core.formats_fr import formater_date, formater_montant
    from .erreurs_achats import ConflitEtat
    aujourdhui = timezone.localdate()
    jour = date_paiement or aujourdhui  # ACNC74 — sans date : le jour même
    if not facture.paiements.filter(montant=montant).filter(
            Q(date_paiement=jour) | Q(date_paiement__isnull=True, date_creation__date=jour)).exists():
        return
    quand = "aujourd'hui" if jour == aujourdhui else f'le {formater_date(jour)}'
    somme = formater_montant(montant, devise='MAD', decimales=(
        0 if montant == montant.to_integral_value() else 2))
    raise ConflitEtat({'detail': f'Un règlement de {somme} a déjà été enregistré {quand} '
                                 'sur cette facture : confirmer ?', 'code': 'paiement_similaire'})


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


def constater_creance_ras_acompte(imputation):
    """AAPV86 (D-AAPV-6 = creance_fournisseur) — l'imputation d'acompte qui
    SOLDE une facture porte la RAS-TVA restante (AAPV5) ; l'acompte ayant été
    versé BRUT, cette retenue déclarée n'a jamais été retenue : elle devient une
    créance sur le fournisseur, constatée à l'imputation comme un avoir
    fournisseur VALIDÉ (le grand livre des créances fournisseur existant, jamais
    un second), imputable sur sa prochaine facture. Rien si la RAS portée est
    nulle. Appelée sous le verrou de ``imputer_acomptes_bcf``."""
    ras = imputation.montant_ras_tva or Decimal('0')
    if ras <= 0:
        return None
    from core.numbering import create_with_reference
    from .models import AvoirFournisseur
    facture = imputation.facture
    company = imputation.company or facture.company
    avoir = AvoirFournisseur(
        company=company, fournisseur_id=facture.fournisseur_id, facture_origine=facture,
        montant_ht=ras, montant_tva=Decimal('0'), montant_ttc=ras,
        statut=AvoirFournisseur.Statut.VALIDE,
        note=(f'Créance RAS-TVA : {ras} déclarés sur la facture {facture.reference} '
              f"par l'imputation de l'acompte versé brut (non retenus) — à réclamer "
              'au fournisseur.'))

    def _save(ref):
        avoir.reference = ref
        avoir.save()
        return avoir

    return create_with_reference(AvoirFournisseur, 'AVF', company, _save)


def borner_retour_au_recu(bon_commande, lignes):
    """ACNC28 (C-ACNC-012) — un retour lié à un BCF ne rend jamais plus que ce
    qui reste reçu : par produit, Σ quantités des lignes du retour ≤ Σ
    ``quantite_recue`` des lignes BCF relues SOUS verrou (dans la transaction
    de la validation). Lève ``EtatIncompatible`` (409) sinon. Sans BCF : sans
    objet (aucune quantité reçue de référence)."""
    from .erreurs_achats import EtatIncompatible
    if bon_commande is None:
        return
    demande = {}
    for ligne in lignes:
        demande[ligne.produit_id] = demande.get(ligne.produit_id, 0) + ligne.quantite
    for produit_id, quantite in demande.items():
        lignes_bcf = list(bon_commande.lignes.select_for_update().filter(produit_id=produit_id))
        recu = sum(lg.quantite_recue or 0 for lg in lignes_bcf)
        # Produit absent du BCF : aucune quantité reçue de référence (AAPV41 le
        # refuse déjà à la création par l'API) — borne sans objet.
        if lignes_bcf and quantite > recu:
            raise EtatIncompatible(
                f'Quantité retournée supérieure à la quantité reçue restante ({recu}).')
