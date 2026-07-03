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
import csv
import hashlib
import io
from decimal import ROUND_HALF_UP, Decimal
from math import asin, cos, radians, sin, sqrt

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    AvancementRevenu, BaremeIndemnite, BordereauRemise, Budget, BudgetLigne,
    Caisse, Campagne, CautionBancaire, CentreCout, CessionImmobilisation,
    ClotureCaisse,
    CommissionPayoutLine, CommissionPayoutRun, CompteComptable,
    CompteTresorerie, ContratAvancement, DeclarationTVA,
    DemandeApprobationConfig, DotationAmortissement,
    ECatalogue, EcritureComptable, Effet, EntiteConsolidation,
    ExerciceComptable, MessageWhatsAppEntrant,
    Immobilisation, IndemniteChantier, Journal, LigneEcriture,
    LignePrevisionnelTresorerie, LigneReleve, MouvementCaisse, NoteFrais,
    OuverturePartage,
    PaymentRun, PaymentRunLine, PeriodeComptable, PlanAmortissement,
    PlanComptable, PointageReleve, ProvisionCreance, Rapprochement,
    RapprochementBancaire, RelanceDevisAbandonne, RetenueSource,
    RetenueGarantie, TimbreFiscal,
    TravauxEnCours, VirementInterne,
    EcheanceAO, ResultatAO, ComptePortailClient,
    PaiementFacturePortail,
    MappingCompte, CompteAuxiliaire,
    PisteAuditComptable,
    ModeleRapprochement,
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
    ('3427', 'Clients - factures à établir', True, True, 'actif'),
    ('3424', 'Clients douteux ou litigieux', True, True, 'actif'),
    ('3134', 'Travaux en cours', False, False, 'actif'),
    ('3455', 'État - TVA récupérable', False, False, 'actif'),
    ('34552', 'État - TVA récupérable sur charges', False, False, 'actif'),
    # XACC1 — TVA récupérable EN ATTENTE (régime encaissement) : la TVA d'un
    # achat non encore réglé au fournisseur transite ici avant de basculer sur
    # 3455 au règlement (transfert au prorata via
    # ``transferer_tva_encaissement``).
    ('34551', 'État - TVA récupérable en attente (encaissement)', False,
     False, 'actif'),
    ('3942', 'Provisions pour dépréciation des clients', False, False,
     'actif'),
    # Classe 4 — Passif circulant
    ('4411', 'Fournisseurs', True, True, 'passif'),
    ('4415', 'Fournisseurs - effets à payer', True, True, 'passif'),
    ('4455', 'État - TVA facturée', False, False, 'passif'),
    # XACC1 — TVA facturée EN ATTENTE (régime encaissement) : la TVA d'une
    # vente non encore encaissée transite ici avant de basculer sur 4455 au
    # règlement client (transfert au prorata du paiement, acomptes inclus).
    ('44551', 'État - TVA facturée en attente (encaissement)', False, False,
     'passif'),
    ('44552', 'État - TVA due', False, False, 'passif'),
    ('4491', "Produits constatés d'avance", False, False, 'passif'),
    ('4486', 'Fournisseurs - factures non parvenues', True, True, 'passif'),
    # Paie (CGNC 44x) — rémunérations dues + organismes sociaux & fiscaux
    ('4432', 'Rémunérations dues au personnel', False, False, 'passif'),
    ('4441', 'Caisse Nationale de Sécurité Sociale (CNSS)', False, False,
     'passif'),
    ('4443', 'Caisses de retraite (CIMR)', False, False, 'passif'),
    ('4452', 'État - Impôts sur les rémunérations (IR)', False, False,
     'passif'),
    # Classe 5 — Trésorerie
    ('5113', 'Effets à encaisser ou à l\'encaissement', False, False, 'actif'),
    ('5141', 'Banque', False, False, 'actif'),
    ('5161', 'Caisse', False, False, 'actif'),
    ('6147', 'Services bancaires (frais de rejet/effets)', False, False,
     'charge'),
    # Classe 6 — Charges
    ('6111', 'Achats de marchandises', False, False, 'charge'),
    ('6171', 'Rémunérations du personnel', False, False, 'charge'),
    ('6174', 'Charges sociales (cotisations patronales)', False, False,
     'charge'),
    ('6125', 'Achats de matières et fournitures consommables', False, False,
     'charge'),
    ('6191', 'Dotations d\'exploitation aux amortissements', False, False,
     'charge'),
    ('6193', 'Dotations d\'exploitation aux amortissements des immobilisations '
     'corporelles', False, False, 'charge'),
    ('6196', 'Dotations aux provisions pour dépréciation de l\'actif '
     'circulant', False, False, 'charge'),
    # Classe 7 — Produits
    ('7111', 'Ventes de marchandises', False, False, 'produit'),
    ('7121', 'Ventes de biens et services produits', False, False, 'produit'),
    ('7196', 'Reprises sur provisions pour dépréciation de l\'actif '
     'circulant', False, False, 'produit'),
    ('7132', 'Variation des stocks de travaux en cours', False, False,
     'produit'),
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
    # COMPTA4 — journal des à-nouveaux (report de bilan) semé d'office. Il était
    # créé à la demande par ``reporter_a_nouveaux`` ; on l'ajoute au seed
    # standard pour que les 6 journaux CGNC (VTE/ACH/BNK/CSH/OD/AN) existent dès
    # l'amorçage. Idempotent : ``get_or_create`` ne duplique jamais.
    ('AN', 'À-nouveaux', Journal.Type.A_NOUVEAUX),
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
            centre_cout=ligne.get('centre_cout'),
        )
    # Garde-fou final : revalide l'équilibre côté modèle.
    ecriture.clean()
    return ecriture


# ── COMPTA40 — Séparation des tâches (saisie vs validation vs clôture) ──────

def valider_ecriture(ecriture, *, user):
    """Valide une écriture au titre du « second regard » (COMPTA40).

    Séparation des tâches : la personne qui a SAISI l'écriture
    (``created_by``) ne peut JAMAIS être celle qui la VALIDE. Un autre
    utilisateur habilité doit poser le second contrôle. Lève
    ``ValidationError`` si :

    * l'écriture est déjà validée (idempotence stricte : on refuse) ;
    * le valideur est aussi le saisisseur (violation de la séparation) ;
    * aucun valideur n'est fourni.

    En cas de succès, passe l'écriture à ``VALIDEE`` et horodate le contrôle
    (``valide_par`` / ``date_validation``). N'altère pas les lignes ; l'équilibre
    reste garanti par ``clean()`` au moment de la saisie.
    """
    if user is None:
        raise ValidationError(
            "Un valideur est requis pour valider une écriture.")
    if ecriture.statut == EcritureComptable.Statut.VALIDEE:
        raise ValidationError("Cette écriture est déjà validée.")
    if ecriture.created_by_id is not None and ecriture.created_by_id == user.id:
        raise ValidationError(
            "Séparation des tâches : la personne qui a saisi l'écriture ne "
            "peut pas la valider elle-même. Un second contrôleur est requis.")
    ecriture.statut = EcritureComptable.Statut.VALIDEE
    ecriture.valide_par = user
    ecriture.date_validation = timezone.now()
    ecriture.save(update_fields=['statut', 'valide_par', 'date_validation'])
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


# ── XACC1 — TVA sur encaissement : transfert du compte d'attente ───────────
# En régime « débit » (défaut), la TVA est constatée directement sur les
# comptes définitifs (4455/3455) à la facturation — RIEN ne change ici, c'est
# le comportement historique de ``ecriture_pour_facture``/
# ``ecriture_pour_facture_fournisseur``. En régime « encaissement »
# (``PlanComptable.regime_tva``), la TVA facturée/récupérable doit transiter
# par un compte d'attente (44551/34551) jusqu'au règlement effectif : c'est ce
# que fait ``transferer_tva_encaissement``, destinée à être appelée à
# l'enregistrement d'un paiement. Le bus ``core.events`` (M6) n'émet à ce jour
# AUCUN événement portant un ``ventes.Paiement`` (``payment_captured`` porte
# une ``core.PaymentTransaction`` — capture carte en ligne, en amont du
# ``Paiement`` métier) : suivant le même point d'ancrage documenté dans
# ``receivers.py``, cette fonction reste donc déclenchée par APPEL DE SERVICE
# EXPLICITE depuis ``ventes`` (à la manière de ``ecriture_pour_paiement``) tant
# que ``ventes``/``stock`` n'émettent pas cet événement dédié — l'ajouter là-bas
# est hors périmètre additif ici (modifierait ``ventes``).

def regime_tva_societe(company):
    """Régime de TVA effectif de la société (``debit`` par défaut).

    Lecture seule. Sème le plan comptable au besoin (idempotent) pour que le
    réglage soit toujours lisible, même sur une société jamais semée.
    """
    plan = PlanComptable.objects.filter(company=company).first()
    if plan is None:
        plan = seed_plan_comptable(company)
    return plan.regime_tva


def _compte_tva_attente_facturee(company):
    return _assurer_compte(company, '44551')


def _compte_tva_attente_recuperable(company):
    return _assurer_compte(company, '34551')


