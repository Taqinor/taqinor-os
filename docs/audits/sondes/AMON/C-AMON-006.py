# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K06 — portail client « Ma consommation » : la vraie route GET portail/client/ma-consommation/ SERT les relevés
saisis/importés (points) mais renvoie provider_configure=False tant que le fournisseur est « Manuel » (noop) ;
l'écran PortailClientConsommation.jsx teste provider_configure AVANT les points et affiche alors
« Suivi de production non raccordé » — les relevés de l'abonné ne sont jamais montrés.
(La lecture de l'écran est statique ; la sonde prouve la réponse servie.)"""
SONDE = {"constat": "C-AMON-006", "sha": "3007f3f04",
         "attendu": "repro si 200, points non vide (3 relevés) et provider_configure == False pour un système "
                    "abonné en saisie manuelle",
         "modeles": ["monitoring.ProductionReading", "monitoring.AbonnementMonitoring"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company, CustomUser
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import AbonnementMonitoring, MonitoringConfig, ProductionReading
    from apps.roles.models import Role
    from apps.roles.permissions_registre import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 006', slug='sonde-amon-006')
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON6', email='amon6@example.invalid')
    inst = Installation.objects.create(company=co, reference='CH-AMON-006', client=cl,
                                       puissance_installee_kwc=Decimal('4'))
    MonitoringConfig.objects.create(company=co, installation=inst, provider='noop', enabled=True,
                                    expected_annual_kwh=Decimal('6000'))
    AbonnementMonitoring.objects.create(company=co, client_id=cl.id, installation_id=inst.id, montant=Decimal('150'),
                                        date_debut=timezone.localdate())
    today = timezone.localdate()
    for i, src in ((30, 'manual'), (20, 'import'), (10, 'import')):
        ProductionReading.objects.create(company=co, installation=inst, date=today - timedelta(days=i),
                                         period_days=1, energy_kwh=Decimal('16'), source=src)
    role, _ = Role.objects.get_or_create(company=co, nom=ROLE_PORTAIL_CLIENT,
                                         defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                                                   'est_systeme': True})
    pu = CustomUser.objects.create_user(username='sonde_amon_006_portail', password='motdepasse-test-1234',
                                        company=co, role=role)
    pu.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    pu.portail_client_id = cl.id
    pu.save()
    api = APIClient()
    api.force_authenticate(pu)
    r = api.get('/api/django/portail/client/ma-consommation/', **H)
    data = r.data if r.status_code == 200 else {}
    obs = {'http': r.status_code, 'points': len(data.get('points') or []),
           'provider_configure': data.get('provider_configure'), 'alertes_ouvertes': data.get('alertes_ouvertes'),
           'detail': None if r.status_code == 200 else str(r.data)[:200]}
    obs['repro'] = bool(r.status_code == 200 and obs['points'] == 3 and obs['provider_configure'] is False)
    return obs
