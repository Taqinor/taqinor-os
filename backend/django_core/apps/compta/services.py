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
from django.db.models import Sum
from django.utils import timezone

from .models import (
    BordereauRemise, Caisse, CessionImmobilisation, ClotureCaisse,
    CompteComptable, DotationAmortissement, EcritureComptable, Effet,
    ExerciceComptable, Immobilisation, Journal, LigneEcriture,
    LignePrevisionnelTresorerie, LigneReleve, MouvementCaisse,
    PeriodeComptable, PlanAmortissement, PlanComptable, PointageReleve,
    Rapprochement, RapprochementBancaire, VirementInterne,
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
    ('2811', 'Amortissements des immobilisations en non-valeurs', False, False,
     'passif'),
    ('2832', 'Amortissements du matériel de transport', False, False, 'passif'),
    ('2833', 'Amortissements des installations techniques, matériel et outillage',
     False, False, 'passif'),
    ('2834', 'Amortissements du matériel de transport', False, False, 'passif'),
    ('2835', 'Amortissements du mobilier, matériel de bureau et aménagements',
     False, False, 'passif'),
    # Classe 3 — Actif circulant
    ('3421', 'Clients', True, True, 'actif'),
    ('3425', 'Clients - effets à recevoir', True, True, 'actif'),
    ('3455', 'État - TVA récupérable', False, False, 'actif'),
    ('34552', 'État - TVA récupérable sur charges', False, False, 'actif'),
    # Classe 4 — Passif circulant
    ('4411', 'Fournisseurs', True, True, 'passif'),
    ('4415', 'Fournisseurs - effets à payer', True, True, 'passif'),
    ('4455', 'État - TVA facturée', False, False, 'passif'),
    ('44552', 'État - TVA due', False, False, 'passif'),
    # Classe 5 — Trésorerie
    ('5113', 'Effets à encaisser ou à l\'encaissement', False, False, 'actif'),
    ('5141', 'Banque', False, False, 'actif'),
    ('5161', 'Caisse', False, False, 'actif'),
    ('6147', 'Services bancaires (frais de rejet/effets)', False, False,
     'charge'),
    # Classe 6 — Charges
    ('6111', 'Achats de marchandises', False, False, 'charge'),
    ('6125', 'Achats de matières et fournitures consommables', False, False,
     'charge'),
    ('6191', 'Dotations d\'exploitation aux amortissements', False, False,
     'charge'),
    ('6193', 'Dotations d\'exploitation aux amortissements des immobilisations '
     'corporelles', False, False, 'charge'),
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


# ── FG119 — Plan d'amortissement & dotations postées au grand livre ─────────

# Comptes d'amortissement (classe 28) par catégorie d'immobilisation (CGNC).
# Le matériel de transport amortit sur 2834, l'outillage/matériel sur 2833, le
# mobilier/informatique sur 2835. Défaut prudent : 2833.
_COMPTE_AMORT_PAR_CATEGORIE = {
    Immobilisation.Categorie.VEHICULE: '2834',
    Immobilisation.Categorie.OUTILLAGE: '2833',
    Immobilisation.Categorie.MATERIEL: '2833',
    Immobilisation.Categorie.MOBILIER: '2835',
    Immobilisation.Categorie.INFORMATIQUE: '2835',
    Immobilisation.Categorie.AUTRE: '2833',
}


# Coefficients dégressifs fiscaux marocains (CGI) selon la durée d'utilisation :
# 1,5 pour 3-4 ans, 2 pour 5-6 ans, 3 au-delà de 6 ans. En deçà de 3 ans, pas de
# régime dégressif → coefficient 1 (équivaut au linéaire).
def coefficient_degressif_maroc(duree_annees):
    """Coefficient fiscal dégressif marocain pour une durée donnée (Decimal)."""
    if duree_annees is None:
        return Decimal('1')
    if duree_annees <= 2:
        return Decimal('1')
    if duree_annees <= 4:
        return Decimal('1.5')
    if duree_annees <= 6:
        return Decimal('2')
    return Decimal('3')


def _arrondi(montant):
    return Decimal(montant).quantize(Decimal('0.01'))


def _calcul_annuites(base, duree, mode, coefficient):
    """Renvoie la liste des annuités (Decimal arrondies) pour ``duree`` années.

    * LINÉAIRE : base / durée chaque année ; la dernière année absorbe l'écart
      d'arrondi pour solder exactement la base.
    * DÉGRESSIF : taux dégressif = (100/durée) × coefficient, appliqué à la
      valeur nette résiduelle ; bascule sur le linéaire du résiduel dès que
      celui-ci devient supérieur ou égal à l'annuité dégressive (règle CGI).
      La dernière année solde le résiduel.
    """
    base = Decimal(base)
    if duree < 1 or base <= 0:
        return []
    annuites = []
    if mode == PlanAmortissement.Mode.LINEAIRE:
        annuite = _arrondi(base / Decimal(duree))
        cumul = Decimal('0')
        for an in range(duree):
            if an == duree - 1:
                montant = base - cumul  # solde exact la dernière année.
            else:
                montant = annuite
            cumul += montant
            annuites.append(_arrondi(montant))
        return annuites

    # Dégressif : taux dégressif sur la valeur nette résiduelle.
    taux_deg = (Decimal('100') / Decimal(duree)) * coefficient / Decimal('100')
    residuel = base
    for an in range(duree):
        annees_restantes = duree - an
        if an == duree - 1:
            montant = residuel  # solde exact.
        else:
            deg = residuel * taux_deg
            lineaire_residuel = residuel / Decimal(annees_restantes)
            # Bascule sur le linéaire du résiduel quand il devient plus avantageux.
            montant = max(deg, lineaire_residuel)
            montant = min(montant, residuel)
        montant = _arrondi(montant)
        residuel -= montant
        annuites.append(montant)
    return annuites


@transaction.atomic
def generer_plan_amortissement(immobilisation, *, mode=None, duree_annees=None,
                               base_amortissable=None, date_debut=None,
                               coefficient_degressif=None):
    """Crée/rafraîchit le plan d'amortissement d'une immobilisation (idempotent).

    Calcule le calendrier de dotations selon le ``mode`` (linéaire ou dégressif
    au coefficient marocain) et matérialise une ``DotationAmortissement`` par
    exercice (montant, cumul, valeur nette). RE-GÉNÉRABLE : les dotations DÉJÀ
    POSTÉES au grand livre sont préservées (ni supprimées ni recalculées) ; seules
    les dotations non encore postées sont reconstruites. Les paramètres non
    fournis sont dérivés de l'immobilisation (base = coût HT, date début = date
    d'acquisition, durée = celle déjà sur le plan si présent). Renvoie le plan.
    """
    company = immobilisation.company
    plan, _ = PlanAmortissement.objects.get_or_create(
        company=company, immobilisation=immobilisation,
        defaults={
            'mode': mode or PlanAmortissement.Mode.LINEAIRE,
            'duree_annees': duree_annees or 5,
            'base_amortissable': (
                base_amortissable if base_amortissable is not None
                else immobilisation.cout),
            'date_debut': date_debut or immobilisation.date_acquisition,
        },
    )
    # Mise à jour des paramètres fournis explicitement (re-paramétrage).
    if mode is not None:
        plan.mode = mode
    if duree_annees is not None:
        plan.duree_annees = duree_annees
    if base_amortissable is not None:
        plan.base_amortissable = base_amortissable
    if date_debut is not None:
        plan.date_debut = date_debut
    # Coefficient dégressif figé (explicite ou barème marocain selon la durée).
    if plan.mode == PlanAmortissement.Mode.DEGRESSIF:
        plan.coefficient_degressif = (
            Decimal(coefficient_degressif) if coefficient_degressif is not None
            else coefficient_degressif_maroc(plan.duree_annees))
    else:
        plan.coefficient_degressif = None
    plan.full_clean()
    plan.save()

    coefficient = plan.coefficient_degressif or Decimal('1')
    annuites = _calcul_annuites(
        plan.base_amortissable, plan.duree_annees, plan.mode, coefficient)

    annee_debut = plan.date_debut.year
    cumul = Decimal('0')
    annees_calculees = set()
    for idx, montant in enumerate(annuites):
        annee = annee_debut + idx
        annees_calculees.add(annee)
        cumul += montant
        valeur_nette = _arrondi(plan.base_amortissable - cumul)
        dotation = DotationAmortissement.objects.filter(
            plan=plan, annee=annee).first()
        if dotation and dotation.posted:
            # On NE TOUCHE PAS une dotation déjà postée (immutabilité comptable).
            continue
        from datetime import date as _date
        date_dotation = _date(annee, 12, 31)
        if dotation is None:
            DotationAmortissement.objects.create(
                company=company, plan=plan, annee=annee,
                date_dotation=date_dotation, montant=montant,
                cumul=_arrondi(cumul), valeur_nette=valeur_nette)
        else:
            dotation.montant = montant
            dotation.cumul = _arrondi(cumul)
            dotation.valeur_nette = valeur_nette
            dotation.date_dotation = date_dotation
            dotation.save(update_fields=[
                'montant', 'cumul', 'valeur_nette', 'date_dotation'])
    # Purge les dotations non postées hors du nouveau calendrier (ex. durée
    # raccourcie) ; jamais une dotation postée.
    DotationAmortissement.objects.filter(
        plan=plan, posted=False).exclude(
        annee__in=annees_calculees).delete()
    return plan


def _intitule_compte(numero):
    """Intitulé du compte ``numero`` dans le barème CGNC semé (ou un défaut)."""
    for entry in _COMPTES_CGNC:
        if entry[0] == numero:
            return entry[1]
    return f'Compte {numero}'


def _sens_compte(numero):
    """Sens « naturel » du compte ``numero`` (depuis le barème CGNC ou déduit)."""
    for entry in _COMPTES_CGNC:
        if entry[0] == numero:
            return entry[4]
    classe = numero[0] if numero else ''
    return {
        '1': 'passif', '2': 'actif', '3': 'actif', '4': 'passif',
        '5': 'actif', '6': 'charge', '7': 'produit',
    }.get(classe, 'charge')


def _assurer_compte(company, numero):
    """Renvoie le compte ``numero`` de la société, le créant au besoin (additif).

    Garantit que les comptes de dotation/amortissement existent même sur une
    société semée AVANT l'ajout de ces comptes au barème CGNC. Idempotent.
    """
    compte = get_compte(company, numero)
    if compte is not None:
        return compte
    plan = PlanComptable.objects.filter(company=company).first()
    if plan is None:
        plan = seed_plan_comptable(company)
        compte = get_compte(company, numero)
        if compte is not None:
            return compte
    compte, _ = CompteComptable.objects.get_or_create(
        company=company, numero=numero,
        defaults={
            'plan': plan,
            'intitule': _intitule_compte(numero),
            'classe': _classe_de(numero),
            'sens': _sens_compte(numero),
        },
    )
    return compte


def _compte_dotation(company, plan):
    """Compte de charge (classe 6) de la dotation — celui du plan ou 6193."""
    if plan.compte_dotation_id:
        return plan.compte_dotation
    return _assurer_compte(company, '6193')


def _compte_amortissement(company, plan):
    """Compte d'amortissement (classe 28) — celui du plan ou selon la catégorie."""
    if plan.compte_amortissement_id:
        return plan.compte_amortissement
    numero = _COMPTE_AMORT_PAR_CATEGORIE.get(
        plan.immobilisation.categorie, '2833')
    return _assurer_compte(company, numero)


@transaction.atomic
def poster_dotation(dotation, *, user=None):
    """Poste une dotation au grand livre : débit classe 6 / crédit classe 28.

    Crée une ``EcritureComptable`` ÉQUILIBRÉE (débit du compte de dotation,
    crédit du compte d'amortissement) datée du 31/12 de l'exercice, dans le
    journal OD. Idempotent : une dotation déjà postée renvoie son écriture. RESPECTE
    LE VERROU DE PÉRIODE : si la date de dotation tombe dans une
    ``PeriodeComptable`` verrouillée, lève ``ValidationError`` (on ne contourne
    jamais le lock — même garde-fou que ``creer_ecriture_od``). Renvoie l'écriture.
    """
    company = dotation.company
    plan = dotation.plan
    if dotation.posted and dotation.ecriture_id:
        return dotation.ecriture
    montant = Decimal(dotation.montant)
    if montant <= 0:
        raise ValidationError(
            "Impossible de poster une dotation d'amortissement nulle.")
    # Garde-fou du verrou de période (FG115) — refus explicite, jamais contourné.
    if PeriodeComptable.date_verrouillee(company.id, dotation.date_dotation):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster la dotation "
            f"d'amortissement du {dotation.date_dotation}.")
    compte_dot = _compte_dotation(company, plan)
    compte_amort = _compte_amortissement(company, plan)
    if compte_dot is None or compte_amort is None:
        raise ValidationError(
            "Comptes d'amortissement introuvables : semez le plan comptable.")
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    libelle = (
        f"Dotation amortissement {dotation.annee} — "
        f"{plan.immobilisation.libelle}")
    lignes = [
        {'compte': compte_dot, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle},
        {'compte': compte_amort, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle},
    ]
    ecriture = creer_ecriture(
        company, journal, dotation.date_dotation, libelle, lignes,
        reference=f'AMORT-{plan.immobilisation_id}-{dotation.annee}',
        source_type='dotation_amortissement', source_id=dotation.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    dotation.posted = True
    dotation.ecriture = ecriture
    dotation.save(update_fields=['posted', 'ecriture'])
    return ecriture


# ── FG120 — Cession / mise au rebut d'immobilisation ───────────────────────

# Compte d'immobilisation brute (classe 2) par catégorie : on solde le coût
# d'acquisition par le crédit de ce compte. CGNC : 2340 matériel de transport,
# 2351 matériel et outillage, 2355 mobilier/matériel de bureau, 2356 matériel
# informatique. Défaut prudent : 2351 (matériel et outillage).
_COMPTE_IMMO_PAR_CATEGORIE = {
    Immobilisation.Categorie.VEHICULE: '2340',
    Immobilisation.Categorie.OUTILLAGE: '2351',
    Immobilisation.Categorie.MATERIEL: '2351',
    Immobilisation.Categorie.MOBILIER: '2355',
    Immobilisation.Categorie.INFORMATIQUE: '2355',
    Immobilisation.Categorie.AUTRE: '2351',
}

# Comptes de résultat de cession (CGNC) :
#  * 6513 — VNA des immobilisations corporelles cédées (charge : la VNC sortie).
#  * 7513 — PV / produits de cession des immobilisations corporelles (produit).
_COMPTE_VNA_CESSION = '6513'  # classe 6 — charge (VNC des biens cédés).
_COMPTE_PRODUIT_CESSION = '7513'  # classe 7 — produit (prix de cession).


def _amortissements_cumules(immobilisation, date_cession):
    """Cumul des amortissements de l'immobilisation à la date de cession.

    Source de vérité : le calendrier d'amortissement (FG119). On somme les
    dotations dont la ``date_dotation`` est antérieure ou égale à la date de
    cession (un plan amorti jusqu'à la cession). En l'absence de plan, le cumul
    est nul (l'actif n'a jamais été amorti → VNC = coût). Lecture seule.
    """
    plan = getattr(immobilisation, 'plan_amortissement', None)
    if plan is None:
        return Decimal('0')
    cumul = Decimal('0')
    for dotation in plan.dotations.filter(date_dotation__lte=date_cession):
        cumul += Decimal(dotation.montant)
    return _arrondi(cumul)


def calculer_cession(immobilisation, date_cession, prix_cession,
                     *, type_cession=None):
    """Calcule (sans persister) VNC, cumul d'amortissement et résultat de cession.

    * cumul amort. = Σ dotations postées/calculées jusqu'à la date de cession.
    * VNC = coût d'acquisition − cumul des amortissements (jamais négative).
    * résultat de cession SIGNÉ = prix de cession − VNC. > 0 plus-value,
      < 0 moins-value. Une mise au rebut (prix 0) donne toujours −VNC.

    Renvoie un dict ``{amortissements_cumules, valeur_nette_comptable,
    resultat_cession}``. Pur calcul, lecture seule.
    """
    cout = Decimal(immobilisation.cout or 0)
    prix = Decimal(prix_cession or 0)
    cumul = _amortissements_cumules(immobilisation, date_cession)
    # Le cumul ne peut excéder le coût (un actif est amorti au plus à 100 %).
    cumul = min(cumul, cout)
    vnc = _arrondi(cout - cumul)
    if vnc < 0:
        vnc = Decimal('0.00')
    resultat = _arrondi(prix - vnc)
    return {
        'amortissements_cumules': cumul,
        'valeur_nette_comptable': vnc,
        'resultat_cession': resultat,
    }


@transaction.atomic
def enregistrer_cession(immobilisation, *, date_cession, prix_cession=None,
                        type_cession=None, user=None):
    """Crée la ``CessionImmobilisation`` (calcul figé) — SANS poster l'écriture.

    Fige la VNC, le cumul d'amortissement et le résultat de cession à la date de
    cession. ``type_cession`` est déduit du prix s'il n'est pas fourni (prix 0 →
    rebut, sinon vente). ``company`` posée côté serveur. Renvoie la cession (non
    postée). Le posting passe par ``poster_cession``.
    """
    company = immobilisation.company
    prix = Decimal(prix_cession or 0)
    if type_cession is None:
        type_cession = (
            CessionImmobilisation.Type.REBUT if prix == 0
            else CessionImmobilisation.Type.VENTE)
    if type_cession == CessionImmobilisation.Type.REBUT:
        prix = Decimal('0')
    calc = calculer_cession(immobilisation, date_cession, prix,
                            type_cession=type_cession)
    cession = CessionImmobilisation(
        company=company,
        immobilisation=immobilisation,
        type_cession=type_cession,
        date_cession=date_cession,
        prix_cession=prix,
        amortissements_cumules=calc['amortissements_cumules'],
        valeur_nette_comptable=calc['valeur_nette_comptable'],
        resultat_cession=calc['resultat_cession'],
    )
    cession.full_clean(exclude=['ecriture'])
    cession.save()
    return cession


def _compte_immo_brut(company, immobilisation):
    """Compte d'immobilisation brute (classe 2) selon la catégorie de l'actif."""
    numero = _COMPTE_IMMO_PAR_CATEGORIE.get(immobilisation.categorie, '2351')
    return _assurer_compte(company, numero)


@transaction.atomic
def poster_cession(cession, *, user=None):
    """Poste la cession au grand livre : sortie de l'actif + résultat de cession.

    Écriture ÉQUILIBRÉE (journal OD), datée de la date de cession :

    * REPRISE DES AMORTISSEMENTS — débit du compte d'amortissement (classe 28)
      pour le cumul des amortissements (s'il est non nul) ;
    * SORTIE DE L'IMMOBILISATION — crédit du compte d'immobilisation brute
      (classe 2) pour le coût d'acquisition ;
    * ENCAISSEMENT (vente) — débit d'un compte de tiers/divers pour le prix de
      cession (omis pour une mise au rebut, prix 0) ;
    * CONSTATATION DU RÉSULTAT — l'écart soldant l'écriture : moins-value au
      débit du 6513 (VNA des biens cédés) ou plus-value au crédit du 7513
      (produit de cession).

    Idempotent : une cession déjà postée renvoie son écriture. RESPECTE LE
    VERROU DE PÉRIODE (FG115) : si la date de cession tombe dans une
    ``PeriodeComptable`` verrouillée, lève ``ValidationError`` (jamais
    contourné, même garde-fou que ``poster_dotation``). Marque l'immobilisation
    INACTIVE. Renvoie l'écriture.
    """
    company = cession.company
    immobilisation = cession.immobilisation
    if cession.posted and cession.ecriture_id:
        return cession.ecriture
    # Garde-fou du verrou de période (FG115) — refus explicite, jamais contourné.
    if PeriodeComptable.date_verrouillee(company.id, cession.date_cession):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster la cession de "
            f"l'immobilisation au {cession.date_cession}.")
    cout = Decimal(immobilisation.cout or 0)
    cumul = Decimal(cession.amortissements_cumules or 0)
    prix = Decimal(cession.prix_cession or 0)
    resultat = Decimal(cession.resultat_cession or 0)

    compte_immo = _compte_immo_brut(company, immobilisation)
    # Compte d'amortissement : celui du plan (classe 28) sinon selon catégorie.
    plan = getattr(immobilisation, 'plan_amortissement', None)
    if plan is not None:
        compte_amort = _compte_amortissement(company, plan)
    else:
        compte_amort = _assurer_compte(
            company,
            _COMPTE_AMORT_PAR_CATEGORIE.get(immobilisation.categorie, '2833'))
    # Contrepartie de l'encaissement (vente) : compte de tiers « débiteurs
    # divers » (3481). Pour une vente avec encaissement immédiat, la trésorerie
    # est constatée par le règlement (FG109) — ici on porte la créance de cession.
    compte_creance = _assurer_compte(company, '3481')

    libelle = f"Cession {immobilisation.libelle}"
    lignes = []
    # Reprise des amortissements (débit classe 28) — seulement si non nul.
    if cumul > 0:
        lignes.append({
            'compte': compte_amort, 'debit': cumul, 'credit': Decimal('0'),
            'libelle': f'Reprise amortissements — {immobilisation.libelle}'})
    # Encaissement / créance de cession (débit) — seulement pour une vente.
    if prix > 0:
        lignes.append({
            'compte': compte_creance, 'debit': prix, 'credit': Decimal('0'),
            'libelle': f'Créance de cession — {immobilisation.libelle}'})
    # Constatation du résultat de cession (la ligne qui solde l'écriture).
    if resultat < 0:
        # Moins-value : VNA des immobilisations cédées au débit (charge).
        compte_vna = _assurer_compte(company, _COMPTE_VNA_CESSION)
        lignes.append({
            'compte': compte_vna, 'debit': -resultat, 'credit': Decimal('0'),
            'libelle': f'Moins-value de cession — {immobilisation.libelle}'})
    elif resultat > 0:
        # Plus-value : produit de cession au crédit.
        compte_pv = _assurer_compte(company, _COMPTE_PRODUIT_CESSION)
        lignes.append({
            'compte': compte_pv, 'debit': Decimal('0'), 'credit': resultat,
            'libelle': f'Plus-value de cession — {immobilisation.libelle}'})
    # Sortie de l'immobilisation (crédit classe 2) pour le coût d'acquisition.
    lignes.append({
        'compte': compte_immo, 'debit': Decimal('0'), 'credit': cout,
        'libelle': f"Sortie de l'immobilisation — {immobilisation.libelle}"})

    if cout <= 0 and not lignes:
        raise ValidationError(
            "Impossible de poster la cession d'une immobilisation de coût nul.")
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    ecriture = creer_ecriture(
        company, journal, cession.date_cession, libelle, lignes,
        reference=f'CESSION-{immobilisation.id}',
        source_type='cession_immobilisation', source_id=cession.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    cession.posted = True
    cession.ecriture = ecriture
    cession.save(update_fields=['posted', 'ecriture'])
    # Sortie du patrimoine : l'immobilisation cédée devient inactive.
    if immobilisation.actif:
        immobilisation.actif = False
        immobilisation.save(update_fields=['actif'])
    return ecriture


# ── FG123 — Rapprochement bancaire (relevé ↔ écritures) ────────────────────

def creer_rapprochement(company, compte_tresorerie, *, date_debut, date_fin,
                        libelle='', date_releve=None, solde_releve=None,
                        created_by=None):
    """Crée un rapprochement bancaire pour un ``CompteTresorerie`` (FG123).

    Ouvre un rapprochement ``en_cours`` sur ``[date_debut ; date_fin]`` avec le
    ``solde_releve`` de clôture. ``company`` posée côté serveur ; le compte de
    trésorerie DOIT appartenir à la société, sinon ``ValidationError``. Aucune
    écriture n'est créée — ce n'est PAS un import de paiements (FG42).
    """
    if compte_tresorerie.company_id != company.id:
        raise ValidationError("Compte de trésorerie inconnu.")
    if not date_debut or not date_fin:
        raise ValidationError(
            "Les dates de début et de fin sont obligatoires.")
    if date_fin < date_debut:
        raise ValidationError(
            "La date de fin doit être postérieure à la date de début.")
    rapprochement = RapprochementBancaire.objects.create(
        company=company,
        compte_tresorerie=compte_tresorerie,
        libelle=libelle or '',
        date_debut=date_debut,
        date_fin=date_fin,
        date_releve=date_releve or date_fin,
        solde_releve=Decimal(solde_releve or 0),
        created_by=created_by,
    )
    return rapprochement


def ajouter_ligne_releve(rapprochement, *, date_operation, libelle, montant,
                         reference=''):
    """Ajoute une ligne de relevé bancaire à un rapprochement (FG123).

    ``montant`` est SIGNÉ tel que lu sur le relevé (+ entrée, − sortie). La
    société est héritée du rapprochement (jamais du corps). On ne peut plus
    ajouter de ligne à un rapprochement déjà ``rapproche``.
    """
    if rapprochement.est_rapproche:
        raise ValidationError(
            "Rapprochement déjà clôturé : on ne peut plus ajouter de ligne.")
    if not date_operation:
        raise ValidationError("La date d'opération est obligatoire.")
    return LigneReleve.objects.create(
        company=rapprochement.company,
        rapprochement=rapprochement,
        date_operation=date_operation,
        libelle=libelle or '',
        reference=reference or '',
        montant=Decimal(montant or 0),
    )


@transaction.atomic
def pointer_ligne_releve(ligne_releve, ligne_gl_ids):
    """Apparie une ligne de relevé à une ou plusieurs lignes GL (FG123).

    REMPLACE l'ensemble des lignes GL pointées par ``ligne_gl_ids`` (liste d'IDs
    de ``LigneEcriture``). Chaque ligne GL doit appartenir à la même société ET
    au compte comptable du compte de trésorerie du rapprochement, sinon
    ``ValidationError``. Si le montant GL pointé concorde avec le montant du
    relevé (écart nul) la ligne passe ``rapprochee``, sinon ``non_pointee``.
    Renvoie la ligne de relevé rafraîchie.
    """
    company = ligne_releve.company
    rapprochement = ligne_releve.rapprochement
    compte_treso = rapprochement.compte_tresorerie.compte_comptable_id
    ids = list(dict.fromkeys(ligne_gl_ids or []))  # déduplique, ordre stable.
    lignes_gl = list(LigneEcriture.objects.filter(
        company=company, id__in=ids))
    if len(lignes_gl) != len(ids):
        raise ValidationError("Ligne du grand livre inconnue.")
    for ligne in lignes_gl:
        if ligne.compte_id != compte_treso:
            raise ValidationError(
                "Une ligne pointée doit appartenir au compte de trésorerie "
                "du rapprochement.")
    # Remplace les pointages existants par le nouveau lot.
    PointageReleve.objects.filter(ligne_releve=ligne_releve).delete()
    for ligne in lignes_gl:
        PointageReleve.objects.create(
            company=company, ligne_releve=ligne_releve, ligne_gl=ligne)
    ligne_releve.refresh_from_db()
    if ligne_releve.est_concordante:
        ligne_releve.statut = LigneReleve.Statut.RAPPROCHEE
    else:
        ligne_releve.statut = LigneReleve.Statut.NON_POINTEE
    ligne_releve.save(update_fields=['statut'])
    return ligne_releve


def cloturer_rapprochement(rapprochement):
    """Clôture un rapprochement quand tout concorde (FG123).

    Vérifie via le selector ``resume_rapprochement`` que chaque ligne de relevé
    est concordante (écart nul) ET que l'écart global (solde relevé − solde GL)
    est nul. Si oui, marque le rapprochement ``rapproche`` (idempotent), sinon
    lève ``ValidationError`` avec l'écart restant. Aucune écriture n'est créée.
    """
    from . import selectors

    resume = selectors.resume_rapprochement(rapprochement)
    if not resume['rapproche']:
        raise ValidationError(
            "Rapprochement impossible : il reste un écart de "
            f"{resume['ecart']} ({resume['lignes_non_pointees']} ligne(s) "
            "non concordante(s)).")
    if not rapprochement.est_rapproche:
        rapprochement.statut = RapprochementBancaire.Statut.RAPPROCHE
        rapprochement.date_rapprochement = timezone.now()
        rapprochement.save(update_fields=['statut', 'date_rapprochement'])
    return rapprochement


# ── FG124 — Caisse / petty cash (journal d'espèces) ────────────────────────

def creer_caisse(company, compte_tresorerie, *, libelle, responsable=None,
                 solde_initial=None):
    """Crée une caisse d'espèces rattachée à un compte de trésorerie (FG124).

    Le ``compte_tresorerie`` DOIT appartenir à la société ET être de type
    ``caisse``, sinon ``ValidationError``. ``company`` posée côté serveur.
    Renvoie la ``Caisse``.
    """
    if compte_tresorerie.company_id != company.id:
        raise ValidationError("Compte de trésorerie inconnu.")
    caisse = Caisse(
        company=company,
        compte_tresorerie=compte_tresorerie,
        libelle=libelle or '',
        responsable=responsable,
        solde_initial=Decimal(solde_initial or 0),
    )
    caisse.full_clean()
    caisse.save()
    return caisse


def _derniere_cloture(caisse):
    """Dernière clôture (la plus récente par date) d'une caisse, ou None."""
    return caisse.clotures.order_by('-date_cloture', '-id').first()


@transaction.atomic
def enregistrer_mouvement_caisse(caisse, *, sens, montant, date_mouvement,
                                 motif, justificatif='', piece='',
                                 compte_contrepartie=None, poster=False,
                                 user=None):
    """Enregistre une entrée/sortie d'espèces dans une caisse (FG124).

    ``sens`` ∈ {entree, sortie}, ``montant`` strictement positif. ``company``
    héritée de la caisse (jamais du corps). Refuse un mouvement daté à une date
    déjà CLÔTURÉE (garde-fou du modèle). Si ``poster`` est vrai, passe l'écriture
    de caisse correspondante au grand livre (via ``poster_mouvement_caisse``).
    Renvoie le mouvement.
    """
    company = caisse.company
    if compte_contrepartie is not None and (
            compte_contrepartie.company_id != company.id):
        raise ValidationError("Compte de contrepartie inconnu.")
    mouvement = MouvementCaisse(
        company=company,
        caisse=caisse,
        sens=sens,
        date_mouvement=date_mouvement,
        montant=Decimal(montant or 0),
        motif=motif or '',
        justificatif=justificatif or '',
        piece=piece or '',
        compte_contrepartie=compte_contrepartie,
        created_by=user,
    )
    mouvement.full_clean(exclude=['ecriture'])
    mouvement.save()  # le save() du modèle refuse une date clôturée.
    if poster:
        poster_mouvement_caisse(mouvement, user=user)
    return mouvement


@transaction.atomic
def poster_mouvement_caisse(mouvement, *, user=None):
    """Poste un mouvement de caisse au grand livre (FG124).

    Écriture ÉQUILIBRÉE dans le journal CSH (caisse), datée du mouvement :

    * ENTRÉE — débit du compte de caisse (classe 5) / crédit du compte de
      contrepartie (le compte fourni, sinon 5161 par défaut faute de mieux) ;
    * SORTIE — crédit du compte de caisse / débit du compte de contrepartie
      (typiquement une charge classe 6 pour un achat terrain).

    Le compte de caisse est celui du ``CompteTresorerie`` lié. RESPECTE LE VERROU
    DE PÉRIODE COMPTABLE (FG115) : si la date tombe dans une ``PeriodeComptable``
    verrouillée, lève ``ValidationError``. Idempotent : un mouvement déjà posté
    renvoie son écriture. Renvoie l'écriture.
    """
    company = mouvement.company
    if mouvement.posted and mouvement.ecriture_id:
        return mouvement.ecriture
    montant = Decimal(mouvement.montant or 0)
    if montant <= 0:
        raise ValidationError(
            "Impossible de poster un mouvement de caisse de montant nul.")
    if PeriodeComptable.date_verrouillee(company.id, mouvement.date_mouvement):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster le mouvement "
            f"de caisse du {mouvement.date_mouvement}.")
    compte_caisse = mouvement.caisse.compte_tresorerie.compte_comptable
    contrepartie = mouvement.compte_contrepartie
    if contrepartie is None:
        # Faute de compte de charge/produit fourni, on retombe sur le compte de
        # caisse lui-même comme contrepartie neutre (l'écriture reste équilibrée).
        contrepartie = compte_caisse
    journal = _journal(company, Journal.Type.CAISSE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.CAISSE)
    libelle = f"Caisse — {mouvement.motif}"
    if mouvement.sens == MouvementCaisse.Sens.ENTREE:
        lignes = [
            {'compte': compte_caisse, 'debit': montant, 'credit': Decimal('0'),
             'libelle': libelle},
            {'compte': contrepartie, 'debit': Decimal('0'), 'credit': montant,
             'libelle': libelle},
        ]
    else:
        lignes = [
            {'compte': contrepartie, 'debit': montant, 'credit': Decimal('0'),
             'libelle': libelle},
            {'compte': compte_caisse, 'debit': Decimal('0'), 'credit': montant,
             'libelle': libelle},
        ]
    ecriture = creer_ecriture(
        company, journal, mouvement.date_mouvement, libelle, lignes,
        reference=mouvement.justificatif or f'CAISSE-{mouvement.id}',
        source_type='mouvement_caisse', source_id=mouvement.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    mouvement.posted = True
    mouvement.ecriture = ecriture
    mouvement.save(update_fields=['posted', 'ecriture'])
    return mouvement.ecriture


def solde_caisse(caisse, *, date_fin=None):
    """Solde courant THÉORIQUE d'une caisse (FG124).

    = ``solde_initial`` + Σ(entrées) − Σ(sorties) des mouvements de la caisse
    jusqu'à ``date_fin`` (incluse) si fournie, sinon tous. Lecture seule.
    """
    qs = MouvementCaisse.objects.filter(caisse=caisse)
    if date_fin is not None:
        qs = qs.filter(date_mouvement__lte=date_fin)
    entrees = qs.filter(sens=MouvementCaisse.Sens.ENTREE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    sorties = qs.filter(sens=MouvementCaisse.Sens.SORTIE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    return (caisse.solde_initial or Decimal('0')) + entrees - sorties


@transaction.atomic
def cloturer_caisse(caisse, *, date_cloture, solde_compte, commentaire='',
                    user=None):
    """Clôture de caisse : comptage physique à une date (FG124).

    Fige le ``solde_theorique`` (= ``solde_caisse`` à la date), enregistre le
    ``solde_compte`` (espèces comptées) et calcule l'``ecart`` = compté −
    théorique. À partir de la clôture, tous les mouvements de la caisse datés ≤
    ``date_cloture`` deviennent immuables (garde-fou du modèle). On ne peut pas
    clôturer à une date antérieure ou égale à une clôture déjà posée (l'unicité
    + cette garde l'interdisent). ``company`` posée côté serveur. Renvoie la
    clôture.
    """
    company = caisse.company
    derniere = _derniere_cloture(caisse)
    if derniere is not None and date_cloture <= derniere.date_cloture:
        raise ValidationError(
            "La date de clôture doit être postérieure à la dernière clôture "
            f"({derniere.date_cloture}).")
    theorique = solde_caisse(caisse, date_fin=date_cloture)
    compte = Decimal(solde_compte or 0)
    ecart = compte - theorique
    cloture = ClotureCaisse(
        company=company,
        caisse=caisse,
        date_cloture=date_cloture,
        solde_theorique=theorique,
        solde_compte=compte,
        ecart=ecart,
        commentaire=commentaire or '',
        cloturee_par=user,
    )
    cloture.full_clean()
    cloture.save()
    return cloture


# ── FG125 — Virements internes entre comptes de trésorerie ─────────────────

@transaction.atomic
def enregistrer_virement(company, *, compte_source, compte_destination,
                         date_virement, montant, libelle='', reference='',
                         poster=False, user=None):
    """Enregistre un virement interne entre deux comptes de trésorerie (FG125).

    Les deux comptes DOIVENT appartenir à la société et être DIFFÉRENTS ;
    ``montant`` strictement positif. ``company`` posée côté serveur. Si
    ``poster`` est vrai, l'écriture à deux jambes est passée au grand livre
    (``poster_virement``). Renvoie le virement.
    """
    if compte_source.company_id != company.id:
        raise ValidationError("Compte source inconnu.")
    if compte_destination.company_id != company.id:
        raise ValidationError("Compte destination inconnu.")
    virement = VirementInterne(
        company=company,
        compte_source=compte_source,
        compte_destination=compte_destination,
        date_virement=date_virement,
        montant=Decimal(montant or 0),
        libelle=libelle or '',
        reference=reference or '',
        created_by=user,
    )
    virement.full_clean(exclude=['ecriture'])
    virement.save()
    if poster:
        poster_virement(virement, user=user)
    return virement


@transaction.atomic
def poster_virement(virement, *, user=None):
    """Poste un virement interne au grand livre : écriture à deux jambes (FG125).

    Débit du compte comptable de la DESTINATION (l'argent arrive), crédit du
    compte comptable de la SOURCE (l'argent part), dans le journal OD, à la date
    du virement. RESPECTE LE VERROU DE PÉRIODE (FG115) : refus si la date tombe
    dans une période verrouillée. Idempotent : un virement déjà posté renvoie son
    écriture. Renvoie l'écriture.
    """
    company = virement.company
    if virement.posted and virement.ecriture_id:
        return virement.ecriture
    montant = Decimal(virement.montant or 0)
    if montant <= 0:
        raise ValidationError(
            "Impossible de poster un virement de montant nul.")
    if PeriodeComptable.date_verrouillee(company.id, virement.date_virement):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster le virement "
            f"du {virement.date_virement}.")
    compte_src = virement.compte_source.compte_comptable
    compte_dst = virement.compte_destination.compte_comptable
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    libelle = virement.libelle or (
        f'Virement {virement.compte_source.libelle} → '
        f'{virement.compte_destination.libelle}')
    lignes = [
        {'compte': compte_dst, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle},
        {'compte': compte_src, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle},
    ]
    ecriture = creer_ecriture(
        company, journal, virement.date_virement, libelle, lignes,
        reference=virement.reference or f'VIR-{virement.id}',
        source_type='virement_interne', source_id=virement.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    virement.posted = True
    virement.ecriture = ecriture
    virement.save(update_fields=['posted', 'ecriture'])
    return virement.ecriture


# ── FG126 — Prévisionnel de trésorerie roulant 13 semaines ─────────────────

def creer_ligne_previsionnel(company, *, libelle, date_prevue, montant,
                             categorie=None, recurrence=None, commentaire=''):
    """Crée une ligne prévue de prévisionnel de trésorerie (FG126).

    ``montant`` SIGNÉ (+ encaissement, − décaissement), non nul. ``company``
    posée côté serveur. Renvoie la ligne.
    """
    ligne = LignePrevisionnelTresorerie(
        company=company,
        libelle=libelle or '',
        categorie=categorie or LignePrevisionnelTresorerie.Categorie.AUTRE,
        date_prevue=date_prevue,
        montant=Decimal(montant or 0),
        recurrence=(
            recurrence or LignePrevisionnelTresorerie.Recurrence.AUCUNE),
        commentaire=commentaire or '',
    )
    ligne.full_clean()
    ligne.save()
    return ligne


# ── FG127 / FG128 — Effets (chèques / traites) ─────────────────────────────

def _compte_effets_recevoir(company):
    return _assurer_compte(company, '3425')


def _compte_effets_payer(company):
    return _assurer_compte(company, '4415')


def _compte_effets_encaissement(company):
    return _assurer_compte(company, '5113')


def _compte_frais_bancaires(company):
    return _assurer_compte(company, '6147')


def enregistrer_effet(company, *, sens, montant, date_emission, date_echeance,
                      type_effet=None, numero='', banque='', tireur='',
                      tiers_type='', tiers_id=None, commentaire='', user=None):
    """Enregistre un effet à recevoir (FG127) ou à payer (FG128).

    ``sens`` ∈ {recevoir, payer}, ``montant`` strictement positif, échéance ≥
    émission. Le tiers est référencé en string-FK. ``company`` posée côté
    serveur ; l'effet naît en ``portefeuille``. Renvoie l'effet.
    """
    effet = Effet(
        company=company,
        sens=sens,
        type_effet=type_effet or Effet.TypeEffet.CHEQUE,
        numero=numero or '',
        montant=Decimal(montant or 0),
        date_emission=date_emission,
        date_echeance=date_echeance,
        banque=banque or '',
        tireur=tireur or '',
        tiers_type=tiers_type or '',
        tiers_id=tiers_id,
        commentaire=commentaire or '',
        created_by=user,
    )
    effet.full_clean(exclude=['bordereau'])
    effet.save()
    return effet


@transaction.atomic
def encaisser_effet(effet, *, date_encaissement=None, user=None):
    """Encaisse un effet à recevoir : remis/portefeuille → encaissé (FG127).

    Passe une écriture banque (débit 5141) / crédit du compte d'attente
    (5113 si l'effet était remis, sinon 3425 effets à recevoir), dans le journal
    BNK, à ``date_encaissement`` (défaut : échéance). Refusé en période close.
    Idempotent : un effet déjà encaissé ne bouge plus. Renvoie l'effet.
    """
    if effet.sens != Effet.Sens.RECEVOIR:
        raise ValidationError(
            "Seul un effet à recevoir peut être encaissé.")
    if effet.statut == Effet.Statut.ENCAISSE:
        return effet
    if effet.statut not in (Effet.Statut.PORTEFEUILLE, Effet.Statut.REMIS):
        raise ValidationError(
            "Cet effet ne peut être encaissé dans son état actuel.")
    company = effet.company
    date_enc = date_encaissement or effet.date_echeance
    if PeriodeComptable.date_verrouillee(company.id, date_enc):
        raise ValidationError(
            "Période comptable clôturée : impossible d'encaisser l'effet du "
            f"{date_enc}.")
    montant = Decimal(effet.montant or 0)
    banque = _assurer_compte(company, '5141')
    if effet.statut == Effet.Statut.REMIS:
        contrepartie = _compte_effets_encaissement(company)
    else:
        contrepartie = _compte_effets_recevoir(company)
    journal = _journal(company, Journal.Type.BANQUE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.BANQUE)
    libelle = f'Encaissement effet {effet.numero or effet.id}'
    lignes = [
        {'compte': banque, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle},
        {'compte': contrepartie, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle,
         'tiers_type': effet.tiers_type, 'tiers_id': effet.tiers_id},
    ]
    creer_ecriture(
        company, journal, date_enc, libelle, lignes,
        reference=effet.numero or f'EFFET-{effet.id}',
        source_type='effet_encaissement', source_id=effet.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    effet.statut = Effet.Statut.ENCAISSE
    effet.save(update_fields=['statut'])
    return effet


@transaction.atomic
def payer_effet(effet, *, date_paiement=None, user=None):
    """Paie un effet à payer fournisseur : portefeuille → payé (FG128).

    Débit 4415 effets à payer / crédit 5141 banque, journal BNK, à
    ``date_paiement`` (défaut : échéance). Refusé en période close. Idempotent.
    Renvoie l'effet.
    """
    if effet.sens != Effet.Sens.PAYER:
        raise ValidationError(
            "Seul un effet à payer peut être réglé.")
    if effet.statut == Effet.Statut.PAYE:
        return effet
    if effet.statut != Effet.Statut.PORTEFEUILLE:
        raise ValidationError(
            "Cet effet ne peut être payé dans son état actuel.")
    company = effet.company
    date_pmt = date_paiement or effet.date_echeance
    if PeriodeComptable.date_verrouillee(company.id, date_pmt):
        raise ValidationError(
            "Période comptable clôturée : impossible de payer l'effet du "
            f"{date_pmt}.")
    montant = Decimal(effet.montant or 0)
    banque = _assurer_compte(company, '5141')
    compte_effets = _compte_effets_payer(company)
    journal = _journal(company, Journal.Type.BANQUE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.BANQUE)
    libelle = f'Paiement effet {effet.numero or effet.id}'
    lignes = [
        {'compte': compte_effets, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle,
         'tiers_type': effet.tiers_type, 'tiers_id': effet.tiers_id},
        {'compte': banque, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle},
    ]
    creer_ecriture(
        company, journal, date_pmt, libelle, lignes,
        reference=effet.numero or f'EFFET-{effet.id}',
        source_type='effet_paiement', source_id=effet.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    effet.statut = Effet.Statut.PAYE
    effet.save(update_fields=['statut'])
    return effet


# ── FG129 — Bordereau de remise en banque ──────────────────────────────────

@transaction.atomic
def creer_bordereau(company, compte_tresorerie, *, date_remise, effet_ids=None,
                    reference='', user=None):
    """Crée un bordereau de remise et y rattache des effets à recevoir (FG129).

    Le ``compte_tresorerie`` DOIT appartenir à la société et être une banque.
    Chaque effet de ``effet_ids`` doit être à recevoir, en ``portefeuille`` et
    de la société. Les effets sont rattachés au bordereau (statut inchangé tant
    que non posté). ``company`` posée côté serveur. Renvoie le bordereau.
    """
    if compte_tresorerie.company_id != company.id:
        raise ValidationError("Compte de trésorerie inconnu.")
    if compte_tresorerie.type_compte != 'banque':
        raise ValidationError(
            "Un bordereau de remise se dépose sur un compte bancaire.")
    bordereau = BordereauRemise.objects.create(
        company=company,
        compte_tresorerie=compte_tresorerie,
        reference=reference or '',
        date_remise=date_remise,
        created_by=user,
    )
    ids = list(dict.fromkeys(effet_ids or []))
    if ids:
        effets = list(Effet.objects.filter(
            company=company, id__in=ids, sens=Effet.Sens.RECEVOIR,
            statut=Effet.Statut.PORTEFEUILLE))
        if len(effets) != len(ids):
            raise ValidationError(
                "Effet inconnu, déjà remis ou non éligible.")
        for effet in effets:
            effet.bordereau = bordereau
            effet.save(update_fields=['bordereau'])
    _recalc_total_bordereau(bordereau)
    return bordereau


def _recalc_total_bordereau(bordereau):
    total = bordereau.effets.aggregate(s=Sum('montant'))['s'] or Decimal('0')
    bordereau.total = total
    bordereau.save(update_fields=['total'])
    return total


@transaction.atomic
def poster_bordereau(bordereau, *, user=None):
    """Poste un bordereau de remise au grand livre (FG129).

    Écriture de remise dans le journal OD : débit 5113 « effets à
    l'encaissement » / crédit 3425 « effets à recevoir » pour le total du
    bordereau, puis passe chaque effet lié en ``remis``. Refusé en période close.
    Idempotent : un bordereau déjà posté renvoie son écriture. Renvoie
    l'écriture.
    """
    company = bordereau.company
    if bordereau.posted and bordereau.ecriture_id:
        return bordereau.ecriture
    effets = list(bordereau.effets.all())
    if not effets:
        raise ValidationError(
            "Un bordereau doit comporter au moins un effet.")
    total = _recalc_total_bordereau(bordereau)
    if total <= 0:
        raise ValidationError("Le total du bordereau est nul.")
    if PeriodeComptable.date_verrouillee(company.id, bordereau.date_remise):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster le bordereau "
            f"du {bordereau.date_remise}.")
    compte_enc = _compte_effets_encaissement(company)
    compte_eff = _compte_effets_recevoir(company)
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    libelle = f'Remise effets {bordereau.reference or bordereau.id}'
    lignes = [
        {'compte': compte_enc, 'debit': total, 'credit': Decimal('0'),
         'libelle': libelle},
        {'compte': compte_eff, 'debit': Decimal('0'), 'credit': total,
         'libelle': libelle},
    ]
    ecriture = creer_ecriture(
        company, journal, bordereau.date_remise, libelle, lignes,
        reference=bordereau.reference or f'BORD-{bordereau.id}',
        source_type='bordereau_remise', source_id=bordereau.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    for effet in effets:
        effet.statut = Effet.Statut.REMIS
        effet.save(update_fields=['statut'])
    bordereau.posted = True
    bordereau.ecriture = ecriture
    bordereau.statut = BordereauRemise.Statut.REMIS
    bordereau.save(update_fields=['posted', 'ecriture', 'statut'])
    return bordereau.ecriture


# ── FG130 — Impayés / rejets d'effets ──────────────────────────────────────

@transaction.atomic
def rejeter_effet(effet, *, date_rejet=None, frais_rejet=None, commentaire='',
                  user=None):
    """Constate l'impayé / rejet d'un effet (FG130).

    Rouvre le montant dû en contre-passant la remise (pour un effet à recevoir
    remis : débit 3425 effets à recevoir / crédit 5113 à l'encaissement) et,
    si des ``frais_rejet`` bancaires sont saisis, les comptabilise (débit 6147
    frais bancaires / crédit 5141 banque). L'effet passe ``impaye``, ses frais
    sont figés. Refusé en période close. Renvoie l'effet.
    """
    if effet.statut == Effet.Statut.IMPAYE:
        return effet
    if effet.statut in (Effet.Statut.ENCAISSE, Effet.Statut.PAYE):
        raise ValidationError(
            "Un effet déjà soldé ne peut être rejeté.")
    company = effet.company
    date_r = date_rejet or effet.date_echeance
    if PeriodeComptable.date_verrouillee(company.id, date_r):
        raise ValidationError(
            "Période comptable clôturée : impossible de rejeter l'effet du "
            f"{date_r}.")
    frais = Decimal(frais_rejet or 0)
    if frais < 0:
        raise ValidationError("Les frais de rejet doivent être positifs.")
    journal = _journal(company, Journal.Type.BANQUE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.BANQUE)
    libelle = f'Rejet effet {effet.numero or effet.id}'
    # Réouverture du montant dû pour un effet à recevoir qui avait été remis :
    # on annule l'effet « à l'encaissement » et on rouvre la créance effet.
    if effet.sens == Effet.Sens.RECEVOIR and effet.statut == Effet.Statut.REMIS:
        montant = Decimal(effet.montant or 0)
        compte_eff = _compte_effets_recevoir(company)
        compte_enc = _compte_effets_encaissement(company)
        lignes = [
            {'compte': compte_eff, 'debit': montant, 'credit': Decimal('0'),
             'libelle': libelle,
             'tiers_type': effet.tiers_type, 'tiers_id': effet.tiers_id},
            {'compte': compte_enc, 'debit': Decimal('0'), 'credit': montant,
             'libelle': libelle},
        ]
        creer_ecriture(
            company, journal, date_r, libelle, lignes,
            reference=effet.numero or f'EFFET-{effet.id}',
            source_type='effet_rejet', source_id=effet.id,
            created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    # Frais de rejet bancaires (le cas échéant), écriture distincte.
    if frais > 0:
        compte_frais = _compte_frais_bancaires(company)
        banque = _assurer_compte(company, '5141')
        lignes_frais = [
            {'compte': compte_frais, 'debit': frais, 'credit': Decimal('0'),
             'libelle': f'Frais rejet effet {effet.numero or effet.id}'},
            {'compte': banque, 'debit': Decimal('0'), 'credit': frais,
             'libelle': f'Frais rejet effet {effet.numero or effet.id}'},
        ]
        creer_ecriture(
            company, journal, date_r,
            f'Frais rejet effet {effet.numero or effet.id}', lignes_frais,
            reference=effet.numero or f'EFFET-{effet.id}',
            source_type='effet_frais_rejet', source_id=effet.id,
            created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    effet.statut = Effet.Statut.IMPAYE
    effet.frais_rejet = frais
    if commentaire:
        effet.commentaire = commentaire
    effet.save(update_fields=['statut', 'frais_rejet', 'commentaire'])
    return effet


# ── FG131 — Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur) ────
# Contrôle de pré-paiement : on confronte les trois montants HT d'un même achat —
# COMMANDÉ (bon de commande fournisseur), REÇU (réceptions confirmées) et FACTURÉ
# (factures fournisseur). Les trois documents vivent dans apps.stock ; la compta
# les lit UNIQUEMENT via ``apps.stock.selectors`` (jamais d'import de
# apps.stock.models) et ne fait que comparer. ``company`` posée côté serveur.


def _amounts_3voies(company, bc_id):
    """Lit les trois montants HT (commandé/reçu/facturé) d'un BCF via les
    sélecteurs de stock. Lève ValidationError si le BCF n'est pas de la société.
    """
    from apps.stock import selectors as stock_selectors
    data = stock_selectors.three_way_amounts(company, bc_id)
    if not data.get('exists'):
        raise ValidationError(
            "Bon de commande fournisseur introuvable dans cette société.")
    return data


def _statut_depuis_ecart(ecart, tolerance):
    """Concordant si |écart| ≤ tolérance, sinon écart détecté (bloquant)."""
    if abs(Decimal(ecart or 0)) <= Decimal(tolerance or 0):
        return Rapprochement.Statut.CONCORDANT
    return Rapprochement.Statut.ECART


def creer_rapprochement(company, *, bon_commande_id, tolerance=None, note='',
                        user=None):
    """Crée (ou renvoie) le rapprochement 3 voies d'un BCF et l'évalue (FG131).

    Le BCF doit appartenir à la société (vérifié via le sélecteur de stock).
    Idempotent : un rapprochement existe déjà pour ce BCF → il est ré-évalué et
    renvoyé. ``company`` posée côté serveur. Renvoie le rapprochement.
    """
    # Garde société + existence du BCF (sans importer le modèle stock).
    _amounts_3voies(company, bon_commande_id)
    tol = Decimal(tolerance or 0)
    if tol < 0:
        raise ValidationError("La tolérance doit être positive ou nulle.")
    rapp, _created = Rapprochement.objects.get_or_create(
        company=company, bon_commande_id=bon_commande_id,
        defaults={'tolerance': tol, 'note': note or '', 'created_by': user})
    if not _created:
        # Garde multi-société : un BCF d'une autre société ne peut être réutilisé
        # (unique_together company+bon_commande le garantit déjà au niveau base).
        if note:
            rapp.note = note
        if tolerance is not None:
            rapp.tolerance = tol
    return evaluer_rapprochement(rapp)


def evaluer_rapprochement(rapprochement):
    """Rafraîchit les trois montants HT du rapprochement depuis stock et
    recalcule l'écart reçu↔facturé + le statut (FG131).

    L'écart bloquant pour le paiement = facturé − reçu (on ne paie jamais plus
    que ce qui est entré en stock). Un rapprochement déjà VALIDÉ reste validé
    (le bon-à-payer explicite n'est pas écrasé par une ré-évaluation), mais ses
    snapshots de montants sont tout de même rafraîchis. Renvoie le
    rapprochement.
    """
    data = _amounts_3voies(rapprochement.company, rapprochement.bon_commande_id)
    rapprochement.montant_commande = Decimal(data['montant_commande'] or 0)
    rapprochement.montant_recu = Decimal(data['montant_recu'] or 0)
    rapprochement.montant_facture = Decimal(data['montant_facture'] or 0)
    rapprochement.ecart = (
        rapprochement.montant_facture - rapprochement.montant_recu)
    if rapprochement.statut != Rapprochement.Statut.VALIDE:
        rapprochement.statut = _statut_depuis_ecart(
            rapprochement.ecart, rapprochement.tolerance)
    rapprochement.date_evaluation = timezone.now()
    rapprochement.save(update_fields=[
        'montant_commande', 'montant_recu', 'montant_facture', 'ecart',
        'statut', 'date_evaluation', 'note', 'tolerance'])
    return rapprochement


@transaction.atomic
def valider_rapprochement(rapprochement, *, user=None, commentaire=''):
    """Marque un rapprochement « bon à payer » (FG131).

    Ré-évalue d'abord les montants (snapshot frais), puis valide. On REFUSE la
    validation tant que la facture dépasse le reçu HORS tolérance (écart
    bloquant) : un montant facturé supérieur au reçu doit être corrigé en amont
    (réception manquante ou facture en trop) avant le bon-à-payer. Renvoie le
    rapprochement.
    """
    evaluer_rapprochement(rapprochement)
    if rapprochement.statut == Rapprochement.Statut.ECART:
        raise ValidationError(
            "Écart bloquant (facturé > reçu hors tolérance) : impossible de "
            "valider le rapprochement avant correction.")
    rapprochement.statut = Rapprochement.Statut.VALIDE
    rapprochement.valide_par = user
    rapprochement.date_validation = timezone.now()
    if commentaire:
        rapprochement.note = commentaire
    rapprochement.save(update_fields=[
        'statut', 'valide_par', 'date_validation', 'note'])
    return rapprochement
