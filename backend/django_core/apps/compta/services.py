"""Services de la Comptabilité générale (écritures, seeding, auto-génération).

Point d'entrée WRITE/orchestration du module. Les autres apps n'écrivent JAMAIS
directement les modèles compta : elles passent par ces fonctions. Réciproquement,
la compta lit les autres domaines (ventes…) via LEURS selectors — jamais en
important leurs ``models`` directement (CLAUDE.md, règle de modularité cross-app).

Trois blocs :

* ``seed_plan_comptable`` / ``seed_journaux`` (FG107/FG108) — idempotents.
* ``creer_ecriture`` (FG108) — fabrique une écriture en partie double VÉRIFIÉE
  équilibrée à partir d'une liste de lignes.
* ``ecriture_*_facture/paiement/avoir`` (FG109) — auto-génération depuis un
  document émis, idempotente, OFF par défaut (réglage ``COMPTA_AUTO_ECRITURES``).
* ``cloturer_periode`` / ``rouvrir_periode`` (FG115) — verrouillage/déverrouillage
  d'une période ; ``verifier_facture_modifiable`` garde l'immutabilité des
  factures en période close.
* ``creer_ecriture_od`` (FG116) — écriture de régularisation manuelle (OD) sans
  document source, équilibrée et refusée si la période est verrouillée.
* ``creer_exercice`` / ``reporter_a_nouveaux`` (FG117) — ouverture d'exercice et
  report des soldes de bilan dans le nouvel exercice (à-nouveaux).
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    CompteComptable, EcritureComptable, ExerciceComptable, Journal,
    LigneEcriture, PeriodeComptable, PlanComptable,
)


# ── FG107 / COMPTA1 — Seed du plan comptable CGNC ──────────────────────────

# Jeu de comptes usuels du CGNC marocain (additif, idempotent). Chaque entrée :
# (numéro, intitulé, est_tiers, lettrable, sens).
_COMPTES_CGNC = [
    # Classe 1 — Financement permanent
    ('1111', 'Capital social', False, False, 'passif'),
    ('1191', 'Résultat net en instance d\'affectation', False, False, 'passif'),
    # Classe 2 — Actif immobilisé
    ('2340', 'Matériel de transport', False, False, 'actif'),
    ('2351', 'Matériel et outillage', False, False, 'actif'),
    ('2832', 'Amortissements du matériel de transport', False, False, 'passif'),
    # Classe 3 — Actif circulant
    ('3421', 'Clients', True, True, 'actif'),
    ('3455', 'État - TVA récupérable', False, False, 'actif'),
    ('34552', 'État - TVA récupérable sur charges', False, False, 'actif'),
    # Classe 4 — Passif circulant
    ('4411', 'Fournisseurs', True, True, 'passif'),
    ('4455', 'État - TVA facturée', False, False, 'passif'),
    ('44552', 'État - TVA due', False, False, 'passif'),
    # Classe 5 — Trésorerie
    ('5141', 'Banque', False, False, 'actif'),
    ('5161', 'Caisse', False, False, 'actif'),
    # Classe 6 — Charges
    ('6111', 'Achats de marchandises', False, False, 'charge'),
    ('6125', 'Achats de matières et fournitures consommables', False, False,
     'charge'),
    ('6191', 'Dotations d\'exploitation aux amortissements', False, False,
     'charge'),
    # Classe 7 — Produits
    ('7111', 'Ventes de marchandises', False, False, 'produit'),
    ('7121', 'Ventes de biens et services produits', False, False, 'produit'),
]


def _classe_de(numero):
    return int(numero[0])


@transaction.atomic
def seed_plan_comptable(company):
    """Sème le plan comptable CGNC d'une société (idempotent, additif).

    Crée le ``PlanComptable`` « CGNC » s'il manque, puis chaque compte usuel
    absent. Ne touche JAMAIS un compte existant (intitulé/flags préservés).
    Renvoie le ``PlanComptable``.
    """
    plan, _ = PlanComptable.objects.get_or_create(
        company=company, code='CGNC',
        defaults={'libelle': 'Plan comptable CGNC'},
    )
    for numero, intitule, est_tiers, lettrable, sens in _COMPTES_CGNC:
        CompteComptable.objects.get_or_create(
            company=company, numero=numero,
            defaults={
                'plan': plan,
                'intitule': intitule,
                'classe': _classe_de(numero),
                'sens': sens,
                'est_tiers': est_tiers,
                'lettrable': lettrable,
            },
        )
    return plan


# ── FG108 / COMPTA4 — Seed des journaux ────────────────────────────────────

_JOURNAUX = [
    ('VTE', 'Journal des ventes', Journal.Type.VENTE),
    ('ACH', 'Journal des achats', Journal.Type.ACHAT),
    ('BNK', 'Journal de banque', Journal.Type.BANQUE),
    ('CSH', 'Journal de caisse', Journal.Type.CAISSE),
    ('OD', 'Opérations diverses', Journal.Type.OPERATIONS_DIVERSES),
]


@transaction.atomic
def seed_journaux(company):
    """Sème les journaux standards d'une société (idempotent, additif)."""
    created = []
    for code, libelle, type_journal in _JOURNAUX:
        journal, _ = Journal.objects.get_or_create(
            company=company, code=code,
            defaults={'libelle': libelle, 'type_journal': type_journal},
        )
        created.append(journal)
    return created


