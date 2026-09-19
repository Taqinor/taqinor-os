"""NTPRT15 — "Ma consommation" (monitoring, portail CLIENT).

Couvre :

* SANS provider configuré (aucune installation/config/relevé) : l'endpoint
  renvoie 200 avec un état VIDE explicite (``points=[]``,
  ``provider_configure=False``) — JAMAIS une erreur 500 (critère
  d'acceptation) ;
* la série de production agrège les relevés (``ProductionReading``) des
  systèmes du client, scopée société+client (jamais ceux d'un autre client
  ni d'une autre société) ;
* les drapeaux de sous-performance OUVERTS (``UnderperformanceFlag``) sont
  comptés, en LECTURE SEULE — aucun endpoint d'écriture n'est exposé ici ;
* ``provider_configure`` reflète une supervision AUTOMATIQUE réellement
  active (``MonitoringConfig.enabled`` + provider non-``noop``).

Run :
    python manage.py test apps.portail.tests.test_ntprt15_ma_consommation -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import (
    MonitoringConfig, ProductionReading, UnderperformanceFlag,
)
from apps.roles.models import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT, Role
from authentication.models import Company, CustomUser

URL = '/api/django/portail/client/ma-consommation/'
_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT15-{n}',
        email=f'ntprt15-{company.id}-{n}@example.invalid')


def make_portal_user(company, username, client_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = client_id
    user.save()
    return user


class SansProviderEtatVideTests(TestCase):
    """Le critère d'acceptation : jamais de 500, un état vide explicite."""

    def setUp(self):
        self.company = make_company('ntprt15-vide-a', 'NTPRT15 Vide A')
        self.client_crm = make_client_crm(self.company)
        self.user = make_portal_user(
            self.company, 'ntprt15-vide-user', self.client_crm.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_aucune_installation_renvoie_un_etat_vide(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['points'], [])
        self.assertFalse(res.data['provider_configure'])
        self.assertEqual(res.data['alertes_ouvertes'], 0)

    def test_installation_sans_config_ni_releve_renvoie_un_etat_vide(self):
        Installation.objects.create(
            company=self.company, client=self.client_crm,
            reference=f'CH-NTPRT15-{next(_seq)}')
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['points'], [])
        self.assertFalse(res.data['provider_configure'])


class ProductionSeriesTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt15-serie-a', 'NTPRT15 Série A')
        self.client_crm = make_client_crm(self.company)
        self.installation = Installation.objects.create(
            company=self.company, client=self.client_crm,
            reference=f'CH-NTPRT15-{next(_seq)}')
        self.user = make_portal_user(
            self.company, 'ntprt15-serie-user', self.client_crm.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_agrege_la_production_du_client(self):
        today = timezone.localdate()
        ProductionReading.objects.create(
            company=self.company, installation=self.installation,
            date=today, energy_kwh=Decimal('12.50'))
        ProductionReading.objects.create(
            company=self.company, installation=self.installation,
            date=today, energy_kwh=Decimal('2.50'))
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data['points']), 1)
        self.assertEqual(res.data['points'][0]['date'], today.isoformat())
        self.assertEqual(
            Decimal(str(res.data['points'][0]['energy_kwh'])),
            Decimal('15.00'))

    def test_isolation_autre_client_ne_fuit_pas(self):
        autre_client = make_client_crm(self.company)
        autre_installation = Installation.objects.create(
            company=self.company, client=autre_client,
            reference=f'CH-NTPRT15-{next(_seq)}')
        ProductionReading.objects.create(
            company=self.company, installation=autre_installation,
            date=timezone.localdate(), energy_kwh=Decimal('999'))
        res = self.api.get(URL)
        self.assertEqual(res.data['points'], [])

    def test_isolation_autre_societe_ne_fuit_pas(self):
        autre = make_company('ntprt15-serie-b', 'NTPRT15 Série B')
        autre_client = make_client_crm(autre)
        autre_installation = Installation.objects.create(
            company=autre, client=autre_client,
            reference=f'CH-NTPRT15-{next(_seq)}')
        ProductionReading.objects.create(
            company=autre, installation=autre_installation,
            date=timezone.localdate(), energy_kwh=Decimal('999'))
        res = self.api.get(URL)
        self.assertEqual(res.data['points'], [])

    def test_provider_configure_reflete_une_supervision_active(self):
        res = self.api.get(URL)
        self.assertFalse(res.data['provider_configure'])

        MonitoringConfig.objects.create(
            company=self.company, installation=self.installation,
            provider='fusionsolar', enabled=True,
            credentials={'station_id': 'x'})
        res = self.api.get(URL)
        self.assertTrue(res.data['provider_configure'])

    def test_provider_noop_ne_compte_pas_comme_configure(self):
        MonitoringConfig.objects.create(
            company=self.company, installation=self.installation,
            provider='noop', enabled=True)
        res = self.api.get(URL)
        self.assertFalse(res.data['provider_configure'])


class AlertesSousPerformanceTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt15-alerte-a', 'NTPRT15 Alerte A')
        self.client_crm = make_client_crm(self.company)
        self.installation = Installation.objects.create(
            company=self.company, client=self.client_crm,
            reference=f'CH-NTPRT15-{next(_seq)}')
        self.user = make_portal_user(
            self.company, 'ntprt15-alerte-user', self.client_crm.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_compte_les_drapeaux_ouverts(self):
        UnderperformanceFlag.objects.create(
            company=self.company, installation=self.installation,
            ratio_pct=Decimal('62.50'), is_open=True)
        res = self.api.get(URL)
        self.assertEqual(res.data['alertes_ouvertes'], 1)

    def test_ignore_les_drapeaux_fermes(self):
        UnderperformanceFlag.objects.create(
            company=self.company, installation=self.installation,
            ratio_pct=Decimal('62.50'), is_open=False,
            date_cloture=timezone.now())
        res = self.api.get(URL)
        self.assertEqual(res.data['alertes_ouvertes'], 0)
