"""NTEDU8 — échéancier de scolarité.

Module dédié (comme ``services_remises``) pour que ``services.
_apres_validation_inscription`` s'y branche par un import local optionnel
sans dépendance dure entre NTEDU3 et NTEDU8."""
import calendar
from datetime import date
from decimal import Decimal

from django.db import transaction


def _add_months(base_date, months):
    """Ajoute ``months`` mois à ``base_date`` sans dépendance externe
    (``python-dateutil`` n'est pas une dépendance déclarée du projet) —
    calcul manuel year/month, jour bordé à la fin du mois cible."""
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def generer_echeancier(eleve, annee_scolaire):
    """NTEDU8 — génère l'échéancier COMPLET de l'année (frais d'inscription +
    scolarité annuelle répartie en ``nombre_echeances`` mensualités, remises
    ``approuvee`` déduites) à la validation de l'inscription — SANS
    intervention manuelle. Idempotent : no-op si un échéancier existe déjà
    pour (eleve, annee_scolaire)."""
    from .models import EcheancierScolarite, GrilleTarifaire

    if EcheancierScolarite.objects.filter(
            eleve=eleve, annee_scolaire=annee_scolaire).exists():
        return EcheancierScolarite.objects.get(
            eleve=eleve, annee_scolaire=annee_scolaire)

    if eleve.classe is None:
        return None
    grille = GrilleTarifaire.objects.filter(
        annee_scolaire=annee_scolaire, niveau=eleve.classe.niveau,
        active=True).first()
    if grille is None:
        return None

    from .services_remises import montant_remises_approuvees

    montant_brut = grille.frais_inscription + grille.scolarite_annuelle
    remise_totale, remises = montant_remises_approuvees(
        eleve, annee_scolaire, grille.scolarite_annuelle)
    montant_total = max(Decimal('0'), montant_brut - remise_totale)
    nombre_echeances = 10

    with transaction.atomic():
        echeancier = EcheancierScolarite.objects.create(
            company=eleve.company, eleve=eleve, annee_scolaire=annee_scolaire,
            grille_tarifaire=grille, montant_total=montant_total,
            nombre_echeances=nombre_echeances)
        if remises:
            echeancier.remises.set(remises)

        _generer_lignes(
            echeancier, frais_inscription=grille.frais_inscription,
            scolarite_nette=montant_total - grille.frais_inscription,
            nombre_echeances=nombre_echeances,
            date_debut=annee_scolaire.date_debut)

    return echeancier


def _generer_lignes(
        echeancier, *, frais_inscription, scolarite_nette,
        nombre_echeances, date_debut):
    """Génère EXACTEMENT ``nombre_echeances`` lignes (aucune ligne
    supplémentaire pour les frais d'inscription — ils sont intégrés à la 1re
    mensualité) : ``échéancier complet`` = un nombre de lignes fixe et
    prévisible, quel que soit le nombre de composantes tarifaires."""
    from .models import LigneEcheance

    mensualite = (
        scolarite_nette / nombre_echeances if scolarite_nette else Decimal('0'))
    lignes = []
    for i in range(nombre_echeances):
        montant = mensualite + (frais_inscription if i == 0 else Decimal('0'))
        libelle = f"Scolarité — mensualité {i + 1}/{nombre_echeances}"
        if i == 0 and frais_inscription:
            libelle += " (+ frais d'inscription)"
        lignes.append(LigneEcheance(
            company=echeancier.company, echeancier=echeancier,
            libelle=libelle, montant=montant,
            date_echeance=_add_months(date_debut, i)))

    LigneEcheance.objects.bulk_create(lignes)
