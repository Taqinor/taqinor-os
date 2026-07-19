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

from django.db import transaction
from django.utils import timezone

from .models import (
    MonitoringConfig, MonitoringSettings, ProductionReading,
    ProductionWarranty, UnderperformanceFlag,
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


def seed_expected_annual_kwh(installation):
    """YSERV8 — sème ``expected_annual_kwh`` du config depuis l'étude/la recette.

    À la mise en service d'un chantier, raccorde la production attendue déjà
    calculée en amont : priorité au test de performance de réception FG278 (PR
    initial mesuré), sinon à la production annuelle de l'``etude_params`` du
    devis lié. Lectures cross-app via ``apps.ventes.selectors`` uniquement
    (jamais un import de ``ventes.models``).

    NE JAMAIS écraser une valeur déjà présente : on ne sème que si
    ``expected_annual_kwh`` est NULL (valeur manuelle ou déjà semée préservée).
    Renvoie le config (mis à jour ou inchangé). No-op si aucune source.
    """
    from apps.ventes import selectors as ventes_selectors

    config = get_or_create_config(installation)
    # Valeur déjà renseignée (manuelle ou semée) : on n'écrase jamais.
    if config.expected_annual_kwh is not None:
        return config

    expected = ventes_selectors.pr_initial_pour_chantier(installation.id)
    if expected is None:
        devis_id = getattr(installation, 'devis_id', None)
        if devis_id is not None:
            expected = ventes_selectors.production_attendue_pour_devis(devis_id)
    if expected is None:
        return config

    config.expected_annual_kwh = expected
    config.save(update_fields=['expected_annual_kwh'])
    return config


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

    # ERR47 — lecture-puis-création du drapeau ouvert SANS verrou : deux
    # évaluations concurrentes pour un même système inséraient toutes deux,
    # violant la contrainte partielle uniq_open_underperf_flag (500). On rend
    # l'open/close atomique et on verrouille le drapeau ouvert existant
    # (select_for_update) ou on le crée idempotemment via get_or_create —
    # défendu par la contrainte unique partielle en dernier recours.
    with transaction.atomic():
        open_flag = (UnderperformanceFlag.objects
                     .select_for_update()
                     .filter(installation=installation, is_open=True)
                     .first())

        if ratio < floor_pct:
            result['underperforming'] = True
            if open_flag is None:
                open_flag, _created = (
                    UnderperformanceFlag.objects.get_or_create(
                        installation=installation, is_open=True,
                        defaults={'company': company,
                                  'ratio_pct': result['ratio_pct']}))
                if not _created:
                    open_flag.ratio_pct = result['ratio_pct']
                    open_flag.save(update_fields=['ratio_pct'])
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


def production_for_calendar_year(installation, year):
    """Somme des relevés (kWh) d'une année calendaire pour un système."""
    agg = ProductionReading.objects.filter(
        installation=installation, date__year=year)
    total = Decimal('0')
    for r in agg.values_list('energy_kwh', flat=True):
        total += Decimal(str(r))
    return total


def production_warranty_status(installation, *, year=None):
    """FG282 — production réelle vs productible garanti (dégradé) d'une année.

    Renvoie un dict {has_warranty, year, guaranteed_kwh, actual_kwh, shortfall_kwh,
    compensation_mad, within_tolerance}. No-op gracieux (has_warranty=False) si
    aucune garantie de production n'est configurée pour le système.
    """
    warranty = getattr(installation, 'production_warranty', None)
    if warranty is None:
        warranty = (ProductionWarranty.objects
                    .filter(installation=installation).first())
    if warranty is None:
        return {'has_warranty': False}

    year = int(year or timezone.localdate().year)
    guaranteed = warranty.guaranteed_kwh_for_year(year)
    actual = production_for_calendar_year(installation, year)

    shortfall = guaranteed - actual
    if shortfall < 0:
        shortfall = Decimal('0')

    tolerance_kwh = guaranteed * (Decimal(str(warranty.tolerance_pct))
                                  / Decimal('100'))
    within_tolerance = shortfall <= tolerance_kwh
    # On ne compense que la part au-delà de la franchise contractuelle.
    compensable = Decimal('0') if within_tolerance else (shortfall - tolerance_kwh)
    compensation = (compensable
                    * Decimal(str(warranty.compensation_mad_per_kwh)))

    q2 = Decimal('0.01')
    return {
        'has_warranty': True,
        'year': year,
        'guaranteed_kwh': guaranteed.quantize(q2),
        'actual_kwh': actual.quantize(q2),
        'shortfall_kwh': shortfall.quantize(q2),
        'within_tolerance': within_tolerance,
        'compensation_mad': compensation.quantize(q2),
    }


def warranty_curve_overlay(installation, *, years=None, today=None,
                           drift_threshold_pct=None):
    """FG284 — superpose production mesurée et courbe garantie de dégradation.

    Pour chaque année écoulée depuis `start_year`, compare la production réelle
    au productible garanti dégradé de cette année (depuis ProductionWarranty).
    Une dérive ANORMALE = la production réelle tombe sous le garanti de plus de
    `drift_threshold_pct` (au-delà de la tolérance contractuelle). Le drapeau
    `manufacturer_recourse` signale un recours fabricant probable.

    Renvoie {has_warranty, threshold_pct, manufacturer_recourse, points:[...]}.
    No-op gracieux (has_warranty=False) sans garantie configurée. 100 % lecture.
    """
    warranty = getattr(installation, 'production_warranty', None)
    if warranty is None:
        warranty = (ProductionWarranty.objects
                    .filter(installation=installation).first())
    if warranty is None:
        return {'has_warranty': False}

    today = today or timezone.localdate()
    last_year = today.year
    start = int(warranty.start_year)
    if years:
        year_list = [int(start) + i for i in range(int(years))]
    else:
        year_list = list(range(start, last_year + 1))

    threshold = Decimal(str(
        drift_threshold_pct if drift_threshold_pct is not None
        else warranty.tolerance_pct or 5))

    points = []
    recourse = False
    for year in year_list:
        guaranteed = warranty.guaranteed_kwh_for_year(year)
        actual = production_for_calendar_year(installation, year)
        has_data = ProductionReading.objects.filter(
            installation=installation, date__year=year).exists()
        drift_pct = None
        anomalous = False
        if has_data and guaranteed > 0:
            # Dérive = (garanti - réel) / garanti × 100 (positive = sous-prod).
            drift_pct = ((guaranteed - actual) / guaranteed) * Decimal('100')
            anomalous = drift_pct > threshold
            if anomalous:
                recourse = True
        points.append({
            'year': year,
            'guaranteed_kwh': guaranteed.quantize(Decimal('0.01')),
            'actual_kwh': (actual.quantize(Decimal('0.01'))
                           if has_data else None),
            'drift_pct': (drift_pct.quantize(Decimal('0.01'))
                          if drift_pct is not None else None),
            'anomalous': anomalous,
        })

    return {
        'has_warranty': True,
        'installation': installation.id,
        'threshold_pct': threshold.quantize(Decimal('0.01')),
        'manufacturer_recourse': recourse,
        'points': points,
    }


def _create_underperf_ticket(installation, flag, user):
    """Crée UN ticket SAV préventif pour un drapeau de sous-performance.

    WIR88 — passe par la frontière services de l'app SAV
    (``apps.sav.services.creer_ticket_preventif``) au lieu d'instancier
    ``sav.Ticket`` directement (M3 : pas d'import de models cross-app). Le
    client vient du chantier. No-op (None) si le chantier n'a pas de client.
    """
    from apps.sav import services as sav_services

    client = getattr(installation, 'client', None)
    if client is None:
        return None
    ratio = flag.ratio_pct

    return sav_services.creer_ticket_preventif(
        company=installation.company, client=client, installation=installation,
        description=(
            'Sous-performance détectée par la supervision : production '
            f'à {ratio} % de l\'attendu sur 12 mois. Vérification requise.'),
        created_by=user)
