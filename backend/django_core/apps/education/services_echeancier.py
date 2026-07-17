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

    from .models import ParametresEducation
    from .services_cantine import montant_cantine_mensuel
    from .services_remises import montant_remises_approuvees

    montant_brut = grille.frais_inscription + grille.scolarite_annuelle
    remise_totale, remises = montant_remises_approuvees(
        eleve, annee_scolaire, grille.scolarite_annuelle)
    montant_total = max(Decimal('0'), montant_brut - remise_totale)
    # NTEDU19 — nombre d'échéances par défaut PARAMÉTRABLE par société
    # (``ParametresEducation.get`` singleton get_or_create) : changer le
    # réglage pré-remplit automatiquement le PROCHAIN échéancier généré, sans
    # ressaisie. 10 reste le défaut historique tant qu'aucun réglage dédié
    # n'a été posé.
    nombre_echeances = ParametresEducation.get(eleve.company).nombre_echeances_defaut

    # NTEDU26 — cantine active proratisée, incluse dans CHAQUE mensualité
    # (jamais seulement la 1re, contrairement aux frais d'inscription).
    cantine_mensuel = montant_cantine_mensuel(eleve, annee_scolaire)
    montant_total += cantine_mensuel * nombre_echeances

    with transaction.atomic():
        echeancier = EcheancierScolarite.objects.create(
            company=eleve.company, eleve=eleve, annee_scolaire=annee_scolaire,
            grille_tarifaire=grille, montant_total=montant_total,
            nombre_echeances=nombre_echeances)
        if remises:
            echeancier.remises.set(remises)

        _generer_lignes(
            echeancier, frais_inscription=grille.frais_inscription,
            scolarite_nette=(
                montant_total - grille.frais_inscription
                - cantine_mensuel * nombre_echeances),
            nombre_echeances=nombre_echeances,
            date_debut=annee_scolaire.date_debut,
            cantine_mensuel=cantine_mensuel)

    return echeancier


def _generer_lignes(
        echeancier, *, frais_inscription, scolarite_nette,
        nombre_echeances, date_debut, cantine_mensuel=Decimal('0')):
    """Génère EXACTEMENT ``nombre_echeances`` lignes (aucune ligne
    supplémentaire pour les frais d'inscription — ils sont intégrés à la 1re
    mensualité) : ``échéancier complet`` = un nombre de lignes fixe et
    prévisible, quel que soit le nombre de composantes tarifaires.
    ``cantine_mensuel`` (NTEDU26) est ajouté à CHAQUE ligne (contrairement aux
    frais d'inscription, ponctuels) et tracé séparément sur
    ``LigneEcheance.cantine_montant`` pour un recalcul non-rétroactif."""
    from .models import LigneEcheance

    mensualite = (
        scolarite_nette / nombre_echeances if scolarite_nette else Decimal('0'))
    lignes = []
    for i in range(nombre_echeances):
        montant = (
            mensualite + cantine_mensuel
            + (frais_inscription if i == 0 else Decimal('0')))
        libelle = f"Scolarité — mensualité {i + 1}/{nombre_echeances}"
        if i == 0 and frais_inscription:
            libelle += " (+ frais d'inscription)"
        if cantine_mensuel:
            libelle += " (+ cantine)"
        lignes.append(LigneEcheance(
            company=echeancier.company, echeancier=echeancier,
            libelle=libelle, montant=montant, cantine_montant=cantine_mensuel,
            date_echeance=_add_months(date_debut, i)))

    LigneEcheance.objects.bulk_create(lignes)
