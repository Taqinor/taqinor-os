"""AFAC47 (C-AFAC-035) — un paramétrage de relance client est borné à la
société en création ET en modification (PATCH/PUT) ; le beat ne lit que les
paramétrages « manuel » de la société de la facture : un locataire ne coupe
plus les relances d'un autre.

Rejoue les sondes FREC-3 / FEVT-2 / L2-C-AFAC-035 (PATCH/PUT `{client: <cB>,
mode: manuel}` par A ⇒ 200, cron 0 envoi pour B). APIClient + beat réel,
e-mail locmem, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_parametrage_relance_societe"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
URL = '/api/django/ventes/parametrages-relance-client/'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ParametrageRelanceSocieteTests(TestCase):
    def setUp(self):
        from apps.ventes.scheduled import casablanca_today
        self.today = casablanca_today()
        self.a = self._societe()
        self.b = self._societe()
        from apps.ventes.models import Facture
        self.facture_b = Facture.objects.create(
            company=self.b['company'], reference=f'FAC-AFAC47-{_nxt():04d}',
            client=self.b['client'], statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            prochaine_relance=self.today)
        r = self.a['api'].post(URL, {'client': self.a['client'].id,
                                     'mode': 'auto'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.param_a = r.data['id']

    def _societe(self):
        from apps.crm.models import Client
        from authentication.models import Company
        n = _nxt()
        company = Company.objects.create(nom=f'AFAC47 {n}', slug=f'afac47-{n}')
        admin = User.objects.create_user(
            username=f'afac47-admin-{n}', password='x', role_legacy='admin',
            company=company)
        client = Client.objects.create(
            company=company, nom=f'Client {n}', prenom='AFAC47',
            email=f'afac47-{n}@example.invalid')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        return {'company': company, 'admin': admin, 'client': client,
                'api': api}

    def _relire_param_a(self):
        from apps.ventes.models import ParametrageRelanceClient
        return ParametrageRelanceClient.objects.get(pk=self.param_a)

    def test_patch_client_etranger_400(self):
        r = self.a['api'].patch(f'{URL}{self.param_a}/', {
            'client': self.b['client'].id, 'mode': 'manuel'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('client', r.data)
        param = self._relire_param_a()
        self.assertEqual(param.client_id, self.a['client'].id)
        self.assertEqual(param.mode, 'auto')

    def test_put_client_etranger_400(self):
        r = self.a['api'].put(f'{URL}{self.param_a}/', {
            'client': self.b['client'].id, 'mode': 'manuel'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        param = self._relire_param_a()
        self.assertEqual(param.client_id, self.a['client'].id)

    def test_beat_ignore_parametrage_autre_societe(self):
        from apps.ventes.models import ParametrageRelanceClient, RelanceLog
        from apps.ventes.scheduled import relance_reminders
        # Ligne déjà corrompue en base : société A, client de B, « manuel ».
        ParametrageRelanceClient.objects.filter(pk=self.param_a).update(
            client=self.b['client'], mode='manuel')
        relance_reminders()
        self.assertTrue(
            RelanceLog.objects.filter(facture=self.facture_b).exists())
        self.facture_b.refresh_from_db()
        self.assertNotEqual(self.facture_b.prochaine_relance, self.today)

    def test_b_peut_parametrer_son_client(self):
        self.a['api'].patch(f'{URL}{self.param_a}/', {
            'client': self.b['client'].id, 'mode': 'manuel'}, format='json')
        r = self.b['api'].post(URL, {'client': self.b['client'].id,
                                     'mode': 'manuel'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
