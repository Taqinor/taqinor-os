"""PUB96/PUB98 — Pont comptable du moteur publicitaire (adsengine → compta).

Le premier coût d'acquisition (``InsightSnapshot.spend``) n'atteignait JAMAIS la
comptabilité : la dépense publicitaire restait hors P&L. Ce pont la fait entrer
en compta comme une **écriture BROUILLON mensuelle** (charge publicitaire au
compte ``6144``), proposée — **jamais validée automatiquement** (comme le pont
``assurances`` : brouillon posé, second regard humain requis) — et RAPPROCHABLE
avec la réconciliation Meta.

Frontière cross-app (M3) : toute écriture passe par ``apps.compta.services``
(jamais un import de ``apps.compta.models`` ni un SQL direct — règle #1). La
société est TOUJOURS dérivée de l'appelant, jamais lue d'un corps de requête.

Idempotence (jamais de double écriture) : chaque écriture porte un
``source_type`` + ``source_id`` STABLE (dérivé de la période ou de la facture) ;
la contrainte d'unicité ``uniq_ecriture_par_source`` de ``EcritureComptable``
(``company`` × ``source_type`` × ``source_id``) garantit au niveau BASE qu'un
re-run du même mois ne crée jamais un doublon.

PUB98 — TVA auto-liquidation : les factures Meta Ireland vers une société
marocaine relèvent de l'auto-liquidation TVA (services importés). L'ingestion
d'une facture Meta (CSV/PDF) pose une écriture BROUILLON de facture fournisseur
avec la TVA auto-liquidée pré-calculée (compensée : due ↔ récupérable), et
SIGNALE l'écart entre le montant facturé et le spend synchronisé.
"""
from __future__ import annotations

import calendar
import csv
import datetime
import io
from decimal import Decimal, InvalidOperation

# Comptes CGNC utilisés (résolus/semés côté compta, jamais importés en modèle).
COMPTE_PUBLICITE = '6144'          # Charge — Publicité, publications, RP
COMPTE_FNP = '4486'               # Fournisseurs - factures non parvenues (accrual)
COMPTE_FOURNISSEUR = '4411'       # Fournisseurs (facture Meta reçue)
COMPTE_TVA_RECUP = '34552'        # État - TVA récupérable sur charges
COMPTE_TVA_DUE = '44552'          # État - TVA due

# Marqueurs de source (idempotence via uniq_ecriture_par_source).
SOURCE_DEPENSE = 'adsengine_depense_pub'
SOURCE_FACTURE = 'adsengine_facture_meta'

# Taux de TVA marocain par défaut (auto-liquidation services importés).
TVA_RATE_DEFAULT = Decimal('0.20')


def _period_source_id(year, month):
    """Clé entière STABLE d'une période (YYYYMM) — support d'idempotence."""
    return int(year) * 100 + int(month)


def _month_bounds(year, month):
    """(premier, dernier) jour du mois."""
    last = calendar.monthrange(int(year), int(month))[1]
    return (datetime.date(int(year), int(month), 1),
            datetime.date(int(year), int(month), last))


def monthly_ad_spend(company, year, month):
    """Somme de la dépense publicitaire (Meta) d'une société sur un mois.

    Sommée sur les ``InsightSnapshot`` de niveau CAMPAGNE uniquement (comme la
    réconciliation ADSENG31) : sommer aussi ad/adset double-compterait la même
    dépense. Renvoie un ``Decimal`` (0 si aucun snapshot)."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Sum

    from .models import AdCampaignMirror, InsightSnapshot

    date_start, date_end = _month_bounds(year, month)
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    total = (InsightSnapshot.objects
             .filter(company=company, content_type=ct,
                     date__gte=date_start, date__lte=date_end)
             .aggregate(s=Sum('spend'))['s'])
    return total or Decimal('0')


def _od_journal(company):
    """Journal des Opérations Diverses de la société (semé si absent)."""
    from apps.compta import services as compta_services
    from apps.compta.models import Journal

    for journal in compta_services.seed_journaux(company):
        if journal.type_journal == Journal.Type.OPERATIONS_DIVERSES:
            return journal
    # Repli défensif : le seed garantit l'OD, mais on ne suppose jamais l'ordre.
    return compta_services.seed_journaux(company)[0]


def _ensure_comptes(company, numeros):
    """Sème le plan comptable si l'un des comptes requis manque (idempotent)."""
    from apps.compta import services as compta_services

    if any(compta_services.get_compte(company, num) is None for num in numeros):
        compta_services.seed_plan_comptable(company)


