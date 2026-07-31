"""NTEDU24 — Facturation transport proratisée dans l'échéancier.

Module dédié (comme ``services_cantine``/``services_echeancier``) : pas de
dépendance dure entre NTEDU8 et NTEDU24 (imports locaux). Une
``AffectationTransport`` active (``date_fin`` vide ou postérieure à la
période) déclenche l'inclusion automatique de ``GrilleTarifaire.
transport_mensuel`` dans CHAQUE mensualité — jamais rétroactive : retirer un
élève du transport en cours d'année (poser ``date_fin``) n'ajuste QUE les
lignes futures (statut ``a_venir``), jamais celles déjà ``facturee``/
``payee``/``en_retard``."""
from decimal import Decimal

from django.db.models import Q


def affectation_transport_active(eleve, annee_scolaire):
    """``AffectationTransport`` ACTIVE de ``eleve`` qui chevauche la période
    de ``annee_scolaire`` — la plus récente si plusieurs (cas normalement
    unique). ``date_fin`` vide = affectation en cours (même règle que
    ``AffectationTransport.__doc__``)."""
    from .models import AffectationTransport

    return AffectationTransport.objects.filter(
        eleve=eleve, date_debut__lte=annee_scolaire.date_fin,
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=annee_scolaire.date_debut),
    ).order_by('-date_debut').first()


def montant_transport_mensuel(eleve, annee_scolaire):
    """NTEDU24 — montant mensuel transport (``GrilleTarifaire.
    transport_mensuel`` du niveau de l'élève) si ``eleve`` a une affectation
    transport active pour cette année scolaire, sinon ``Decimal('0')``."""
    from .models import GrilleTarifaire

    affectation = affectation_transport_active(eleve, annee_scolaire)
    if affectation is None or eleve.classe is None:
        return Decimal('0')

    grille = GrilleTarifaire.objects.filter(
        annee_scolaire=annee_scolaire, niveau=eleve.classe.niveau,
        active=True).first()
    if grille is None or not grille.transport_mensuel:
        return Decimal('0')

    return grille.transport_mensuel


def resynchroniser_lignes_futures_transport(eleve):
    """NTEDU24 — recalcule la composante transport des lignes d'échéance
    FUTURES (statut ``a_venir`` UNIQUEMENT) de TOUS les échéanciers de
    ``eleve`` — à appeler à la création/mise à jour d'une
    ``AffectationTransport``. JAMAIS rétroactif : une ligne déjà
    ``facturee``/``payee``/``en_retard`` garde son montant historique même si
    l'affectation change en cours d'année (retirer un élève du transport ne
    modifie jamais la facture déjà émise, seulement les mois suivants)."""
    from .models import EcheancierScolarite, LigneEcheance

    for echeancier in EcheancierScolarite.objects.filter(eleve=eleve):
        nouveau_transport = montant_transport_mensuel(
            eleve, echeancier.annee_scolaire)
        lignes = echeancier.lignes.filter(statut=LigneEcheance.Statut.A_VENIR)
        montant_total_delta = Decimal('0')
        for ligne in lignes:
            if ligne.transport_montant == nouveau_transport:
                continue
            montant_total_delta += nouveau_transport - ligne.transport_montant
            ligne.montant = (
                ligne.montant - ligne.transport_montant + nouveau_transport)
            ligne.transport_montant = nouveau_transport
            ligne.save(update_fields=['montant', 'transport_montant'])
        if montant_total_delta:
            echeancier.montant_total = (
                echeancier.montant_total + montant_total_delta)
            echeancier.save(update_fields=['montant_total'])
