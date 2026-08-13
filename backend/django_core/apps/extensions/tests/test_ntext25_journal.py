"""NTEXT25 — journal unifié des exécutions de la plateforme.

``GET extensions/journal/`` agrège, PAR SOCIÉTÉ, les exécutions
d'automatisation, les envois d'abonnement de rapport et les
installations/désinstallations de packages — filtrable par type et par issue.
Aucun nouveau modèle : les journaux existants sont relus.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)
from apps.extensions.models import ExtensionInstall, ExtensionPackage
from apps.reporting.models import RapportAbonnement, RapportDefinition

User = get_user_model()

URL = '/api/django/extensions/journal/'


class JournalPlateformeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT25 Co')
        self.autre = Company.objects.create(nom='NTEXT25 Autre')
        self.user = User.objects.create_user(
            username='ntext25_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        self.regle = AutomationRule.objects.create(
            company=self.company, nom='Relance devis',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL, action_config={})
        AutomationRun.objects.create(
            company=self.company, rule=self.regle,
            status=AutomationRun.Status.SUCCESS, message='Email envoyé.')
        AutomationRun.objects.create(
            company=self.company, rule=self.regle,
            status=AutomationRun.Status.FAILED, message='Canal indisponible.')
        # Journal d'une AUTRE société : ne doit jamais apparaître.
        AutomationRun.objects.create(
            company=self.autre, rule=None,
            status=AutomationRun.Status.SUCCESS, message='Étranger.')

        rapport = RapportDefinition.objects.create(
            company=self.company, titre='Pipeline hebdo', dataset='vitals',
            spec={})
        RapportAbonnement.objects.create(
            company=self.company, rapport_def=rapport, cron='0 8 * * 1',
            destinataires={'emails': ['a@b.c']},
            dernier_statut=RapportAbonnement.Statut.OK,
            dernier_detail={'detail': 'Rapport envoyé.'},
            derniere_execution_le=timezone.now())

        package = ExtensionPackage.objects.create(
            code='ntext25-pkg', nom='Pack test', version='1.0.0')
        ExtensionInstall.objects.create(
            company=self.company, package=package, version='1.0.0',
            statut=ExtensionInstall.Statut.INSTALLE,
            objets_crees=['customfields.customobjectdef:1'])

    def test_journal_aggregates_the_three_sources(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        types = {e['type'] for e in res.data['entrees']}
        self.assertEqual(types, {'automatisation', 'rapport', 'extension'})
        self.assertEqual(res.data['types'],
                         ['automatisation', 'rapport', 'extension'])

    def test_other_company_entries_never_appear(self):
        res = self.api.get(URL)
        messages = [e['message'] for e in res.data['entrees']]
        self.assertNotIn('Étranger.', messages)

    def test_filter_by_type(self):
        res = self.api.get(f'{URL}?type=automatisation')
        self.assertEqual(
            {e['type'] for e in res.data['entrees']}, {'automatisation'})
        self.assertEqual(len(res.data['entrees']), 2)

    def test_filter_by_success(self):
        res = self.api.get(f'{URL}?type=automatisation&succes=0')
        entrees = res.data['entrees']
        self.assertEqual(len(entrees), 1)
        self.assertFalse(entrees[0]['succes'])
        self.assertEqual(entrees[0]['statut'], AutomationRun.Status.FAILED)

    def test_entries_are_most_recent_first(self):
        res = self.api.get(URL)
        horodatages = [e['horodatage'] for e in res.data['entrees']]
        self.assertEqual(horodatages, sorted(horodatages, reverse=True))

    def test_limit_is_bounded(self):
        res = self.api.get(f'{URL}?limite=1')
        self.assertEqual(len(res.data['entrees']), 1)

    def test_limited_role_is_refused(self):
        limite = User.objects.create_user(
            username='ntext25_normal', password='x', role_legacy='normal',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(limite)}')
        self.assertEqual(api.get(URL).status_code, 403)