def get_compte(company, numero):
    """Compte de la société par numéro (ou None). Lecture seule."""
    return CompteComptable.objects.filter(
        company=company, numero=numero).first()


# ── FG108 / COMPTA7 — Fabrique d'écriture en partie double ─────────────────

@transaction.atomic
def creer_ecriture(company, journal, date_ecriture, libelle, lignes, *,
                   reference='', source_type='', source_id=None,
                   created_by=None, statut=None):
    """Crée une écriture équilibrée et ses lignes, ou lève ``ValidationError``.

    ``lignes`` est une liste de dicts : ``{'compte', 'debit', 'credit',
    'libelle'?, 'tiers_type'?, 'tiers_id'?}``. La somme des débits doit égaler
    la somme des crédits, sinon RIEN n'est créé (transaction atomique).
    """
    debit_total = sum((Decimal(lig.get('debit') or 0) for lig in lignes),
                      Decimal('0'))
    credit_total = sum((Decimal(lig.get('credit') or 0) for lig in lignes),
                       Decimal('0'))
    if not lignes:
        raise ValidationError("Une écriture doit comporter au moins une ligne.")
    if debit_total != credit_total:
        raise ValidationError(
            "L'écriture comptable doit être équilibrée : "
            f"Σ débit ({debit_total}) ≠ Σ crédit ({credit_total})."
        )
    ecriture = EcritureComptable.objects.create(
        company=company,
        journal=journal,
        date_ecriture=date_ecriture,
        libelle=libelle,
        reference=reference,
        source_type=source_type,
        source_id=source_id,
        created_by=created_by,
        statut=statut or EcritureComptable.Statut.BROUILLON,
    )
    for ligne in lignes:
        LigneEcriture.objects.create(
            company=company,
            ecriture=ecriture,
            compte=ligne['compte'],
            libelle=ligne.get('libelle', '') or '',
            debit=Decimal(ligne.get('debit') or 0),
            credit=Decimal(ligne.get('credit') or 0),
            tiers_type=ligne.get('tiers_type', '') or '',
            tiers_id=ligne.get('tiers_id'),
        )
    # Garde-fou final : revalide l'équilibre côté modèle.
    ecriture.clean()
    return ecriture


# ── FG109 / COMPTA12-14 — Auto-génération depuis les documents ─────────────