def book_monthly_ad_spend(company, *, year, month, user=None, spend=None):
    """PUB96 — Propose l'écriture BROUILLON mensuelle de charge publicitaire.

    Débite ``6144`` (Publicité) et crédite ``4486`` (fournisseurs - factures
    non parvenues : la dépense est certaine mais pas encore facturée), en
    BROUILLON — jamais validée automatiquement. Idempotente par
    ``(company, SOURCE_DEPENSE, YYYYMM)`` : un re-run du même mois renvoie
    l'écriture existante sans en créer une seconde.

    NO-OP propre si la dépense du mois est nulle (aucune écriture à zéro).
    Renvoie l'``EcritureComptable`` (ou ``None`` si dépense nulle)."""
    from apps.compta import services as compta_services
    from apps.compta.models import EcritureComptable
    from apps.compta.selectors import ecriture_pour_source

    montant = Decimal(spend) if spend is not None else monthly_ad_spend(
        company, year, month)
    montant = montant.quantize(Decimal('0.01'))
    source_id = _period_source_id(year, month)

    # Idempotence : une écriture pour ce (source_type, source_id) existe déjà ?
    existing = ecriture_pour_source(company, SOURCE_DEPENSE, source_id)
    if existing is not None:
        return existing
    if montant <= 0:
        return None

    _ensure_comptes(company, (COMPTE_PUBLICITE, COMPTE_FNP))
    compte_charge = compta_services.get_compte(company, COMPTE_PUBLICITE)
    compte_fnp = compta_services.get_compte(company, COMPTE_FNP)
    date_start, date_end = _month_bounds(year, month)
    libelle = f'Dépense publicitaire Meta — {year:04d}-{month:02d}'
    lignes = [
        {'compte': compte_charge, 'libelle': libelle,
         'debit': montant, 'credit': Decimal('0')},
        {'compte': compte_fnp, 'libelle': libelle,
         'debit': Decimal('0'), 'credit': montant},
    ]
    return compta_services.creer_ecriture(
        company, _od_journal(company), date_end, libelle, lignes,
        reference=f'PUB-{year:04d}{month:02d}',
        source_type=SOURCE_DEPENSE, source_id=source_id,
        created_by=user, statut=EcritureComptable.Statut.BROUILLON)


# ── PUB98 — Ingestion facture Meta + TVA auto-liquidation ────────────────────

def parse_meta_invoice_csv(content):
    """Extrait le montant HT (Decimal) d'un export CSV de facturation Meta.

    Tolérant : cherche une colonne « amount »/« montant »/« total » (insensible
    à la casse) et somme les valeurs numériques. Renvoie ``Decimal('0')`` si
    rien d'exploitable (dégradation propre — jamais d'exception). ``content``
    accepte ``str`` ou ``bytes``."""
    if isinstance(content, bytes):
        content = content.decode('utf-8', errors='replace')
    total = Decimal('0')
    try:
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            return Decimal('0')
        cols = {(name or '').strip().lower(): name for name in reader.fieldnames}
        target = None
        for key in ('amount', 'montant', 'amount_spent', 'total', 'spend'):
            if key in cols:
                target = cols[key]
                break
        if target is None:
            return Decimal('0')
        for row in reader:
            raw = (row.get(target) or '').strip().replace(',', '.')
            raw = ''.join(c for c in raw if c.isdigit() or c in '.-')
            if not raw:
                continue
            try:
                total += Decimal(raw)
            except (InvalidOperation, ValueError):
                continue
    except (csv.Error, ValueError):
        return Decimal('0')
    return total.quantize(Decimal('0.01'))


