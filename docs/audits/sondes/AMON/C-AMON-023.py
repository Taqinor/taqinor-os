# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K23 : après résiliation (vraie route POST abonnements/<id>/resilier/), la config passe enabled=False mais le
beat balayage_quotidien évalue-t-il encore le système et lui ouvre-t-il un drapeau + ticket « sous-performance »
quand plus aucun relevé n'arrive ? Le beat est joué pour de vrai, borné à la société de la sonde
(active_companies patché) et daté J+30/60/90/120 (localdate patché). Témoin : J0 juste après la résiliation,
système sain, aucun drapeau."""
SONDE = {"constat": "C-AMON-023", "sha": "39313d48e",
         "attendu": "repro si enabled=False après résiliation ET drapeau ouvert + ticket préventif à une date J+n par le beat",
         "modeles": ["monitoring.UnderperformanceFlag", "monitoring.AbonnementMonitoring", "sav.Ticket"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import (AbonnementMonitoring, MonitoringConfig, MonitoringSettings,
                                        ProductionReading, UnderperformanceFlag)
    from apps.monitoring.tasks import balayage_quotidien
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde AMON 023', slug='sonde-amon-023')
    st = MonitoringSettings.get(co)
    st.auto_create_ticket = True
    st.save()
    u = get_user_model().objects.create_user('amon023_adm', password='x', company=co, role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON023', email='amon023@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-AMON023', client=cl,
                                       puissance_installee_kwc=Decimal('5.00'))
    cfg = MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('9000'),
                                          enabled=True)

    def mois(k):
        y, m = today.year, today.month - k
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1)
    for k in range(12, -1, -1):
        ProductionReading.objects.create(company=co, installation=inst, date=mois(k), energy_kwh=Decimal('750'),
                                         period_days=30)
    ab = AbonnementMonitoring.objects.create(company=co, client_id=cl.id, installation_id=inst.id,
                                             montant=Decimal('150'), date_debut=mois(12))
    r = api.post(f'/api/django/monitoring/abonnements/{ab.id}/resilier/', {'motif': 'client parti'}, format='json', **H)
    cfg.refresh_from_db()
    ab.refresh_from_db()
    obs = {'resilier_http': r.status_code, 'abonnement_statut': ab.statut, 'config_enabled': cfg.enabled}

    def beat(jour):
        with mock.patch('authentication.selectors.active_companies', return_value=[co]), \
             mock.patch('django.utils.timezone.localdate', return_value=jour):
            balayage_quotidien()
        f = UnderperformanceFlag.objects.filter(installation=inst, is_open=True).first()
        return {'jour': jour.isoformat(), 'drapeau_ouvert': f is not None,
                'ratio': None if f is None else str(f.ratio_pct),
                'ticket': None if f is None or f.ticket_id is None else {
                    'type': getattr(f.ticket, 'type_ticket', None), 'priorite': getattr(f.ticket, 'priorite', None)}}
    obs['J0'] = beat(today)
    obs['suivi'] = [beat(today + timedelta(days=n)) for n in (30, 60, 90, 120)]
    premier = next((x for x in obs['suivi'] if x['drapeau_ouvert']), None)
    obs['premier_drapeau'] = premier
    temoin_ok = obs['resilier_http'] == 200 and not obs['J0']['drapeau_ouvert']
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and obs['config_enabled'] is False and premier is not None
                        and premier['ticket'] is not None)
    return obs