def auto_ecritures_actif():
    """Toggle maître de l'auto-génération. OFF par défaut → rien ne change.

    Le founder active la passation automatique des écritures en posant
    ``COMPTA_AUTO_ECRITURES = True`` (settings) ou la variable d'env du même
    nom. Tant que c'est faux, aucun document ne génère d'écriture.
    """
    return bool(getattr(settings, 'COMPTA_AUTO_ECRITURES', False))


def _comptes_requis(company):
    """Sème le plan/journaux si besoin et renvoie les comptes/journaux usuels.

    Garantit que l'auto-génération dispose toujours de ses comptes même sur une
    société qui n'a pas encore été semée explicitement (idempotent).
    """
    if not PlanComptable.objects.filter(company=company).exists():
        seed_plan_comptable(company)
    if not Journal.objects.filter(company=company).exists():
        seed_journaux(company)
    return {
        'clients': get_compte(company, '3421'),
        'fournisseurs': get_compte(company, '4411'),
        'tva_facturee': get_compte(company, '4455'),
        'tva_recuperable': get_compte(company, '3455'),
        'ventes': get_compte(company, '7121'),
        'achats': get_compte(company, '6111'),
        'banque': get_compte(company, '5141'),
        'caisse': get_compte(company, '5161'),
    }


def _journal(company, type_journal):
    return Journal.objects.filter(
        company=company, type_journal=type_journal).first()


def _ecriture_existante(company, source_type, source_id):
    return EcritureComptable.objects.filter(
        company=company, source_type=source_type, source_id=source_id).first()


@transaction.atomic
def ecriture_pour_facture(facture, *, force=False, user=None):
    """Génère l'écriture de vente d'une facture client (3421 / 71xx / 4455).

    Débit 3421 Clients (TTC), crédit 71xx Ventes (HT) + 4455 TVA facturée.
    Idempotent : ne recrée pas l'écriture d'une facture déjà passée. Renvoie
    l'écriture (existante ou nouvelle), ou None si désactivé/non applicable.

    ``facture`` est une instance ``ventes.Facture`` ; on lit ses montants via
    ses propriétés publiques (total_ht/total_tva/total_ttc) — pas d'import de
    modèle d'une autre app dans la signature, seulement la donnée passée.
    """
    if not force and not auto_ecritures_actif():
        return None
    company = facture.company
    if company is None:
        return None
    existante = _ecriture_existante(company, 'facture', facture.id)
    if existante:
        return existante
    comptes = _comptes_requis(company)
    journal = _journal(company, Journal.Type.VENTE)
    ht = Decimal(facture.total_ht)
    tva = Decimal(facture.total_tva)
    ttc = Decimal(facture.total_ttc)
    client_id = getattr(facture, 'client_id', None)
    lignes = [
        {'compte': comptes['clients'], 'debit': ttc, 'credit': Decimal('0'),
         'libelle': f'Facture {facture.reference}',
         'tiers_type': 'client', 'tiers_id': client_id},
        {'compte': comptes['ventes'], 'debit': Decimal('0'), 'credit': ht,
         'libelle': f'Vente {facture.reference}'},
    ]
    if tva:
        lignes.append({
            'compte': comptes['tva_facturee'], 'debit': Decimal('0'),
            'credit': tva, 'libelle': f'TVA {facture.reference}'})
    return creer_ecriture(
        company, journal, facture.date_emission,
        f'Facture client {facture.reference}', lignes,
        reference=facture.reference, source_type='facture',
        source_id=facture.id, created_by=user,
        statut=EcritureComptable.Statut.VALIDEE,
    )


