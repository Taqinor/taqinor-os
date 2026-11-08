# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K10 — la résiliation (vraie route POST monitoring/abonnements/<id>/resilier/) ne fait que couper
`MonitoringConfig.enabled` ; l'évaluation de sous-performance (et le balayage quotidien, qui ne filtre pas
`enabled`) continue sur un système dont les relevés s'arrêtent avec l'abonnement. Système à 100 % jusqu'à
la résiliation ; 120 jours plus tard : drapeau + ticket SAV préventif au nom du client parti, et indice de
disponibilité sous le SLA garanti."""
SONDE = {"constat": "C-AMON-010", "sha": "3007f3f04",
         "attendu": "repro si témoin (avant résiliation) non sous-performant, puis à J+120 après résiliation : "
                    "underperforming, drapeau ouvert et ticket créé ; SLA sous garantie",
         "modeles": ["monitoring.UnderperformanceFlag", "sav.Ticket", "monitoring.AbonnementMonitoring"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import (MonitoringConfig, MonitoringSettings, ProductionReading, SlaDisponibilite,
                                        UnderperformanceFlag)
    from apps.monitoring.services import evaluate_underperformance
    from apps.monitoring.selectors import disponibilite_vs_garantie
    from apps.sav.models import Ticket
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 010', slug='sonde-amon-010')
    u = get_user_model().objects.create_user(username='sonde_amon_010', password='x', role_legacy='responsable',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    s = MonitoringSettings.get(co)
    s.auto_create_ticket = True
    s.underperf_threshold_pct = Decimal('20')
    s.save()
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON10', email='amon10@example.invalid')
    inst = Installation.objects.create(company=co, reference='CH-AMON-010', client=cl,
                                       puissance_installee_kwc=Decimal('4'))
    cfg = MonitoringConfig.objects.create(company=co, installation=inst, enabled=True,
                                          expected_annual_kwh=Decimal('6000'))
    SlaDisponibilite.objects.create(company=co, installation=inst, disponibilite_garantie_pct=Decimal('98'))
    today = timezone.localdate()
    jour = (Decimal('6000') / Decimal('365')).quantize(Decimal('0.01'))
    for i in range(200, 0, -1):
        ProductionReading.objects.create(company=co, installation=inst, date=today - timedelta(days=i),
                                         period_days=1, energy_kwh=jour)
    temoin = evaluate_underperformance(inst, user=u, today=today)
    r = api.post('/api/django/monitoring/abonnements/', {'installation_id': inst.id, 'periodicite': 'mensuel',
                                                         'montant': '150'}, format='json', **H)
    rr = api.post(f'/api/django/monitoring/abonnements/{r.data["id"]}/resilier/', {'motif': 'client parti'},
                  format='json', **H)
    cfg.refresh_from_db()
    plus120 = today + timedelta(days=120)
    apres = evaluate_underperformance(inst, today=plus120)
    flag = UnderperformanceFlag.objects.filter(installation=inst, is_open=True).first()
    dv = disponibilite_vs_garantie(inst, today=plus120)
    obs = {'temoin': {'ratio_pct': str(temoin['ratio_pct']), 'underperforming': temoin['underperforming']},
           'creation_http': r.status_code, 'resilier_http': rr.status_code, 'config_enabled_apres': cfg.enabled,
           'J+120': {'ratio_pct': str(apres['ratio_pct']), 'underperforming': apres['underperforming'],
                     'data_status': apres['data_status']},
           'drapeau_ouvert': bool(flag), 'ticket': flag and flag.ticket and flag.ticket.reference,
           'tickets_systeme': Ticket.objects.filter(installation=inst).count(),
           'sla_J+120': {'mesuree': str(dv.get('disponibilite_mesuree_pct')), 'ecart': str(dv.get('ecart_pct')),
                         'sous_garantie': dv.get('sous_garantie')}}
    defaut = (not temoin['underperforming'] and rr.status_code == 200 and cfg.enabled is False
              and apres['underperforming'] and flag is not None and flag.ticket_id is not None)
    obs['repro'] = bool(defaut)
    return obs
