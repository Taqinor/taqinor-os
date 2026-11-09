# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K24 : réglage par défaut (auto_create_ticket=False), un drapeau de sous-performance s'ouvre. Le personnel
reçoit-il une notification ? Existe-t-il une route pour lister / classer les drapeaux ? Le client, lui, le voit-il
sur la vraie route portail ? On lit aussi ce que la vraie route fleet (vue parc) expose par système."""
SONDE = {"constat": "C-AMON-024", "sha": "39313d48e",
         "attendu": "repro si drapeau ouvert, 0 Notification, aucune route drapeau au routeur, portail alertes_ouvertes=1, fleet sans id de système en alerte",
         "modeles": ["monitoring.UnderperformanceFlag", "notifications.Notification"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.apps import apps as dj
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company, CustomUser
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import MonitoringConfig, MonitoringSettings, ProductionReading, UnderperformanceFlag
    from apps.monitoring.services import evaluate_underperformance
    from apps.monitoring import urls as murls
    from apps.roles.models import Role
    from apps.roles.permissions_registre import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT
    Notification = dj.get_model('notifications', 'Notification')
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde AMON 024', slug='sonde-amon-024')
    st = MonitoringSettings.get(co)
    adm = get_user_model().objects.create_user('amon024_adm', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON024', email='amon024@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-AMON024', client=cl,
                                       puissance_installee_kwc=Decimal('5.00'))
    MonitoringConfig.objects.create(company=co, installation=inst, expected_annual_kwh=Decimal('9000'))

    def mois(k):
        y, m = today.year, today.month - k
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1)
    for k in range(12, -1, -1):  # système à 60 % : 450 kWh/mois
        ProductionReading.objects.create(company=co, installation=inst, date=mois(k), energy_kwh=Decimal('450'),
                                         period_days=30)
    n_notif_avant = Notification.objects.filter(company=co).count()
    res = evaluate_underperformance(inst, today=today)
    n_notif_apres = Notification.objects.filter(company=co).count()
    routes = sorted({p for p, *_ in murls.router.registry})
    api = APIClient()
    api.force_authenticate(adm)
    probes = {}
    for chemin in ('/api/django/monitoring/flags/', '/api/django/monitoring/underperformance-flags/',
                   '/api/django/monitoring/drapeaux/'):
        probes[chemin] = api.get(chemin, **H).status_code
    fleet = None
    for chemin in ('/api/django/monitoring/configs/fleet/', '/api/django/monitoring/readings/fleet/'):
        rr = api.get(chemin, **H)
        if rr.status_code == 200:
            fj = rr.json()
            fleet = {'route': chemin, 'open_alerts': fj.get('open_alerts'),
                     'cles_systeme': sorted((fj.get('systems') or [{}])[0].keys()) if fj.get('systems') else []}
            break
    role, _ = Role.objects.get_or_create(company=co, nom=ROLE_PORTAIL_CLIENT,
                                         defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS), 'est_systeme': True})
    pu = CustomUser.objects.create_user(username='amon024_portail', password='motdepasse-test-1234', company=co, role=role)
    pu.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    pu.portail_client_id = cl.id
    pu.save()
    papi = APIClient()
    papi.force_authenticate(pu)
    pr = papi.get('/api/django/portail/client/ma-consommation/', **H)
    obs = {'auto_create_ticket_defaut': st.auto_create_ticket, 'ratio': str(res.get('ratio_pct')),
           'drapeau_ouvert': UnderperformanceFlag.objects.filter(installation=inst, is_open=True).exists(),
           'ticket': res.get('ticket') is not None, 'notifications_creees': n_notif_apres - n_notif_avant,
           'routes_monitoring': routes, 'routes_drapeau_http': probes, 'fleet': fleet,
           'portail_http': pr.status_code,
           'portail_alertes_ouvertes': pr.json().get('alertes_ouvertes') if pr.status_code == 200 else None}
    obs['repro'] = bool(obs['drapeau_ouvert'] and obs['notifications_creees'] == 0
                        and not any('flag' in r or 'drapeau' in r for r in routes)
                        and obs['portail_alertes_ouvertes'] == 1)
    return obs
