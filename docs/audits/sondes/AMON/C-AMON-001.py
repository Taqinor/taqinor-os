# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K01 — deux relevés qui se CHEVAUCHENT (31 journaliers importés en CSV + 1 mensuel saisi à l'écran sur
le même mois) sont tous deux acceptés et leurs énergies ADDITIONNÉES par tous les lecteurs (CO2/certificat,
garantie annuelle, fenêtre de sous-performance), alors que la disponibilité, elle, fait l'union des jours.
Vraies routes : POST configs/<id>/import-releves/ puis POST readings/. Témoin : un doublon EXACT est refusé 409."""
SONDE = {"constat": "C-AMON-001", "sha": "3007f3f04",
         "attendu": "repro si le mensuel chevauchant est accepté (201) et que octobre compte 930 kWh au lieu de 465 "
                    "(co2, année calendaire, fenêtre récente, tCO2 doublées) ; témoin : doublon exact 409",
         "modeles": ["monitoring.ProductionReading", "monitoring.MonitoringConfig", "installations.Installation"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, ProductionReading
    from apps.monitoring.selectors import co2_for_installation
    from apps.monitoring.services import production_for_calendar_year, recent_production_kwh
    from apps.monitoring.analytics import om_metrics
    from apps.monitoring.report_carbon import tco2_evitees_periode
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 001', slug='sonde-amon-001')
    u = get_user_model().objects.create_user(username='sonde_amon_001', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON1', email='amon1@example.invalid')
    inst = Installation.objects.create(company=co, reference='CH-AMON-001', client=cl,
                                       puissance_installee_kwc=Decimal('4'))
    cfg = MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('6000'))
    d0 = date(2026, 10, 1)
    lignes = ['date;periode_jours;energie_kwh'] + [
        f'{(d0 + timedelta(days=i)).isoformat()};1;15' for i in range(31)]
    r_imp = api.post(f'/api/django/monitoring/configs/{cfg.pk}/import-releves/',
                     {'csv': '\n'.join(lignes) + '\n'}, format='json', **H)
    since, until = date(2026, 10, 1), date(2026, 10, 31)
    avant = {'co2_kwh': str(co2_for_installation(inst, since=since, until=until)['production_kwh']),
             'tco2': str(tco2_evitees_periode(co, installation=inst, since=since, until=until)[0])}
    r_mens = api.post('/api/django/monitoring/readings/', {
        'installation': inst.id, 'date': '2026-10-01', 'period_days': 31, 'energy_kwh': '465'}, format='json', **H)
    r_dup = api.post('/api/django/monitoring/readings/', {
        'installation': inst.id, 'date': '2026-10-01', 'period_days': 31, 'energy_kwh': '465'}, format='json', **H)
    today = date(2026, 11, 7)
    m = om_metrics(inst, today=today)
    apres = {'co2_kwh': str(co2_for_installation(inst, since=since, until=until)['production_kwh']),
             'tco2': str(tco2_evitees_periode(co, installation=inst, since=since, until=until)[0]),
             'annee_2026_kwh': str(production_for_calendar_year(inst, 2026)),
             'fenetre_recente_kwh': str(recent_production_kwh(inst, today=today)),
             'om_production_kwh': str(m['production_kwh']),
             'om_availability_pct': str(m['availability_pct'])}
    obs = {'import_http': r_imp.status_code, 'import': r_imp.data if r_imp.status_code == 200 else str(r_imp.data)[:200],
           'mensuel_chevauchant_http': r_mens.status_code,
           'doublon_exact_http': r_dup.status_code,
           'releves_en_base': ProductionReading.objects.filter(installation=inst).count(),
           'avant_mensuel': avant, 'apres_mensuel': apres}
    temoin_ok = r_imp.status_code == 200 and r_dup.status_code == 409
    defaut = (r_mens.status_code == 201 and Decimal(apres['co2_kwh']) == Decimal('930')
              and Decimal(apres['annee_2026_kwh']) == Decimal('930')
              and Decimal(apres['tco2']) > Decimal(avant['tco2']))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