@transaction.atomic
def transferer_tva_encaissement(paiement, *, montant=None, user=None,
                                force=False):
    """Transfère la TVA du compte d'attente vers le compte définitif (XACC1).

    ``paiement`` est une instance ``ventes.Paiement`` (lue par valeur — aucun
    import du modèle). Ne fait RIEN (renvoie ``None``) si :

    * la société n'est pas en régime ``encaissement`` (régime ``debit`` =
      comportement inchangé) ;
    * la facture liée ne porte pas de TVA ;
    * une écriture de transfert existe déjà pour ce paiement (idempotence).

    Le transfert est calculé AU PRORATA du montant réellement encaissé par
    rapport au TTC de la facture (acomptes inclus : un paiement partiel ne
    transfère que sa quote-part de TVA). Débite 4455 (TVA facturée) et crédite
    44551 (attente) à hauteur de la quote-part de TVA — l'écriture est de fait
    un virement de compte à compte, toujours équilibrée. Respecte le verrou de
    période (``creer_ecriture_od`` refuse une période clôturée). Renvoie
    l'écriture de transfert, ou ``None`` si non applicable.
    """
    company = getattr(paiement, 'company', None)
    if company is None:
        facture = getattr(paiement, 'facture', None)
        company = getattr(facture, 'company', None)
    if company is None:
        return None
    if not force and regime_tva_societe(company) != PlanComptable.RegimeTVA.ENCAISSEMENT:
        return None
    facture = paiement.facture
    ttc = Decimal(getattr(facture, 'total_ttc', 0) or 0)
    tva_facture = Decimal(getattr(facture, 'total_tva', 0) or 0)
    if ttc <= 0 or tva_facture <= 0:
        return None
    existante = _ecriture_existante(company, 'tva_encaissement', paiement.id)
    if existante:
        return existante
    montant_regle = Decimal(montant) if montant is not None \
        else Decimal(paiement.montant)
    if montant_regle <= 0:
        return None
    # Quote-part de TVA proportionnelle au montant réellement encaissé,
    # plafonnée à la TVA totale de la facture (un paiement > solde ne
    # transfère jamais plus que la TVA due).
    quote_part_tva = (tva_facture * montant_regle / ttc).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    quote_part_tva = min(quote_part_tva, tva_facture)
    if quote_part_tva <= 0:
        return None
    compte_attente = _compte_tva_attente_facturee(company)
    compte_definitif = _assurer_compte(company, '4455')
    ref = getattr(facture, 'reference', '')
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = [
        {'compte': compte_attente, 'debit': quote_part_tva,
         'credit': Decimal('0'),
         'libelle': f'Transfert TVA encaissement {ref}'},
        {'compte': compte_definitif, 'debit': Decimal('0'),
         'credit': quote_part_tva,
         'libelle': f'TVA due sur encaissement {ref}'},
    ]
    return creer_ecriture(
        company, journal, paiement.date_paiement,
        f'Transfert TVA encaissement {ref}', lignes,
        reference=ref, source_type='tva_encaissement', source_id=paiement.id,
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


# ── COMPTA15 — Auto-écriture depuis une facture fournisseur (achat) ─────────
# Symétrique de ``ecriture_pour_facture`` (vente), mais côté ACHAT : la facture
# reçue d'un fournisseur débite une charge (61xx) + la TVA récupérable (3455x)
# et crédite le compte collectif fournisseurs (4411). ``facture`` est une
# instance ``stock.FactureFournisseur`` : on lit UNIQUEMENT ses attributs
# publics (montant_ht/montant_tva/montant_ttc, reference, fournisseur_id,
# date_facture) — aucun import du modèle d'une autre app. Idempotent, gardé par
# le toggle ``COMPTA_AUTO_ECRITURES`` (OFF par défaut). Le compte de charge peut
# être surchargé via le mapping DC22 (``type_clef='famille'``).

@transaction.atomic
def ecriture_pour_facture_fournisseur(facture, *, force=False, user=None,
                                      famille_charge=None):
    """Génère l'écriture d'achat d'une facture fournisseur (61xx/3455 → 4411).

    Débit 61xx Achats/Charges (HT) + 3455 TVA récupérable (TVA), crédit 4411
    Fournisseurs (TTC). Idempotent : ne recrée pas l'écriture d'une facture déjà
    passée. Renvoie l'écriture (existante ou nouvelle), ou None si désactivé/non
    applicable. ``famille_charge`` (optionnel) consulte le mapping DC22 pour
    router vers un compte de charge précis (défaut : 6111 Achats).
    """
    if not force and not auto_ecritures_actif():
        return None
    company = facture.company
    if company is None:
        return None
    existante = _ecriture_existante(company, 'facture_fournisseur', facture.id)
    if existante:
        return existante
    comptes = _comptes_requis(company)
    journal = _journal(company, Journal.Type.ACHAT)
    ht = Decimal(getattr(facture, 'montant_ht', 0) or 0)
    tva = Decimal(getattr(facture, 'montant_tva', 0) or 0)
    ttc = Decimal(getattr(facture, 'montant_ttc', 0) or 0)
    fournisseur_id = getattr(facture, 'fournisseur_id', None)
    reference = getattr(facture, 'reference', '') or ''
    # DC22 : famille de charge → compte 6x (défaut 6111 si non mappé).
    compte_charge = compte_pour_clef(
        company, MappingCompte.TypeClef.FAMILLE, famille_charge,
        defaut=comptes['achats']) if famille_charge else comptes['achats']
    lignes = [
        {'compte': compte_charge, 'debit': ht, 'credit': Decimal('0'),
         'libelle': f'Achat {reference}'},
    ]
    if tva:
        lignes.append({
            'compte': comptes['tva_recuperable'], 'debit': tva,
            'credit': Decimal('0'),
            'libelle': f'TVA récupérable {reference}'})
    lignes.append({
        'compte': comptes['fournisseurs'], 'debit': Decimal('0'), 'credit': ttc,
        'libelle': f'Facture fournisseur {reference}',
        'tiers_type': 'fournisseur', 'tiers_id': fournisseur_id})
    return creer_ecriture(
        company, journal, getattr(facture, 'date_facture', None),
        f'Facture fournisseur {reference}', lignes,
        reference=reference, source_type='facture_fournisseur',
        source_id=facture.id, created_by=user,
        statut=EcritureComptable.Statut.VALIDEE,
    )


# ── COMPTA16 — Auto-écriture depuis un paiement fournisseur ─────────────────
# Symétrique de ``ecriture_pour_paiement`` (encaissement client) : le règlement
# d'une facture fournisseur débite 4411 Fournisseurs (on solde la dette) et
# crédite la trésorerie (banque/caisse selon le mode). ``paiement`` est une
# instance ``stock.PaiementFournisseur`` — lecture des seuls attributs publics.

@transaction.atomic
def ecriture_pour_paiement_fournisseur(paiement, *, force=False, user=None):
    """Génère l'écriture d'un paiement fournisseur (4411 → 514x/516x).

    Débit 4411 Fournisseurs (on solde la dette), crédit trésorerie (banque, ou
    caisse si mode ``especes``). Idempotent. Renvoie l'écriture, ou None si
    désactivé/non applicable.
    """
    if not force and not auto_ecritures_actif():
        return None
    company = paiement.company
    if company is None:
        return None
    existante = _ecriture_existante(
        company, 'paiement_fournisseur', paiement.id)
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
    montant = Decimal(getattr(paiement, 'montant', 0) or 0)
    facture = getattr(paiement, 'facture', None)
    fournisseur_id = getattr(facture, 'fournisseur_id', None)
    ref = getattr(facture, 'reference', '') or ''
    lignes = [
        {'compte': comptes['fournisseurs'], 'debit': montant,
         'credit': Decimal('0'), 'libelle': f'Règlement {ref}',
         'tiers_type': 'fournisseur', 'tiers_id': fournisseur_id},
        {'compte': compte_treso, 'debit': Decimal('0'), 'credit': montant,
         'libelle': f'Décaissement {ref}'},
    ]
    return creer_ecriture(
        company, journal, getattr(paiement, 'date_paiement', None),
        f'Paiement fournisseur {ref}', lignes,
        reference=ref, source_type='paiement_fournisseur',
        source_id=paiement.id, created_by=user,
        statut=EcritureComptable.Statut.VALIDEE,
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


# ── XACC2 — Import de la balance d'ouverture (reprise des existants) ────────
# Aucun outil de reprise n'existait pour démarrer la compta d'une société sur
# TAQINOR OS : import CSV guidé de la balance d'ouverture par compte (avec, en
# option, les items ouverts par tiers pour la balance âgée/lettrage dès le
# jour 1). Une seule écriture d'ouverture équilibrée est postée au journal AN,
# idempotente par exercice (rejouable sans doublon).

BALANCE_OUVERTURE_COLONNES = [
    'compte', 'libelle', 'debit', 'credit', 'tiers_type', 'tiers_id',
]


def gabarit_import_balance_ouverture():
    """Fichier modèle (CSV) téléchargeable pour l'import de balance d'ouverture.

    Colonnes : ``compte`` (numéro CGNC existant), ``libelle`` (optionnel),
    ``debit``/``credit`` (l'un des deux, jamais les deux), ``tiers_type``/
    ``tiers_id`` (optionnels — poser sur un compte tiers 3421/4411 rattache la
    ligne à un item ouvert par tiers, cf. ``CompteAuxiliaire``). Renvoie les
    octets du CSV.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(BALANCE_OUVERTURE_COLONNES)
    writer.writerow(['3421', 'Client Dupont — solde ouverture', '12000', '',
                     'client', '1'])
    writer.writerow(['4411', 'Fournisseur Atlas — solde ouverture', '', '5000',
                     'fournisseur', '3'])
    writer.writerow(['1111', 'Capital social', '', '50000', '', ''])
    return buffer.getvalue().encode('utf-8-sig')


def _valider_ligne_balance_ouverture(company, index, row):
    """Valide UNE ligne du fichier de balance d'ouverture.

    Renvoie ``(ligne_ecriture_dict_ou_None, erreur_ou_None)``. N'écrit rien :
    validation pure, ligne par ligne, pour le rapport d'erreurs (COMPTA3).
    """
    numero = (row.get('compte') or '').strip()
    if not numero:
        return None, {'ligne': index, 'raison': 'numéro de compte manquant'}
    compte = get_compte(company, numero)
    if compte is None:
        return None, {
            'ligne': index, 'raison': f'compte inconnu : {numero!r}'}
    raw_debit = (row.get('debit') or '').strip()
    raw_credit = (row.get('credit') or '').strip()
    try:
        debit = Decimal(raw_debit.replace(',', '.')) if raw_debit else Decimal('0')
        credit = Decimal(raw_credit.replace(',', '.')) if raw_credit else Decimal('0')
    except Exception:
        return None, {
            'ligne': index, 'raison': 'débit/crédit non numérique'}
    if debit and credit:
        return None, {
            'ligne': index,
            'raison': 'une ligne ne peut porter à la fois débit et crédit'}
    if not debit and not credit:
        return None, {'ligne': index, 'raison': 'débit et crédit tous deux nuls'}
    if debit < 0 or credit < 0:
        return None, {'ligne': index, 'raison': 'montant négatif refusé'}
    tiers_type = (row.get('tiers_type') or '').strip().lower()
    tiers_id_raw = (row.get('tiers_id') or '').strip()
    tiers_id = None
    if tiers_type and tiers_id_raw:
        try:
            tiers_id = int(tiers_id_raw)
        except ValueError:
            return None, {
                'ligne': index, 'raison': f'tiers_id non numérique : {tiers_id_raw!r}'}
    return {
        'compte': compte,
        'debit': debit,
        'credit': credit,
        'libelle': (row.get('libelle') or '').strip() or "Balance d'ouverture",
        'tiers_type': tiers_type,
        'tiers_id': tiers_id,
    }, None


def valider_balance_ouverture(company, rows):
    """Valide TOUTES les lignes d'un import de balance d'ouverture.

    ``rows`` est une liste de dicts (une ligne de fichier = un dict de
    colonnes). Renvoie ``{'lignes': [...valides...], 'erreurs': [...]}``. Une
    ligne totalement vide est ignorée silencieusement (pas une erreur).
    """
    lignes, erreurs = [], []
    for i, row in enumerate(rows, start=1):
        if not any((v or '').strip() for v in row.values() if isinstance(v, str)):
            continue
        ligne, erreur = _valider_ligne_balance_ouverture(company, i, row)
        if erreur:
            erreurs.append(erreur)
        else:
            lignes.append(ligne)
    return {'lignes': lignes, 'erreurs': erreurs}


@transaction.atomic
def importer_balance_ouverture(company, rows, *, exercice, date_ecriture=None,
                               user=None):
    """Importe la balance d'ouverture : UNE écriture AN équilibrée + items ouverts.

    Valide d'abord TOUTES les lignes (``valider_balance_ouverture``) — si la
    moindre erreur est trouvée, RIEN n'est écrit et le rapport d'erreurs par
    ligne est renvoyé (``{'ok': False, 'erreurs': [...]}``). Sinon, poste une
    écriture unique au journal AN dont la somme des débits doit égaler la somme
    des crédits (sinon ``ValidationError`` — fichier de balance déséquilibré).
    Les lignes portant un ``tiers_type``/``tiers_id`` deviennent des items
    ouverts (non lettrés) rattachés à l'auxiliaire correspondant, prêts pour la
    balance âgée et le lettrage dès le jour 1 (COMPTA3). IDEMPOTENT par
    exercice : rejouer le même exercice renvoie l'écriture déjà postée sans
    dupliquer (``source_type='balance_ouverture'``, ``source_id=exercice.id``).
    """
    existante = _ecriture_existante(company, 'balance_ouverture', exercice.id)
    if existante:
        return {'ok': True, 'ecriture': existante, 'erreurs': [],
                'deja_importee': True}
    verif = valider_balance_ouverture(company, rows)
    if verif['erreurs']:
        return {'ok': False, 'ecriture': None, 'erreurs': verif['erreurs']}
    if not verif['lignes']:
        return {'ok': False, 'ecriture': None,
                'erreurs': [{'ligne': 0, 'raison': 'fichier vide'}]}
    journal = _journal(company, Journal.Type.A_NOUVEAUX)
    if journal is None:
        journal, _ = Journal.objects.get_or_create(
            company=company, code='AN',
            defaults={'libelle': 'À-nouveaux',
                      'type_journal': Journal.Type.A_NOUVEAUX})
    date_piece = date_ecriture or exercice.date_debut
    ecriture = creer_ecriture(
        company, journal, date_piece, "Balance d'ouverture", verif['lignes'],
        reference=f'AN-OUV-{exercice.id}', source_type='balance_ouverture',
        source_id=exercice.id, created_by=user,
        statut=EcritureComptable.Statut.VALIDEE,
    )
    return {'ok': True, 'ecriture': ecriture, 'erreurs': [],
            'deja_importee': False}


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


# ── XACC3 — Auto-suggestion de rapprochement bancaire ───────────────────────

@transaction.atomic
def accepter_suggestions_rapprochement(rapprochement):
    """Pointe en un clic les suggestions NON ambiguës (XACC3).

    Relit ``selectors.suggestions_rapprochement`` et, pour chaque ligne de
    relevé suggérée, pointe AUTOMATIQUEMENT la meilleure candidate SEULEMENT
    si : il y a au moins un candidat, la suggestion n'est PAS ``ambigue``
    (deux candidats à égalité de score ne sont JAMAIS auto-acceptés — l'humain
    tranche), et le score du meilleur candidat est strictement positif. JAMAIS
    de pointage silencieux : chaque ligne effectivement pointée est listée dans
    le retour. Renvoie ``{'pointees': [...ligne_releve_id...], 'ignorees':
    [{'ligne_releve_id', 'raison'}, ...]}``.
    """
    from . import selectors

    suggestions = selectors.suggestions_rapprochement(rapprochement)
    pointees, ignorees = [], []
    for sugg in suggestions:
        if sugg['ambigue']:
            ignorees.append({
                'ligne_releve_id': sugg['ligne_releve_id'],
                'raison': 'ambiguë : plusieurs candidats au même score'})
            continue
        if not sugg['candidats']:
            ignorees.append({
                'ligne_releve_id': sugg['ligne_releve_id'],
                'raison': 'aucun candidat'})
            continue
        meilleur = sugg['candidats'][0]
        ligne_releve = LigneReleve.objects.get(
            company=rapprochement.company, id=sugg['ligne_releve_id'])
        pointer_ligne_releve(ligne_releve, [meilleur['ligne_gl_id']])
        pointees.append(sugg['ligne_releve_id'])
    return {'pointees': pointees, 'ignorees': ignorees}


# ── XACC4 — Modèles de rapprochement (règles de contrepartie automatique) ──

def modele_correspondant(company, libelle_releve):
    """Premier ``ModeleRapprochement`` actif dont le motif matche (ou None).

    Trié par ``priorite`` croissante (plus petit = prioritaire). Lecture seule.
    """
    for modele in ModeleRapprochement.objects.filter(
            company=company, actif=True).order_by('priorite', 'id'):
        if modele.correspond(libelle_releve):
            return modele
    return None


@transaction.atomic
def appliquer_modele_rapprochement(ligne_releve, modele=None):
    """Applique une règle de contrepartie à une ligne de relevé (XACC4).

    Sans ``modele`` explicite, résout la première règle active dont le motif
    matche le libellé (``modele_correspondant``) — lève ``ValidationError`` si
    aucune ne correspond. Crée une écriture ÉQUILIBRÉE banque↔contrepartie
    (débit/crédit selon le signe du montant : une sortie d'argent débite la
    contrepartie et crédite la banque, une entrée l'inverse), ventile la TVA si
    ``modele.taux_tva`` est posé, puis POINTE la ligne de relevé sur la ligne
    banque de l'écriture créée. Respecte le verrou de période (``creer_
    ecriture``). Idempotent : rejouer sur la même ligne de relevé déjà pointée
    ne recrée rien (renvoie l'écriture existante liée à son pointage).
    """
    company = ligne_releve.company
    rapprochement = ligne_releve.rapprochement
    if ligne_releve.statut == LigneReleve.Statut.RAPPROCHEE:
        pointage = PointageReleve.objects.filter(
            ligne_releve=ligne_releve).select_related(
            'ligne_gl__ecriture').first()
        if pointage:
            return pointage.ligne_gl.ecriture
    if modele is None:
        modele = modele_correspondant(company, ligne_releve.libelle)
    if modele is None:
        raise ValidationError(
            "Aucun modèle de rapprochement ne correspond à cette ligne.")
    if modele.company_id != company.id:
        raise ValidationError("Modèle de rapprochement inconnu.")
    montant = (Decimal(modele.montant_fixe)
               if modele.montant_fixe is not None
               else abs(Decimal(ligne_releve.montant or 0)))
    if montant <= 0:
        raise ValidationError(
            "Le montant à comptabiliser doit être strictement positif.")
    compte_banque = rapprochement.compte_tresorerie.compte_comptable
    entree = (ligne_releve.montant or Decimal('0')) >= 0
    lignes = []
    if modele.taux_tva:
        taux = Decimal(modele.taux_tva) / Decimal('100')
        tva = (montant * taux / (1 + taux)).quantize(Decimal('0.01'))
        ht = montant - tva
        compte_tva = _assurer_compte(company, '34552')
    else:
        tva = Decimal('0')
        ht = montant
        compte_tva = None
    if entree:
        lignes.append({'compte': compte_banque, 'debit': montant,
                       'credit': Decimal('0'), 'libelle': modele.libelle})
        lignes.append({'compte': modele.compte_contrepartie, 'debit': Decimal('0'),
                       'credit': ht, 'libelle': modele.libelle})
        if tva:
            lignes.append({'compte': compte_tva, 'debit': Decimal('0'),
                           'credit': tva, 'libelle': f'TVA {modele.libelle}'})
    else:
        lignes.append({'compte': modele.compte_contrepartie, 'debit': ht,
                       'credit': Decimal('0'), 'libelle': modele.libelle})
        if tva:
            lignes.append({'compte': compte_tva, 'debit': tva,
                           'credit': Decimal('0'), 'libelle': f'TVA {modele.libelle}'})
        lignes.append({'compte': compte_banque, 'debit': Decimal('0'),
                       'credit': montant, 'libelle': modele.libelle})
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    ecriture = creer_ecriture(
        company, journal, ligne_releve.date_operation,
        f'{modele.libelle} — {ligne_releve.libelle}', lignes,
        reference=ligne_releve.reference,
        source_type='modele_rapprochement', source_id=ligne_releve.id,
        statut=EcritureComptable.Statut.VALIDEE,
    )
    ligne_gl_banque = ecriture.lignes.get(compte=compte_banque)
    pointer_ligne_releve(ligne_releve, [ligne_gl_banque.id])
    return ecriture


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


def creer_rapprochement_3voies(company, *, bon_commande_id, tolerance=None,
                               note='', user=None):
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


# ── FG133 — Campagnes de règlement fournisseurs (payment run) ──────────────
# Sélection de dettes fournisseur dues → proposition de paiement par échéance →
# post EN LOT (une écriture : débit 4411 par ligne / crédit 5141 banque). Les
# fournisseurs restent en string-FK ; on ne lit leur nom/coordonnées qu'à travers
# le sélecteur de stock (jamais d'import de apps.stock.models).


def _compte_fournisseurs(company):
    return _assurer_compte(company, '4411')


def _coordonnees_fournisseur(company, tiers_id):
    """Nom + RIB/IBAN d'un fournisseur via le sélecteur de stock (cross-app).

    N'importe JAMAIS ``apps.stock.models`` : passe par
    ``apps.stock.selectors.get_fournisseur_by_id``. Renvoie un dict
    ``{'nom', 'rib', 'iban'}`` (valeurs vides si le tiers/champ est inconnu).
    """
    nom = rib = iban = ''
    if tiers_id is not None:
        try:
            from apps.stock.selectors import get_fournisseur_by_id
            fournisseur = get_fournisseur_by_id(company, tiers_id)
        except Exception:  # pragma: no cover - défensif
            fournisseur = None
        if fournisseur is not None:
            nom = getattr(fournisseur, 'nom', '') or ''
            rib = getattr(fournisseur, 'rib', '') or ''
            iban = getattr(fournisseur, 'iban', '') or ''
    return {'nom': nom, 'rib': rib, 'iban': iban}


@transaction.atomic
def creer_payment_run(company, *, date_paiement, mode_paiement=None,
                      compte_tresorerie=None, reference='', note='',
                      lignes=None, user=None):
    """Crée une campagne de règlement fournisseurs et ses lignes (FG133).

    ``lignes`` est une liste de dicts ``{'tiers_id', 'montant',
    'reference'?, 'date_echeance'?, 'beneficiaire'?, 'rib'?, 'iban'?}``. Pour
    chaque ligne sans bénéficiaire/coordonnées explicites, on complète depuis le
    sélecteur de stock (nom + RIB/IBAN). Le ``compte_tresorerie``, s'il est
    fourni, DOIT appartenir à la société. ``company`` posée côté serveur. La
    campagne naît en ``brouillon`` ; le total est recalculé. Renvoie la campagne.
    """
    if compte_tresorerie is not None and compte_tresorerie.company_id != company.id:
        raise ValidationError("Compte de trésorerie inconnu.")
    run = PaymentRun.objects.create(
        company=company,
        reference=reference or '',
        mode_paiement=mode_paiement or PaymentRun.ModePaiement.VIREMENT,
        compte_tresorerie=compte_tresorerie,
        date_paiement=date_paiement,
        note=note or '',
        created_by=user,
    )
    for ligne in (lignes or []):
        ajouter_ligne_payment_run(run, **ligne)
    _recalc_total_payment_run(run)
    return run


def ajouter_ligne_payment_run(run, *, tiers_id=None, montant,
                              tiers_type='fournisseur', reference='',
                              date_echeance=None, beneficiaire='', rib='',
                              iban=''):
    """Ajoute une ligne d'échéance à une campagne en ``brouillon`` (FG133).

    Complète le bénéficiaire et les coordonnées bancaires manquants depuis le
    sélecteur de stock. Refuse un montant non strictement positif et une campagne
    déjà figée/postée. Renvoie la ligne.
    """
    if run.statut != PaymentRun.Statut.BROUILLON:
        raise ValidationError(
            "Une campagne figée ou postée ne peut plus être modifiée.")
    montant = Decimal(montant or 0)
    if montant <= 0:
        raise ValidationError(
            "Le montant d'une ligne de règlement doit être strictement "
            "positif.")
    if not (beneficiaire and (rib or iban)):
        coord = _coordonnees_fournisseur(run.company, tiers_id)
        beneficiaire = beneficiaire or coord['nom']
        rib = rib or coord['rib']
        iban = iban or coord['iban']
    ligne = PaymentRunLine.objects.create(
        company=run.company,
        payment_run=run,
        tiers_type=tiers_type or 'fournisseur',
        tiers_id=tiers_id,
        beneficiaire=beneficiaire or '',
        reference=reference or '',
        montant=montant,
        date_echeance=date_echeance,
        rib=rib or '',
        iban=iban or '',
    )
    _recalc_total_payment_run(run)
    return ligne


def _recalc_total_payment_run(run):
    total = run.lignes.aggregate(s=Sum('montant'))['s'] or Decimal('0')
    run.total = total
    run.save(update_fields=['total'])
    return total


def figer_payment_run(run):
    """Fige la proposition d'une campagne : ``brouillon`` → ``proposee`` (FG133).

    Idempotent (une campagne déjà figée reste figée). Refuse une campagne vide.
    Renvoie la campagne.
    """
    if run.statut == PaymentRun.Statut.POSTEE:
        raise ValidationError("Une campagne postée ne peut être refigée.")
    if not run.lignes.exists():
        raise ValidationError(
            "Une campagne doit comporter au moins une ligne.")
    _recalc_total_payment_run(run)
    if run.statut == PaymentRun.Statut.BROUILLON:
        run.statut = PaymentRun.Statut.PROPOSEE
        run.save(update_fields=['statut'])
    return run


@transaction.atomic
def poster_payment_run(run, *, user=None):
    """Poste une campagne de règlement au grand livre EN LOT (FG133).

    Une seule écriture (journal BNK) : un débit 4411 Fournisseurs par ligne (avec
    l'auxiliaire tiers de la ligne) et un crédit 5141 Banque pour le total —
    l'écriture solde les dettes fournisseur réglées. Requiert un compte de
    trésorerie payeur (banque). Refusé en période close. Idempotent : une campagne
    déjà postée renvoie son écriture. Renvoie l'écriture.
    """
    company = run.company
    if run.posted and run.ecriture_id:
        return run.ecriture
    lignes = list(run.lignes.all())
    if not lignes:
        raise ValidationError(
            "Une campagne doit comporter au moins une ligne.")
    total = _recalc_total_payment_run(run)
    if total <= 0:
        raise ValidationError("Le total de la campagne est nul.")
    if run.compte_tresorerie_id is None:
        raise ValidationError(
            "Un compte de trésorerie payeur est requis pour poster la "
            "campagne.")
    treso = run.compte_tresorerie
    if treso.type_compte != 'banque':
        raise ValidationError(
            "Le règlement par virement se débite d'un compte bancaire.")
    if PeriodeComptable.date_verrouillee(company.id, run.date_paiement):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster la campagne "
            f"du {run.date_paiement}.")
    journal = _journal(company, Journal.Type.BANQUE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.BANQUE)
    compte_fourn = _compte_fournisseurs(company)
    libelle = f'Règlement fournisseurs {run.reference or run.id}'
    ecriture_lignes = []
    for ligne in lignes:
        ecriture_lignes.append({
            'compte': compte_fourn,
            'debit': Decimal(ligne.montant or 0),
            'credit': Decimal('0'),
            'libelle': (f'Règlement {ligne.beneficiaire or ligne.tiers_id} '
                        f'{ligne.reference}').strip(),
            'tiers_type': ligne.tiers_type,
            'tiers_id': ligne.tiers_id,
        })
    ecriture_lignes.append({
        'compte': treso.compte_comptable,
        'debit': Decimal('0'),
        'credit': total,
        'libelle': libelle,
    })
    ecriture = creer_ecriture(
        company, journal, run.date_paiement, libelle, ecriture_lignes,
        reference=run.reference or f'PAYRUN-{run.id}',
        source_type='payment_run', source_id=run.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    run.posted = True
    run.ecriture = ecriture
    run.statut = PaymentRun.Statut.POSTEE
    run.save(update_fields=['posted', 'ecriture', 'statut'])
    return ecriture


# ── FG134 — Génération de fichier de virement bancaire ─────────────────────
# Export d'un payment run (en virement) au format d'ordre de virement de la
# banque. Format texte tabulé pivot, simple et lisible par la plupart des portails
# bancaires marocains (import « multi-virements » CSV/délimité). LECTURE SEULE :
# l'export ne modifie ni la campagne ni le grand livre.

# En-tête du fichier de virement (champs d'un ordre de virement multiple).
FICHIER_VIREMENT_HEADERS = [
    'Beneficiaire', 'RIB', 'IBAN', 'Montant', 'Devise', 'Reference', 'Motif',
]


def fichier_virement(run):
    """Construit le fichier de virement bancaire d'une campagne (FG134).

    Une ligne par échéance EN VIREMENT de la campagne : bénéficiaire, RIB/IBAN,
    montant au centime, devise (MAD), référence et motif. Renvoie
    ``{'headers', 'rows', 'total', 'nb_lignes', 'mode_paiement'}`` — la vue se
    charge de la sérialisation texte/CSV. Lecture seule.

    Lève ``ValidationError`` si la campagne n'est pas un virement, ou si une
    ligne n'a ni RIB ni IBAN (un virement sans coordonnées bancaires ne peut
    être exécuté).
    """
    if run.mode_paiement != PaymentRun.ModePaiement.VIREMENT:
        raise ValidationError(
            "Le fichier de virement ne s'exporte que pour une campagne en "
            "virement bancaire.")
    lignes = list(run.lignes.all())
    if not lignes:
        raise ValidationError(
            "La campagne ne comporte aucune ligne à exporter.")
    rows = []
    total = Decimal('0')
    devise = 'MAD'
    if run.compte_tresorerie_id is not None:
        devise = run.compte_tresorerie.devise or 'MAD'
    for ligne in lignes:
        if not (ligne.rib or ligne.iban):
            raise ValidationError(
                "Coordonnées bancaires manquantes pour "
                f"« {ligne.beneficiaire or ligne.tiers_id} » : un virement "
                "exige un RIB ou un IBAN.")
        montant = Decimal(ligne.montant or 0).quantize(Decimal('0.01'))
        total += montant
        rows.append([
            ligne.beneficiaire or '',
            ligne.rib or '',
            ligne.iban or '',
            str(montant),
            devise,
            ligne.reference or '',
            f'Règlement {ligne.reference}'.strip() or 'Règlement fournisseur',
        ])
    return {
        'headers': list(FICHIER_VIREMENT_HEADERS),
        'rows': rows,
        'total': total,
        'nb_lignes': len(rows),
        'mode_paiement': run.mode_paiement,
    }


# ── FG135 — Notes de frais & remboursements employés ───────────────────────

# Compte de charge par défaut imputé à une note de frais validée (classe 6) :
# 6143 « Déplacements, missions et réceptions » du barème CGNC.
_COMPTE_NOTE_FRAIS_DEFAUT = '6143'
# Compte personnel-créditeur (classe 4) : la dette de la société envers
# l'employé qui a avancé le cash (4432 « Rémunérations dues au personnel »).
_COMPTE_PERSONNEL_CREDITEUR = '4432'


def creer_note_frais(company, *, employe, date_frais, montant, motif,
                     categorie=None, justificatif=None, compte_charge=None,
                     user=None):
    """Crée une note de frais (FG135) en BROUILLON, référence posée côté serveur.

    ``montant`` doit être strictement positif (validé par ``clean``). La
    ``reference`` (NDF-YYYYMM-NNNN) est attribuée via la fabrique gap-free
    race-safe (``apps.ventes.utils.references`` — jamais count()+1). ``company``
    posée côté serveur. Renvoie la note.
    """
    note = NoteFrais(
        company=company,
        employe=employe,
        date_frais=date_frais,
        montant=Decimal(montant or 0),
        motif=motif or '',
        categorie=categorie or NoteFrais.Categorie.AUTRE,
        compte_charge=compte_charge,
        created_by=user,
    )
    if justificatif is not None:
        note.justificatif = justificatif
    note.full_clean(exclude=['reference', 'employe', 'created_by'])
    from apps.ventes.utils.references import create_with_reference

    def _save(reference):
        note.reference = reference
        note.save()
        return note

    # Savepoint + retry : sous double-création concurrente même société/mois,
    # le perdant réessaie le numéro suivant au lieu de 500 (collision connue).
    return create_with_reference(NoteFrais, 'NDF', company, _save)


def soumettre_note_frais(note):
    """Soumet une note pour validation (brouillon → soumise) — FG135."""
    if note.statut not in (NoteFrais.Statut.BROUILLON,
                           NoteFrais.Statut.REJETEE):
        raise ValidationError(
            "Seule une note en brouillon (ou rejetée) peut être soumise.")
    note.statut = NoteFrais.Statut.SOUMISE
    note.motif_rejet = ''
    note.save(update_fields=['statut', 'motif_rejet'])
    return note


@transaction.atomic
def valider_note_frais(note, *, user=None, compte_charge=None):
    """Valide une note de frais et POSTE la charge au grand livre (FG135).

    Écriture ÉQUILIBRÉE dans le journal OD, datée du jour de la dépense :
    débit du compte de charge classe 6 (``compte_charge`` fourni, sinon celui
    de la note, sinon 6143 par défaut) / crédit du compte personnel-créditeur
    4432 (la dette envers l'employé). RESPECTE LE VERROU DE PÉRIODE (FG115).
    Idempotent : une note déjà validée renvoie sa note inchangée. Renvoie la
    note.
    """
    if note.statut == NoteFrais.Statut.VALIDEE:
        return note
    if note.statut != NoteFrais.Statut.SOUMISE:
        raise ValidationError(
            "Seule une note soumise peut être validée.")
    company = note.company
    montant = Decimal(note.montant or 0)
    if montant <= 0:
        raise ValidationError(
            "Impossible de valider une note de frais de montant nul.")
    if PeriodeComptable.date_verrouillee(company.id, note.date_frais):
        raise ValidationError(
            "Période comptable clôturée : impossible de valider la note de "
            f"frais du {note.date_frais}.")
    charge = compte_charge or note.compte_charge or _assurer_compte(
        company, _COMPTE_NOTE_FRAIS_DEFAUT)
    personnel = _assurer_compte(company, _COMPTE_PERSONNEL_CREDITEUR)
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    libelle = f"Note de frais {note.reference} — {note.motif}"
    lignes = [
        {'compte': charge, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle},
        {'compte': personnel, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle, 'tiers_type': 'employe',
         'tiers_id': note.employe_id},
    ]
    ecriture = creer_ecriture(
        company, journal, note.date_frais, libelle, lignes,
        reference=note.reference or f'NDF-{note.id}',
        source_type='note_frais', source_id=note.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    note.statut = NoteFrais.Statut.VALIDEE
    note.compte_charge = charge
    note.valide_par = user
    note.date_validation = timezone.now()
    note.ecriture_charge = ecriture
    note.motif_rejet = ''
    note.save(update_fields=[
        'statut', 'compte_charge', 'valide_par', 'date_validation',
        'ecriture_charge', 'motif_rejet'])
    return note


def rejeter_note_frais(note, *, motif_rejet='', user=None):
    """Rejette une note soumise (soumise → rejetée), motif figé — FG135."""
    if note.statut != NoteFrais.Statut.SOUMISE:
        raise ValidationError(
            "Seule une note soumise peut être rejetée.")
    note.statut = NoteFrais.Statut.REJETEE
    note.motif_rejet = motif_rejet or ''
    note.save(update_fields=['statut', 'motif_rejet'])
    return note


@transaction.atomic
def rembourser_note_frais(note, *, compte_tresorerie, date_remboursement=None,
                          mode_remboursement=None, user=None):
    """Rembourse une note validée et POSTE le paiement au grand livre (FG135).

    Écriture ÉQUILIBRÉE dans le journal de trésorerie (BNK pour une banque, CSH
    pour une caisse), datée du remboursement : débit du compte personnel-
    créditeur 4432 (extinction de la dette) / crédit du compte comptable du
    ``compte_tresorerie`` payeur. Le compte de trésorerie DOIT appartenir à la
    société de la note. RESPECTE LE VERROU DE PÉRIODE (FG115). Idempotent : une
    note déjà remboursée renvoie sa note inchangée. Renvoie la note.
    """
    if note.statut == NoteFrais.Statut.REMBOURSEE:
        return note
    if note.statut != NoteFrais.Statut.VALIDEE:
        raise ValidationError(
            "Seule une note validée peut être remboursée.")
    company = note.company
    if compte_tresorerie is None:
        raise ValidationError(
            "Un compte de trésorerie payeur est requis pour le remboursement.")
    if compte_tresorerie.company_id != company.id:
        raise ValidationError("Compte de trésorerie inconnu.")
    montant = Decimal(note.montant or 0)
    date_rbt = date_remboursement or note.date_frais
    if PeriodeComptable.date_verrouillee(company.id, date_rbt):
        raise ValidationError(
            "Période comptable clôturée : impossible de rembourser la note de "
            f"frais à la date du {date_rbt}.")
    personnel = _assurer_compte(company, _COMPTE_PERSONNEL_CREDITEUR)
    compte_treso = compte_tresorerie.compte_comptable
    if compte_tresorerie.type_compte == CompteTresorerie.Type.CAISSE:
        journal = _journal(company, Journal.Type.CAISSE)
    else:
        journal = _journal(company, Journal.Type.BANQUE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(
            company,
            Journal.Type.CAISSE
            if compte_tresorerie.type_compte == CompteTresorerie.Type.CAISSE
            else Journal.Type.BANQUE)
    libelle = (f"Remboursement note de frais {note.reference} — "
               f"{note.employe_id}")
    lignes = [
        {'compte': personnel, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle, 'tiers_type': 'employe',
         'tiers_id': note.employe_id},
        {'compte': compte_treso, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle},
    ]
    ecriture = creer_ecriture(
        company, journal, date_rbt, libelle, lignes,
        reference=note.reference or f'NDF-{note.id}',
        source_type='note_frais_remboursement', source_id=note.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    note.statut = NoteFrais.Statut.REMBOURSEE
    note.compte_tresorerie = compte_tresorerie
    note.mode_remboursement = (
        mode_remboursement or note.mode_remboursement
        or NoteFrais.ModeRemboursement.VIREMENT)
    note.date_remboursement = date_rbt
    note.rembourse_par = user
    note.ecriture_remboursement = ecriture
    note.save(update_fields=[
        'statut', 'compte_tresorerie', 'mode_remboursement',
        'date_remboursement', 'rembourse_par', 'ecriture_remboursement'])
    return note


# ── FG136 — Indemnités kilométriques & per-diem chantier ───────────────────

# Compte de charge par défaut imputé à une indemnité chantier validée : le même
# 6143 « Déplacements, missions et réceptions » du barème CGNC que les notes de
# frais de déplacement (la dette envers l'employé reste créditée en 4432).
_COMPTE_INDEM_DEFAUT = '6143'
_CENT = Decimal('0.01')


def _haversine_km(lat1, lng1, lat2, lng2):
    """Distance en kilomètres entre deux points GPS (haversine) — FG136.

    Réutilise la même formule de distance que le reste du code (terrain/SAV) :
    math pure, aucun service externe. Renvoie ``None`` si une coordonnée manque
    ou est illisible.
    """
    if None in (lat1, lng1, lat2, lng2):
        return None
    try:
        lat1, lng1, lat2, lng2 = (
            float(lat1), float(lng1), float(lat2), float(lng2))
    except (TypeError, ValueError):
        return None
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = (sin(dlat / 2) ** 2
         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2)
    return round(2 * r * asin(sqrt(a)), 3)


def bareme_indemnite_defaut(company):
    """Barème par défaut actif de la société, ou ``None`` — FG136."""
    return BaremeIndemnite.objects.filter(
        company=company, defaut=True, actif=True).first()


def calculer_indemnite(taux_km, per_diem, distance_km, nombre_jours, *,
                       aller_retour=True):
    """Calcule les montants d'une indemnité chantier (math pure) — FG136.

    ``distance_km`` est la distance simple (départ → chantier) ; elle est
    doublée si ``aller_retour``. Renvoie un dict figé
    ``{distance_km, montant_km, montant_per_diem, montant_total}`` arrondi au
    centime. Aucune écriture en base.
    """
    taux_km = Decimal(taux_km or 0)
    per_diem = Decimal(per_diem or 0)
    distance = Decimal(str(distance_km or 0))
    jours = int(nombre_jours or 0)
    parcourue = distance * (2 if aller_retour else 1)
    montant_km = (taux_km * parcourue).quantize(_CENT, rounding=ROUND_HALF_UP)
    montant_per_diem = (
        per_diem * Decimal(jours)).quantize(_CENT, rounding=ROUND_HALF_UP)
    return {
        'distance_km': parcourue.quantize(
            Decimal('0.001'), rounding=ROUND_HALF_UP),
        'montant_km': montant_km,
        'montant_per_diem': montant_per_diem,
        'montant_total': montant_km + montant_per_diem,
    }


def creer_indemnite_chantier(company, *, employe, date_deplacement,
                             bareme=None, site_lat=None, site_lng=None,
                             depart_lat=None, depart_lng=None,
                             aller_retour=True, nombre_jours=1,
                             libelle_chantier='', user=None):
    """Crée une indemnité chantier (FG136) en BROUILLON, montants auto-calculés.

    La distance ``départ → chantier`` est calculée par haversine depuis les GPS
    fournis (réutilise le calcul de distance existant) ; le montant est figé à
    ``taux_km × km(× 2 si aller-retour) + per_diem × nombre_jours``. Le barème
    par défaut de la société est utilisé si aucun n'est fourni. La ``reference``
    (IND-YYYYMM-NNNN) et la ``company`` sont posées côté serveur (jamais lues du
    corps). Renvoie l'indemnité.
    """
    bareme = bareme or bareme_indemnite_defaut(company)
    if bareme is None:
        raise ValidationError(
            "Aucun barème d'indemnité : définissez-en un (ou marquez-en un par "
            "défaut) avant de créer une indemnité chantier.")
    if bareme.company_id != company.id:
        raise ValidationError("Barème inconnu.")
    distance = _haversine_km(depart_lat, depart_lng, site_lat, site_lng) or 0
    montants = calculer_indemnite(
        bareme.taux_km, bareme.per_diem, distance, nombre_jours,
        aller_retour=aller_retour)
    indem = IndemniteChantier(
        company=company,
        employe=employe,
        bareme=bareme,
        date_deplacement=date_deplacement,
        libelle_chantier=libelle_chantier or '',
        depart_lat=depart_lat, depart_lng=depart_lng,
        site_lat=site_lat, site_lng=site_lng,
        aller_retour=bool(aller_retour),
        nombre_jours=int(nombre_jours or 0),
        distance_km=montants['distance_km'],
        montant_km=montants['montant_km'],
        montant_per_diem=montants['montant_per_diem'],
        montant_total=montants['montant_total'],
        created_by=user,
    )
    indem.full_clean(exclude=['reference', 'employe', 'bareme', 'created_by'])
    from apps.ventes.utils.references import create_with_reference

    def _save(reference):
        indem.reference = reference
        indem.save()
        return indem

    # Savepoint + retry race-safe (highest-used+1, jamais count()+1).
    return create_with_reference(IndemniteChantier, 'IND', company, _save)


def recalculer_indemnite_chantier(indem):
    """Recalcule les montants d'une indemnité encore modifiable — FG136.

    Réservé aux états non engagés (brouillon/rejetée) ; refuse de toucher une
    indemnité déjà validée/remboursée (montants figés et postés). Renvoie
    l'indemnité.
    """
    if indem.statut not in (IndemniteChantier.Statut.BROUILLON,
                            IndemniteChantier.Statut.REJETEE):
        raise ValidationError(
            "Seule une indemnité en brouillon (ou rejetée) peut être "
            "recalculée.")
    distance = _haversine_km(
        indem.depart_lat, indem.depart_lng,
        indem.site_lat, indem.site_lng) or 0
    montants = calculer_indemnite(
        indem.bareme.taux_km, indem.bareme.per_diem, distance,
        indem.nombre_jours, aller_retour=indem.aller_retour)
    indem.distance_km = montants['distance_km']
    indem.montant_km = montants['montant_km']
    indem.montant_per_diem = montants['montant_per_diem']
    indem.montant_total = montants['montant_total']
    indem.save(update_fields=[
        'distance_km', 'montant_km', 'montant_per_diem', 'montant_total'])
    return indem


def soumettre_indemnite_chantier(indem):
    """Soumet une indemnité pour validation (brouillon → soumise) — FG136."""
    if indem.statut not in (IndemniteChantier.Statut.BROUILLON,
                            IndemniteChantier.Statut.REJETEE):
        raise ValidationError(
            "Seule une indemnité en brouillon (ou rejetée) peut être soumise.")
    if indem.montant_total is None or indem.montant_total <= 0:
        raise ValidationError(
            "Impossible de soumettre une indemnité de montant nul.")
    indem.statut = IndemniteChantier.Statut.SOUMISE
    indem.motif_rejet = ''
    indem.save(update_fields=['statut', 'motif_rejet'])
    return indem


@transaction.atomic
def valider_indemnite_chantier(indem, *, user=None, compte_charge=None):
    """Valide une indemnité chantier et POSTE la charge au grand livre (FG136).

    Écriture ÉQUILIBRÉE dans le journal OD, datée du déplacement : débit du
    compte de charge classe 6 (fourni, sinon 6143) / crédit du compte
    personnel-créditeur 4432 (la dette envers l'employé). RESPECTE LE VERROU DE
    PÉRIODE (FG115). Idempotent. Renvoie l'indemnité.
    """
    if indem.statut == IndemniteChantier.Statut.VALIDEE:
        return indem
    if indem.statut != IndemniteChantier.Statut.SOUMISE:
        raise ValidationError(
            "Seule une indemnité soumise peut être validée.")
    company = indem.company
    montant = Decimal(indem.montant_total or 0)
    if montant <= 0:
        raise ValidationError(
            "Impossible de valider une indemnité de montant nul.")
    if PeriodeComptable.date_verrouillee(company.id, indem.date_deplacement):
        raise ValidationError(
            "Période comptable clôturée : impossible de valider l'indemnité "
            f"du {indem.date_deplacement}.")
    charge = compte_charge or indem.compte_charge or _assurer_compte(
        company, _COMPTE_INDEM_DEFAUT)
    personnel = _assurer_compte(company, _COMPTE_PERSONNEL_CREDITEUR)
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    libelle = (f"Indemnité chantier {indem.reference} — "
               f"{indem.libelle_chantier}").strip()
    lignes = [
        {'compte': charge, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle},
        {'compte': personnel, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle, 'tiers_type': 'employe',
         'tiers_id': indem.employe_id},
    ]
    ecriture = creer_ecriture(
        company, journal, indem.date_deplacement, libelle, lignes,
        reference=indem.reference or f'IND-{indem.id}',
        source_type='indemnite_chantier', source_id=indem.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    indem.statut = IndemniteChantier.Statut.VALIDEE
    indem.compte_charge = charge
    indem.valide_par = user
    indem.date_validation = timezone.now()
    indem.ecriture_charge = ecriture
    indem.motif_rejet = ''
    indem.save(update_fields=[
        'statut', 'compte_charge', 'valide_par', 'date_validation',
        'ecriture_charge', 'motif_rejet'])
    return indem


def rejeter_indemnite_chantier(indem, *, motif_rejet='', user=None):
    """Rejette une indemnité soumise (soumise → rejetée), motif figé — FG136."""
    if indem.statut != IndemniteChantier.Statut.SOUMISE:
        raise ValidationError(
            "Seule une indemnité soumise peut être rejetée.")
    indem.statut = IndemniteChantier.Statut.REJETEE
    indem.motif_rejet = motif_rejet or ''
    indem.save(update_fields=['statut', 'motif_rejet'])
    return indem


@transaction.atomic
def rembourser_indemnite_chantier(indem, *, compte_tresorerie,
                                  date_remboursement=None, user=None):
    """Rembourse une indemnité validée et POSTE le paiement au GL (FG136).

    Écriture ÉQUILIBRÉE dans le journal de trésorerie (BNK banque / CSH caisse),
    datée du remboursement : débit 4432 (extinction de la dette) / crédit du
    compte comptable du ``compte_tresorerie`` payeur. Le compte DOIT appartenir
    à la société. RESPECTE LE VERROU DE PÉRIODE (FG115). Idempotent. Renvoie
    l'indemnité.
    """
    if indem.statut == IndemniteChantier.Statut.REMBOURSEE:
        return indem
    if indem.statut != IndemniteChantier.Statut.VALIDEE:
        raise ValidationError(
            "Seule une indemnité validée peut être remboursée.")
    company = indem.company
    if compte_tresorerie is None:
        raise ValidationError(
            "Un compte de trésorerie payeur est requis pour le remboursement.")
    if compte_tresorerie.company_id != company.id:
        raise ValidationError("Compte de trésorerie inconnu.")
    montant = Decimal(indem.montant_total or 0)
    date_rbt = date_remboursement or indem.date_deplacement
    if PeriodeComptable.date_verrouillee(company.id, date_rbt):
        raise ValidationError(
            "Période comptable clôturée : impossible de rembourser "
            f"l'indemnité à la date du {date_rbt}.")
    personnel = _assurer_compte(company, _COMPTE_PERSONNEL_CREDITEUR)
    compte_treso = compte_tresorerie.compte_comptable
    if compte_tresorerie.type_compte == CompteTresorerie.Type.CAISSE:
        journal = _journal(company, Journal.Type.CAISSE)
    else:
        journal = _journal(company, Journal.Type.BANQUE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(
            company,
            Journal.Type.CAISSE
            if compte_tresorerie.type_compte == CompteTresorerie.Type.CAISSE
            else Journal.Type.BANQUE)
    libelle = (f"Remboursement indemnité chantier {indem.reference} — "
               f"{indem.employe_id}")
    lignes = [
        {'compte': personnel, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle, 'tiers_type': 'employe',
         'tiers_id': indem.employe_id},
        {'compte': compte_treso, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle},
    ]
    ecriture = creer_ecriture(
        company, journal, date_rbt, libelle, lignes,
        reference=indem.reference or f'IND-{indem.id}',
        source_type='indemnite_chantier_remb', source_id=indem.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    indem.statut = IndemniteChantier.Statut.REMBOURSEE
    indem.compte_tresorerie = compte_tresorerie
    indem.date_remboursement = date_rbt
    indem.rembourse_par = user
    indem.ecriture_remboursement = ecriture
    indem.save(update_fields=[
        'statut', 'compte_tresorerie', 'date_remboursement',
        'rembourse_par', 'ecriture_remboursement'])
    return indem


# ── FG137 — Préparation de la déclaration de TVA ────────────────────────────

def preparer_declaration_tva(company, *, date_debut, date_fin,
                             regime='mensuel', methode='debit',
                             credit_anterieur=Decimal('0'), libelle='',
                             validees_seulement=False, user=None):
    """Prépare et FIGE une déclaration de TVA sur une période (FG137).

    Agrège la TVA collectée (4455…, crédit) et la TVA déductible (3455…, débit)
    du grand livre sur ``[date_debut ; date_fin]`` (cf.
    ``selectors.preparer_declaration_tva``), en déduit le montant à déclarer et
    l'éventuel crédit reportable, puis persiste un snapshot ``DeclarationTVA`` en
    statut « préparée ». La ``reference`` (TVA-YYYYMM-NNNN) et la ``company`` sont
    posées côté serveur (jamais lues du corps). Renvoie la déclaration.
    """
    from . import selectors  # import local : évite tout cycle au chargement.
    from apps.ventes.utils.references import create_with_reference

    calc = selectors.preparer_declaration_tva(
        company, date_debut=date_debut, date_fin=date_fin, regime=regime,
        methode=methode, credit_anterieur=credit_anterieur or Decimal('0'),
        validees_seulement=validees_seulement)
    declaration = DeclarationTVA(
        company=company,
        regime=regime,
        methode=methode,
        date_debut=date_debut,
        date_fin=date_fin,
        tva_collectee=calc['tva_collectee'],
        tva_deductible=calc['tva_deductible'],
        credit_anterieur=calc['credit_anterieur'],
        tva_a_declarer=calc['tva_a_declarer'],
        credit_reportable=calc['credit_reportable'],
        statut=DeclarationTVA.Statut.PREPAREE,
        libelle=libelle or '',
        created_by=user,
    )
    declaration.full_clean(exclude=['reference', 'created_by'])

    def _save(reference):
        declaration.reference = reference
        declaration.save()
        return declaration

    # Savepoint + retry race-safe (highest-used+1, jamais count()+1).
    return create_with_reference(DeclarationTVA, 'TVA', company, _save)


# ── FG139 — Retenue à la source (RAS) sur honoraires/prestations ───────────

def enregistrer_retenue_source(company, *, date_piece, base, taux=None,
                               type_prestation=None, tiers_type='', tiers_id=None,
                               tiers_nom='', identifiant_fiscal='', piece='',
                               libelle='', user=None):
    """Enregistre une RAS sur une pièce d'honoraires/prestation (FG139).

    Calcule le ``montant`` retenu = base × taux % (arrondi 2 décimales) et FIGE le
    snapshot dans une ``RetenueSource`` en statut « à verser ». Le ``taux`` par
    défaut est ``RetenueSource.TAUX_DEFAUT`` (10 %). La ``reference``
    (RAS-YYYYMM-NNNN) et la ``company`` sont posées côté serveur (jamais lues du
    corps). Le tiers prestataire est référencé par auxiliaire string-FK
    (``tiers_type`` / ``tiers_id``) — jamais d'import cross-app de modèle. Renvoie
    la retenue.
    """
    from apps.ventes.utils.references import create_with_reference

    ras = RetenueSource(
        company=company,
        date_piece=date_piece,
        base=Decimal(base or 0),
        taux=(Decimal(taux) if taux is not None
              else RetenueSource.TAUX_DEFAUT),
        type_prestation=(type_prestation
                         or RetenueSource.TypePrestation.HONORAIRES),
        tiers_type=tiers_type or '',
        tiers_id=tiers_id,
        tiers_nom=tiers_nom or '',
        identifiant_fiscal=identifiant_fiscal or '',
        piece=piece or '',
        statut=RetenueSource.Statut.A_VERSER,
        libelle=libelle or '',
        created_by=user,
    )
    ras.recalculer()
    ras.full_clean(exclude=['reference', 'created_by'])

    def _save(reference):
        ras.reference = reference
        ras.save()
        return ras

    # Savepoint + retry race-safe (highest-used+1, jamais count()+1).
    return create_with_reference(RetenueSource, 'RAS', company, _save)


def marquer_ras_versee(retenue):
    """Marque une retenue à la source comme versée au Trésor (FG139)."""
    retenue.statut = RetenueSource.Statut.VERSEE
    retenue.save(update_fields=['statut'])
    return retenue


# ── FG144 — Droit de timbre sur encaissements en espèces ───────────────────
# Mode de règlement « espèces » (miroir de apps.ventes.Paiement.Mode.ESPECES) —
# repris par valeur (string-ref) et JAMAIS par import du modèle ventes.
MODE_ESPECES = 'especes'


def est_reglement_especes(mode_reglement):
    """Vrai si le mode de règlement est « espèces » (cash) — sinon exonéré.

    Le droit de timbre de quittance ne frappe QUE les encaissements en espèces ;
    virement / chèque / carte / prélèvement / autre en sont exonérés."""
    return (mode_reglement or '').strip().lower() == MODE_ESPECES


def enregistrer_timbre_fiscal(company, *, date_encaissement, base,
                              mode_reglement=MODE_ESPECES, taux=None,
                              minimum=None, paiement_id=None, facture_ref='',
                              tiers_type='', tiers_id=None, tiers_nom='',
                              libelle='', user=None):
    """Enregistre le droit de timbre sur un encaissement ESPÈCES (FG144).

    Le droit de timbre marocain de quittance frappe la somme reçue EN ESPÈCES :
    ``montant`` = max(base × taux %, minimum), FIGÉ dans un snapshot
    ``TimbreFiscal`` en statut « à verser ». Le ``taux`` par défaut est
    ``TimbreFiscal.TAUX_DEFAUT`` (0,25 %) et le ``minimum`` forfaitaire
    ``TimbreFiscal.MINIMUM_DEFAUT`` ; tous deux sont configurables par appel. Un
    règlement NON espèces est EXONÉRÉ : la fonction renvoie ``None`` sans rien
    créer. La ``reference`` (TIMBRE-YYYYMM-NNNN) et la ``company`` sont posées côté
    serveur (jamais lues du corps). Le paiement d'origine est référencé par
    string-id (``paiement_id`` / ``facture_ref``) — jamais d'import cross-app de
    modèle ventes. Renvoie le timbre, ou ``None`` si exonéré.
    """
    from apps.ventes.utils.references import create_with_reference

    if not est_reglement_especes(mode_reglement):
        # Règlement non espèces → exonéré : aucun droit de timbre.
        return None

    timbre = TimbreFiscal(
        company=company,
        date_encaissement=date_encaissement,
        base=Decimal(base or 0),
        taux=(Decimal(taux) if taux is not None
              else TimbreFiscal.TAUX_DEFAUT),
        minimum=(Decimal(minimum) if minimum is not None
                 else TimbreFiscal.MINIMUM_DEFAUT),
        mode_reglement=MODE_ESPECES,
        paiement_id=paiement_id,
        facture_ref=facture_ref or '',
        tiers_type=tiers_type or '',
        tiers_id=tiers_id,
        tiers_nom=tiers_nom or '',
        statut=TimbreFiscal.Statut.A_VERSER,
        libelle=libelle or '',
        created_by=user,
    )
    timbre.recalculer()
    timbre.full_clean(exclude=['reference', 'created_by'])

    def _save(reference):
        timbre.reference = reference
        timbre.save()
        return timbre

    # Savepoint + retry race-safe (highest-used+1, jamais count()+1).
    return create_with_reference(TimbreFiscal, 'TIMBRE', company, _save)


def marquer_timbre_verse(timbre):
    """Marque un droit de timbre comme versé au Trésor (FG144)."""
    timbre.statut = TimbreFiscal.Statut.VERSEE
    timbre.save(update_fields=['statut'])
    return timbre


# ── FG145 — Retenue de garantie & cautions bancaires sur marchés ───────────
def enregistrer_retenue_garantie(company, *, date_constitution, base,
                                 taux=None, marche_ref='', facture_id=None,
                                 facture_ref='', tiers_type='', tiers_id=None,
                                 tiers_nom='', date_levee_prevue=None,
                                 libelle='', user=None):
    """Enregistre une retenue de garantie (RG) sur un marché/décompte (FG145).

    Calcule le ``montant`` retenu = base × taux % (arrondi 2 décimales) et FIGE le
    snapshot dans une ``RetenueGarantie`` en statut « retenue ». Le ``taux`` par
    défaut est ``RetenueGarantie.TAUX_DEFAUT`` (10 %). La ``reference``
    (RG-YYYYMM-NNNN) et la ``company`` sont posées côté serveur (jamais lues du
    corps). Le marché/la facture sont référencés par string-ref
    (``marche_ref`` / ``facture_id`` / ``facture_ref``) — jamais d'import
    cross-app de modèle. Renvoie la retenue.
    """
    from apps.ventes.utils.references import create_with_reference

    rg = RetenueGarantie(
        company=company,
        date_constitution=date_constitution,
        base=Decimal(base or 0),
        taux=(Decimal(taux) if taux is not None
              else RetenueGarantie.TAUX_DEFAUT),
        marche_ref=marche_ref or '',
        facture_id=facture_id,
        facture_ref=facture_ref or '',
        tiers_type=tiers_type or '',
        tiers_id=tiers_id,
        tiers_nom=tiers_nom or '',
        date_levee_prevue=date_levee_prevue,
        statut=RetenueGarantie.Statut.RETENUE,
        libelle=libelle or '',
        created_by=user,
    )
    rg.recalculer()
    rg.full_clean(exclude=['reference', 'created_by'])

    def _save(reference):
        rg.reference = reference
        rg.save()
        return rg

    # Savepoint + retry race-safe (highest-used+1, jamais count()+1).
    return create_with_reference(RetenueGarantie, 'RG', company, _save)


def liberer_retenue_garantie(retenue, *, date_liberation=None):
    """Libère (restitue) une retenue de garantie à sa levée (FG145).

    Pose le statut « libérée » et la ``date_liberation`` (défaut = aujourd'hui).
    """
    retenue.statut = RetenueGarantie.Statut.LIBEREE
    retenue.date_liberation = date_liberation or timezone.now().date()
    retenue.save(update_fields=['statut', 'date_liberation'])
    return retenue


def enregistrer_caution_bancaire(company, *, type_caution=None, date_emission,
                                 montant, banque='', marche_ref='',
                                 tiers_nom='', date_echeance=None, libelle='',
                                 user=None):
    """Enregistre une caution bancaire émise sur un marché (FG145).

    Fige l'engagement hors-bilan dans une ``CautionBancaire`` en statut
    « active ». Le ``type_caution`` par défaut est
    ``CautionBancaire.TypeCaution.DEFINITIVE``. La ``reference``
    (CAUTION-YYYYMM-NNNN) et la ``company`` sont posées côté serveur (jamais lues
    du corps). Le marché est référencé par string-ref (``marche_ref``) — jamais
    d'import cross-app de modèle. Renvoie la caution.
    """
    from apps.ventes.utils.references import create_with_reference

    caution = CautionBancaire(
        company=company,
        type_caution=(type_caution
                      or CautionBancaire.TypeCaution.DEFINITIVE),
        date_emission=date_emission,
        montant=Decimal(montant or 0),
        banque=banque or '',
        marche_ref=marche_ref or '',
        tiers_nom=tiers_nom or '',
        date_echeance=date_echeance,
        statut=CautionBancaire.Statut.ACTIVE,
        libelle=libelle or '',
        created_by=user,
    )
    caution.full_clean(exclude=['reference', 'created_by'])

    def _save(reference):
        caution.reference = reference
        caution.save()
        return caution

    # Savepoint + retry race-safe (highest-used+1, jamais count()+1).
    return create_with_reference(CautionBancaire, 'CAUTION', company, _save)


def mainlevee_caution_bancaire(caution, *, date_mainlevee=None,
                               restituee=False):
    """Lève (mainlevée) ou restitue une caution bancaire (FG145).

    Pose la ``date_mainlevee`` (défaut = aujourd'hui) et le statut : « restituée »
    si ``restituee`` est vrai (acompte rendu), sinon « mainlevée » (banque déliée).
    """
    caution.date_mainlevee = date_mainlevee or timezone.now().date()
    caution.statut = (CautionBancaire.Statut.RESTITUEE if restituee
                      else CautionBancaire.Statut.LEVEE)
    caution.save(update_fields=['statut', 'date_mainlevee'])
    return caution


# ── FG146 — Reconnaissance du revenu par avancement (% completion) ──────────

def creer_contrat_avancement(company, *, revenu_total, cout_total_estime=0,
                             methode=None, libelle='', chantier_ref='',
                             marche_ref='', client_id=None, client_nom='',
                             date_debut=None, date_fin_prevue=None, user=None):
    """Crée un contrat reconnu au pourcentage d'avancement (FG146).

    Fige le revenu total contractuel et le coût total estimé. La ``reference``
    (CONTRAT-YYYYMM-NNNN) et la ``company`` sont posées côté serveur. Le
    chantier/marché/client est référencé par string-ref — jamais d'import
    cross-app de modèle. Renvoie le contrat.
    """
    from apps.ventes.utils.references import create_with_reference

    contrat = ContratAvancement(
        company=company,
        revenu_total=Decimal(revenu_total or 0),
        cout_total_estime=Decimal(cout_total_estime or 0),
        methode=methode or ContratAvancement.Methode.COUTS,
        libelle=libelle or '',
        chantier_ref=chantier_ref or '',
        marche_ref=marche_ref or '',
        client_id=client_id,
        client_nom=client_nom or '',
        date_debut=date_debut,
        date_fin_prevue=date_fin_prevue,
        statut=ContratAvancement.Statut.EN_COURS,
        created_by=user,
    )
    contrat.full_clean(exclude=['reference', 'created_by'])

    def _save(reference):
        contrat.reference = reference
        contrat.save()
        return contrat

    return create_with_reference(
        ContratAvancement, 'CONTRAT', company, _save)


def _pourcentage_avancement(contrat, *, pourcentage=None,
                            cout_engage_cumule=None):
    """Détermine le % d'avancement cumulé selon la méthode du contrat.

    Méthode « couts » (cost-to-cost) = coût engagé cumulé / coût total estimé,
    plafonné à 100 %. Méthode « saisie » = pourcentage saisi tel quel. Renvoie
    un ``Decimal`` 0–100 arrondi à 2 décimales.
    """
    if contrat.methode == ContratAvancement.Methode.COUTS:
        total = contrat.cout_total_estime or Decimal('0')
        engage = Decimal(cout_engage_cumule or 0)
        if total <= 0:
            pct = Decimal('0')
        else:
            pct = (engage / total * Decimal('100'))
    else:
        pct = Decimal(pourcentage or 0)
    if pct < 0:
        pct = Decimal('0')
    if pct > 100:
        pct = Decimal('100')
    return pct.quantize(Decimal('0.01'))


@transaction.atomic
def constater_avancement(contrat, *, date_arrete, pourcentage=None,
                         cout_engage_cumule=None, libelle='', poster=True,
                         user=None):
    """Constate l'avancement à une date et reconnaît le CA cumulé (FG146).

    Calcule le revenu cumulé à reconnaître = ``revenu_total`` × % d'avancement,
    fige le DELTA (``revenu_periode``) par rapport au cumul déjà reconnu, et —
    si ``poster`` — passe l'écriture OD de reconnaissance (3427 « clients -
    factures à établir » au débit / 71xx « ventes » au crédit pour le delta
    positif, et l'inverse si négatif). Le ``%`` et le revenu sont DÉRIVÉS côté
    serveur (jamais imposés par le corps). Renvoie le constat.
    """
    company = contrat.company
    pct = _pourcentage_avancement(
        contrat, pourcentage=pourcentage,
        cout_engage_cumule=cout_engage_cumule)
    revenu_cumule = (
        (contrat.revenu_total or Decimal('0')) * pct / Decimal('100')
    ).quantize(Decimal('0.01'))
    deja = contrat.revenu_reconnu
    revenu_periode = (revenu_cumule - deja).quantize(Decimal('0.01'))
    constat = AvancementRevenu(
        company=company,
        contrat=contrat,
        date_arrete=date_arrete,
        pourcentage=pct,
        cout_engage_cumule=Decimal(cout_engage_cumule or 0),
        revenu_cumule=revenu_cumule,
        revenu_periode=revenu_periode,
        libelle=libelle or '',
        created_by=user,
    )
    constat.full_clean(exclude=['created_by', 'libelle'])
    constat.save()
    if poster and revenu_periode != 0:
        comptes = _comptes_requis(company)
        compte_fae = get_compte(company, '3427')
        compte_ventes = comptes['ventes']
        montant = abs(revenu_periode)
        if revenu_periode > 0:
            lignes = [
                {'compte': compte_fae, 'debit': montant,
                 'credit': Decimal('0'),
                 'libelle': f'Avancement {pct}%'},
                {'compte': compte_ventes, 'debit': Decimal('0'),
                 'credit': montant,
                 'libelle': f'Avancement {pct}%'},
            ]
        else:
            lignes = [
                {'compte': compte_ventes, 'debit': montant,
                 'credit': Decimal('0'),
                 'libelle': f'Avancement {pct}%'},
                {'compte': compte_fae, 'debit': Decimal('0'),
                 'credit': montant,
                 'libelle': f'Avancement {pct}%'},
            ]
        ecriture = creer_ecriture_od(
            company, date_arrete,
            (f'Reconnaissance revenu avancement '
             f'{contrat.reference} — {pct}%'),
            lignes, created_by=user)
        constat.ecriture_id = ecriture.id
        constat.save(update_fields=['ecriture_id'])
    return constat


# ── FG147 — Produits constatés d'avance & travaux en cours (WIP) ────────────

# (compte_débit, compte_crédit) de chaque nature de régularisation.
_TEC_COMPTES = {
    TravauxEnCours.Nature.PCA: ('7121', '4491'),
    TravauxEnCours.Nature.WIP: ('3134', '7132'),
}


@transaction.atomic
def constater_regularisation(company, *, nature, montant, date_arrete,
                             libelle='', chantier_ref='', contrat_id=None,
                             poster=True, user=None):
    """Constate une régularisation de cut-off (PCA ou WIP) — FG147.

    Fige le ``montant`` régularisé et — si ``poster`` — passe l'écriture OD de
    constat (PCA : 7121 débit / 4491 crédit ; WIP : 3134 débit / 7132 crédit).
    La ``reference`` (REG-YYYYMM-NNNN) et la ``company`` sont posées côté
    serveur. Renvoie la régularisation.
    """
    from apps.ventes.utils.references import create_with_reference

    nature = nature or TravauxEnCours.Nature.WIP
    reg = TravauxEnCours(
        company=company,
        nature=nature,
        montant=Decimal(montant or 0),
        date_arrete=date_arrete,
        libelle=libelle or '',
        chantier_ref=chantier_ref or '',
        contrat_id=contrat_id,
        statut=TravauxEnCours.Statut.CONSTATE,
        created_by=user,
    )
    reg.full_clean(exclude=['reference', 'created_by', 'libelle'])

    def _save(reference):
        reg.reference = reference
        reg.save()
        return reg

    reg = create_with_reference(TravauxEnCours, 'REG', company, _save)
    if poster and reg.montant > 0:
        _comptes_requis(company)
        num_debit, num_credit = _TEC_COMPTES[nature]
        compte_debit = get_compte(company, num_debit)
        compte_credit = get_compte(company, num_credit)
        ecriture = creer_ecriture_od(
            company, date_arrete,
            f'Régularisation {reg.get_nature_display()} {reg.reference}',
            [
                {'compte': compte_debit, 'debit': reg.montant,
                 'credit': Decimal('0'), 'libelle': reg.libelle},
                {'compte': compte_credit, 'debit': Decimal('0'),
                 'credit': reg.montant, 'libelle': reg.libelle},
            ],
            created_by=user)
        reg.ecriture_id = ecriture.id
        reg.save(update_fields=['ecriture_id'])
    return reg


@transaction.atomic
def reprendre_regularisation(reg, *, date_reprise=None, poster=True,
                             user=None):
    """Reprend (extourne) une régularisation à l'ouverture suivante (FG147).

    Passe l'écriture OD inverse (crédit ↔ débit) puis pose le statut « repris ».
    Idempotent : ne reprend pas deux fois. Renvoie la régularisation.
    """
    if reg.statut == TravauxEnCours.Statut.REPRIS:
        return reg
    date_reprise = date_reprise or timezone.now().date()
    if poster and reg.montant > 0:
        _comptes_requis(reg.company)
        num_debit, num_credit = _TEC_COMPTES[reg.nature]
        # Extourne : on inverse débit/crédit.
        compte_debit = get_compte(reg.company, num_debit)
        compte_credit = get_compte(reg.company, num_credit)
        ecriture = creer_ecriture_od(
            reg.company, date_reprise,
            f'Reprise régularisation {reg.reference}',
            [
                {'compte': compte_credit, 'debit': reg.montant,
                 'credit': Decimal('0'), 'libelle': reg.libelle},
                {'compte': compte_debit, 'debit': Decimal('0'),
                 'credit': reg.montant, 'libelle': reg.libelle},
            ],
            created_by=user)
        reg.ecriture_reprise_id = ecriture.id
    reg.statut = TravauxEnCours.Statut.REPRIS
    reg.date_reprise = date_reprise
    reg.save(update_fields=['statut', 'date_reprise', 'ecriture_reprise_id'])
    return reg


# ── FG148 — Campagnes de versement des commissions (payout run) ─────────────

@transaction.atomic
def creer_commission_run(company, *, date_run, periode='', libelle='',
                         lignes=None, user=None):
    """Crée une campagne de versement de commissions (FG148).

    ``lignes`` est une liste de dicts ``{'commercial_id'?, 'commercial_nom',
    'base'?, 'taux'?, 'montant', 'libelle'?}``. La ``reference``
    (COMM-YYYYMM-NNNN) et la ``company`` sont posées côté serveur. Le total est
    recalculé. Le commercial est référencé par string-ref — jamais d'import
    cross-app. Renvoie le run.
    """
    from apps.ventes.utils.references import create_with_reference

    run = CommissionPayoutRun(
        company=company,
        date_run=date_run,
        periode=periode or '',
        libelle=libelle or '',
        statut=CommissionPayoutRun.Statut.BROUILLON,
        created_by=user,
    )

    def _save(reference):
        run.reference = reference
        run.save()
        return run

    run = create_with_reference(
        CommissionPayoutRun, 'COMM', company, _save)
    for ligne in (lignes or []):
        CommissionPayoutLine.objects.create(
            company=company,
            run=run,
            commercial_id=ligne.get('commercial_id'),
            commercial_nom=ligne.get('commercial_nom', '') or '',
            base=Decimal(ligne.get('base') or 0),
            taux=Decimal(ligne.get('taux') or 0),
            montant=Decimal(ligne.get('montant') or 0),
            libelle=ligne.get('libelle', '') or '',
        )
    run.recalculer_total()
    run.save(update_fields=['total'])
    return run


@transaction.atomic
def valider_commission_run(run):
    """Valide un run de commissions : gèle les montants (FG148).

    Refuse si le run n'est pas en brouillon. Renvoie le run.
    """
    if run.statut != CommissionPayoutRun.Statut.BROUILLON:
        raise ValidationError(
            "Seul un run en brouillon peut être validé.")
    run.recalculer_total()
    run.statut = CommissionPayoutRun.Statut.VALIDE
    run.date_validation = timezone.now()
    run.save(update_fields=['statut', 'date_validation', 'total'])
    return run


@transaction.atomic
def poster_commission_run(run, *, user=None):
    """Poste un run de commissions au grand livre (FG148).

    Passe l'écriture OD (débit 6171 « rémunérations du personnel » / crédit
    4432 « rémunérations dues au personnel ») pour le total du run. Refuse si le
    run n'est pas validé ; idempotent (ne reposte pas). Renvoie le run.
    """
    if run.statut == CommissionPayoutRun.Statut.POSTE:
        return run
    if run.statut != CommissionPayoutRun.Statut.VALIDE:
        raise ValidationError(
            "Seul un run validé peut être posté au grand livre.")
    company = run.company
    run.recalculer_total()
    if run.total > 0:
        _comptes_requis(company)
        compte_charge = get_compte(company, '6171')
        compte_dette = get_compte(company, '4432')
        ecriture = creer_ecriture_od(
            company, run.date_run,
            f'Commissions commerciales {run.reference} — {run.periode}',
            [
                {'compte': compte_charge, 'debit': run.total,
                 'credit': Decimal('0'), 'libelle': run.libelle},
                {'compte': compte_dette, 'debit': Decimal('0'),
                 'credit': run.total, 'libelle': run.libelle},
            ],
            created_by=user)
        run.ecriture_id = ecriture.id
    run.statut = CommissionPayoutRun.Statut.POSTE
    run.date_poste = timezone.now()
    run.save(update_fields=['statut', 'date_poste', 'ecriture_id', 'total'])
    return run


# ── FG149 — Budgets annuels & suivi budget-vs-réalisé ──────────────────────

@transaction.atomic
def creer_budget(company, *, annee, libelle='', lignes=None, user=None):
    """Crée un budget annuel et ses lignes (FG149).

    ``lignes`` est une liste de dicts ``{'compte', 'centre_cout'?, 'libelle'?,
    'm01'…'m12'?}``. ``company`` posée côté serveur. Renvoie le budget.
    """
    budget = Budget.objects.create(
        company=company, annee=int(annee), libelle=libelle or '',
        created_by=user)
    for ligne in (lignes or []):
        champs = {m: Decimal(ligne.get(m) or 0) for m in BudgetLigne.MOIS}
        BudgetLigne.objects.create(
            company=company,
            budget=budget,
            compte=ligne['compte'],
            centre_cout=ligne.get('centre_cout'),
            libelle=ligne.get('libelle', '') or '',
            **champs,
        )
    return budget


# ── FG150 — Comptabilité analytique / centres de coût ──────────────────────

def creer_centre_cout(company, *, code, libelle, axe=None):
    """Crée (ou récupère) un centre de coût (idempotent par code) — FG150."""
    centre, _ = CentreCout.objects.get_or_create(
        company=company, code=code,
        defaults={
            'libelle': libelle,
            'axe': axe or CentreCout.Axe.CHANTIER,
        },
    )
    return centre


# ── FG152 — Provisions pour créances douteuses ─────────────────────────────

@transaction.atomic
def enregistrer_provision_creance(company, *, date_dotation, base, taux=None,
                                  tiers_type='', tiers_id=None, tiers_nom='',
                                  anciennete_jours=0, libelle='', poster=True,
                                  user=None):
    """Enregistre une dotation de provision pour créance douteuse (FG152).

    Calcule la ``dotation`` = base × taux % (arrondi) et — si ``poster`` —
    passe l'écriture OD (débit 6196 « dotations aux provisions » / crédit 3942
    « provisions pour dépréciation des clients »). La ``reference``
    (PROV-YYYYMM-NNNN) et la ``company`` sont posées côté serveur. Le client est
    référencé par string-ref. Renvoie la provision.
    """
    from apps.ventes.utils.references import create_with_reference

    prov = ProvisionCreance(
        company=company,
        date_dotation=date_dotation,
        base=Decimal(base or 0),
        taux=(Decimal(taux) if taux is not None else Decimal('0')),
        tiers_type=tiers_type or '',
        tiers_id=tiers_id,
        tiers_nom=tiers_nom or '',
        anciennete_jours=int(anciennete_jours or 0),
        statut=ProvisionCreance.Statut.DOTATION,
        libelle=libelle or '',
        created_by=user,
    )
    prov.recalculer()
    prov.full_clean(exclude=['reference', 'created_by', 'libelle'])

    def _save(reference):
        prov.reference = reference
        prov.save()
        return prov

    prov = create_with_reference(ProvisionCreance, 'PROV', company, _save)
    if poster and prov.dotation > 0:
        _comptes_requis(company)
        compte_charge = get_compte(company, '6196')
        compte_prov = get_compte(company, '3942')
        ecriture = creer_ecriture_od(
            company, date_dotation,
            f'Dotation provision créance douteuse {prov.reference}',
            [
                {'compte': compte_charge, 'debit': prov.dotation,
                 'credit': Decimal('0'), 'libelle': prov.tiers_nom},
                {'compte': compte_prov, 'debit': Decimal('0'),
                 'credit': prov.dotation, 'libelle': prov.tiers_nom,
                 'tiers_type': prov.tiers_type, 'tiers_id': prov.tiers_id},
            ],
            created_by=user)
        prov.ecriture_id = ecriture.id
        prov.save(update_fields=['ecriture_id'])
    return prov


@transaction.atomic
def reprendre_provision_creance(prov, *, date_reprise=None, poster=True,
                                user=None):
    """Reprend une provision (créance recouvrée/soldée) — FG152.

    Passe l'écriture OD inverse (débit 3942 / crédit 7196 « reprises sur
    provisions ») puis pose le statut « reprise ». Idempotent. Renvoie la
    provision.
    """
    if prov.statut == ProvisionCreance.Statut.REPRISE:
        return prov
    date_reprise = date_reprise or timezone.now().date()
    if poster and prov.dotation > 0:
        _comptes_requis(prov.company)
        compte_prov = get_compte(prov.company, '3942')
        compte_reprise = get_compte(prov.company, '7196')
        ecriture = creer_ecriture_od(
            prov.company, date_reprise,
            f'Reprise provision créance {prov.reference}',
            [
                {'compte': compte_prov, 'debit': prov.dotation,
                 'credit': Decimal('0'), 'libelle': prov.tiers_nom},
                {'compte': compte_reprise, 'debit': Decimal('0'),
                 'credit': prov.dotation, 'libelle': prov.tiers_nom},
            ],
            created_by=user)
        prov.ecriture_reprise_id = ecriture.id
    prov.statut = ProvisionCreance.Statut.REPRISE
    prov.date_reprise = date_reprise
    prov.save(update_fields=[
        'statut', 'date_reprise', 'ecriture_reprise_id'])
    return prov


# ── FG153 — Inter-sociétés / consolidation multi-entités ───────────────────

def ajouter_entite_consolidation(company, *, entite, pourcentage_interet=None,
                                 methode=None, libelle=''):
    """Rattache une entité au périmètre de consolidation (FG153, idempotent).

    ``company`` = société tête de groupe (posée côté serveur) ; ``entite`` =
    société membre (FK ``authentication.Company``). Renvoie l'entité de
    consolidation.
    """
    obj, _ = EntiteConsolidation.objects.get_or_create(
        company=company, entite=entite,
        defaults={
            'pourcentage_interet': (
                Decimal(pourcentage_interet)
                if pourcentage_interet is not None else Decimal('100.00')),
            'methode': (
                methode or EntiteConsolidation.Methode.INTEGRATION_GLOBALE),
            'libelle': libelle or '',
        },
    )
    return obj


# ── FG201 — Envoi groupé email/SMS (Brevo, GATED, NO-OP par défaut) ─────────

def brevo_actif():
    """Toggle maître de l'intégration Brevo. OFF par défaut → envoi NO-OP.

    Le founder active l'envoi réel en posant ``BREVO_ENABLED = True`` et une clé
    ``BREVO_API_KEY`` (settings/env). Tant que c'est faux ou sans clé, aucun
    appel payant n'est émis : ``envoyer_campagne`` se contente d'horodater la
    campagne et de compter les destinataires (simulation), comme le NoOp des
    autres intégrations gated.
    """
    return bool(getattr(settings, 'BREVO_ENABLED', False)
                and getattr(settings, 'BREVO_API_KEY', ''))


def envoyer_campagne(campagne, *, destinataires=None):
    """Déclenche l'envoi groupé d'une campagne (FG201), idempotent.

    ``destinataires`` = liste d'adresses/numéros (optionnelle, sinon 0). Si
    l'intégration Brevo est inactive (défaut), c'est un NO-OP : on marque la
    campagne ``envoyee`` et on enregistre le nombre de destinataires SANS
    aucun appel réseau. Renvoie la campagne. Une campagne déjà envoyée ou
    annulée n'est pas ré-envoyée.
    """
    if campagne.statut != Campagne.Statut.BROUILLON:
        return campagne
    cibles = list(destinataires or [])
    campagne.nb_destinataires = len(cibles)
    if brevo_actif() and cibles:
        # Intégration réelle (future) — jamais appelée tant que le flag est OFF.
        # On laisse le compteur d'envois aligné sur les destinataires ; les
        # ouvertures/clics seront remontés par les webhooks Brevo.
        campagne.nb_envois = len(cibles)
    campagne.statut = Campagne.Statut.ENVOYEE
    campagne.envoyee_le = timezone.now()
    campagne.save(update_fields=[
        'nb_destinataires', 'nb_envois', 'statut', 'envoyee_le'])
    return campagne


# ── FG202 — Déclenchement d'une séquence de relance (GATED, NO-OP) ──────────

def whatsapp_actif():
    """Toggle de l'intégration WhatsApp Business Cloud (Meta). OFF par défaut.

    Le founder l'active en posant ``WHATSAPP_ENABLED = True`` et un jeton
    ``WHATSAPP_ACCESS_TOKEN`` (settings/env). Tant que c'est faux/sans jeton,
    toute action WhatsApp (séquence FG202, inbound FG207) est un NO-OP — aucun
    appel Meta, aucune dépendance dure (CLAUDE.md règle #3 / blocage G2).
    """
    return bool(getattr(settings, 'WHATSAPP_ENABLED', False)
                and getattr(settings, 'WHATSAPP_ACCESS_TOKEN', ''))


def planifier_etapes_sequence(sequence, *, declenchee_le=None):
    """Calcule le calendrier d'une séquence (FG202) sans rien envoyer.

    Renvoie la liste des étapes avec leur date d'échéance (J0/J3/J7…). L'envoi
    réel (WhatsApp/email) est gated et n'a lieu que via les intégrations
    activées ; cette fonction est pure et NO-OP côté réseau. Sert au moteur de
    drip et aux tests.
    """
    base = declenchee_le or timezone.now()
    plan = []
    for etape in sequence.etapes.all().order_by('ordre'):
        echeance = base + timezone.timedelta(days=etape.delai_jours)
        plan.append({
            'etape_id': etape.id,
            'ordre': etape.ordre,
            'canal': etape.canal,
            'delai_jours': etape.delai_jours,
            'echeance': echeance,
            'envoye': False,  # gated : jamais d'envoi réel ici
        })
    return plan


# ── FG203 — Relance d'un devis abandonné ───────────────────────────────────

def enregistrer_relance_devis_abandonne(company, *, devis_id, devis_reference='',
                                        jours_sans_reponse=0, canal='',
                                        note=''):
    """Consigne une relance sur un devis envoyé non répondu (FG203).

    Ne touche pas le modèle Devis ; on ne fait qu'enregistrer la relance émise
    (comme un journal de recouvrement). ``devis_id`` est l'identifiant opaque
    côté ventes, fourni par l'appelant.
    """
    return RelanceDevisAbandonne.objects.create(
        company=company,
        devis_id=devis_id,
        devis_reference=devis_reference or '',
        jours_sans_reponse=jours_sans_reponse or 0,
        canal=canal or '',
        note=note or '',
    )


# ── FG205 — Enregistrement d'une ouverture de lien de partage ──────────────

def enregistrer_ouverture_partage(company, *, token, cible='devis',
                                  cible_reference=''):
    """Horodate une ouverture d'un ShareLink devis/facture (FG205), idempotent.

    Incrémente le compteur et met à jour premier/dernier vu. Un seul
    enregistrement par (société, token). Le ShareLink lui-même reste côté ventes
    — on n'indexe ici que l'événement d'ouverture pour prioriser les relances.
    """
    maintenant = timezone.now()
    obj, cree = OuverturePartage.objects.get_or_create(
        company=company, token=token,
        defaults={
            'cible': cible or 'devis',
            'cible_reference': cible_reference or '',
            'nb_ouvertures': 1,
            'premier_vu_le': maintenant,
            'dernier_vu_le': maintenant,
        },
    )
    if not cree:
        obj.nb_ouvertures = (obj.nb_ouvertures or 0) + 1
        obj.dernier_vu_le = maintenant
        if obj.premier_vu_le is None:
            obj.premier_vu_le = maintenant
        if cible_reference and not obj.cible_reference:
            obj.cible_reference = cible_reference
        obj.save(update_fields=[
            'nb_ouvertures', 'dernier_vu_le', 'premier_vu_le',
            'cible_reference'])
    return obj


# ── FG207 — Capture d'un message WhatsApp entrant (GATED, NO-OP) ───────────

def capturer_message_whatsapp(company, *, wa_message_id, expediteur,
                              nom_profil='', texte='', user=None):
    """Capture un message WhatsApp entrant → lead pré-qualifié (FG207), gated.

    Si l'intégration WhatsApp est inactive (défaut), c'est un NO-OP strict :
    aucun message n'est traité ni stocké. Quand activée, le message est
    journalisé (idempotent par ``wa_message_id``) et un lead DRAFT est
    créé/rattaché via ``crm.services`` (import function-local — jamais les
    modèles crm), en laissant le funnel à NEW. Renvoie le log, ou ``None`` si
    l'intégration est OFF.
    """
    if not whatsapp_actif():
        return None
    log, cree = MessageWhatsAppEntrant.objects.get_or_create(
        company=company, wa_message_id=wa_message_id,
        defaults={
            'expediteur': expediteur,
            'nom_profil': nom_profil or '',
            'texte': texte or '',
        },
    )
    if not cree or log.traite:
        return log
    # Création du lead DRAFT via le service crm (jamais ses modèles).
    try:
        from apps.crm import services as crm_services
        lead = crm_services.create_draft_lead_from_ocr(
            company=company, user=user,
            fields={
                # le service lit 'fournisseur'/'client' pour le nom du lead
                'client': nom_profil or expediteur,
                'telephone': expediteur,
                'whatsapp': expediteur,
            },
        )
        log.lead_id = getattr(lead, 'id', None)
    except Exception:
        # Le lead reste à créer manuellement ; le message est conservé.
        log.lead_id = None
    log.traite = True
    log.save(update_fields=['lead_id', 'traite'])
    return log


# ── FG211 — Configurateur guidé : validation de cohérence ──────────────────

def evaluer_session_guided_selling(reponses):
    """Valide la cohérence d'une configuration guidée (FG211).

    Vérifie des invariants simples (puissance onduleur vs kWc des panneaux,
    présence batterie si hybride…) et renvoie ``(composition, complet, alertes)``.
    Pur : ne crée aucun document. Sert l'assistant pas-à-pas commercial junior.
    """
    reponses = reponses or {}
    alertes = []
    composition = {}

    def _num(cle):
        try:
            return Decimal(str(reponses.get(cle)))
        except (TypeError, ValueError):
            return None

    kwc = _num('kwc')
    onduleur_kw = _num('onduleur_kw')
    if kwc is not None and onduleur_kw is not None:
        # Onduleur cohérent : ~0.8×–1.2× la puissance crête.
        if onduleur_kw < kwc * Decimal('0.7'):
            alertes.append(
                "Onduleur sous-dimensionné par rapport au champ PV (kWc).")
        if onduleur_kw > kwc * Decimal('1.5'):
            alertes.append(
                "Onduleur sur-dimensionné par rapport au champ PV (kWc).")
        composition['ratio_onduleur'] = float(
            (onduleur_kw / kwc).quantize(Decimal('0.01')))

    type_systeme = (reponses.get('type_systeme') or '').lower()
    a_batterie = bool(reponses.get('batterie'))
    if 'hybride' in type_systeme and not a_batterie:
        alertes.append("Système hybride sans batterie déclarée.")

    composition['type_systeme'] = type_systeme or 'reseau'
    composition['kwc'] = float(kwc) if kwc is not None else None
    complet = bool(kwc is not None and onduleur_kw is not None
                   and not alertes)
    return composition, complet, alertes


# ── FG213 — Décision d'approbation d'une configuration non-standard ────────

def decider_approbation_config(demande, *, approuver, user=None, commentaire=''):
    """Approuve ou refuse une demande d'approbation de config (FG213).

    Idempotent : une demande déjà décidée n'est pas re-décidée. Trace décideur,
    date et commentaire.
    """
    if demande.statut != DemandeApprobationConfig.Statut.EN_ATTENTE:
        return demande
    demande.statut = (
        DemandeApprobationConfig.Statut.APPROUVEE if approuver
        else DemandeApprobationConfig.Statut.REFUSEE)
    demande.decideur = user
    demande.commentaire_decision = commentaire or ''
    demande.date_decision = timezone.now()
    demande.save(update_fields=[
        'statut', 'decideur', 'commentaire_decision', 'date_decision'])
    return demande


# ── FG214 — Génération d'un token d'e-catalogue public ─────────────────────

def generer_ecatalogue(company, *, titre='Catalogue', produit_ids=None,
                       expire_le=None):
    """Crée une page e-catalogue publique tokenisée (FG214).

    Le token est long et imprévisible (secrets). La page n'exposera JAMAIS le
    prix d'achat ni de marge — uniquement le prix public TTC (filtré au rendu).
    """
    import secrets
    return ECatalogue.objects.create(
        company=company,
        titre=titre or 'Catalogue',
        token=secrets.token_urlsafe(32),
        produit_ids=list(produit_ids or []),
        expire_le=expire_le,
    )


# ── FG216 — Création (gated) d'un lead depuis une simulation publique ───────

def leads_depuis_simulation_actif():
    """Toggle de la création automatique d'un lead depuis le simulateur public.

    OFF par défaut → NO-OP (on enregistre seulement la simulation). Le founder
    l'active en posant ``PUBLIC_SIM_LEAD_ENABLED = True`` (settings/env). Aligné
    sur le pattern des autres intégrations gated (BREVO/WHATSAPP).
    """
    return bool(getattr(settings, 'PUBLIC_SIM_LEAD_ENABLED', False))


def creer_lead_depuis_simulation(simulation, *, user=None):
    """Crée un lead pré-rempli depuis une simulation publique (FG216), gated.

    Si le flag ``PUBLIC_SIM_LEAD_ENABLED`` est OFF (défaut), c'est un NO-OP :
    aucune création de lead. Quand il est ON et qu'un nom de prospect est
    présent, on délègue au SERVICE crm (jamais ses modèles, CLAUDE.md règle de
    modularité cross-app) via un import fonction-local. Idempotent : une
    simulation qui a déjà un lead n'en recrée pas. Renvoie l'id du lead ou None.
    """
    if simulation.lead_cree:
        return simulation.lead_id
    if not leads_depuis_simulation_actif():
        return None
    nom = (simulation.nom_prospect or '').strip()
    if not nom:
        return None
    from apps.crm import services as crm_services  # import local (anti-cycle)
    lead = crm_services.create_draft_lead_from_ocr(
        company=simulation.company,
        user=user,
        fields={'client': nom},
    )
    simulation.lead_cree = True
    simulation.lead_id = lead.id
    simulation.save(update_fields=['lead_cree', 'lead_id'])
    return lead.id


# ── FG217 — Calcul de mensualité crédit/leasing ────────────────────────────

def calcul_mensualite(montant, duree_mois, taux_annuel):
    """Mensualité d'un crédit amortissable (FG217), arrondie au centime.

    Formule classique de l'annuité constante. Taux 0 → simple division. Renvoie
    ``(mensualite, cout_total_credit)`` en Decimal. Pur, sans effet de bord.
    """
    montant = Decimal(montant or 0)
    n = int(duree_mois or 0)
    taux_annuel = Decimal(taux_annuel or 0)
    if n <= 0 or montant <= 0:
        return Decimal('0.00'), Decimal('0.00')
    if taux_annuel == 0:
        mensualite = montant / Decimal(n)
    else:
        taux_mensuel = taux_annuel / Decimal('100') / Decimal('12')
        facteur = (Decimal('1') + taux_mensuel) ** n
        mensualite = montant * taux_mensuel * facteur / (facteur - Decimal('1'))
    mensualite = mensualite.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    cout_total = (mensualite * Decimal(n) - montant).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    if cout_total < 0:
        cout_total = Decimal('0.00')
    return mensualite, cout_total


def recalculer_simulation_financement(simulation):
    """Recalcule mensualité + coût total d'une SimulationFinancement (FG217)."""
    mensualite, cout_total = calcul_mensualite(
        simulation.montant_finance, simulation.duree_mois,
        simulation.taux_annuel)
    simulation.mensualite = mensualite
    simulation.cout_total_credit = cout_total
    return simulation


# ── FG221 — Comparateur cash vs financement (calcul pur) ───────────────────

def comparer_cash_vs_financement(montant, duree_mois, taux_annuel,
                                 *, economie_annuelle=Decimal('0')):
    """Compare l'achat cash et le financement (FG221), calcul pur.

    Renvoie un dict {cash, financement} avec coût total et payback (années)
    estimé à partir de l'économie annuelle. Sert l'encart client anti-objection
    prix. Aucun stockage.
    """
    montant = Decimal(montant or 0)
    economie = Decimal(economie_annuelle or 0)
    mensualite, cout_credit = calcul_mensualite(
        montant, duree_mois, taux_annuel)
    cout_total_finance = montant + cout_credit

    def _payback(cout):
        if economie <= 0:
            return None
        return (cout / economie).quantize(
            Decimal('0.1'), rounding=ROUND_HALF_UP)

    return {
        'cash': {
            'cout_total': montant,
            'payback_annees': _payback(montant),
        },
        'financement': {
            'mensualite': mensualite,
            'cout_credit': cout_credit,
            'cout_total': cout_total_finance,
            'payback_annees': _payback(cout_total_finance),
        },
        'surcout_financement': cout_credit,
    }


# ── FG226 — Échéances d'AO dues (rappels) ──────────────────────────────────

def echeances_ao_dues(company, *, a_la_date=None):
    """Liste les échéances d'AO dont le rappel est dû (FG226), NON traitées.

    Une échéance est due quand ``date_echeance - rappel_jours <= a_la_date`` et
    qu'elle n'est pas encore traitée. Calcul pur (aucun envoi réseau) — sert au
    moteur d'alertes et aux tests.
    """
    a_la_date = a_la_date or timezone.now().date()
    dues = []
    qs = EcheanceAO.objects.filter(
        company=company, traitee=False).order_by('date_echeance')
    for ech in qs:
        seuil = ech.date_echeance - timezone.timedelta(days=ech.rappel_jours)
        if seuil <= a_la_date:
            dues.append(ech)
    return dues


# ── FG227 — Taux de réussite des appels d'offres ───────────────────────────

def taux_reussite_ao(company):
    """Taux de réussite gagné/perdu des AO (FG227).

    Compte les résultats par issue et calcule le taux = gagnés / (gagnés +
    perdus). Renvoie un dict d'agrégats. Lecture seule.
    """
    resultats = ResultatAO.objects.filter(company=company)
    gagnes = resultats.filter(issue=ResultatAO.Issue.GAGNE).count()
    perdus = resultats.filter(issue=ResultatAO.Issue.PERDU).count()
    total_decides = gagnes + perdus
    taux = Decimal('0.00')
    if total_decides > 0:
        taux = (Decimal(gagnes) / Decimal(total_decides) * Decimal('100')
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'gagnes': gagnes,
        'perdus': perdus,
        'total_decides': total_decides,
        'total_resultats': resultats.count(),
        'taux_reussite_pct': taux,
    }


# ── FG228 — Provisionnement (gated) d'un compte portail client ─────────────

def provisionner_compte_portail(company, *, client_id):
    """Crée/active un compte portail client tokenisé (FG228).

    Token long/imprévisible (secrets). Idempotent par (company, client) :
    réactive et renvoie le compte existant plutôt que d'en dupliquer un. Le
    compte se lie au client PAR FK (``crm.Client``) et réutilise son email
    (DC32 — pas de 2ᵉ copie d'identité) ; il NE duplique aucune donnée métier
    (devis/factures/chantiers lus à la volée via les selectors des apps cibles).
    """
    import secrets
    compte = ComptePortailClient.objects.filter(
        company=company, client_id=client_id).first()
    if compte is not None:
        if not compte.actif:
            compte.actif = True
            compte.save(update_fields=['actif'])
        return compte
    return ComptePortailClient.objects.create(
        company=company,
        client_id=client_id,
        token_acces=secrets.token_urlsafe(32),
    )


# ── FG229 — Acceptation / e-signature de devis dans le portail ─────────────

def signer_acceptation_devis(acceptation, *, nom=None, ip=None):
    """Matérialise la signature d'une acceptation de devis (FG229), idempotent.

    Pose le nom du signataire (si fourni), l'IP, le drapeau ``accepte`` et
    l'horodatage de signature. Une acceptation déjà signée n'est PAS resignée
    (idempotent). Renvoie l'acceptation. L'effet sur le statut du devis côté
    ``ventes`` (passage à ``accepte``) reste à la charge de l'app ventes via son
    service ; on ne touche jamais ses modèles ici (cross-app).
    """
    if acceptation.accepte:
        return acceptation
    if nom:
        acceptation.nom_signataire = nom
    if ip:
        acceptation.signature_ip = ip
    acceptation.accepte = True
    acceptation.signe_le = timezone.now()
    acceptation.save(update_fields=[
        'nom_signataire', 'signature_ip', 'accepte', 'signe_le'])
    return acceptation


# ── FG230 — Paiement en ligne des factures (portail, GATED CMI) ────────────

def cmi_actif():
    """Toggle de la passerelle de paiement carte CMI. OFF par défaut → NO-OP.

    Le founder l'active en posant ``CMI_ENABLED = True`` et une clé marchande
    ``CMI_MERCHANT_KEY`` (settings/env). Tant que c'est faux/sans clé, initier un
    paiement carte ne fait AUCUN appel réseau (intention reste « initie ») — le
    rapprochement reste manuel, comme le virement (blocage G/COST FG230).
    """
    return bool(getattr(settings, 'CMI_ENABLED', False)
                and getattr(settings, 'CMI_MERCHANT_KEY', ''))


def initier_paiement_facture(paiement):
    """Initie un paiement de facture portail (FG230), idempotent.

    Pose une référence locale si absente. Si la méthode est carte et que CMI est
    actif, l'intégration réelle (future) générerait l'URL de paiement ; tant que
    CMI est OFF, c'est un NO-OP propre (aucun appel réseau). Renvoie le paiement.
    """
    if paiement.statut != PaiementFacturePortail.Statut.INITIE:
        return paiement
    if not paiement.reference:
        import secrets
        paiement.reference = f'PF-{secrets.token_hex(8)}'
        paiement.save(update_fields=['reference'])
    # NO-OP gated : l'appel CMI réel n'a lieu que si cmi_actif() est vrai.
    return paiement


def rapprocher_paiement_facture(paiement, *, reference=None):
    """Marque un paiement de facture portail comme payé (FG230), idempotent.

    Sert le rapprochement auto (webhook CMI) ET le rapprochement manuel d'un
    virement reçu. Un paiement déjà payé/échoué n'est pas re-rapproché. Le
    report vers un ``Paiement`` comptable reste à la charge de la chaîne ventes
    via son service (cross-app) ; on ne touche jamais ses modèles ici.
    """
    if paiement.statut != PaiementFacturePortail.Statut.INITIE:
        return paiement
    if reference:
        paiement.reference = reference
    paiement.statut = PaiementFacturePortail.Statut.PAYE
    paiement.paye_le = timezone.now()
    paiement.save(update_fields=['reference', 'statut', 'paye_le'])
    return paiement


# ── FG235 — Commissions partenaires ────────────────────────────────────────

def calculer_montant_commission(base_ht, taux):
    """Calcule le montant d'une commission = base_ht × taux%, arrondi 2 déc."""
    base = Decimal(base_ht or 0)
    t = Decimal(taux or 0)
    montant = (base * t / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    return montant


def enregistrer_commission(commission):
    """Recalcule et fige le montant d'une commission (FG235) depuis base×taux.

    Idempotent : appelable à la création et à chaque mise à jour. Renvoie la
    commission. Si le taux n'est pas fourni, on retombe sur celui du partenaire.
    """
    if not commission.taux and commission.partenaire_id:
        commission.taux = commission.partenaire.taux_commission
    commission.montant = calculer_montant_commission(
        commission.base_ht, commission.taux)
    return commission


# ── FG236 — Affectation automatique par territoire commercial ──────────────

def affecter_territoire(company, ville):
    """Renvoie le territoire commercial (scopé société) matchant ``ville``.

    Parcourt les territoires ACTIFS par priorité décroissante et renvoie le
    premier dont le zonage matche la ville, ou ``None``. Sert l'affectation auto
    d'un lead (FG236) — le lead réel est rattaché par l'app crm ; ici on résout
    seulement la zone/commercial cible (pas d'import crm).
    """
    from .models import TerritoireCommercial
    if not ville:
        return None
    territoires = (TerritoireCommercial.objects
                   .filter(company=company, actif=True)
                   .order_by('-priorite', 'nom'))
    for t in territoires:
        if t.matche_ville(ville):
            return t
    return None


# ── FG238 — Enquêtes NPS / satisfaction (envoi gated, score consolidé) ─────

def envoyer_enquete_nps(enquete):
    """Marque l'envoi d'une enquête NPS (FG238), gated Brevo (NO-OP par défaut).

    Si Brevo est actif (``brevo_actif()``), l'intégration réelle (future)
    enverrait l'email et ``envoi_reel`` passerait à vrai. Tant que c'est OFF,
    l'enquête est créée/marquée « envoyée » SANS appel réseau. Idempotent.
    """
    if brevo_actif():
        enquete.envoi_reel = True
        enquete.save(update_fields=['envoi_reel'])
    return enquete


def repondre_enquete_nps(enquete, *, score, commentaire=None):
    """Enregistre la réponse d'un client à une enquête NPS (FG238).

    ``score`` est borné 0–10. Passe l'enquête à « répondue » et horodate.
    Renvoie l'enquête. Une enquête déjà répondue n'est pas ré-écrite.
    """
    from .models import EnqueteNPS
    if enquete.statut == EnqueteNPS.Statut.REPONDUE:
        return enquete
    note = max(0, min(10, int(score)))
    enquete.score = note
    if commentaire is not None:
        enquete.commentaire = commentaire
    enquete.statut = EnqueteNPS.Statut.REPONDUE
    enquete.repondue_le = timezone.now()
    enquete.save(update_fields=[
        'score', 'commentaire', 'statut', 'repondue_le'])
    return enquete


def score_nps(company):
    """Score NPS consolidé (FG238) = %promoteurs − %détracteurs, scopé société.

    Ne compte que les enquêtes répondues (score non nul). Renvoie un dict avec
    le score NPS (entier, −100..100), les compteurs et le nombre de réponses.
    Zéro réponse → score None.
    """
    from .models import EnqueteNPS
    reponses = EnqueteNPS.objects.filter(
        company=company, statut=EnqueteNPS.Statut.REPONDUE,
        score__isnull=False)
    total = reponses.count()
    if total == 0:
        return {'nps': None, 'total': 0, 'promoteurs': 0, 'passifs': 0,
                'detracteurs': 0}
    promoteurs = reponses.filter(score__gte=9).count()
    detracteurs = reponses.filter(score__lte=6).count()
    passifs = total - promoteurs - detracteurs
    nps = round((promoteurs - detracteurs) * 100 / total)
    return {'nps': nps, 'total': total, 'promoteurs': promoteurs,
            'passifs': passifs, 'detracteurs': detracteurs}


# ── FG239 — Push Google Reviews (routage, gated par URL société) ───────────

def google_review_url_configuree():
    """Lien de dépôt d'avis Google configuré (paramètre ``GOOGLE_REVIEW_URL``).

    Pas d'API payante — juste une URL « place review » à laquelle on route le
    client. Vide → le push est un NO-OP propre.
    """
    return str(getattr(settings, 'GOOGLE_REVIEW_URL', '') or '')


def pousser_avis_google(avis):
    """Route un avis client vers Google Reviews (FG239), idempotent.

    Si un lien Google est configuré, on le pose sur l'avis et on passe le statut
    à « routé vers Google ». Sinon NO-OP (aucun lien, statut inchangé). Renvoie
    l'avis. On ne publie jamais rien via une API payante — on fournit le lien.
    """
    from .models import AvisClient
    url = google_review_url_configuree()
    if not url:
        return avis
    avis.google_review_url = url
    avis.statut = AvisClient.Statut.PUBLIE_GOOGLE
    avis.save(update_fields=['google_review_url', 'statut'])
    return avis


# ── FG240 — Programme de fidélité étendu (points + paliers) ────────────────

def palier_pour_points(points):
    """Palier de fidélité (FG240) déduit d'un solde de points.

    Bronze <500, Argent 500–1999, Or 2000–4999, Platine ≥5000.
    """
    p = int(points or 0)
    if p >= 5000:
        return 'platine'
    if p >= 2000:
        return 'or'
    if p >= 500:
        return 'argent'
    return 'bronze'


def appliquer_mouvement_fidelite(compte, *, points, motif=''):
    """Applique un mouvement de points (FG240) et recalcule solde + palier.

    Crée un ``MouvementFidelite`` (idempotence à la charge de l'appelant), met à
    jour le solde et le palier du compte de façon atomique. Le solde ne descend
    jamais sous 0. Renvoie le mouvement créé.
    """
    from .models import MouvementFidelite
    delta = int(points or 0)
    with transaction.atomic():
        mouvement = MouvementFidelite.objects.create(
            company=compte.company, compte=compte, points=delta, motif=motif)
        compte.points = max(0, compte.points + delta)
        compte.palier = palier_pour_points(compte.points)
        compte.save(update_fields=['points', 'palier'])
    return mouvement


# ── FG241 — Moteur d'upsell / cross-sell ───────────────────────────────────

def suggestions_upsell(company, contexte):
    """Suggestions d'upsell/cross-sell (FG241) pour un contexte client.

    ``contexte`` est un dict de drapeaux booléens dont les CLÉS sont des valeurs
    de ``RegleUpsell.Declencheur`` (ex. ``{'sans_batterie': True,
    'site_unique': True}``). Renvoie la liste des règles ACTIVES (scopées
    société) dont le déclencheur est vrai dans le contexte, triées par priorité
    décroissante. Fonction pure (pas d'effet de bord, pas d'import cross-app).
    """
    from .models import RegleUpsell
    contexte = contexte or {}
    actives_vraies = [
        cle for cle, val in contexte.items() if val]
    if not actives_vraies:
        return []
    return list(
        RegleUpsell.objects
        .filter(company=company, actif=True, declencheur__in=actives_vraies)
        .order_by('-priorite', 'id'))


# ── FG244 — Abonnements de monitoring (échéance récurrente) ────────────────

def _ajouter_mois(d, mois):
    """Ajoute ``mois`` mois à une date en bornant le jour à la fin de mois."""
    import calendar
    total = d.month - 1 + mois
    annee = d.year + total // 12
    mois_final = total % 12 + 1
    jour = min(d.day, calendar.monthrange(annee, mois_final)[1])
    return d.replace(year=annee, month=mois_final, day=jour)


def prochaine_echeance_abonnement(depuis, periodicite):
    """Prochaine échéance d'un abonnement monitoring (FG244) depuis ``depuis``.

    Mensuel → +1 mois ; annuel → +12 mois. ``depuis`` est une date.
    """
    from .models import AbonnementMonitoring
    pas = 12 if periodicite == AbonnementMonitoring.Periodicite.ANNUEL else 1
    return _ajouter_mois(depuis, pas)


def renouveler_abonnement_monitoring(abonnement, *, today=None):
    """Renouvelle un abonnement monitoring (FG244) : avance l'échéance.

    Actif uniquement. Pose ``date_debut`` si absente, puis fixe
    ``prochaine_echeance`` à une période après la base (échéance courante si
    future, sinon aujourd'hui). Idempotence à la charge de l'appelant. Renvoie
    l'abonnement.
    """
    from .models import AbonnementMonitoring
    if abonnement.statut != AbonnementMonitoring.Statut.ACTIF:
        return abonnement
    if today is None:
        today = timezone.localdate()
    if abonnement.date_debut is None:
        abonnement.date_debut = today
    base = abonnement.prochaine_echeance or today
    if base < today:
        base = today
    abonnement.prochaine_echeance = prochaine_echeance_abonnement(
        base, abonnement.periodicite)
    abonnement.save(update_fields=['date_debut', 'prochaine_echeance'])
    return abonnement


# ── COMPTA2 — Mapping document → compte comptable ──────────────────────────

# Correspondances par défaut « clef documentaire → numéro de compte CGNC ».
# Semées de façon idempotente, elles rendent le posting paramétrable sans coder
# les comptes en dur. (type_clef, clef, numéro, libellé.)
_MAPPINGS_DEFAUT = [
    # Familles de produit → comptes de produits (classe 7)
    ('famille', 'panneau', '7121', 'Ventes panneaux'),
    ('famille', 'onduleur', '7121', 'Ventes onduleurs'),
    ('famille', 'batterie', '7121', 'Ventes batteries'),
    ('famille', 'pompe', '7121', 'Ventes pompage'),
    ('famille', 'installation', '7121', 'Prestations installation'),
    # Taux de TVA → comptes de TVA facturée (classe 4)
    ('tva', '20', '4455', 'TVA facturée 20 %'),
    ('tva', '14', '4455', 'TVA facturée 14 %'),
    ('tva', '10', '4455', 'TVA facturée 10 %'),
    ('tva', '7', '4455', 'TVA facturée 7 %'),
    ('tva', '0', '4455', 'TVA facturée 0 %'),
    # Modes de paiement → comptes de trésorerie (classe 5)
    ('paiement', 'virement', '5141', 'Banque (virement)'),
    ('paiement', 'cheque', '5141', 'Banque (chèque)'),
    ('paiement', 'carte', '5141', 'Banque (carte)'),
    ('paiement', 'especes', '5161', 'Caisse (espèces)'),
]


@transaction.atomic
def seed_mappings_defaut(company):
    """Sème les mappings document→compte par défaut (idempotent, additif).

    Ne touche JAMAIS un mapping existant : le founder peut redéfinir un compte
    pour une clef sans que le seed ne l'écrase. Sème le plan comptable au besoin
    (les comptes cibles doivent exister). Renvoie la liste des mappings.
    """
    if not PlanComptable.objects.filter(company=company).exists():
        seed_plan_comptable(company)
    created = []
    for type_clef, clef, numero, libelle in _MAPPINGS_DEFAUT:
        compte = get_compte(company, numero)
        if compte is None:
            continue
        mapping, _ = MappingCompte.objects.get_or_create(
            company=company, type_clef=type_clef, clef=clef,
            defaults={'compte': compte, 'libelle': libelle},
        )
        created.append(mapping)
    return created


def compte_pour_clef(company, type_clef, clef, *, defaut=None):
    """Compte mappé pour ``(type_clef, clef)`` d'une société, ou ``defaut``.

    Lecture seule. ``clef`` est normalisée (str, minuscules, sans espaces) pour
    tolérer les variations de casse. Un mapping inactif est ignoré.
    """
    if clef is None:
        return defaut
    clef_norm = str(clef).strip().lower()
    mapping = MappingCompte.objects.filter(
        company=company, type_clef=type_clef, clef__iexact=clef_norm,
        actif=True,
    ).select_related('compte').first()
    return mapping.compte if mapping else defaut


# ── COMPTA3 — Comptes auxiliaires tiers (via selectors crm/stock) ──────────

def _prochain_code_auxiliaire(company, type_tiers):
    """Prochain code auxiliaire libre (C0001/F0001…) pour un type de tiers.

    Basé sur le plus grand suffixe numérique déjà utilisé + 1 (jamais count()+1)
    — cohérent avec la politique de numérotation du projet. Scopé société.
    """
    import re
    prefixe = 'C' if type_tiers == CompteAuxiliaire.TypeTiers.CLIENT else 'F'
    codes = CompteAuxiliaire.objects.filter(
        company=company, type_tiers=type_tiers,
    ).values_list('code', flat=True)
    plus_haut = 0
    for code in codes:
        m = re.search(r'(\d+)$', code or '')
        if m:
            plus_haut = max(plus_haut, int(m.group(1)))
    return f'{prefixe}{plus_haut + 1:04d}'


@transaction.atomic
def assurer_compte_auxiliaire_client(company, client_id):
    """Compte auxiliaire du client (crée s'il manque), ou None si client inconnu.

    Le client est VALIDÉ scopé société via ``crm.selectors.get_company_client``
    (jamais un import de ``crm.models``). Rattaché au compte collectif 3421.
    Idempotent : un même client ne produit qu'un auxiliaire par société.
    """
    from apps.crm.selectors import get_company_client
    client = get_company_client(company, client_id)
    if client is None:
        return None
    existant = CompteAuxiliaire.objects.filter(
        company=company, type_tiers=CompteAuxiliaire.TypeTiers.CLIENT,
        tiers_id=client_id,
    ).first()
    if existant:
        return existant
    collectif = get_compte(company, '3421')
    if collectif is None:
        seed_plan_comptable(company)
        collectif = get_compte(company, '3421')
    return CompteAuxiliaire.objects.create(
        company=company,
        compte_collectif=collectif,
        type_tiers=CompteAuxiliaire.TypeTiers.CLIENT,
        tiers_id=client_id,
        code=_prochain_code_auxiliaire(
            company, CompteAuxiliaire.TypeTiers.CLIENT),
    )


@transaction.atomic
def assurer_compte_auxiliaire_fournisseur(company, fournisseur_id):
    """Compte auxiliaire du fournisseur (crée s'il manque), ou None si inconnu.

    Le fournisseur est VALIDÉ scopé société via
    ``stock.selectors.get_fournisseur_tiers_identity`` (jamais un import de
    ``stock.models``). Rattaché au compte collectif 4411. Idempotent.
    """
    from apps.stock.selectors import get_fournisseur_tiers_identity
    identite = get_fournisseur_tiers_identity(company, fournisseur_id)
    if identite is None:
        return None
    existant = CompteAuxiliaire.objects.filter(
        company=company, type_tiers=CompteAuxiliaire.TypeTiers.FOURNISSEUR,
        tiers_id=fournisseur_id,
    ).first()
    if existant:
        return existant
    collectif = get_compte(company, '4411')
    if collectif is None:
        seed_plan_comptable(company)
        collectif = get_compte(company, '4411')
    return CompteAuxiliaire.objects.create(
        company=company,
        compte_collectif=collectif,
        type_tiers=CompteAuxiliaire.TypeTiers.FOURNISSEUR,
        tiers_id=fournisseur_id,
        code=_prochain_code_auxiliaire(
            company, CompteAuxiliaire.TypeTiers.FOURNISSEUR),
    )


# ── COMPTA9 — Numérotation séquentielle des pièces (references.py) ─────────

def creer_ecriture_numerotee(company, journal, date_ecriture, libelle, lignes,
                             *, prefixe=None, created_by=None, statut=None,
                             source_type='', source_id=None):
    """Comme ``creer_ecriture`` mais attribue une référence de pièce SÉQUENTIELLE.

    La référence (ex. ``PC-202607-0001``) est générée par
    ``apps.ventes.utils.references.create_with_reference`` (plus-haut-utilisé + 1,
    savepoint + retry sur course) — JAMAIS ``count()+1``. Le préfixe par défaut
    dérive du code du journal (``PC-<CODE>``). Renvoie l'écriture équilibrée.
    """
    from apps.ventes.utils.references import create_with_reference
    pref = prefixe or f'PC-{journal.code}'

    def _save(reference):
        return creer_ecriture(
            company, journal, date_ecriture, libelle, lignes,
            reference=reference, source_type=source_type, source_id=source_id,
            created_by=created_by, statut=statut,
        )

    return create_with_reference(
        EcritureComptable, pref, company, _save)


def sequence_piece_journal(company, journal, *, prefixe=None):
    """COMPTA4 — Prochain numéro de pièce SÉQUENTIEL d'un journal (aperçu).

    Renvoie la prochaine référence libre (ex. ``PC-VTE-202607-0003``) pour le
    journal sans créer d'écriture — pratique pour afficher le numéro qui SERA
    attribué. S'appuie sur ``references.next_reference`` (plus-haut+1, scopé
    société/mois), donc chaque journal a sa propre séquence via son préfixe.
    """
    from apps.ventes.utils.references import next_reference
    pref = prefixe or f'PC-{journal.code}'
    return next_reference(EcritureComptable, pref, company)


# ── COMPTA11 — Extourne / contre-passation d'une écriture validée ──────────

@transaction.atomic
def extourner_ecriture(ecriture, *, date_extourne=None, user=None,
                       libelle=None):
    """Crée l'écriture d'extourne (contre-passation) d'une écriture existante.

    On NE SUPPRIME JAMAIS une écriture validée : on passe une écriture inverse
    (débit↔crédit permutés) au même journal, ce qui solde comptablement
    l'originale tout en gardant la piste d'audit. Idempotent via
    ``source_type='extourne'`` + ``source_id`` = id de l'écriture d'origine.

    Refuse d'extourner une écriture dont la date d'extourne tombe dans une
    période verrouillée (garde-fou hérité de ``EcritureComptable.save``).
    Renvoie l'écriture d'extourne (existante ou nouvelle).
    """
    company = ecriture.company
    if date_extourne is None:
        date_extourne = timezone.localdate()
    # Idempotence : une écriture n'a qu'une seule extourne par société.
    existante = _ecriture_existante(company, 'extourne', ecriture.id)
    if existante:
        return existante
    lignes = []
    for lig in ecriture.lignes.all():
        # Permute débit et crédit pour annuler la ligne d'origine.
        lignes.append({
            'compte': lig.compte,
            'debit': lig.credit,
            'credit': lig.debit,
            'libelle': f'Extourne — {lig.libelle}' if lig.libelle else 'Extourne',
            'tiers_type': lig.tiers_type,
            'tiers_id': lig.tiers_id,
            'centre_cout': lig.centre_cout,
        })
    if not lignes:
        raise ValidationError(
            "Impossible d'extourner une écriture sans ligne.")
    lib = libelle or f'Extourne de : {ecriture.libelle}'
    return creer_ecriture(
        company, ecriture.journal, date_extourne, lib, lignes,
        reference=f'EXT-{ecriture.reference}' if ecriture.reference else '',
        source_type='extourne', source_id=ecriture.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )


# ── COMPTA39 — Piste d'audit comptable inaltérable (hash-chaînée) ──────────
# Chaque écriture validée est scellée dans un maillon append-only enchaîné au
# précédent : hash = SHA256(hash_precedent + empreinte_contenu). Toute altération
# d'une écriture déjà scellée casse la chaîne à la vérification. Purement additif :
# aucun scellement n'a lieu tant que ``enregistrer_piste_audit`` n'est pas appelé.

def _empreinte_ecriture(ecriture):
    """Empreinte SHA-256 déterministe du contenu d'une écriture (+ ses lignes).

    On sérialise les champs de tête (référence, date, journal, libellé, statut,
    source) et chaque ligne (compte, débit, crédit, tiers) dans un ordre stable,
    puis on hache. Toute modification ultérieure d'un de ces champs change
    l'empreinte — donc casse la chaîne. Lecture seule.
    """
    parties = [
        str(ecriture.company_id),
        str(ecriture.reference or ''),
        ecriture.date_ecriture.isoformat() if ecriture.date_ecriture else '',
        str(ecriture.journal_id),
        str(ecriture.libelle or ''),
        str(ecriture.statut or ''),
        str(ecriture.source_type or ''),
        str(ecriture.source_id or ''),
    ]
    lignes = ecriture.lignes.order_by('id').values_list(
        'compte__numero', 'debit', 'credit', 'tiers_type', 'tiers_id')
    for numero, debit, credit, t_type, t_id in lignes:
        parties.append(
            f'{numero}|{debit}|{credit}|{t_type or ""}|{t_id or ""}')
    charge = '\n'.join(parties).encode('utf-8')
    return hashlib.sha256(charge).hexdigest()


@transaction.atomic
def enregistrer_piste_audit(ecriture):
    """Scelle une écriture dans la piste d'audit hash-chaînée (idempotent).

    Crée UN maillon enchaîné au dernier maillon de la société. Si l'écriture est
    déjà scellée, renvoie son maillon existant sans rien récrire (append-only).
    ``company`` déduite de l'écriture. Renvoie le maillon.
    """
    company = ecriture.company
    if company is None:
        return None
    existant = PisteAuditComptable.objects.filter(
        company=company, ecriture=ecriture).first()
    if existant:
        return existant
    dernier = PisteAuditComptable.objects.filter(
        company=company).order_by('-sequence').first()
    hash_precedent = dernier.hash if dernier else ''
    sequence = (dernier.sequence + 1) if dernier else 1
    empreinte = _empreinte_ecriture(ecriture)
    hash_maillon = hashlib.sha256(
        (hash_precedent + empreinte).encode('utf-8')).hexdigest()
    return PisteAuditComptable.objects.create(
        company=company,
        ecriture=ecriture,
        sequence=sequence,
        empreinte_contenu=empreinte,
        hash_precedent=hash_precedent,
        hash=hash_maillon,
    )


def verifier_integrite_piste(company):
    """Vérifie l'intégrité de la piste d'audit hash-chaînée d'une société.

    Recalcule chaque maillon dans l'ordre : l'empreinte doit correspondre au
    contenu ACTUEL de l'écriture et le hash chaîné doit recoller au maillon
    précédent. Renvoie ``{'valide': bool, 'nb_maillons': int, 'rupture': …}`` où
    ``rupture`` est le rang du premier maillon incohérent (None si tout est
    intègre). Lecture seule.
    """
    maillons = list(PisteAuditComptable.objects.filter(
        company=company).select_related('ecriture').order_by('sequence'))
    hash_precedent = ''
    for maillon in maillons:
        empreinte = _empreinte_ecriture(maillon.ecriture)
        attendu = hashlib.sha256(
            (hash_precedent + empreinte).encode('utf-8')).hexdigest()
        if (empreinte != maillon.empreinte_contenu
                or maillon.hash_precedent != hash_precedent
                or maillon.hash != attendu):
            return {
                'valide': False,
                'nb_maillons': len(maillons),
                'rupture': maillon.sequence,
            }
        hash_precedent = maillon.hash
    return {
        'valide': True,
        'nb_maillons': len(maillons),
        'rupture': None,
    }


# ── COMPTA6 — Dossier CGNC prêt à valider (fiduciaire) ─────────────────────
#
# Cette section NE crée ni ne modifie aucune donnée : elle STRUCTURE le plan
# comptable existant + son barème CGNC de référence, puis produit un DOSSIER DE
# CONTRÔLE qu'un fiduciaire / expert-comptable humain relit avant la validation
# LÉGALE finale (qui, elle, reste un acte humain — cf. docs/compta-cgnc-dossier).
# Tout est scopé société et purement en lecture ; aucune donnée d'achat/marge
# n'y figure (le module ne stocke pas de prix d'achat).

# Libellés officiels des 8 classes du CGNC marocain (source : IntegerChoices du
# modèle ``CompteComptable.Classe`` — jamais réécrits en dur ailleurs).
CGNC_CLASSES = {
    1: 'Financement permanent',
    2: 'Actif immobilisé',
    3: 'Actif circulant (hors trésorerie)',
    4: 'Passif circulant (hors trésorerie)',
    5: 'Trésorerie',
    6: 'Charges',
    7: 'Produits',
    8: 'Résultats',
}


def _sens_attendu_pour_classe(classe):
    """Sens « naturel » attendu d'un compte d'après sa classe CGNC.

    Sert au contrôle de cohérence du champ ``sens`` : un compte de classe 6 est
    une charge, de classe 7 un produit, etc. Les classes de bilan (1..5) ont un
    sens actif/passif de référence ; on ne bloque pas (certains comptes de
    régularisation dérogent), on SIGNALE.
    """
    return {
        1: 'passif', 2: 'actif', 3: 'actif', 4: 'passif',
        5: 'actif', 6: 'charge', 7: 'produit',
    }.get(classe)


def plan_cgnc_reference():
    """Barème CGNC de référence semé par le module (lecture seule, structuré).

    Renvoie la liste des comptes usuels du CGNC marocain que le module connaît,
    groupés par classe : ``{classe: {'libelle', 'comptes': [{numero, intitule,
    est_tiers, lettrable, sens}, …]}}``. C'est le référentiel auquel le plan
    RÉEL d'une société est comparé (complétude du mapping).
    """
    ref = {}
    for numero, intitule, est_tiers, lettrable, sens in _COMPTES_CGNC:
        classe = _classe_de(numero)
        bucket = ref.setdefault(
            classe, {'libelle': CGNC_CLASSES.get(classe, ''), 'comptes': []})
        bucket['comptes'].append({
            'numero': numero,
            'intitule': intitule,
            'est_tiers': est_tiers,
            'lettrable': lettrable,
            'sens': sens,
        })
    for bucket in ref.values():
        bucket['comptes'].sort(key=lambda c: c['numero'])
    return ref


def _plan_comptable_structure(company):
    """Plan comptable RÉEL d'une société, groupé par classe (lecture seule).

    ``{classe: {'libelle', 'comptes': [{numero, intitule, sens, est_tiers,
    lettrable, actif}, …]}}`` pour les classes 1..8, uniquement celles qui
    portent au moins un compte.
    """
    structure = {}
    comptes = CompteComptable.objects.filter(
        company=company).order_by('numero')
    for compte in comptes:
        bucket = structure.setdefault(
            compte.classe,
            {'libelle': CGNC_CLASSES.get(compte.classe, ''), 'comptes': []})
        bucket['comptes'].append({
            'numero': compte.numero,
            'intitule': compte.intitule,
            'sens': compte.sens,
            'est_tiers': compte.est_tiers,
            'lettrable': compte.lettrable,
            'actif': compte.actif,
        })
    return structure


def controles_coherence_cgnc(company):
    """Contrôles de cohérence du plan comptable d'une société (COMPTA6).

    Purement en lecture, scopé société. Renvoie la liste des anomalies, chacune
    ``{'code', 'severite', 'message', 'comptes'?}`` où ``severite`` ∈
    {'bloquant', 'avertissement', 'info'} :

    * ``classe_incoherente`` — le 1er chiffre du numéro ≠ champ ``classe``.
    * ``classe_hors_cgnc`` — classe hors 1..8.
    * ``sens_incoherent`` — sens ≠ sens naturel attendu de la classe.
    * ``numero_non_numerique`` — numéro qui ne commence pas par un chiffre.
    * ``compte_reference_absent`` — un compte MOUVEMENTÉ (présent dans une ligne
      d'écriture) qui n'existe plus au plan (référence orpheline).
    * ``compte_ref_manquant`` — un compte usuel du barème CGNC absent du plan
      (complétude du mapping vs le standard marocain).

    Les seules anomalies ``bloquant`` sont les incohérences structurelles
    (classe/numéro) ; le reste est un avertissement ou une info que le
    fiduciaire arbitre.
    """
    anomalies = []
    comptes = list(CompteComptable.objects.filter(
        company=company).order_by('numero'))
    numeros_existants = {c.numero for c in comptes}

    for compte in comptes:
        prem = compte.numero[:1]
        if not prem.isdigit():
            anomalies.append({
                'code': 'numero_non_numerique',
                'severite': 'bloquant',
                'message': (
                    f"Compte {compte.numero} « {compte.intitule} » : le numéro "
                    "ne commence pas par un chiffre de classe CGNC."),
                'comptes': [compte.numero],
            })
            continue
        classe_num = int(prem)
        if classe_num not in CGNC_CLASSES:
            anomalies.append({
                'code': 'classe_hors_cgnc',
                'severite': 'bloquant',
                'message': (
                    f"Compte {compte.numero} : classe {classe_num} hors du "
                    "cadre CGNC (1 à 8)."),
                'comptes': [compte.numero],
            })
            continue
        if compte.classe != classe_num:
            anomalies.append({
                'code': 'classe_incoherente',
                'severite': 'bloquant',
                'message': (
                    f"Compte {compte.numero} : classe déclarée "
                    f"{compte.classe} ≠ classe du numéro ({classe_num})."),
                'comptes': [compte.numero],
            })
        attendu = _sens_attendu_pour_classe(classe_num)
        if compte.sens and attendu and compte.sens != attendu:
            anomalies.append({
                'code': 'sens_incoherent',
                'severite': 'avertissement',
                'message': (
                    f"Compte {compte.numero} : sens « {compte.sens} » ≠ sens "
                    f"naturel attendu « {attendu} » de la classe {classe_num}."),
                'comptes': [compte.numero],
            })

    # Références orphelines : un compte mouvementé mais absent du plan. Comme le
    # FK LigneEcriture→CompteComptable est protégé, ce cas ne survient qu'avec
    # des comptes désactivés (actif=False) encore porteurs d'écritures.
    numeros_mouvementes = set(
        LigneEcriture.objects.filter(company=company)
        .values_list('compte__numero', flat=True).distinct())
    numeros_inactifs = {c.numero for c in comptes if not c.actif}
    for numero in sorted(numeros_mouvementes & numeros_inactifs):
        anomalies.append({
            'code': 'compte_reference_absent',
            'severite': 'avertissement',
            'message': (
                f"Compte {numero} désactivé mais encore mouvementé : à "
                "réactiver ou à solder avant clôture."),
            'comptes': [numero],
        })

    # Complétude du mapping : comptes usuels du barème CGNC absents du plan.
    manquants = [
        entry[0] for entry in _COMPTES_CGNC
        if entry[0] not in numeros_existants
    ]
    if manquants:
        anomalies.append({
            'code': 'compte_ref_manquant',
            'severite': 'info',
            'message': (
                f"{len(manquants)} compte(s) usuel(s) du barème CGNC absent(s) "
                "du plan (semer via seed_plan_comptable si nécessaire)."),
            'comptes': sorted(manquants),
        })

    return anomalies


def construire_dossier_cgnc(company):
    """Construit le DOSSIER DE CONTRÔLE CGNC d'une société (COMPTA6).

    Assemble, en lecture seule et scopé société :

    * ``plan_comptable`` — le plan RÉEL groupé par classe (1..8) ;
    * ``reference_cgnc`` — le barème CGNC de référence groupé par classe ;
    * ``controles`` — la liste des anomalies (cf. ``controles_coherence_cgnc``) ;
    * ``synthese`` — compteurs (nb comptes, comptes par classe, nb anomalies par
      sévérité, complétude vs le barème) ;
    * ``a_valider_fiduciaire`` — la liste EXPLICITE de ce qui reste à la charge
      du fiduciaire humain (la validation légale elle-même).

    NE modifie rien ; idempotent ; deux appels successifs donnent le même
    résultat pour un plan inchangé. Aucun prix d'achat / marge (le module n'en
    stocke pas).
    """
    plan = _plan_comptable_structure(company)
    reference = plan_cgnc_reference()
    anomalies = controles_coherence_cgnc(company)

    nb_comptes = sum(len(b['comptes']) for b in plan.values())
    comptes_par_classe_ = {
        classe: len(bucket['comptes'])
        for classe, bucket in sorted(plan.items())
    }
    par_severite = {'bloquant': 0, 'avertissement': 0, 'info': 0}
    for anomalie in anomalies:
        par_severite[anomalie['severite']] = (
            par_severite.get(anomalie['severite'], 0) + 1)

    numeros_existants = {
        c['numero'] for bucket in plan.values() for c in bucket['comptes']}
    ref_total = len(_COMPTES_CGNC)
    ref_presents = sum(
        1 for entry in _COMPTES_CGNC if entry[0] in numeros_existants)

    synthese = {
        'company': company.nom,
        'company_slug': company.slug,
        'genere_le': timezone.now().isoformat(),
        'nb_comptes': nb_comptes,
        'comptes_par_classe': comptes_par_classe_,
        'anomalies_par_severite': par_severite,
        'nb_anomalies': len(anomalies),
        'reference_cgnc_couverte': ref_presents,
        'reference_cgnc_totale': ref_total,
        'pret_a_transmettre': par_severite['bloquant'] == 0,
    }

    a_valider_fiduciaire = [
        "Validation LÉGALE finale du plan et du format CGNC : acte réservé à un "
        "fiduciaire / expert-comptable inscrit à l'Ordre (non automatisable).",
        "Confirmer l'adéquation du plan aux spécificités de l'activité "
        "(comptes sectoriels solaire/BTP, sous-comptes analytiques éventuels).",
        "Arbitrer les avertissements de sens/cohérence signalés ci-dessus.",
        "Valider le rattachement des comptes de tiers et le lettrage.",
        "Attester la conformité des états de synthèse (CPC, Bilan, ESG, ETIC) "
        "au moment de la liasse fiscale.",
    ]

    return {
        'synthese': synthese,
        'plan_comptable': plan,
        'reference_cgnc': reference,
        'controles': anomalies,
        'a_valider_fiduciaire': a_valider_fiduciaire,
    }
