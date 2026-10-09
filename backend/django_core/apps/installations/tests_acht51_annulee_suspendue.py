"""ACHT51 (C-ACHT-050/051) — annuler un chantier coupe toute communication
client : une intervention annulée n'est ni rappelée (J-1), ni évaluée
(météo), ni servie par le lien public « en route », ni proposée par
`lien-client`/`ma-tournee` ; les beats ne balayent pas une société
suspendue.

Rejoue CTEN-2/CTEN-3. Seul `weather.fetch_forecast` (API externe) est
remplacé.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht51_annulee_suspendue"
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations import tasks
from apps.installations.models import Installation, Intervention
from apps.crm.models import Client

User = get_user_model()
BASE = '/api/django/installations/interventions'


class AnnuleeSuspendueTests(TestCase):
    def setUp(self):
        self.demain = tasks.casablanca_today() + datetime.timedelta(days=1)
        self.j3 = tasks.casablanca_today() + datetime.timedelta(days=3)
        self.co, _ = Company.objects.get_or_create(
            slug='co-acht51', defaults={'nom': 'Co ACHT51'})
        self.co_susp, _ = Company.objects.get_or_create(
            slug='co-acht51-susp', defaults={'nom': 'Co ACHT51 suspendue'})
        Company.objects.filter(pk=self.co_susp.pk).update(actif=False)
        self.user = User.objects.create_user(
            username='resp-acht51', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.a = self._iv(self.co, 'A', annulee=True)
        self.d = self._iv(self.co, 'D', annulee=False)
        self.b = self._iv(self.co_susp, 'B', annulee=False)

    def _iv(self, company, tag, annulee):
        client = Client.objects.create(
            company=company, nom='Client', prenom=tag,
            email=f'acht51-{tag}@example.invalid')
        inst = Installation.objects.create(
            company=company, reference=f'CH-ACHT51-{tag}', client=client,
            gps_lat=33.5, gps_lng=-7.6)
        iv = Intervention.objects.create(
            company=company, installation=inst, type_intervention='pose',
            technicien=self.user if company == self.co else None,
            date_prevue=self.demain, annulee=annulee)
        # Jumelle « pose » à J+3 pour la météo.
        Intervention.objects.create(
            company=company, installation=inst, type_intervention='pose',
            date_prevue=self.j3, annulee=annulee)
        return iv

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.'
                                     'EmailBackend')
    def test_rappel_ni_annulee_ni_suspendue(self):
        mail.outbox.clear()
        res = tasks.rappel_rdv_j1()
        destinataires = [m.to[0] for m in mail.outbox]
        self.assertNotIn('acht51-A@example.invalid', destinataires)
        self.assertNotIn('acht51-B@example.invalid', destinataires)
        self.assertIn('acht51-D@example.invalid', destinataires)
        self.assertEqual(res['cibles'], 1)

    def test_meteo_ni_annulee_ni_suspendue(self):
        appels = []

        def faux(lat, lng, jour):
            appels.append(jour)
            return {'precipitation_mm': 50.0, 'windgusts_kmh': 90.0}

        with mock.patch('apps.installations.weather.fetch_forecast', faux):
            res = tasks.meteo_planning_j3()
        self.assertEqual(res['cibles'], 1)       # seule D (active, société active)
        self.assertEqual(len(appels), 1)
        for iv in Intervention.objects.filter(
                installation__reference__in=['CH-ACHT51-A', 'CH-ACHT51-B']):
            self.assertIsNone(iv.meteo_risque)

    def test_page_publique_et_lien_client(self):
        self.d.ensure_lien_client_token()
        self.a.ensure_lien_client_token()
        url = '/api/django/public/installations/intervention/{}/'
        r = self.client.get(url.format(self.a.lien_client_token))
        self.assertEqual(r.status_code, 404)
        r = self.client.get(url.format(self.d.lien_client_token))
        self.assertEqual(r.status_code, 200)
        r = self.api.get(f'{BASE}/{self.a.id}/lien-client/')
        self.assertEqual(r.status_code, 409, r.data)
        r = self.api.get(f'{BASE}/{self.d.id}/lien-client/')
        self.assertEqual(r.status_code, 200)

    def test_ma_tournee_sans_annulee(self):
        r = self.api.get(f'{BASE}/ma-tournee/', {'date': str(self.demain)})
        self.assertEqual(r.status_code, 200, r.data)
        ids = [s['id'] for s in r.data['stops']]
        self.assertNotIn(self.a.id, ids)
        self.assertIn(self.d.id, ids)
