"""
Services monitoring — synchronisation des relevés + évaluation N52.

`sync_system` appelle le fournisseur configuré et stocke les relevés renvoyés
(source='auto'), de façon IDEMPOTENTE via `external_id`. No-op sûr quand aucun
fournisseur n'est configuré (renvoie 0 relevé importé).

`evaluate_underperformance` compare la production récente d'un système à son
attendu (config.expected_annual_kwh, sinon estimée depuis la puissance et le
productible). Sous le seuil société (MonitoringSettings), on ouvre (idempotent)
un drapeau ; et si la société a activé l'auto-ticket, on crée UN ticket SAV
préventif lié au drapeau — jamais deux pour un même drapeau ouvert. Repasse
au-dessus du seuil : on ferme le drapeau ouvert.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import (
    MonitoringConfig, MonitoringSettings, ProductionReading,
    UnderperformanceFlag,
)
from .providers import _coerce_reading, get_provider

# Productible conservateur (kWh/kWc/an) pour estimer l'attendu si non renseigné.
DEFAULT_PRODUCTIBLE_KWH_KWC = Decimal('1500')
# Fenêtre (jours) de récence pour l'évaluation de performance.
RECENT_WINDOW_DAYS = 365


def get_or_create_config(installation):
    """Config de supervision d'un système (créée à défaut, provider 'noop')."""
    obj, _ = MonitoringConfig.objects.get_or_create(
        installation=installation,
        defaults={'company': installation.company})
    return obj


def sync_system(installation, *, user=None):
    """Synchronise les relevés d'un système via son fournisseur configuré.

    Renvoie (nb_importes, provider_key). No-op sûr (0) si aucun fournisseur
    actif/configuré. Idempotent : un relevé auto déjà présent (même
    external_id) n'est pas re-créé.
    """
    config = get_or_create_config(installation)
    provider = get_provider(config.provider)
    raw_readings = provider.fetch_recent(installation, config) or []
    imported = 0
    for raw in raw_readings:
        try:
            data = _coerce_reading(raw)
        except (ValueError, TypeError, InvalidOperation):
            continue
        if data['date'] is None:
            continue
        ext = data['external_id']
        if ext:
            exists = ProductionReading.objects.filter(
                installation=installation, source=ProductionReading.Source.AUTO,
                external_id=ext).exists()
            if exists:
                continue
        ProductionReading.objects.create(
            company=installation.company, installation=installation,
            date=data['date'], period_days=data['period_days'],
            energy_kwh=Decimal(str(data['energy_kwh'])),
            source=ProductionReading.Source.AUTO, external_id=ext,
            created_by=user)
        imported += 1
    config.last_sync = timezone.now()
    config.save(update_fields=['last_sync'])
    return imported, config.provider


def _expected_recent_kwh(installation, config, window_days):
    """Production attendue (kWh) sur la fenêtre. None si inconnaissable."""
    annual = config.expected_annual_kwh
    if annual is None:
        kwc = installation.puissance_installee_kwc
        if not kwc:
            return None
        annual = Decimal(str(kwc)) * DEFAULT_PRODUCTIBLE_KWH_KWC
    return Decimal(str(annual)) * Decimal(window_days) / Decimal('365')


def recent_production_kwh(installation, *, window_days=RECENT_WINDOW_DAYS,
                          today=None):
    """Somme des relevés sur la fenêtre récente (toutes sources)."""
    today = today or timezone.localdate()
    since = today - timedelta(days=window_days)
    agg = ProductionReading.objects.filter(
        installation=installation, date__gte=since, date__lte=today)
    total = Decimal('0')
    for r in agg.values_list('energy_kwh', flat=True):
        total += Decimal(str(r))
    return total


def evaluate_underperformance(installation, *, user=None, today=None):
    """Évalue la performance d'un système et gère drapeau + ticket (N52).

    Renvoie un dict {evaluated, underperforming, ratio_pct, flag, ticket}.
    Ne fait RIEN de destructif ; l'auto-ticket n'est créé que si la société a
    activé la bascule. Idempotent : un drapeau ouvert ⇒ pas de second ticket.
    """
    today = today or timezone.localdate()
    company = installation.company
    settings_obj = MonitoringSettings.get(company) if company else None
    config = get_or_create_config(installation)

    result = {'evaluated': False, 'underperforming': False,
              'ratio_pct': None, 'flag': None, 'ticket': None}

    expected = _expected_recent_kwh(installation, config, RECENT_WINDOW_DAYS)
    has_data = ProductionReading.objects.filter(
        installation=installation).exists()
    # Pas de donnée de production OU pas d'attendu : on n'évalue pas (no-op).
    if not has_data or not expected or expected <= 0:
        return result

    actual = recent_production_kwh(installation, today=today)
    ratio = (actual / expected) * Decimal('100')
    result.update(evaluated=True, ratio_pct=ratio.quantize(Decimal('0.01')))

    threshold_pct = (settings_obj.underperf_threshold_pct
                     if settings_obj else Decimal('20'))
    # Sous-performe si le ratio est sous (100 - seuil) % de l'attendu.
    floor_pct = Decimal('100') - Decimal(str(threshold_pct))
    open_flag = UnderperformanceFlag.objects.filter(
        installation=installation, is_open=True).first()

    if ratio < floor_pct:
        result['underperforming'] = True
        if open_flag is None:
            open_flag = UnderperformanceFlag.objects.create(
                company=company, installation=installation,
                ratio_pct=result['ratio_pct'])
        else:
            open_flag.ratio_pct = result['ratio_pct']
            open_flag.save(update_fields=['ratio_pct'])
        result['flag'] = open_flag
        # Auto-ticket SAV — seulement si activé ET pas déjà lié (idempotent).
        if (settings_obj and settings_obj.auto_create_ticket
                and open_flag.ticket_id is None):
            ticket = _create_underperf_ticket(installation, open_flag, user)
            if ticket is not None:
                open_flag.ticket = ticket
                open_flag.save(update_fields=['ticket'])
                result['ticket'] = ticket
        elif open_flag.ticket_id is not None:
            result['ticket'] = open_flag.ticket
    else:
        # Performance revenue au-dessus du seuil : on ferme le drapeau ouvert.
        if open_flag is not None:
            open_flag.is_open = False
            open_flag.date_cloture = timezone.now()
            open_flag.save(update_fields=['is_open', 'date_cloture'])
    return result


def _create_underperf_ticket(installation, flag, user):
    """Crée UN ticket SAV préventif pour un drapeau de sous-performance.

    Réutilise la création de ticket SAV (références collision-proof). Le client
    vient du chantier. No-op (None) si le chantier n'a pas de client.
    """
    from apps.sav.models import Ticket
    from apps.ventes.utils.references import create_with_reference

    client = getattr(installation, 'client', None)
    if client is None:
        return None
    company = installation.company
    ratio = flag.ratio_pct

    def _save(ref):
        return Ticket.objects.create(
            reference=ref, company=company, client=client,
            installation=installation, type=Ticket.Type.PREVENTIF,
            statut=Ticket.Statut.NOUVEAU,
            priorite=Ticket.Priorite.HAUTE,
            description=(
                'Sous-performance détectée par la supervision : production '
                f'à {ratio} % de l\'attendu sur 12 mois. Vérification requise.'),
            created_by=user)

    return create_with_reference(Ticket, 'SAV', company, _save)
