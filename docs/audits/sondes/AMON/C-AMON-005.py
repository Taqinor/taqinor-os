# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K05 — changement de formule = créer le nouvel abonnement puis résilier l'ancien (aucune modification
possible). Vraies routes : 2 × POST monitoring/abonnements/ sur le MÊME système, puis POST resilier sur le
premier. L'abonné `_arreter_supervision_a_la_resiliation` coupe la config sans regarder s'il reste un
abonnement actif : système toujours abonné mais supervision coupée, portail « non raccordé »."""
SONDE = {"constat": "C-AMON-005", "sha": "3007f3f04",
         "attendu": "repro si 2 × 201 sur le même système, resilier 200, config enabled=False alors que le 2e "
                    "abonnement est « actif »",
         "modeles": ["monitoring.AbonnementMonitoring", "monitoring.MonitoringConfig"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import AbonnementMonitoring, MonitoringConfig
    from apps.monitoring.selectors import production_kwh_series_client_portail
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 005', slug='sonde-amon-005')
    u = get_user_model().objects.create_user(username='sonde_amon_005', password='x', role_legacy='responsable',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON5', email='amon5@example.invalid')
    inst = Installation.objects.create(company=co, reference='CH-AMON-005', client=cl,
                                       puissance_installee_kwc=Decimal('4'))
    cfg = MonitoringConfig.objects.create(company=co, installation=inst, enabled=True, provider='fusionsolar')
    url = '/api/django/monitoring/abonnements/'
    r1 = api.post(url, {'installation_id': inst.id, 'periodicite': 'mensuel', 'montant': '150'}, format='json', **H)
    portail_avant = production_kwh_series_client_portail(co, cl.id)['provider_configure']
    r2 = api.post(url, {'installation_id': inst.id, 'periodicite': 'annuel', 'montant': '1500'}, format='json', **H)
    rr = None
    if r1.status_code == 201:
        rr = api.post(f'{url}{r1.data["id"]}/resilier/', {'motif': 'passage à l\'annuel'}, format='json', **H)
    cfg.refresh_from_db()
    statuts = list(AbonnementMonitoring.objects.filter(company=co).order_by('id').values_list('periodicite', 'statut'))
    obs = {'creation_1_http': r1.status_code, 'creation_2_http': r2.status_code,
           'resilier_1_http': rr and rr.status_code,
           'abonnements': statuts, 'config_enabled_apres': cfg.enabled,
           'portail_provider_configure_avant': portail_avant,
           'portail_provider_configure_apres': production_kwh_series_client_portail(co, cl.id)['provider_configure']}
    defaut = (r1.status_code == 201 and r2.status_code == 201 and rr is not None and rr.status_code == 200
              and cfg.enabled is False and ('annuel', 'actif') in statuts)
    obs['repro'] = bool(defaut)
    return obs
