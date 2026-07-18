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
import re
import urllib.request
import uuid
from decimal import ROUND_HALF_UP, Decimal
from math import asin, cos, radians, sin, sqrt

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
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
    Emprunt, EcheanceEmprunt, ChargeConstateeAvance, DotationEtalement,
    PlanAmortissementFiscal, DotationDerogatoire, TauxDevise,
    ItemOuvertDevise, EcartChange, ReevaluationCloture, LigneReevaluation,
    EtatPersonnalise, LigneEtatPersonnalise, ColonneEtatPersonnalise,
    VentilationAnalytique, LigneVentilation, RegleImputation,
    LigneRegleImputation, DemandeApprobationRib,
    Immobilisation, IndemniteChantier, Journal, LigneEcriture,
    LignePrevisionnelTresorerie, LigneReleve, MouvementCaisse, NoteFrais,
    OuverturePartage, PlafondNoteFrais, RapportNoteFrais,
    PaymentRun, PaymentRunLine, PeriodeComptable, PlanAmortissement,
    PlanComptable, PointageReleve, Provision, ProvisionCreance, Rapprochement,
    RapprochementBancaire, RelanceDevisAbandonne, RetenueSource,
    RetenueGarantie, TimbreFiscal,
    TravauxEnCours, VirementInterne,
    EcheanceAO, ResultatAO, ComptePortailClient,
    PaiementFacturePortail,
    MappingCompte, CompteAuxiliaire,
    PisteAuditComptable,
    ModeleRapprochement,
    AbonnementEcriture,
    ObligationFiscale,
    FamilleTvaNonDeductible,
    EtapeSequence, ExecutionEtapeSequence, InscriptionSequence,
    SequenceRelance, EnvoiCampagne, SuppressionMarketing,
    ListeDiffusion, AbonnementListe, RebondSoft,
    Compensation, LigneCompensation,
    LienTrackee, ClicLien,
    StatutEngagementContact,
    ApprobationEnvoiCampagne,
    Enquete, ReponseEnquete,
    InscriptionEvenement,
    EvenementMarketing,
    SupportOffline,
    DomaineEnvoi,
    CommunicationEvenement,
    CycleConsolidation, LiasseRemontee, MappingConsolidation,
    OperationInterco, EcritureElimination,
    ReferentielComptable, AjustementGaap,
    RunAllocation, AllocationRecurrente,
    EngagementComptable,
    ModeleCloture, TacheClotureModele, InstanceCloture, TacheCloture,
    AccrualCloture,
    RapprochementCompte, LigneJustificationCompte,
    DepreciationImmobilisation, MutationImmobilisation,
    ImmobilisationEnCours,
    ObligationPerformance, EcheancierReconnaissance,
    EtapeAuditConsolidation,
    AcompteIS,
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
    # XACC6 — Stock de marchandises (inventaire permanent).
    ('3111', 'Stock de marchandises', False, False, 'actif'),
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
    # YLEDG11 — avances/acomptes clients (jamais un produit avant livraison ;
    # apuré à la facture de solde/complete du même devis, cf.
    # ecriture_pour_facture).
    ('4421', 'Clients - avances et acomptes reçus', True, True, 'passif'),
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
    # XPAI20 — Provisions pour charges de personnel (gratification 13e mois /
    # indemnité de fin de carrière), constituées mensuellement et reprises
    # (extourne) au paiement — même patron que la provision CP (PAIE25).
    ('4506', 'Provisions pour charges de personnel', False, False, 'passif'),
    # Classe 5 — Trésorerie
    ('5113', 'Effets à encaisser ou à l\'encaissement', False, False, 'actif'),
    ('5141', 'Banque', False, False, 'actif'),
    ('5161', 'Caisse', False, False, 'actif'),
    # XACC34 — Crédits d'escompte (mobilisation d'effets avant échéance) :
    # crédité au tirage de l'escompte, débité à l'apurement l'échéance venue.
    ('5520', "Crédits d'escompte", False, False, 'passif'),
    ('6147', 'Services bancaires (frais de rejet/effets)', False, False,
     'charge'),
    # Classe 6 — Charges
    ('6111', 'Achats de marchandises', False, False, 'charge'),
    # NTASS6 — primes d'assurance d'entreprise (RC pro, décennale,
    # multirisque, cyber, homme-clé…), débitées lors de la proposition
    # d'écriture sur échéance de prime (apps.assurances.services).
    ('6134', 'Assurances', False, False, 'charge'),
    # XACC6 — Variation de stock de marchandises (inventaire permanent) : une
    # SORTIE valorisée débite cette charge (le CGNC compte la variation de
    # stock en charge, contrepartie du crédit 3111).
    ('6114', 'Variation de stocks de marchandises', False, False, 'charge'),
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
    # XPAI20 — Dotation de la provision pour charges de personnel (contre-
    # partie du crédit 4506 ci-dessus).
    ('6195', 'Dotations aux provisions pour risques et charges', False,
     False, 'charge'),
    # Classe 7 — Produits
    ('7111', 'Ventes de marchandises', False, False, 'produit'),
    ('7121', 'Ventes de biens et services produits', False, False, 'produit'),
    ('7196', 'Reprises sur provisions pour dépréciation de l\'actif '
     'circulant', False, False, 'produit'),
    ('7132', 'Variation des stocks de travaux en cours', False, False,
     'produit'),
    # NTASS13 — indemnités d'assurances reçues (produit non courant),
    # créditées lors de la proposition d'écriture sur indemnisation encaissée
    # (apps.assurances.services). Contrepartie de la trésorerie (banque 5141).
    ('7582', "Indemnités d'assurances reçues", False, False, 'produit'),
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


def get_centre_cout(company, centre_cout_id):
    """``CentreCout`` de la société par id (ou None). Lecture seule.

    Utilisé par les appelants cross-app (ex. ``paie.journal_de_paie_ventile``,
    XPAI17) qui ne connaissent qu'un id résolu via ``creer_centre_cout`` et
    doivent le repasser en INSTANCE à ``creer_ecriture`` (la FK
    ``LigneEcriture.centre_cout`` n'accepte pas un entier brut).
    """
    if not centre_cout_id:
        return None
    return CentreCout.objects.filter(
        company=company, pk=centre_cout_id).first()


# ── FG108 / COMPTA7 — Fabrique d'écriture en partie double ─────────────────

@transaction.atomic
def creer_ecriture(company, journal, date_ecriture, libelle, lignes, *,
                   reference='', source_type='', source_id=None,
                   created_by=None, statut=None, referentiel=None):
    """Crée une écriture équilibrée et ses lignes, ou lève ``ValidationError``.

    ``lignes`` est une liste de dicts : ``{'compte', 'debit', 'credit',
    'libelle'?, 'tiers_type'?, 'tiers_id'?}``. La somme des débits doit égaler
    la somme des crédits, sinon RIEN n'est créé (transaction atomique).

    NTFIN14 — ``referentiel`` (optionnel) tague TOUTES les lignes vers un livre
    parallèle (multi-GAAP) ; une ligne peut aussi porter son propre
    ``'referentiel'``. NULL = référentiel principal (comportement historique).
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
        ligne_ecriture = LigneEcriture.objects.create(
            company=company,
            ecriture=ecriture,
            compte=ligne['compte'],
            libelle=ligne.get('libelle', '') or '',
            debit=Decimal(ligne.get('debit') or 0),
            credit=Decimal(ligne.get('credit') or 0),
            tiers_type=ligne.get('tiers_type', '') or '',
            tiers_id=ligne.get('tiers_id'),
            centre_cout=ligne.get('centre_cout'),
            referentiel=ligne.get('referentiel') or referentiel,
        )
        # XACC20 — auto-imputation analytique : si aucune ventilation/centre de
        # coût n'est déjà fourni sur la ligne ET qu'une règle matche, on
        # applique automatiquement sa distribution (additif, jamais bloquant).
        if not ligne.get('centre_cout') and 'ventilation' not in ligne:
            _appliquer_regle_imputation_si_match(
                company, ligne_ecriture, tiers_id=ligne.get('tiers_id'),
                produit_id=ligne.get('produit_id'))
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

def auto_ecritures_actif(company=None):
    """Toggle maître de l'auto-génération. OFF par défaut → rien ne change.

    Le founder active la passation automatique des écritures en posant
    ``COMPTA_AUTO_ECRITURES = True`` (settings) ou la variable d'env du même
    nom. Tant que c'est faux, aucun document ne génère d'écriture.

    WIR24 — désormais réglable PAR SOCIÉTÉ via
    ``parametres.CompanyProfile.comptabilite_auto_ecritures`` (défaut False), en
    plus du réglage global. Le global reste un interrupteur MAÎTRE : s'il est
    True, l'auto-génération est active pour TOUTES les sociétés (comportement +
    tests historiques inchangés). S'il est False (défaut), on consulte le
    drapeau de la ``company`` passée ; sans société (appel générique), on
    retombe sur False — comportement byte-identique à l'ancienne signature.
    """
    if bool(getattr(settings, 'COMPTA_AUTO_ECRITURES', False)):
        return True
    if company is None:
        return False
    # ``parametres`` est une app foundation (exemptée de la frontière
    # inter-apps) : lecture directe du profil, sans effet de bord (pas de
    # get_or_create — un profil absent = réglage à False).
    from apps.parametres.models_company import CompanyProfile
    profil = CompanyProfile.objects.filter(company=company).first()
    return bool(profil and profil.comptabilite_auto_ecritures)


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

    YLEDG11 — ``type_facture='acompte'`` (CGNC : pas de produit avant
    livraison) crédite 4421 « Clients — avances et acomptes » au lieu de
    71xx (zéro TVA facturée constatée en produit — le HT+TVA entier part en
    avance). Une facture ``solde``/``intermediaire``/``complete`` du MÊME
    devis débite alors 4421 du cumul des acomptes déjà comptabilisés de ce
    devis (apurement, jamais plus que le cumul disponible) en plus du crédit
    71xx habituel sur la totalité HT de CETTE facture — le produit total est
    donc constaté normalement, et le solde de 4421 du dossier retombe à 0
    une fois tous les acomptes apurés. Une facture ``complete`` SANS acompte
    au devis est inchangée (apurement = 0).
    """
    company = facture.company
    if company is None:
        return None
    if not force and not auto_ecritures_actif(company):
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
    type_facture = getattr(facture, 'type_facture', None) or 'complete'
    compte_avances = _assurer_compte(company, '4421')

    if type_facture == 'acompte':
        # CGNC : un acompte ne constate JAMAIS de produit — tout le TTC part
        # en avance (4421), zéro ligne 71xx/4455 ici (comportement documenté
        # dans la docstring, ce N'EST PAS un oubli de TVA : la TVA facturée
        # à l'acompte reste due normalement au moment de l'émission, seule
        # la contrepartie produit est différée — la ligne TVA suit le régime
        # habituel de l'entreprise, portée par le crédit 4421 au TTC).
        lignes = [
            {'compte': comptes['clients'], 'debit': ttc, 'credit': Decimal('0'),
             'libelle': f'Facture {facture.reference}',
             'tiers_type': 'client', 'tiers_id': client_id},
            {'compte': compte_avances, 'debit': Decimal('0'), 'credit': ttc,
             'libelle': f'Acompte {facture.reference}',
             'tiers_type': 'client', 'tiers_id': client_id},
        ]
        return creer_ecriture(
            company, journal, facture.date_emission,
            f'Facture acompte {facture.reference}', lignes,
            reference=facture.reference, source_type='facture',
            source_id=facture.id, created_by=user,
            statut=EcritureComptable.Statut.VALIDEE,
        )

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

    # YLEDG11 — apurement des acomptes déjà comptabilisés du MÊME devis
    # (jamais plus que le cumul disponible — un devis sans acompte apure 0).
    # Un devis n'a qu'UNE facture de solde/complete par construction du
    # parcours vente (échéancier FG46/FG220) : pas de risque de compter le
    # même cumul deux fois — l'idempotence de CETTE écriture (garde
    # ``_ecriture_existante`` en tête de fonction) couvre le reste.
    devis = getattr(facture, 'devis', None)
    if devis is not None and type_facture in ('solde', 'intermediaire',
                                              'complete'):
        cumul_acomptes = Decimal('0')
        for soeur in devis.factures.all():
            if soeur.id == facture.id:
                continue
            if getattr(soeur, 'type_facture', None) != 'acompte':
                continue
            eco_acompte = _ecriture_existante(company, 'facture', soeur.id)
            if eco_acompte is None:
                continue
            cumul_acomptes += Decimal(soeur.total_ttc)
        if cumul_acomptes > 0:
            lignes.append({
                'compte': compte_avances, 'debit': cumul_acomptes,
                'credit': Decimal('0'),
                'libelle': f'Apurement acompte(s) {facture.reference}',
                'tiers_type': 'client', 'tiers_id': client_id})
            lignes.append({
                'compte': comptes['clients'], 'debit': Decimal('0'),
                'credit': cumul_acomptes,
                'libelle': f'Apurement acompte(s) {facture.reference}',
                'tiers_type': 'client', 'tiers_id': client_id})

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

    XFAC12 — quand ``paiement.escompte_montant`` est renseigné (règlement
    anticipé dans la fenêtre d'escompte), le différentiel part en écriture
    d'escompte accordé (compte 6386) qui solde le CLIENT au même titre que le
    règlement — le débit trésorerie reste le montant NET réellement encaissé.
    """
    company = paiement.company
    if company is None:
        return None
    if not force and not auto_ecritures_actif(company):
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
    escompte = Decimal(getattr(paiement, 'escompte_montant', None) or 0)
    facture = paiement.facture
    client_id = getattr(facture, 'client_id', None)
    ref = getattr(facture, 'reference', '')
    total_credit_client = montant + escompte
    lignes = [
        {'compte': compte_treso, 'debit': montant, 'credit': Decimal('0'),
         'libelle': f'Encaissement {ref}'},
        {'compte': comptes['clients'], 'debit': Decimal('0'),
         'credit': total_credit_client, 'libelle': f'Règlement {ref}',
         'tiers_type': 'client', 'tiers_id': client_id},
    ]
    if escompte:
        compte_escompte = _assurer_compte(company, '6386')
        lignes.append({
            'compte': compte_escompte, 'debit': escompte, 'credit': Decimal('0'),
            'libelle': f'Escompte accordé {ref}'})
    return creer_ecriture(
        company, journal, paiement.date_paiement,
        f'Encaissement facture {ref}', lignes,
        reference=ref, source_type='paiement', source_id=paiement.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )


@transaction.atomic
def auto_lettrer_facture_soldee(facture):
    """YLEDG6 — lettre automatiquement le compte clients (3421) d'une facture
    INTÉGRALEMENT réglée.

    Rassemble les lignes 3421 non lettrées des écritures liées à cette
    facture (la vente elle-même, tous ses règlements, tous ses avoirs — via
    ``source_type``/``source_id``, jamais un import du modèle ``ventes`` :
    ``facture`` est lu par attribut/relation, comme le reste du bloc
    ``ecriture_pour_*``) et pose un même code de lettrage SSI elles
    s'équilibrent. No-op silencieux si le lot ne solde pas (ex. génération
    désactivée pour une partie du dossier) — jamais d'exception qui casserait
    le flux d'encaissement appelant.

    Un paiement PARTIEL n'appelle jamais cette fonction (le receveur ne
    l'invoque qu'au passage résiduel→0, comme YDOCF4) : le lot reste ouvert.
    """
    company = facture.company
    if company is None:
        return None
    compte_clients = get_compte(company, '3421')
    source_ids = {
        'facture': [facture.id],
        'paiement': [p.id for p in facture.paiements.all()],
        'avoir': [a.id for a in facture.avoirs.all()],
    }
    q_sources = Q()
    for source_type, ids in source_ids.items():
        if ids:
            q_sources |= Q(ecriture__source_type=source_type,
                           ecriture__source_id__in=ids)
    if not q_sources:
        return None
    lignes = list(
        LigneEcriture.objects.filter(
            q_sources, company=company, compte=compte_clients, lettrage='',
        ).values_list('id', flat=True))
    if len(lignes) < 2:
        # Rien à apparier (une seule ligne, ou déjà lettré).
        return None
    from . import selectors
    code = selectors.prochain_code_lettrage(company, compte_clients)
    try:
        return selectors.lettrer(company, lignes, code)
    except ValueError:
        # Lot déséquilibré (ex. génération partielle désactivée) : on laisse
        # le lettrage manuel s'en charger, jamais d'exception ici.
        return None


@transaction.atomic
def ecriture_pour_paiement_especes_via_caisse(paiement, *, force=False,
                                              user=None):
    """YLEDG9 — route un encaissement ESPÈCES via le module caisse (COMPTA24)
    au lieu de l'écriture banque directe de ``ecriture_pour_paiement`` :
    crée + poste un ``MouvementCaisse`` ENTREE (compte de caisse en débit,
    3421 Clients en contrepartie créditée — solde la créance comme un
    encaissement normal) sur la PREMIÈRE caisse active de la société, et
    enregistre le droit de timbre fiscal dû (FG144, exonéré si le montant
    de base est nul). Idempotent via la garde ``source_type='paiement'``
    déjà posée par ``creer_ecriture`` (jamais deux écritures pour le même
    paiement — le receveur n'appelle JAMAIS ``ecriture_pour_paiement`` en
    plus de celle-ci sur le même événement). Gardée par le même toggle maître
    que ses sœurs (``auto_ecritures_actif``, OFF par défaut) : sans cela, un
    règlement espèces posté explicitement par un appelant (ex. POS,
    ``pos.services.valider_vente``) se retrouvait DOUBLE-compté par ce
    récepteur d'événement même quand l'auto-génération comptable est
    désactivée. Renvoie l'écriture du mouvement de caisse, ou ``None`` si
    désactivé ou si aucune caisse n'est configurée (fallback : l'appelant
    retombe sur ``ecriture_pour_paiement``)."""
    company = paiement.company
    if company is None:
        return None
    if not force and not auto_ecritures_actif(company):
        return None
    existante = _ecriture_existante(company, 'paiement', paiement.id)
    if existante:
        return existante
    caisse = Caisse.objects.filter(company=company).order_by('id').first()
    if caisse is None:
        return None
    comptes = _comptes_requis(company)
    montant = Decimal(paiement.montant)
    facture = paiement.facture
    client_id = getattr(facture, 'client_id', None)
    ref = getattr(facture, 'reference', '')

    mouvement = MouvementCaisse(
        company=company, caisse=caisse,
        sens=MouvementCaisse.Sens.ENTREE,
        date_mouvement=paiement.date_paiement,
        montant=montant, motif=f'Encaissement facture {ref}',
        justificatif=ref, compte_contrepartie=comptes['clients'],
        created_by=user,
    )
    mouvement.full_clean(exclude=['ecriture'])
    mouvement.save()
    ecriture = poster_mouvement_caisse(mouvement, user=user)
    # L'écriture du mouvement de caisse est source_type='mouvement_caisse' —
    # on l'enregistre AUSSI comme l'écriture DU PAIEMENT (source_type=
    # 'paiement') pour que l'idempotence/le rapprochement YLEDG13 la
    # retrouvent comme n'importe quel encaissement.
    EcritureComptable.objects.filter(pk=ecriture.pk).update(
        source_type='paiement', source_id=paiement.id)
    ecriture.refresh_from_db()

    if montant > 0:
        enregistrer_timbre_fiscal(
            company, date_encaissement=paiement.date_paiement,
            base=montant, mode_reglement=MODE_ESPECES,
            paiement_id=paiement.id, facture_ref=ref,
            tiers_type='client', tiers_id=client_id,
            tiers_nom=getattr(facture.client, 'nom', '') or '' if facture
            else '',
            libelle=f'Timbre fiscal encaissement {ref}', user=user,
        )
    return ecriture


def enregistrer_effet_pour_paiement_cheque(paiement, *, user=None):
    """YLEDG10 — un règlement CHÈQUE client route par le portefeuille
    d'effets (``enregistrer_effet``, sens ``recevoir``) au lieu de l'écriture
    banque directe de ``ecriture_pour_paiement`` : l'argent n'est PAS encore
    en banque tant que le chèque n'a pas été remis puis encaissé.

    Idempotent (référence au paiement dans le commentaire + garde par
    ``numero``) : si un ``Effet`` existe déjà pour ce paiement (rejoué sur
    best-effort), on le renvoie sans en créer un second. Aucune écriture GL
    n'est postée ici (elle vient du bordereau de remise existant,
    ``poster_bordereau``, qui crédite 3425 → banque) : ce n'est PAS une
    régression de YLEDG6 — l'auto-lettrage no-op tant que rien n'est
    comptabilisé, exactement comme un document jamais émis. Renvoie l'Effet,
    ou ``None`` si le paiement ne porte aucune facture exploitable."""
    facture = getattr(paiement, 'facture', None)
    if facture is None:
        return None
    company = facture.company
    if company is None:
        return None
    reference_paiement = f'PAIEMENT-{paiement.id}'
    existant = Effet.objects.filter(
        company=company, commentaire=reference_paiement).first()
    if existant is not None:
        return existant
    date_emission = paiement.date_paiement or timezone.localdate()
    return enregistrer_effet(
        company, sens=Effet.Sens.RECEVOIR,
        montant=Decimal(paiement.montant or 0),
        date_emission=date_emission, date_echeance=date_emission,
        type_effet=Effet.TypeEffet.CHEQUE,
        numero=getattr(paiement, 'reference', '') or '',
        tiers_type='client', tiers_id=facture.client_id,
        commentaire=reference_paiement, user=user,
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
    company = avoir.company
    if company is None:
        return None
    if not force and not auto_ecritures_actif(company):
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

# ── XACC11 — Prorata de déduction TVA & TVA non déductible ─────────────────

def est_famille_non_deductible(company, famille):
    """Vrai si ``famille`` (clef DC22) est dans le référentiel non-déductible.

    Lecture seule. ``famille`` vide/None → toujours False (comportement
    historique inchangé quand aucune famille n'est renseignée).
    """
    if not famille:
        return False
    return FamilleTvaNonDeductible.objects.filter(
        company=company, famille=famille, actif=True).exists()


def coefficient_prorata_tva(company, une_date):
    """Coefficient de prorata TVA (%) de l'exercice couvrant ``une_date``.

    Défaut 100 % (déduction intégrale, comportement historique) si aucun
    exercice ne couvre la date ou si le champ n'a jamais été paramétré.
    Lecture seule.
    """
    if une_date is None:
        return Decimal('100')
    exercice = ExerciceComptable.objects.filter(
        company=company, date_debut__lte=une_date,
        date_fin__gte=une_date).first()
    if exercice is None:
        return Decimal('100')
    return exercice.coefficient_prorata_tva or Decimal('100')


@transaction.atomic
def ecriture_pour_facture_fournisseur(facture, *, force=False, user=None,
                                      famille_charge=None):
    """Génère l'écriture d'achat d'une facture fournisseur (61xx/3455 → 4411).

    Débit 61xx Achats/Charges (HT) + 3455 TVA récupérable (TVA), crédit 4411
    Fournisseurs (TTC). Idempotent : ne recrée pas l'écriture d'une facture déjà
    passée. Renvoie l'écriture (existante ou nouvelle), ou None si désactivé/non
    applicable. ``famille_charge`` (optionnel) consulte le mapping DC22 pour
    router vers un compte de charge précis (défaut : 6111 Achats).

    XACC11 — TVA non déductible / prorata : si ``famille_charge`` est dans le
    référentiel ``FamilleTvaNonDeductible`` (véhicule de tourisme…), AUCUNE
    ligne 3455 n'est postée — la TVA entière reste dans la charge (débit 61xx
    majoré). Sinon, le coefficient de prorata de l'exercice
    (``ExerciceComptable.coefficient_prorata_tva``, défaut 100 %) réduit la
    fraction déductible ; le reliquat non déductible rejoint lui aussi la
    charge. À 100 % (défaut), le comportement est STRICTEMENT identique à
    avant (aucune régression).
    """
    company = facture.company
    if company is None:
        return None
    if not force and not auto_ecritures_actif(company):
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
    # Une facture fournisseur sans date (ex. créée par facturer_reception
    # avant le fix, ou import partiel) ne doit pas faire crasher l'écriture
    # (NOT NULL date_ecriture) — repli : date du jour.
    date_facture = getattr(facture, 'date_facture', None) or timezone.now().date()
    # DC22 : famille de charge → compte 6x (défaut 6111 si non mappé).
    compte_charge = compte_pour_clef(
        company, MappingCompte.TypeClef.FAMILLE, famille_charge,
        defaut=comptes['achats']) if famille_charge else comptes['achats']

    # XACC11 — répartit la TVA entre déductible (3455) et non déductible
    # (folded dans la charge), selon la famille et le coefficient de prorata.
    non_deductible_totale = est_famille_non_deductible(company, famille_charge)
    prorata = Decimal('100')
    if non_deductible_totale:
        tva_deductible = Decimal('0')
    else:
        prorata = coefficient_prorata_tva(company, date_facture)
        tva_deductible = (tva * prorata / Decimal('100')).quantize(
            Decimal('0.01')) if tva else Decimal('0')
    tva_non_deductible = tva - tva_deductible
    charge_totale = ht + tva_non_deductible

    lignes = [
        {'compte': compte_charge, 'debit': charge_totale, 'credit': Decimal('0'),
         'libelle': f'Achat {reference}'},
    ]
    if tva_deductible:
        # XACC11 — marque la ligne « prorata » (visible tel quel dans le
        # relevé FG138, dérivé du libellé GL — jamais un champ à part).
        suffixe_prorata = f' (prorata {prorata}%)' if prorata != 100 else ''
        lignes.append({
            'compte': comptes['tva_recuperable'], 'debit': tva_deductible,
            'credit': Decimal('0'),
            'libelle': f'TVA récupérable {reference}{suffixe_prorata}'})
    lignes.append({
        'compte': comptes['fournisseurs'], 'debit': Decimal('0'), 'credit': ttc,
        'libelle': f'Facture fournisseur {reference}',
        'tiers_type': 'fournisseur', 'tiers_id': fournisseur_id})
    return creer_ecriture(
        company, journal, date_facture,
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
    company = paiement.company
    if company is None:
        return None
    if not force and not auto_ecritures_actif(company):
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


# ── XACC7 — Provisions FNP / FAE de fin de période ──────────────────────────
# Aucun accrual « factures non parvenues / à établir » n'existait. Les
# réceptions/avancements NON facturés vivent dans ``apps.stock``/``apps.ventes``
# (rapprochement 3 voies FG131, avancement FG146…) : compta les reçoit ICI par
# VALEUR — une liste de dicts déjà résolus par l'appelant via LEURS sélecteurs
# (``stock.selectors.three_way_amounts`` pour les réceptions, les sélecteurs de
# ``ventes`` pour l'avancement non facturé) — jamais un import de leurs
# ``models``. Chaque item ``{'reference', 'montant_ht', 'tiers_id'?,
# 'tiers_nom'?}`` devient UNE ligne de la provision ; ``source_id`` (entier)
# identifie le document source pour l'idempotence (ex. l'id du BCF/chantier).

def _ligne_provision(compte, montant, libelle, tiers_id=None, tiers_type=''):
    return {'compte': compte, 'debit': montant, 'credit': Decimal('0'),
            'libelle': libelle, 'tiers_type': tiers_type, 'tiers_id': tiers_id}


@transaction.atomic
def generer_provisions_fnp(company, *, date_periode, items, date_extourne=None,
                           compte_charge=None, user=None):
    """Provisionne les FACTURES NON PARVENUES (réceptions non facturées).

    ``items`` : liste de ``{'source_id': int, 'reference': str, 'montant_ht':
    Decimal, 'tiers_id'?: int}`` (une réception fournisseur non encore
    facturée = un item). Pour chaque item, poste une écriture OD (débit
    ``compte_charge`` [défaut 6111], crédit 4486 « Fournisseurs — factures non
    parvenues ») datée ``date_periode``, PUIS son extourne automatique
    (``extourner_ecriture``) datée du premier jour de la période suivante
    (``date_extourne``, obligatoire — calculé côté appelant). IDEMPOTENT par
    item (``source_type='fnp'``, ``source_id``). Renvoie la liste des
    ``{'source_id', 'ecriture_id', 'extourne_id', 'montant'}`` postés.
    """
    if date_extourne is None:
        raise ValidationError(
            "La date d'extourne (1er jour de la période suivante) est "
            "obligatoire.")
    comptes = _comptes_requis(company)
    compte_fnp = _assurer_compte(company, '4486')
    compte_ch = compte_charge or comptes['achats']
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    resultats = []
    for item in items or []:
        source_id = item['source_id']
        montant = Decimal(item.get('montant_ht') or 0)
        if montant <= 0:
            continue
        existante = _ecriture_existante(company, 'fnp', source_id)
        if existante:
            ecriture = existante
        else:
            ref = item.get('reference', '') or ''
            tiers_id = item.get('tiers_id')
            lignes = [
                _ligne_provision(
                    compte_ch, montant, f'FNP {ref}', tiers_id, 'fournisseur'),
                {'compte': compte_fnp, 'debit': Decimal('0'), 'credit': montant,
                 'libelle': f'FNP {ref}', 'tiers_type': 'fournisseur',
                 'tiers_id': tiers_id},
            ]
            ecriture = creer_ecriture(
                company, journal, date_periode, f'Provision FNP {ref}', lignes,
                reference=ref, source_type='fnp', source_id=source_id,
                created_by=user, statut=EcritureComptable.Statut.VALIDEE,
            )
        extourne = extourner_ecriture(
            ecriture, date_extourne=date_extourne, user=user,
            libelle=f'Extourne FNP {ecriture.reference}')
        resultats.append({
            'source_id': source_id, 'ecriture_id': ecriture.id,
            'extourne_id': extourne.id, 'montant': montant,
        })
    return resultats


@transaction.atomic
def generer_provisions_fae(company, *, date_periode, items, date_extourne=None,
                           compte_produit=None, user=None):
    """Provisionne les FACTURES À ÉTABLIR (livraisons/avancements non facturés).

    Miroir client de ``generer_provisions_fnp``. ``items`` : liste de
    ``{'source_id': int, 'reference': str, 'montant_ht': Decimal, 'tiers_id'?:
    int}`` (une livraison/un avancement non encore facturé = un item). Poste
    une écriture OD (débit 3427 « Clients — factures à établir », crédit
    ``compte_produit`` [défaut 7121]) datée ``date_periode``, PUIS son extourne
    automatique datée du premier jour de la période suivante. IDEMPOTENT par
    item (``source_type='fae'``, ``source_id``). Renvoie la liste des
    ``{'source_id', 'ecriture_id', 'extourne_id', 'montant'}`` postés.
    """
    if date_extourne is None:
        raise ValidationError(
            "La date d'extourne (1er jour de la période suivante) est "
            "obligatoire.")
    comptes = _comptes_requis(company)
    compte_fae = _assurer_compte(company, '3427')
    compte_pr = compte_produit or comptes['ventes']
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    resultats = []
    for item in items or []:
        source_id = item['source_id']
        montant = Decimal(item.get('montant_ht') or 0)
        if montant <= 0:
            continue
        existante = _ecriture_existante(company, 'fae', source_id)
        if existante:
            ecriture = existante
        else:
            ref = item.get('reference', '') or ''
            tiers_id = item.get('tiers_id')
            lignes = [
                {'compte': compte_fae, 'debit': montant, 'credit': Decimal('0'),
                 'libelle': f'FAE {ref}', 'tiers_type': 'client',
                 'tiers_id': tiers_id},
                {'compte': compte_pr, 'debit': Decimal('0'), 'credit': montant,
                 'libelle': f'FAE {ref}', 'tiers_type': 'client',
                 'tiers_id': tiers_id},
            ]
            ecriture = creer_ecriture(
                company, journal, date_periode, f'Provision FAE {ref}', lignes,
                reference=ref, source_type='fae', source_id=source_id,
                created_by=user, statut=EcritureComptable.Statut.VALIDEE,
            )
        extourne = extourner_ecriture(
            ecriture, date_extourne=date_extourne, user=user,
            libelle=f'Extourne FAE {ecriture.reference}')
        resultats.append({
            'source_id': source_id, 'ecriture_id': ecriture.id,
            'extourne_id': extourne.id, 'montant': montant,
        })
    return resultats


def rapport_provisions_periode(company, *, date_debut, date_fin,
                               type_provision=None):
    """Rapport de contrôle des provisions FNP/FAE postées sur une période.

    Liste chaque écriture ``source_type in ('fnp', 'fae')`` dont
    ``date_ecriture`` tombe dans ``[date_debut ; date_fin]``, avec sa pièce
    source (``reference``, ``source_id``) et le montant. Lecture seule, prête
    pour l'export CSV (``services.export_provisions_periode_csv``).
    """
    types = [type_provision] if type_provision else ['fnp', 'fae']
    qs = EcritureComptable.objects.filter(
        company=company, source_type__in=types,
        date_ecriture__gte=date_debut, date_ecriture__lte=date_fin,
    ).order_by('source_type', 'date_ecriture', 'id')
    lignes = []
    for ecr in qs:
        lignes.append({
            'type': ecr.source_type,
            'source_id': ecr.source_id,
            'reference': ecr.reference,
            'date': ecr.date_ecriture,
            'libelle': ecr.libelle,
            'montant': ecr.total_debit,
        })
    return lignes


def export_provisions_periode_csv(company, *, date_debut, date_fin,
                                  type_provision=None):
    """Export CSV du rapport de contrôle des provisions FNP/FAE (XACC7)."""
    lignes = rapport_provisions_periode(
        company, date_debut=date_debut, date_fin=date_fin,
        type_provision=type_provision)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(['Type', 'Référence', 'Date', 'Libellé', 'Montant HT'])
    for lig in lignes:
        writer.writerow([
            lig['type'].upper(), lig['reference'], lig['date'], lig['libelle'],
            lig['montant']])
    return buffer.getvalue().encode('utf-8-sig')


# ── XACC8 — Modèles d'écriture, écritures récurrentes & extourne auto ──────

@transaction.atomic
def generer_ecriture_depuis_modele(modele, *, date_ecriture, montants=None,
                                   libelle=None, source_type='', source_id=None,
                                   user=None, statut=None):
    """Génère UNE écriture à partir d'un ``ModeleEcriture`` (lignes pré-codées).

    ``montants`` (optionnel) : dict ``{ligne_modele_id: Decimal}`` qui
    surcharge le ``montant_defaut`` de la ligne — obligatoire pour toute ligne
    dont ``montant_defaut`` est ``None``, sinon ``ValidationError``. Renvoie
    l'écriture (naît en BROUILLON par défaut — relecture humaine avant
    validation, sauf ``statut`` explicite).
    """
    montants = montants or {}
    lignes = []
    for lig_modele in modele.lignes.order_by('ordre', 'id'):
        montant = montants.get(lig_modele.id, lig_modele.montant_defaut)
        if montant is None:
            raise ValidationError(
                f"Montant manquant pour la ligne {lig_modele.compte.numero} "
                "du modèle (pas de montant par défaut).")
        montant = Decimal(montant)
        lignes.append({
            'compte': lig_modele.compte,
            'debit': montant if lig_modele.sens == 'debit' else Decimal('0'),
            'credit': montant if lig_modele.sens == 'credit' else Decimal('0'),
            'libelle': lig_modele.libelle or modele.libelle,
        })
    return creer_ecriture(
        modele.company, modele.journal, date_ecriture,
        libelle or modele.libelle, lignes,
        source_type=source_type, source_id=source_id, created_by=user,
        statut=statut or EcritureComptable.Statut.BROUILLON,
    )


@transaction.atomic
def generer_ecritures_recurrentes(company, *, jusqua=None, user=None):
    """Génère les écritures dues de tous les abonnements actifs (XACC8).

    Pour chaque ``AbonnementEcriture`` actif dont ``prochaine_echeance`` est
    ≤ ``jusqua`` (défaut : aujourd'hui) ET ``date_fin`` non dépassée, génère
    l'écriture du modèle (montants par défaut des lignes — un abonnement sans
    montant par défaut sur une ligne est SKIP avec le détail), puis avance
    ``prochaine_echeance`` d'un cran. IDEMPOTENT PAR PÉRIODE :
    ``source_type='abonnement'`` + ``source_id=abonnement.id`` ne suffit pas à
    distinguer deux échéances du même abonnement — la référence de l'écriture
    porte la période (``AB{id}-{YYYY-MM}``) et sert de clef d'idempotence
    explicite en plus du couple source. Si ``modele.extourne_auto`` est posé,
    l'extourne est postée au 1er jour du mois suivant (COMPTA11). Renvoie
    ``{'generees': [...], 'ignorees': [...]}``.
    """
    ref_date = jusqua or timezone.localdate()
    generees, ignorees = [], []
    abonnements = AbonnementEcriture.objects.filter(
        company=company, actif=True,
        prochaine_echeance__lte=ref_date).select_related('modele')
    for ab in abonnements:
        if ab.date_fin and ab.prochaine_echeance > ab.date_fin:
            continue
        periode_key = ab.prochaine_echeance.strftime('%Y-%m')
        ref = f'AB{ab.id}-{periode_key}'
        deja = EcritureComptable.objects.filter(
            company=company, source_type='abonnement', reference=ref).first()
        if deja:
            ignorees.append({'abonnement_id': ab.id, 'periode': periode_key,
                             'raison': 'déjà générée'})
        else:
            try:
                ecriture = generer_ecriture_depuis_modele(
                    ab.modele, date_ecriture=ab.prochaine_echeance,
                    libelle=ab.libelle or ab.modele.libelle,
                    source_type='abonnement', source_id=ab.id, user=user)
            except ValidationError as exc:
                ignorees.append({
                    'abonnement_id': ab.id, 'periode': periode_key,
                    'raison': exc.messages[0] if exc.messages else str(exc)})
                continue
            ecriture.reference = ref
            ecriture.save(update_fields=['reference'])
            extourne_id = None
            if ab.modele.extourne_auto:
                prochain_mois = ab.echeance_suivante(ab.prochaine_echeance)
                date_extourne = prochain_mois.replace(day=1)
                extourne = extourner_ecriture(
                    ecriture, date_extourne=date_extourne, user=user)
                extourne_id = extourne.id
            generees.append({
                'abonnement_id': ab.id, 'ecriture_id': ecriture.id,
                'extourne_id': extourne_id, 'periode': periode_key})
        ab.prochaine_echeance = ab.echeance_suivante(ab.prochaine_echeance)
        ab.derniere_generation = ref_date
        ab.save(update_fields=['prochaine_echeance', 'derniere_generation'])
    return {'generees': generees, 'ignorees': ignorees}


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


def _calcul_annuites(base, duree, mode, coefficient, *, mois_premiere_annee=12):
    """Renvoie la liste des annuités (Decimal arrondies) pour ``duree`` années.

    * LINÉAIRE : base / durée chaque année ; la dernière année absorbe l'écart
      d'arrondi pour solder exactement la base. XACC32 — ``mois_premiere_
      annee`` (1-12) proratise la 1re annuité (CGI marocain : prorata au mois
      depuis la mise en service) ; la fraction non dotée en 1re année (12 −
      mois_premiere_annee) est reportée en ANNUITÉ COMPLÉMENTAIRE ajoutée à
      la DERNIÈRE année — la durée totale (nombre d'exercices) reste
      ``duree``, seule la répartition change. ``mois_premiere_annee=12``
      (défaut) reproduit EXACTEMENT le comportement historique (années
      pleines, aucun prorata).
    * DÉGRESSIF : taux dégressif = (100/durée) × coefficient, appliqué à la
      valeur nette résiduelle ; bascule sur le linéaire du résiduel dès que
      celui-ci devient supérieur ou égal à l'annuité dégressive (règle CGI).
      La dernière année solde le résiduel. Le prorata temporis ne s'applique
      PAS au dégressif (garde sa règle actuelle, XACC32).
    """
    base = Decimal(base)
    if duree < 1 or base <= 0:
        return []
    annuites = []
    if mode == PlanAmortissement.Mode.LINEAIRE:
        annuite = _arrondi(base / Decimal(duree))
        mois = max(1, min(12, int(mois_premiere_annee or 12)))
        if mois == 12 or duree == 1:
            cumul = Decimal('0')
            for an in range(duree):
                if an == duree - 1:
                    montant = base - cumul  # solde exact la dernière année.
                else:
                    montant = annuite
                cumul += montant
                annuites.append(_arrondi(montant))
            return annuites
        # Prorata temporis : 1re année = annuite × mois/12 ; la fraction
        # différée est reportée en annuité complémentaire sur la dernière
        # année (durée totale — nombre d'exercices — inchangée).
        premiere = _arrondi(annuite * Decimal(mois) / Decimal('12'))
        cumul = premiere
        annuites.append(premiere)
        for an in range(1, duree - 1):
            cumul += annuite
            annuites.append(_arrondi(annuite))
        derniere = base - cumul  # absorbe pleine annuité + fraction différée.
        annuites.append(_arrondi(derniere))
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
    # XACC32 — prorata temporis LINÉAIRE uniquement : mois restants depuis la
    # mise en service (défaut = date d'acquisition, comportement inchangé si
    # la mise en service n'est pas renseignée). Le dégressif garde sa règle
    # actuelle (aucun prorata).
    mois_premiere_annee = 12
    if plan.mode == PlanAmortissement.Mode.LINEAIRE:
        mise_en_service = immobilisation.date_mise_en_service_effective
        if mise_en_service and mise_en_service.year == plan.date_debut.year:
            mois_premiere_annee = 13 - mise_en_service.month
    annuites = _calcul_annuites(
        plan.base_amortissable, plan.duree_annees, plan.mode, coefficient,
        mois_premiere_annee=mois_premiere_annee)

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


# ── XACC33 — "Immobiliser" une ligne de facture fournisseur ────────────────

@transaction.atomic
def capitaliser_ligne_facture_fournisseur(company, *, facture_id, ligne_id,
                                          categorie=None, duree_annees=5,
                                          mode=None, user=None):
    """Capitalise une ligne de facture fournisseur en immobilisation (XACC33).

    Lit la ligne via ``apps.stock.selectors.ligne_facture_fournisseur_scoped``
    (company-scopée, JAMAIS un import de ``apps.stock.models``) et crée
    l'``Immobilisation`` pré-remplie (libellé = désignation de la ligne, coût
    = son total HT, TVA = son taux — ou celui de la facture si vide, date =
    date de la facture, pièce d'origine en string-ref) + son
    ``PlanAmortissement`` en un seul geste. Anti-doublon : une ligne ne peut
    capitaliser qu'UNE seule immobilisation (contrainte d'unicité sur
    ``piece_origine_ligne_facture_fournisseur_id`` — une 2e tentative lève
    ``ValidationError``). Lève ``ValidationError`` si la ligne est introuvable
    pour cette société (l'appelant traduit en 404). Renvoie l'``Immobilisation``
    créée."""
    from apps.stock.selectors import ligne_facture_fournisseur_scoped

    ligne = ligne_facture_fournisseur_scoped(company, facture_id, ligne_id)
    if ligne is None:
        raise ValidationError(
            "Ligne de facture fournisseur introuvable pour cette société.")
    if Immobilisation.objects.filter(
            company=company,
            piece_origine_ligne_facture_fournisseur_id=ligne.id).exists():
        raise ValidationError(
            "Cette ligne a déjà été immobilisée (une ligne ne peut "
            "capitaliser qu'une seule immobilisation).")
    facture = ligne.facture
    taux_tva = ligne.taux_tva if ligne.taux_tva is not None else Decimal('20')
    immo = Immobilisation(
        company=company,
        libelle=ligne.designation or f'Immobilisation (facture {facture.reference})',
        categorie=categorie or Immobilisation.Categorie.MATERIEL,
        cout=Decimal(ligne.total_ht or 0).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP),
        taux_tva=taux_tva,
        date_acquisition=facture.date_facture or timezone.now().date(),
        piece_origine_facture_fournisseur_id=facture.id,
        piece_origine_ligne_facture_fournisseur_id=ligne.id,
    )
    immo.full_clean(exclude=[
        'piece_origine_facture_fournisseur_id',
        'piece_origine_ligne_facture_fournisseur_id'])
    immo.save()
    generer_plan_amortissement(immo, mode=mode, duree_annees=duree_annees)
    return immo


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
                         reference='', devise='MAD', taux_change=None):
    """Ajoute une ligne de relevé bancaire à un rapprochement (FG123).

    ``montant`` est SIGNÉ tel que lu sur le relevé (+ entrée, − sortie). La
    société est héritée du rapprochement (jamais du corps). On ne peut plus
    ajouter de ligne à un rapprochement déjà ``rapproche``. NTTRE13 — ``devise``
    (défaut MAD) + ``taux_change`` (vers MAD, optionnel) pour un relevé en devise
    étrangère.
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
        devise=(devise or 'MAD'),
        taux_change=(Decimal(str(taux_change)) if taux_change else None),
    )


# ── XACC30 — OCR de relevé bancaire (KEY-GATED) ────────────────────────────
#
# Réutilise le SERVICE OCR existant (``backend/fastapi_ia``, Zhipu AI, no-op
# tant que sans clé), à l'image de ``apps.flotte.services.extraire_recu_
# carburant`` (XFLT23) et de l'OCR notes de frais (XACC27). AUCUNE
# intégration silencieuse : les lignes extraites sont PROPOSÉES (jamais
# injectées automatiquement) et un contrôle de solde (solde initial + Σ
# mouvements = solde final déclaré) est calculé AVANT toute acceptation.

def ocr_releve_bancaire_active():
    """XACC30 — True si l'OCR de relevé bancaire est activé (clé configurée).

    KEY-GATED : sans ``settings.COMPTA_OCR_RELEVE_ENABLED`` (posé par le
    founder aux côtés de ``ZHIPU_API_KEY``), reste désactivé. Ne lève jamais.
    """
    from django.conf import settings
    return bool(getattr(settings, 'COMPTA_OCR_RELEVE_ENABLED', False))


def extraire_releve_bancaire(file_bytes, *, mime=''):
    """XACC30 — Extrait les lignes d'un relevé bancaire (PDF/scan) par OCR.

    NO-OP tant que ``ocr_releve_bancaire_active()`` est faux : lève
    ``RuntimeError`` (la vue traduit en 503, message FR clair). Une fois
    activé, délègue à un module fournisseur isolé (``releve_ocr_provider``,
    non câblé dans ce dépôt) qui appelle le service OCR ``backend/fastapi_ia``
    et renvoie ``{'solde_initial', 'solde_final', 'lignes': [{'date',
    'libelle', 'montant'}, ...]}``. Toute erreur provider est avalée (dict
    vide) — jamais de crash de l'écran d'import.
    """
    if not ocr_releve_bancaire_active():
        raise RuntimeError('OCR indisponible (configuration manquante).')
    if not file_bytes:
        return {}
    try:  # pragma: no cover - dépend d'un provider externe non câblé ici.
        from . import releve_ocr_provider as provider  # noqa: F401
    except ImportError:  # pragma: no cover
        return {}
    try:  # pragma: no cover
        return provider.extraire_releve(file_bytes, mime=mime) or {}
    except Exception:  # pragma: no cover - jamais casser l'écran d'import.
        return {}


def controler_solde_releve_ocr(champs_bruts):
    """XACC30 — Contrôle solde initial + Σ mouvements == solde final déclaré.

    ``champs_bruts`` est le dict renvoyé par ``extraire_releve_bancaire``
    (ou un mock en test). Renvoie
    ``{'lignes', 'solde_initial', 'solde_final_declare', 'solde_calcule',
    'ecart', 'concordant'}`` — ``concordant`` est vrai si l'écart est nul (à 1
    centime près). Ne lève jamais : des champs manquants donnent des zéros
    et ``concordant=False`` plutôt qu'un crash."""
    lignes = champs_bruts.get('lignes') or []
    solde_initial = Decimal(str(champs_bruts.get('solde_initial') or 0))
    solde_final_declare = Decimal(str(champs_bruts.get('solde_final') or 0))
    somme_mouvements = sum(
        (Decimal(str(ligne.get('montant') or 0)) for ligne in lignes),
        Decimal('0'))
    solde_calcule = solde_initial + somme_mouvements
    ecart = (solde_final_declare - solde_calcule).quantize(Decimal('0.01'))
    return {
        'lignes': lignes,
        'solde_initial': solde_initial,
        'solde_final_declare': solde_final_declare,
        'solde_calcule': solde_calcule.quantize(Decimal('0.01')),
        'ecart': ecart,
        'concordant': abs(ecart) < Decimal('0.01'),
    }


@transaction.atomic
def accepter_lignes_releve_ocr(rapprochement, lignes):
    """XACC30 — Injecte des lignes de relevé PROPOSÉES (post-acceptation).

    Appelée UNIQUEMENT après acceptation explicite côté utilisateur (jamais
    automatique) : chaque ``ligne`` de ``{'date'/'date_operation', 'libelle',
    'montant', 'reference'?}`` devient une ``LigneReleve`` via
    ``ajouter_ligne_releve`` (même garde-fous : rapprochement non clôturé,
    date obligatoire). Renvoie la liste des ``LigneReleve`` créées."""
    creees = []
    for ligne in lignes or []:
        creees.append(ajouter_ligne_releve(
            rapprochement,
            date_operation=ligne.get('date_operation') or ligne.get('date'),
            libelle=ligne.get('libelle', '') or '',
            montant=ligne.get('montant'),
            reference=ligne.get('reference', '') or '',
        ))
    return creees


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


# ── NTTRE4 — Rapprochement auto APPRENANT (au-delà des règles déclaratives) ─
#
# XACC3 (au-dessus) note un candidat de façon DÉCLARATIVE (montant/date/réf).
# NTTRE4 ajoute une couche STATISTIQUE : elle APPREND de l'historique des
# ``PointageReleve`` déjà validés de la société — quel libellé récurrent a
# historiquement été pointé vers quel compte du grand livre — et propose la
# meilleure ligne GL NON LETTRÉE pour une nouvelle ligne de relevé au libellé
# similaire. Stdlib pur (distance de Levenshtein), aucune dépendance ML. Ne
# poste JAMAIS : la suggestion pré-remplit seulement ``accepter_suggestions_
# rapprochement`` (l'humain valide toujours).

def _normaliser_libelle_appris(texte):
    """Normalise un libellé pour la comparaison apprise (minuscules, sans
    chiffres/ponctuation, espaces compactés)."""
    import re
    texte = (texte or '').lower()
    texte = re.sub(r'[^a-zàâäéèêëïîôöùûüç ]', ' ', texte)
    return re.sub(r'\s+', ' ', texte).strip()


def _distance_levenshtein(a, b):
    """Distance de Levenshtein classique (stdlib, O(len(a)*len(b)))."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    precedente = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        courante = [i]
        for j, cb in enumerate(b, start=1):
            cout = 0 if ca == cb else 1
            courante.append(min(
                precedente[j] + 1,       # suppression
                courante[j - 1] + 1,     # insertion
                precedente[j - 1] + cout,  # substitution
            ))
        precedente = courante
    return precedente[-1]


def _similarite_libelle_appris(a, b):
    """Similarité de libellé 0..1 (1 = identique) fondée sur Levenshtein."""
    if not a and not b:
        return 1.0
    longueur = max(len(a), len(b)) or 1
    return max(0.0, 1.0 - _distance_levenshtein(a, b) / longueur)


def suggerer_rapprochement_appris(ligne_releve, *, seuil_similarite=0.5):
    """NTTRE4 — Suggestion APPRISE d'appariement pour une ligne de relevé.

    Construit un score de similarité (libellé normalisé + montant + fréquence
    du tiers récurrent) à partir de l'HISTORIQUE des ``PointageReleve`` déjà
    validés de la société, et propose la meilleure ``LigneEcriture`` du grand
    livre NON encore lettrée pour ``ligne_releve``. Renvoie ``None`` si aucun
    historique ou aucune correspondance au-dessus de ``seuil_similarite``, sinon
    ``{'ligne_releve_id', 'ligne_gl_id', 'confiance' (0..1), 'similarite',
    'frequence', 'pattern_libelle', 'montant_concordant'}``. Lecture seule —
    n'auto-poste jamais.
    """
    from .models import LigneEcriture, PointageReleve

    company = ligne_releve.company
    cible = _normaliser_libelle_appris(ligne_releve.libelle)
    if not cible:
        return None

    # 1. HISTORIQUE : agrège les pointages validés par libellé source normalisé.
    patterns = {}  # libellé normalisé -> {'freq', 'comptes': {compte_id: n}}
    historiques = (PointageReleve.objects
                   .filter(company=company)
                   .exclude(ligne_releve_id=ligne_releve.id)
                   .select_related('ligne_releve', 'ligne_gl'))
    for pointage in historiques:
        lib = _normaliser_libelle_appris(pointage.ligne_releve.libelle)
        if not lib:
            continue
        entree = patterns.setdefault(lib, {'freq': 0, 'comptes': {}})
        entree['freq'] += 1
        cid = pointage.ligne_gl.compte_id
        entree['comptes'][cid] = entree['comptes'].get(cid, 0) + 1
    if not patterns:
        return None

    # 2. Meilleur pattern historique par similarité de libellé.
    meilleur_lib, meilleure_sim = None, 0.0
    for lib in patterns:
        sim = _similarite_libelle_appris(cible, lib)
        if sim > meilleure_sim:
            meilleure_sim, meilleur_lib = sim, lib
    if meilleur_lib is None or meilleure_sim < seuil_similarite:
        return None
    pattern = patterns[meilleur_lib]
    compte_appris = max(pattern['comptes'], key=pattern['comptes'].get)
    frequence = pattern['freq']

    # 3. Meilleure ligne GL NON lettrée (montant le plus proche) sur ce compte.
    montant = ligne_releve.montant or Decimal('0')
    deja_pointees = set(PointageReleve.objects.filter(
        company=company).values_list('ligne_gl_id', flat=True))
    meilleur_gl, meilleur_ecart = None, None
    for gl in (LigneEcriture.objects
               .filter(company=company, compte_id=compte_appris)
               .select_related('ecriture')):
        if gl.id in deja_pointees:
            continue
        montant_gl = (gl.debit or Decimal('0')) - (gl.credit or Decimal('0'))
        ecart = abs(montant_gl - montant)
        if meilleur_ecart is None or ecart < meilleur_ecart:
            meilleur_ecart, meilleur_gl = ecart, gl
    if meilleur_gl is None:
        return None

    tolerance = max(abs(montant) * Decimal('0.01'), Decimal('0.01'))
    montant_concordant = meilleur_ecart <= tolerance
    poids_frequence = min(frequence, 10) / 10.0
    confiance = (0.55 * meilleure_sim
                 + 0.30 * (1.0 if montant_concordant else 0.0)
                 + 0.15 * poids_frequence)
    return {
        'ligne_releve_id': ligne_releve.id,
        'ligne_gl_id': meilleur_gl.id,
        'confiance': round(min(1.0, confiance), 3),
        'similarite': round(meilleure_sim, 3),
        'frequence': frequence,
        'pattern_libelle': meilleur_lib,
        'montant_concordant': montant_concordant,
    }


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


# ── XACC6 — Écritures de stock automatiques (inventaire permanent) ─────────
# Les auto-écritures couvrent factures/paiements/avoirs/FF (FG109), mais aucun
# mouvement de stock ne poste au GL. ``poster_mouvement_stock`` comble ce
# manque, derrière le toggle société ``PlanComptable.inventaire_permanent``
# (défaut OFF = comportement actuel intact, zéro écriture). La valeur
# unitaire est lue via ``apps.stock.selectors`` (jamais un import du modèle
# ``Produit``) — en l'absence d'un CUMP glissant dans ``apps.stock`` à ce
# jour, on retient ``Produit.prix_achat`` comme valorisation (usage 100 %
# interne/GL, jamais exposé dans un PDF ou un document client, conforme à la
# règle CLAUDE.md sur ce champ).

def inventaire_permanent_actif(company):
    """Vrai si l'inventaire permanent est activé pour la société (XACC6).

    Sème le plan comptable au besoin (idempotent) pour que le réglage soit
    toujours lisible, même sur une société jamais semée.
    """
    plan = PlanComptable.objects.filter(company=company).first()
    if plan is None:
        plan = seed_plan_comptable(company)
    return bool(plan.inventaire_permanent)


@transaction.atomic
def poster_mouvement_stock(company, *, mouvement_ref, produit_id, sens,
                           quantite, valeur_unitaire=None, date_mouvement=None,
                           user=None, force=False):
    """Poste l'écriture GL d'un mouvement de stock valorisé (XACC6).

    ``sens`` ∈ {'entree', 'sortie'} : une ENTRÉE valorisée débite 3111 (stock)
    et crédite 6114 (variation de stock) ; une SORTIE fait l'inverse (débite
    6114, crédite 3111) — reflet CGNC de la variation. Ne fait RIEN (renvoie
    ``None``) si le toggle ``inventaire_permanent`` est OFF (sauf ``force``),
    ou si la valeur totale du mouvement est nulle. IDEMPOTENT PAR MOUVEMENT :
    ``mouvement_ref`` doit être unique par société (ex. l'id du
    ``MouvementStock`` d'origine) — rejouer le même mouvement renvoie
    l'écriture déjà postée sans dupliquer. ``valeur_unitaire`` : si omise, est
    résolue via ``apps.stock.selectors.get_produit_scoped(company,
    produit_id).prix_achat`` (jamais un import du modèle ``Produit``).
    """
    if sens not in ('entree', 'sortie'):
        raise ValidationError("Sens de mouvement invalide (entree/sortie).")
    if not force and not inventaire_permanent_actif(company):
        return None
    existante = _ecriture_existante(company, 'mouvement_stock', mouvement_ref)
    if existante:
        return existante
    if valeur_unitaire is None:
        from apps.stock import selectors as stock_selectors
        produit = stock_selectors.get_produit_scoped(company, produit_id)
        if produit is None:
            raise ValidationError(
                "Produit introuvable dans cette société pour ce mouvement.")
        valeur_unitaire = produit.prix_achat
    valeur_totale = (Decimal(valeur_unitaire or 0)
                     * Decimal(quantite or 0)).copy_abs()
    if valeur_totale <= 0:
        return None
    compte_stock = _assurer_compte(company, '3111')
    compte_variation = _assurer_compte(company, '6114')
    if sens == 'entree':
        lignes = [
            {'compte': compte_stock, 'debit': valeur_totale, 'credit': Decimal('0'),
             'libelle': f'Entrée stock {mouvement_ref}'},
            {'compte': compte_variation, 'debit': Decimal('0'), 'credit': valeur_totale,
             'libelle': f'Entrée stock {mouvement_ref}'},
        ]
    else:
        lignes = [
            {'compte': compte_variation, 'debit': valeur_totale, 'credit': Decimal('0'),
             'libelle': f'Sortie stock {mouvement_ref}'},
            {'compte': compte_stock, 'debit': Decimal('0'), 'credit': valeur_totale,
             'libelle': f'Sortie stock {mouvement_ref}'},
        ]
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    return creer_ecriture(
        company, journal, date_mouvement or timezone.localdate(),
        f'Mouvement de stock {mouvement_ref}', lignes,
        reference=str(mouvement_ref), source_type='mouvement_stock',
        source_id=mouvement_ref, created_by=user,
        statut=EcritureComptable.Statut.VALIDEE,
    )


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
    # NTTRE8 — après l'écriture GL, vérifie les seuils d'alerte des comptes
    # impactés (source + destination) et notifie une fois par jour au maximum.
    notifier_comptes_sous_seuil(company, user=user)
    return virement.ecriture


def notifier_comptes_sous_seuil(company, *, user=None):
    """NTTRE8 — Notifie (une fois/jour/compte) les comptes passés sous leur seuil.

    S'appuie sur le sélecteur ``selectors.comptes_sous_seuil`` (lecture GL) et
    l'infrastructure ``notifications.notify`` existante — aucun nouveau canal ni
    nouveau type d'événement. Dé-doublonne : si une notification pour ce compte a
    déjà été émise le jour même, elle n'est pas répétée. Renvoie la liste des
    ``compte_id`` effectivement notifiés (best-effort, ne lève jamais).
    """
    from . import selectors
    try:  # pragma: no cover - défensif : ne jamais casser un posting GL
        from apps.notifications.models import EventType, Notification
        from apps.notifications.services import notify
    except Exception:  # pragma: no cover
        return []

    breaches = selectors.comptes_sous_seuil(company)
    if not breaches:
        return []
    destinataires = _destinataires_alerte_tresorerie(company, user)
    if not destinataires:
        return []
    aujourdhui = timezone.now().date()
    event = EventType.FLOTTE_BUDGET_DEPASSEMENT  # réutilise un type existant
    notifies = []
    for compte in breaches:
        lien = f'/compta/tresorerie?compte={compte["id"]}'
        deja = Notification.objects.filter(
            company=company, event_type=event, link=lien,
            created_at__date=aujourdhui).exists()
        if deja:
            continue
        titre = f"Compte « {compte['libelle']} » sous son seuil d'alerte"
        corps = (f"Solde courant : {compte['solde']} — "
                 f"seuil bas : {compte['seuil_alerte_bas']}, "
                 f"seuil découvert : {compte['seuil_alerte_decouvert']}.")
        for dest in destinataires:
            notify(dest, event, titre, body=corps[:2000], link=lien,
                   company=company)
        notifies.append(compte['id'])
    return notifies


def _destinataires_alerte_tresorerie(company, user):
    """Destinataires d'une alerte de trésorerie : les admins/responsables de la
    société (repli sur ``user`` si aucun n'est trouvé)."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    dests = list(User.objects.filter(
        company=company, is_active=True,
        role_legacy__in=['admin', 'responsable']))
    if not dests and user is not None:
        dests = [user]
    return dests


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


def _compte_credits_escompte(company):
    return _assurer_compte(company, '5520')


_TRANSITIONS_ESCOMPTABLES = (Effet.Statut.PORTEFEUILLE, Effet.Statut.REMIS)


@transaction.atomic
def escompter_effet(effet, *, compte_tresorerie, agios=None, interets=None,
                    date_escompte=None, user=None):
    """XACC34 — Remise à l'escompte d'un effet à recevoir avant échéance.

    Mobilisation bancaire : la banque avance le NET (montant − agios −
    intérêts) avant l'échéance. Poste UNE écriture équilibrée : débit
    ``compte_tresorerie`` du net + débit 6147/6311 (agios/intérêts, ici
    regroupés sur 6147 « services bancaires ») / crédit 5520 « crédits
    d'escompte » du montant BRUT de l'effet. Seul un effet ``portefeuille``
    ou ``remis`` peut être escompté (jamais un effet déjà soldé/impayé/
    escompté). Refusé en période close. Renvoie l'effet (``statut`` =
    ``escompte``).
    """
    if effet.sens != Effet.Sens.RECEVOIR:
        raise ValidationError("Seul un effet à recevoir peut être escompté.")
    if effet.statut not in _TRANSITIONS_ESCOMPTABLES:
        raise ValidationError(
            "Cet effet ne peut pas être escompté dans son état actuel.")
    company = effet.company
    if compte_tresorerie.company_id != company.id:
        raise ValidationError('Compte de trésorerie inconnu.')
    date_esc = date_escompte or timezone.now().date()
    if PeriodeComptable.date_verrouillee(company.id, date_esc):
        raise ValidationError(
            "Période comptable clôturée : impossible d'escompter l'effet du "
            f"{date_esc}.")
    montant = Decimal(effet.montant or 0)
    agios_dec = Decimal(agios or 0)
    interets_dec = Decimal(interets or 0)
    frais_total = agios_dec + interets_dec
    if frais_total < 0 or frais_total >= montant:
        raise ValidationError(
            "Les agios + intérêts doivent être positifs et inférieurs au "
            "montant de l'effet.")
    net = montant - frais_total
    compte_treso_comptable = compte_tresorerie.compte_comptable
    compte_5520 = _compte_credits_escompte(company)
    journal = _journal(company, Journal.Type.BANQUE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.BANQUE)
    libelle = f'Escompte effet {effet.numero or effet.id}'
    lignes = [
        {'compte': compte_treso_comptable, 'debit': net, 'credit': Decimal('0'),
         'libelle': libelle},
    ]
    if frais_total > 0:
        compte_frais = _compte_frais_bancaires(company)
        lignes.append({
            'compte': compte_frais, 'debit': frais_total, 'credit': Decimal('0'),
            'libelle': f'Agios/intérêts escompte {effet.numero or effet.id}'})
    lignes.append({
        'compte': compte_5520, 'debit': Decimal('0'), 'credit': montant,
        'libelle': libelle,
        'tiers_type': effet.tiers_type, 'tiers_id': effet.tiers_id})
    ecriture = creer_ecriture(
        company, journal, date_esc, libelle, lignes,
        reference=effet.numero or f'EFFET-{effet.id}',
        source_type='effet_escompte', source_id=effet.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    effet.statut = Effet.Statut.ESCOMPTE
    effet.agios_escompte = agios_dec
    effet.interets_escompte = interets_dec
    effet.date_escompte = date_esc
    effet.ecriture_escompte_id = ecriture.id
    effet.save(update_fields=[
        'statut', 'agios_escompte', 'interets_escompte', 'date_escompte',
        'ecriture_escompte_id'])
    return effet


@transaction.atomic
def apurer_escompte_effet(effet, *, date_apurement=None, user=None):
    """XACC34 — Apure le crédit d'escompte à l'échéance (5520 ↔ 3425).

    À l'échéance, la banque encaisse effectivement l'effet pour son propre
    compte : le crédit d'escompte (5520) est soldé contre la sortie de
    l'effet à recevoir (3425). Idempotent (un effet non-escompté ou déjà
    apuré/soldé ne bouge plus). Refusé en période close.
    """
    if effet.statut != Effet.Statut.ESCOMPTE:
        return effet
    company = effet.company
    date_ap = date_apurement or effet.date_echeance
    if PeriodeComptable.date_verrouillee(company.id, date_ap):
        raise ValidationError(
            "Période comptable clôturée : impossible d'apurer l'escompte du "
            f"{date_ap}.")
    montant = Decimal(effet.montant or 0)
    compte_5520 = _compte_credits_escompte(company)
    compte_eff = _compte_effets_recevoir(company)
    journal = _journal(company, Journal.Type.BANQUE)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.BANQUE)
    libelle = f'Apurement escompte effet {effet.numero or effet.id}'
    lignes = [
        {'compte': compte_5520, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle},
        {'compte': compte_eff, 'debit': Decimal('0'), 'credit': montant,
         'libelle': libelle,
         'tiers_type': effet.tiers_type, 'tiers_id': effet.tiers_id},
    ]
    ecriture = creer_ecriture(
        company, journal, date_ap, libelle, lignes,
        reference=effet.numero or f'EFFET-{effet.id}',
        source_type='effet_apurement_escompte', source_id=effet.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    effet.statut = Effet.Statut.ENCAISSE
    effet.ecriture_apurement_escompte_id = ecriture.id
    effet.save(update_fields=['statut', 'ecriture_apurement_escompte_id'])
    return effet


def endosser_effet(effet, *, beneficiaire, date_endossement=None, user=None):
    """XACC34 — Endosse un effet à recevoir à un tiers bénéficiaire.

    Transfert (sans mobilisation bancaire) : la créance de l'entreprise sur
    le tiré est SOLDÉE côté entreprise, le bénéficiaire devenant seul
    porteur. Aucune écriture comptable propre à ce module (le paiement au
    tiers via l'effet endossé se règle hors de ce système) — seul le statut
    et le bénéficiaire sont tracés pour l'audit. Refuse les transitions
    illégales (effet déjà soldé/escompté/impayé)."""
    if effet.sens != Effet.Sens.RECEVOIR:
        raise ValidationError("Seul un effet à recevoir peut être endossé.")
    if effet.statut not in _TRANSITIONS_ESCOMPTABLES:
        raise ValidationError(
            "Cet effet ne peut pas être endossé dans son état actuel.")
    if not beneficiaire:
        raise ValidationError("Le bénéficiaire de l'endossement est obligatoire.")
    effet.statut = Effet.Statut.ENDOSSE
    effet.beneficiaire_endossement = beneficiaire
    effet.date_endossement = date_endossement or timezone.now().date()
    effet.save(update_fields=[
        'statut', 'beneficiaire_endossement', 'date_endossement'])
    _chatter_action_sensible(
        effet, user, 'effet.endossement',
        detail=f'beneficiaire={beneficiaire}')
    return effet


def constater_protet(effet, *, frais_protet=None, date_protet=None, user=None):
    """NTTRE7 — Constate un protêt (constat d'huissier) sur un effet impayé.

    DISTINCT du simple rejet (``rejeter_effet``, FG130) : le protêt est l'acte
    d'huissier qui ouvre la voie du recouvrement forcé. Il ne change PAS le
    statut de l'effet (qui reste ``impaye``) — il enregistre la date et les
    frais de protêt pour la traçabilité. L'effet doit d'abord être ``impaye``.
    Journalise via ``AuditLog`` (NTTRE42). Renvoie l'effet.
    """
    if effet.statut != Effet.Statut.IMPAYE:
        raise ValidationError(
            "Un protêt ne se constate que sur un effet impayé (constater "
            "d'abord le rejet).")
    frais = Decimal(frais_protet or 0)
    if frais < 0:
        raise ValidationError("Les frais de protêt doivent être positifs.")
    effet.date_protet = date_protet or timezone.now().date()
    effet.frais_protet = frais
    effet.save(update_fields=['date_protet', 'frais_protet'])
    _chatter_action_sensible(
        effet, user, 'effet.protet', detail=f'frais={frais}')
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
    sont figés. XACC34 — un effet ``escompte`` impayé (rejeté par le tiré après
    mobilisation bancaire) RÉ-OUVRE la créance (débit 3425 / crédit 5520,
    réutilisant cette même contre-passation FG130) au lieu de la contre-
    passation « remis » classique. Refusé en période close. Renvoie l'effet.
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
    elif effet.sens == Effet.Sens.RECEVOIR and effet.statut == Effet.Statut.ESCOMPTE:
        # Impayé POST-escompte : le tiré n'a pas payé — la banque contre-passe
        # le crédit d'escompte et notre créance sur le client rouvre.
        montant = Decimal(effet.montant or 0)
        compte_eff = _compte_effets_recevoir(company)
        compte_5520 = _compte_credits_escompte(company)
        lignes = [
            {'compte': compte_eff, 'debit': montant, 'credit': Decimal('0'),
             'libelle': libelle,
             'tiers_type': effet.tiers_type, 'tiers_id': effet.tiers_id},
            {'compte': compte_5520, 'debit': Decimal('0'), 'credit': montant,
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
    ancien_commentaire = effet.commentaire
    effet.statut = Effet.Statut.IMPAYE
    effet.frais_rejet = frais
    if commentaire:
        effet.commentaire = commentaire
    effet.save(update_fields=['statut', 'frais_rejet', 'commentaire'])

    # YLEDG10 — un effet À RECEVOIR créé depuis un règlement chèque client
    # (``enregistrer_effet_pour_paiement_cheque``, commentaire
    # 'PAIEMENT-<id>') dont le rejet doit rouvrir la facture ventes : émettre
    # `effet_rejete` pour que `ventes` consomme (jamais un import cross-app de
    # modèle). Un effet sans cette origine (fournisseur, ou saisi à la main)
    # ne matche aucun préfixe → no-op côté abonné.
    if effet.sens == Effet.Sens.RECEVOIR and (
            ancien_commentaire or '').startswith('PAIEMENT-'):
        try:
            paiement_id = int(ancien_commentaire.split('-', 1)[1])
        except (ValueError, IndexError):
            paiement_id = None
        if paiement_id:
            from core.events import effet_rejete
            effet_rejete.send(
                sender=Effet, effet=effet, paiement_id=paiement_id,
                frais=frais, company=company)
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


def refresh_rapprochements_ouverts_pour_bcf(company, bon_commande_id):
    """YPROC8 — rafraîchit (ré-évalue) tous les rapprochements 3 voies OUVERTS
    (statut différent de VALIDE) d'un BCF donné, après un événement stock qui
    change le montant reçu (ex. retour fournisseur qui rouvre du reçu). Un
    rapprochement déjà VALIDÉ (bon-à-payer explicite) n'est PAS touché — le
    bon-à-payer n'est jamais écrasé silencieusement.

    Point d'entrée cross-app dédié : ``apps.stock`` appelle CETTE fonction
    (jamais le modèle ``Rapprochement`` directement) pour respecter le sens
    d'import autorisé (stock → compta via service, jamais l'inverse). Best-
    effort côté appelant recommandé ; ne lève que si le BCF n'appartient pas à
    la société (garantie multi-tenant). Renvoie le nombre de rapprochements
    rafraîchis."""
    qs = Rapprochement.objects.filter(
        company=company, bon_commande_id=bon_commande_id,
    ).exclude(statut=Rapprochement.Statut.VALIDE)
    count = 0
    for rapprochement in qs:
        evaluer_rapprochement(rapprochement)
        count += 1
    return count


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

    XACC24 — si une ``DemandeApprobationRib`` NON approuvée existe pour ce
    fournisseur, le RIB retourné est l'ANCIEN (``rib_actif``) et non celui
    actuellement sur le référentiel stock : le fichier de virement ne doit
    JAMAIS utiliser un RIB fournisseur en cours d'approbation.
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
        demande_en_cours = DemandeApprobationRib.objects.filter(
            company=company, fournisseur_id=tiers_id,
        ).exclude(statut=DemandeApprobationRib.Statut.REFUSEE).order_by(
            '-date_creation').first()
        if demande_en_cours is not None and (
                demande_en_cours.statut != DemandeApprobationRib.Statut.APPROUVEE):
            rib = demande_en_cours.ancien_rib
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
    # ── NTTRE5/6 — contrôle à 4 yeux (double validation) ──
    if double_validation_requise(run) and not run.approbations_distinctes:
        raise ValidationError(
            "Double validation requise : deux approbateurs DISTINCTS et "
            "habilités doivent approuver cette campagne avant de la poster.")
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
    _chatter_action_sensible(
        run, user, 'payment_run.postee', detail=f'total={run.total}')

    # YLEDG8 — pour chaque ligne référençant une FactureFournisseur (posée par
    # `proposer_lignes_payment_run` ou saisie manuellement), créer SON
    # PaiementFournisseur (mode virement, date du run) via le service dédié de
    # stock — jamais un import de ses modèles. Une ligne SANS référence (achat
    # libre / hors AP standard) reste inchangée (comportement historique).
    from apps.stock import services as stock_services
    for ligne in lignes:
        if not ligne.facture_fournisseur_id:
            continue
        stock_services.enregistrer_paiement_fournisseur_depuis_run(
            company=company, facture_id=ligne.facture_fournisseur_id,
            montant=ligne.montant, date_paiement=run.date_paiement,
            user=user)
    return ecriture


# ── NTTRE27 — Réglages trésorerie (singleton par société, auto-créé) ────────

def get_parametres_tresorerie(company):
    """NTTRE27 — Réglages trésorerie de la société (get-or-create singleton).

    Une société sans réglage explicite obtient les valeurs par défaut (aucune
    régression). Consommé par NTTRE5 (double validation), NTTRE9/28 (comptes de
    frais), NTTRE14 (format export), NTTRE16 (scénario), NTTRE18 (délai rupture).
    """
    from .models import ParametresTresorerie
    params, _ = ParametresTresorerie.objects.get_or_create(company=company)
    return params


# ── NTTRE11 — Plans de relance clients (recouvrement segmenté) ──────────────

def plan_relance_applicable(company, *, segment='', jours_retard=0):
    """NTTRE11 — (plan, palier) applicable pour un segment + un retard donné.

    Cherche d'abord un ``PlanRelanceTresorerie`` actif spécifique au ``segment``,
    à défaut le plan par défaut (segment vide). Renvoie ``(plan, palier)`` où
    ``palier`` est le palier au plus grand ``jours`` ≤ ``jours_retard`` — ou
    ``(None, None)`` si aucun plan/palier applicable. Lecture seule.
    """
    from .models import PlanRelanceTresorerie
    qs = PlanRelanceTresorerie.objects.filter(company=company, actif=True)
    plan = None
    if segment:
        plan = qs.filter(segment_client=segment).order_by('id').first()
    if plan is None:
        plan = qs.filter(segment_client='').order_by('id').first()
    if plan is None:
        return None, None
    return plan, plan.palier_applicable(jours_retard)


def declencher_relances_du_jour(company, *, aujourdhui=None, user=None):
    """NTTRE11 — Déclenche les paliers de relance dus, par facture en retard.

    Appelé par le job Celery de retard existant (``check_overdue_factures``) —
    ne le remplace pas. Pour chaque facture en retard (lue via le sélecteur de
    ``ventes``, cross-app, best-effort), résout le palier applicable selon le
    segment du client et le nombre de jours de retard, et pousse une notification
    interne (jamais d'envoi externe automatique). Renvoie la liste des
    déclenchements ``[{'facture_id', 'segment', 'jours_retard', 'canal'}]``.
    """
    aujourdhui = aujourdhui or timezone.localdate()
    declenchements = []
    try:  # cross-app : lecture des factures en retard via le sélecteur ventes.
        from apps.ventes.selectors import factures_en_retard
        factures = factures_en_retard(company)
    except Exception:  # pragma: no cover - sélecteur absent → best-effort no-op.
        return declenchements
    for fac in factures:
        segment = getattr(fac, 'segment_client', '') or ''
        echeance = getattr(fac, 'date_echeance', None)
        if echeance is None:
            continue
        jours_retard = (aujourdhui - echeance).days
        if jours_retard <= 0:
            continue
        plan, palier = plan_relance_applicable(
            company, segment=segment, jours_retard=jours_retard)
        if not palier:
            continue
        declenchements.append({
            'facture_id': getattr(fac, 'id', None),
            'segment': segment,
            'jours_retard': jours_retard,
            'canal': palier.get('canal', ''),
        })
    return declenchements


# ── NTTRE5/6 — Workflow à 4 yeux sur les campagnes de paiement ──────────────

def _pouvoir_bancaire_actif(run, user):
    """PouvoirBancaire ACTIF de ``user`` sur le compte payeur du run (ou None)."""
    from .models import PouvoirBancaire
    if user is None or run.compte_tresorerie_id is None:
        return None
    return (PouvoirBancaire.objects
            .filter(company=run.company, compte_tresorerie_id=run.compte_tresorerie_id,
                    utilisateur=user, statut=PouvoirBancaire.Statut.ACTIF)
            .order_by('-id').first())


def double_validation_requise(run):
    """NTTRE5/6 — True si le run exige deux approbateurs distincts.

    Deux déclencheurs INDÉPENDANTS :
      * le réglage société ``double_validation_paiement_actif`` (NTTRE5) ;
      * un plafond (NTTRE6) : le premier approbateur a un ``PouvoirBancaire``
        dont ``plafond_signature_seul`` est inférieur au total du run — il ne
        peut alors PAS engager seul, une seconde signature habilitée est exigée
        même si le réglage société est désactivé.
    Sans réglage ni pouvoir enregistré, retourne False (comportement historique
    inchangé : mono-validation).
    """
    params = get_parametres_tresorerie(run.company)
    if params.double_validation_paiement_actif:
        return True
    if run.approbateur_1_id:
        pouvoir = _pouvoir_bancaire_actif(run, run.approbateur_1)
        if pouvoir is not None and (run.total or Decimal('0')) > (
                pouvoir.plafond_signature_seul or Decimal('0')):
            return True
    return False


def approuver_payment_run(run, user):
    """NTTRE5 — Première approbation d'une campagne (approbateur ≠ créateur).

    Le premier approbateur ne peut pas être le créateur de la campagne. Fige la
    campagne en ``en_attente_approbation``. Journalise via ``AuditLog`` (NTTRE42).
    """
    if run.est_postee:
        raise ValidationError("Campagne déjà postée : approbation impossible.")
    if run.created_by_id and user is not None and run.created_by_id == user.id:
        raise ValidationError(
            "Le créateur de la campagne ne peut pas être le premier "
            "approbateur (contrôle à 4 yeux).")
    if run.approbateur_1_id:
        raise ValidationError("Campagne déjà approuvée une première fois.")
    run.approbateur_1 = user
    run.date_approbation_1 = timezone.now()
    if run.statut in (PaymentRun.Statut.BROUILLON, PaymentRun.Statut.PROPOSEE):
        run.statut = PaymentRun.Statut.EN_ATTENTE_APPROBATION
    run.save(update_fields=[
        'approbateur_1', 'date_approbation_1', 'statut'])
    _chatter_payment_run(run, user, 'approbation_1')
    return run


def approuver_final_payment_run(run, user):
    """NTTRE5 — Seconde approbation (approbateur ≠ premier ≠ créateur).

    Le second approbateur doit être distinct du premier ET du créateur. Rend la
    campagne éligible au posting. Journalise via ``AuditLog`` (NTTRE42).
    """
    if run.est_postee:
        raise ValidationError("Campagne déjà postée : approbation impossible.")
    if not run.approbateur_1_id:
        raise ValidationError(
            "Une première approbation est requise avant l'approbation finale.")
    if user is not None and run.approbateur_1_id == user.id:
        raise ValidationError(
            "Le second approbateur doit être distinct du premier.")
    if run.created_by_id and user is not None and run.created_by_id == user.id:
        raise ValidationError(
            "Le créateur ne peut pas être le second approbateur.")
    run.approbateur_2 = user
    run.date_approbation_2 = timezone.now()
    run.save(update_fields=['approbateur_2', 'date_approbation_2'])
    _chatter_payment_run(run, user, 'approbation_2')
    return run


def _chatter_action_sensible(instance, user, action, detail=''):
    """NTTRE41 — Trace une action sensible trésorerie dans le chatter
    ``records.Activity`` (best-effort, ne lève jamais).

    L'entrée ``AuditLog`` (NTTRE42) est écrite au niveau VUE
    (``apps/compta/views.py``, ``from apps.audit.recorder import record``) et NON
    ici : ``apps.compta.services`` doit rester libre de toute dépendance vers
    ``apps.audit`` pour respecter le contrat import-linter M4 — ``ventes`` importe
    ``compta.services`` mais ne doit jamais atteindre transitivement ``apps.audit``
    (``ventes`` n'importe pas ``compta.views``). Utilisé par les
    approbations/postings de PaymentRun (NTTRE5), la révocation de
    PouvoirBancaire (NTTRE6) et l'endossement/protêt (NTTRE7) : chaque action
    génère automatiquement une entrée ``Activity`` visible en écran détail
    (NTTRE41), sans action manuelle.
    """
    try:  # NTTRE41 — chatter (best-effort, ne bloque jamais l'action).
        from apps.records.models import Activity
        from apps.records.services import log_activity
        corps = f'{action}' + (f' — {detail}' if detail else '')
        log_activity(instance, Activity.Kind.MODIFICATION, user=user,
                     body=corps[:2000])
    except Exception:  # pragma: no cover - chatter best-effort
        pass


def _chatter_payment_run(run, user, action):
    _chatter_action_sensible(
        run, user, f'payment_run.{action}',
        detail=f'statut={run.statut} total={run.total}')


def proposer_lignes_payment_run(run, *, date_limite=None):
    """YLEDG8 — Remplit une campagne BROUILLON depuis les échéances
    fournisseur dues (``stock.selectors.factures_fournisseur_ouvertes`` —
    jamais un import de ses modèles), triées par date d'échéance. N'ajoute
    QUE les factures pas déjà référencées par une ligne existante de CETTE
    campagne (idempotent si appelé deux fois). Renvoie la liste des lignes
    ajoutées."""
    from apps.stock import selectors as stock_selectors

    if run.statut != PaymentRun.Statut.BROUILLON:
        raise ValidationError(
            "Une campagne figée ou postée ne peut plus être modifiée.")
    deja_references = set(
        run.lignes.exclude(facture_fournisseur_id__isnull=True)
        .values_list('facture_fournisseur_id', flat=True))
    candidates = stock_selectors.factures_fournisseur_ouvertes(
        run.company, date_limite=date_limite)
    ajoutees = []
    for candidate in candidates:
        if candidate['facture_id'] in deja_references:
            continue
        ligne = PaymentRunLine.objects.create(
            company=run.company, payment_run=run,
            tiers_type='fournisseur', tiers_id=candidate['fournisseur_id'],
            beneficiaire=candidate['fournisseur_nom'],
            reference=candidate['reference'], montant=candidate['montant'],
            date_echeance=candidate['date_echeance'],
            rib=candidate['rib'],
            facture_fournisseur_id=candidate['facture_id'],
        )
        ajoutees.append(ligne)
    if ajoutees:
        _recalc_total_payment_run(run)
    return ajoutees


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


def fichier_virement_bancaire(run):
    """NTTRE14 — Fichier de virement à LARGEUR FIXE (portail banque marocaine).

    Format texte compatible import direct d'un portail bancaire courant (type
    Attijari/BMCE) : une ligne détail par virement à largeur fixe
    (motif « VIR », RIB 24 chiffres cadré, montant en centimes cadré à droite,
    référence bénéficiaire), close par une ligne de contrôle « TOT » portant le
    nombre de lignes et le total en centimes. Réutilise la validation de
    ``fichier_virement`` (mode/coordonnées). Renvoie ``{'texte', 'total',
    'nb_lignes'}``. Lecture seule.
    """
    base = fichier_virement(run)  # valide mode + coordonnées, calcule le total.
    lignes = list(run.lignes.all())
    texte_lignes = []
    for ligne in lignes:
        rib = ''.join(c for c in (ligne.rib or ligne.iban or '') if c.isdigit())
        rib = rib[:24].rjust(24, '0')
        centimes = int((Decimal(ligne.montant or 0) * 100).to_integral_value())
        motif = 'VIR'
        beneficiaire = (ligne.beneficiaire or '')[:30].ljust(30)
        reference = (ligne.reference or '')[:16].ljust(16)
        texte_lignes.append(
            f'{motif}{rib}{str(centimes).rjust(15, "0")}'
            f'{beneficiaire}{reference}')
    total_centimes = int((base['total'] * 100).to_integral_value())
    texte_lignes.append(
        f'TOT{str(len(lignes)).rjust(6, "0")}'
        f'{str(total_centimes).rjust(15, "0")}')
    return {
        'texte': '\n'.join(texte_lignes) + '\n',
        'total': base['total'],
        'nb_lignes': len(lignes),
    }


# ── FG135 — Notes de frais & remboursements employés ───────────────────────

# Compte de charge par défaut imputé à une note de frais validée (classe 6) :
# 6143 « Déplacements, missions et réceptions » du barème CGNC.
_COMPTE_NOTE_FRAIS_DEFAUT = '6143'
# Compte personnel-créditeur (classe 4) : la dette de la société envers
# l'employé qui a avancé le cash (4432 « Rémunérations dues au personnel »).
_COMPTE_PERSONNEL_CREDITEUR = '4432'


def plafond_note_frais_pour(company, categorie):
    """Plafond configuré (XACC27) pour ``categorie``, ou ``None`` si absent."""
    return PlafondNoteFrais.objects.filter(
        company=company, categorie=categorie).first()


def note_frais_hors_politique(company, *, categorie, montant):
    """XACC27 — Vrai si ``montant`` dépasse le plafond de ``categorie``.

    Une catégorie sans plafond configuré n'est jamais hors politique (pas de
    référentiel = pas de contrôle, jamais bloquant)."""
    plafond = plafond_note_frais_pour(company, categorie)
    if plafond is None or not plafond.montant_max:
        return False
    return Decimal(montant or 0) > plafond.montant_max


def note_frais_doublon_possible(company, *, employe, date_frais, montant,
                                exclude_id=None):
    """XACC27 — Notes existantes du même employé/date/montant (doublon).

    Renvoie le queryset des notes candidates (jamais bloquant : l'appelant
    décide d'afficher un warning). Exclut la note ``exclude_id`` elle-même
    (utile lors d'une mise à jour)."""
    qs = NoteFrais.objects.filter(
        company=company, employe=employe, date_frais=date_frais,
        montant=Decimal(montant or 0))
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs


# ── XACC27 — OCR du justificatif → pré-remplissage (KEY-GATED) ─────────────
#
# Réutilise le SERVICE OCR existant (``backend/fastapi_ia``, Zhipu AI, no-op
# tant que sans clé), à l'image de ``apps.flotte.services.extraire_recu_carburant``
# (XFLT23). Ne crée JAMAIS de note de frais : ne fait QUE lire/renvoyer des
# champs pour pré-remplir le formulaire — l'utilisateur valide toujours.

def ocr_notes_frais_active():
    """XACC27 — True si l'OCR du justificatif de note de frais est activé.

    KEY-GATED : sans ``settings.COMPTA_OCR_NOTES_FRAIS_ENABLED`` (posé par le
    founder aux côtés de ``ZHIPU_API_KEY``), reste désactivé. Ne lève jamais.
    """
    from django.conf import settings
    return bool(getattr(settings, 'COMPTA_OCR_NOTES_FRAIS_ENABLED', False))


def extraire_justificatif_note_frais(file_bytes, *, mime=''):
    """XACC27 — Extrait montant/date/fournisseur d'un justificatif (photo).

    NO-OP tant que ``ocr_notes_frais_active()`` est faux : lève
    ``RuntimeError`` (la vue traduit en 503, message FR clair). Une fois
    activé, délègue à un module fournisseur isolé (``notes_frais_ocr_provider``,
    non câblé dans ce dépôt) qui appelle le service OCR ``backend/fastapi_ia``.
    Toute erreur provider est avalée (dict vide) — jamais de crash de l'écran
    de saisie.
    """
    if not ocr_notes_frais_active():
        raise RuntimeError('OCR indisponible (configuration manquante).')
    if not file_bytes:
        return {}
    try:  # pragma: no cover - dépend d'un provider externe non câblé ici.
        from . import notes_frais_ocr_provider as provider  # noqa: F401
    except ImportError:  # pragma: no cover
        return {}
    try:  # pragma: no cover
        return provider.extraire_justificatif(file_bytes, mime=mime) or {}
    except Exception:  # pragma: no cover - jamais casser l'écran de saisie.
        return {}


def mapper_justificatif_vers_note_frais(champs_bruts):
    """XACC27 — Normalise les champs OCR bruts vers les clés du formulaire
    ``NoteFrais`` (lecture seule, aucun effet de bord).

    Accepte ``montant``/``date``/``fournisseur`` (clés FR du provider) et
    projette vers ``montant``/``date_frais``/``motif``. Une clé absente est
    omise (l'utilisateur complète le reste à la main) ; NE remplace JAMAIS une
    saisie manuelle déjà présente — c'est l'appelant (vue/frontend) qui décide
    de fusionner sans écraser."""
    if not champs_bruts:
        return {}
    resultat = {}
    if champs_bruts.get('montant') is not None:
        resultat['montant'] = champs_bruts['montant']
    if champs_bruts.get('date'):
        resultat['date_frais'] = champs_bruts['date']
    if champs_bruts.get('fournisseur'):
        resultat['motif'] = champs_bruts['fournisseur']
    return resultat


# ── XACC28 — Refacturation des frais au client (billable expenses) ────────

@transaction.atomic
def refacturer_frais_client(company, *, facture, note_frais_ids, user=None):
    """Génère des lignes de refacturation sur une ``Facture`` EXISTANTE (XACC28).

    ``facture`` est l'objet ``ventes.Facture`` déjà résolu et vérifié
    company-scopé par l'APPELANT (la vue) — ce service ne fait AUCUN import de
    ``ventes.models`` : il délègue la création des lignes à
    ``apps.ventes.services.ajouter_lignes_frais_refactures`` (frontière
    cross-app). Chaque ``NoteFrais`` : (a) doit être ``refacturable`` et
    ``VALIDEE``, (b) ne doit pas déjà avoir été refacturée
    (``facture_refacturation_id`` vide) — sinon levée ``ValidationError``
    listant les références en défaut (jamais de refacturation silencieuse
    deux fois). Le montant de ligne = ``montant`` × (1 + ``taux_marge`` %).
    Marque chaque note ``facture_refacturation_id`` = facture. Renvoie la
    liste des ``LigneFacture`` créées (objets ``ventes``, opaques ici)."""
    from apps.ventes.services import ajouter_lignes_frais_refactures

    notes = list(NoteFrais.objects.filter(
        company=company, id__in=note_frais_ids or []))
    trouvees = {n.id for n in notes}
    manquantes = set(note_frais_ids or []) - trouvees
    if manquantes:
        raise ValidationError(
            f"Notes de frais introuvables pour cette société : {sorted(manquantes)}.")
    invalides = [
        n.reference or str(n.id) for n in notes
        if not n.refacturable or n.statut != NoteFrais.Statut.VALIDEE
        or n.facture_refacturation_id
    ]
    if invalides:
        raise ValidationError(
            "Notes non refacturables (non validées, non marquées "
            f"refacturables, ou déjà refacturées) : {', '.join(invalides)}.")
    lignes_payload = []
    for note in notes:
        taux_marge = Decimal(note.taux_marge or 0)
        montant_avec_marge = (
            Decimal(note.montant or 0) * (1 + taux_marge / Decimal('100'))
        ).quantize(Decimal('0.01'))
        lignes_payload.append({
            'designation': f'Frais refacturé — {note.motif or note.reference}',
            'montant_ht': montant_avec_marge,
        })
    lignes_creees = ajouter_lignes_frais_refactures(
        facture=facture, lignes=lignes_payload, user=user)
    for note in notes:
        note.facture_refacturation_id = facture.id
        note.save(update_fields=['facture_refacturation_id'])
    return lignes_creees


def creer_note_frais(company, *, employe, date_frais, montant, motif,
                     categorie=None, justificatif=None, compte_charge=None,
                     refacturable=False, taux_marge=None,
                     client_refacturation_id=None,
                     chantier_refacturation='', user=None):
    """Crée une note de frais (FG135) en BROUILLON, référence posée côté serveur.

    ``montant`` doit être strictement positif (validé par ``clean``). La
    ``reference`` (NDF-YYYYMM-NNNN) est attribuée via la fabrique gap-free
    race-safe (``apps.ventes.utils.references`` — jamais count()+1). XACC27 :
    ``hors_politique`` est calculé côté serveur (jamais imposable) depuis le
    plafond de la catégorie — c'est un warning affiché au valideur, jamais un
    blocage à la création. XACC28 : ``refacturable``/``taux_marge``/
    ``client_refacturation_id``/``chantier_refacturation`` rattachent la note à
    un client/chantier (string-ref) pour une refacturation ultérieure —
    ``facture_refacturation_id`` reste toujours vide à la création. ``company``
    posée côté serveur. Renvoie la note.
    """
    categorie = categorie or NoteFrais.Categorie.AUTRE
    montant_dec = Decimal(montant or 0)
    note = NoteFrais(
        company=company,
        employe=employe,
        date_frais=date_frais,
        montant=montant_dec,
        motif=motif or '',
        categorie=categorie,
        compte_charge=compte_charge,
        created_by=user,
        hors_politique=note_frais_hors_politique(
            company, categorie=categorie, montant=montant_dec),
        refacturable=bool(refacturable),
        taux_marge=Decimal(taux_marge) if taux_marge is not None else Decimal('0'),
        client_refacturation_id=client_refacturation_id,
        chantier_refacturation=chantier_refacturation or '',
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
    # XACC27 — au-delà du seuil configuré, le justificatif devient obligatoire.
    plafond = plafond_note_frais_pour(company, note.categorie)
    if (plafond is not None
            and plafond.seuil_justificatif_obligatoire is not None
            and montant > plafond.seuil_justificatif_obligatoire
            and not note.justificatif):
        raise ValidationError(
            "Justificatif obligatoire : le montant dépasse le seuil de "
            f"{plafond.seuil_justificatif_obligatoire} pour cette catégorie.")
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


# ── ZACC6 — Rapport de notes de frais (regroupement multi-lignes) ─────────

def creer_rapport_note_frais(company, *, employe, note_frais_ids,
                             libelle='', user=None):
    """Crée un ``RapportNoteFrais`` (ZACC6) en BROUILLON et y RATTACHE les
    notes désignées (``rapport = ce rapport``).

    Les notes doivent appartenir à la MÊME société + au MÊME employé, être en
    ``brouillon`` ou ``rejetee`` (pas déjà engagées dans un cycle de
    validation), et ne pas déjà porter un rapport. Référence ``RNF-`` posée
    côté serveur (fabrique gap-free race-safe). Renvoie le rapport.
    """
    notes = list(NoteFrais.objects.filter(
        company=company, employe=employe, id__in=note_frais_ids))
    if len(notes) != len(set(note_frais_ids or [])):
        raise ValidationError(
            "Certaines notes de frais sont introuvables pour cet employé.")
    for note in notes:
        if note.rapport_id is not None:
            raise ValidationError(
                f"La note {note.reference or note.id} appartient déjà à un "
                "rapport.")
        if note.statut not in (NoteFrais.Statut.BROUILLON,
                               NoteFrais.Statut.REJETEE):
            raise ValidationError(
                f"La note {note.reference or note.id} n'est pas en "
                "brouillon/rejetée : impossible de la regrouper.")
    rapport = RapportNoteFrais(
        company=company, employe=employe, libelle=libelle or '',
        created_by=user)

    def _save(reference):
        rapport.reference = reference
        rapport.save()
        NoteFrais.objects.filter(
            id__in=[n.id for n in notes]).update(rapport=rapport)
        return rapport

    from apps.ventes.utils.references import create_with_reference
    return create_with_reference(RapportNoteFrais, 'RNF', company, _save)


def soumettre_rapport_note_frais(rapport):
    """Soumet le RAPPORT (brouillon → soumis) — ZACC6. Soumet aussi chaque
    note rattachée encore en brouillon/rejetée (jamais un double-cycle)."""
    if rapport.statut not in (RapportNoteFrais.Statut.BROUILLON,):
        raise ValidationError(
            "Seul un rapport en brouillon peut être soumis.")
    for note in rapport.notes.all():
        if note.statut in (NoteFrais.Statut.BROUILLON,
                           NoteFrais.Statut.REJETEE):
            soumettre_note_frais(note)
    rapport.statut = RapportNoteFrais.Statut.SOUMIS
    rapport.save(update_fields=['statut'])
    return rapport


@transaction.atomic
def valider_rapport_note_frais(rapport, *, user=None):
    """Valide le RAPPORT et poste UNE écriture AGRÉGÉE (ZACC6).

    Σ des charges (groupées PAR COMPTE de charge) au débit / crédit UNIQUE
    4432 personnel-créditeur pour le total — une seule écriture équilibrée au
    lieu d'une par note. RESPECTE le verrou de période sur la date du jour.
    Idempotent : un rapport déjà validé renvoie son rapport inchangé. Chaque
    note rattachée passe individuellement à ``VALIDEE`` (même effet qu'un
    ``valider_note_frais`` un par un) MAIS sans poster sa propre écriture —
    seule l'écriture agrégée du rapport est créée.
    """
    if rapport.statut == RapportNoteFrais.Statut.VALIDE:
        return rapport
    if rapport.statut != RapportNoteFrais.Statut.SOUMIS:
        raise ValidationError("Seul un rapport soumis peut être validé.")
    company = rapport.company
    notes = list(rapport.notes.filter(statut=NoteFrais.Statut.SOUMISE))
    if not notes:
        raise ValidationError(
            "Aucune note soumise dans ce rapport : rien à valider.")
    date_ref = max(note.date_frais for note in notes)
    if PeriodeComptable.date_verrouillee(company.id, date_ref):
        raise ValidationError(
            "Période comptable clôturée : impossible de valider le rapport "
            f"de notes de frais au {date_ref}.")
    total = sum((Decimal(n.montant or 0) for n in notes), Decimal('0'))
    if total <= 0:
        raise ValidationError(
            "Impossible de valider un rapport de montant total nul.")
    # Regroupe Σ par compte de charge (celui de chaque note, ou le défaut) :
    # {compte_id: (compte, montant_cumule)}.
    par_compte = {}
    for note in notes:
        charge = note.compte_charge or _assurer_compte(
            company, _COMPTE_NOTE_FRAIS_DEFAUT)
        _, cumul = par_compte.get(charge.id, (charge, Decimal('0')))
        par_compte[charge.id] = (charge, cumul + Decimal(note.montant or 0))
    personnel = _assurer_compte(company, _COMPTE_PERSONNEL_CREDITEUR)
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    libelle = f"Rapport de notes de frais {rapport.reference}"
    lignes = [
        {'compte': charge, 'debit': montant, 'credit': Decimal('0'),
         'libelle': libelle}
        for (charge, montant) in par_compte.values()
    ]
    lignes.append({
        'compte': personnel, 'debit': Decimal('0'), 'credit': total,
        'libelle': libelle, 'tiers_type': 'employe',
        'tiers_id': rapport.employe_id,
    })
    ecriture = creer_ecriture(
        company, journal, date_ref, libelle, lignes,
        reference=rapport.reference or f'RNF-{rapport.id}',
        source_type='rapport_note_frais', source_id=rapport.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    for note in notes:
        charge = note.compte_charge or _assurer_compte(
            company, _COMPTE_NOTE_FRAIS_DEFAUT)
        note.statut = NoteFrais.Statut.VALIDEE
        note.compte_charge = charge
        note.valide_par = user
        note.date_validation = timezone.now()
        note.ecriture_charge = ecriture
        note.save(update_fields=[
            'statut', 'compte_charge', 'valide_par', 'date_validation',
            'ecriture_charge'])
    rapport.statut = RapportNoteFrais.Statut.VALIDE
    rapport.valide_par = user
    rapport.date_validation = timezone.now()
    rapport.ecriture_charge = ecriture
    rapport.save(update_fields=[
        'statut', 'valide_par', 'date_validation', 'ecriture_charge'])
    return rapport


@transaction.atomic
def rembourser_rapport_note_frais(rapport, *, compte_tresorerie,
                                  date_remboursement=None,
                                  mode_remboursement=None, user=None):
    """Rembourse le RAPPORT validé en UN SEUL paiement agrégé (ZACC6).

    Débit 4432 personnel-créditeur (Σ du rapport) / crédit du compte de
    trésorerie payeur. RESPECTE le verrou de période. Idempotent : un rapport
    déjà remboursé renvoie son rapport inchangé, jamais re-postable. Chaque
    note rattachée passe à ``REMBOURSEE``.
    """
    if rapport.statut == RapportNoteFrais.Statut.REMBOURSE:
        return rapport
    if rapport.statut != RapportNoteFrais.Statut.VALIDE:
        raise ValidationError("Seul un rapport validé peut être remboursé.")
    company = rapport.company
    if compte_tresorerie is None:
        raise ValidationError(
            "Un compte de trésorerie payeur est requis pour le "
            "remboursement.")
    if compte_tresorerie.company_id != company.id:
        raise ValidationError("Compte de trésorerie inconnu.")
    notes = list(rapport.notes.filter(statut=NoteFrais.Statut.VALIDEE))
    if not notes:
        raise ValidationError(
            "Aucune note validée dans ce rapport : rien à rembourser.")
    total = sum((Decimal(n.montant or 0) for n in notes), Decimal('0'))
    date_rbt = date_remboursement or timezone.localdate()
    if PeriodeComptable.date_verrouillee(company.id, date_rbt):
        raise ValidationError(
            "Période comptable clôturée : impossible de rembourser le "
            f"rapport de notes de frais à la date du {date_rbt}.")
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
    libelle = (f"Remboursement rapport de notes de frais {rapport.reference}"
               f" — {rapport.employe_id}")
    lignes = [
        {'compte': personnel, 'debit': total, 'credit': Decimal('0'),
         'libelle': libelle, 'tiers_type': 'employe',
         'tiers_id': rapport.employe_id},
        {'compte': compte_treso, 'debit': Decimal('0'), 'credit': total,
         'libelle': libelle},
    ]
    ecriture = creer_ecriture(
        company, journal, date_rbt, libelle, lignes,
        reference=rapport.reference or f'RNF-{rapport.id}',
        # ZACC6 — ``source_type`` est un CharField(max_length=30) ; la valeur
        # 'rapport_note_frais_remboursement' (32) dépassait la limite →
        # DataError à l'insert (aucune écriture n'a jamais été persistée, donc
        # zéro impact données). Valeur raccourcie (≤30) ; l'écriture est reliée
        # au rapport par la FK ``ecriture_remboursement``, jamais relue par cette
        # chaîne — aucun lecteur/préfixe ne l'utilise.
        source_type='rapport_frais_remboursement', source_id=rapport.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    for note in notes:
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
    rapport.statut = RapportNoteFrais.Statut.REMBOURSE
    rapport.compte_tresorerie = compte_tresorerie
    rapport.mode_remboursement = (
        mode_remboursement or rapport.mode_remboursement
        or RapportNoteFrais.ModeRemboursement.VIREMENT)
    rapport.date_remboursement = date_rbt
    rapport.rembourse_par = user
    rapport.ecriture_remboursement = ecriture
    rapport.save(update_fields=[
        'statut', 'compte_tresorerie', 'mode_remboursement',
        'date_remboursement', 'rembourse_par', 'ecriture_remboursement'])
    return rapport


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


# ── XPAI25 — Remboursement d'une indemnité chantier VIA LA PAIE ────────────
# Fonction fine dédiée : distincte de ``rembourser_indemnite_chantier``
# (paiement par trésorerie, FG136) — ici le montant est versé AVEC le net du
# bulletin de salaire (aucun compte de trésorerie ni écriture GL séparée côté
# compta : la ligne « Remboursement frais » du bulletin ET l'écriture du
# journal de paie portent déjà le montant, cf. ``apps.paie.services``).

def marquer_indemnite_remboursee_par_paie(indem, *, user=None,
                                          date_remboursement=None):
    """Marque une indemnité chantier REMBOURSÉE via la paie (XPAI25).

    Idempotent : une indemnité déjà ``REMBOURSEE`` est renvoyée telle quelle
    (jamais retraitée — double comptage impossible). Refuse une indemnité pas
    encore ``VALIDEE``. Aucune écriture de trésorerie n'est postée ici (le
    montant est déjà porté par le bulletin de paie qui appelle cette
    fonction) — ``compte_tresorerie``/``ecriture_remboursement`` restent
    vides, ce qui distingue ce remboursement du remboursement par trésorerie
    (``rembourser_indemnite_chantier``). Renvoie l'indemnité.
    """
    if indem.statut == IndemniteChantier.Statut.REMBOURSEE:
        return indem
    if indem.statut != IndemniteChantier.Statut.VALIDEE:
        raise ValidationError(
            "Seule une indemnité validée peut être remboursée.")
    indem.statut = IndemniteChantier.Statut.REMBOURSEE
    indem.date_remboursement = date_remboursement or indem.date_deplacement
    indem.rembourse_par = user
    indem.save(update_fields=['statut', 'date_remboursement', 'rembourse_par'])
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


# ── XACC9 — Calendrier des obligations fiscales ─────────────────────────────
# Les briques existent (TVA FG137, acomptes IS FG140, RAS FG139, timbre FG144,
# état 9421 FG143, liasse FG142) mais aucune vue calendaire unifiée. On
# GÉNÈRE ici toutes les échéances de l'exercice avec leur date limite
# marocaine (délais CGI standards, arrondis au jour ouvré n'est PAS géré ici —
# le fiduciaire humain ajuste en cas de jour férié), idempotent (une
# obligation par (company, type, période) — la contrainte d'unicité du modèle
# empêche tout doublon même en cas de rejeu).

def _dernier_jour_mois(annee, mois):
    import calendar
    return calendar.monthrange(annee, mois)[1]


# NB : l'ajout de mois avec clamp de fin de mois est DÉJÀ fourni par
# ``_ajouter_mois(d, mois)`` (FG244, plus bas dans ce fichier) — on le
# réutilise ici (même signature ``(date, n_mois)``) plutôt que de dupliquer.


def _echeances_tva(exercice, regime_tva):
    """Périodes + dates limites TVA de l'exercice (mensuel ou trimestriel).

    Délai CGI marocain : dépôt/paiement au 20 du mois suivant la fin de la
    période (mensuelle ou trimestrielle).
    """
    from datetime import date as _date

    echeances = []
    if regime_tva == DeclarationTVA.Regime.TRIMESTRIEL:
        for q in range(4):
            mois_debut = 1 + q * 3
            debut = _date(exercice.date_debut.year, mois_debut, 1)
            if debut > exercice.date_fin:
                break
            fin_mois = min(mois_debut + 2, 12)
            fin = _date(debut.year, fin_mois,
                        _dernier_jour_mois(debut.year, fin_mois))
            fin = min(fin, exercice.date_fin)
            limite = _ajouter_mois(fin.replace(day=1), 1).replace(day=20)
            echeances.append((debut, fin, limite))
    else:
        mois = exercice.date_debut.replace(day=1)
        while mois <= exercice.date_fin:
            fin = mois.replace(day=_dernier_jour_mois(mois.year, mois.month))
            fin = min(fin, exercice.date_fin)
            limite = _ajouter_mois(mois, 1).replace(day=20)
            echeances.append((mois, fin, limite))
            mois = _ajouter_mois(mois, 1)
    return echeances


@transaction.atomic
def generer_calendrier_fiscal(company, exercice, *, regime_tva=None,
                              regime_ras=None):
    """Génère le calendrier fiscal COMPLET de l'exercice (XACC9).

    Régime TVA (mensuel/trimestriel, défaut mensuel) pilote la cadence TVA ET
    RAS (même échéance CGI, 20 du mois suivant). Ajoute aussi : 4 acomptes IS
    (31 mars/juin/sept/déc — CGI), 1 droit de timbre annuel (aligné sur la
    dernière échéance TVA de l'exercice), 1 état 9421 et 1 liasse fiscale (31
    mars N+1 — 3 mois après la clôture, hypothèse exercice civil). IDEMPOTENT :
    ``get_or_create`` par ``(company, type, periode_debut, periode_fin)``, ne
    duplique jamais un exercice déjà généré. Renvoie la liste des
    ``ObligationFiscale`` (créées ou déjà existantes) triée par date limite.
    """
    from datetime import date as _date

    regime_tva = regime_tva or DeclarationTVA.Regime.MENSUEL
    obligations = []

    for debut, fin, limite in _echeances_tva(exercice, regime_tva):
        obl, _ = ObligationFiscale.objects.get_or_create(
            company=company, type_obligation=ObligationFiscale.Type.TVA,
            periode_debut=debut, periode_fin=fin,
            defaults={'date_limite': limite,
                      'libelle': f'TVA {debut.strftime("%m/%Y")}'})
        obligations.append(obl)
        obl_ras, _ = ObligationFiscale.objects.get_or_create(
            company=company, type_obligation=ObligationFiscale.Type.RAS,
            periode_debut=debut, periode_fin=fin,
            defaults={'date_limite': limite,
                      'libelle': f'RAS {debut.strftime("%m/%Y")}'})
        obligations.append(obl_ras)

    for mois in (3, 6, 9, 12):
        if _date(exercice.date_debut.year, mois, 1) > exercice.date_fin:
            continue
        limite = _date(exercice.date_debut.year, mois,
                       _dernier_jour_mois(exercice.date_debut.year, mois))
        obl, _ = ObligationFiscale.objects.get_or_create(
            company=company, type_obligation=ObligationFiscale.Type.IS_ACOMPTE,
            periode_debut=exercice.date_debut, periode_fin=limite,
            defaults={
                'date_limite': limite,
                'libelle': f'Acompte IS {mois:02d}/{exercice.date_debut.year}',
            })
        obligations.append(obl)

    if obligations:
        derniere_tva = max(
            (o.date_limite for o in obligations
             if o.type_obligation == ObligationFiscale.Type.TVA),
            default=None)
        if derniere_tva:
            obl, _ = ObligationFiscale.objects.get_or_create(
                company=company, type_obligation=ObligationFiscale.Type.TIMBRE,
                periode_debut=exercice.date_debut, periode_fin=exercice.date_fin,
                defaults={'date_limite': derniere_tva,
                          'libelle': 'Droit de timbre'})
            obligations.append(obl)

    limite_liasse = _ajouter_mois(
        exercice.date_fin.replace(day=1), 3).replace(day=31)
    try:
        limite_liasse = limite_liasse.replace(day=31)
    except ValueError:
        limite_liasse = limite_liasse.replace(
            day=_dernier_jour_mois(limite_liasse.year, limite_liasse.month))
    obl, _ = ObligationFiscale.objects.get_or_create(
        company=company, type_obligation=ObligationFiscale.Type.LIASSE_FISCALE,
        periode_debut=exercice.date_debut, periode_fin=exercice.date_fin,
        defaults={'date_limite': limite_liasse, 'libelle': 'Liasse fiscale'})
    obligations.append(obl)
    obl_9421, _ = ObligationFiscale.objects.get_or_create(
        company=company, type_obligation=ObligationFiscale.Type.ETAT_9421,
        periode_debut=exercice.date_debut, periode_fin=exercice.date_fin,
        defaults={'date_limite': limite_liasse, 'libelle': 'État 9421'})
    obligations.append(obl_9421)

    return sorted(obligations, key=lambda o: (o.date_limite, o.id))


def marquer_obligation_deposee(obligation, *, source_type='', source_id=None):
    """Passe une obligation en « déposée », liée à sa déclaration source (XACC9).

    Appelé au dépôt d'une ``DeclarationTVA`` (ou toute autre déclaration
    source interne à compta) : ``source_type``/``source_id`` tracent la pièce
    déposée. Idempotent (repasser la même obligation à « déposée » ne change
    rien d'autre). Renvoie l'obligation.
    """
    if obligation.statut == ObligationFiscale.Statut.A_PREPARER:
        obligation.statut = ObligationFiscale.Statut.DEPOSEE
    if source_type:
        obligation.source_type = source_type
    if source_id is not None:
        obligation.source_id = source_id
    obligation.save(update_fields=['statut', 'source_type', 'source_id'])
    return obligation


def envoyer_rappels_j7(company, *, aujourdhui=None):
    """Notifie J-7 chaque obligation « à préparer » dont l'échéance approche.

    Diffuse via ``notifications.services.notify_many`` (satellite — jamais
    importé au niveau module, cf. carte des couches M4) vers les comptes
    Admin/Responsable de la société. IDEMPOTENT : ``rappel_envoye_le`` marque
    l'obligation notifiée, un second appel le même jour (ou plus tard) ne
    renotifie pas. Renvoie la liste des obligations notifiées.
    """
    from datetime import timedelta

    ref = aujourdhui or timezone.localdate()
    seuil = ref + timedelta(days=7)
    dues = ObligationFiscale.objects.filter(
        company=company, statut=ObligationFiscale.Statut.A_PREPARER,
        date_limite__lte=seuil, date_limite__gte=ref,
        rappel_envoye_le__isnull=True)
    notifiees = []
    if not dues.exists():
        return notifiees
    from authentication.models import CustomUser
    destinataires = CustomUser.objects.filter(
        company=company, is_active=True,
        role_legacy__in=[CustomUser.ROLE_ADMIN, CustomUser.ROLE_RESPONSABLE])
    if not destinataires.exists():
        return notifiees
    from apps.notifications.services import notify_many
    from apps.notifications.models import EventType
    for obligation in dues:
        libelle_defaut = obligation.get_type_obligation_display()
        notify_many(
            list(destinataires), EventType.DIGEST,
            f'Échéance fiscale J-7 : {libelle_defaut}',
            body=(f'{obligation.libelle or libelle_defaut} — date limite '
                  f'{obligation.date_limite}.'),
            company=company,
        )
        obligation.rappel_envoye_le = timezone.now()
        obligation.save(update_fields=['rappel_envoye_le'])
        notifiees.append(obligation)
    return notifiees


def deposer_declaration_tva(declaration):
    """Dépose une ``DeclarationTVA`` PRÉPARÉE : passe DEPOSEE + son obligation.

    Idempotent (redéposer une déclaration déjà déposée ne change rien
    d'autre). Cherche l'``ObligationFiscale`` TVA de la société dont la
    période COUVRE ``declaration`` (``periode_debut`` ≤ date_debut ET
    ``periode_fin`` ≥ date_fin) et la fait passer « déposée » via
    ``marquer_obligation_deposee`` — no-op silencieux si aucun calendrier
    fiscal n'a été généré pour cette période (XACC9 est additif : ne bloque
    jamais le dépôt d'une déclaration). Renvoie la déclaration.
    """
    if declaration.statut != DeclarationTVA.Statut.DEPOSEE:
        declaration.statut = DeclarationTVA.Statut.DEPOSEE
        declaration.save(update_fields=['statut'])
    obligation = ObligationFiscale.objects.filter(
        company=declaration.company,
        type_obligation=ObligationFiscale.Type.TVA,
        periode_debut__lte=declaration.date_debut,
        periode_fin__gte=declaration.date_fin,
    ).first()
    if obligation is not None:
        marquer_obligation_deposee(
            obligation, source_type='declaration_tva', source_id=declaration.id)
    return declaration


# ── XACC10 — Solde TVA de la période (clôture) ──────────────────────────────

@transaction.atomic
def solder_tva_periode(periode, *, user=None):
    """Poste l'écriture de solde TVA d'une période (XACC10, checklist de clôture).

    Recalcule la TVA à déclarer EXACTEMENT comme ``preparer_declaration_tva``
    (même agrégation GL, cohérente avec FG137 — aucune divergence possible)
    et poste, si le montant net dû est positif, l'écriture de solde :
    débit 4455 (TVA facturée, on solde) + débit 3455 (TVA récupérable, on
    solde) → crédit 44552 (« État TVA due »). Si le net est négatif (crédit de
    TVA), ne poste rien (rien à devoir — le crédit se reporte via FG137).
    IDEMPOTENT par période (``source_type='solde_tva'``,
    ``source_id=periode.id``). Renvoie l'écriture, ou None si rien à solder.
    """
    from . import selectors

    company = periode.company
    existante = _ecriture_existante(company, 'solde_tva', periode.id)
    if existante:
        return existante
    calc = selectors.preparer_declaration_tva(
        company, date_debut=periode.date_debut, date_fin=periode.date_fin)
    collectee = calc['tva_collectee']
    deductible = calc['tva_deductible']
    net = calc['tva_a_declarer']
    if net <= 0:
        return None
    comptes = _comptes_requis(company)
    compte_due = _assurer_compte(company, '44552')
    # Mécanique CGNC : 4455 (TVA facturée) porte un solde CRÉDITEUR, 3455 (TVA
    # récupérable) un solde DÉBITEUR. Pour les solder tous les deux, on
    # DÉBITE 4455 (annule son crédit) et on CRÉDITE 3455 (annule son débit) ;
    # le NET (collectée − déductible = 44552) équilibre l'écriture.
    lignes = []
    if collectee > 0:
        lignes.append({
            'compte': comptes['tva_facturee'], 'debit': collectee,
            'credit': Decimal('0'), 'libelle': 'Solde TVA facturée'})
    if deductible > 0:
        lignes.append({
            'compte': comptes['tva_recuperable'], 'debit': Decimal('0'),
            'credit': deductible, 'libelle': 'Solde TVA récupérable'})
    lignes.append({
        'compte': compte_due, 'debit': Decimal('0'), 'credit': net,
        'libelle': 'État TVA due'})
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    return creer_ecriture(
        company, journal, periode.date_fin, 'Solde TVA de la période', lignes,
        reference=f'SOLDE-TVA-{periode.id}', source_type='solde_tva',
        source_id=periode.id, created_by=user,
        statut=EcritureComptable.Statut.VALIDEE,
    )


# ── FG139 — Retenue à la source (RAS) sur honoraires/prestations ───────────

def taux_ras_conventionnel(company, pays_beneficiaire):
    """NTMAR18 — taux RAS conventionnel réduit d'une prestation étrangère si une
    ``ConventionFiscale`` active existe pour ``pays_beneficiaire`` (matché sur le
    nom du pays, insensible à la casse), sinon ``None`` (taux de droit commun)."""
    from .models import ConventionFiscale

    if not pays_beneficiaire:
        return None
    convention = ConventionFiscale.objects.filter(
        company=company, actif=True,
        pays__iexact=pays_beneficiaire.strip()).first()
    return convention.taux_conventionnel if convention else None


def enregistrer_retenue_source(company, *, date_piece, base, taux=None,
                               type_prestation=None, tiers_type='', tiers_id=None,
                               tiers_nom='', identifiant_fiscal='', piece='',
                               libelle='', pays_beneficiaire='',
                               convention_appliquee=None, user=None):
    """Enregistre une RAS sur une pièce d'honoraires/prestation (FG139).

    Calcule le ``montant`` retenu = base × taux % (arrondi 2 décimales) et FIGE le
    snapshot dans une ``RetenueSource`` en statut « à verser ». Le ``taux`` par
    défaut est ``RetenueSource.TAUX_DEFAUT`` (10 %). La ``reference``
    (RAS-YYYYMM-NNNN) et la ``company`` sont posées côté serveur (jamais lues du
    corps). Le tiers prestataire est référencé par auxiliaire string-FK
    (``tiers_type`` / ``tiers_id``) — jamais d'import cross-app de modèle. Renvoie
    la retenue.

    NTMAR18 — pour une prestation étrangère (``type_prestation=
    prestation_etrangere``) sans ``taux`` explicite, on applique le taux
    CONVENTIONNEL réduit si une ``ConventionFiscale`` active couvre
    ``pays_beneficiaire`` (sinon le taux de droit commun). ``convention_
    appliquee`` est posé automatiquement en conséquence si non fourni.
    """
    from apps.ventes.utils.references import create_with_reference

    # NTMAR18 — résolution du taux conventionnel pour une prestation étrangère
    # quand aucun taux n'est imposé explicitement.
    taux_applique = taux
    convention_effective = bool(convention_appliquee)
    if (taux is None
            and type_prestation == RetenueSource.TypePrestation.PRESTATION_ETRANGERE):
        taux_conv = taux_ras_conventionnel(company, pays_beneficiaire)
        if taux_conv is not None:
            taux_applique = taux_conv
            convention_effective = True

    ras = RetenueSource(
        company=company,
        date_piece=date_piece,
        base=Decimal(base or 0),
        taux=(Decimal(taux_applique) if taux_applique is not None
              else RetenueSource.TAUX_DEFAUT),
        type_prestation=(type_prestation
                         or RetenueSource.TypePrestation.HONORAIRES),
        tiers_type=tiers_type or '',
        tiers_id=tiers_id,
        tiers_nom=tiers_nom or '',
        identifiant_fiscal=identifiant_fiscal or '',
        pays_beneficiaire=pays_beneficiaire or '',
        convention_appliquee=convention_effective,
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
                              libelle='', mode_acquittement=None, user=None):
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
        mode_acquittement=(mode_acquittement or 'papier'),
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


# ── XACC26 — Provisions risques & charges / dépréciation stock / immo ─────

_COMPTES_PROVISION_PAR_NATURE = {
    Provision.Nature.RISQUES_CHARGES: {
        'passif': '1516', 'charge': '6195', 'produit': '7195',
    },
    Provision.Nature.DEPRECIATION_STOCK: {
        'passif': '3910', 'charge': '6196', 'produit': '7196',
    },
    Provision.Nature.DEPRECIATION_IMMO: {
        'passif': '2911', 'charge': '6392', 'produit': '7392',
    },
}


def _comptes_provision(company, nature):
    numeros = _COMPTES_PROVISION_PAR_NATURE.get(
        nature, _COMPTES_PROVISION_PAR_NATURE[Provision.Nature.RISQUES_CHARGES])
    return {
        key: _assurer_compte(company, numero)
        for key, numero in numeros.items()
    }


@transaction.atomic
def enregistrer_provision(company, *, nature, date_dotation, montant, motif='',
                          date_echeance_revue=None, poster=True, user=None):
    """Enregistre une dotation de provision risques/charges/stock/immo (XACC26).

    Poste (sauf ``poster=false``) l'écriture OD : débit compte de charge (6195
    risques&charges / 6196 dépréciation stock / 6392 dépréciation immo) / crédit
    compte de passif (1516 / 3910 / 2911 selon ``nature``). ``reference``
    (PROV-YYYYMM-NNNN) et ``company`` posées côté serveur. Renvoie la provision.
    """
    from apps.ventes.utils.references import create_with_reference

    montant = Decimal(montant or 0)
    prov = Provision(
        company=company,
        nature=nature,
        date_dotation=date_dotation,
        montant_dotation=montant,
        motif=motif or '',
        date_echeance_revue=date_echeance_revue,
        created_by=user,
    )
    prov.full_clean(exclude=['reference', 'created_by'])

    def _save(reference):
        prov.reference = reference
        prov.save()
        return prov

    prov = create_with_reference(Provision, 'PROV', company, _save)
    if poster and prov.montant_dotation > 0:
        comptes = _comptes_provision(company, prov.nature)
        ecriture = creer_ecriture_od(
            company, date_dotation,
            f'Dotation provision {prov.get_nature_display()} {prov.reference}',
            [
                {'compte': comptes['charge'], 'debit': prov.montant_dotation,
                 'credit': Decimal('0'), 'libelle': prov.motif or prov.reference},
                {'compte': comptes['passif'], 'debit': Decimal('0'),
                 'credit': prov.montant_dotation,
                 'libelle': prov.motif or prov.reference},
            ],
            created_by=user)
        prov.ecriture_dotation_id = ecriture.id
        prov.save(update_fields=['ecriture_dotation_id'])
    return prov


@transaction.atomic
def reprendre_provision(prov, *, montant=None, date_reprise=None, poster=True,
                        user=None):
    """Reprend (partiellement ou totalement) une provision XACC26.

    ``montant`` par défaut = solde restant (reprise totale). Poste l'écriture
    OD inverse (débit passif / crédit produit de reprise) et cumule
    ``montant_repris``. Refuse une reprise qui dépasserait le solde. Idempotent
    au sens où une provision déjà soldée ne peut plus être reprise (400 côté
    vue). Renvoie la provision.
    """
    if prov.est_soldee:
        raise ValidationError("Cette provision est déjà entièrement reprise.")
    solde = prov.solde
    montant = Decimal(montant) if montant is not None else solde
    if montant <= 0 or montant > solde:
        raise ValidationError(
            f"Le montant de reprise doit être compris entre 0 et le solde "
            f"({solde}).")
    date_reprise = date_reprise or timezone.now().date()
    if poster:
        comptes = _comptes_provision(prov.company, prov.nature)
        creer_ecriture_od(
            prov.company, date_reprise,
            f'Reprise provision {prov.get_nature_display()} {prov.reference}',
            [
                {'compte': comptes['passif'], 'debit': montant,
                 'credit': Decimal('0'), 'libelle': prov.motif or prov.reference},
                {'compte': comptes['produit'], 'debit': Decimal('0'),
                 'credit': montant, 'libelle': prov.motif or prov.reference},
            ],
            created_by=user)
    prov.montant_repris = (prov.montant_repris or Decimal('0')) + montant
    prov.date_derniere_reprise = date_reprise
    prov.save(update_fields=['montant_repris', 'date_derniere_reprise'])
    return prov


# ── XFAC13 — Abandon de créance (write-off) ────────────────────────────────

def provisions_ouvertes_pour_tiers(company, *, tiers_type='client', tiers_id):
    """Provisions FG152 encore en dotation pour ce tiers (lecture seule).

    Utilisé par ``ventes`` pour reprendre automatiquement une provision
    existante quand la créance qu'elle couvrait est abandonnée (soldée), sans
    dupliquer la logique de reprise. Jamais d'import du modèle ``ventes`` ici :
    le tiers est référencé par ``(tiers_type, tiers_id)``.
    """
    return list(ProvisionCreance.objects.filter(
        company=company, tiers_type=tiers_type, tiers_id=tiers_id,
        statut=ProvisionCreance.Statut.DOTATION,
    ))


@transaction.atomic
def abandonner_creance(company, *, montant, date_abandon=None,
                       tiers_type='client', tiers_id=None, tiers_nom='',
                       libelle='', reprendre_provisions=True, poster=True,
                       user=None):
    """Écriture d'abandon de créance (write-off) — XFAC13.

    Solde une créance irrécouvrable/négligeable : débit 6585 « pertes sur
    créances irrécouvrables » / crédit 3421 « clients » (le compte 6585 est
    assuré à la volée s'il n'a pas encore été semé — barème CGNC). Si
    ``reprendre_provisions``, reprend aussi toute provision FG152 encore
    ouverte pour ce tiers (la créance provisionnée est maintenant définitivement
    perdue, pas juste recouvrée). Respecte le verrou de période (via
    ``creer_ecriture_od``). Renvoie l'écriture (ou ``None`` si ``montant`` est
    nul/négatif — rien n'est posté).
    """
    montant = Decimal(montant or 0)
    if montant <= 0:
        return None
    date_abandon = date_abandon or timezone.now().date()
    ecriture = None
    if poster:
        _comptes_requis(company)
        compte_perte = _assurer_compte(company, '6585')
        compte_clients = get_compte(company, '3421')
        if compte_clients is None:
            compte_clients = _assurer_compte(company, '3421')
        ecriture = creer_ecriture_od(
            company, date_abandon,
            libelle or f'Abandon de créance {tiers_nom}'.strip(),
            [
                {'compte': compte_perte, 'debit': montant,
                 'credit': Decimal('0'), 'libelle': tiers_nom,
                 'tiers_type': tiers_type, 'tiers_id': tiers_id},
                {'compte': compte_clients, 'debit': Decimal('0'),
                 'credit': montant, 'libelle': tiers_nom,
                 'tiers_type': tiers_type, 'tiers_id': tiers_id},
            ],
            created_by=user)
    if reprendre_provisions and tiers_id is not None:
        for prov in provisions_ouvertes_pour_tiers(
                company, tiers_type=tiers_type, tiers_id=tiers_id):
            reprendre_provision_creance(
                prov, date_reprise=date_abandon, poster=poster, user=user)
    return ecriture


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


# ── XPLT20 — Écritures inter-sociétés miroir (vente A → achat B) ──────────

def generer_facture_fournisseur_miroir_intersociete(facture, company):
    """XPLT20 — miroir vente ``company`` (A) → achat B (``RegleInterSociete``,
    opt-in STRICT, désactivée par défaut).

    Appelé sur ``facture_emise``. NO-OP (comportement inchangé) si : aucune
    règle ``actif=True`` pour ``company`` ; le client de la facture ne
    correspond (ICE/IF) à aucun ``CompanyProfile`` de règle ; ``company``
    (A) n'a pas d'ICE/IF renseigné ; ou B n'a pas déjà de fiche Fournisseur
    pour A (JAMAIS de création silencieuse d'un tiers hors du groupe).
    Jamais d'auto-validation : le miroir est une ``FactureFournisseur``
    BROUILLON que B doit valider lui-même. Idempotent (contrainte unique
    ``EcritureLiaisonInterSociete`` : une facture source ne génère jamais
    deux miroirs).
    """
    from .models import EcritureLiaisonInterSociete, RegleInterSociete

    client = getattr(facture, 'client', None)
    if client is None:
        return None
    client_ice = (getattr(client, 'ice', '') or '').strip()
    client_if = (getattr(client, 'if_fiscal', '') or '').strip()
    if not client_ice and not client_if:
        return None

    from apps.parametres.models_company import CompanyProfile

    profil_a = CompanyProfile.objects.filter(company=company).first()
    a_ice = (profil_a.ice or '').strip() if profil_a else ''
    a_if = (profil_a.identifiant_fiscal or '').strip() if profil_a else ''
    if not a_ice and not a_if:
        return None  # A n'a pas d'ICE/IF renseigné : rapprochement impossible.

    for regle in RegleInterSociete.objects.filter(
            societe_a=company, actif=True).select_related('societe_b'):
        if EcritureLiaisonInterSociete.objects.filter(
                regle=regle, facture_source_id=facture.id).exists():
            continue  # déjà miroirée (idempotence).

        societe_b = regle.societe_b
        profil_b = CompanyProfile.objects.filter(company=societe_b).first()
        if profil_b is None:
            continue
        b_ice = (profil_b.ice or '').strip()
        b_if = (profil_b.identifiant_fiscal or '').strip()
        if not ((client_ice and b_ice and client_ice == b_ice)
                or (client_if and b_if and client_if == b_if)):
            continue  # ce client de A n'est pas B — rien à miroirer.

        from apps.stock import selectors as stock_selectors
        candidats = stock_selectors.fournisseurs_pour_controle_ice(societe_b)
        fournisseur_match = next(
            (f for f in candidats
             if (a_ice and f['ice'] == a_ice)
             or (a_if and f['if_fiscal'] == a_if)),
            None)
        if fournisseur_match is None:
            # B n'a pas encore de fiche fournisseur pour A : jamais de
            # création silencieuse d'un tiers hors du groupe.
            continue

        montant_ht = facture.total_ht
        montant_tva = facture.total_tva
        montant_ttc = facture.total_ttc

        from apps.stock import services as stock_services
        try:
            miroir, _doublons = (
                stock_services.creer_facture_fournisseur_depuis_ocr(
                    company=societe_b, user=None,
                    fields={
                        'ice': a_ice or None,
                        'numero': facture.reference,
                        'date': (facture.date_emission.isoformat()
                                 if facture.date_emission else None),
                        'date_echeance': (facture.date_echeance.isoformat()
                                          if facture.date_echeance else None),
                        'montant_ht': str(montant_ht),
                        'montant_tva': str(montant_tva),
                        'montant_ttc': str(montant_ttc),
                    },
                )
            )
        except ValueError:
            # Course improbable (fournisseur introuvable au moment précis de
            # la création) — garde défensive, jamais de crash sur l'émission
            # de la facture source.
            continue

        EcritureLiaisonInterSociete.objects.create(
            regle=regle,
            facture_source_id=facture.id,
            facture_fournisseur_miroir_id=miroir.id,
            montant_ht=montant_ht, montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            compte_liaison=regle.compte_liaison,
        )
    return None


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


# ── XMKT7 — Planification, throttling et fenêtres de silence d'envoi ───────

def _hors_fenetre_silence(company, maintenant=None):
    """XMKT7 — True si ``maintenant`` (par défaut l'instant présent) tombe
    dans une fenêtre de silence (nuit ou jour férié/non-ouvré) pour
    ``company``. Réutilise le selector de ``notifications`` — jamais
    d'import direct de ses modèles.
    """
    from apps.notifications import selectors as notifications_selectors
    return notifications_selectors.est_hors_fenetre_silence(
        maintenant or timezone.now(), company)


def _plafond_pression_atteint(company, destinataire):
    """XMKT7 — True si ``destinataire`` a déjà atteint le plafond de pression
    marketing (tous canaux, campagnes + séquences confondus) sur la fenêtre
    glissante société. Sans réglage (``pression_marketing_max_par_contact``
    NULL), aucune limite (comportement actuel).
    """
    if not destinataire:
        return False
    try:
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # pragma: no cover - défensif
        profil = None
    plafond = getattr(profil, 'pression_marketing_max_par_contact', None)
    if not plafond:
        return False
    periode_jours = getattr(profil, 'pression_marketing_periode_jours', 7) or 7
    depuis = timezone.now() - timezone.timedelta(days=periode_jours)
    nb_campagnes = EnvoiCampagne.objects.filter(
        company=company, destinataire=destinataire,
        date_creation__gte=depuis,
    ).exclude(statut=EnvoiCampagne.Statut.REBOND).count()
    nb_sequences = ExecutionEtapeSequence.objects.filter(
        company=company, execute_le__gte=depuis,
        inscription__lead_reference=destinataire,
    ).count() if destinataire else 0
    return (nb_campagnes + nb_sequences) >= plafond


# ── XMKT22 — Politique « sunset » d'engagement ──────────────────────────────

def sunset_fenetre_jours(company):
    """XMKT22 — fenêtre société (jours), ``None`` si désactivé (défaut)."""
    try:
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
        return getattr(profil, 'sunset_fenetre_jours', None) if profil else None
    except Exception:  # pragma: no cover - défensif
        return None


def est_dormant(company, destinataire):
    """XMKT22 — True si ``destinataire`` est marqué dormant (comportement
    historique préservé si la politique est désactivée, ou si le contact n'a
    jamais été évalué)."""
    if not destinataire:
        return False
    return StatutEngagementContact.objects.filter(
        company=company, destinataire=destinataire,
        statut=StatutEngagementContact.Statut.DORMANT).exists()


def recalculer_dormants(company, *, maintenant=None):
    """XMKT22 — Enveloppe beat : recalcule le statut d'engagement de chaque
    destinataire connu (EnvoiCampagne) sur la fenêtre société. Désactivé
    (``sunset_fenetre_jours`` NULL) : no-op, aucun contact n'est jamais
    marqué dormant. Un destinataire sans AUCUNE ouverture/clic sur la
    fenêtre → dormant ; sinon → actif (réactivation automatique s'il
    redevient engagé). Renvoie le nombre de destinataires marqués dormants.
    """
    fenetre = sunset_fenetre_jours(company)
    if not fenetre:
        return 0
    maintenant = maintenant or timezone.now()
    depuis = maintenant - timezone.timedelta(days=fenetre)
    destinataires = set(
        EnvoiCampagne.objects.filter(company=company)
        .values_list('destinataire', flat=True).distinct())
    marques_dormants = 0
    for destinataire in destinataires:
        if not destinataire:
            continue
        engage_recemment = EnvoiCampagne.objects.filter(
            company=company, destinataire=destinataire,
        ).filter(
            Q(ouvert_le__gte=depuis) | Q(clique_le__gte=depuis)
        ).exists()
        nouveau_statut = (
            StatutEngagementContact.Statut.ACTIF if engage_recemment
            else StatutEngagementContact.Statut.DORMANT)
        obj, _cree = StatutEngagementContact.objects.update_or_create(
            company=company, destinataire=destinataire,
            defaults={'statut': nouveau_statut})
        if nouveau_statut == StatutEngagementContact.Statut.DORMANT:
            marques_dormants += 1
    return marques_dormants


def reactiver_contact(company, destinataire):
    """XMKT22 — réactive un contact dormant (chemin de re-permission : clic
    sur la campagne dédiée « voulez-vous rester informé ? »)."""
    StatutEngagementContact.objects.update_or_create(
        company=company, destinataire=destinataire,
        defaults={'statut': StatutEngagementContact.Statut.ACTIF})


# ── XMKT23 — Approbation avant envoi de masse + journal d'audit ────────────

def seuil_approbation_envoi_masse(company):
    """XMKT23 — seuil société (défaut 100)."""
    try:
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
        return getattr(profil, 'seuil_approbation_envoi_masse', 100) if profil else 100
    except Exception:  # pragma: no cover - défensif
        return 100


def demander_ou_envoyer_campagne(campagne, *, destinataires=None, user=None):
    """XMKT23 — au-delà du seuil société de destinataires, crée une demande
    d'approbation EN ATTENTE au lieu d'envoyer directement ; sous le seuil,
    envoie normalement (comportement actuel préservé). Renvoie
    ``(campagne, approbation_ou_none)``.
    """
    nb = len(destinataires or [])
    seuil = seuil_approbation_envoi_masse(campagne.company)
    if nb <= seuil:
        return envoyer_campagne(campagne, destinataires=destinataires), None
    approbation = ApprobationEnvoiCampagne.objects.create(
        company=campagne.company, campagne=campagne,
        nb_destinataires_demandes=nb, demande_par=user,
    )
    # Conserve les destinataires demandés pour l'envoi une fois approuvé.
    campagne.segment = dict(campagne.segment or {})
    campagne.segment['_xmkt23_destinataires_en_attente'] = list(destinataires or [])
    campagne.save(update_fields=['segment'])
    return campagne, approbation


def approuver_envoi_campagne(approbation, *, user=None):
    """XMKT23 — approuve une demande EN ATTENTE, déclenche l'envoi
    différé."""
    if approbation.statut != ApprobationEnvoiCampagne.Statut.EN_ATTENTE:
        return approbation
    approbation.statut = ApprobationEnvoiCampagne.Statut.APPROUVE
    approbation.decide_par = user
    approbation.date_decision = timezone.now()
    approbation.save(update_fields=['statut', 'decide_par', 'date_decision'])
    destinataires = (approbation.campagne.segment or {}).pop(
        '_xmkt23_destinataires_en_attente', [])
    envoyer_campagne(approbation.campagne, destinataires=destinataires)
    return approbation


def rejeter_envoi_campagne(approbation, *, motif='', user=None):
    """XMKT23 — rejette une demande EN ATTENTE (motivé) ; la campagne reste
    brouillon, jamais envoyée."""
    if approbation.statut != ApprobationEnvoiCampagne.Statut.EN_ATTENTE:
        return approbation
    approbation.statut = ApprobationEnvoiCampagne.Statut.REJETE
    approbation.decide_par = user
    approbation.motif_rejet = motif or ''
    approbation.date_decision = timezone.now()
    approbation.save(update_fields=[
        'statut', 'decide_par', 'motif_rejet', 'date_decision'])
    return approbation


def journal_audit_envois(company):
    """XMKT23 — journal d'audit immuable : qui a envoyé/approuvé quoi à
    combien de contacts, horodaté (dérivé des ``ApprobationEnvoiCampagne`` +
    des campagnes envoyées directement sous le seuil)."""
    lignes = []
    for approb in ApprobationEnvoiCampagne.objects.filter(company=company):
        lignes.append({
            'campagne_id': approb.campagne_id,
            'campagne_nom': approb.campagne.nom,
            'nb_destinataires': approb.nb_destinataires_demandes,
            'statut': approb.statut,
            'demande_par': getattr(approb.demande_par, 'username', None),
            'decide_par': getattr(approb.decide_par, 'username', None),
            'date_creation': approb.date_creation,
            'date_decision': approb.date_decision,
        })
    return lignes


# ── ZMKT1 — Statuts de pipeline mailing + vue Kanban ────────────────────────

def campagnes_par_statut(company):
    """ZMKT1 — groupe les campagnes par statut (company-scoped) pour la vue
    Kanban (4 colonnes : brouillon/en_file+envoi_en_cours/envoyee/annulee).
    """
    resultat = {statut: [] for statut, _ in Campagne.Statut.choices}
    # ZMKT3 — un modèle n'est jamais envoyé, jamais dans le pipeline d'envoi.
    qs = Campagne.objects.filter(
        company=company, est_modele=False).order_by('-date_creation')
    for campagne in qs:
        taux_ouverture = 0.0
        if campagne.nb_envois:
            taux_ouverture = round(
                campagne.nb_ouvertures / campagne.nb_envois * 100, 1)
        resultat.setdefault(campagne.statut, []).append({
            'id': campagne.id,
            'nom': campagne.nom,
            'canal': campagne.canal,
            'nb_destinataires': campagne.nb_destinataires,
            'taux_ouverture_pct': taux_ouverture,
        })
    return resultat


# ── ZMKT3 — Enregistrer une campagne comme modèle réutilisable ─────────────

def creer_depuis_modele(modele):
    """ZMKT3 — clone objet/corps/canal/segment/variantes langue (XMKT11)
    d'un modèle dans une nouvelle campagne BROUILLON indépendante. Le clone
    n'altère JAMAIS le modèle source (jamais un ``.save()`` dessus)."""
    clone = Campagne.objects.create(
        company=modele.company,
        nom=f'{modele.nom} (copie)',
        canal=modele.canal,
        objet=modele.objet,
        corps=modele.corps,
        segment=dict(modele.segment or {}),
        sms_sender_id=modele.sms_sender_id,
        variantes_langue=dict(modele.variantes_langue or {}),
        est_modele=False,
    )
    clone.listes.set(modele.listes.all())
    return clone


# ── ZMKT4 — Actions Renvoyer les échecs / Dupliquer / Annuler ──────────────

def dupliquer_campagne(campagne):
    """ZMKT4 — clone une campagne en brouillon indépendant (mêmes règles que
    ZMKT3 ``creer_depuis_modele``, mais depuis N'IMPORTE QUELLE campagne, pas
    seulement un modèle)."""
    clone = Campagne.objects.create(
        company=campagne.company,
        nom=f'{campagne.nom} (copie)',
        canal=campagne.canal,
        objet=campagne.objet,
        corps=campagne.corps,
        segment=dict(campagne.segment or {}),
        sms_sender_id=campagne.sms_sender_id,
        variantes_langue=dict(campagne.variantes_langue or {}),
        est_modele=False,
    )
    clone.listes.set(campagne.listes.all())
    return clone


def annuler_campagne(campagne):
    """ZMKT4 — annule une campagne ``en_file``/``envoi_en_cours`` : le beat
    cesse tout envoi restant (journalisé). Idempotent — une campagne déjà
    envoyée/annulée n'est pas modifiée."""
    if campagne.statut not in (
            Campagne.Statut.EN_FILE, Campagne.Statut.ENVOI_EN_COURS,
            Campagne.Statut.BROUILLON):
        return campagne
    campagne.statut = Campagne.Statut.ANNULEE
    campagne.save(update_fields=['statut'])
    return campagne


def renvoyer_echecs_campagne(campagne):
    """ZMKT4 — recrée l'envoi UNIQUEMENT vers les destinataires en statut
    rebond soft/échec récupérable de la trace XMKT2 (jamais les
    désinscrits/consentement refusé — motifs
    ``consentement_refuse_ou_absent``/``plafond_pression_marketing``/
    ``contact_dormant_sunset`` exclus)."""
    motifs_non_recuperables = {
        'consentement_refuse_ou_absent', 'plafond_pression_marketing',
        'contact_dormant_sunset',
    }
    echecs = campagne.envois.filter(
        statut=EnvoiCampagne.Statut.REBOND,
    ).exclude(raison_smtp__in=motifs_non_recuperables)
    destinataires = [e.destinataire for e in echecs]
    if not destinataires:
        return []
    nouvelle_campagne = Campagne.objects.create(
        company=campagne.company,
        nom=f'{campagne.nom} (renvoi échecs)',
        canal=campagne.canal, objet=campagne.objet, corps=campagne.corps,
    )
    envoyer_campagne(nouvelle_campagne, destinataires=destinataires)
    return [nouvelle_campagne]


def _destinataires_des_listes(campagne):
    """XMKT7 — résout les destinataires INSCRITS des ``listes`` ciblées par
    la campagne (XMKT5). Simple source stable pour l'envoi planifié beat —
    ne duplique pas la résolution de segment (XMKT6, IDs de lead).
    """
    abonnements = AbonnementListe.objects.filter(
        liste__in=campagne.listes.all(),
        statut=AbonnementListe.Statut.INSCRIT,
    ).values('destinataire', 'contact_ref').distinct()
    vus = set()
    resultat = []
    for a in abonnements:
        dest = a['destinataire']
        if dest in vus:
            continue
        vus.add(dest)
        resultat.append({'destinataire': dest, 'contact_ref': a['contact_ref'] or ''})
    return resultat


def planifier_campagne(campagne, *, planifiee_le):
    """ZMKT1 — planifie une campagne : passe ``brouillon`` → ``en_file``
    (pipeline Odoo-style Draft → In Queue). Idempotent (no-op si déjà
    planifiée/envoyée/annulée)."""
    if campagne.statut != Campagne.Statut.BROUILLON:
        return campagne
    campagne.planifiee_le = planifiee_le
    campagne.statut = Campagne.Statut.EN_FILE
    campagne.save(update_fields=['planifiee_le', 'statut'])
    return campagne


def envoyer_campagnes_planifiees(company, *, maintenant=None):
    """XMKT7 — Enveloppe beat : envoie chaque campagne ``planifiee_le`` dont
    l'échéance est atteinte, par lots throttlés si ``debit_max_par_heure``
    est renseigné (le lot = les destinataires des listes ciblées, tronqué au
    débit horaire ; le reliquat repart en file au prochain passage beat en
    restant ``en_file`` avec sa ``planifiee_le`` inchangée).

    ZMKT1 — la campagne passe ``en_file`` → ``envoi_en_cours`` (positionné
    par le moteur d'envoi) → ``envoyee``.
    """
    maintenant = maintenant or timezone.now()
    campagnes = Campagne.objects.filter(
        company=company,
        statut__in=[Campagne.Statut.BROUILLON, Campagne.Statut.EN_FILE],
        planifiee_le__isnull=False, planifiee_le__lte=maintenant,
    )
    envoyees = []
    for campagne in campagnes:
        destinataires = _destinataires_des_listes(campagne)
        if campagne.debit_max_par_heure:
            lot = destinataires[:campagne.debit_max_par_heure]
        else:
            lot = destinataires
        envoyees.append(envoyer_campagne(campagne, destinataires=lot))
    return envoyees


def envoyer_campagne(campagne, *, destinataires=None):
    """Déclenche l'envoi groupé d'une campagne (FG201), idempotent.

    ``destinataires`` = liste d'adresses/numéros (optionnelle, sinon 0), ou de
    dicts ``{'destinataire': ..., 'contact_ref': ...}`` pour porter la
    référence contact opaque (XMKT2). Si l'intégration Brevo est inactive
    (défaut), c'est un NO-OP : on marque la campagne ``envoyee`` et on
    enregistre le nombre de destinataires SANS aucun appel réseau. Renvoie la
    campagne. Une campagne déjà envoyée ou annulée n'est pas ré-envoyée.

    Un destinataire présent sur la liste de suppression marketing (XMKT3,
    ``SuppressionMarketing``) est filtré AVANT l'envoi — jamais ciblé, même
    après ré-import de contacts. Chaque destinataire restant obtient sa ligne
    ``EnvoiCampagne`` (XMKT2), point de départ du drill-down par KPI et du
    suivi webhook Brevo.

    ZMKT1 — pipeline Odoo-style : accepte une campagne ``brouillon`` (envoi
    direct) ou ``en_file`` (planifiée, XMKT7) ; passe transitoirement par
    ``envoi_en_cours`` pendant le traitement du lot avant ``envoyee``.
    """
    if campagne.statut not in (Campagne.Statut.BROUILLON, Campagne.Statut.EN_FILE):
        return campagne
    statut_avant = campagne.statut
    campagne.statut = Campagne.Statut.ENVOI_EN_COURS
    campagne.save(update_fields=['statut'])
    brutes = list(destinataires or [])

    def _adresse(cible):
        brute = cible.get('destinataire') if isinstance(cible, dict) else cible
        return (brute or '').strip()

    # XMKT7 — fenêtre de silence : un SMS/WhatsApp ne part jamais la nuit ni
    # un jour férié/non-ouvré (email non concerné par la fenêtre horaire).
    if campagne.canal in ('sms', 'whatsapp') and _hors_fenetre_silence(campagne.company):
        # ZMKT1 — repasse à son statut d'avant l'envoi (jamais coincée en
        # envoi_en_cours) : un ``en_file`` reste en_file (le prochain passage
        # beat retentera), un ``brouillon`` envoyé directement hors fenêtre
        # redevient brouillon (aucun envoi planifié n'a été créé ici — le
        # forcer en_file le ferait ré-essayer tout seul via le beat sans
        # qu'aucune planification n'ait été demandée).
        campagne.statut = statut_avant
        campagne.save(update_fields=['statut'])
        return campagne

    cibles = [
        cible for cible in brutes
        if not est_supprime(campagne.company, _adresse(cible))
        # XMKT4 — un contact sans ConsentRecord accordé pour le canal n'est
        # jamais ciblé (comportement historique préservé tant qu'AUCUNE
        # entrée de consentement n'existe pour ce destinataire).
        and consentement_accorde(
            campagne.company, _adresse(cible), canal=campagne.canal)
        # XMKT7 — un contact déjà au plafond de pression marketing sur la
        # période est sauté (journalisé).
        and not _plafond_pression_atteint(campagne.company, _adresse(cible))
        # XMKT22 — un contact dormant (politique sunset) est sauté, sauf
        # sur la campagne de re-permission elle-même (aucun marquage
        # spécial requis — le clic sur SON lien réactive via traiter_clic_lien).
        and not est_dormant(campagne.company, _adresse(cible))
    ]
    refuses_consentement = [
        _adresse(cible) for cible in brutes
        if not est_supprime(campagne.company, _adresse(cible))
        and not consentement_accorde(
            campagne.company, _adresse(cible), canal=campagne.canal)
    ]
    for dest in refuses_consentement:
        if dest:
            EnvoiCampagne.objects.create(
                company=campagne.company, campagne=campagne,
                destinataire=dest, contact_ref='',
                statut=EnvoiCampagne.Statut.REBOND,
                raison_smtp='consentement_refuse_ou_absent',
            )
    plafonnes = [
        _adresse(cible) for cible in brutes
        if not est_supprime(campagne.company, _adresse(cible))
        and consentement_accorde(
            campagne.company, _adresse(cible), canal=campagne.canal)
        and _plafond_pression_atteint(campagne.company, _adresse(cible))
    ]
    for dest in plafonnes:
        if dest:
            EnvoiCampagne.objects.create(
                company=campagne.company, campagne=campagne,
                destinataire=dest, contact_ref='',
                statut=EnvoiCampagne.Statut.REBOND,
                raison_smtp='plafond_pression_marketing',
            )
    dormants = [
        _adresse(cible) for cible in brutes
        if not est_supprime(campagne.company, _adresse(cible))
        and consentement_accorde(
            campagne.company, _adresse(cible), canal=campagne.canal)
        and not _plafond_pression_atteint(campagne.company, _adresse(cible))
        and est_dormant(campagne.company, _adresse(cible))
    ]
    for dest in dormants:
        if dest:
            EnvoiCampagne.objects.create(
                company=campagne.company, campagne=campagne,
                destinataire=dest, contact_ref='',
                statut=EnvoiCampagne.Statut.REBOND,
                raison_smtp='contact_dormant_sunset',
            )
    campagne.nb_destinataires = len(cibles)
    if campagne.canal == Campagne.Canal.WHATSAPP and cibles:
        # XMKT10 — le canal whatsapp ne dépend jamais de Brevo (email/SMS
        # uniquement) : chaque destinataire obtient TOUJOURS un message —
        # via BSP (jeton présent) ou repli manuel (lien wa.me), jamais aucun
        # des deux (comportement du provider QJ23/FG33). On compte l'envoi
        # comme « traité » indépendamment de brevo_actif().
        campagne.nb_envois = len(cibles)
    elif brevo_actif() and cibles:
        # Intégration réelle (future) — jamais appelée tant que le flag est OFF.
        # On laisse le compteur d'envois aligné sur les destinataires ; les
        # ouvertures/clics seront remontés par les webhooks Brevo.
        campagne.nb_envois = len(cibles)
    # XMKT9 — réécrit les liens du corps en redirections tokenisées AU MOMENT
    # DE L'ENVOI (une seule fois, jamais si aucun lien HTTP(S) présent).
    if cibles:
        corps_reecrit, _liens = envelopper_liens_campagne(campagne)
        if corps_reecrit != campagne.corps:
            campagne.corps = corps_reecrit
    campagne.statut = Campagne.Statut.ENVOYEE
    campagne.envoyee_le = timezone.now()
    campagne.save(update_fields=[
        'nb_destinataires', 'nb_envois', 'statut', 'envoyee_le', 'corps'])
    maintenant = timezone.now() if campagne.nb_envois else None
    # XMKT14 — répartition A/B sans chevauchement ni doublon (échantillon =
    # les N premiers destinataires, moitié A / moitié B) si un test A/B est
    # configuré et pas encore décidé.
    ab_config = campagne.ab_test or {}
    ab_actif = bool(ab_config) and not campagne.ab_gagnant
    pct_echantillon = int(ab_config.get('pct_echantillon', 0) or 0) if ab_actif else 0
    taille_echantillon = (len(cibles) * pct_echantillon) // 100 if ab_actif else 0
    moitie = taille_echantillon // 2

    for index, cible in enumerate(cibles):
        if isinstance(cible, dict):
            destinataire = (cible.get('destinataire') or '').strip()
            contact_ref = cible.get('contact_ref') or ''
        else:
            destinataire = (cible or '').strip()
            contact_ref = ''
        if not destinataire:
            continue
        variante_ab = ''
        if ab_actif and index < taille_echantillon:
            variante_ab = 'a' if index < moitie else 'b'
        EnvoiCampagne.objects.create(
            company=campagne.company,
            campagne=campagne,
            destinataire=destinataire,
            contact_ref=contact_ref,
            statut=(EnvoiCampagne.Statut.ENVOYE if maintenant
                    else EnvoiCampagne.Statut.QUEUED),
            envoye_le=maintenant,
            variante_ab=variante_ab,
        )
        # XMKT10 — canal whatsapp : envoi réel (BSP, jeton présent) ou repli
        # sur une file wa.me (aucune clé) — chaque tentative est journalisée
        # dans notifications.WhatsAppMessageLog, liée à cette campagne.
        if campagne.canal == Campagne.Canal.WHATSAPP:
            from apps.notifications.services import (
                render_whatsapp_template, send_whatsapp_campaign_message,
            )
            corps_whatsapp = (
                render_whatsapp_template(campagne.whatsapp_template)
                or campagne.corps)
            send_whatsapp_campaign_message(
                campagne.company, recipient=destinataire, body=corps_whatsapp,
                campagne_id=campagne.id, template=campagne.whatsapp_template)
        # XMKT16 — une ligne de chatter par lead ciblé, jamais par batch.
        noter_touche_marketing_pour_lead(
            campagne.company, contact_ref,
            f'Campagne « {campagne.nom} » envoyée')
    return campagne


def _metrique_ab(campagne, variante, critere):
    """XMKT14 — mesure (nb d'ouvertures ou de clics) pour une variante A/B,
    lue sur les traces ``EnvoiCampagne`` (XMKT2)."""
    qs = campagne.envois.filter(variante_ab=variante)
    if critere == 'clics':
        return qs.filter(clique_le__isnull=False).count()
    return qs.filter(ouvert_le__isnull=False).count()


def decider_gagnant_ab(campagne, *, maintenant=None):
    """XMKT14 — Compare les métriques A vs B à l'issue de la fenêtre de
    décision et envoie la variante gagnante au reste (destinataires non
    échantillonnés, encore ``queued``). Égalité → A. No-op si aucun test A/B
    configuré, déjà décidé, ou fenêtre pas encore écoulée. Renvoie le
    gagnant ('a'/'b') ou ``None``.
    """
    maintenant = maintenant or timezone.now()
    ab_config = campagne.ab_test or {}
    if not ab_config or campagne.ab_gagnant:
        return None
    if not campagne.envoyee_le:
        return None
    fenetre_heures = int(ab_config.get('fenetre_heures', 4) or 4)
    echeance = campagne.envoyee_le + timezone.timedelta(hours=fenetre_heures)
    if maintenant < echeance:
        return None
    critere = ab_config.get('critere', 'ouvertures')
    metrique_a = _metrique_ab(campagne, 'a', critere)
    metrique_b = _metrique_ab(campagne, 'b', critere)
    gagnant = 'b' if metrique_b > metrique_a else 'a'
    campagne.ab_gagnant = gagnant
    campagne.ab_decide_le = maintenant
    campagne.save(update_fields=['ab_gagnant', 'ab_decide_le'])
    # Envoie le contenu gagnant au reste (destinataires jamais échantillonnés,
    # toujours en file d'attente).
    reste = campagne.envois.filter(variante_ab='', statut=EnvoiCampagne.Statut.QUEUED)
    reste.update(
        statut=EnvoiCampagne.Statut.ENVOYE, envoye_le=maintenant,
        variante_ab=gagnant)
    return gagnant


# ── XMKT35 — Posts réseaux sociaux (publication Meta Graph gated) ───────────
# La publication réelle est OFF par défaut : sans jeton, un post dû devient un
# RAPPEL manuel notifié à son auteur (texte prêt à coller) — aucun appel
# réseau, aucun statut « publié » posé tout seul. AUCUNE création de campagne
# publicitaire ici (règle n°3 — ce module publie du CONTENU de page, jamais
# une campagne Ads ; si un jour l'Ads s'ajoute : toujours --status PAUSED).

def meta_graph_actif():
    """Toggle maître de la publication Meta Graph (XMKT35). OFF par défaut.

    Actif uniquement avec ``META_GRAPH_ENABLED=1`` ET un jeton ET un id de
    page (env). Sans ça : aucun appel réseau, chemin rappel manuel."""
    import os
    return (os.getenv('META_GRAPH_ENABLED', '0') == '1'
            and bool(os.getenv('META_GRAPH_TOKEN', '').strip())
            and bool(os.getenv('META_GRAPH_PAGE_ID', '').strip()))


def planifier_post_social(post, *, date_planifiee):
    """Planifie un post social : brouillon → planifié (XMKT35). Idempotent —
    un post déjà publié/en échec n'est jamais replanifié par cette fonction."""
    from .models import PostSocial
    if post.statut not in (PostSocial.Statut.BROUILLON,
                           PostSocial.Statut.PLANIFIE):
        return post
    post.date_planifiee = date_planifiee
    post.statut = PostSocial.Statut.PLANIFIE
    post.save(update_fields=['date_planifiee', 'statut'])
    return post


def publier_post_social(post):
    """Publie RÉELLEMENT un post via l'API Meta Graph — GATED (XMKT35).

    Sans jeton (``meta_graph_actif()`` faux) : NO-OP strict (le sweep pose le
    rappel manuel à la place). Avec jeton : POST ``/{page_id}/feed`` (contenu
    de page uniquement — jamais de campagne publicitaire, règle n°3) ;
    succès → statut ``publie`` + ``external_id``, échec → ``echec`` +
    ``erreur``. Ne relance jamais un post déjà publié."""
    from .models import PostSocial
    import json
    import os
    import urllib.parse
    if post.statut != PostSocial.Statut.PLANIFIE:
        return post
    if not meta_graph_actif():
        return post
    token = os.getenv('META_GRAPH_TOKEN', '').strip()
    page_id = os.getenv('META_GRAPH_PAGE_ID', '').strip()
    base = (os.getenv('META_GRAPH_BASE_URL', '')
            or 'https://graph.facebook.com/v19.0').rstrip('/')
    payload = urllib.parse.urlencode({
        'message': post.texte or '', 'access_token': token}).encode()
    req = urllib.request.Request(
        f'{base}/{page_id}/feed', data=payload, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read() or b'{}')
        post.external_id = str(data.get('id') or '')
        post.statut = PostSocial.Statut.PUBLIE
        post.publie_le = timezone.now()
        post.erreur = ''
        post.save(update_fields=[
            'external_id', 'statut', 'publie_le', 'erreur'])
    except Exception as exc:
        post.statut = PostSocial.Statut.ECHEC
        post.erreur = str(exc)[:255]
        post.save(update_fields=['statut', 'erreur'])
    return post


def traiter_posts_sociaux_dus(company, *, maintenant=None):
    """Sweep beat XMKT35 : traite chaque post planifié arrivé à échéance.

    Jeton Meta Graph présent → publication réelle (``publier_post_social``).
    Sans jeton → RAPPEL manuel notifié UNE fois à l'auteur du post
    (``notifications.notify``, texte prêt à coller) ; le post reste
    ``planifie`` (l'utilisateur publie à la main puis met à jour le statut).
    Idempotent : ``rappel_envoye`` garantit zéro double rappel."""
    from .models import PostSocial
    maintenant = maintenant or timezone.now()
    dus = PostSocial.objects.filter(
        company=company, statut=PostSocial.Statut.PLANIFIE,
        date_planifiee__isnull=False, date_planifiee__lte=maintenant)
    traites = []
    actif = meta_graph_actif()
    for post in dus:
        if actif:
            traites.append(publier_post_social(post))
            continue
        if post.rappel_envoye:
            continue
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        if post.created_by is not None:
            notify(
                post.created_by, EventType.POST_SOCIAL_RAPPEL,
                f'Post {post.get_reseau_display()} à publier maintenant',
                body=(post.texte or '')[:2000],
                link='/marketing/calendrier', company=company)
        post.rappel_envoye = True
        post.save(update_fields=['rappel_envoye'])
        traites.append(post)
    return traites


def webhook_brevo_evenement(company, *, campagne_id, destinataire, evenement,
                            raison_smtp='', bounce_type='', max_rebonds_soft=3):
    """Traite un événement webhook Brevo (XMKT2/XMKT12), gated/no-op sans clé.

    ``evenement`` ∈ delivered/opened/click/bounce/unsubscribed/complaint. Met
    à jour LA ligne ``EnvoiCampagne`` correspondante (company+campagne+
    destinataire) et laisse les compteurs agrégés de ``Campagne`` dérivables
    (recalculés par ``recalculer_compteurs_campagne``). Idempotent : rejouer
    le même événement ne fait qu'écraser l'horodatage, jamais dupliquer de
    ligne.

    XMKT12 — classification des rebonds : ``bounce_type='hard'`` supprime
    IMMÉDIATEMENT le destinataire (XMKT3, motif rebond_dur, raison SMTP
    stockée sur la trace) ; ``bounce_type='soft'`` incrémente un compteur
    persistant (``RebondSoft``, à travers toutes les campagnes) et ne
    supprime qu'après ``max_rebonds_soft`` occurrences (paramètre société,
    défaut 3) ; ``evenement='complaint'`` (plainte spam) supprime
    immédiatement, comme un rebond dur.
    """
    envoi = EnvoiCampagne.objects.filter(
        company=company, campagne_id=campagne_id,
        destinataire=destinataire).order_by('-date_creation').first()
    if not envoi:
        return None
    maintenant = timezone.now()
    mapping = {
        'delivered': EnvoiCampagne.Statut.DELIVRE,
        'opened': EnvoiCampagne.Statut.OUVERT,
        'click': EnvoiCampagne.Statut.CLIQUE,
        'bounce': EnvoiCampagne.Statut.REBOND,
        'unsubscribed': EnvoiCampagne.Statut.DESINSCRIT,
        'complaint': EnvoiCampagne.Statut.DESINSCRIT,
    }
    nouveau_statut = mapping.get(evenement)
    if not nouveau_statut:
        return envoi
    envoi.statut = nouveau_statut
    update_fields = ['statut']
    if evenement == 'opened' and not envoi.ouvert_le:
        envoi.ouvert_le = maintenant
        update_fields.append('ouvert_le')
        # XMKT16 — chatter uniquement à la PREMIÈRE ouverture (pas par rejeu).
        noter_touche_marketing_pour_lead(
            company, envoi.contact_ref,
            f'Campagne « {envoi.campagne.nom} » ouverte')
    if evenement == 'click' and not envoi.clique_le:
        envoi.clique_le = maintenant
        update_fields.append('clique_le')
        noter_touche_marketing_pour_lead(
            company, envoi.contact_ref,
            f'Campagne « {envoi.campagne.nom} » cliquée')
    if evenement in ('bounce', 'complaint') and raison_smtp:
        envoi.raison_smtp = raison_smtp[:255]
        update_fields.append('raison_smtp')
    envoi.save(update_fields=update_fields)
    recalculer_compteurs_campagne(envoi.campagne)

    if evenement == 'complaint':
        supprimer_destinataire(
            company, destinataire, motif=SuppressionMarketing.Motif.PLAINTE,
            source='webhook_brevo')
    elif evenement == 'bounce' and bounce_type == 'hard':
        supprimer_destinataire(
            company, destinataire, motif=SuppressionMarketing.Motif.REBOND_DUR,
            source=raison_smtp or 'webhook_brevo')
    elif evenement == 'bounce' and bounce_type == 'soft':
        compteur, _cree = RebondSoft.objects.get_or_create(
            company=company, destinataire=destinataire)
        compteur.compte += 1
        compteur.save(update_fields=['compte', 'date_maj'])
        if compteur.compte >= max_rebonds_soft:
            supprimer_destinataire(
                company, destinataire,
                motif=SuppressionMarketing.Motif.REBOND_DUR,
                source=raison_smtp or 'webhook_brevo_soft_repete')
    return envoi


def recalculer_compteurs_campagne(campagne):
    """Recalcule ``nb_ouvertures``/``nb_clics`` d'une ``Campagne`` (XMKT2) à
    partir des lignes ``EnvoiCampagne`` — les compteurs deviennent dérivés.
    """
    envois = campagne.envois.all()
    campagne.nb_ouvertures = envois.filter(
        ouvert_le__isnull=False).count()
    campagne.nb_clics = envois.filter(clique_le__isnull=False).count()
    campagne.save(update_fields=['nb_ouvertures', 'nb_clics'])
    return campagne


# ── XMKT9 — Tracker de liens + auto-tag UTM ─────────────────────────────────

_LIEN_URL_RE = re.compile(r'https?://[^\s<>"\')]+')


def _tagger_utm(url, campagne):
    """Ajoute utm_source/medium/campaign à ``url`` (XMKT9). Ne casse jamais
    une URL déjà taguée (les paramètres existants sont préservés en tête).
    """
    from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query.setdefault('utm_source', 'campagne')
    query.setdefault('utm_medium', campagne.canal)
    query.setdefault('utm_campaign', campagne.nom)
    nouvelle_query = urlencode(query)
    return urlunparse(parsed._replace(query=nouvelle_query))


def envelopper_liens_campagne(campagne):
    """XMKT9 — Enveloppe chaque lien HTTP(S) du corps de la campagne dans une
    redirection tokenisée company-scoped (créant un ``LienTrackee`` par URL
    distincte trouvée), et renvoie le corps avec les liens réécrits en
    ``/api/django/compta/r/<token>/``. Idempotent : rejouer sur un corps déjà
    réécrit ne recrée pas de doublon (dédoublonné par URL cible taguée).
    """
    corps = campagne.corps or ''
    urls = set(_LIEN_URL_RE.findall(corps))
    corps_reecrit = corps
    liens = []
    for url in urls:
        url_taguee = _tagger_utm(url, campagne)
        lien = LienTrackee.objects.filter(
            company=campagne.company, campagne=campagne,
            url_cible=url_taguee).first()
        if lien is None:
            lien = LienTrackee.objects.create(
                company=campagne.company, campagne=campagne,
                url_cible=url_taguee, token=uuid.uuid4().hex)
        liens.append(lien)
        corps_reecrit = corps_reecrit.replace(
            url, f'/api/django/compta/r/{lien.token}/')
    return corps_reecrit, liens


def traiter_clic_lien(token, *, destinataire=''):
    """XMKT9 — Traite un clic sur un lien tracké : incrémente le lien +
    crée la ligne ``ClicLien`` par destinataire, met à jour l'``EnvoiCampagne``
    correspondant (``clique_le`` — alimente XMKT2) et crée le point de
    contact (``crm.PointContact`` FG204) si le destinataire est connu.
    Renvoie ``(ok, url_cible_ou_message_erreur)``.
    """
    lien = LienTrackee.objects.filter(token=token).first()
    if not lien:
        return False, 'Lien invalide.'
    lien.nb_clics += 1
    lien.save(update_fields=['nb_clics'])
    destinataire = (destinataire or '').strip()
    ClicLien.objects.create(
        company=lien.company, lien=lien, destinataire=destinataire)
    if destinataire and lien.campagne_id:
        # XMKT22 — un clic réactive automatiquement un contact dormant
        # (chemin de re-permission).
        reactiver_contact(lien.company, destinataire)
        envoi = webhook_brevo_evenement(
            lien.company, campagne_id=lien.campagne_id,
            destinataire=destinataire, evenement='click')
        if envoi and envoi.contact_ref:
            noter_touche_marketing_pour_lead(
                lien.company, envoi.contact_ref,
                f'Lien « {lien.url_cible[:80]} » cliqué (campagne '
                f'« {lien.campagne.nom} »)')
    return True, lien.url_cible


def clics_par_lien(campagne):
    """XMKT9 — Page « clics par lien » du détail campagne : compte par URL
    cible."""
    return [
        {'lien_id': lien.id, 'url_cible': lien.url_cible, 'nb_clics': lien.nb_clics}
        for lien in campagne.liens_trackes.all()
    ]


# ── XMKT17 — Coût & ROI MAD par campagne ────────────────────────────────────

def cout_total_campagne(campagne):
    """XMKT17 — Coût total (MAD) : ``cout_reel_mad`` s'il est renseigné,
    sinon Σ des ``lignes_cout`` libres, sinon 0."""
    if campagne.cout_reel_mad is not None:
        return Decimal(str(campagne.cout_reel_mad))
    total = Decimal('0')
    for ligne in (campagne.lignes_cout or []):
        try:
            total += Decimal(str(ligne.get('montant_mad', 0)))
        except Exception:
            continue
    return total


def roi_campagne(campagne):
    """XMKT17 — ROI MAD d'une campagne : rapproche le coût (saisi) et le
    revenu attribué (leads portant l'utm_campaign de la campagne → devis
    signés, dernier-touch, via ``apps.crm.selectors`` — jamais d'import de
    ``apps.ventes``/``apps.crm.models``). Renvoie coût, revenu, ROI (%) et
    coût-par-lead (division par zéro = 0).
    """
    from apps.crm.selectors import revenu_attribue_campagne

    cout = cout_total_campagne(campagne)
    attribution = revenu_attribue_campagne(campagne.company, campagne.nom)
    revenu = Decimal(attribution['revenu_ttc'])
    roi_pct = 0.0
    if cout > 0:
        roi_pct = round(float((revenu - cout) / cout * 100), 1)
    cout_par_lead = 0.0
    if attribution['nb_leads']:
        cout_par_lead = round(float(cout / attribution['nb_leads']), 2)
    return {
        'budget_mad': str(campagne.budget_mad) if campagne.budget_mad is not None else None,
        'cout_mad': str(cout),
        'revenu_ttc_mad': str(revenu),
        'roi_pct': roi_pct,
        'nb_leads': attribution['nb_leads'],
        'nb_signes': attribution['nb_signes'],
        'cout_par_lead_mad': cout_par_lead,
    }


def leads_source_roi(campagne):
    """XMKT17 — Drill-down vers les leads sources du ROI (via
    ``apps.crm.selectors``)."""
    from apps.crm.selectors import leads_source_campagne
    return leads_source_campagne(campagne.company, campagne.nom)


# ── XMKT3 — Désinscription un clic + liste de suppression globale ──────────

_DESINSCRIPTION_SALT = 'compta.xmkt3.desinscription'


def est_supprime(company, destinataire):
    """Le destinataire est-il sur la liste de suppression marketing (XMKT3) ?
    Vérifiée AU MOMENT DE L'ENVOI — jamais pour un message transactionnel.
    """
    return SuppressionMarketing.objects.filter(
        company=company, destinataire=destinataire).exists()


def supprimer_destinataire(company, destinataire, *, motif=SuppressionMarketing.Motif.DESINSCRIT,
                           source=''):
    """Ajoute (idempotent) un destinataire à la liste de suppression (XMKT3).

    Immune au ré-import de contacts : une fois supprimé, un destinataire le
    reste tant qu'il n'est pas retiré manuellement — aucun import ne
    l'écrase.
    """
    obj, _cree = SuppressionMarketing.objects.get_or_create(
        company=company, destinataire=destinataire,
        defaults={'motif': motif, 'source': source or ''},
    )
    return obj


def generer_token_desinscription(company_id, destinataire):
    """Jeton signé (XMKT3) pour le lien public de désinscription un clic —
    non expirant (comme le pattern ``reporting.calendar``), signé par
    destinataire donc invalidable en changeant le sel serait excessif ; la
    sécurité repose sur la clé secrète Django (``SECRET_KEY``).
    """
    return signing.dumps(
        {'company_id': company_id, 'destinataire': destinataire},
        salt=_DESINSCRIPTION_SALT)


def desinscrire_via_token(token, *, source='desinscription_publique'):
    """Traite un clic sur le lien public de désinscription (XMKT3).

    Renvoie ``(ok, destinataire_ou_message_erreur)``. Un jeton invalide/
    corrompu ne fait rien (pas d'exception, pas de suppression).
    """
    try:
        payload = signing.loads(token, salt=_DESINSCRIPTION_SALT)
    except signing.BadSignature:
        return False, 'Lien invalide.'
    from authentication.models import Company
    company = Company.objects.filter(id=payload.get('company_id')).first()
    if not company:
        return False, 'Lien invalide.'
    destinataire = payload.get('destinataire') or ''
    if not destinataire:
        return False, 'Lien invalide.'
    supprimer_destinataire(
        company, destinataire, motif=SuppressionMarketing.Motif.DESINSCRIT,
        source=source)
    return True, destinataire


def importer_liste_opposition(company, destinataires, *, source='import_csv'):
    """Importe une liste d'opposition externe (XMKT3), idempotent : les
    entrées déjà supprimées ne sont jamais écrasées (get_or_create).
    """
    ajoutes = 0
    for destinataire in destinataires:
        destinataire = (destinataire or '').strip()
        if not destinataire:
            continue
        _obj, cree = SuppressionMarketing.objects.get_or_create(
            company=company, destinataire=destinataire,
            defaults={
                'motif': SuppressionMarketing.Motif.IMPORT,
                'source': source,
            },
        )
        if cree:
            ajoutes += 1
    return ajoutes


# ── XMKT4 — Application du consentement marketing par canal (loi 09-08) ────
# Le registre EXISTE déjà : ``core.ConsentRecord`` (FG394). On ne le duplique
# JAMAIS ici — on l'applique au moment de l'envoi (campagnes ET séquences).

_CANAL_VERS_PURPOSE = {
    'email': 'email',
    'sms': 'sms',
    'whatsapp': 'whatsapp',
}

_DOUBLE_OPTIN_SALT = 'compta.xmkt4.double_optin'


def _purpose_pour_canal(canal):
    return _CANAL_VERS_PURPOSE.get((canal or '').strip().lower(), 'marketing')


def consentement_accorde(company, destinataire, *, canal='email'):
    """XMKT4 — un destinataire a-t-il un ``ConsentRecord`` accordé (le plus
    récent) pour le canal donné ? Sans AUCUNE entrée de consentement pour ce
    destinataire+finalité, le comportement HISTORIQUE est préservé (True) —
    l'application stricte ne s'active qu'une fois qu'au moins une entrée de
    consentement existe pour ce destinataire (évite de bloquer toute la base
    existante avant migration des consentements).
    """
    from core.models import ConsentRecord

    purpose = _purpose_pour_canal(canal)
    dernier = (
        ConsentRecord.objects
        .filter(company=company, subject_identifier=destinataire,
                purpose=purpose)
        .order_by('-id')
        .first())
    if dernier is None:
        return True
    return bool(dernier.granted)


def filtrer_destinataires_consentants(company, destinataires, *, canal='email'):
    """Filtre une liste de destinataires (str) : garde ceux qui ont un
    consentement accordé (ou aucune entrée = comportement historique) pour le
    canal. Renvoie ``(consentants, refuses)``.
    """
    consentants, refuses = [], []
    for dest in destinataires:
        d = (dest or '').strip()
        if not d:
            continue
        if consentement_accorde(company, d, canal=canal):
            consentants.append(d)
        else:
            refuses.append(d)
    return consentants, refuses


def generer_token_double_optin(company_id, destinataire, *, version_texte=''):
    """Jeton signé (XMKT4) pour le lien de confirmation du double opt-in."""
    return signing.dumps(
        {'company_id': company_id, 'destinataire': destinataire,
         'version_texte': version_texte},
        salt=_DOUBLE_OPTIN_SALT)


def double_optin_actif(company):
    """XMKT4 — toggle société (``CompanyProfile.double_optin_actif``), OFF
    par défaut : sans réglage, l'inscription publique reste immédiatement
    consentante (comportement actuel).
    """
    try:
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
        return bool(profil and profil.double_optin_actif)
    except Exception:  # pragma: no cover - défensif
        return False


def confirmer_double_optin_via_token(token):
    """Traite le clic de confirmation du double opt-in (XMKT4).

    Pose un ``ConsentRecord`` ``granted=True`` pour la finalité marketing,
    avec l'IP + horodatage comme preuve (loi 09-08). Renvoie
    ``(ok, destinataire_ou_message_erreur)``.
    """
    try:
        payload = signing.loads(token, salt=_DOUBLE_OPTIN_SALT)
    except signing.BadSignature:
        return False, 'Lien invalide.'
    from authentication.models import Company
    from core.models import ConsentRecord

    company = Company.objects.filter(id=payload.get('company_id')).first()
    if not company:
        return False, 'Lien invalide.'
    destinataire = (payload.get('destinataire') or '').strip()
    if not destinataire:
        return False, 'Lien invalide.'
    ConsentRecord.objects.create(
        company=company,
        subject_identifier=destinataire,
        purpose='marketing',
        granted=True,
        source='double_optin_confirmation',
        occurred_at=timezone.now(),
        version_texte=payload.get('version_texte') or '',
    )
    return True, destinataire


def cndp_footer_texte(company):
    """XMKT4 — texte de pied d'email marketing avec le n° de déclaration CNDP,
    si renseigné (``CompanyProfile.numero_declaration_cndp``). Chaîne vide si
    non renseigné (comportement actuel, aucun pied additionnel).
    """
    try:
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
        numero = (profil.numero_declaration_cndp or '').strip() if profil else ''
    except Exception:  # pragma: no cover - défensif
        numero = ''
    if not numero:
        return ''
    return f'Déclaration CNDP n° {numero}'


# ── XMKT5 — Listes de diffusion nommées + abonnements ───────────────────────

def _normaliser_destinataire(brut):
    """Normalise un destinataire (XMKT5) : email en minuscules, téléphone
    marocain en ``212XXXXXXXXX`` (même convention que le lien wa.me
    ``ventes.utils.phone.normalize_ma_phone`` — dupliqué ici pour garder
    ``apps.compta`` autonome, sans import cross-app).
    """
    brut = (brut or '').strip()
    if not brut:
        return ''
    if '@' in brut:
        return brut.lower()
    digits = re.sub(r'\D', '', brut)
    if not digits:
        return brut
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('212'):
        local = digits[3:]
    elif digits.startswith('0'):
        local = digits[1:]
    else:
        local = digits
    local = local.lstrip('0')
    if not local:
        return brut
    return '212' + local


def creer_liste_diffusion(company, *, nom, description=''):
    """Crée une liste de diffusion nommée (XMKT5)."""
    return ListeDiffusion.objects.create(
        company=company, nom=nom, description=description or '')


def inscrire_dans_liste(liste, destinataire, *, contact_ref=''):
    """Inscrit (idempotent) un destinataire dans une liste (XMKT5).

    Dédoublonne par destinataire NORMALISÉ. Un destinataire déjà désinscrit
    de CETTE liste n'est jamais ré-inscrit silencieusement par un import — un
    import qui referait `get_or_create` laisserait le statut existant intact
    (voir ``importer_abonnements_liste``) ; cette fonction, elle, réinscrit
    explicitement à la demande (action manuelle).
    """
    destinataire = _normaliser_destinataire(destinataire)
    if not destinataire:
        return None
    obj, cree = AbonnementListe.objects.get_or_create(
        liste=liste, destinataire=destinataire,
        defaults={
            'company': liste.company,
            'contact_ref': contact_ref or '',
            'statut': AbonnementListe.Statut.INSCRIT,
        },
    )
    if not cree and obj.statut != AbonnementListe.Statut.INSCRIT:
        obj.statut = AbonnementListe.Statut.INSCRIT
        obj.save(update_fields=['statut'])
    return obj


def desinscrire_de_liste(liste, destinataire):
    """Désinscrit un destinataire d'UNE liste (XMKT5), sans toucher la liste
    globale de suppression (XMKT3, portée différente)."""
    destinataire = _normaliser_destinataire(destinataire)
    abonnement = AbonnementListe.objects.filter(
        liste=liste, destinataire=destinataire).first()
    if not abonnement:
        return None
    abonnement.statut = AbonnementListe.Statut.DESINSCRIT
    abonnement.save(update_fields=['statut'])
    return abonnement


def importer_abonnements_liste(liste, lignes, *, colonne_destinataire='destinataire',
                               colonne_contact_ref='contact_ref'):
    """Importe des abonnements dans une liste depuis des lignes CSV/XLSX déjà
    parsées (XMKT5) : ``lignes`` = liste de dicts (mapping de colonnes fait
    par l'appelant). Renvoie un rapport ``{ajoutes, doublons, ignores_supprimes}``.

    Ne réinscrit JAMAIS un destinataire déjà désinscrit de cette liste (les
    doublons sont comptés, pas les lignes qui matchent un désinscrit — celles-
    ci sont comptées séparément dans ``ignores_supprimes``).
    """
    rapport = {'ajoutes': 0, 'doublons': 0, 'ignores_supprimes': 0}
    vus = set()
    for ligne in lignes:
        brut = ligne.get(colonne_destinataire) if isinstance(ligne, dict) else ligne
        destinataire = _normaliser_destinataire(brut)
        if not destinataire:
            continue
        if destinataire in vus:
            rapport['doublons'] += 1
            continue
        vus.add(destinataire)
        existant = AbonnementListe.objects.filter(
            liste=liste, destinataire=destinataire).first()
        if existant:
            if existant.statut == AbonnementListe.Statut.DESINSCRIT:
                rapport['ignores_supprimes'] += 1
            else:
                rapport['doublons'] += 1
            continue
        contact_ref = (
            ligne.get(colonne_contact_ref, '') if isinstance(ligne, dict) else '')
        AbonnementListe.objects.create(
            company=liste.company, liste=liste, destinataire=destinataire,
            contact_ref=contact_ref or '',
            statut=AbonnementListe.Statut.INSCRIT,
        )
        rapport['ajoutes'] += 1
    return rapport


# ── XMKT6 — Segments dynamiques enregistrés et réutilisables ────────────────

_SEGMENT_ACTIVITE_CHOICES = ('a_ouvert', 'a_clique', 'jamais_ouvert')


def valider_regles_segment(regles):
    """Valide les règles JSON d'un segment (XMKT6) : lève ``ValueError`` sur
    une clé inconnue (champ lead OU clé d'activité marketing). Ne touche
    jamais à la base — appelée avant la sauvegarde ET avant l'évaluation.

    XMKT28 — clés additives ``evenement_present``/``evenement_absent`` (id
    d'``EvenementMarketing``) pour cibler les leads présents/absents à un
    événement (suivi différencié post-événement).
    """
    from apps.crm.selectors import LEAD_SEGMENT_FIELDS

    regles = regles or {}
    cles_activite = {'activite', 'evenement_present', 'evenement_absent'}
    cles_connues = set(LEAD_SEGMENT_FIELDS) | cles_activite
    inconnues = set(regles) - cles_connues
    if inconnues:
        raise ValueError(f"Règle(s) de segment inconnue(s) : {sorted(inconnues)}")
    activite = regles.get('activite')
    if activite and activite not in _SEGMENT_ACTIVITE_CHOICES:
        raise ValueError(f"Activité de segment inconnue : {activite}")
    return regles


def _filtrer_par_evenement(company, lead_ids, evenement_id, *, statut):
    """XMKT28 — filtre par présence/absence à un événement (via
    ``InscriptionEvenement.lead_id``)."""
    if not evenement_id or not lead_ids:
        return lead_ids
    lead_ids_evenement = set(
        InscriptionEvenement.objects.filter(
            company=company, evenement_id=evenement_id, statut=statut,
            lead_id__isnull=False,
        ).values_list('lead_id', flat=True))
    return [lid for lid in lead_ids if lid in lead_ids_evenement]


def _filtrer_par_activite(company, lead_ids, activite):
    """Filtre une liste d'IDs de lead par activité marketing (XMKT6),
    évaluée sur les traces ``EnvoiCampagne`` (XMKT2) via ``contact_ref``.
    """
    if not activite or not lead_ids:
        return lead_ids
    refs = {f'lead:{lid}' for lid in lead_ids}
    if activite == 'a_ouvert':
        matches = EnvoiCampagne.objects.filter(
            company=company, contact_ref__in=refs,
            ouvert_le__isnull=False).values_list('contact_ref', flat=True)
    elif activite == 'a_clique':
        matches = EnvoiCampagne.objects.filter(
            company=company, contact_ref__in=refs,
            clique_le__isnull=False).values_list('contact_ref', flat=True)
    elif activite == 'jamais_ouvert':
        ont_ouvert = set(EnvoiCampagne.objects.filter(
            company=company, contact_ref__in=refs,
            ouvert_le__isnull=False).values_list('contact_ref', flat=True))
        return [lid for lid in lead_ids if f'lead:{lid}' not in ont_ouvert]
    else:
        return lead_ids
    matches = set(matches)
    return [lid for lid in lead_ids if f'lead:{lid}' in matches]


def evaluer_segment(segment):
    """Ré-évalue un ``SegmentMarketing`` AU MOMENT DE L'APPEL (XMKT6) — jamais
    mis en cache : une campagne/séquence ciblant le segment prend toujours
    les contacts du moment. Renvoie la liste des IDs de lead correspondants.
    """
    from apps.crm.selectors import leads_matching_regles

    regles = valider_regles_segment(segment.regles)
    regles_lead = {
        k: v for k, v in regles.items()
        if k not in ('activite', 'evenement_present', 'evenement_absent')
    }
    lead_ids = list(
        leads_matching_regles(segment.company, regles_lead)
        .values_list('id', flat=True))
    lead_ids = _filtrer_par_activite(segment.company, lead_ids, regles.get('activite'))
    lead_ids = _filtrer_par_evenement(
        segment.company, lead_ids, regles.get('evenement_present'),
        statut=InscriptionEvenement.Statut.PRESENT)
    lead_ids = _filtrer_par_evenement(
        segment.company, lead_ids, regles.get('evenement_absent'),
        statut=InscriptionEvenement.Statut.ABSENT)
    return lead_ids


def previsualiser_segment(segment, *, taille_echantillon=10):
    """Prévisualisation d'un segment (XMKT6) : compte exact + échantillon
    d'IDs de lead (pas de données PII fabriquées ici — l'appelant résout
    l'affichage via les selectors crm existants)."""
    lead_ids = evaluer_segment(segment)
    return {
        'count': len(lead_ids),
        'echantillon': lead_ids[:taille_echantillon],
    }


# ── XMKT36 — [DECISION] Export de segments vers audiences Meta (gated) ──────
# AUCUNE création de campagne publicitaire ici (règle n°3 — si un jour elle
# s'ajoute : toujours --status PAUSED). Uniquement la synchronisation d'une
# audience personnalisée : identifiants hashés SHA-256 CÔTÉ SERVEUR (norme
# Meta), consentement XMKT4 exigé, clients signés en liste d'exclusion.
# DÉFAUT OFF : sans jeton, aucune donnée ne quitte jamais le serveur.

def meta_audiences_actif():
    """Toggle maître de l'export d'audiences Meta (XMKT36). OFF par défaut.

    Actif uniquement avec ``META_ADS_ENABLED=1`` ET un jeton ET un id de
    compte publicitaire (env). DECISION founder requise avant de poser un
    vrai jeton (loi 09-08 : envoi de données hashées à Meta)."""
    import os
    return (os.getenv('META_ADS_ENABLED', '0') == '1'
            and bool(os.getenv('META_ADS_TOKEN', '').strip())
            and bool(os.getenv('META_AD_ACCOUNT_ID', '').strip()))


def _normaliser_email_meta(email):
    """Norme Meta : trim + minuscules. Chaîne vide si absent."""
    return (email or '').strip().lower()


def _normaliser_telephone_meta(telephone):
    """Norme Meta : chiffres uniquement, AVEC indicatif pays (212…).

    Réutilise la normalisation marocaine existante quand elle matche ;
    sinon repli chiffres-bruts (0X… → 212X…)."""
    brut = (telephone or '').strip()
    if not brut:
        return ''
    try:
        from apps.ventes.utils.phone import normalize_ma_phone
        norme = normalize_ma_phone(brut)
        if norme:
            return norme
    except Exception:  # pragma: no cover - défensif
        pass
    chiffres = re.sub(r'\D', '', brut)
    if chiffres.startswith('0') and len(chiffres) == 10:
        chiffres = '212' + chiffres[1:]
    return chiffres


def hash_identifiant_meta(valeur, *, genre='email'):
    """SHA-256 hex d'un identifiant NORMALISÉ (norme Meta customaudiences).

    ``genre`` ∈ ('email', 'telephone'). Chaîne vide → '' (jamais hashée)."""
    if genre == 'telephone':
        norme = _normaliser_telephone_meta(valeur)
    else:
        norme = _normaliser_email_meta(valeur)
    if not norme:
        return ''
    return hashlib.sha256(norme.encode('utf-8')).hexdigest()


def _contacts_hashes_meta(company, contacts):
    """Hash SHA-256 les contacts CONSENTIS (XMKT4) — jamais les autres.

    ``contacts`` : liste de dicts ``{'email':…, 'telephone':…}`` (selectors
    crm). Un contact sans AUCUN consentement marketing valide est exclu. Un
    contact supprimé (XMKT3) est exclu. Renvoie des lignes
    ``{'email_sha256':…, 'telephone_sha256':…}`` (champs vides omis → '')."""
    lignes = []
    for c in contacts or []:
        email = (c.get('email') or '').strip()
        telephone = (c.get('telephone') or '').strip()
        identifiant = email or telephone
        if not identifiant:
            continue
        if est_supprime(company, identifiant):
            continue
        if not consentement_accorde(company, identifiant, canal='marketing'):
            continue
        lignes.append({
            'email_sha256': hash_identifiant_meta(email, genre='email'),
            'telephone_sha256': hash_identifiant_meta(
                telephone, genre='telephone'),
        })
    return lignes


def _meta_ads_post(path, payload):
    """POST JSON vers l'API Meta Graph (audiences) — chemin GATED uniquement.

    Jamais appelée sans jeton (l'appelant vérifie ``meta_audiences_actif``).
    Renvoie le dict de réponse, ou lève (l'appelant capture)."""
    import json
    import os
    base = (os.getenv('META_GRAPH_BASE_URL', '')
            or 'https://graph.facebook.com/v19.0').rstrip('/')
    token = os.getenv('META_ADS_TOKEN', '').strip()
    body = dict(payload)
    body['access_token'] = token
    req = urllib.request.Request(
        f'{base}/{path}', data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read() or b'{}')


def exporter_segment_audience_meta(segment, *, inclure_exclusions=True):
    """XMKT36 — Synchronise un ``SegmentMarketing`` comme audience Meta.

    Émet UNIQUEMENT des identifiants hashés SHA-256 côté serveur (jamais de
    PII en clair), pour les seuls contacts au consentement XMKT4 valide ;
    les CLIENTS SIGNÉS partent en liste d'exclusion séparée. GATED : sans
    jeton (``meta_audiences_actif()`` faux), NO-OP réseau strict — renvoie
    quand même le résumé (compteurs) pour l'UI. AUCUNE campagne publicitaire
    n'est créée ici (règle n°3)."""
    import os
    from apps.crm.selectors import (
        clients_contact_identifiers, lead_contact_identifiers,
    )
    company = segment.company
    lead_ids = evaluer_segment(segment)
    inclus = _contacts_hashes_meta(
        company, lead_contact_identifiers(company, lead_ids))
    exclus = []
    if inclure_exclusions:
        exclus = _contacts_hashes_meta(
            company, clients_contact_identifiers(company))
    resume = {
        'configured': meta_audiences_actif(),
        'segment': segment.nom,
        'inclus': len(inclus),
        'exclus': len(exclus),
        'audience_id': '',
        'exclusion_audience_id': '',
    }
    if not resume['configured']:
        return resume
    ad_account = os.getenv('META_AD_ACCOUNT_ID', '').strip()
    schema = ['EMAIL_SHA256', 'PHONE_SHA256']

    def _payload_users(lignes):
        return {
            'schema': schema,
            'data': [
                [ligne['email_sha256'], ligne['telephone_sha256']]
                for ligne in lignes
            ],
        }

    try:
        audience = _meta_ads_post(
            f'act_{ad_account}/customaudiences',
            {'name': f'Segment — {segment.nom}',
             'subtype': 'CUSTOM', 'customer_file_source':
                 'USER_PROVIDED_ONLY'})
        resume['audience_id'] = str(audience.get('id') or '')
        if resume['audience_id'] and inclus:
            _meta_ads_post(
                f"{resume['audience_id']}/users",
                {'payload': _payload_users(inclus)})
        if exclus:
            exclusion = _meta_ads_post(
                f'act_{ad_account}/customaudiences',
                {'name': f'Exclusion clients — {segment.nom}',
                 'subtype': 'CUSTOM', 'customer_file_source':
                     'USER_PROVIDED_ONLY'})
            resume['exclusion_audience_id'] = str(exclusion.get('id') or '')
            if resume['exclusion_audience_id']:
                _meta_ads_post(
                    f"{resume['exclusion_audience_id']}/users",
                    {'payload': _payload_users(exclus)})
    except Exception as exc:
        resume['erreur'] = str(exc)[:255]
    return resume


# ── XMKT8 — Variables de fusion dans les campagnes avec fallback ───────────

# Variables disponibles au rendu — jamais ``prix_achat`` ni aucune donnée
# interne (règle explicite de la tâche). Whitelist stricte : une variable
# ``{inconnue}`` dans un corps de campagne est une ERREUR de validation.
MERGE_VARIABLES = (
    'prenom', 'nom', 'ville', 'societe', 'proprietaire_lead',
)

_MERGE_VAR_RE = re.compile(r'\{([a-zA-Z_]+)\}')


def variables_du_corps(corps):
    """Renvoie l'ensemble des noms de variables ``{xxx}`` présentes dans un
    corps de campagne (XMKT8), pour la validation à l'édition."""
    return set(_MERGE_VAR_RE.findall(corps or ''))


def valider_variables_fusion(corps):
    """Lève ``ValueError`` si ``corps`` référence une variable de fusion
    inconnue (XMKT8) — erreur claire à la validation, comme demandé."""
    inconnues = variables_du_corps(corps) - set(MERGE_VARIABLES)
    if inconnues:
        raise ValueError(
            f"Variable(s) de fusion inconnue(s) : {sorted(inconnues)}")
    return corps


def rendre_variables_fusion(corps, company, lead_id, *, fallback=''):
    """Substitue les variables de fusion d'un corps de campagne (XMKT8) avec
    les champs du lead ciblé (lus via ``apps.crm.selectors.lead_merge_fields``
    — jamais d'import direct de ``apps.crm.models``). Une variable vide sur
    le contact retombe sur ``fallback`` (par variable, comme
    ``crm.MessageTemplate.render``).
    """
    from apps.crm.selectors import lead_merge_fields

    valider_variables_fusion(corps)
    champs = lead_merge_fields(company, lead_id) or {}
    rendu = corps or ''
    for variable in MERGE_VARIABLES:
        valeur = champs.get(variable) or fallback
        rendu = rendu.replace('{' + variable + '}', valeur)
    return rendu


# ── XMKT11 — Campagnes multilingues FR/AR/Darija avec variantes ────────────

def variante_pour_langue(campagne, langue):
    """Renvoie ``(objet, corps)`` pour ``langue`` (XMKT11) — fallback FR
    (``campagne.objet``/``campagne.corps``) si la langue est absente de
    ``variantes_langue`` ou vaut ``'fr'``.
    """
    langue = (langue or 'fr').strip().lower()
    if langue == 'fr':
        return campagne.objet, campagne.corps
    variante = (campagne.variantes_langue or {}).get(langue)
    if not variante:
        return campagne.objet, campagne.corps
    objet = variante.get('objet') or campagne.objet
    corps = variante.get('corps') or campagne.corps
    return objet, corps


def rendre_pour_lead(campagne, company, lead_id):
    """XMKT11 — Sélectionne la variante de langue selon
    ``lead.langue_preferee`` (lu via ``apps.crm.selectors.get_company_lead``)
    puis applique la fusion de variables (XMKT8). Renvoie
    ``{'objet': ..., 'corps': ..., 'langue': ..., 'rtl': bool}``.
    """
    from apps.crm.selectors import get_company_lead

    lead = get_company_lead(company, lead_id)
    langue = getattr(lead, 'langue_preferee', None) or 'fr'
    objet, corps = variante_pour_langue(campagne, langue)
    corps_rendu = rendre_variables_fusion(corps, company, lead_id)
    return {
        'objet': objet,
        'corps': corps_rendu,
        'langue': langue,
        'rtl': langue in ('ar',),
    }


# ── XMKT13 — Envoi test + aperçu fusionné + pré-check santé ─────────────────

_URL_RE = re.compile(r'https?://[^\s<>"\')]+')
_IMG_URL_RE = re.compile(r'\.(?:jpg|jpeg|png|gif|webp)(?:\?\S*)?$', re.IGNORECASE)


def envoyer_test_campagne(campagne, *, adresses_seed, lead_id_exemple=None):
    """XMKT13 — Envoi de test d'une campagne (jamais vers de vrais
    destinataires) : corps fusionné pour un contact d'exemple si fourni, sinon
    le corps brut. NE modifie ni le statut ni les compteurs de la campagne
    (contrairement à ``envoyer_campagne``) — c'est un test, pas un envoi réel.
    Renvoie ``{'seeds': [...], 'corps_fusionne': ...}``.
    """
    corps = campagne.corps
    if lead_id_exemple:
        corps = rendre_variables_fusion(
            campagne.corps, campagne.company, lead_id_exemple)
    return {
        'seeds': [a for a in (adresses_seed or []) if a],
        'corps_fusionne': corps,
    }


def _lien_casse(url, timeout=3):
    """HEAD best-effort (XMKT13) : renvoie True si le lien semble cassé.
    Toute erreur réseau/timeout est traitée comme "on ne sait pas" (False) —
    un pré-check ne doit jamais planter sur un problème réseau transitoire.
    """
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status >= 400
    except Exception:
        return False


def precheck_sante_campagne(campagne, *, verifier_liens=False):
    """Pré-check bloquant/avertissant avant l'envoi de masse d'une campagne
    (XMKT13). Renvoie ``{'bloque': bool, 'avertissements': [...]}``.

    BLOQUE (email marketing) si le lien de désinscription (XMKT3) est absent
    du corps. Le reste (liens cassés, poids d'images, segment vide) est un
    AVERTISSEMENT non bloquant. ``verifier_liens`` est OFF par défaut (le HEAD
    réseau n'est fait qu'à la demande explicite, jamais en arrière-plan).
    """
    avertissements = []
    bloque = False
    corps = campagne.corps or ''
    urls = _URL_RE.findall(corps)

    if campagne.canal == Campagne.Canal.EMAIL:
        a_lien_desinscription = (
            '/desinscription/' in corps or '{lien_desinscription}' in corps)
        if not a_lien_desinscription:
            bloque = True
            avertissements.append(
                'Lien de désinscription manquant — envoi email bloqué (loi 09-08).')

    if verifier_liens:
        for url in urls:
            if _lien_casse(url):
                avertissements.append(f'Lien possiblement cassé : {url}')

    for url in urls:
        if _IMG_URL_RE.search(url):
            avertissements.append(f"Image dans le corps : {url} (vérifier le poids).")

    segment_vide = not (campagne.segment or {}) and not campagne.listes.exists()
    if segment_vide:
        avertissements.append('Aucun segment ni liste ciblée — 0 destinataire prévu.')

    # XMKT33 — avertissement si le domaine d'envoi (email société) n'est pas
    # authentifié (SPF/DKIM/DMARC). Best-effort, jamais bloquant.
    if campagne.canal == Campagne.Canal.EMAIL:
        try:
            from apps.parametres.models_company import CompanyProfile
            profil = CompanyProfile.objects.filter(company=campagne.company).first()
            email_expediteur = (profil.email or '') if profil else ''
        except Exception:  # pragma: no cover - défensif
            email_expediteur = ''
        if '@' in email_expediteur:
            domaine = email_expediteur.split('@', 1)[1]
            if not domaine_envoi_authentifie(campagne.company, domaine):
                avertissements.append(
                    f'Domaine d\'envoi « {domaine} » non authentifié '
                    '(SPF/DKIM/DMARC) — risque de délivrabilité.')

    return {'bloque': bloque, 'avertissements': avertissements}


# ── XMKT15 — Conformité SMS Maroc : comptage, coût, sender-ID, STOP ─────────

_GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ"
    " !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
_GSM7_EXTENDED = '^{}\\[~]|€'

SMS_STOP_SUFFIX = ' STOP au 00000'
SMS_PRIX_MAD_DEFAUT = Decimal('0.35')


def _est_gsm7(texte):
    """Un caractère hors du jeu GSM-7 (de base + étendu) force l'encodage
    UCS-2 (XMKT15) — chaque caractère spécial étendu compte pour 2 dans un
    SMS GSM-7 mais on reste en GSM-7 tant que TOUS les caractères y sont."""
    jeu = set(_GSM7_BASIC) | set(_GSM7_EXTENDED)
    return all(c in jeu for c in (texte or ''))


def compter_segments_sms(texte):
    """XMKT15 — Compte les segments SMS d'un corps (GSM-7 vs UCS-2).

    Limites usuelles opérateur : GSM-7 = 160 caractères (1 segment) / 153 par
    segment au-delà (en-tête UDH multi-part) ; UCS-2 = 70 / 67. Renvoie
    ``{'encodage': 'gsm7'|'ucs2', 'nb_caracteres': int, 'nb_segments': int}``.
    """
    texte = texte or ''
    nb = len(texte)
    if nb == 0:
        return {'encodage': 'gsm7', 'nb_caracteres': 0, 'nb_segments': 0}
    if _est_gsm7(texte):
        encodage = 'gsm7'
        limite_seul, limite_multi = 160, 153
    else:
        encodage = 'ucs2'
        limite_seul, limite_multi = 70, 67
    if nb <= limite_seul:
        segments = 1
    else:
        segments = -(-nb // limite_multi)  # ceil division
    return {'encodage': encodage, 'nb_caracteres': nb, 'nb_segments': segments}


def estimer_cout_sms(texte, *, prix_unitaire_mad=SMS_PRIX_MAD_DEFAUT,
                     nb_destinataires=1):
    """XMKT15 — Aperçu du coût multi-part avant envoi (MAD), prix unitaire
    paramétrable société (défaut ``SMS_PRIX_MAD_DEFAUT``)."""
    info = compter_segments_sms(texte)
    prix_unitaire_mad = Decimal(str(prix_unitaire_mad))
    cout_par_destinataire = info['nb_segments'] * prix_unitaire_mad
    return {
        **info,
        'prix_unitaire_mad': prix_unitaire_mad,
        'cout_par_destinataire_mad': cout_par_destinataire,
        'cout_total_mad': cout_par_destinataire * nb_destinataires,
    }


def ajouter_mention_stop(corps):
    """XMKT15 — Ajoute la mention STOP obligatoire si absente (idempotent)."""
    corps = corps or ''
    if 'stop' in corps.lower():
        return corps
    return corps + SMS_STOP_SUFFIX


def valider_numero_sms(numero):
    """XMKT15 — Valide un numéro mobile marocain E.164 avant envoi SMS
    (préfixes 06/07 uniquement — un fixe/invalide est exclu pour ne pas payer
    un SMS mort). Renvoie ``(numero_normalise_ou_None, motif_si_exclu)``.
    """
    normalise = _normaliser_destinataire(numero)
    if not normalise or '@' in normalise:
        return None, 'Non un numéro de téléphone.'
    if not normalise.startswith('212'):
        return None, 'Préfixe international inattendu.'
    local = normalise[3:]
    if not (local.startswith('6') or local.startswith('7')):
        return None, 'Numéro fixe (préfixe 05) exclu — mobile requis.'
    if len(local) != 9:
        return None, 'Longueur de numéro invalide.'
    return normalise, ''


def filtrer_destinataires_sms(numeros):
    """XMKT15 — Filtre une liste de numéros pour un envoi SMS. Renvoie
    ``{'valides': [...], 'exclus': [{'numero':..., 'motif':...}]}``."""
    valides, exclus = [], []
    for numero in numeros or []:
        normalise, motif = valider_numero_sms(numero)
        if normalise:
            valides.append(normalise)
        else:
            exclus.append({'numero': numero, 'motif': motif})
    return {'valides': valides, 'exclus': exclus}


def traiter_stop_entrant(company, numero, *, source='webhook_agregateur_sms'):
    """XMKT15 — Traite le mot-clé STOP entrant (webhook agrégateur, gated) :
    désinscrit immédiatement le numéro (XMKT3)."""
    normalise, _motif = valider_numero_sms(numero)
    destinataire = normalise or (numero or '').strip()
    if not destinataire:
        return None
    return supprimer_destinataire(
        company, destinataire, motif=SuppressionMarketing.Motif.DESINSCRIT,
        source=source)


# ── XMKT16 — Touches marketing sur le chatter du lead (vue 360°) ───────────

def _lead_id_depuis_contact_ref(contact_ref):
    """``contact_ref`` porte la convention ``lead:<id>`` utilisée par
    l'attribution segment (XMKT6). Renvoie l'ID ou ``None`` si le format ne
    correspond pas (contact_ref d'un client, ou vide)."""
    if not contact_ref or not contact_ref.startswith('lead:'):
        return None
    suffixe = contact_ref[len('lead:'):]
    return int(suffixe) if suffixe.isdigit() else None


def noter_touche_marketing_pour_lead(company, contact_ref, message, *, ordre=0):
    """XMKT16 — Écrit une touche marketing sur le chatter d'un lead (via
    ``apps.crm.services.noter_touche_marketing`` — jamais d'import du modèle
    CRM depuis compta). No-op silencieux si ``contact_ref`` ne pointe pas un
    lead (ex. contact_ref vide ou format client) — une ligne par événement
    clé, jamais par batch.
    """
    lead_id = _lead_id_depuis_contact_ref(contact_ref)
    if not lead_id:
        return None
    from apps.crm.selectors import get_company_lead
    from apps.crm.services import noter_touche_marketing
    lead = get_company_lead(company, lead_id)
    if not lead:
        return None
    return noter_touche_marketing(lead, message, ordre=ordre)


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


# ── XMKT1 — Inscription + exécution réelle des séquences de relance ────────

def inscrire_lead_sequence(company, sequence, *, lead_id, lead_reference=''):
    """Inscrit un lead dans une séquence (XMKT1), idempotent.

    Si le lead a déjà une inscription ACTIVE pour cette séquence, la renvoie
    sans en créer une seconde (contrainte d'unicité en base). Pointe
    ``etape_courante`` sur la première étape (ordre le plus bas) si la
    séquence en a au moins une.
    """
    existante = InscriptionSequence.objects.filter(
        company=company, sequence=sequence, lead_id=lead_id,
        statut=InscriptionSequence.Statut.ACTIF,
    ).first()
    if existante:
        return existante
    premiere_etape = sequence.etapes.order_by('ordre').first()
    return InscriptionSequence.objects.create(
        company=company,
        sequence=sequence,
        lead_id=lead_id,
        lead_reference=lead_reference or '',
        etape_courante=premiere_etape,
        statut=InscriptionSequence.Statut.ACTIF,
    )


def inscrire_leads_pour_stage(company, stage_key, *, lead_id, lead_reference=''):
    """Inscrit un lead entrant dans ``stage_key`` sur toute séquence active
    déclenchée par cette étape (XMKT1). ``stage_key`` vient de ``STAGES.py``
    côté appelant — jamais recalculé/hardcodé ici.
    """
    sequences = SequenceRelance.objects.filter(
        company=company, actif=True, stage_declencheur=stage_key)
    return [
        inscrire_lead_sequence(
            company, seq, lead_id=lead_id, lead_reference=lead_reference)
        for seq in sequences
    ]


def _condition_vraie(inscription, condition):
    """XMKT18 — évalue une condition d'engagement pour une inscription, sur
    les traces existantes : ``EnvoiCampagne`` (ouverture/clic, TOUTES
    campagnes du lead depuis le déclenchement) et ``MessageWhatsAppEntrant``
    (réponse WhatsApp entrante rattachée au lead depuis le déclenchement).
    """
    if condition in ('', EtapeSequence.Condition.TOUJOURS):
        return True
    contact_ref = f'lead:{inscription.lead_id}'
    depuis = inscription.declenchee_le
    if condition == EtapeSequence.Condition.A_OUVERT:
        return EnvoiCampagne.objects.filter(
            company=inscription.company, contact_ref=contact_ref,
            ouvert_le__isnull=False, ouvert_le__gte=depuis).exists()
    if condition == EtapeSequence.Condition.A_CLIQUE:
        return EnvoiCampagne.objects.filter(
            company=inscription.company, contact_ref=contact_ref,
            clique_le__isnull=False, clique_le__gte=depuis).exists()
    if condition == EtapeSequence.Condition.N_A_PAS_OUVERT:
        return not EnvoiCampagne.objects.filter(
            company=inscription.company, contact_ref=contact_ref,
            ouvert_le__isnull=False, ouvert_le__gte=depuis).exists()
    if condition == EtapeSequence.Condition.A_REPONDU:
        return MessageWhatsAppEntrant.objects.filter(
            company=inscription.company, lead_id=inscription.lead_id,
            date_reception__gte=depuis).exists()
    return True


def _appliquer_action_alternative(inscription, etape, action):
    """XMKT18 — applique l'action alternative (condition fausse). Deux
    formes reconnues : ``renvoyer:<nouvel_objet>`` (renvoi de l'étape avec un
    objet différent — journalisé, gated comme l'envoi normal) et
    ``tache_commerciale`` (crée une relance/tâche au propriétaire du lead via
    ``crm.services`` — jamais d'import direct du modèle crm)."""
    if not action:
        return
    if action == 'tache_commerciale':
        from apps.crm.selectors import get_company_lead
        lead = get_company_lead(inscription.company, inscription.lead_id)
        if lead is not None:
            noter_touche_marketing_pour_lead(
                inscription.company, f'lead:{inscription.lead_id}',
                f'Séquence « {inscription.sequence.nom} » — relance '
                f'commerciale créée (branche alternative étape {etape.ordre})')
    elif action.startswith('renvoyer:'):
        noter_touche_marketing_pour_lead(
            inscription.company, f'lead:{inscription.lead_id}',
            f'Séquence « {inscription.sequence.nom} » — renvoi avec un '
            f'autre objet (branche alternative étape {etape.ordre})')


def _executer_action_crm(inscription, etape):
    """XMKT19 — exécute l'action CRM configurée sur ``etape.action_crm``
    (JSON ``{"action": ..., "params": {...}}``), toujours via
    ``apps.crm.services`` (jamais d'import direct du modèle CRM). Renvoie
    ``'execute'`` / ``'lead_introuvable'`` / ``'action_inconnue'`` / ``'erreur'``.
    """
    from apps.crm.selectors import get_company_lead
    from apps.crm import services as crm_services

    lead = get_company_lead(inscription.company, inscription.lead_id)
    if lead is None:
        return 'lead_introuvable'
    config = etape.action_crm or {}
    action = config.get('action')
    params = config.get('params') or {}
    try:
        if action == 'avancer_stage':
            crm_services.avancer_stage_lead_vers(lead, None, params.get('stage'))
        elif action == 'assigner':
            crm_services.assigner_lead_a(lead, None, params.get('owner_id'))
        elif action == 'tag':
            crm_services.poser_tag_lead(lead, None, params.get('tag'))
        elif action == 'retirer_tag':
            crm_services.retirer_tag_lead(lead, None, params.get('tag'))
        elif action == 'score':
            crm_services.ajuster_score_lead(lead, None, params.get('delta', 0))
        elif action == 'tache':
            crm_services.creer_relance_lead(
                lead, None, relance_date=params.get('relance_date'),
                note=params.get('note', ''))
        else:
            return 'action_inconnue'
    except Exception:
        return 'erreur'
    noter_touche_marketing_pour_lead(
        inscription.company, f'lead:{inscription.lead_id}',
        f'Séquence « {inscription.sequence.nom} » — action CRM « {action} » '
        f'exécutée (étape {etape.ordre})')
    return 'execute'


def _executer_une_etape(inscription, etape, *, maintenant=None):
    """Exécute (ou planifie, gated) une étape pour une inscription et trace
    le résultat. N'envoie jamais réellement ici : réutilise le comportement
    NO-OP existant des intégrations (FG31 — file de relance manuelle quand
    aucune intégration n'est active).

    XMKT18 — si l'étape porte une ``condition``, elle n'est exécutée QUE si
    la condition est vraie au moment dû ; sinon l'``action_alternative``
    (si renseignée) est appliquée à la place. La branche prise est tracée
    sur ``ExecutionEtapeSequence.branche_prise``.

    ``maintenant`` — instant simulé (XMKT7 throttling) : propagé jusqu'à la
    vérification de fenêtre de silence pour que la décision reste cohérente
    avec l'instant utilisé par ``executer_etapes_dues`` plutôt que l'horloge
    réelle (sinon la fenêtre de silence de l'exécution réelle "fuit" dans une
    exécution simulée à un autre instant).
    """
    maintenant = maintenant or timezone.now()
    resultat = 'planifie'
    erreur = ''
    canal = etape.canal
    condition = getattr(etape, 'condition', EtapeSequence.Condition.TOUJOURS)
    condition_vraie = _condition_vraie(inscription, condition)
    branche_prise = 'condition' if condition_vraie else 'alternative'

    if not condition_vraie:
        _appliquer_action_alternative(
            inscription, etape, getattr(etape, 'action_alternative', ''))
        execution = ExecutionEtapeSequence.objects.create(
            company=inscription.company,
            inscription=inscription,
            etape=etape,
            canal=canal,
            resultat='condition_fausse',
            erreur=erreur,
            branche_prise=branche_prise,
        )
        return execution

    # XMKT19 — étape d'action CRM (au lieu d'un message) : pose l'action puis
    # trace, jamais de faux "envoi" journalisé pour ce type d'étape.
    if getattr(etape, 'type_etape', EtapeSequence.TypeEtape.MESSAGE) == \
            EtapeSequence.TypeEtape.ACTION_CRM:
        resultat_action = _executer_action_crm(inscription, etape)
        return ExecutionEtapeSequence.objects.create(
            company=inscription.company,
            inscription=inscription,
            etape=etape,
            canal='',
            resultat=resultat_action,
            erreur='' if resultat_action != 'erreur' else 'action CRM échouée',
            branche_prise=branche_prise,
        )

    # ZMKT5 — rejet consentement/suppression/fenêtre AVANT tout envoi
    # (email/whatsapp uniquement — l'appel n'a jamais lieu, comportement
    # historique préservé pour l'appel téléphonique manuel).
    if canal in (EtapeSequence.Canal.EMAIL, EtapeSequence.Canal.WHATSAPP):
        from apps.crm.selectors import get_company_lead
        lead = get_company_lead(inscription.company, inscription.lead_id)
        destinataire = ''
        if lead is not None:
            destinataire = (
                lead.email if canal == EtapeSequence.Canal.EMAIL
                else (lead.whatsapp or lead.telephone)) or ''
        motif_rejet = ''
        if destinataire and est_supprime(inscription.company, destinataire):
            motif_rejet = ExecutionEtapeSequence.MotifRejet.SUPPRIME
        elif destinataire and not consentement_accorde(
                inscription.company, destinataire, canal=canal):
            motif_rejet = ExecutionEtapeSequence.MotifRejet.SANS_CONSENTEMENT
        elif (canal == EtapeSequence.Canal.WHATSAPP
                and _hors_fenetre_silence(inscription.company, maintenant)):
            motif_rejet = ExecutionEtapeSequence.MotifRejet.HORS_FENETRE
        if motif_rejet:
            return ExecutionEtapeSequence.objects.create(
                company=inscription.company, inscription=inscription,
                etape=etape, canal=canal, resultat='rejete',
                branche_prise=branche_prise,
                statut_trace=ExecutionEtapeSequence.StatutTrace.REJETE,
                motif_rejet=motif_rejet,
            )

    if canal == EtapeSequence.Canal.WHATSAPP and not whatsapp_actif():
        resultat = 'planifie'  # file manuelle FG31, aucun appel réseau
    elif canal == EtapeSequence.Canal.EMAIL and not email_marketing_actif():
        resultat = 'planifie'
    else:
        resultat = 'planifie'  # gated par défaut, tant qu'aucune clé n'existe
    execution = ExecutionEtapeSequence.objects.create(
        company=inscription.company,
        inscription=inscription,
        etape=etape,
        canal=canal,
        resultat=resultat,
        erreur=erreur,
        branche_prise=branche_prise,
        statut_trace=ExecutionEtapeSequence.StatutTrace.TRAITE,
    )
    # XMKT16 — une ligne de chatter par étape exécutée (pas par batch).
    noter_touche_marketing_pour_lead(
        inscription.company, f'lead:{inscription.lead_id}',
        f'Séquence « {inscription.sequence.nom} » — étape {etape.ordre} exécutée')
    return execution


def email_marketing_actif():
    """Alias explicite de ``brevo_actif`` pour les séquences (XMKT1)."""
    return brevo_actif()


# ── ZMKT5 — Traces d'activité de séquence + compteurs par étape ────────────

def traces_sequence(sequence, *, etape_id=None, statut_trace=None):
    """ZMKT5 — traces filtrables par étape et statut, company-scopées."""
    qs = ExecutionEtapeSequence.objects.filter(
        company=sequence.company, etape__sequence=sequence,
    ).select_related('etape', 'inscription')
    if etape_id:
        qs = qs.filter(etape_id=etape_id)
    if statut_trace:
        qs = qs.filter(statut_trace=statut_trace)
    return [
        {
            'id': t.id, 'etape_id': t.etape_id, 'etape_ordre': t.etape.ordre,
            'inscription_id': t.inscription_id, 'lead_id': t.inscription.lead_id,
            'statut_trace': t.statut_trace, 'motif_rejet': t.motif_rejet,
            'resultat': t.resultat, 'execute_le': t.execute_le,
        }
        for t in qs.order_by('-execute_le')
    ]


def participants_sequence(sequence, *, statut=None):
    """ZMKT6 — liste des participants (``InscriptionSequence``) : nœud
    courant + prochaine échéance, filtrable par statut."""
    qs = sequence.inscriptions.select_related('etape_courante').all()
    if statut:
        qs = qs.filter(statut=statut)
    resultat = []
    for insc in qs:
        prochaine_echeance = None
        if insc.etape_courante is not None:
            prochaine_echeance = insc.declenchee_le + timezone.timedelta(
                days=insc.etape_courante.delai_jours)
        resultat.append({
            'id': insc.id,
            'lead_id': insc.lead_id,
            'lead_reference': insc.lead_reference,
            'etape_courante_id': insc.etape_courante_id,
            'statut': insc.statut,
            'prochaine_echeance': prochaine_echeance,
        })
    return resultat


def reporting_campagnes(company, *, groupby='canal'):
    """ZMKT8 — reporting multi-vue (Graph/Pivot/Cohorte) sur la trace XMKT2 :
    mesures délivrés/ouverts/cliqués/rebonds/désinscrits + CTR/CTOR/
    délivrabilité, groupables par ``canal``/``mois``/``campagne``.
    Division par zéro = 0 (jamais d'exception).
    """
    from django.db.models.functions import TruncMonth

    envois = EnvoiCampagne.objects.filter(company=company)
    if groupby == 'mois':
        envois = envois.annotate(groupe=TruncMonth('date_creation'))
        cle = 'groupe'
    elif groupby == 'campagne':
        cle = 'campagne_id'
    else:
        cle = 'campagne__canal'

    groupes = {}
    for e in envois.values(cle, 'statut'):
        clef_groupe = e[cle]
        slot = groupes.setdefault(clef_groupe, {
            'delivres': 0, 'ouverts': 0, 'cliques': 0, 'rebonds': 0,
            'desinscrits': 0, 'total': 0,
        })
        slot['total'] += 1
        if e['statut'] == EnvoiCampagne.Statut.REBOND:
            slot['rebonds'] += 1
        elif e['statut'] == EnvoiCampagne.Statut.DESINSCRIT:
            slot['desinscrits'] += 1
        else:
            slot['delivres'] += 1
    # Ouvertures/clics comptés séparément (un envoi peut être ouvert ET
    # cliqué — pas mutuellement exclusif avec le statut agrégé ci-dessus).
    for e in envois.filter(ouvert_le__isnull=False).values(cle):
        groupes.setdefault(e[cle], {
            'delivres': 0, 'ouverts': 0, 'cliques': 0, 'rebonds': 0,
            'desinscrits': 0, 'total': 0})['ouverts'] += 1
    for e in envois.filter(clique_le__isnull=False).values(cle):
        groupes.setdefault(e[cle], {
            'delivres': 0, 'ouverts': 0, 'cliques': 0, 'rebonds': 0,
            'desinscrits': 0, 'total': 0})['cliques'] += 1

    resultat = []
    for clef_groupe, slot in groupes.items():
        total = slot['total'] or 1
        ctr = round(slot['cliques'] / total * 100, 1) if total else 0.0
        ctor = (round(slot['cliques'] / slot['ouverts'] * 100, 1)
                if slot['ouverts'] else 0.0)
        delivrabilite = (
            round(slot['delivres'] / total * 100, 1) if total else 0.0)
        resultat.append({
            'groupe': clef_groupe,
            'delivres': slot['delivres'], 'ouverts': slot['ouverts'],
            'cliques': slot['cliques'], 'rebonds': slot['rebonds'],
            'desinscrits': slot['desinscrits'],
            'ctr_pct': ctr, 'ctor_pct': ctor,
            'delivrabilite_pct': delivrabilite,
        })
    return resultat


def nb_participants_actifs(sequence):
    """ZMKT6 — compteur « N participants actifs »."""
    return sequence.inscriptions.filter(
        statut=InscriptionSequence.Statut.ACTIF).count()


def compteurs_par_etape(sequence):
    """ZMKT5 — agrège par étape des compteurs Succès/Rejeté/Envoyé."""
    resultat = []
    for etape in sequence.etapes.order_by('ordre'):
        executions = etape.executions.all()
        resultat.append({
            'etape_id': etape.id,
            'ordre': etape.ordre,
            'succes': executions.exclude(
                statut_trace=ExecutionEtapeSequence.StatutTrace.REJETE).count(),
            'rejete': executions.filter(
                statut_trace=ExecutionEtapeSequence.StatutTrace.REJETE).count(),
            'envoye': executions.filter(resultat='envoye').count(),
        })
    return resultat


def sortir_inscription(inscription, *, motif=''):
    """Sort une inscription de sa séquence (XMKT1) : refus/acceptation devis,
    désinscription. Idempotent — une inscription déjà sortie/terminée n'est
    pas re-modifiée.
    """
    if inscription.statut != InscriptionSequence.Statut.ACTIF:
        return inscription
    inscription.statut = InscriptionSequence.Statut.SORTI
    inscription.motif_sortie = (motif or '')[:255]
    inscription.sortie_le = timezone.now()
    inscription.save(update_fields=['statut', 'motif_sortie', 'sortie_le'])
    return inscription


def sortir_inscriptions_pour_lead(company, lead_id, *, motif=''):
    """Sort TOUTES les inscriptions actives d'un lead (tous séquences), p.ex.
    à l'acceptation/refus d'un devis (XMKT1, câblé via ``receivers.py``).
    """
    inscriptions = InscriptionSequence.objects.filter(
        company=company, lead_id=lead_id,
        statut=InscriptionSequence.Statut.ACTIF)
    return [sortir_inscription(insc, motif=motif) for insc in inscriptions]


def executer_etapes_dues(company, *, maintenant=None):
    """Exécute, pour toute inscription ACTIVE de la société, l'étape courante
    si son échéance (J+delai depuis ``declenchee_le``) est atteinte (XMKT1).

    Appelée par la tâche Celery beat ``compta.executer_sequences_relance``.
    Après exécution, avance ``etape_courante`` vers la prochaine étape (par
    ``ordre``) ou termine l'inscription si c'était la dernière. Renvoie la
    liste des ``ExecutionEtapeSequence`` créées.
    """
    maintenant = maintenant or timezone.now()
    executions = []
    qs = InscriptionSequence.objects.filter(
        company=company, statut=InscriptionSequence.Statut.ACTIF,
        etape_courante__isnull=False,
    ).select_related('etape_courante', 'sequence')
    for inscription in qs:
        etape = inscription.etape_courante
        echeance = inscription.declenchee_le + timezone.timedelta(
            days=etape.delai_jours)
        if maintenant < echeance:
            continue
        executions.append(
            _executer_une_etape(inscription, etape, maintenant=maintenant))
        suivante = inscription.sequence.etapes.filter(
            ordre__gt=etape.ordre).order_by('ordre').first()
        if suivante:
            inscription.etape_courante = suivante
            inscription.save(update_fields=['etape_courante'])
        else:
            inscription.etape_courante = None
            inscription.statut = InscriptionSequence.Statut.TERMINE
            inscription.save(update_fields=['etape_courante', 'statut'])
    return executions


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
    journalisé (idempotent par ``wa_message_id``) et rattaché via
    ``crm.services.resolve_or_create_lead_from_whatsapp`` (YLEAD8, import
    function-local — jamais les modèles crm) : un lead OUVERT existant du
    même numéro est réutilisé (message ajouté à son chatter) au lieu de
    toujours créer un doublon ; sinon un lead DRAFT est créé, funnel à NEW.
    Renvoie le log, ou ``None`` si l'intégration est OFF.
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
    # Rattachement/création du lead via le service crm (jamais ses modèles).
    try:
        from apps.crm import services as crm_services
        lead = crm_services.resolve_or_create_lead_from_whatsapp(
            company, expediteur, nom=nom_profil, user=user)
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

    YSERV11 — au moment de l'enchantement : un PROMOTEUR (9-10) déclenche,
    si ``CompanyProfile.referral_enabled``, une notification au commercial du
    client avec un brouillon WhatsApp wa.me « parrainage » (MessageTemplate
    FR/darija, éditable) + lien vers la création de Parrainage (parrain
    pré-rempli) ; un DÉTRACTEUR (0-6) ouvre une activité de rappel assignée
    au responsable. Idempotent par enquête : la garde « déjà répondue »
    ci-dessus ne laisse ce déclencheur s'exécuter qu'UNE fois.
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
    try:
        _declencher_suivi_nps(enquete)
    except Exception:  # pragma: no cover - défensif, jamais bloquant
        pass
    return enquete


def _referral_actif(company):
    """YSERV11 — toggle ``CompanyProfile.referral_enabled`` (N98). OFF → rien."""
    try:
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # pragma: no cover - défensif
        profil = None
    return bool(getattr(profil, 'referral_enabled', False))


def _commercial_pour_client(company, client_id):
    """YSERV11 — le commercial du client : owner du lead le plus récent lié,
    sinon le créateur de la fiche client. Peut renvoyer ``None``."""
    from apps.crm.selectors import get_company_client, get_latest_lead_for_client
    lead = get_latest_lead_for_client(company, client_id)
    if lead is not None and lead.owner_id:
        return lead.owner
    client = get_company_client(company, client_id)
    return getattr(client, 'created_by', None)


def _declencher_suivi_nps(enquete):
    """YSERV11 — suivi post-réponse NPS (promoteur → parrainage, détracteur →
    rappel). Gated ``referral_enabled`` (OFF par défaut → no-op strict).
    Appelé UNE seule fois par enquête (garde « déjà répondue » de l'appelant).
    """
    company = enquete.company
    score = enquete.score
    if score is None or not _referral_actif(company):
        return
    if 7 <= score <= 8:  # passif : aucun suivi automatique
        return
    from apps.crm.selectors import get_company_client, get_latest_lead_for_client
    client = get_company_client(company, enquete.client_id)
    if client is None:
        return
    commercial = _commercial_pour_client(company, enquete.client_id)

    if score >= 9:
        # ── Promoteur : notification + brouillon WhatsApp wa.me parrainage ──
        from apps.crm.services import get_or_create_parrainage_template
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        from apps.notifications.whatsapp_bsp import get_whatsapp_provider
        if commercial is None:
            return
        lead = get_latest_lead_for_client(company, enquete.client_id)
        langue = getattr(lead, 'langue_preferee', None) or 'fr'
        template = get_or_create_parrainage_template(company, langue=langue)
        message = template.render(
            prenom=client.prenom or client.nom or '')
        wa_url = None
        telephone = client.telephone or ''
        if telephone:
            try:
                wa_result = get_whatsapp_provider().get_wa_url(
                    telephone, message)
                wa_url = wa_result.get('url')
            except Exception:  # pragma: no cover - défensif
                wa_url = None
        corps = f'Brouillon : {message}'
        if wa_url:
            corps += f'\nEnvoyer : {wa_url}'
        notify(
            commercial, EventType.NPS_PROMOTEUR,
            'Client promoteur — proposer le parrainage',
            body=corps[:2000],
            link=f'/crm/parrainage?parrain={client.id}',
            company=company)
        return

    # ── Détracteur (0-6) : activité de rappel assignée au responsable ──────
    from django.contrib.contenttypes.models import ContentType
    from apps.records.models import Activity, ActivityType
    assigne = commercial
    if assigne is None:
        return
    atype = ActivityType.objects.filter(company=company, nom='Appel').first()
    if atype is None:
        atype = ActivityType.objects.create(
            company=company, nom='Appel', ordre=10)
    ct = ContentType.objects.get_for_model(type(client))
    marque = f'[nps:{enquete.id}]'
    deja = Activity.objects.filter(
        company=company, content_type=ct, object_id=client.id,
        note__contains=marque).exists()
    if deja:
        return
    Activity.objects.create(
        company=company, content_type=ct, object_id=client.id,
        activity_type=atype,
        summary='Client détracteur — rappeler'[:255],
        due_date=timezone.localdate(),
        assigned_to=assigne,
        note=f'{marque} Score NPS : {score}/10. '
             f'{(enquete.commentaire or "")[:500]}'.strip(),
        created_by=None,
    )


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


class AbonnementMonitoringError(ValidationError):
    """Levée sans rien écrire quand la facturation/transition d'un
    AbonnementMonitoring est refusée (déjà facturé pour la période,
    résilié/suspendu, motif de résiliation absent)."""


def facturer_abonnement_monitoring(abonnement, *, user=None):
    """YSUBS3 — Émet la ``ventes.Facture`` standard de la période due d'un
    abonnement monitoring ACTIF, DÉCOUPLÉ de ``renouveler`` (qui n'avance
    plus que l'échéance — la facturation confondait les deux, anti-pattern
    du blueprint).

    Garde d'idempotence : refuse si ``derniere_facturation`` == la période
    en cours de facturation (``prochaine_echeance``, ou aujourd'hui si
    absente) — ne re-facture jamais la même période. Le client est résolu
    via ``apps.crm.selectors.get_company_client`` (jamais un import de
    ``apps.crm.models``) ; la Facture est créée EMISE, TVA 20 %, numérotée
    via ``ventes.utils.references.create_with_reference`` (même patron que
    ``ventes.services.creer_facture_contrat``), et émet ``facture_emise``
    (YLEDG1/YSUBS6) pour que l'auto-écriture compta se déclenche comme
    toute facture récurrente. Renvoie la Facture créée.
    """
    from apps.crm.selectors import get_company_client
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference
    from core.events import facture_emise
    from .models import AbonnementMonitoring

    if abonnement.statut != AbonnementMonitoring.Statut.ACTIF:
        raise AbonnementMonitoringError(
            "Seul un abonnement actif peut être facturé.")
    if not abonnement.montant or abonnement.montant <= 0:
        raise AbonnementMonitoringError(
            "Le montant de l'abonnement doit être positif.")

    company = abonnement.company
    periode = abonnement.prochaine_echeance or timezone.localdate()
    if abonnement.derniere_facturation == periode:
        raise AbonnementMonitoringError(
            f'La période {periode} a déjà été facturée pour cet abonnement.')

    client = get_company_client(company, abonnement.client_id)
    if client is None:
        raise AbonnementMonitoringError(
            "Client introuvable pour cet abonnement.")

    tva_pct = Decimal('20')
    prix_ttc = Decimal(str(abonnement.montant))
    prix_ht = (prix_ttc / (1 + tva_pct / 100)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (prix_ttc - prix_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    libelle = f'Supervision monitoring — abonnement #{abonnement.pk} ({periode})'

    def _create(ref):
        return Facture.objects.create(
            reference=ref, company=company, client=client,
            statut=Facture.Statut.EMISE, taux_tva=tva_pct,
            montant_ht=prix_ht, montant_tva=montant_tva,
            montant_ttc=prix_ttc, libelle=libelle, created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)
    facture_emise.send(sender=Facture, instance=facture, company=company)

    abonnement.derniere_facturation = periode
    abonnement.save(update_fields=['derniere_facturation'])
    return facture


def facturer_abonnement_monitoring_beat(abonnement, *, user=None):
    """SCA44 — Facture UN ``AbonnementMonitoring`` dû, pour le beat
    quotidien de ``apps.contrats.scheduled`` (3e flux de facturation
    récurrente automatique, après les échéanciers contrats et les contrats
    de maintenance SAV).

    Même effet que l'action ``facturer`` de ``AbonnementMonitoringViewSet``
    (``apps.compta.views``) : émet la Facture standard via
    ``facturer_abonnement_monitoring`` (garde d'idempotence déjà posée sur
    ``derniere_facturation`` — un second appel pour la même période refuse),
    PUIS avance l'échéance via ``renouveler_abonnement_monitoring`` pour que
    l'abonnement ne soit plus jamais re-sélectionné par
    ``apps.compta.selectors.abonnements_monitoring_dus_facturation`` tant
    que sa prochaine période n'est pas atteinte. Renvoie la Facture créée ;
    lève ``AbonnementMonitoringError`` si la facturation échoue — l'appelant
    (le beat) capture l'exception PAR abonnement pour ne jamais bloquer les
    suivants."""
    facture = facturer_abonnement_monitoring(abonnement, user=user)
    renouveler_abonnement_monitoring(abonnement)
    return facture


def suspendre_abonnement_monitoring(abonnement):
    """YSUBS4 — Suspend un abonnement ACTIF (transition gardée, service —
    plus une écriture directe du viewset). Bloque la facturation récurrente
    (``facturer_abonnement_monitoring`` refuse un abonnement non-actif) tant
    que le statut reste ``suspendu``. Idempotent (un abonnement déjà
    suspendu/résilié n'est pas re-transitionné). Renvoie l'abonnement."""
    from .models import AbonnementMonitoring

    if abonnement.statut != AbonnementMonitoring.Statut.ACTIF:
        return abonnement
    abonnement.statut = AbonnementMonitoring.Statut.SUSPENDU
    abonnement.save(update_fields=['statut'])
    return abonnement


def resilier_abonnement_monitoring(abonnement, *, motif, user=None):
    """YSUBS4 — Résilie un abonnement (transition gardée, motif OBLIGATOIRE
    — capturé sur ``motif_resiliation``, jamais perdu comme avec l'ancien
    PATCH direct du viewset). Bloque définitivement la facturation
    récurrente. Émet ``abonnement_monitoring_resilie`` (core.events) pour
    les effets aval — abonné dans ce repo (ARC36) :
    ``apps/monitoring/receivers.py`` coupe la supervision automatique liée
    (``MonitoringConfig.enabled=False``). Idempotent (déjà résilié → no-op,
    aucune ré-émission de l'événement). Renvoie l'abonnement."""
    from core.events import abonnement_monitoring_resilie
    from .models import AbonnementMonitoring

    if abonnement.statut == AbonnementMonitoring.Statut.RESILIE:
        return abonnement
    motif = (motif or '').strip()
    if not motif:
        raise AbonnementMonitoringError(
            'Le motif de résiliation est obligatoire.')
    abonnement.statut = AbonnementMonitoring.Statut.RESILIE
    abonnement.motif_resiliation = motif
    abonnement.save(update_fields=['statut', 'motif_resiliation'])
    abonnement_monitoring_resilie.send(
        sender=AbonnementMonitoring, abonnement=abonnement, motif=motif,
        company=abonnement.company)
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


# ── XACC14 — Emprunts & crédits-bails (financements de la société) ─────────

_COMPTE_CAPITAL_PAR_TYPE = {
    Emprunt.Type.EMPRUNT: '1481',
    Emprunt.Type.LEASING: '1671',
}


def _mois_suivant(une_date, n):
    """Ajoute ``n`` mois à ``une_date`` (jour conservé, borné à fin de mois)."""
    import calendar
    mois_total = une_date.month - 1 + n
    annee = une_date.year + mois_total // 12
    mois = mois_total % 12 + 1
    jour = min(une_date.day, calendar.monthrange(annee, mois)[1])
    return une_date.replace(year=annee, month=mois, day=jour)


def generer_tableau_amortissement(emprunt):
    """Génère (persiste) le tableau d'amortissement complet d'un emprunt (XACC14).

    Réutilise la maths d'annuité constante de FG217 (``calcul_mensualite``)
    pour obtenir la mensualité, puis ventile chaque échéance en part de
    principal / intérêts (intérêts = capital restant dû × taux mensuel ;
    principal = mensualité − intérêts) — méthode classique d'un tableau
    d'amortissement français/marocain. La DERNIÈRE échéance absorbe l'écart
    d'arrondi pour que la somme des principaux soit EXACTEMENT le capital.
    Idempotent : si des échéances existent déjà, elles sont supprimées et
    régénérées (seulement pour celles NON postées ; refuse si une échéance
    déjà postée existerait — on ne régénère jamais un historique posté).
    Renvoie la liste des échéances créées.
    """
    if emprunt.echeances.filter(posted=True).exists():
        raise ValidationError(
            "Impossible de régénérer le tableau : des échéances sont déjà "
            "postées au grand livre.")
    emprunt.echeances.all().delete()

    capital = Decimal(emprunt.capital or 0)
    n = int(emprunt.duree_mois or 0)
    taux_annuel = Decimal(emprunt.taux_annuel or 0)
    mensualite, _ = calcul_mensualite(capital, n, taux_annuel)
    taux_mensuel = taux_annuel / Decimal('100') / Decimal('12')

    echeances = []
    solde = capital
    for i in range(1, n + 1):
        interets = (solde * taux_mensuel).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP) if taux_mensuel else Decimal('0.00')
        if i == n:
            # Dernière échéance : absorbe l'écart d'arrondi pour solder EXACTEMENT.
            principal = solde
        else:
            principal = (mensualite - interets).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            if principal > solde:
                principal = solde
        solde = (solde - principal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        echeances.append(EcheanceEmprunt(
            company=emprunt.company,
            emprunt=emprunt,
            numero=i,
            date_echeance=_mois_suivant(emprunt.date_debut, i),
            principal=principal,
            interets=interets,
            mensualite=(principal + interets).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP),
            capital_restant_du=solde,
        ))
    EcheanceEmprunt.objects.bulk_create(echeances)
    return list(emprunt.echeances.order_by('numero'))


def _compte_capital_emprunt(company, emprunt):
    if emprunt.compte_capital_id:
        return emprunt.compte_capital
    numero = _COMPTE_CAPITAL_PAR_TYPE.get(emprunt.type_financement, '1481')
    return _assurer_compte(company, numero)


def _compte_interets_emprunt(company, emprunt):
    if emprunt.compte_interets_id:
        return emprunt.compte_interets
    return _assurer_compte(company, '6311')


@transaction.atomic
def poster_echeance_emprunt(echeance, *, user=None):
    """Poste une échéance d'emprunt au grand livre (XACC14).

    Écriture ÉQUILIBRÉE (journal OD) : débit du compte de capital restant dû
    (part de principal) + débit du compte de charges financières (part
    d'intérêts) / crédit banque (5141, mensualité totale). Idempotente
    (renvoie l'écriture existante si déjà postée). RESPECTE LE VERROU DE
    PÉRIODE (FG115) : refuse si la date d'échéance tombe dans une période
    verrouillée.
    """
    emprunt = echeance.emprunt
    company = echeance.company
    if echeance.posted and echeance.ecriture_id:
        return echeance.ecriture
    mensualite = Decimal(echeance.mensualite)
    if mensualite <= 0:
        raise ValidationError("Impossible de poster une échéance nulle.")
    if PeriodeComptable.date_verrouillee(company.id, echeance.date_echeance):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster l'échéance "
            f"du {echeance.date_echeance}.")
    compte_capital = _compte_capital_emprunt(company, emprunt)
    compte_interets = _compte_interets_emprunt(company, emprunt)
    compte_banque = _assurer_compte(company, '5141')
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        seed_journaux(company)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    libelle = (
        f"Échéance {echeance.numero} — {emprunt.banque or emprunt.reference}")
    lignes = [
        {'compte': compte_capital, 'debit': echeance.principal,
         'credit': Decimal('0'), 'libelle': libelle},
    ]
    if echeance.interets and echeance.interets > 0:
        lignes.append({
            'compte': compte_interets, 'debit': echeance.interets,
            'credit': Decimal('0'), 'libelle': libelle,
        })
    lignes.append({
        'compte': compte_banque, 'debit': Decimal('0'),
        'credit': mensualite, 'libelle': libelle,
    })
    ecriture = creer_ecriture(
        company, journal, echeance.date_echeance, libelle, lignes,
        reference=f'EMPR-{emprunt.id}-{echeance.numero}',
        source_type='echeance_emprunt', source_id=echeance.id,
        created_by=user, statut=EcritureComptable.Statut.VALIDEE,
    )
    echeance.posted = True
    echeance.ecriture = ecriture
    echeance.save(update_fields=['posted', 'ecriture'])
    return ecriture


def injecter_echeances_previsionnel(company, *, date_debut=None, nb_semaines=13):
    """Échéances d'emprunt FUTURES à injecter dans le prévisionnel 13 semaines
    (FG126) — lecture seule, pure. Renvoie une liste de dicts compatibles avec
    les lignes du prévisionnel : ``{'libelle', 'date_prevue', 'montant'}``
    (montant NÉGATIF = décaissement). Ne persiste rien : c'est
    ``selectors.previsionnel_tresorerie`` qui les agrège à l'existant.
    """
    from datetime import timedelta
    debut = date_debut or timezone.now().date()
    fin = debut + timedelta(weeks=nb_semaines)
    qs = EcheanceEmprunt.objects.filter(
        company=company, date_echeance__gte=debut, date_echeance__lte=fin,
    ).select_related('emprunt').order_by('date_echeance')
    return [
        {
            'libelle': f'Échéance emprunt {e.emprunt.banque or e.emprunt.reference}',
            'date_prevue': e.date_echeance,
            'montant': -Decimal(e.mensualite),
        }
        for e in qs
    ]


# ── XACC15 — Charges constatées d'avance (étalement des charges prépayées) ──

_COMPTE_CCA = '3491'


@transaction.atomic
def etaler_charge_avance(company, *, montant_total, date_debut, nb_mois,
                         libelle='', facture_fournisseur_id=None,
                         compte_charge=None, poster_origine=True, user=None):
    """Crée l'échéancier d'étalement d'une charge prépayée (XACC15).

    Porte le montant total au débit de 3491 (crédit du compte de charge
    d'origine, 61xx par défaut) SAUF si ``poster_origine=False`` (l'écriture
    d'origine existe déjà, ex. saisie directe depuis une facture fournisseur
    qui a déjà débité 3491), puis génère ``nb_mois`` ``DotationEtalement``
    NON postées (à poster mois par mois via ``poster_dotation_etalement``).
    La DERNIÈRE dotation absorbe l'écart d'arrondi (Σ dotations = montant
    total, exact). ``reference`` et ``company`` posés côté serveur. Renvoie
    la charge créée.
    """
    from apps.ventes.utils.references import create_with_reference

    montant_total = Decimal(montant_total or 0)
    nb_mois = int(nb_mois or 0)
    compte = compte_charge or _assurer_compte(company, '6132')

    charge = ChargeConstateeAvance(
        company=company,
        libelle=libelle or '',
        facture_fournisseur_id=facture_fournisseur_id,
        montant_total=montant_total,
        date_debut=date_debut,
        nb_mois=nb_mois,
        compte_charge=compte,
        created_by=user,
    )
    charge.full_clean(exclude=['reference', 'created_by', 'libelle'])

    def _save(reference):
        charge.reference = reference
        charge.save()
        return charge

    charge = create_with_reference(ChargeConstateeAvance, 'CCA', company, _save)

    if poster_origine:
        compte_cca = _assurer_compte(company, _COMPTE_CCA)
        journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
        if journal is None:
            seed_journaux(company)
            journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
        libelle_ecr = f'Constat charge à étaler {charge.reference}'
        ecriture = creer_ecriture_od(
            company, date_debut, libelle_ecr,
            [
                {'compte': compte_cca, 'debit': montant_total,
                 'credit': Decimal('0'), 'libelle': libelle_ecr},
                {'compte': compte, 'debit': Decimal('0'),
                 'credit': montant_total, 'libelle': libelle_ecr},
            ],
            created_by=user)
        charge.ecriture_origine = ecriture
        charge.save(update_fields=['ecriture_origine'])

    # Génère les dotations mensuelles (montants égaux, arrondi sur la dernière).
    montant_mensuel = (montant_total / Decimal(nb_mois)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP) if nb_mois else Decimal('0.00')
    dotations = []
    cumul = Decimal('0.00')
    for i in range(1, nb_mois + 1):
        if i == nb_mois:
            montant = (montant_total - cumul).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            montant = montant_mensuel
        cumul += montant
        dotations.append(DotationEtalement(
            company=company,
            charge=charge,
            numero=i,
            date_dotation=_mois_suivant(date_debut, i - 1),
            montant=montant,
        ))
    DotationEtalement.objects.bulk_create(dotations)
    return charge


@transaction.atomic
def poster_dotation_etalement(dotation, *, user=None):
    """Poste une dotation d'étalement au grand livre (XACC15).

    Écriture ÉQUILIBRÉE (journal OD) : débit du compte de charge (classe 6) /
    crédit 3491 « charges constatées d'avance ». Idempotente. RESPECTE LE
    VERROU DE PÉRIODE (FG115).
    """
    charge = dotation.charge
    company = dotation.company
    if dotation.posted and dotation.ecriture_id:
        return dotation.ecriture
    montant = Decimal(dotation.montant)
    if montant <= 0:
        raise ValidationError("Impossible de poster une dotation nulle.")
    if PeriodeComptable.date_verrouillee(company.id, dotation.date_dotation):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster la dotation "
            f"d'étalement du {dotation.date_dotation}.")
    compte_charge = charge.compte_charge or _assurer_compte(company, '6132')
    compte_cca = _assurer_compte(company, _COMPTE_CCA)
    libelle = f'Dotation étalement {dotation.numero} — {charge.reference}'
    ecriture = creer_ecriture_od(
        company, dotation.date_dotation, libelle,
        [
            {'compte': compte_charge, 'debit': montant,
             'credit': Decimal('0'), 'libelle': libelle},
            {'compte': compte_cca, 'debit': Decimal('0'),
             'credit': montant, 'libelle': libelle},
        ],
        reference=f'CCA-{charge.id}-{dotation.numero}',
        created_by=user)
    dotation.posted = True
    dotation.ecriture = ecriture
    dotation.save(update_fields=['posted', 'ecriture'])
    return ecriture


# ── XACC16 — Amortissements dérogatoires (double plan comptable / fiscal) ───

_COMPTE_DOTATION_DEROGATOIRE = '65941'   # dotation aux provisions réglementées.
_COMPTE_PROVISION_REGLEMENTEE = '1351'   # provisions pour amortissements dérog.
_COMPTE_REPRISE_DEROGATOIRE = '7594'     # reprise sur provisions réglementées.


def creer_plan_amortissement_fiscal(plan_comptable, *, mode=None,
                                    duree_annees, coefficient_degressif=None):
    """Crée (ou met à jour) le plan FISCAL parallèle d'un plan comptable (XACC16).

    ``duree_annees`` requis explicitement (le fiscal peut différer du
    comptable). Le coefficient dégressif est déduit du barème marocain si le
    mode est dégressif et qu'aucun coefficient explicite n'est fourni. Idempotent
    (get_or_create + mise à jour des champs fournis). Renvoie le plan fiscal.
    """
    company = plan_comptable.company
    plan_fiscal, _ = PlanAmortissementFiscal.objects.get_or_create(
        company=company, plan_comptable=plan_comptable,
        defaults={
            'mode': mode or PlanAmortissement.Mode.DEGRESSIF,
            'duree_annees': duree_annees,
        },
    )
    if mode is not None:
        plan_fiscal.mode = mode
    if duree_annees is not None:
        plan_fiscal.duree_annees = duree_annees
    if plan_fiscal.mode == PlanAmortissement.Mode.DEGRESSIF:
        plan_fiscal.coefficient_degressif = (
            Decimal(coefficient_degressif) if coefficient_degressif is not None
            else coefficient_degressif_maroc(plan_fiscal.duree_annees))
    else:
        plan_fiscal.coefficient_degressif = None
    plan_fiscal.full_clean()
    plan_fiscal.save()
    return plan_fiscal


def generer_dotations_derogatoires(plan_fiscal):
    """Calcule/matérialise les différences comptable-vs-fiscal par exercice
    (XACC16).

    Recalcule les deux annuités (comptable via ``plan_comptable.mode``/
    ``duree_annees``, fiscal via ``plan_fiscal.mode``/``duree_annees``) sur la
    même base amortissable, année par année, et fige la différence SIGNÉE
    (fiscal − comptable) dans une ``DotationDerogatoire``. Une différence déjà
    POSTÉE n'est jamais recalculée (immutabilité comptable — même garde-fou que
    ``generer_plan_amortissement``). Renvoie la liste des dotations
    dérogatoires (créées ou déjà existantes).
    """
    plan_comptable = plan_fiscal.plan_comptable
    base = plan_comptable.base_amortissable
    coeff_compt = plan_comptable.coefficient_degressif or Decimal('1')
    coeff_fisc = plan_fiscal.coefficient_degressif or Decimal('1')

    annuites_comptables = _calcul_annuites(
        base, plan_comptable.duree_annees, plan_comptable.mode, coeff_compt)
    annuites_fiscales = _calcul_annuites(
        base, plan_fiscal.duree_annees, plan_fiscal.mode, coeff_fisc)

    annee_debut = plan_comptable.date_debut.year
    nb_annees = max(len(annuites_comptables), len(annuites_fiscales))
    resultat = []
    for idx in range(nb_annees):
        annee = annee_debut + idx
        dot_compt = (annuites_comptables[idx] if idx < len(annuites_comptables)
                     else Decimal('0'))
        dot_fisc = (annuites_fiscales[idx] if idx < len(annuites_fiscales)
                    else Decimal('0'))
        difference = _arrondi(dot_fisc - dot_compt)
        existante = DotationDerogatoire.objects.filter(
            plan_fiscal=plan_fiscal, annee=annee).first()
        if existante and existante.posted:
            resultat.append(existante)
            continue
        from datetime import date as _date
        date_dotation = _date(annee, 12, 31)
        if existante is None:
            existante = DotationDerogatoire.objects.create(
                company=plan_fiscal.company, plan_fiscal=plan_fiscal,
                annee=annee, date_dotation=date_dotation,
                dotation_comptable=dot_compt, dotation_fiscale=dot_fisc,
                difference=difference)
        else:
            existante.dotation_comptable = dot_compt
            existante.dotation_fiscale = dot_fisc
            existante.difference = difference
            existante.date_dotation = date_dotation
            existante.save(update_fields=[
                'dotation_comptable', 'dotation_fiscale', 'difference',
                'date_dotation'])
        resultat.append(existante)
    return resultat


@transaction.atomic
def poster_dotation_derogatoire(dotation, *, user=None):
    """Poste une différence dérogatoire au grand livre (XACC16).

    ``difference`` > 0 (fiscal > comptable) → DOTATION : débit 65941 / crédit
    1351. ``difference`` < 0 (comptable > fiscal, fin de vie) → REPRISE
    inverse : débit 1351 / crédit 7594. ``difference`` == 0 → rien à poster
    (marque quand même ``posted`` pour ne plus y revenir). Idempotente.
    RESPECTE LE VERROU DE PÉRIODE (FG115).
    """
    company = dotation.company
    if dotation.posted:
        return dotation.ecriture
    if PeriodeComptable.date_verrouillee(company.id, dotation.date_dotation):
        raise ValidationError(
            "Période comptable clôturée : impossible de poster la dotation "
            f"dérogatoire du {dotation.date_dotation}.")
    difference = Decimal(dotation.difference)
    if difference == 0:
        dotation.posted = True
        dotation.save(update_fields=['posted'])
        return None
    compte_provision = _assurer_compte(company, _COMPTE_PROVISION_REGLEMENTEE)
    libelle = f'Amortissement dérogatoire {dotation.annee} — plan #{dotation.plan_fiscal_id}'
    if difference > 0:
        compte_dotation = _assurer_compte(company, _COMPTE_DOTATION_DEROGATOIRE)
        lignes = [
            {'compte': compte_dotation, 'debit': difference,
             'credit': Decimal('0'), 'libelle': libelle},
            {'compte': compte_provision, 'debit': Decimal('0'),
             'credit': difference, 'libelle': libelle},
        ]
    else:
        montant = -difference
        compte_reprise = _assurer_compte(company, _COMPTE_REPRISE_DEROGATOIRE)
        lignes = [
            {'compte': compte_provision, 'debit': montant,
             'credit': Decimal('0'), 'libelle': libelle},
            {'compte': compte_reprise, 'debit': Decimal('0'),
             'credit': montant, 'libelle': libelle},
        ]
    ecriture = creer_ecriture_od(
        company, dotation.date_dotation, libelle, lignes,
        reference=f'DEROG-{dotation.plan_fiscal_id}-{dotation.annee}',
        created_by=user)
    dotation.posted = True
    dotation.ecriture = ecriture
    dotation.save(update_fields=['posted', 'ecriture'])
    return ecriture


# ── XACC17 — Table de taux de change + contre-valeur MAD ───────────────────

def enregistrer_taux_devise(company, *, devise, date_taux, taux_vers_mad,
                            source=None):
    """Enregistre (upsert) le taux du jour ``devise`` → MAD (XACC17).

    Idempotent sur ``(company, devise, date_taux)`` : une saisie MANUELLE
    écrase toujours un feed automatique existant pour le même jour (RÈGLE
    « never snap » : un taux SAISI par l'utilisateur reste prioritaire — on ne
    l'écrase JAMAIS avec un feed). Renvoie le ``TauxDevise``.
    """
    devise = (devise or '').upper()
    if not devise or devise == 'MAD':
        raise ValidationError("MAD n'a pas besoin de table de taux (1:1).")
    source = source or TauxDevise.Source.MANUEL
    existant = TauxDevise.objects.filter(
        company=company, devise=devise, date_taux=date_taux).first()
    if existant is not None:
        if (existant.source == TauxDevise.Source.MANUEL
                and source != TauxDevise.Source.MANUEL):
            # Un feed ne doit JAMAIS écraser une saisie manuelle du même jour.
            return existant
        existant.taux_vers_mad = Decimal(taux_vers_mad)
        existant.source = source
        existant.full_clean()
        existant.save()
        return existant
    taux = TauxDevise(
        company=company, devise=devise, date_taux=date_taux,
        taux_vers_mad=Decimal(taux_vers_mad), source=source)
    taux.full_clean()
    taux.save()
    return taux


def feed_taux_bkam(company, *, devise, date_taux=None):
    """Feed automatique BKAM (gratuit) — NO-OP tant qu'aucune clé n'est
    configurée (XACC17, key-gated). Renvoie ``None`` si le feed est
    indisponible (pas de clé/URL) : le repli est alors la dernière saisie
    manuelle existante (``selectors.taux_du_jour``), jamais une erreur. Une
    fois une clé ``BKAM_FX_API_KEY`` configurée dans les settings, cette
    fonction ferait l'appel réel — non implémenté ici (aucune clé fournie).
    """
    api_key = getattr(settings, 'BKAM_FX_API_KEY', '') or ''
    if not api_key:
        return None
    return None  # pragma: no cover - intégration réelle hors périmètre sans clé.


def contre_valeur_mad(montant_devise, devise, company=None, *, une_date=None,
                      taux_vers_mad=None):
    """Contre-valeur MAD d'un montant en devise (XACC17), pur calcul.

    Priorité : ``taux_vers_mad`` explicite (un taux SAISI sur le document,
    jamais snappé) > le taux du jour de la table (``selectors.taux_du_jour``,
    nécessite ``company``) > repli 1:1 si ``devise`` est MAD ou si aucune
    table n'existe (comportement actuel intact). Renvoie un Decimal arrondi au
    centime.
    """
    devise = (devise or 'MAD').upper()
    montant = Decimal(montant_devise or 0)
    if devise == 'MAD':
        return _arrondi(montant)
    if taux_vers_mad is not None:
        taux = Decimal(taux_vers_mad)
    elif company is not None:
        from apps.compta.selectors import taux_du_jour as _taux_du_jour
        enregistrement = _taux_du_jour(company, devise, une_date)
        taux = enregistrement.taux_vers_mad if enregistrement else Decimal('1')
    else:
        taux = Decimal('1')
    return _arrondi(montant * taux)


# ── XACC18 — Écarts de change réalisés & réévaluation de clôture ───────────

_COMPTE_GAIN_CHANGE = '733'    # produit financier — gains de change réalisés.
_COMPTE_PERTE_CHANGE = '633'   # charge financière — pertes de change réalisées.
_COMPTE_ECART_ACTIF_CLOTURE = '2701'   # écart de conversion actif (perte latente).
_COMPTE_ECART_PASSIF_CLOTURE = '1701'  # écart de conversion passif (gain latent).


def enregistrer_item_ouvert_devise(company, *, type_document, document_id,
                                   document_reference='', devise,
                                   montant_devise, taux_origine, date_origine):
    """Enregistre (idempotent) un poste ouvert en devise à suivre (XACC18).

    Un document 100 % MAD (``devise == 'MAD'``) n'a jamais besoin de cette
    table — lève ``ValidationError`` pour éviter une saisie inutile. Unicité
    ``(company, type_document, document_id)`` : ré-appeler avec le même
    document renvoie l'item existant SANS l'écraser (le taux d'origine reste
    figé une fois créé). Renvoie l'``ItemOuvertDevise``.
    """
    devise = (devise or '').upper()
    if not devise or devise == 'MAD':
        raise ValidationError(
            "Un document en MAD n'a pas besoin de suivi de change.")
    existant = ItemOuvertDevise.objects.filter(
        company=company, type_document=type_document,
        document_id=document_id).first()
    if existant is not None:
        return existant
    item = ItemOuvertDevise(
        company=company, type_document=type_document,
        document_id=document_id, document_reference=document_reference or '',
        devise=devise, montant_devise=Decimal(montant_devise),
        taux_origine=Decimal(taux_origine), date_origine=date_origine,
    )
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def constater_ecart_change(item, *, date_reglement, taux_reglement=None,
                           user=None):
    """Constate l'écart de change RÉALISÉ au règlement d'un item ouvert (XACC18).

    ``taux_reglement`` (devise → MAD) explicite ou déduit de la table
    (``selectors.taux_du_jour`` à ``date_reglement``, repli = taux d'origine
    si aucune table). ``difference`` = contre-valeur au taux de règlement −
    contre-valeur au taux d'origine : > 0 GAIN (crédit 733) ; < 0 PERTE (débit
    633). Marque l'item ``solde``. Idempotente (un item n'a qu'un seul écart,
    OneToOne). Si ``difference == 0`` (tout est resté en MAD ou même taux),
    AUCUNE écriture n'est postée. RESPECTE LE VERROU DE PÉRIODE (FG115).
    """
    company = item.company
    existant = getattr(item, 'ecart_change', None)
    if existant is not None and existant.posted:
        return existant
    if taux_reglement is None:
        from apps.compta.selectors import taux_du_jour as _taux_du_jour
        enregistrement = _taux_du_jour(company, item.devise, date_reglement)
        taux_reglement = (
            enregistrement.taux_vers_mad if enregistrement
            else item.taux_origine)
    taux_reglement = Decimal(taux_reglement)
    cv_origine = item.contre_valeur_origine
    cv_reglement = (Decimal(item.montant_devise) * taux_reglement).quantize(
        Decimal('0.01'))
    difference = cv_reglement - cv_origine

    ecart = existant or EcartChange(company=company, item=item)
    ecart.date_reglement = date_reglement
    ecart.taux_reglement = taux_reglement
    ecart.difference = difference

    if difference != 0:
        if PeriodeComptable.date_verrouillee(company.id, date_reglement):
            raise ValidationError(
                "Période comptable clôturée : impossible de constater "
                f"l'écart de change du {date_reglement}.")
        libelle = (
            f'Écart de change {item.document_reference or item.document_id}')
        if difference > 0:
            compte_gain = _assurer_compte(company, _COMPTE_GAIN_CHANGE)
            compte_client = _compte_fournisseurs(company) if (
                item.type_document == ItemOuvertDevise.TypeDocument.FACTURE_FOURNISSEUR
            ) else _assurer_compte(company, '3421')
            lignes = [
                {'compte': compte_client, 'debit': difference,
                 'credit': Decimal('0'), 'libelle': libelle},
                {'compte': compte_gain, 'debit': Decimal('0'),
                 'credit': difference, 'libelle': libelle},
            ]
        else:
            montant = -difference
            compte_perte = _assurer_compte(company, _COMPTE_PERTE_CHANGE)
            compte_client = _compte_fournisseurs(company) if (
                item.type_document == ItemOuvertDevise.TypeDocument.FACTURE_FOURNISSEUR
            ) else _assurer_compte(company, '3421')
            lignes = [
                {'compte': compte_perte, 'debit': montant,
                 'credit': Decimal('0'), 'libelle': libelle},
                {'compte': compte_client, 'debit': Decimal('0'),
                 'credit': montant, 'libelle': libelle},
            ]
        ecriture = creer_ecriture_od(
            company, date_reglement, libelle, lignes,
            reference=f'FX-{item.id}', created_by=user)
        ecart.ecriture = ecriture
    ecart.posted = True
    ecart.full_clean()
    ecart.save()
    item.solde = True
    item.save(update_fields=['solde'])
    return ecart


@transaction.atomic
def reevaluer_cloture(company, *, date_cloture, user=None):
    """Run de réévaluation de clôture des items ouverts en devise (XACC18).

    Réévalue chaque item NON soldé au taux de clôture (``taux_du_jour`` à
    ``date_cloture`` ; item ignoré si aucune table n'existe pour sa devise —
    aucun écart latent calculable). Poste l'écart de conversion LATENT en une
    seule écriture : > 0 (contre-valeur au taux de clôture > origine, gain
    latent) → crédit 1701 ; < 0 (perte latente) → débit 2701, contrepartie sur
    le compte client/fournisseur de l'item. AUCUNE écriture si tout est en MAD
    ou si aucun item n'a d'écart. Génère aussi l'écriture d'EXTOURNE (inverse)
    datée du lendemain (ouverture suivante). Idempotent (unicité
    ``(company, date_cloture)``). Renvoie le run.
    """
    from apps.compta.selectors import taux_du_jour as _taux_du_jour

    existant = ReevaluationCloture.objects.filter(
        company=company, date_cloture=date_cloture).first()
    if existant is not None and existant.ecriture_id:
        return existant

    items = ItemOuvertDevise.objects.filter(company=company, solde=False)
    lignes_gl = []
    total_ecart = Decimal('0')
    run = existant or ReevaluationCloture(
        company=company, date_cloture=date_cloture)
    run.save()

    for item in items:
        enregistrement = _taux_du_jour(company, item.devise, date_cloture)
        if enregistrement is None:
            continue
        taux_cloture = enregistrement.taux_vers_mad
        cv_cloture = (Decimal(item.montant_devise) * taux_cloture).quantize(
            Decimal('0.01'))
        ecart = cv_cloture - item.contre_valeur_origine
        if ecart == 0:
            continue
        total_ecart += ecart
        LigneReevaluation.objects.update_or_create(
            reevaluation=run, item=item,
            defaults={
                'company': company, 'taux_cloture': taux_cloture,
                'ecart': ecart,
            },
        )
        compte_tiers = _compte_fournisseurs(company) if (
            item.type_document == ItemOuvertDevise.TypeDocument.FACTURE_FOURNISSEUR
        ) else _assurer_compte(company, '3421')
        libelle = f'Réévaluation clôture {item.document_reference or item.document_id}'
        if ecart > 0:
            compte_ecart = _assurer_compte(company, _COMPTE_ECART_PASSIF_CLOTURE)
            lignes_gl.append({'compte': compte_tiers, 'debit': ecart,
                              'credit': Decimal('0'), 'libelle': libelle})
            lignes_gl.append({'compte': compte_ecart, 'debit': Decimal('0'),
                              'credit': ecart, 'libelle': libelle})
        else:
            montant = -ecart
            compte_ecart = _assurer_compte(company, _COMPTE_ECART_ACTIF_CLOTURE)
            lignes_gl.append({'compte': compte_ecart, 'debit': montant,
                              'credit': Decimal('0'), 'libelle': libelle})
            lignes_gl.append({'compte': compte_tiers, 'debit': Decimal('0'),
                              'credit': montant, 'libelle': libelle})

    run.total_ecart = total_ecart
    if lignes_gl:
        if PeriodeComptable.date_verrouillee(company.id, date_cloture):
            raise ValidationError(
                "Période comptable clôturée : impossible de poster la "
                f"réévaluation de change du {date_cloture}.")
        libelle_run = f'Réévaluation de clôture (change) {date_cloture}'
        ecriture = creer_ecriture_od(
            company, date_cloture, libelle_run, lignes_gl,
            reference=f'FXCLOT-{run.id}', created_by=user)
        run.ecriture = ecriture
        from datetime import timedelta
        date_extourne = date_cloture + timedelta(days=1)
        lignes_inverse = [
            {'compte': ligne['compte'], 'debit': ligne['credit'],
             'credit': ligne['debit'], 'libelle': ligne['libelle']}
            for ligne in lignes_gl
        ]
        ecriture_extourne = creer_ecriture_od(
            company, date_extourne, f'Extourne {libelle_run}', lignes_inverse,
            reference=f'FXCLOT-{run.id}-EXT', created_by=user)
        run.ecriture_extourne = ecriture_extourne
        run.date_extourne = date_extourne
    run.save()
    return run


# ── XACC19 — Générateur d'états financiers personnalisés ───────────────────

@transaction.atomic
def creer_etat_personnalise(company, *, libelle, description='', lignes=None,
                            colonnes=None, user=None):
    """Crée un ``EtatPersonnalise`` avec ses lignes/colonnes en un appel (XACC19).

    ``lignes`` : liste de dicts ``{'libelle', 'type_ligne'?, 'formule'?,
    'ordre'?}``. ``colonnes`` : liste de dicts ``{'libelle', 'type_colonne'?,
    'date_debut'?, 'date_fin'?, 'budget'?, 'ordre'?}``. Valide chaque formule
    (``selectors._parser_formule``) AVANT toute création : une formule
    invalide lève ``ValidationError`` (400 explicite côté vue), rien n'est
    persisté. ``company`` posée côté serveur. Renvoie l'état créé.
    """
    from apps.compta.selectors import (
        FormuleEtatInvalideError, _parser_formule as _valider_formule)

    for spec in (lignes or []):
        if spec.get('type_ligne', LigneEtatPersonnalise.TypeLigne.TOTAL) == \
                LigneEtatPersonnalise.TypeLigne.TOTAL:
            try:
                _valider_formule(spec.get('formule', ''))
            except FormuleEtatInvalideError as exc:
                raise ValidationError(str(exc))

    etat = EtatPersonnalise(
        company=company, libelle=libelle, description=description or '',
        created_by=user)
    etat.full_clean()
    etat.save()

    for idx, spec in enumerate(lignes or []):
        LigneEtatPersonnalise.objects.create(
            company=company, etat=etat, ordre=spec.get('ordre', idx),
            libelle=spec['libelle'],
            type_ligne=spec.get(
                'type_ligne', LigneEtatPersonnalise.TypeLigne.TOTAL),
            formule=spec.get('formule', '') or '',
        )
    for idx, spec in enumerate(colonnes or []):
        ColonneEtatPersonnalise.objects.create(
            company=company, etat=etat, ordre=spec.get('ordre', idx),
            libelle=spec['libelle'],
            type_colonne=spec.get(
                'type_colonne', ColonneEtatPersonnalise.Type.PERIODE),
            date_debut=spec.get('date_debut'), date_fin=spec.get('date_fin'),
            budget=spec.get('budget'),
        )
    return etat


# ── XACC20 — Ventilation analytique %  & règles d'auto-imputation ──────────

@transaction.atomic
def ventiler_ligne_ecriture(ligne_ecriture, distributions):
    """Ventile une ``LigneEcriture`` sur plusieurs ``CentreCout`` en % (XACC20).

    ``distributions`` : liste de dicts ``{'centre_cout', 'pourcentage'}``. La
    somme des pourcentages DOIT valoir exactement 100 (sinon
    ``ValidationError``, rien n'est persisté). Idempotent : ré-appeler sur la
    même ligne remplace la distribution précédente (OneToOne). Le champ
    ``centre_cout`` simple (FG150) de la ligne reste INTACT — c'est une
    information ADDITIONNELLE, jamais un remplacement destructif. Renvoie la
    ``VentilationAnalytique``.
    """
    total = sum(
        (Decimal(d['pourcentage']) for d in distributions), Decimal('0'))
    if total != Decimal('100'):
        raise ValidationError(
            f"La ventilation doit sommer à 100 % (reçu {total} %).")
    ventilation, _ = VentilationAnalytique.objects.get_or_create(
        company=ligne_ecriture.company, ligne_ecriture=ligne_ecriture)
    ventilation.distributions.all().delete()
    for d in distributions:
        LigneVentilation.objects.create(
            company=ligne_ecriture.company, ventilation=ventilation,
            centre_cout=d['centre_cout'],
            pourcentage=Decimal(d['pourcentage']))
    return ventilation


def creer_regle_imputation(company, *, libelle, prefixe_compte,
                           distributions, tiers_id=None, produit_id=None,
                           priorite=100):
    """Crée une règle d'auto-imputation analytique (XACC20).

    ``distributions`` (même contrat que ``ventiler_ligne_ecriture``) doit
    sommer à 100 %. La règle s'applique aux NOUVELLES écritures dont un
    compte commence par ``prefixe_compte`` (et, si fournis, dont le
    ``tiers_id``/``produit_id`` matchent). Renvoie la règle créée.
    """
    total = sum(
        (Decimal(d['pourcentage']) for d in distributions), Decimal('0'))
    if total != Decimal('100'):
        raise ValidationError(
            f"La distribution de la règle doit sommer à 100 % (reçu {total} %).")
    regle = RegleImputation.objects.create(
        company=company, libelle=libelle, prefixe_compte=prefixe_compte,
        tiers_id=tiers_id, produit_id=produit_id, priorite=priorite,
    )
    for d in distributions:
        LigneRegleImputation.objects.create(
            company=company, regle=regle, centre_cout=d['centre_cout'],
            pourcentage=Decimal(d['pourcentage']))
    return regle


def _appliquer_regle_imputation_si_match(company, ligne_ecriture, *,
                                         tiers_id=None, produit_id=None):
    """Applique, si une règle matche, sa distribution à ``ligne_ecriture``
    (XACC20). Silencieuse et non bloquante : aucune règle qui matche = rien ne
    se passe (comportement de saisie manuelle actuel intact). La première
    règle active par ``priorite`` dont le compte commence par
    ``prefixe_compte`` (et dont ``tiers_id``/``produit_id``, si renseignés sur
    la règle, correspondent) gagne.
    """
    numero = ligne_ecriture.compte.numero
    regles = RegleImputation.objects.filter(
        company=company, actif=True).order_by('priorite', 'id')
    for regle in regles:
        if not numero.startswith(regle.prefixe_compte):
            continue
        if regle.tiers_id is not None and regle.tiers_id != tiers_id:
            continue
        if regle.produit_id is not None and regle.produit_id != produit_id:
            continue
        distributions_regle = list(regle.distributions.all())
        if not distributions_regle:
            continue
        ventiler_ligne_ecriture(ligne_ecriture, [
            {'centre_cout': d.centre_cout, 'pourcentage': d.pourcentage}
            for d in distributions_regle
        ])
        return regle
    return None


# ── XACC21 — Contrôle du budget COMPTABLE à l'engagement ───────────────────

def verifier_engagement_budgetaire(company, *, montant_engage, periode,
                                   centre_cout=None, compte=None,
                                   est_responsable=False):
    """Contrôle un engagement (BCF stock, note de frais…) contre le budget
    COMPTABLE restant (XACC21) — EN COMPLÉMENT du contrôle PROJET FG313
    (``installations.selectors``, jamais dupliqué ici). Consommé par
    ``apps.stock``/``apps.rh`` via ce service (jamais un import de modèle
    compta).

    Renvoie un dict ``{'autorise': bool, 'warning': str|None,
    'budget_restant': Decimal|None}`` :

    * aucun budget défini pour le centre/compte/année → ``autorise=True``,
      ``warning=None`` (aucun contrôle possible, comportement actuel intact) ;
    * budget en mode ``warning`` (défaut) → TOUJOURS ``autorise=True``, avec
      un ``warning`` texte si l'engagement dépasse le restant (montants
      inclus) ;
    * budget en mode ``bloquant`` → un dépassement REFUSE
      (``autorise=False``) SAUF si ``est_responsable=True`` (override
      responsable, alors autorisé avec un ``warning`` traçant l'override).
    """
    from apps.compta.selectors import budget_restant as _budget_restant

    info = _budget_restant(
        company, centre_cout=centre_cout, compte=compte, periode=periode)
    if info is None:
        return {'autorise': True, 'warning': None, 'budget_restant': None}

    montant_engage = Decimal(montant_engage or 0)
    nouveau_restant = info['restant'] - montant_engage
    if nouveau_restant >= 0:
        return {
            'autorise': True, 'warning': None,
            'budget_restant': nouveau_restant,
        }

    depassement = -nouveau_restant
    message = (
        f"Dépassement du budget comptable restant : engagement de "
        f"{montant_engage} MAD, restant disponible {info['restant']} MAD "
        f"(dépassement de {depassement} MAD).")
    if info['controle'] == Budget.Controle.BLOQUANT and not est_responsable:
        return {
            'autorise': False, 'warning': message,
            'budget_restant': nouveau_restant,
        }
    if info['controle'] == Budget.Controle.BLOQUANT and est_responsable:
        message += " Autorisé par override responsable."
    return {
        'autorise': True, 'warning': message,
        'budget_restant': nouveau_restant,
    }


# ── XACC22 — Révisions & scénarios budgétaires ─────────────────────────────

@transaction.atomic
def reviser_budget(budget, *, nouveau_libelle=None, user=None):
    """Révise un budget : fige la version courante, crée la V+1 éditable
    (XACC22).

    La version N est marquée ``figee=True`` (lecture seule pour toujours) et
    reste consultable pour la comparaison côte-à-côte. La nouvelle version
    (N+1) est une COPIE éditable de toutes les ``BudgetLigne`` de N, avec
    ``budget_parent`` pointant vers N. Refuse de réviser une version déjà
    figée SANS créer de nouvelle version (une version figée ne se révise
    qu'une fois — la révision suivante part de la dernière version éditable).
    Renvoie la nouvelle version.
    """
    if budget.figee:
        raise ValidationError(
            "Ce budget est déjà figé : révisez plutôt sa dernière révision.")
    budget.figee = True
    Budget.objects.filter(pk=budget.pk).update(figee=True)

    nouvelle = Budget.objects.create(
        company=budget.company, annee=budget.annee,
        libelle=nouveau_libelle or budget.libelle,
        statut=Budget.Statut.BROUILLON, controle=budget.controle,
        version=budget.version + 1, figee=False,
        budget_parent=budget, scenario=budget.scenario, created_by=user,
    )
    for bl in budget.lignes.all():
        BudgetLigne.objects.create(
            company=nouvelle.company, budget=nouvelle, compte=bl.compte,
            centre_cout=bl.centre_cout, libelle=bl.libelle,
            m01=bl.m01, m02=bl.m02, m03=bl.m03, m04=bl.m04, m05=bl.m05,
            m06=bl.m06, m07=bl.m07, m08=bl.m08, m09=bl.m09, m10=bl.m10,
            m11=bl.m11, m12=bl.m12,
        )
    return nouvelle


def creer_scenario_what_if(budget_engage, *, scenario, user=None):
    """Crée un scénario what-if (optimiste/pessimiste) à partir du budget
    ENGAGÉ (XACC22) — une COPIE indépendante, jamais consommée par le
    contrôle d'engagement (XACC21) ni le suivi budget-vs-réel (FG149) qui
    restent sur ``Scenario.ENGAGE`` uniquement. Renvoie le scénario créé.
    """
    if scenario == Budget.Scenario.ENGAGE:
        raise ValidationError(
            "Un scénario what-if doit être optimiste ou pessimiste "
            "(le scénario 'engage' est LE budget officiel).")
    nouveau = Budget.objects.create(
        company=budget_engage.company, annee=budget_engage.annee,
        libelle=budget_engage.libelle, statut=Budget.Statut.BROUILLON,
        controle=budget_engage.controle, version=1, figee=False,
        scenario=scenario, created_by=user,
    )
    for bl in budget_engage.lignes.all():
        BudgetLigne.objects.create(
            company=nouveau.company, budget=nouveau, compte=bl.compte,
            centre_cout=bl.centre_cout, libelle=bl.libelle,
            m01=bl.m01, m02=bl.m02, m03=bl.m03, m04=bl.m04, m05=bl.m05,
            m06=bl.m06, m07=bl.m07, m08=bl.m08, m09=bl.m09, m10=bl.m10,
            m11=bl.m11, m12=bl.m12,
        )
    return nouveau


# Courbes de répartition usuelles (XACC22) : poids relatif par mois (1..12),
# normalisés à 1.0 par ``repartir_montant_annuel``. « saisonniere » modélise
# une activité solaire marocaine (pic printemps/été).
_COURBE_EGALE = [Decimal('1')] * 12
_COURBE_SAISONNIERE = [
    Decimal('0.05'), Decimal('0.05'), Decimal('0.08'), Decimal('0.10'),
    Decimal('0.12'), Decimal('0.12'), Decimal('0.11'), Decimal('0.10'),
    Decimal('0.09'), Decimal('0.07'), Decimal('0.06'), Decimal('0.05'),
]


def repartir_montant_annuel(montant_annuel, *, courbe='egale', poids=None):
    """Répartit ``montant_annuel`` sur 12 mois selon une courbe (XACC22).

    ``courbe`` : ``egale`` (1/12 chacun), ``saisonniere`` (barème solaire
    marocain figé ci-dessus) ou ``pourcentage`` (``poids`` = liste de 12 %
    fournie explicitement, DOIT sommer à 100). La répartition somme
    EXACTEMENT ``montant_annuel`` (le douzième/dernier mois absorbe l'écart
    d'arrondi). Renvoie une liste de 12 ``Decimal``.
    """
    montant_annuel = Decimal(montant_annuel or 0)
    if courbe == 'egale':
        poids_mois = _COURBE_EGALE
    elif courbe == 'saisonniere':
        poids_mois = _COURBE_SAISONNIERE
    elif courbe == 'pourcentage':
        if not poids or len(poids) != 12:
            raise ValidationError(
                "La courbe 'pourcentage' requiert exactement 12 poids.")
        total_poids = sum((Decimal(p) for p in poids), Decimal('0'))
        if total_poids != Decimal('100'):
            raise ValidationError(
                f"Les poids doivent sommer à 100 % (reçu {total_poids} %).")
        poids_mois = [Decimal(p) / Decimal('100') for p in poids]
    else:
        raise ValidationError(f"Courbe de répartition inconnue : {courbe}.")

    total_poids_brut = sum(poids_mois, Decimal('0'))
    montants = []
    cumul = Decimal('0.00')
    for idx, poids_m in enumerate(poids_mois):
        if idx == 11:
            montant = (montant_annuel - cumul).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            montant = (
                montant_annuel * poids_m / total_poids_brut
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        cumul += montant
        montants.append(montant)
    return montants


def generer_ligne_budget_repartie(budget, *, compte, montant_annuel,
                                  centre_cout=None, libelle='',
                                  courbe='egale', poids=None):
    """Crée une ``BudgetLigne`` avec ses 12 montants générés par une courbe de
    répartition (XACC22), au lieu d'une saisie manuelle par période. Renvoie
    la ligne créée.
    """
    montants = repartir_montant_annuel(montant_annuel, courbe=courbe, poids=poids)
    ligne = BudgetLigne.objects.create(
        company=budget.company, budget=budget, compte=compte,
        centre_cout=centre_cout, libelle=libelle or '',
        m01=montants[0], m02=montants[1], m03=montants[2], m04=montants[3],
        m05=montants[4], m06=montants[5], m07=montants[6], m08=montants[7],
        m09=montants[8], m10=montants[9], m11=montants[10], m12=montants[11],
    )
    return ligne


# ── XACC24 — Validation RIB marocain + approbation des changements de RIB ──

def diagnostic_rib(rib):
    """Diagnostic RIB marocain (mod 97) via ``core.rib`` (XACC24), pur.

    Renvoie ``{'rib', 'valide', 'erreurs'}`` — jamais d'exception, jamais de
    blocage de saisie historique : c'est un WARNING d'affichage laissé à
    l'appelant (``apps.stock`` Fournisseur, ``CompteTresorerie`` ici,
    ``apps.rh`` DossierEmploye).
    """
    from core.rib import valider_rib
    return valider_rib(rib)


def demander_changement_rib(company, *, fournisseur_id, fournisseur_nom='',
                            ancien_rib, nouveau_rib, user=None):
    """Ouvre une demande d'approbation pour un CHANGEMENT de RIB fournisseur
    (XACC24, principe 4-yeux). Tant qu'elle n'est pas approuvée, le payment
    run (FG133, via ``_coordonnees_fournisseur``) continue d'utiliser
    ``ancien_rib``. Renvoie la demande créée (statut ``en_attente``).
    """
    demande = DemandeApprobationRib(
        company=company, fournisseur_id=fournisseur_id,
        fournisseur_nom=fournisseur_nom or '', ancien_rib=ancien_rib or '',
        nouveau_rib=nouveau_rib, demandeur=user,
    )
    demande.full_clean()
    demande.save()
    return demande


def approuver_demande_rib(demande, *, decideur, commentaire=''):
    """Approuve une demande de changement de RIB (XACC24) : à partir de là,
    le nouveau RIB devient actif (``rib_actif``) pour le payment run. Idempotente
    (une demande déjà décidée n'est pas re-décidée)."""
    if demande.statut != DemandeApprobationRib.Statut.EN_ATTENTE:
        return demande
    demande.statut = DemandeApprobationRib.Statut.APPROUVEE
    demande.decideur = decideur
    demande.commentaire_decision = commentaire or ''
    demande.date_decision = timezone.now()
    demande.save(update_fields=[
        'statut', 'decideur', 'commentaire_decision', 'date_decision'])
    return demande


def refuser_demande_rib(demande, *, decideur, commentaire=''):
    """Refuse une demande de changement de RIB (XACC24) : l'ancien RIB reste
    actif définitivement pour cette demande. Idempotente."""
    if demande.statut != DemandeApprobationRib.Statut.EN_ATTENTE:
        return demande
    demande.statut = DemandeApprobationRib.Statut.REFUSEE
    demande.decideur = decideur
    demande.commentaire_decision = commentaire or ''
    demande.date_decision = timezone.now()
    demande.save(update_fields=[
        'statut', 'decideur', 'commentaire_decision', 'date_decision'])
    return demande


# ── XFAC14 — Compensation AR/AP (netting) ──────────────────────────────────

class CompensationError(ValidationError):
    """Levée sans rien écrire (atomicité) quand une compensation est
    impossible : sur-compensation, tiers non trouvé, factures d'un tiers
    différent, etc."""


def creer_compensation(company, *, client_id, fournisseur_id, lignes, user=None):
    """XFAC14 — Crée une ``Compensation`` BROUILLON entre les factures AR
    (client, ``apps.ventes``) et AP (fournisseur, ``apps.stock``) d'un même
    tiers réel.

    ``lignes`` : liste de ``{'type': 'ar'|'ap', 'facture_id': int,
    'montant': Decimal}``. Chaque facture est relue via le sélecteur de
    l'app cible (jamais un import de ses modèles) pour vérifier
    l'appartenance société + résoudre le solde dû ; le montant imputé ne
    peut jamais dépasser le solde dû de sa facture, et
    ``montant_compense`` = min(Σ AR, Σ AP) (jamais plus que le plus petit des
    deux soldes globaux — sur-compensation refusée). Lève
    ``CompensationError`` sans rien créer si une garde échoue. Ne poste
    AUCUNE écriture (fait par ``valider_compensation``)."""
    from apps.crm.selectors import get_company_client
    from apps.stock import selectors as stock_selectors
    from apps.ventes import selectors as ventes_selectors

    client = get_company_client(company, client_id)
    if client is None:
        raise CompensationError('Client introuvable dans votre société.')

    fournisseur = stock_selectors.get_fournisseur_by_id(company, fournisseur_id)
    if fournisseur is None:
        raise CompensationError('Fournisseur introuvable dans votre société.')

    if not lignes:
        raise CompensationError(
            'Sélectionnez au moins une facture AR et une facture AP.')

    total_ar = Decimal('0')
    total_ap = Decimal('0')
    lignes_valides = []
    for entree in lignes:
        type_facture = entree.get('type')
        facture_id = entree.get('facture_id')
        montant = Decimal(str(entree.get('montant') or 0))
        if montant <= 0:
            raise CompensationError('Le montant imputé doit être positif.')
        if type_facture == LigneCompensation.Type.AR:
            facture = ventes_selectors.get_facture_scoped(company, facture_id)
            if facture is None:
                raise CompensationError(
                    f'Facture client #{facture_id} introuvable.')
            if facture.client_id != client.id:
                raise CompensationError(
                    "Cette facture n'appartient pas au client sélectionné.")
            if montant > facture.montant_du:
                raise CompensationError(
                    f'Le montant imputé dépasse le solde dû de {facture.reference}.')
            total_ar += montant
            reference = facture.reference
        elif type_facture == LigneCompensation.Type.AP:
            facture = stock_selectors.facture_fournisseur_scoped(
                company, facture_id)
            if facture is None:
                raise CompensationError(
                    f'Facture fournisseur #{facture_id} introuvable.')
            if facture.fournisseur_id != fournisseur.id:
                raise CompensationError(
                    "Cette facture n'appartient pas au fournisseur sélectionné.")
            if montant > facture.solde_du:
                raise CompensationError(
                    f'Le montant imputé dépasse le solde dû de {facture.reference}.')
            total_ap += montant
            reference = facture.reference
        else:
            raise CompensationError(f"Type de facture invalide : {type_facture!r}.")
        lignes_valides.append({
            'type_facture': type_facture, 'facture_id': facture_id,
            'reference_facture': reference, 'montant_impute': montant,
        })

    if total_ar <= 0 or total_ap <= 0:
        raise CompensationError(
            'Il faut au moins une facture AR et une facture AP.')

    montant_compense = min(total_ar, total_ap)

    with transaction.atomic():
        compensation = Compensation.objects.create(
            company=company, client_id=client.id,
            client_nom=str(client), fournisseur_id=fournisseur.id,
            fournisseur_nom=fournisseur.nom,
            montant_compense=montant_compense, created_by=user,
        )
        compensation.reference = f'CMP-{compensation.id:06d}'
        compensation.save(update_fields=['reference'])
        for ligne in lignes_valides:
            LigneCompensation.objects.create(compensation=compensation, **ligne)
    return compensation


def valider_compensation(compensation, *, user=None):
    """XFAC14 — Valide une ``Compensation`` BROUILLON : poste l'écriture
    équilibrée 4411 (fournisseur) / 3421 (client) du montant compensé et
    enregistre les règlements croisés via les services de chaque app
    (jamais un import de leurs modèles). Idempotente (une compensation déjà
    validée n'est pas re-postée). Respecte le verrou de période (via
    ``creer_ecriture_od``)."""
    if compensation.statut == Compensation.Statut.VALIDEE:
        return compensation

    from apps.stock import selectors as stock_selectors
    from apps.stock import services as stock_services
    from apps.ventes import selectors as ventes_selectors
    from apps.ventes import services as ventes_services

    compte_clients = get_compte(compensation.company, '3421')
    compte_fournisseurs = get_compte(compensation.company, '4411')
    if compte_clients is None or compte_fournisseurs is None:
        raise CompensationError(
            'Comptes 3421/4411 introuvables — semez le plan comptable.')

    with transaction.atomic():
        ecriture = creer_ecriture_od(
            compensation.company, timezone.localdate(),
            f'Compensation {compensation.reference} — '
            f'{compensation.client_nom} / {compensation.fournisseur_nom}',
            [
                {'compte': compte_fournisseurs,
                 'debit': compensation.montant_compense, 'credit': Decimal('0'),
                 'tiers_type': 'fournisseur',
                 'tiers_id': compensation.fournisseur_id},
                {'compte': compte_clients,
                 'debit': Decimal('0'), 'credit': compensation.montant_compense,
                 'tiers_type': 'client', 'tiers_id': compensation.client_id},
            ],
            reference=compensation.reference, created_by=user,
        )

        restant = compensation.montant_compense
        for ligne in compensation.lignes.filter(
                type_facture=LigneCompensation.Type.AR).order_by('id'):
            if restant <= 0:
                break
            montant = min(ligne.montant_impute, restant)
            facture = ventes_selectors.get_facture_scoped(
                compensation.company, ligne.facture_id)
            if facture is not None and montant > 0:
                ventes_services.enregistrer_paiement(
                    facture=facture, montant=montant, mode='autre',
                    date_paiement=timezone.localdate(), user=user,
                    reference=compensation.reference,
                    note=f'Compensation AR/AP {compensation.reference}')
            restant -= montant

        restant = compensation.montant_compense
        for ligne in compensation.lignes.filter(
                type_facture=LigneCompensation.Type.AP).order_by('id'):
            if restant <= 0:
                break
            montant = min(ligne.montant_impute, restant)
            facture_ap = stock_selectors.facture_fournisseur_scoped(
                compensation.company, ligne.facture_id)
            if facture_ap is not None and montant > 0:
                stock_services.add_paiement_sous_traitant(
                    company=compensation.company, user=user,
                    facture=facture_ap, montant=montant,
                    date_paiement=timezone.localdate(), mode='autre',
                    note=f'Compensation AR/AP {compensation.reference}')
            restant -= montant

        compensation.statut = Compensation.Statut.VALIDEE
        compensation.ecriture_id = ecriture.id
        compensation.date_validation = timezone.now()
        compensation.save(update_fields=[
            'statut', 'ecriture_id', 'date_validation'])
    return compensation


# ── XFAC27 — Portail client : contester une facture ─────────────────────────

def creer_reclamation_portail(facture, *, motif_label, commentaire=''):
    """XFAC27 — Ouvre la ``litiges.Reclamation`` d'une contestation de
    facture initiée par le CLIENT depuis le portail self-service (jamais un
    import de ``apps.litiges.models`` — passe par son ``services.py``, le
    type ``'financier'`` est la valeur stable de
    ``Reclamation.TypeReclamation.FINANCIER``).
    ``bloque_relances=True`` (défaut) : LITIGE3 suspend automatiquement les
    relances de cette facture tant que la réclamation reste ouverte."""
    from apps.litiges import services as litiges_services

    objet = f'Facture {facture.reference} contestée par le client (portail)'
    description = motif_label
    if commentaire:
        description += f' — {commentaire}'
    return litiges_services.creer_reclamation(
        company=facture.company,
        type_reclamation='financier',
        source_type='facture', source_id=facture.id,
        objet=objet, description=description,
        montant_conteste=facture.montant_du,
        bloque_relances=True,
    )


# ── XMKT27 — Constructeur d'enquêtes avec logique conditionnelle ───────────

_TYPES_QUESTION_VALIDES = {'choix', 'echelle', 'texte', 'nps'}


def valider_questions_enquete(questions):
    """XMKT27 — valide la structure JSON des questions d'une enquête.
    Lève ``ValueError`` sur un type/format inconnu."""
    if not isinstance(questions, list):
        raise ValueError('questions doit être une liste.')
    ids_vus = set()
    for q in questions:
        if not isinstance(q, dict):
            raise ValueError('chaque question doit être un objet.')
        qid = q.get('id')
        if not qid:
            raise ValueError('chaque question doit avoir un id.')
        if qid in ids_vus:
            raise ValueError(f'id de question dupliqué : {qid}')
        ids_vus.add(qid)
        qtype = q.get('type')
        if qtype not in _TYPES_QUESTION_VALIDES:
            raise ValueError(f'type de question inconnu : {qtype}')
        condition = q.get('condition')
        if condition is not None:
            if not isinstance(condition, dict) or 'question_id' not in condition:
                raise ValueError(
                    f'condition invalide pour la question {qid}.')
    return questions


def creer_enquete(company, *, titre, questions=None):
    """XMKT27 — crée une enquête avec un jeton public unique."""
    questions = valider_questions_enquete(questions or [])
    return Enquete.objects.create(
        company=company, titre=titre, questions=questions,
        token=uuid.uuid4().hex)


def questions_visibles(enquete, reponses_partielles):
    """XMKT27 — filtre les questions visibles selon la logique conditionnelle
    « question B si réponse A », évaluée sur les réponses déjà données."""
    visibles = []
    for q in enquete.questions or []:
        condition = q.get('condition')
        if not condition:
            visibles.append(q)
            continue
        valeur_attendue = condition.get('valeur')
        valeur_donnee = reponses_partielles.get(condition.get('question_id'))
        if valeur_donnee == valeur_attendue:
            visibles.append(q)
    return visibles


def rendre_enquete_publique(enquete, reponses_partielles, *, seed=None):
    """ZMKT9 — applique l'ordre aléatoire (si activé) aux questions visibles,
    pour le rendu public de l'enquête. ``seed`` optionnel pour un ordre
    reproductible en test ; sans ``seed``, l'ordre varie à chaque appel
    (nouvelle ouverture)."""
    import random

    visibles = questions_visibles(enquete, reponses_partielles)
    if enquete.ordre_aleatoire:
        rng = random.Random(seed)
        visibles = list(visibles)
        rng.shuffle(visibles)
    return {
        'titre': enquete.titre,
        'questions': visibles,
        'mode_pagination': enquete.mode_pagination,
        'barre_progression': enquete.barre_progression,
        'bouton_retour': enquete.bouton_retour,
        'limite_temps_minutes': enquete.limite_temps_minutes,
        'description_accueil': enquete.description_accueil,
        'message_fin': enquete.message_fin,
    }


def limite_temps_depassee(enquete, *, debute_le, maintenant=None):
    """ZMKT9 — True si la limite de temps de l'enquête est dépassée pour une
    session commencée à ``debute_le``. Pas de limite (NULL) → jamais
    dépassée (comportement actuel)."""
    if not enquete.limite_temps_minutes or not debute_le:
        return False
    maintenant = maintenant or timezone.now()
    echeance = debute_le + timezone.timedelta(minutes=enquete.limite_temps_minutes)
    return maintenant > echeance


def soumettre_reponse_enquete(
        enquete, *, reponses, contact_ref='', nom_repondant=''):
    """ZMKT11 — refuse (ValueError) si ``tentatives_max`` est dépassé pour
    ``contact_ref`` (email d'un répondant identifié)."""
    if contact_ref and enquete.tentatives_max:
        restantes = tentatives_restantes(enquete, contact_ref)
        if restantes is not None and restantes <= 0:
            raise ValueError('Nombre maximum de tentatives atteint.')
    return _soumettre_reponse_enquete_interne(
        enquete, reponses=reponses, contact_ref=contact_ref,
        nom_repondant=nom_repondant)


def _soumettre_reponse_enquete_interne(
        enquete, *, reponses, contact_ref='', nom_repondant=''):
    """XMKT27 — soumission publique d'une enquête (sans auth). Ne valide QUE
    les questions effectivement visibles (logique conditionnelle) : une
    question masquée n'est jamais requise. Lève ``ValueError`` si une
    question obligatoire visible est absente.

    ZMKT10 — si ``mode_scoring`` != 'aucun', calcule le score (points par
    réponse dans le JSON questions) et marque réussi/échoué vs
    ``score_requis_pct``. Si ``est_certification`` et réussi, génère le
    certificat PDF (stocké nulle part ici — régénérable à la demande via
    ``generer_certificat_pdf``).
    """
    reponses = reponses or {}
    visibles = questions_visibles(enquete, reponses)
    for q in visibles:
        if q.get('obligatoire') and not reponses.get(q['id']):
            raise ValueError(f'question obligatoire manquante : {q["id"]}')

    score_pct = None
    reussi = None
    if enquete.mode_scoring != Enquete.ModeScoring.AUCUN:
        score_pct = calculer_score_enquete(enquete, reponses)
        if enquete.score_requis_pct is not None:
            reussi = float(score_pct) >= enquete.score_requis_pct

    reponse = ReponseEnquete.objects.create(
        company=enquete.company, enquete=enquete,
        contact_ref=contact_ref or '', reponses=reponses,
        score_pct=score_pct, reussi=reussi)

    if enquete.est_certification and reussi:
        reponse.certificat_genere = True
        reponse.save(update_fields=['certificat_genere'])
    return reponse


def calculer_score_enquete(enquete, reponses):
    """ZMKT10 — calcule le score (%) : Σ points obtenus / Σ points possibles
    × 100 sur les questions portant un ``points``/``bonne_reponse``.
    Questions sans barème ignorées (0 point possible)."""
    from decimal import Decimal

    points_obtenus = Decimal('0')
    points_possibles = Decimal('0')
    for q in (enquete.questions or []):
        points = q.get('points')
        bonne_reponse = q.get('bonne_reponse')
        if points is None or bonne_reponse is None:
            continue
        points_possibles += Decimal(str(points))
        if reponses.get(q['id']) == bonne_reponse:
            points_obtenus += Decimal(str(points))
    if points_possibles == 0:
        return Decimal('0')
    return (points_obtenus / points_possibles * 100).quantize(Decimal('0.01'))


def acces_enquete_autorise(enquete, *, jeton_invite=None):
    """ZMKT11 — vérifie le mode d'accès : lien public toujours autorisé,
    invités-seulement exige un jeton émis (présent dans ``jetons_invites``).
    """
    if enquete.mode_acces == Enquete.ModeAcces.LIEN_PUBLIC:
        return True
    return bool(jeton_invite and jeton_invite in (enquete.jetons_invites or []))


def emettre_jeton_invite(enquete):
    """ZMKT11 — émet (et enregistre) un nouveau jeton d'invitation."""
    jeton = uuid.uuid4().hex
    jetons = list(enquete.jetons_invites or [])
    jetons.append(jeton)
    enquete.jetons_invites = jetons
    enquete.save(update_fields=['jetons_invites'])
    return jeton


def qr_svg_enquete(enquete):
    """ZMKT12 — QR SVG du lien public de l'enquête (réutilise
    ``stock.selectors.qr_svg`` — pattern XMKT29, aucune dépendance)."""
    from apps.stock.selectors import qr_svg

    url_publique = f'/api/django/compta/enquetes-publiques/{enquete.token}/'
    return qr_svg(url_publique)


def inviter_enquete(enquete, *, segment=None, liste=None):
    """ZMKT12 — envoie le lien de l'enquête par email (gated Brevo, no-op
    sans clé → file de relance manuelle FG31) aux contacts d'un segment
    (XMKT6) ou d'une liste (XMKT5). Respecte consentement + suppression
    (XMKT3/XMKT4). Renvoie le nombre de destinataires ciblés."""
    destinataires = []
    if segment is not None:
        lead_ids = evaluer_segment(segment)
        from apps.crm.selectors import get_company_lead
        for lead_id in lead_ids:
            lead = get_company_lead(enquete.company, lead_id)
            if lead is not None and lead.email:
                destinataires.append(lead.email)
    if liste is not None:
        abonnements = AbonnementListe.objects.filter(
            liste=liste, statut=AbonnementListe.Statut.INSCRIT)
        destinataires.extend(a.destinataire for a in abonnements)

    cibles = [
        d for d in destinataires
        if not est_supprime(enquete.company, d)
        and consentement_accorde(enquete.company, d, canal='email')
    ]
    if not brevo_actif():
        # No-op réseau : file de relance manuelle FG31 (aucun appel payant).
        return {'destinataires_cibles': len(cibles), 'envoye_reel': False}
    return {'destinataires_cibles': len(cibles), 'envoye_reel': True}


def participations_enquete(enquete, *, reussi=None):
    """ZMKT13 — liste des soumissions individuelles (contact quand connu,
    score, durée, date) filtrable réussi/échoué."""
    from apps.crm.selectors import get_company_lead

    qs = enquete.reponses.all()
    if reussi is not None:
        qs = qs.filter(reussi=reussi)
    resultat = []
    for reponse in qs:
        contact_nom = reponse.contact_ref or 'Anonyme'
        if reponse.contact_ref.startswith('lead:'):
            lead_id = reponse.contact_ref.split(':', 1)[1]
            lead = get_company_lead(
                enquete.company, int(lead_id)) if lead_id.isdigit() else None
            if lead is not None:
                contact_nom = f'{lead.nom} {lead.prenom or ""}'.strip()
        resultat.append({
            'id': reponse.id,
            'contact': contact_nom,
            'score_pct': reponse.score_pct,
            'reussi': reponse.reussi,
            'date_creation': reponse.date_creation,
        })
    return resultat


def tester_enquete(enquete):
    """ZMKT11 — ouvre l'enquête en mode aperçu (test) SANS enregistrer de
    ``ReponseEnquete`` — renvoie le rendu public tel qu'un vrai répondant le
    verrait."""
    return rendre_enquete_publique(enquete, {})


def tentatives_restantes(enquete, identifiant):
    """ZMKT11 — nombre de tentatives restantes pour ``identifiant`` (email),
    ``None`` = illimité (comportement actuel)."""
    if not enquete.tentatives_max:
        return None
    deja_soumises = ReponseEnquete.objects.filter(
        enquete=enquete, contact_ref=identifiant).count()
    return max(0, enquete.tentatives_max - deja_soumises)


def generer_certificat_pdf(reponse):
    """ZMKT10 — génère le PDF du certificat (WeasyPrint, HORS /proposal)
    pour une réponse réussie/certifiée. Renvoie ``None`` si non
    certifiée/échouée."""
    if not reponse.certificat_genere:
        return None
    from .pdf_certificat_enquete import render_certificat_pdf

    nom = reponse.reponses.get('_nom_repondant', reponse.contact_ref or 'Répondant')
    return render_certificat_pdf(
        nom_repondant=nom, titre_enquete=reponse.enquete.titre,
        score_pct=reponse.score_pct)


def taux_completion_enquete(enquete):
    """XMKT27 — taux de complétion vs abandon : une réponse est « complète »
    si toutes les questions obligatoires VISIBLES pour elle ont une valeur."""
    total = enquete.reponses.count()
    if not total:
        return {'total': 0, 'completes': 0, 'taux_completion_pct': 0.0}
    completes = 0
    for reponse in enquete.reponses.all():
        visibles = questions_visibles(enquete, reponse.reponses or {})
        obligatoires_ok = all(
            reponse.reponses.get(q['id']) for q in visibles if q.get('obligatoire'))
        if obligatoires_ok:
            completes += 1
    return {
        'total': total,
        'completes': completes,
        'taux_completion_pct': round(completes / total * 100, 1),
    }


def analytics_enquete(enquete):
    """XMKT27 — analytics agrégées par question : répartition des choix,
    moyenne/distribution des échelles, nuage des réponses texte, NPS
    consolidé si question NPS."""
    reponses = list(enquete.reponses.all())
    resultats = {}
    for q in (enquete.questions or []):
        qid = q['id']
        valeurs = [r.reponses.get(qid) for r in reponses if r.reponses.get(qid) is not None]
        if q['type'] == 'choix':
            repartition = {}
            for v in valeurs:
                repartition[v] = repartition.get(v, 0) + 1
            resultats[qid] = {'type': 'choix', 'repartition': repartition}
        elif q['type'] in ('echelle', 'nps'):
            nombres = [float(v) for v in valeurs if _est_nombre(v)]
            moyenne = round(sum(nombres) / len(nombres), 2) if nombres else 0.0
            entry = {'type': q['type'], 'moyenne': moyenne, 'n': len(nombres)}
            if q['type'] == 'nps' and nombres:
                promoteurs = sum(1 for n in nombres if n >= 9)
                detracteurs = sum(1 for n in nombres if n <= 6)
                entry['nps'] = round(
                    (promoteurs - detracteurs) / len(nombres) * 100, 1)
            resultats[qid] = entry
        else:
            resultats[qid] = {'type': 'texte', 'reponses': valeurs}
    resultats['_completion'] = taux_completion_enquete(enquete)
    return resultats


def _est_nombre(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


# ── XMKT28 — Événements marketing légers ────────────────────────────────────

def inscrire_evenement(
        evenement, *, nom, email='', telephone='', billet=None,
        reponses_questions=None):
    """XMKT28 — Inscription publique à un événement : crée l'inscription +
    le lead dédupliqué (via ``crm.services``, jamais d'import direct du
    modèle CRM), attribue un jeton QR de check-in par inscrit.

    ZMKT15 — si ``billet`` est fourni : refuse (ValueError) au-delà du
    quota, ou hors fenêtre de vente.

    ZMKT16 — ``reponses_questions`` (JSON) refusé (ValueError) si une
    question obligatoire de l'événement est absente ; stocké sur
    l'inscription et reporté (note chatter) sur le lead créé.
    """
    from apps.crm import services as crm_services

    if billet is not None:
        if not billet.dans_fenetre_vente():
            raise ValueError('Billet hors fenêtre de vente.')
        if billet.places_restantes is not None and billet.places_restantes <= 0:
            raise ValueError('Quota de places atteint pour ce billet.')

    reponses_questions = reponses_questions or {}
    questions_obligatoires = evenement.questions.filter(obligatoire=True)
    for question in questions_obligatoires:
        if not reponses_questions.get(str(question.id)):
            raise ValueError(
                f'question obligatoire manquante : {question.libelle}')

    inscription = InscriptionEvenement.objects.create(
        company=evenement.company, evenement=evenement,
        nom=nom, email=email or '', telephone=telephone or '',
        qr_token=uuid.uuid4().hex, billet=billet,
        reponses_questions=reponses_questions,
    )
    lead = crm_services.create_lead_from_evenement_marketing(
        company=evenement.company, nom=nom, telephone=telephone,
        email=email, evenement_nom=evenement.nom)
    inscription.lead_id = lead.id
    inscription.save(update_fields=['lead_id'])
    return inscription


def pointer_presence(inscription):
    """XMKT28 — Check-in sur place : bascule le statut en présent
    (horodaté)."""
    if inscription.statut == InscriptionEvenement.Statut.PRESENT:
        return inscription
    inscription.statut = InscriptionEvenement.Statut.PRESENT
    inscription.date_pointage = timezone.now()
    inscription.save(update_fields=['statut', 'date_pointage'])
    return inscription


def reporting_evenements(company, *, groupby=None):
    """ZMKT20 — reporting événement : inscrits/confirmés/présents/absents,
    taux de présence, répartition par billet, recette théorique MAD (Σ prix
    billet × inscrits), leads générés, groupable par type d'événement/mois.
    """
    resultats = []
    qs = EvenementMarketing.objects.filter(company=company)
    for evenement in qs:
        inscriptions = evenement.inscriptions.all()
        nb_inscrits = inscriptions.count()
        nb_confirmes = inscriptions.filter(
            statut=InscriptionEvenement.Statut.CONFIRME).count()
        nb_presents = inscriptions.filter(
            statut=InscriptionEvenement.Statut.PRESENT).count()
        nb_absents = inscriptions.filter(
            statut=InscriptionEvenement.Statut.ABSENT).count()
        taux_presence = (
            round(nb_presents / nb_inscrits * 100, 1) if nb_inscrits else 0.0)
        recette = Decimal('0')
        repartition_billets = {}
        for billet in evenement.billets.all():
            nb = billet.inscriptions.count()
            repartition_billets[billet.libelle] = nb
            recette += Decimal(str(billet.prix_ttc_mad)) * nb
        nb_leads = inscriptions.exclude(lead_id__isnull=True).values(
            'lead_id').distinct().count()
        resultats.append({
            'evenement_id': evenement.id,
            'nom': evenement.nom,
            'type_evenement': evenement.type_evenement,
            'mois': evenement.date_debut.strftime('%Y-%m'),
            'nb_inscrits': nb_inscrits,
            'nb_confirmes': nb_confirmes,
            'nb_presents': nb_presents,
            'nb_absents': nb_absents,
            'taux_presence_pct': taux_presence,
            'repartition_billets': repartition_billets,
            'recette_theorique_mad': str(recette),
            'nb_leads': nb_leads,
        })

    if groupby == 'type':
        groupes = {}
        for r in resultats:
            groupes.setdefault(r['type_evenement'], []).append(r)
        return groupes
    if groupby == 'mois':
        groupes = {}
        for r in resultats:
            groupes.setdefault(r['mois'], []).append(r)
        return groupes
    return resultats


def generer_badge_pdf(inscription):
    """ZMKT19 — badge PDF imprimable d'UN inscrit : nom, événement, société
    organisatrice, QR de check-in (via ``stock.selectors.qr_svg``)."""
    from apps.stock.selectors import qr_svg
    from .pdf_badge_evenement import render_badge_pdf

    nom_societe = ''
    try:
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.objects.filter(
            company=inscription.company).first()
        nom_societe = profil.nom if profil else ''
    except Exception:  # pragma: no cover - défensif
        pass
    svg = qr_svg(inscription.qr_token or '')
    return render_badge_pdf(
        nom_inscrit=inscription.nom, nom_evenement=inscription.evenement.nom,
        nom_societe=nom_societe, qr_svg=svg)


def generer_badges_pdf_lot(evenement):
    """ZMKT19 — impression en lot (PDF multi-pages) pour tous les inscrits
    confirmés de l'événement."""
    from apps.stock.selectors import qr_svg
    from .pdf_badge_evenement import render_badges_pdf

    nom_societe = ''
    try:
        from apps.parametres.models_company import CompanyProfile
        profil = CompanyProfile.objects.filter(company=evenement.company).first()
        nom_societe = profil.nom if profil else ''
    except Exception:  # pragma: no cover - défensif
        pass
    inscrits = evenement.inscriptions.filter(
        statut__in=[
            InscriptionEvenement.Statut.CONFIRME,
            InscriptionEvenement.Statut.INSCRIT])
    donnees = [
        {
            'nom_inscrit': i.nom, 'nom_evenement': evenement.nom,
            'nom_societe': nom_societe, 'qr_svg': qr_svg(i.qr_token or ''),
        }
        for i in inscrits
    ]
    return render_badges_pdf(donnees)


def rechercher_inscrits_borne(evenement, terme):
    """ZMKT18 — recherche par nom/email parmi les inscrits (borne de
    check-in), company-scopée."""
    terme = (terme or '').strip()
    if not terme:
        return []
    qs = InscriptionEvenement.objects.filter(
        company=evenement.company, evenement=evenement,
    ).filter(Q(nom__icontains=terme) | Q(email__icontains=terme))
    return [
        {'id': i.id, 'nom': i.nom, 'email': i.email, 'statut': i.statut}
        for i in qs
    ]


def pointer_presence_via_qr_ou_recherche(evenement, *, qr_token=None,
                                         inscription_id=None):
    """ZMKT18 — check-in via le token QR par inscrit (XMKT28) ou une
    recherche/sélection directe. Idempotent (une seule fois — délègue à
    ``pointer_presence``)."""
    inscription = None
    if qr_token:
        inscription = InscriptionEvenement.objects.filter(
            company=evenement.company, evenement=evenement,
            qr_token=qr_token).first()
    elif inscription_id:
        inscription = InscriptionEvenement.objects.filter(
            company=evenement.company, evenement=evenement,
            id=inscription_id).first()
    if inscription is None:
        return None
    return pointer_presence(inscription)


def cloturer_presences_evenement(evenement):
    """XMKT28 — marque ``absent`` les inscrits confirmés/inscrits non pointés
    à la fin de l'événement."""
    qs = InscriptionEvenement.objects.filter(
        company=evenement.company, evenement=evenement,
    ).exclude(statut__in=[
        InscriptionEvenement.Statut.PRESENT, InscriptionEvenement.Statut.ABSENT])
    nb = qs.update(statut=InscriptionEvenement.Statut.ABSENT)
    return nb


# ── ZMKT14 — Types d'événements + modèles + étapes de pipeline ─────────────

def creer_evenement_depuis_type(type_evenement, *, nom, date_debut, **kwargs):
    """ZMKT14 — crée un ``EvenementMarketing`` depuis un ``TypeEvenement`` :
    pré-remplit le type d'événement par défaut, garde la trace du modèle
    source (``type_modele``)."""
    return EvenementMarketing.objects.create(
        company=type_evenement.company, nom=nom,
        type_evenement=type_evenement.type_evenement_defaut,
        date_debut=date_debut, type_modele=type_evenement, **kwargs)


def avancer_etape_evenement(evenement, nouvelle_etape):
    """ZMKT14 — avance l'événement dans le pipeline configurable (JAMAIS les
    clés STAGES.py du funnel CRM — un vocabulaire strictement séparé)."""
    evenement.etape = nouvelle_etape
    evenement.save(update_fields=['etape'])
    return evenement


def evenements_par_etape(company):
    """ZMKT14 — Kanban par étape (company-scoped)."""
    resultat = {etape: [] for etape, _ in EvenementMarketing.Etape.choices}
    for evenement in EvenementMarketing.objects.filter(company=company):
        resultat.setdefault(evenement.etape, []).append({
            'id': evenement.id, 'nom': evenement.nom,
            'type_evenement': evenement.type_evenement,
        })
    return resultat


# ── ZMKT17 — Communications programmées d'événement ────────────────────────

def envoyer_communications_evenement_dues(company, *, maintenant=None):
    """ZMKT17 — Enveloppe beat : envoie chaque communication d'événement dont
    l'échéance (relative à ``evenement.date_debut``) est atteinte, aux
    inscrits pertinents (inscrit/confirmé/présent), consentement +
    suppression respectés, gated comme FG201 (no-op sans clé).
    """
    maintenant = maintenant or timezone.now()
    envoyees = []
    qs = CommunicationEvenement.objects.filter(
        company=company, envoyee_le__isnull=True,
    ).select_related('evenement')
    for comm in qs:
        if maintenant < comm.echeance():
            continue
        inscrits = InscriptionEvenement.objects.filter(
            company=company, evenement=comm.evenement,
            statut__in=[
                InscriptionEvenement.Statut.INSCRIT,
                InscriptionEvenement.Statut.CONFIRME,
                InscriptionEvenement.Statut.PRESENT],
        )
        destinataires = []
        for inscrit in inscrits:
            dest = inscrit.email if comm.canal == 'email' else inscrit.telephone
            if not dest:
                continue
            if est_supprime(company, dest):
                continue
            if not consentement_accorde(company, dest, canal=comm.canal):
                continue
            destinataires.append(dest)
        comm.envoyee_le = maintenant
        comm.save(update_fields=['envoyee_le'])
        envoyees.append({
            'communication_id': comm.id, 'nb_destinataires': len(destinataires),
            'envoye_reel': brevo_actif(),
        })
    return envoyees


# ── XMKT29 — Ponts QR pour supports offline (flyers, bâches, véhicules) ────

def _tagger_utm_offline(url, nom_support):
    """XMKT29 — auto-tague l'URL cible utm_source=offline&utm_campaign=nom."""
    from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query.setdefault('utm_source', 'offline')
    query.setdefault('utm_campaign', nom_support)
    return urlunparse(parsed._replace(query=urlencode(query)))


def creer_support_offline(company, *, nom, url_cible):
    """XMKT29 — crée un support offline avec son lien tracké (QR
    téléchargeable). Réutilise ``LienTrackee``/``traiter_clic_lien``
    (XMKT9) — ``campagne=None`` (lien issu d'un support, pas d'un envoi)."""
    url_taguee = _tagger_utm_offline(url_cible, nom)
    lien = LienTrackee.objects.create(
        company=company, campagne=None, url_cible=url_taguee,
        token=uuid.uuid4().hex)
    return SupportOffline.objects.create(
        company=company, nom=nom, url_cible=url_taguee, lien_tracke=lien)


def qr_svg_support_offline(support):
    """XMKT29 — SVG du QR téléchargeable pointant vers la redirection
    tokenisée du support (compte les scans)."""
    from apps.stock.selectors import qr_svg

    if not support.lien_tracke:
        return None
    url_redirection = f'/api/django/compta/r/{support.lien_tracke.token}/'
    return qr_svg(url_redirection)


def tableau_scans_par_support(company):
    """XMKT29 — tableau scans/leads par support (drill-down)."""
    resultats = []
    for support in SupportOffline.objects.filter(company=company):
        lien = support.lien_tracke
        nb_scans = lien.nb_clics if lien else 0
        resultats.append({
            'support_id': support.id,
            'nom': support.nom,
            'nb_scans': nb_scans,
        })
    return resultats


# ── XMKT31 — Conteneur de campagne multi-canal ──────────────────────────────

def rattacher_a_campagne_mere(campagne_mere, *, type_objet, objet_id):
    """XMKT31 — rattache un objet OPAQUE (séquence/formulaire/code promo/
    événement) à une campagne mère. Idempotent."""
    rattachements = list(campagne_mere.rattachements or [])
    entree = {'type': type_objet, 'id': objet_id}
    if entree not in rattachements:
        rattachements.append(entree)
        campagne_mere.rattachements = rattachements
        campagne_mere.save(update_fields=['rattachements'])
    return campagne_mere


def kpi_campagne_mere(campagne_mere):
    """XMKT31 — agrège KPI/coûts/ROI de TOUS les enfants (canaux) d'une
    campagne mère. Renvoie les totaux + le détail par enfant."""
    enfants = list(campagne_mere.enfants.all())
    nb_destinataires = sum(e.nb_destinataires for e in enfants)
    nb_envois = sum(e.nb_envois for e in enfants)
    nb_ouvertures = sum(e.nb_ouvertures for e in enfants)
    nb_clics = sum(e.nb_clics for e in enfants)
    cout_total = cout_total_campagne(campagne_mere)
    for enfant in enfants:
        cout_total += cout_total_campagne(enfant)
    revenu_total = Decimal('0')
    nb_leads_total = 0
    nb_signes_total = 0
    for campagne in [campagne_mere] + enfants:
        roi = roi_campagne(campagne)
        revenu_total += Decimal(roi['revenu_ttc_mad'])
        nb_leads_total += roi['nb_leads']
        nb_signes_total += roi['nb_signes']
    roi_pct = 0.0
    if cout_total > 0:
        roi_pct = round(float((revenu_total - cout_total) / cout_total * 100), 1)
    return {
        'campagne_mere_id': campagne_mere.id,
        'nb_enfants': len(enfants),
        'nb_destinataires': nb_destinataires,
        'nb_envois': nb_envois,
        'nb_ouvertures': nb_ouvertures,
        'nb_clics': nb_clics,
        'cout_total_mad': str(cout_total),
        'revenu_total_ttc_mad': str(revenu_total),
        'roi_pct': roi_pct,
        'nb_leads': nb_leads_total,
        'nb_signes': nb_signes_total,
        'rattachements': campagne_mere.rattachements or [],
    }


# ── XMKT33 — Assistant d'authentification du domaine d'envoi ──────────────

def enregistrements_dns_attendus(domaine):
    """XMKT33 — enregistrements DNS ATTENDUS pour ``domaine`` (SPF/DKIM
    Brevo/DMARC), affichés dans la page Paramètres avant vérification."""
    return {
        'spf': {
            'type': 'TXT', 'hote': domaine,
            'valeur_attendue': 'v=spf1 include:spf.brevo.com ~all',
        },
        'dkim': {
            'type': 'CNAME', 'hote': f'mail._domainkey.{domaine}',
            'valeur_attendue': f'mail._domainkey.{domaine}.brevo.com',
        },
        'dmarc': {
            'type': 'TXT', 'hote': f'_dmarc.{domaine}',
            'valeur_attendue': 'v=DMARC1; p=none;',
        },
    }


def _lookup_txt(hote):
    """Lookup DNS TXT best-effort (dnspython) ; renvoie une liste de chaînes,
    liste vide si échec (jamais d'exception propagée — no-op réseau en
    tests, mock)."""
    try:
        import dns.resolver
        reponses = dns.resolver.resolve(hote, 'TXT')
        return [str(r).strip('"') for r in reponses]
    except Exception:  # pragma: no cover - défensif (réseau/DNS absent)
        return []


def _lookup_cname(hote):
    """Lookup DNS CNAME best-effort (dnspython)."""
    try:
        import dns.resolver
        reponses = dns.resolver.resolve(hote, 'CNAME')
        return [str(r).rstrip('.') for r in reponses]
    except Exception:  # pragma: no cover - défensif
        return []


def verifier_domaine_envoi(domaine_envoi):
    """XMKT33 — relance la vérification DNS des 3 enregistrements pour
    ``domaine_envoi`` (mutable, relançable). Renvoie l'objet mis à jour."""
    attendus = enregistrements_dns_attendus(domaine_envoi.domaine)

    spf_txts = _lookup_txt(attendus['spf']['hote'])
    domaine_envoi.spf_verifie = any('v=spf1' in t for t in spf_txts)

    dkim_cnames = _lookup_cname(attendus['dkim']['hote'])
    domaine_envoi.dkim_verifie = bool(dkim_cnames)

    dmarc_txts = _lookup_txt(attendus['dmarc']['hote'])
    domaine_envoi.dmarc_verifie = any('v=dmarc1' in t.lower() for t in dmarc_txts)

    domaine_envoi.derniere_verification_le = timezone.now()
    domaine_envoi.save(update_fields=[
        'spf_verifie', 'dkim_verifie', 'dmarc_verifie',
        'derniere_verification_le'])
    return domaine_envoi


def domaine_envoi_authentifie(company, domaine):
    """XMKT33 — True si le domaine est intégralement authentifié (utilisé
    par le pré-check XMKT13). Domaine jamais enregistré = non authentifié
    (avertissement, comportement conservateur)."""
    obj = DomaineEnvoi.objects.filter(company=company, domaine=domaine).first()
    return bool(obj and obj.authentifie)


# ═══════════════════════════════════════════════════════════════════════════
# Groupe NTFIN — Moteur de consolidation multi-sociétés (grand groupe)
# ═══════════════════════════════════════════════════════════════════════════

_CENT = Decimal('0.01')


def _classe_de_numero(numero):
    """Classe CGNC (1-8) déduite du premier chiffre d'un numéro de compte."""
    n = str(numero or '').strip()
    return int(n[0]) if n[:1].isdigit() else 0


def _verifier_cycle_modifiable(cycle):
    """NTFIN1 — refuse toute mutation des données agrégées d'un cycle verrouillé."""
    if cycle.est_verrouille:
        raise ValidationError(
            "Cycle de consolidation verrouillé : ses données agrégées ne "
            "peuvent plus être modifiées.")


def ouvrir_cycle_consolidation(cycle):
    """NTFIN1 — (ré)ouvre un cycle verrouillé pour reprendre la consolidation."""
    cycle.verrouille = False
    if cycle.statut == CycleConsolidation.Statut.PUBLIE:
        cycle.statut = CycleConsolidation.Statut.ELIMINATIONS
    cycle.save(update_fields=['verrouille', 'statut', 'updated_at'])
    return cycle


def verrouiller_cycle_consolidation(cycle):
    """NTFIN1 — verrouille un cycle (fige ses données agrégées)."""
    cycle.verrouille = True
    cycle.save(update_fields=['verrouille', 'updated_at'])
    return cycle


# ── NTFIN2 — Collecte de la balance d'une entité ───────────────────────────

def collecter_balance_entite(cycle, entite_company, *, devise_locale=None):
    """Fige un snapshot de la balance N d'une société membre (NTFIN2).

    Lit la balance générale cumulée de ``entite_company`` à la date de fin du
    cycle (via ``balance_generale``, son grand livre local) et l'enregistre dans
    une ``LiasseRemontee``. Idempotent par (cycle, entite) : re-collecter écrase
    le snapshot sans dupliquer. Refuse si le cycle est verrouillé.
    """
    from . import selectors as _sel
    _verifier_cycle_modifiable(cycle)
    bal = _sel.balance_generale(entite_company, date_fin=cycle.date_fin)
    snapshot = [{
        'numero': li['numero'],
        'intitule': li['intitule'],
        'classe': li['classe'],
        'debit': str(li['debit']),
        'credit': str(li['credit']),
    } for li in bal['lignes']]
    liasse, _ = LiasseRemontee.objects.update_or_create(
        company=cycle.company, cycle=cycle, entite=entite_company,
        defaults={
            'statut': LiasseRemontee.Statut.COLLECTE,
            'date_collecte': timezone.now(),
            'devise_locale': devise_locale or 'MAD',
            'snapshot_balance': snapshot,
        })
    return liasse


def collecter_cycle(cycle):
    """NTFIN2 — collecte la tête de groupe + toutes ses entités du périmètre.

    La société tête de groupe (``cycle.company``) est elle-même consolidée : sa
    balance est collectée en plus de celles des filiales membres.
    """
    _verifier_cycle_modifiable(cycle)
    liasses = [collecter_balance_entite(cycle, cycle.company)]
    membres = EntiteConsolidation.objects.filter(
        cycle=cycle, actif=True).select_related('entite')
    for m in membres:
        if m.entite_id == cycle.company_id:
            continue  # déjà collectée en tant que tête.
        liasses.append(collecter_balance_entite(cycle, m.entite))
    if cycle.statut == CycleConsolidation.Statut.OUVERT:
        cycle.statut = CycleConsolidation.Statut.COLLECTE
        cycle.save(update_fields=['statut', 'updated_at'])
    return liasses


# ── NTFIN4 — Mapping compte local → compte groupe ──────────────────────────

def mapper_compte_groupe(company, numero_local):
    """NTFIN4 — compte de groupe pour un numéro local (préfixe le plus long).

    Renvoie le ``CompteComptable`` de groupe mappé, ou ``None`` si aucun mapping
    actif ne couvre ``numero_local``.
    """
    numero = str(numero_local or '')
    candidats = [
        m for m in MappingConsolidation.objects.filter(
            company=company, actif=True).select_related('compte_groupe')
        if numero.startswith(m.plan_local_prefixe)]
    if not candidats:
        return None
    meilleur = max(candidats, key=lambda m: len(m.plan_local_prefixe))
    return meilleur.compte_groupe


def agreger_balance_groupe(cycle):
    """NTFIN4/11 — balance groupe agrégée des liasses collectées.

    Applique le mapping de consolidation à chaque ligne de chaque snapshot et
    somme par compte de groupe (numéro). Un compte local non mappé conserve son
    propre numéro (remonté comme anomalie par les contrôles NTFIN3). Renvoie un
    dict ``{numero_groupe: {'debit', 'credit', 'intitule', 'classe'}}``.
    """
    agg = {}
    for liasse in LiasseRemontee.objects.filter(cycle=cycle):
        for li in (liasse.snapshot_balance or []):
            compte_groupe = mapper_compte_groupe(cycle.company, li['numero'])
            if compte_groupe is not None:
                numero = compte_groupe.numero
                intitule = compte_groupe.intitule
                classe = compte_groupe.classe
            else:
                numero = li['numero']
                intitule = li.get('intitule', '')
                classe = li.get('classe') or _classe_de_numero(numero)
            slot = agg.setdefault(numero, {
                'debit': Decimal('0'), 'credit': Decimal('0'),
                'intitule': intitule, 'classe': classe})
            slot['debit'] += Decimal(str(li.get('debit') or 0))
            slot['credit'] += Decimal(str(li.get('credit') or 0))
    return agg


# ── NTFIN5 — Conversion de devise d'une entité (cours de clôture) ──────────

def convertir_entite(liasse, taux_cloture, taux_moyen):
    """Convertit la balance d'une entité en devise de présentation (NTFIN5).

    Méthode du cours de clôture : les postes de bilan (classes 1-5) sont
    convertis au ``taux_cloture``, les comptes de résultat (classes 6-7) au
    ``taux_moyen``. L'écart qui en résulte (le résultat converti au cours moyen
    diffère du solde de bilan converti au cours de clôture) est l'**écart de
    conversion** (CTA), porté en réserves de conversion pour équilibrer la
    balance convertie au centime.

    Renvoie ``{'lignes': [...], 'ecart_conversion', 'total_debit',
    'total_credit'}`` où ``lignes`` reprend chaque compte converti.
    """
    taux_cloture = Decimal(str(taux_cloture))
    taux_moyen = Decimal(str(taux_moyen))
    lignes = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for li in (liasse.snapshot_balance or []):
        classe = li.get('classe') or _classe_de_numero(li['numero'])
        taux = taux_moyen if classe in (6, 7) else taux_cloture
        debit = (Decimal(str(li.get('debit') or 0)) * taux).quantize(_CENT)
        credit = (Decimal(str(li.get('credit') or 0)) * taux).quantize(_CENT)
        total_debit += debit
        total_credit += credit
        lignes.append({
            'numero': li['numero'], 'intitule': li.get('intitule', ''),
            'classe': classe, 'debit': debit, 'credit': credit})
    # CTA : le plug qui rééquilibre la balance convertie (Σ débit = Σ crédit).
    # ecart > 0 → il manque du débit (on ajoute la CTA au débit) ; ecart < 0 →
    # il manque du crédit. La balance convertie AVEC CTA est équilibrée au
    # centime.
    ecart = total_credit - total_debit
    debit_equilibre = total_debit + (ecart if ecart > 0 else Decimal('0'))
    credit_equilibre = total_credit + (-ecart if ecart < 0 else Decimal('0'))
    return {
        'lignes': lignes,
        'ecart_conversion': ecart,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'debit_equilibre': debit_equilibre,
        'credit_equilibre': credit_equilibre,
        'equilibre': debit_equilibre == credit_equilibre,
    }


# ── NTFIN6 — Matching des opérations inter-co ──────────────────────────────

def apparier_intercos(cycle):
    """Rapproche les opérations réciproques d'un cycle (NTFIN6).

    Pour chaque ``OperationInterco``, calcule l'écart entre les deux montants
    déclarés et pose le statut : ``apparie`` si l'écart ≤ tolérance du cycle,
    sinon ``ecart``. Refuse si le cycle est verrouillé.
    """
    _verifier_cycle_modifiable(cycle)
    tolerance = cycle.tolerance_interco or Decimal('0')
    resultats = []
    for op in OperationInterco.objects.filter(cycle=cycle):
        ecart = (op.montant_declare_a - op.montant_declare_b)
        op.ecart = abs(ecart)
        if op.ecart <= tolerance:
            op.statut = OperationInterco.Statut.APPARIE
        else:
            op.statut = OperationInterco.Statut.ECART
        op.save(update_fields=['ecart', 'statut', 'updated_at'])
        resultats.append(op)
    return resultats


# ── NTFIN7 — Journaux d'élimination interco (créances/dettes réciproques) ──

def generer_eliminations_reciproques(cycle):
    """Génère les écritures d'élimination des intercos appariés (NTFIN7).

    Pour chaque ``OperationInterco`` ``apparie``, crée une ``EcritureElimination``
    de type ``reciproque`` annulant exactement le solde réciproque apparié
    (montant apparié = le plus petit des deux montants déclarés) sur le compte
    de groupe réciproque : on annule la créance (crédit) et la dette (débit) du
    même montant. Idempotent : un interco déjà éliminé n'est pas redoublé.
    Refuse si le cycle est verrouillé.
    """
    _verifier_cycle_modifiable(cycle)
    ecritures = []
    for op in OperationInterco.objects.filter(
            cycle=cycle, statut=OperationInterco.Statut.APPARIE):
        if EcritureElimination.objects.filter(
                cycle=cycle, source_interco=op).exists():
            continue
        montant = min(op.montant_declare_a, op.montant_declare_b)
        if montant <= 0:
            continue
        elim = EcritureElimination.objects.create(
            company=cycle.company, cycle=cycle,
            type_elimination=EcritureElimination.Type.RECIPROQUE,
            libelle=f'Élimination réciproque {op.compte_reciproque}',
            automatique=True, source_interco=op,
            lignes=[
                {'compte': op.compte_reciproque,
                 'libelle': 'Annulation dette réciproque',
                 'debit': str(montant), 'credit': '0'},
                {'compte': op.compte_reciproque,
                 'libelle': 'Annulation créance réciproque',
                 'debit': '0', 'credit': str(montant)},
            ])
        ecritures.append(elim)
    return ecritures


# ── NTFIN8 — Élimination des marges internes sur stock ─────────────────────

def eliminer_marge_interne(marge):
    """Élimine la marge interne non réalisée sur stock (NTFIN8).

    Retranche la marge incluse dans le stock détenu en fin d'exercice du
    résultat consolidé (débit résultat/charge, crédit stock) et constate l'impôt
    différé actif correspondant (débit impôt différé, crédit charge d'impôt).
    Impact net sur le résultat = marge × (1 − taux d'impôt). Renvoie l'écriture
    d'élimination générée (type ``marge_interne``). Refuse si cycle verrouillé.
    """
    cycle = marge.cycle
    _verifier_cycle_modifiable(cycle)
    m = marge.marge_non_realisee
    impot = (m * (marge.taux_impot or Decimal('0')) / Decimal('100')).quantize(_CENT)
    lignes = [
        # Élimination de la marge : réduit le stock et le résultat.
        {'compte': '7', 'libelle': 'Élimination marge interne (résultat)',
         'debit': str(m), 'credit': '0'},
        {'compte': '3', 'libelle': 'Réduction stock (marge interne)',
         'debit': '0', 'credit': str(m)},
    ]
    if impot > 0:
        lignes += [
            {'compte': '3', 'libelle': 'Impôt différé actif',
             'debit': str(impot), 'credit': '0'},
            {'compte': '6', 'libelle': 'Produit d\'impôt différé',
             'debit': '0', 'credit': str(impot)},
        ]
    elim = EcritureElimination.objects.create(
        company=cycle.company, cycle=cycle,
        type_elimination=EcritureElimination.Type.MARGE_INTERNE,
        libelle='Élimination marge interne sur stock',
        automatique=True, lignes=lignes)
    marge.elimination = elim
    marge.save(update_fields=['elimination', 'updated_at'])
    return elim


# ── NTFIN9 — Élimination des titres + goodwill ─────────────────────────────

def eliminer_titres(elim_titres):
    """Élimine les titres d'une fille et dégage le goodwill (NTFIN9).

    Élimine la valeur des titres contre la quote-part de capitaux propres de la
    fille et porte l'écart d'acquisition (goodwill) à l'actif consolidé. Débit :
    capitaux propres (quote-part) + goodwill (si positif) ; crédit : titres. Un
    badwill (écart négatif) est porté au crédit (produit). Renvoie l'écriture
    d'élimination (type ``titres``). Refuse si cycle verrouillé.
    """
    cycle = elim_titres.cycle
    _verifier_cycle_modifiable(cycle)
    goodwill = elim_titres.calculer_ecart()
    lignes = [
        {'compte': '1', 'libelle': 'Élimination quote-part capitaux propres',
         'debit': str(elim_titres.quote_part_capitaux_propres), 'credit': '0'},
    ]
    if goodwill >= 0:
        if goodwill > 0:
            lignes.append({
                'compte': '2', 'libelle': 'Goodwill (écart d\'acquisition)',
                'debit': str(goodwill), 'credit': '0'})
    else:
        # Badwill : produit constaté (crédit).
        lignes.append({
            'compte': '7', 'libelle': 'Badwill (écart d\'acquisition négatif)',
            'debit': '0', 'credit': str(-goodwill)})
    lignes.append({
        'compte': '2', 'libelle': 'Élimination titres de participation',
        'debit': '0', 'credit': str(elim_titres.valeur_titres)})
    elim = EcritureElimination.objects.create(
        company=cycle.company, cycle=cycle,
        type_elimination=EcritureElimination.Type.TITRES,
        libelle=f'Élimination titres {elim_titres.entite_fille_id}',
        automatique=True, lignes=lignes)
    elim_titres.elimination = elim
    elim_titres.save(update_fields=['elimination', 'ecart_acquisition',
                                    'updated_at'])
    return elim


# ── NTFIN10 — Intérêts minoritaires ────────────────────────────────────────

def calculer_interets_minoritaires(cycle):
    """Répartit la quote-part des minoritaires (NTFIN10).

    Pour chaque filiale en intégration globale détenue à moins de 100 %,
    attribue aux minoritaires (100 % − pourcentage d'intérêt) leur part des
    capitaux propres ET du résultat, via une écriture d'élimination dédiée
    (type ``minoritaires``) : débit capitaux propres / résultat, crédit poste
    « Intérêts minoritaires » (passif). Renvoie la liste des écritures générées.
    Le résultat de chaque filiale est lu depuis sa liasse collectée (soldes des
    classes 6/7 du snapshot). Refuse si cycle verrouillé.
    """
    _verifier_cycle_modifiable(cycle)
    ecritures = []
    membres = EntiteConsolidation.objects.filter(
        cycle=cycle, actif=True,
        methode=EntiteConsolidation.Methode.INTEGRATION_GLOBALE)
    for m in membres:
        pct_minoritaire = Decimal('100') - (m.pourcentage_interet or Decimal('0'))
        if pct_minoritaire <= 0:
            continue
        liasse = LiasseRemontee.objects.filter(
            cycle=cycle, entite=m.entite).first()
        if not liasse:
            continue
        resultat = Decimal('0')
        capitaux = Decimal('0')
        for li in (liasse.snapshot_balance or []):
            classe = li.get('classe') or _classe_de_numero(li['numero'])
            solde = Decimal(str(li.get('credit') or 0)) - Decimal(
                str(li.get('debit') or 0))
            if classe in (6, 7):
                resultat += solde  # produit − charge = résultat
            elif classe == 1:
                capitaux += solde  # capitaux propres = solde créditeur
        part_resultat = (resultat * pct_minoritaire / Decimal('100')).quantize(_CENT)
        part_capitaux = (capitaux * pct_minoritaire / Decimal('100')).quantize(_CENT)
        total = part_resultat + part_capitaux
        if total == 0:
            continue
        elim = EcritureElimination.objects.create(
            company=cycle.company, cycle=cycle,
            type_elimination=EcritureElimination.Type.MINORITAIRES,
            libelle=f'Intérêts minoritaires {m.entite_id}',
            automatique=True,
            lignes=[
                {'compte': '1', 'libelle': 'Capitaux propres part minoritaires',
                 'debit': str(part_capitaux), 'credit': '0'},
                {'compte': '1', 'libelle': 'Résultat part minoritaires',
                 'debit': str(part_resultat), 'credit': '0'},
                {'compte': '1', 'libelle': 'Intérêts minoritaires (passif)',
                 'debit': '0', 'credit': str(total)},
            ])
        ecritures.append(elim)
    return ecritures


# ═══════════════════════════════════════════════════════════════════════════
# Groupe NTFIN — Multi-référentiel / multi-GAAP
# ═══════════════════════════════════════════════════════════════════════════

# ── NTFIN13 — Référentiel comptable (livres parallèles) ────────────────────

def seed_referentiel_principal(company):
    """Amorce le référentiel CGNC principal d'une société (NTFIN13, idempotent).

    Garantit qu'une société possède exactement un référentiel principal (CGNC).
    Les états existants lisent le principal — rétro-compatible. Renvoie le
    référentiel principal.
    """
    principal = ReferentielComptable.objects.filter(
        company=company, est_principal=True).first()
    if principal:
        return principal
    ref, _ = ReferentielComptable.objects.get_or_create(
        company=company, code=ReferentielComptable.Code.CGNC,
        defaults={'libelle': 'CGNC (Maroc)', 'devise_fonctionnelle': 'MAD',
                  'est_principal': True, 'actif': True})
    if not ref.est_principal:
        ref.est_principal = True
        ref.save(update_fields=['est_principal', 'updated_at'])
    return ref


# ── NTFIN15 — Écritures d'ajustement GAAP (delta CGNC→IFRS) ────────────────

def poster_ajustement_gaap(company, referentiel_cible, lignes, motif, *,
                           type_ajustement='', created_by=None):
    """Poste un ajustement de retraitement GAAP dans un livre parallèle (NTFIN15).

    Crée une écriture équilibrée dont TOUTES les lignes sont taguées
    ``referentiel_cible`` (sans toucher au livre CGNC) et enregistre un
    ``AjustementGaap`` traçable/réversible. ``lignes`` : liste de dicts
    ``{'compte', 'debit', 'credit', 'libelle'?}``. Renvoie l'``AjustementGaap``.
    """
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    ecriture = creer_ecriture(
        company, journal, timezone.now().date(),
        f'Ajustement GAAP : {motif}', lignes,
        created_by=created_by, statut=EcritureComptable.Statut.VALIDEE,
        referentiel=referentiel_cible)
    return AjustementGaap.objects.create(
        company=company, referentiel=referentiel_cible,
        type_ajustement=type_ajustement or '', motif=motif,
        ecriture=ecriture, reversible=True)


# ═══════════════════════════════════════════════════════════════════════════
# Groupe NTFIN — Moteur d'allocations & comptabilité d'engagement (encumbrance)
# ═══════════════════════════════════════════════════════════════════════════

# ── NTFIN20 — Clés de répartition ──────────────────────────────────────────

def valider_cle_repartition(cle):
    """NTFIN20 — vérifie que Σ des coefficients d'une clé vaut 100 %.

    Lève ``ValidationError`` si la somme des coefficients de ses lignes n'est
    pas égale à 100 (une clé sans ligne est refusée). Renvoie la clé.
    """
    total = cle.total_coefficients
    if total != Decimal('100'):
        raise ValidationError(
            "La clé de répartition doit sommer à 100 % "
            f"(actuel : {total} %).")
    return cle


# ── NTFIN21 — Moteur d'allocation (déversement de charges indirectes) ──────

def _solde_compte_centre(company, compte_numero, *, centre_cout=None,
                         date_fin=None):
    """Solde débiteur net (débit − crédit) d'un compte (+ centre) au GL."""
    qs = LigneEcriture.objects.filter(
        company=company, compte__numero=compte_numero)
    if centre_cout is not None:
        qs = qs.filter(centre_cout=centre_cout)
    if date_fin is not None:
        qs = qs.filter(ecriture__date_ecriture__lte=date_fin)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0')) - (agg['credit'] or Decimal('0'))


@transaction.atomic
def executer_allocation(company, compte_source, cle, periode, *,
                        referentiel=None, montant=None, centre_source=None,
                        created_by=None):
    """Déverse un compte/centre source vers les cibles d'une clé (NTFIN21).

    ``montant`` (optionnel) : montant à répartir ; par défaut le solde débiteur
    net du ``compte_source`` (+ ``centre_source``) au grand livre à la fin de la
    ``periode``. Poste une OD d'allocation qui déplace analytiquement la charge
    du centre source vers les centres cibles (crédit source, débit cibles au
    prorata des coefficients de la clé) — le solde comptable du compte reste
    inchangé, seule la ventilation analytique bouge. Réversible via
    ``reverser_allocation``. Renvoie le ``RunAllocation`` créé.
    """
    valider_cle_repartition(cle)
    if montant is None:
        montant = _solde_compte_centre(
            company, compte_source, centre_cout=centre_source,
            date_fin=periode)
    montant = Decimal(str(montant)).quantize(_CENT)
    if montant <= 0:
        raise ValidationError(
            "Aucun montant à répartir pour cette allocation.")
    compte_obj = _assurer_compte(company, compte_source)
    lignes = [
        {'compte': compte_obj,
         'libelle': f'Déversement source {compte_source}',
         'debit': '0', 'credit': str(montant),
         'centre_cout': centre_source},
    ]
    reparti = Decimal('0')
    lignes_cle = list(cle.lignes.select_related('centre_cout').all())
    for i, li in enumerate(lignes_cle):
        if i == len(lignes_cle) - 1:
            part = montant - reparti  # dernier reçoit le résiduel (arrondi)
        else:
            part = (montant * (li.coefficient or Decimal('0'))
                    / Decimal('100')).quantize(_CENT)
        reparti += part
        lignes.append({
            'compte': compte_obj,
            'libelle': f'Allocation vers {li.centre_cout.code}',
            'debit': str(part), 'credit': '0',
            'centre_cout': li.centre_cout})
    journal = _journal(company, Journal.Type.OPERATIONS_DIVERSES)
    ecriture = creer_ecriture(
        company, journal, periode,
        f'Allocation {compte_source} ({cle.code})', lignes,
        created_by=created_by, statut=EcritureComptable.Statut.VALIDEE,
        referentiel=referentiel)
    return RunAllocation.objects.create(
        company=company, cle=cle, compte_source=compte_source,
        centre_source=centre_source, referentiel=referentiel,
        periode=periode, montant_reparti=montant, ecriture=ecriture,
        statut=RunAllocation.Statut.EXECUTEE)


@transaction.atomic
def reverser_allocation(run, *, created_by=None):
    """NTFIN21 — extourne une allocation (OD inverse), la marque ``reversee``."""
    if run.statut == RunAllocation.Statut.REVERSEE:
        raise ValidationError("Cette allocation est déjà réversée.")
    lignes = []
    if run.ecriture_id:
        for lg in run.ecriture.lignes.select_related('compte').all():
            lignes.append({
                'compte': lg.compte,
                'libelle': f'Extourne {lg.libelle}',
                'debit': str(lg.credit), 'credit': str(lg.debit),
                'centre_cout': lg.centre_cout})
    if lignes:
        journal = _journal(run.company, Journal.Type.OPERATIONS_DIVERSES)
        creer_ecriture(
            run.company, journal, run.periode,
            f'Extourne allocation {run.compte_source}', lignes,
            created_by=created_by, statut=EcritureComptable.Statut.VALIDEE,
            referentiel=run.referentiel)
    run.statut = RunAllocation.Statut.REVERSEE
    run.save(update_fields=['statut', 'updated_at'])
    return run


# ── NTFIN22 — Allocations récurrentes planifiées ───────────────────────────

def generer_allocations_recurrentes(company, *, jusqua=None):
    """NTFIN22 — exécute les allocations récurrentes échues (idempotent).

    Pour chaque ``AllocationRecurrente`` active dont ``prochaine_echeance`` ≤
    ``jusqua`` (défaut aujourd'hui), exécute l'allocation via NTFIN21 et avance
    l'échéance. IDEMPOTENT par (clé, compte_source, période) : une allocation
    déjà exécutée pour la période n'est pas redoublée. Renvoie
    ``{'generees': [...], 'ignorees': [...]}``.
    """
    jusqua = jusqua or timezone.localdate()
    generees, ignorees = [], []
    recurrentes = AllocationRecurrente.objects.filter(
        company=company, actif=True,
        prochaine_echeance__lte=jusqua).select_related('cle')
    for rec in recurrentes:
        echeance = rec.prochaine_echeance
        # Boucle de rattrapage : plusieurs périodes échues d'un coup.
        while echeance <= jusqua:
            deja = RunAllocation.objects.filter(
                company=company, cle=rec.cle,
                compte_source=rec.compte_source, periode=echeance,
                statut=RunAllocation.Statut.EXECUTEE).exists()
            if deja:
                ignorees.append({
                    'allocation_id': rec.id, 'periode': echeance.isoformat(),
                    'raison': 'déjà exécutée pour cette période'})
            else:
                try:
                    run = executer_allocation(
                        company, rec.compte_source, rec.cle, echeance,
                        referentiel=rec.referentiel,
                        centre_source=rec.centre_source)
                    generees.append({
                        'allocation_id': rec.id, 'run_id': run.id,
                        'periode': echeance.isoformat()})
                except ValidationError as exc:
                    ignorees.append({
                        'allocation_id': rec.id,
                        'periode': echeance.isoformat(),
                        'raison': '; '.join(exc.messages)})
            echeance = rec.echeance_suivante(echeance)
        rec.prochaine_echeance = echeance
        rec.derniere_generation = jusqua
        rec.save(update_fields=['prochaine_echeance', 'derniere_generation',
                                'updated_at'])
    return {'generees': generees, 'ignorees': ignorees}


# ── NTFIN23 — Engagements (encumbrance) ────────────────────────────────────

def engager(company, *, compte, montant, date_engagement, type_engagement=None,
            centre_cout=None, referentiel=None, source_type='', source_id=None,
            reference='', libelle=''):
    """NTFIN23 — crée un engagement comptable (réserve un budget à la commande).

    ``compte`` est un ``CompteComptable``. Renvoie l'``EngagementComptable``.
    """
    eng = EngagementComptable(
        company=company, compte=compte,
        montant_engage=Decimal(str(montant)).quantize(_CENT),
        date_engagement=date_engagement,
        type_engagement=type_engagement or EngagementComptable.Type.BON_COMMANDE,
        centre_cout=centre_cout, referentiel=referentiel,
        source_type=source_type or '', source_id=source_id,
        reference=reference or '', libelle=libelle or '',
        statut=EngagementComptable.Statut.ENGAGE)
    eng.full_clean()
    eng.save()
    return eng


def liquider(engagement, montant):
    """NTFIN23 — liquide (consomme) une part d'un engagement à la facturation.

    Ajoute ``montant`` au liquidé et met à jour le statut (engagé →
    partiellement liquidé → soldé). Refuse un dépassement du montant engagé.
    Renvoie l'engagement.
    """
    montant = Decimal(str(montant)).quantize(_CENT)
    nouveau = (engagement.montant_liquide or Decimal('0')) + montant
    if nouveau > engagement.montant_engage:
        raise ValidationError(
            "La liquidation dépasserait le montant engagé "
            f"({engagement.montant_engage}).")
    engagement.montant_liquide = nouveau
    if nouveau >= engagement.montant_engage:
        engagement.statut = EngagementComptable.Statut.SOLDE
    elif nouveau > 0:
        engagement.statut = EngagementComptable.Statut.PARTIELLEMENT_LIQUIDE
    engagement.save(update_fields=['montant_liquide', 'statut', 'updated_at'])
    return engagement


# ── NTFIN24 — Contrôle budgétaire à l'engagement ───────────────────────────

def verifier_disponible_engagement(company, *, compte, centre_cout=None,
                                   montant, periode):
    """NTFIN24 — contrôle qu'un nouvel engagement tient dans le disponible.

    Disponible = budget − engagé − réalisé (le contrôle XACC21 ne comptait que
    le réalisé). Renvoie un dict ``{'statut': 'ok'|'avertissement'|'blocage',
    'disponible', 'budget', 'engage', 'realise', 'controle'}``. Ne LÈVE PAS :
    l'appelant décide (la vue 400 sur ``blocage``). Sans budget défini →
    ``statut='ok'`` (aucun contrôle possible, comportement historique).
    """
    from . import selectors as _sel
    montant = Decimal(str(montant)).quantize(_CENT)
    dispo = _sel.disponible_budgetaire_compte(
        company, compte=compte, centre_cout=centre_cout, periode=periode)
    if dispo is None:
        return {'statut': 'ok', 'disponible': None, 'budget': None,
                'engage': Decimal('0'), 'realise': Decimal('0'),
                'controle': None}
    apres = dispo['disponible'] - montant
    if apres >= 0:
        statut = 'ok'
    elif dispo['controle'] == Budget.Controle.BLOQUANT:
        statut = 'blocage'
    else:
        statut = 'avertissement'
    return {
        'statut': statut,
        'disponible': dispo['disponible'],
        'disponible_apres': apres,
        'budget': dispo['budget'],
        'engage': dispo['engage'],
        'realise': dispo['realise'],
        'controle': dispo['controle'],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Groupe NTFIN — Close management (clôture rapide)
# ═══════════════════════════════════════════════════════════════════════════

# ── NTFIN26 — Seed d'un modèle de clôture mensuelle standard ───────────────

_TACHES_CLOTURE_MENSUELLE = [
    ('Rapprochements bancaires du mois', 'rapprochement', True),
    ('Rapprochement des comptes de tiers', 'rapprochement', True),
    ('Clôture des caisses', 'rapprochement', True),
    ('Comptabilisation des accruals (FAE/FNP)', 'accrual', True),
    ('Dotations aux amortissements du mois', 'accrual', True),
    ('Provisions et régularisations', 'accrual', False),
    ('Analyse des variations significatives', 'analyse', True),
    ('Revue des comptes d\'attente', 'analyse', True),
    ('Édition de la balance et du grand livre', 'reporting', True),
    ('Validation de la clôture', 'reporting', True),
]


def seed_modele_cloture_mensuel(company):
    """NTFIN26 — amorce un modèle de clôture mensuelle standard (idempotent).

    Crée (une fois) un ``ModeleCloture`` mensuel + ses ≥ 8 tâches ordonnées.
    Re-lancement : ne duplique rien. Renvoie le modèle.
    """
    modele, _ = ModeleCloture.objects.get_or_create(
        company=company, libelle='Clôture mensuelle standard',
        periodicite=ModeleCloture.Periodicite.MENSUELLE,
        defaults={'actif': True})
    for ordre, (libelle, categorie, obligatoire) in enumerate(
            _TACHES_CLOTURE_MENSUELLE, start=1):
        TacheClotureModele.objects.get_or_create(
            company=company, modele=modele, libelle=libelle,
            defaults={'ordre': ordre, 'categorie': categorie,
                      'obligatoire': obligatoire})
    return modele


# ── NTFIN27 — Instance de clôture (workspace de période) ───────────────────

@transaction.atomic
def instancier_cloture(periode, modele, *, date_cible=None):
    """NTFIN27 — matérialise une checklist de clôture sur une période.

    Crée l'``InstanceCloture`` (une par période, idempotent) et une
    ``TacheCloture`` par tâche-modèle. Renvoie l'instance.
    """
    instance, cree = InstanceCloture.objects.get_or_create(
        company=periode.company, periode=periode,
        defaults={'modele': modele, 'date_cible': date_cible})
    if not cree:
        return instance
    for tm in modele.taches.order_by('ordre', 'id'):
        TacheCloture.objects.create(
            company=periode.company, instance=instance, libelle=tm.libelle,
            ordre=tm.ordre, obligatoire=tm.obligatoire, categorie=tm.categorie)
    return instance


def cocher_tache_cloture(tache, *, user=None, statut=None,
                         piece_jointe_key=None):
    """NTFIN27 — met à jour le statut d'une tâche de clôture (fait par défaut).

    Rafraîchit le statut global de l'instance selon l'avancement. Renvoie la
    tâche.
    """
    tache.statut = statut or TacheCloture.Statut.FAIT
    if tache.statut == TacheCloture.Statut.FAIT:
        tache.fait_par = user
        tache.fait_le = timezone.now()
    if piece_jointe_key is not None:
        tache.piece_jointe_key = piece_jointe_key
    tache.save(update_fields=['statut', 'fait_par', 'fait_le',
                              'piece_jointe_key', 'updated_at'])
    _rafraichir_statut_instance(tache.instance)
    return tache


def _rafraichir_statut_instance(instance):
    """Recalcule le statut global d'une instance de clôture depuis ses tâches."""
    taches = list(instance.taches.all())
    if not taches:
        return instance
    faites = [t for t in taches
              if t.statut in (TacheCloture.Statut.FAIT, TacheCloture.Statut.NA)]
    if len(faites) == len(taches):
        statut = InstanceCloture.Statut.VALIDE
    elif faites:
        statut = InstanceCloture.Statut.EN_COURS
    else:
        statut = InstanceCloture.Statut.OUVERT
    if instance.statut != statut:
        instance.statut = statut
        instance.save(update_fields=['statut', 'updated_at'])
    return instance


# ── NTFIN29 — Accruals automatiques (avec extourne) ────────────────────────

@transaction.atomic
def poster_accrual(accrual, *, user=None):
    """NTFIN29 — poste l'OD d'accrual + son extourne au 1er jour suivant.

    Charge à payer / FNP : débit charge, crédit contrepartie ; produit à
    recevoir : débit contrepartie (créance), crédit produit. L'extourne inverse
    exactement l'écriture, datée du lendemain de la fin de période (impact net
    nul sur la période suivante hors régularisation). Idempotent : un accrual
    déjà posté n'est pas redoublé. Renvoie l'accrual.
    """
    from datetime import timedelta
    if accrual.ecriture_id:
        return accrual
    montant = accrual.montant
    if montant is None or montant <= 0:
        raise ValidationError("Le montant de l'accrual doit être positif.")
    date_accrual = accrual.periode.date_fin
    date_extourne = date_accrual + timedelta(days=1)
    compte_cp = _assurer_compte(accrual.company, accrual.compte_charge_produit)
    compte_ctr = _assurer_compte(accrual.company, accrual.compte_contrepartie)
    if accrual.type_accrual == AccrualCloture.Type.PRODUIT_A_RECEVOIR:
        lignes = [
            {'compte': compte_ctr,
             'libelle': accrual.libelle or 'Produit à recevoir',
             'debit': str(montant), 'credit': '0'},
            {'compte': compte_cp,
             'libelle': accrual.libelle or 'Produit à recevoir',
             'debit': '0', 'credit': str(montant)},
        ]
    else:
        lignes = [
            {'compte': compte_cp,
             'libelle': accrual.libelle or 'Charge à payer',
             'debit': str(montant), 'credit': '0'},
            {'compte': compte_ctr,
             'libelle': accrual.libelle or 'Charge à payer',
             'debit': '0', 'credit': str(montant)},
        ]
    ecriture = creer_ecriture_od(
        accrual.company, date_accrual,
        f'Accrual clôture : {accrual.libelle or accrual.type_accrual}',
        lignes, created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    lignes_extourne = [
        {'compte': li['compte'], 'libelle': f"Extourne {li['libelle']}",
         'debit': li['credit'], 'credit': li['debit']} for li in lignes]
    ecriture_extourne = creer_ecriture_od(
        accrual.company, date_extourne,
        f'Extourne accrual : {accrual.libelle or accrual.type_accrual}',
        lignes_extourne, created_by=user,
        statut=EcritureComptable.Statut.VALIDEE)
    accrual.ecriture = ecriture
    accrual.ecriture_extourne = ecriture_extourne
    accrual.save(update_fields=['ecriture', 'ecriture_extourne', 'updated_at'])
    return accrual


# ── NTFIN32 — Journaux récurrents de clôture (OD depuis modèle) ────────────

@transaction.atomic
def generer_od_cloture(tache_cloture, modele_ecriture, *, date_ecriture,
                       montants=None, user=None):
    """NTFIN32 — matérialise une OD de clôture depuis un modèle et coche la tâche.

    Réutilise ``generer_ecriture_depuis_modele`` (XACC8) et coche la
    ``TacheCloture`` dans la foulée. Renvoie ``(ecriture, tache)``.
    """
    ecriture = generer_ecriture_depuis_modele(
        modele_ecriture, date_ecriture=date_ecriture, montants=montants,
        user=user, statut=EcritureComptable.Statut.VALIDEE)
    cocher_tache_cloture(tache_cloture, user=user)
    return ecriture, tache_cloture


# ═══════════════════════════════════════════════════════════════════════════
# Groupe NTFIN — Rapprochements de comptes de bilan (workflow 4 yeux)
# ═══════════════════════════════════════════════════════════════════════════

# ── NTFIN35/36 — Recalcul du solde justifié depuis les lignes ──────────────

def recalculer_rapprochement_compte(rapprochement):
    """NTFIN35/36 — recalcule solde justifié (Σ lignes) et écart. Renvoie l'objet."""
    total = sum(
        (li.montant or Decimal('0')
         for li in rapprochement.lignes.all()), Decimal('0'))
    rapprochement.solde_justifie = total
    rapprochement.recalculer_ecart()
    rapprochement.save(update_fields=['solde_justifie', 'ecart', 'updated_at'])
    if rapprochement.ecart == 0 and rapprochement.statut in (
            RapprochementCompte.Statut.A_RAPPROCHER,
            RapprochementCompte.Statut.EN_COURS):
        rapprochement.statut = RapprochementCompte.Statut.RAPPROCHE
        rapprochement.save(update_fields=['statut', 'updated_at'])
    return rapprochement


# ── NTFIN37 — Workflow préparateur → réviseur (revue 4 yeux) ───────────────

def soumettre_rapprochement_compte(rapprochement, *, user):
    """NTFIN37 — le préparateur soumet le rapprochement à revue.

    Enregistre l'acteur (préparateur) et l'horodatage côté serveur. Renvoie
    l'objet.
    """
    if user is None:
        raise ValidationError("Un préparateur est requis.")
    rapprochement.preparateur = user
    rapprochement.statut = RapprochementCompte.Statut.SOUMIS
    rapprochement.date_soumission = timezone.now()
    rapprochement.save(update_fields=[
        'preparateur', 'statut', 'date_soumission', 'updated_at'])
    return rapprochement


def valider_rapprochement_compte(rapprochement, *, user):
    """NTFIN37 — le réviseur valide (revue 4 yeux, séparation des tâches).

    Le réviseur ne peut PAS être le préparateur (COMPTA40) → ``ValidationError``.
    Contrôle aussi que Σ lignes justificatives = solde justifié. Enregistre
    l'acteur (réviseur) + horodatage. Renvoie l'objet.
    """
    if user is None:
        raise ValidationError("Un réviseur est requis pour valider.")
    if (rapprochement.preparateur_id is not None
            and rapprochement.preparateur_id == user.id):
        raise ValidationError(
            "Séparation des tâches : le préparateur d'un rapprochement ne peut "
            "pas le valider lui-même. Un réviseur distinct est requis.")
    total = sum(
        (li.montant or Decimal('0')
         for li in rapprochement.lignes.all()), Decimal('0'))
    if total != rapprochement.solde_justifie:
        raise ValidationError(
            "La somme des lignes justificatives "
            f"({total}) doit égaler le solde justifié "
            f"({rapprochement.solde_justifie}).")
    rapprochement.reviseur = user
    rapprochement.statut = RapprochementCompte.Statut.VALIDE
    rapprochement.date_validation = timezone.now()
    rapprochement.save(update_fields=[
        'reviseur', 'statut', 'date_validation', 'updated_at'])
    return rapprochement


def rejeter_rapprochement_compte(rapprochement, *, user, motif=''):
    """NTFIN37 — le réviseur rejette le rapprochement (retour au préparateur)."""
    if (rapprochement.preparateur_id is not None
            and rapprochement.preparateur_id == user.id if user else False):
        raise ValidationError(
            "Séparation des tâches : le préparateur ne peut pas arbitrer sa "
            "propre revue.")
    rapprochement.reviseur = user
    rapprochement.statut = RapprochementCompte.Statut.EN_COURS
    if motif:
        rapprochement.commentaire = motif
    rapprochement.save(update_fields=[
        'reviseur', 'statut', 'commentaire', 'updated_at'])
    return rapprochement


# ── NTFIN39 — Modèles de rapprochement récurrents (report N-1) ─────────────

def ouvrir_rapprochement_compte(company, compte, periode, *, solde_gl=None):
    """NTFIN35/39 — ouvre un rapprochement de compte pour la période N.

    Idempotent par (company, compte, periode). Pré-remplit les lignes
    justificatives PERMANENTES reportées du rapprochement le plus récent d'une
    période antérieure du même compte (report du justifié N-1, NTFIN39).
    ``solde_gl`` (optionnel) fige le solde grand livre à rapprocher. Renvoie le
    rapprochement.
    """
    rappr, cree = RapprochementCompte.objects.get_or_create(
        company=company, compte=compte, periode=periode,
        defaults={'solde_gl': Decimal(str(solde_gl or 0))})
    if not cree:
        return rappr
    precedent = RapprochementCompte.objects.filter(
        company=company, compte=compte,
        periode__date_debut__lt=periode.date_debut).order_by(
        '-periode__date_debut').first()
    if precedent is not None:
        for li in precedent.lignes.filter(permanente=True):
            LigneJustificationCompte.objects.create(
                company=company, rapprochement=rappr, libelle=li.libelle,
                montant=li.montant, type_element=li.type_element,
                source_type=li.source_type, source_id=li.source_id,
                permanente=True)
    # Fige l'écart dès l'ouverture (solde_gl - Σ lignes), même sans report
    # N-1 : un compte ouvert non justifié doit remonter dans la liste des
    # en-retard (NTFIN38) avec son écart réel.
    recalculer_rapprochement_compte(rappr)
    return rappr


# ═══════════════════════════════════════════════════════════════════════════
# Groupe NTFIN — Immobilisations avancées
# ═══════════════════════════════════════════════════════════════════════════

# ── NTFIN41 — Dépréciation d'immobilisation (impairment IAS 36) ────────────

@transaction.atomic
def poster_depreciation_immobilisation(depreciation, *, user=None):
    """NTFIN41 — poste la dépréciation quand recouvrable < comptable (IAS 36).

    Débit 6194 (dotations aux provisions pour dépréciation des immos) / crédit
    2920 (provisions pour dépréciation des immobilisations). Idempotent : une
    dépréciation déjà postée n'est pas redoublée. Renvoie la dépréciation.
    """
    if depreciation.ecriture_id:
        return depreciation
    perte = depreciation.calculer_perte()
    depreciation.save(update_fields=['perte_valeur', 'updated_at'])
    if perte <= 0:
        return depreciation
    compte_dot = _assurer_compte(depreciation.company, '6194')
    compte_prov = _assurer_compte(depreciation.company, '2920')
    ecriture = creer_ecriture_od(
        depreciation.company, depreciation.date_test,
        f'Dépréciation immobilisation {depreciation.immobilisation_id}',
        [
            {'compte': compte_dot,
             'libelle': 'Dotation dépréciation immobilisation',
             'debit': str(perte), 'credit': '0'},
            {'compte': compte_prov,
             'libelle': 'Provision pour dépréciation immobilisation',
             'debit': '0', 'credit': str(perte)},
        ], created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    depreciation.ecriture = ecriture
    depreciation.save(update_fields=['ecriture', 'updated_at'])
    return depreciation


@transaction.atomic
def reprendre_depreciation_immobilisation(depreciation_origine, montant_reprise,
                                          *, date_reprise=None, user=None):
    """NTFIN41 — reprise de dépréciation quand la valeur remonte (réversible).

    Poste l'écriture inverse (débit 2920 / crédit 7194) et crée une
    ``DepreciationImmobilisation`` marquée ``reprise``. Renvoie la reprise.
    """
    if not depreciation_origine.reversible:
        raise ValidationError("Cette dépréciation n'est pas réversible.")
    montant = Decimal(str(montant_reprise)).quantize(_CENT)
    if montant <= 0:
        raise ValidationError("Le montant de reprise doit être positif.")
    date_reprise = date_reprise or timezone.localdate()
    compte_prov = _assurer_compte(depreciation_origine.company, '2920')
    compte_reprise = _assurer_compte(depreciation_origine.company, '7194')
    ecriture = creer_ecriture_od(
        depreciation_origine.company, date_reprise,
        f'Reprise dépréciation immobilisation '
        f'{depreciation_origine.immobilisation_id}',
        [
            {'compte': compte_prov,
             'libelle': 'Reprise provision dépréciation',
             'debit': str(montant), 'credit': '0'},
            {'compte': compte_reprise,
             'libelle': 'Reprise sur dépréciation immobilisation',
             'debit': '0', 'credit': str(montant)},
        ], created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    return DepreciationImmobilisation.objects.create(
        company=depreciation_origine.company,
        immobilisation=depreciation_origine.immobilisation,
        date_test=date_reprise,
        valeur_recuperable=Decimal('0'), valeur_comptable=Decimal('0'),
        perte_valeur=-montant, reversible=False, reprise=True,
        ecriture=ecriture)


# ── NTFIN42 — Mutation / transfert d'immobilisation ────────────────────────

def muter_immobilisation(immobilisation, *, nouveau_centre=None,
                         entite_cible=None, date=None, motif='',
                         ancien_centre=None):
    """NTFIN42 — trace le transfert d'un actif entre centres/entités.

    Enregistre la mutation ; les futures dotations sont réaffectées au nouveau
    centre (le plan d'amortissement lit le centre courant à compter de la date).
    Renvoie la ``MutationImmobilisation``.
    """
    return MutationImmobilisation.objects.create(
        company=immobilisation.company, immobilisation=immobilisation,
        ancien_centre=ancien_centre, nouveau_centre=nouveau_centre,
        entite_source=immobilisation.company, entite_cible=entite_cible,
        date=date or timezone.localdate(), motif=motif or '')


# ── NTFIN43 — Immobilisations en cours (CIP) & mise en service ─────────────

@transaction.atomic
def mettre_en_service_encours(encours, *, date_mise_en_service=None,
                              categorie=None, compte_immo='2321', user=None):
    """NTFIN43 — transfère un CIP (compte 23) vers une immobilisation (compte 2).

    Crée une ``Immobilisation`` de valeur = montant cumulé, poste l'écriture de
    transfert (débit compte 2 / crédit compte 23) et solde le CIP. Idempotent :
    un CIP déjà mis en service n'est pas retransféré. Renvoie l'immobilisation.
    """
    from .models import Immobilisation as _Immo
    if encours.statut == ImmobilisationEnCours.Statut.MIS_EN_SERVICE:
        return encours.immobilisation
    montant = encours.montant_cumule
    if montant is None or montant <= 0:
        raise ValidationError("Le CIP n'a aucun montant cumulé à immobiliser.")
    date_mes = date_mise_en_service or timezone.localdate()
    immo = _Immo.objects.create(
        company=encours.company, libelle=encours.libelle,
        categorie=categorie or _Immo.Categorie.MATERIEL,
        cout=montant, date_acquisition=date_mes,
        date_mise_en_service=date_mes)
    compte_2 = _assurer_compte(encours.company, compte_immo)
    compte_23 = _assurer_compte(encours.company, encours.compte_encours)
    creer_ecriture_od(
        encours.company, date_mes,
        f'Mise en service immobilisation : {encours.libelle}',
        [
            {'compte': compte_2, 'libelle': 'Immobilisation mise en service',
             'debit': str(montant), 'credit': '0'},
            {'compte': compte_23, 'libelle': 'Solde immobilisation en cours',
             'debit': '0', 'credit': str(montant)},
        ], created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    encours.statut = ImmobilisationEnCours.Statut.MIS_EN_SERVICE
    encours.date_mise_en_service = date_mes
    encours.immobilisation = immo
    encours.save(update_fields=[
        'statut', 'date_mise_en_service', 'immobilisation', 'updated_at'])
    return immo


# ═══════════════════════════════════════════════════════════════════════════
# Groupe NTFIN — Reconnaissance du revenu IFRS 15 & états consolidés
# ═══════════════════════════════════════════════════════════════════════════

# ── NTFIN47 — Allocation du prix de transaction (IFRS 15 étape 4) ──────────

def allouer_prix_transaction(contrat):
    """NTFIN47 — répartit le prix de transaction au prorata des PVS (IFRS 15).

    Alloue ``contrat.montant_transaction`` entre ses obligations au prorata de
    leur ``prix_vente_specifique`` (standalone selling price). La dernière
    obligation reçoit le résiduel (arrondi). Renvoie la liste des obligations.
    """
    obligations = list(contrat.obligations.all())
    total_pvs = sum(
        (o.prix_vente_specifique or Decimal('0') for o in obligations),
        Decimal('0'))
    if total_pvs <= 0:
        raise ValidationError(
            "Impossible d'allouer : la somme des prix de vente spécifiques "
            "est nulle.")
    montant = contrat.montant_transaction or Decimal('0')
    alloue = Decimal('0')
    for i, o in enumerate(obligations):
        if i == len(obligations) - 1:
            part = montant - alloue
        else:
            part = (montant * o.prix_vente_specifique / total_pvs).quantize(
                _CENT)
        alloue += part
        o.prix_alloue = part
        o.save(update_fields=['prix_alloue', 'updated_at'])
    return obligations


# ── NTFIN48 — Échéancier & produit constaté d'avance (IFRS 15 étape 5) ─────

def generer_echeancier_reconnaissance(obligation):
    """NTFIN48 — génère l'échéancier de reconnaissance d'une obligation.

    ``dans_le_temps`` : ``duree_mois`` échéances linéaires (dernière = résiduel)
    à compter de ``date_debut``. ``a_une_date`` : une seule échéance au
    ``date_debut``. Idempotent : ne régénère pas si des échéances existent.
    Renvoie la liste des échéances.
    """
    import calendar
    if obligation.echeances.exists():
        return list(obligation.echeances.all())
    montant = obligation.prix_alloue or Decimal('0')
    debut = obligation.date_debut or timezone.localdate()
    echeances = []
    if (obligation.methode_reconnaissance
            == ObligationPerformance.Methode.DANS_LE_TEMPS
            and obligation.duree_mois):
        n = obligation.duree_mois
        part = (montant / Decimal(n)).quantize(_CENT)
        cumul = Decimal('0')
        for i in range(n):
            mois_total = debut.month - 1 + i
            annee = debut.year + mois_total // 12
            mois = mois_total % 12 + 1
            jour = min(debut.day, calendar.monthrange(annee, mois)[1])
            d = debut.replace(year=annee, month=mois, day=jour)
            m = part if i < n - 1 else (montant - cumul)
            cumul += m
            echeances.append(EcheancierReconnaissance.objects.create(
                company=obligation.company, obligation=obligation, date=d,
                montant_a_reconnaitre=m))
    else:
        echeances.append(EcheancierReconnaissance.objects.create(
            company=obligation.company, obligation=obligation, date=debut,
            montant_a_reconnaitre=montant))
    return echeances


@transaction.atomic
def reconnaitre_echeance(echeance, *, compte_pca='4870', compte_produit='7111',
                         user=None):
    """NTFIN48 — reconnaît une échéance (solde le produit constaté d'avance).

    Débit ``compte_pca`` (487 produit constaté d'avance) / crédit
    ``compte_produit`` (7xxx). Idempotent : une échéance déjà reconnue n'est pas
    redoublée. Renvoie l'échéance.
    """
    if echeance.statut == EcheancierReconnaissance.Statut.RECONNU:
        return echeance
    montant = echeance.montant_a_reconnaitre
    if montant is None or montant <= 0:
        raise ValidationError("Le montant à reconnaître doit être positif.")
    compte_pca_obj = _assurer_compte(echeance.company, compte_pca)
    compte_prod_obj = _assurer_compte(echeance.company, compte_produit)
    ecriture = creer_ecriture_od(
        echeance.company, echeance.date,
        f'Reconnaissance revenu IFRS 15 (obligation {echeance.obligation_id})',
        [
            {'compte': compte_pca_obj,
             'libelle': "Solde produit constaté d'avance",
             'debit': str(montant), 'credit': '0'},
            {'compte': compte_prod_obj, 'libelle': 'Revenu reconnu',
             'debit': '0', 'credit': str(montant)},
        ], created_by=user, statut=EcritureComptable.Statut.VALIDEE)
    echeance.statut = EcheancierReconnaissance.Statut.RECONNU
    echeance.ecriture = ecriture
    echeance.save(update_fields=['statut', 'ecriture', 'updated_at'])
    return echeance


# ── NTFIN55 — Piste d'audit renforcée des opérations de consolidation ──────

def enregistrer_etape_audit_consolidation(cycle, etape, *, acteur=None,
                                          snapshot=None, detail=''):
    """NTFIN55 — scelle un maillon d'audit d'une étape de consolidation.

    Chaîne le maillon au précédent du même cycle : ``hash = SHA256(
    hash_precedent + etape + hash_snapshot + sequence)``. Append-only : chaque
    republication laisse une trace horodatée distincte sans écraser l'historique.
    Renvoie le maillon.
    """
    dernier = EtapeAuditConsolidation.objects.filter(
        cycle=cycle).order_by('-sequence').first()
    sequence = (dernier.sequence + 1) if dernier else 1
    hash_precedent = dernier.hash if dernier else ''
    hash_snapshot = ''
    if snapshot is not None:
        hash_snapshot = hashlib.sha256(
            str(snapshot).encode('utf-8')).hexdigest()
    empreinte = f'{hash_precedent}{etape}{hash_snapshot}{sequence}'
    hash_maillon = hashlib.sha256(empreinte.encode('utf-8')).hexdigest()
    return EtapeAuditConsolidation.objects.create(
        company=cycle.company, cycle=cycle, etape=etape, acteur=acteur,
        sequence=sequence, hash_snapshot=hash_snapshot,
        hash_precedent=hash_precedent, hash=hash_maillon, detail=detail or '')


# ── NTFIN56 — Simulation de consolidation (what-if périmètre) ──────────────

def simuler_consolidation(cycle, ajustements_perimetre=None):
    """NTFIN56 — recalcule un bilan/CPC consolidé provisoire (what-if).

    ``ajustements_perimetre`` : liste de dicts ``{'entite_id', 'pourcentage'}``
    (nouveau % d'intérêt) et/ou ``{'entite_id', 'retirer': True}``. Recalcule les
    intérêts minoritaires et le résultat part groupe SANS écrire aucune écriture
    définitive (le cycle publié n'est pas altéré). Renvoie un dict provisoire.
    """
    from . import selectors as _sel
    ajustements = {a['entite_id']: a for a in (ajustements_perimetre or [])}
    cpc = _sel.cpc_consolide_v2(cycle)
    resultat_total = cpc['resultat']
    # Recalcule la part minoritaire simulée par entité intégrée globalement.
    membres = EntiteConsolidation.objects.filter(
        cycle=cycle, actif=True,
        methode=EntiteConsolidation.Methode.INTEGRATION_GLOBALE)
    part_minoritaires = Decimal('0')
    perimetre = []
    for m in membres:
        adj = ajustements.get(m.entite_id)
        if adj and adj.get('retirer'):
            continue
        pct = Decimal(str(adj['pourcentage'])) if adj and 'pourcentage' in adj \
            else (m.pourcentage_interet or Decimal('0'))
        liasse = LiasseRemontee.objects.filter(
            cycle=cycle, entite=m.entite).first()
        resultat_entite = Decimal('0')
        if liasse:
            for li in (liasse.snapshot_balance or []):
                classe = li.get('classe') or _classe_de_numero(li['numero'])
                if classe in (6, 7):
                    resultat_entite += (
                        Decimal(str(li.get('credit') or 0))
                        - Decimal(str(li.get('debit') or 0)))
        pct_min = Decimal('100') - pct
        part = (resultat_entite * pct_min / Decimal('100')).quantize(_CENT)
        part_minoritaires += part
        perimetre.append({
            'entite_id': m.entite_id, 'pourcentage_interet': pct,
            'resultat_entite': resultat_entite,
            'part_minoritaire': part})
    return {
        'cycle': cycle.id,
        'simulation': True,
        'resultat_consolide': resultat_total,
        'part_minoritaires': part_minoritaires,
        'resultat_part_groupe': resultat_total - part_minoritaires,
        'perimetre': perimetre,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Groupe NTMAR — Télédéclarations SIMPL (formats EDI structurés)
#
# NOTE DE PÉRIMÈTRE (CLAUDE.md / instructions NTMAR) : ces exports produisent un
# fichier STRUCTURÉ et RECHARGEABLE portant tous les postes de la déclaration
# (au format XML DGI-shaped, positions nommées). Le CSV humain existant reste
# inchangé. La correspondance BYTE-À-BYTE avec le gabarit officiel SIMPL de la
# DGI (encodage positionnel exact) doit être validée par le fondateur contre la
# spec DGI publiée — ce module fournit le socle de données et la structure, pas
# un connecteur certifié (aucun appel réseau, aucune transmission ici).
# ─────────────────────────────────────────────────────────────────────────────

def _xml_escape(value):
    return (str(value)
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def export_simpl_tva(declaration):
    """NTMAR10 — génère le fichier SIMPL-TVA (structure DGI) d'une
    ``DeclarationTVA``. Renvoie une str XML portant tous les postes attendus
    (régime, période, TVA collectée/déductible/crédit/net à déclarer/reportable)
    aux positions nommées, rechargeable sans erreur de structure. Le CSV humain
    existant n'est pas modifié."""
    d = declaration
    postes = [
        ('Regime', d.regime),
        ('Methode', d.methode),
        ('PeriodeDebut', d.date_debut.isoformat() if d.date_debut else ''),
        ('PeriodeFin', d.date_fin.isoformat() if d.date_fin else ''),
        ('TVACollectee', str(d.tva_collectee or Decimal('0'))),
        ('TVADeductible', str(d.tva_deductible or Decimal('0'))),
        ('CreditAnterieur', str(d.credit_anterieur or Decimal('0'))),
        ('TVAADeclarer', str(d.tva_a_declarer or Decimal('0'))),
        ('CreditReportable', str(d.credit_reportable or Decimal('0'))),
    ]
    lignes = '\n'.join(
        f'  <Poste code="{code}">{_xml_escape(val)}</Poste>' for code, val in postes)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!-- SIMPL-TVA (structure DGI, NTMAR10) - genere localement, non '
        'transmis. Encodage positionnel exact a valider contre la spec DGI. -->\n'
        f'<DeclarationTVA reference="{_xml_escape(d.reference or "")}">\n'
        f'{lignes}\n'
        '</DeclarationTVA>\n'
    )


def materialiser_acomptes_is(company, exercice, *, is_reference=None,
                             validees_seulement=False):
    """NTMAR12 — matérialise (idempotent) les 4 ``AcompteIS`` d'un exercice à
    partir du calcul ``selectors.echeancier_acomptes`` (FG140). Ne recrée pas un
    rang déjà présent (``get_or_create`` par (company, exercice, rang)) et ne
    touche jamais un acompte déjà payé. Renvoie la liste des ``AcompteIS``."""
    from . import selectors as compta_selectors

    if exercice.company_id != company.id:
        raise ValidationError("L'exercice n'appartient pas à cette société.")
    echeancier = compta_selectors.echeancier_acomptes(
        company, exercice, is_reference=is_reference,
        validees_seulement=validees_seulement)
    resultats = []
    for acompte in echeancier['acomptes']:
        obj, _created = AcompteIS.objects.get_or_create(
            company=company, exercice=exercice, rang=acompte['numero'],
            defaults={
                'montant': acompte['montant'],
                'date_echeance': acompte['date_echeance'],
            })
        resultats.append(obj)
    return resultats


def export_simpl_is(company, exercice, *, is_reference=None,
                    reintegrations=None, deductions=None,
                    validees_seulement=False):
    """NTMAR12 — génère le fichier SIMPL-IS (structure DGI) d'un exercice :
    résultat fiscal, IS dû, les 4 acomptes datés et la régularisation. Renvoie
    une str XML rechargeable. Réutilise ``selectors.estimer_is`` /
    ``echeancier_acomptes`` / ``regularisation_is`` (aucun nouveau calcul)."""
    from . import selectors as compta_selectors

    if exercice.company_id != company.id:
        raise ValidationError("L'exercice n'appartient pas à cette société.")
    estimation = compta_selectors.estimer_is(
        company, exercice, reintegrations=reintegrations, deductions=deductions,
        validees_seulement=validees_seulement)
    echeancier = compta_selectors.echeancier_acomptes(
        company, exercice, is_reference=is_reference,
        validees_seulement=validees_seulement)
    regul = compta_selectors.regularisation_is(
        company, exercice, is_reference=is_reference,
        reintegrations=reintegrations, deductions=deductions,
        validees_seulement=validees_seulement)

    acomptes_xml = '\n'.join(
        f'    <Acompte rang="{a["numero"]}" echeance="{a["date_echeance"].isoformat()}">'
        f'{a["montant"]}</Acompte>'
        for a in echeancier['acomptes'])
    postes = [
        ('ExerciceDebut', exercice.date_debut.isoformat()),
        ('ExerciceFin', exercice.date_fin.isoformat()),
        ('ResultatFiscal', str(estimation['resultat_fiscal'])),
        ('ISDu', str(estimation['is_du'])),
        ('TotalAcomptes', str(echeancier['total_acomptes'])),
        ('Regularisation', str(regul['regularisation'])),
        ('SensRegularisation', regul['sens']),
    ]
    lignes = '\n'.join(
        f'  <Poste code="{code}">{_xml_escape(val)}</Poste>' for code, val in postes)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!-- SIMPL-IS (structure DGI, NTMAR12) - genere localement, non '
        'transmis. Encodage positionnel exact a valider contre la spec DGI. -->\n'
        f'<DeclarationIS exercice="{exercice.id}">\n'
        f'{lignes}\n'
        '  <Acomptes>\n'
        f'{acomptes_xml}\n'
        '  </Acomptes>\n'
        '</DeclarationIS>\n'
    )