def ingest_meta_invoice(company, *, year, month, montant_ht, tva_rate=None,
                        user=None, reference=''):
    """PUB98 — Facture fournisseur Meta BROUILLON avec TVA auto-liquidée.

    Les services Meta Ireland facturés à une société marocaine relèvent de
    l'auto-liquidation (services importés) : la société AUTO-LIQUIDE la TVA (elle
    la déclare comme due ET la récupère — effet net nul en trésorerie). L'écriture
    BROUILLON (jamais validée auto) reclasse l'accrual ``4486`` vers le
    fournisseur ``4411`` et enregistre la TVA auto-liquidée
    (``34552`` récupérable ↔ ``44552`` due) ::

        Débit 4486 (HT)  |  Crédit 4411 (HT)          — reclassement FNP→fournisseur
        Débit 34552 (TVA)|  Crédit 44552 (TVA)        — TVA auto-liquidée compensée

    Idempotente par ``(company, SOURCE_FACTURE, YYYYMM)``. SIGNALE l'écart entre
    le montant facturé et le spend synchronisé du mois (``ecart_vs_spend``).

    Renvoie ``{'ecriture', 'montant_ht', 'montant_tva', 'spend_synchronise',
    'ecart_vs_spend', 'created'}``."""
    from apps.compta import services as compta_services
    from apps.compta.models import EcritureComptable
    from apps.compta.selectors import ecriture_pour_source

    montant_ht = Decimal(montant_ht).quantize(Decimal('0.01'))
    rate = Decimal(tva_rate) if tva_rate is not None else TVA_RATE_DEFAULT
    montant_tva = (montant_ht * rate).quantize(Decimal('0.01'))
    source_id = _period_source_id(year, month)
    spend = monthly_ad_spend(company, year, month).quantize(Decimal('0.01'))
    ecart = (montant_ht - spend).quantize(Decimal('0.01'))

    existing = ecriture_pour_source(company, SOURCE_FACTURE, source_id)
    if existing is not None:
        return {'ecriture': existing, 'montant_ht': montant_ht,
                'montant_tva': montant_tva, 'spend_synchronise': spend,
                'ecart_vs_spend': ecart, 'created': False}

    _ensure_comptes(
        company,
        (COMPTE_FNP, COMPTE_FOURNISSEUR, COMPTE_TVA_RECUP, COMPTE_TVA_DUE))
    compte_fnp = compta_services.get_compte(company, COMPTE_FNP)
    compte_fourn = compta_services.get_compte(company, COMPTE_FOURNISSEUR)
    compte_tva_recup = compta_services.get_compte(company, COMPTE_TVA_RECUP)
    compte_tva_due = compta_services.get_compte(company, COMPTE_TVA_DUE)
    _, date_end = _month_bounds(year, month)
    libelle = f'Facture Meta (auto-liquidation TVA) — {year:04d}-{month:02d}'
    lignes = [
        {'compte': compte_fnp, 'libelle': libelle,
         'debit': montant_ht, 'credit': Decimal('0'),
         'tiers_type': 'adsengine_meta', 'tiers_id': None},
        {'compte': compte_fourn, 'libelle': libelle,
         'debit': Decimal('0'), 'credit': montant_ht,
         'tiers_type': 'adsengine_meta', 'tiers_id': None},
    ]
    if montant_tva > 0:
        lignes.extend([
            {'compte': compte_tva_recup,
             'libelle': f'{libelle} — TVA récupérable',
             'debit': montant_tva, 'credit': Decimal('0')},
            {'compte': compte_tva_due,
             'libelle': f'{libelle} — TVA due (auto-liquidée)',
             'debit': Decimal('0'), 'credit': montant_tva},
        ])
    ecriture = compta_services.creer_ecriture(
        company, _od_journal(company), date_end, libelle, lignes,
        reference=reference or f'META-{year:04d}{month:02d}',
        source_type=SOURCE_FACTURE, source_id=source_id,
        created_by=user, statut=EcritureComptable.Statut.BROUILLON)
    return {'ecriture': ecriture, 'montant_ht': montant_ht,
            'montant_tva': montant_tva, 'spend_synchronise': spend,
            'ecart_vs_spend': ecart, 'created': True}
