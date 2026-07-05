"""
ZFAC8 — Responsable de relance + mode manuel/automatique par client
(Follow-up responsible & mode).

Un client en mode manuel est ignoré par le cron automatique, le responsable
filtre « mes relances », le mode auto reste le comportement actuel pour tous
les autres clients.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac8_parametrage_relance_client -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, ParametrageRelanceClient, RelanceLog

User = get_user_model()


def make_company(slug='zfac8-co', nom='ZFAC8 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestParametrageRelanceClientCron(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_auto = Client.objects.create(
            company=self.company, nom='Auto', prenom='Client',
            telephone='+212600000006')
        self.client_manuel = Client.objects.create(
            company=self.company, nom='Manuel', prenom='Client',
            telephone='+212600000007')
        ParametrageRelanceClient.objects.create(
            company=self.company, client=self.client_manuel,
            mode=ParametrageRelanceClient.Mode.MANUEL)
        today = timezone.now().date()
        self.facture_auto = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC8-0001',
            client=self.client_auto, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), prochaine_relance=today)
        self.facture_manuel = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC8-0002',
            client=self.client_manuel, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), prochaine_relance=today)

    def test_manual_client_skipped_by_cron(self):
        from apps.ventes.scheduled import relance_reminders
        with mock.patch('apps.ventes.email_service.send_relance_email'):
            relance_reminders()
        self.assertTrue(
            RelanceLog.objects.filter(facture=self.facture_auto).exists())
        self.assertFalse(
            RelanceLog.objects.filter(facture=self.facture_manuel).exists())

    def test_auto_default_unchanged_for_client_without_row(self):
        # Aucune ligne ParametrageRelanceClient pour client_auto → défaut
        # 'auto' → comportement historique (relancé normalement).
        self.assertFalse(
            ParametrageRelanceClient.objects.filter(
                client=self.client_auto).exists())
        from apps.ventes.scheduled import relance_reminders
        with mock.patch('apps.ventes.email_service.send_relance_email'):
            relance_reminders()
        self.assertTrue(
            RelanceLog.objects.filter(facture=self.facture_auto).exists())


class TestParametrageRelanceClientAPI(TestCase):
    def setUp(self):
        from apps.roles.models import RESPONSABLE_PERMISSIONS, Role
        self.company = make_company(slug='zfac8-api-co', nom='ZFAC8 API Co')
        resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.resp = User.objects.create_user(
            username='zfac8_resp', password='x', role=resp_role,
            role_legacy='responsable', company=self.company)
        self.other_resp = User.objects.create_user(
            username='zfac8_resp2', password='x', role=resp_role,
            role_legacy='responsable', company=self.company)
        self.client_a = Client.objects.create(
            company=self.company, nom='A', prenom='Client',
            telephone='+212600000008')
        self.client_b = Client.objects.create(
            company=self.company, nom='B', prenom='Client',
            telephone='+212600000009')
        today = timezone.now().date()
        self.facture_a = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC8API-0001',
            client=self.client_a, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('5000'), date_echeance=today,
            prochaine_relance=today)
        self.facture_b = Facture.objects.create(
            company=self.company, reference='FAC-ZFAC8API-0002',
            client=self.client_b, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('3000'), date_echeance=today,
            prochaine_relance=today)

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_create_parametrage_scoped_to_company(self):
        api = self._api(self.resp)
        resp = api.post(
            '/api/django/ventes/parametrages-relance-client/',
            {'client': self.client_a.id, 'responsable': self.resp.id,
             'mode': 'manuel'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        param = ParametrageRelanceClient.objects.get(client=self.client_a)
        self.assertEqual(param.company_id, self.company.id)

    def test_mes_relances_filters_by_responsable(self):
        ParametrageRelanceClient.objects.create(
            company=self.company, client=self.client_a,
            responsable=self.resp, mode='auto')
        ParametrageRelanceClient.objects.create(
            company=self.company, client=self.client_b,
            responsable=self.other_resp, mode='auto')
        api = self._api(self.resp)
        resp = api.get(
            '/api/django/ventes/relances/?mes_relances=1')
        self.assertEqual(resp.status_code, 200)
        references = {row['reference'] for row in resp.data}
        self.assertIn('FAC-ZFAC8API-0001', references)
        self.assertNotIn('FAC-ZFAC8API-0002', references)
