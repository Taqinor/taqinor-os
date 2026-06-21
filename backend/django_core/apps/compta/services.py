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
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    CompteComptable, EcritureComptable, Journal, LigneEcriture, PlanComptable,
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
    debit_total = sum((Decimal(l.get('debit') or 0) for l in lignes),
                      Decimal('0'))
    credit_total = sum((Decimal(l.get('credit') or 0) for l in lignes),
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
