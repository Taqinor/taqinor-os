"""PUB96 — Pont comptable du moteur publicitaire (adsengine → compta).

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
``source_type`` + ``source_id`` STABLE (dérivé de la période) ; la contrainte
d'unicité ``uniq_ecriture_par_source`` de ``EcritureComptable``
(``company`` × ``source_type`` × ``source_id``) garantit au niveau BASE qu'un
re-run du même mois ne crée jamais un doublon.
"""
from __future__ import annotations

import calendar
import datetime
from decimal import Decimal

# Comptes CGNC utilisés (résolus/semés côté compta, jamais importés en modèle).
COMPTE_PUBLICITE = '6144'          # Charge — Publicité, publications, RP
COMPTE_FNP = '4486'               # Fournisseurs - factures non parvenues (accrual)

# Marqueur de source (idempotence via uniq_ecriture_par_source).
SOURCE_DEPENSE = 'adsengine_depense_pub'


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
    _, date_end = _month_bounds(year, month)
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