@transaction.atomic
def ecriture_pour_paiement(paiement, *, force=False, user=None):
    """Génère l'écriture d'encaissement d'un paiement client (514x/516x → 3421).

    Débit trésorerie (banque/caisse selon le mode), crédit 3421 Clients.
    Idempotent. Renvoie l'écriture, ou None si désactivé/non applicable.
    """
    if not force and not auto_ecritures_actif():
        return None
    company = paiement.company
    if company is None:
        return None
    existante = _ecriture_existante(company, 'paiement', paiement.id)
    if existante:
        return existante
    comptes = _comptes_requis(company)
    mode = getattr(paiement, 'mode', '')
    if mode == 'especes':
        compte_treso = comptes['caisse']
        journal = _journal(company, Journal.Type.CAISSE)
    else:
        compte_treso = comptes['banque']
        journal = _journal(company, Journal.Type.BANQUE)
    montant = Decimal(paiement.montant)
    facture = paiement.facture
    client_id = getattr(facture, 'client_id', None)
    ref = getattr(facture, 'reference', '')
    lignes = [
        {'compte': compte_treso, 'debit': montant, 'credit': Decimal('0'),
         'libelle': f'Encaissement {ref}'},
        {'compte': comptes['clients'], 'debit': Decimal('0'), 'credit': montant,
         'libelle': f'Règlement {ref}',
         'tiers_type': 'client', 'tiers_id': client_id},
    ]
    return creer_ecriture(
        company, journal, paiement.date_paiement,
        f'Encaissement facture {ref}', lignes,
        reference=ref, source_type='paiement', source_id=paiement.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )


@transaction.atomic
def ecriture_pour_avoir(avoir, *, force=False, user=None):
    """Génère l'écriture d'un avoir client (contre-passation de la vente).

    Débit 71xx Ventes (HT) + 4455 TVA, crédit 3421 Clients (TTC) — l'inverse de
    la facture. Idempotent. Renvoie l'écriture, ou None si désactivé.
    """
    if not force and not auto_ecritures_actif():
        return None
    company = avoir.company
    if company is None:
        return None
    existante = _ecriture_existante(company, 'avoir', avoir.id)
    if existante:
        return existante
    comptes = _comptes_requis(company)
    journal = _journal(company, Journal.Type.VENTE)
    ht = Decimal(avoir.total_ht)
    tva = Decimal(avoir.total_tva)
    ttc = Decimal(avoir.total_ttc)
    client_id = getattr(avoir, 'client_id', None)
    lignes = [
        {'compte': comptes['ventes'], 'debit': ht, 'credit': Decimal('0'),
         'libelle': f'Avoir {avoir.reference}'},
    ]
    if tva:
        lignes.append({
            'compte': comptes['tva_facturee'], 'debit': tva,
            'credit': Decimal('0'), 'libelle': f'TVA avoir {avoir.reference}'})
    lignes.append({
        'compte': comptes['clients'], 'debit': Decimal('0'), 'credit': ttc,
        'libelle': f'Avoir {avoir.reference}',
        'tiers_type': 'client', 'tiers_id': client_id})
    return creer_ecriture(
        company, journal, avoir.date_emission,
        f'Avoir client {avoir.reference}', lignes,
        reference=avoir.reference, source_type='avoir', source_id=avoir.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )


# ── FG115 — Clôture & verrouillage de période comptable ────────────────────

@transaction.atomic
def cloturer_periode(periode, *, user=None):
    """Verrouille une période : ses écritures & factures deviennent immuables.

    Idempotent (re-clôturer une période déjà close ne change rien d'autre que
    de rafraîchir l'acteur/horodatage si manquants). Renvoie la période.
    """
    if not periode.verrouillee:
        periode.verrouillee = True
        periode.date_verrouillage = timezone.now()
        periode.verrouillee_par = user
        periode.save(update_fields=[
            'verrouillee', 'date_verrouillage', 'verrouillee_par'])
    return periode


