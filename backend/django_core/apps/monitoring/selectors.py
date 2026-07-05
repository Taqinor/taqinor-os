"""
Sélecteurs monitoring (lecture) — agrégations multi-systèmes (FG281).

Vue PARC/FLOTTE : production totale, kWc installés, PR moyen et alertes
ouvertes sur l'ensemble des systèmes actifs d'une société. 100 % lecture,
scoping société assuré par l'appelant (viewset filtre déjà par company).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import (
    MonitoringConfig, ProductionReading, UnderperformanceFlag,
)
from .services import _expected_recent_kwh

# FG286 — facteur d'émission du réseau marocain (kg CO₂ évité par kWh
# autoproduit). Même hypothèse que l'energy report (apps.installations) : on la
# RECOPIE ici plutôt que d'importer un autre app domaine (frontière services).
DEFAULT_CO2_KG_PAR_KWH = Decimal('0.81')
# FG288 — tarif électricité par défaut (MAD/kWh) pour chiffrer les économies
# côté portail client. Même hypothèse que l'energy report (recopiée, pas
# importée).
DEFAULT_TARIF_MAD_PAR_KWH = Decimal('1.40')


def _q(value, places='0.01'):
    return Decimal(str(value)).quantize(Decimal(places)) if value is not None else None


def fleet_overview(company, *, window_days=365, today=None):
    """Synthèse parc d'une société sur la fenêtre récente.

    Renvoie production totale, kWc cumulés, PR moyen pondéré par l'attendu,
    nombre de systèmes actifs, et alertes (drapeaux de sous-performance
    ouverts). Réutilise la logique d'attendu du service N52.
    """
    today = today or timezone.localdate()
    since = today - timedelta(days=window_days)

    # Systèmes actifs supervisés : tout chantier ayant une config monitoring.
    configs = (MonitoringConfig.objects
               .filter(company=company)
               .select_related('installation'))

    total_kwh = Decimal('0')
    total_expected = Decimal('0')
    total_kwc = Decimal('0')
    systems = []
    active_count = 0

    for config in configs:
        inst = config.installation
        if not getattr(inst, 'parc_actif', True):
            continue
        active_count += 1
        kwc = inst.puissance_installee_kwc or Decimal('0')
        total_kwc += Decimal(str(kwc))

        prod = ProductionReading.objects.filter(
            installation=inst, date__gte=since, date__lte=today
        ).aggregate(s=Sum('energy_kwh'))['s'] or Decimal('0')
        prod = Decimal(str(prod))
        total_kwh += prod

        expected = _expected_recent_kwh(inst, config, window_days)
        pr_pct = None
        if expected and expected > 0:
            total_expected += expected
            pr_pct = _q((prod / expected) * Decimal('100'))

        systems.append({
            'installation': inst.id,
            'reference': getattr(inst, 'reference', None),
            'puissance_kwc': _q(kwc),
            'production_kwh': _q(prod),
            'pr_pct': pr_pct,
        })

    fleet_pr = None
    if total_expected > 0:
        fleet_pr = _q((total_kwh / total_expected) * Decimal('100'))

    open_alerts = UnderperformanceFlag.objects.filter(
        company=company, is_open=True).count()

    return {
        'window_days': window_days,
        'systems_active': active_count,
        'total_kwc': _q(total_kwc),
        'total_production_kwh': _q(total_kwh),
        'fleet_pr_pct': fleet_pr,
        'open_alerts': open_alerts,
        'systems': systems,
    }


def co2_for_installation(installation, *, since=None, until=None,
                         co2_kg_par_kwh=None):
    """CO₂ évité (kg + tonnes) d'un système sur une période (toutes sources).

    `since`/`until` (dates) bornent la période ; sinon toute la production.
    Réutilise le facteur réseau marocain par défaut.
    """
    factor = Decimal(str(co2_kg_par_kwh)) if co2_kg_par_kwh is not None \
        else DEFAULT_CO2_KG_PAR_KWH
    qs = ProductionReading.objects.filter(installation=installation)
    if since is not None:
        qs = qs.filter(date__gte=since)
    if until is not None:
        qs = qs.filter(date__lte=until)
    total_kwh = qs.aggregate(s=Sum('energy_kwh'))['s'] or Decimal('0')
    total_kwh = Decimal(str(total_kwh))
    co2_kg = total_kwh * factor
    return {
        'installation': installation.id,
        'production_kwh': _q(total_kwh),
        'co2_kg': _q(co2_kg),
        'co2_tonnes': co2_kg / Decimal('1000'),
        'co2_kg_par_kwh': factor,
    }


def co2_fleet(company, *, since=None, until=None, co2_kg_par_kwh=None):
    """FG286 — CO₂ évité par système ET cumulé sur le parc d'une société."""
    factor = Decimal(str(co2_kg_par_kwh)) if co2_kg_par_kwh is not None \
        else DEFAULT_CO2_KG_PAR_KWH
    configs = (MonitoringConfig.objects
               .filter(company=company)
               .select_related('installation'))
    systems = []
    total_kwh = Decimal('0')
    for config in configs:
        inst = config.installation
        if not getattr(inst, 'parc_actif', True):
            continue
        row = co2_for_installation(
            inst, since=since, until=until, co2_kg_par_kwh=factor)
        total_kwh += Decimal(str(row['production_kwh'] or 0))
        systems.append({
            'installation': inst.id,
            'reference': getattr(inst, 'reference', None),
            'production_kwh': row['production_kwh'],
            'co2_kg': row['co2_kg'],
            'co2_tonnes': row['co2_tonnes'].quantize(Decimal('0.001')),
        })
    total_co2_kg = total_kwh * factor
    return {
        'co2_kg_par_kwh': factor,
        'total_production_kwh': _q(total_kwh),
        'total_co2_kg': _q(total_co2_kg),
        'total_co2_tonnes': (total_co2_kg / Decimal('1000')).quantize(
            Decimal('0.001')),
        'systems': systems,
    }