@transaction.atomic
def rouvrir_periode(periode):
    """Déverrouille une période close (correction admin). Renvoie la période.

    Lève ``ValidationError`` si la période appartient à un exercice déjà
    clôturé (FG117) — on rouvre alors l'exercice d'abord.
    """
    if periode.exercice_id and periode.exercice.est_cloture:
        raise ValidationError(
            "Impossible de rouvrir une période d'un exercice clôturé : "
            "rouvrez d'abord l'exercice.")
    if periode.verrouillee:
        periode.verrouillee = False
        periode.date_verrouillage = None
        periode.verrouillee_par = None
        periode.save(update_fields=[
            'verrouillee', 'date_verrouillage', 'verrouillee_par'])
    return periode


def periode_verrouillee_pour(company, une_date):
    """Période VERROUILLÉE couvrant ``une_date`` (ou None). Lecture seule."""
    if une_date is None:
        return None
    return PeriodeComptable.objects.filter(
        company=company, verrouillee=True,
        date_debut__lte=une_date, date_fin__gte=une_date,
    ).first()


def verifier_facture_modifiable(facture):
    """Garde l'immutabilité d'une facture en période close (FG115).

    À appeler depuis la couche service de ``ventes`` avant toute modification
    d'une facture. ``facture`` est lue par valeur (``company``, ``date_emission``)
    — aucun import du modèle ``ventes`` ici. Lève ``ValidationError`` si la
    date de la facture tombe dans une période verrouillée.
    """
    company = getattr(facture, 'company', None)
    une_date = getattr(facture, 'date_emission', None)
    if company is None or une_date is None:
        return
    if PeriodeComptable.date_verrouillee(company.id, une_date):
        raise ValidationError(
            "Période comptable clôturée : la facture du "
            f"{une_date} est verrouillée et ne peut plus être modifiée.")


def creer_periode(company, date_debut, date_fin, *, type_periode=None,
                  libelle='', exercice=None):
    """Crée (ou récupère) une période comptable pour la société (idempotent).

    L'unicité ``(company, date_debut, date_fin)`` garantit qu'on ne duplique
    jamais une même période. Renvoie la ``PeriodeComptable``.
    """
    periode, _ = PeriodeComptable.objects.get_or_create(
        company=company, date_debut=date_debut, date_fin=date_fin,
        defaults={
            'type_periode': type_periode or PeriodeComptable.Type.MOIS,
            'libelle': libelle,
            'exercice': exercice,
        },
    )
    return periode


# ── FG116 — Écritures de régularisation / OD manuelles ─────────────────────

@transaction.atomic
def creer_ecriture_od(company, date_ecriture, libelle, lignes, *,
                      journal=None, reference='', created_by=None,
                      statut=None):
    """Écriture de régularisation manuelle (OD) sans document source.

    Pour provisions, amortissements, corrections… : pas de ``source_type``/
    ``source_id`` (écriture purement manuelle). Passe par le journal OD par
    défaut, exige l'équilibre Σ débit = Σ crédit (via ``creer_ecriture``) et est
    refusée si la période de ``date_ecriture`` est verrouillée (garde-fou du
    modèle, FG115). Sème le journal OD au besoin. Renvoie l'écriture.
    """
    if journal is None:
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
        if journal is None:
            seed_journaux(company)
            journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if PeriodeComptable.date_verrouillee(company.id, date_ecriture):
        raise ValidationError(
            "Période comptable clôturée : impossible de saisir une écriture "
            f"de régularisation au {date_ecriture}.")
    return creer_ecriture(
        company, journal, date_ecriture, libelle, lignes,
        reference=reference, created_by=created_by,
        statut=statut or EcritureComptable.Statut.VALIDEE,
    )


# ── FG117 — À-nouveaux / réouverture d'exercice ────────────────────────────

def creer_exercice(company, date_debut, date_fin, *, libelle=''):
    """Crée (ou récupère) un exercice comptable (idempotent). Renvoie l'objet."""
    exercice, _ = ExerciceComptable.objects.get_or_create(
        company=company, date_debut=date_debut, date_fin=date_fin,
        defaults={'libelle': libelle},
    )
    return exercice


@transaction.atomic
def cloturer_exercice(exercice, *, user=None):
    """Clôture un exercice : statut ``cloture`` + verrouille toutes ses périodes.

    Idempotent. Renvoie l'exercice. La réouverture (correction) passe par
    ``rouvrir_exercice``.
    """
    if not exercice.est_cloture:
        exercice.statut = ExerciceComptable.Statut.CLOTURE
        exercice.date_cloture = timezone.now()
        exercice.save(update_fields=['statut', 'date_cloture'])
    for periode in exercice.periodes.all():
        cloturer_periode(periode, user=user)
    return exercice


@transaction.atomic
def rouvrir_exercice(exercice):
    """Rouvre un exercice clôturé (correction admin). Renvoie l'exercice."""
    if exercice.est_cloture:
        exercice.statut = ExerciceComptable.Statut.OUVERT
        exercice.date_cloture = None
        exercice.save(update_fields=['statut', 'date_cloture'])
    return exercice


# Comptes de bilan : classes 1 à 5 (le résultat des classes 6/7 est soldé via
# le compte de résultat — non reporté tel quel en à-nouveau).
_CLASSES_BILAN = (1, 2, 3, 4, 5)


@transaction.atomic
def reporter_a_nouveaux(exercice_clos, exercice_nouveau, *, user=None):
    """Reporte les soldes de bilan de l'exercice clos dans le nouvel exercice.

    « À-nouveaux » : on solde chaque compte de bilan (classes 1-5) de
    l'exercice clos par une écriture d'ouverture datée du premier jour du
    nouvel exercice, dans le journal AN (À-nouveaux). Idempotent : ne reporte
    pas deux fois (``ExerciceComptable.an_reporte``). Renvoie l'écriture créée
    (ou None s'il n'y a aucun solde à reporter).

    Le résultat (classes 6/7) n'est PAS reporté ligne à ligne ; il est porté au
    bilan via le CPC et s'affecte ensuite (1191) — hors périmètre de ce report
    automatique d'à-nouveaux de bilan.
    """
    from . import selectors  # import local : évite tout cycle au chargement.

    company = exercice_clos.company
    if company != exercice_nouveau.company:
        raise ValidationError(
            "Les deux exercices doivent appartenir à la même société.")
    if exercice_nouveau.an_reporte:
        return _ecriture_an_existante(company, exercice_nouveau)

    # Journal AN (créé au besoin).
    journal = _journal(company, Journal.Type.A_NOUVEAUX)
    if journal is None:
        journal, _ = Journal.objects.get_or_create(
            company=company, code='AN',
            defaults={'libelle': 'À-nouveaux',
                      'type_journal': Journal.Type.A_NOUVEAUX})

    # Soldes des comptes de bilan à la date de fin de l'exercice clos.
    lignes = []
    for compte in CompteComptable.objects.filter(
            company=company, classe__in=_CLASSES_BILAN).order_by('numero'):
        solde = selectors.solde_compte(
            company, compte, date_fin=exercice_clos.date_fin)
        if solde == Decimal('0'):
            continue
        if solde > 0:
            lignes.append({'compte': compte, 'debit': solde,
                           'credit': Decimal('0'),
                           'libelle': "À-nouveau"})
        else:
            lignes.append({'compte': compte, 'debit': Decimal('0'),
                           'credit': -solde, 'libelle': "À-nouveau"})

    exercice_nouveau.an_reporte = True
    exercice_nouveau.save(update_fields=['an_reporte'])
    if not lignes:
        return None
    ecriture = creer_ecriture(
        company, journal, exercice_nouveau.date_debut,
        "Report des à-nouveaux", lignes,
        reference=f'AN-{exercice_nouveau.date_debut.year}',
        source_type='a_nouveaux', source_id=exercice_nouveau.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    return ecriture


def _ecriture_an_existante(company, exercice):
    return EcritureComptable.objects.filter(
        company=company, source_type='a_nouveaux',
        source_id=exercice.id).first()