def client_environmental_dashboard(company, client_id, *,
                                   tarif_mad_par_kwh=None,
                                   co2_kg_par_kwh=None):
    """FG288 — synthèse environnementale CUMULÉE des systèmes d'un client.

    Production / économies (MAD) / CO₂ évité cumulés sur tous les systèmes du
    client de la société. Lecture via jointure string-FK
    (`installation__client_id`), sans importer un autre app domaine. Scoping
    société assuré par le filtre `company`.
    """
    tarif = Decimal(str(tarif_mad_par_kwh)) if tarif_mad_par_kwh is not None \
        else DEFAULT_TARIF_MAD_PAR_KWH
    factor = Decimal(str(co2_kg_par_kwh)) if co2_kg_par_kwh is not None \
        else DEFAULT_CO2_KG_PAR_KWH

    qs = ProductionReading.objects.filter(
        company=company, installation__client_id=client_id)
    total_kwh = qs.aggregate(s=Sum('energy_kwh'))['s'] or Decimal('0')
    total_kwh = Decimal(str(total_kwh))

    economies = total_kwh * tarif
    co2_kg = total_kwh * factor

    # Nombre de systèmes du client (distincts) dans le périmètre.
    systems_count = (qs.values('installation_id').distinct().count())

    return {
        'client': int(client_id),
        'systems_count': systems_count,
        'total_production_kwh': _q(total_kwh),
        'economies_mad': _q(economies),
        'co2_kg': _q(co2_kg),
        'co2_tonnes': (co2_kg / Decimal('1000')).quantize(Decimal('0.001')),
        'tarif_mad_par_kwh': tarif,
        'co2_kg_par_kwh': factor,
    }


def usage_kwh_periode(company, installation, periode_debut, periode_fin):
    """XCTR16 — kWh supervisés (``ProductionReading``) d'un système sur une
    période [``periode_debut``, ``periode_fin``) — borne de fin EXCLUSIVE pour
    ne jamais compter le premier jour du cycle suivant.

    Renvoie ``None`` (pas ``Decimal('0')``) quand AUCUN relevé n'existe sur la
    période : l'appelant (facturation à l'usage, XCTR16) distingue ainsi
    « aucune lecture disponible » (ligne omise + motif tracé) de « 0 kWh
    consommés » (ligne facturée à 0, franchise non dépassée). Lecture seule,
    scoping société assuré par le filtre ``company``.
    """
    if installation is None or periode_debut is None or periode_fin is None:
        return None
    qs = ProductionReading.objects.filter(
        company=company, installation=installation,
        date__gte=periode_debut, date__lt=periode_fin)
    if not qs.exists():
        return None
    total = qs.aggregate(s=Sum('energy_kwh'))['s'] or Decimal('0')
    return Decimal(str(total))
