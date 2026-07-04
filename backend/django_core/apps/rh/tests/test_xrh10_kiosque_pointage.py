"""Tests XRH10 — Kiosque de pointage partagé (PIN + token de device).

Couvre :
* le RH émet un device kiosque (token en clair renvoyé UNE FOIS) ;
* avec le token de device + PIN, un pointage complet se déroule (arrivée puis
  départ au 2e appel du même jour) ;
* PIN inconnu → 404 neutre ;
* token révoqué / inconnu → 401 ;
* throttling configuré (30/min) ;
* isolation société (PIN d'une autre société invisible au device A).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, Pointage
from apps.rh import services

User = get_user_model()

DEVICES = '/api/django/rh/devices-kiosque/'
KIOSQUE = '/api/django/rh/pointages/kiosque/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class KiosquePointageTests(TestCase):
    def setUp(self):
        self.co_a = make_company('kio-a', 'A')
        self.co_b = make_company('kio-b', 'B')
        self.rh = make_user(self.co_a, 'kio-rh')
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='K001', nom='Alami', prenom='Yasmine',
            code_pointage='1234')

    def _emettre_device(self, user, label='Tablette dépôt'):
        resp = auth(user).post(DEVICES + 'emettre/', {'label': label})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('token', resp.data)
        return resp.data['token'], resp.data['id']

    def test_emission_device_puis_pointage_complet(self):
        token, device_id = self._emettre_device(self.rh)

        client = APIClient()
        client.credentials(HTTP_X_KIOSQUE_TOKEN=token)
        resp = client.post(KIOSQUE, {'pin': '1234'})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['sens'], 'arrivee')
        self.assertEqual(Pointage.objects.filter(employe=self.emp).count(), 1)

        # 2e pointage le même jour → ferme (départ).
        resp = client.post(KIOSQUE, {'pin': '1234'})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['sens'], 'depart')
        self.assertEqual(Pointage.objects.filter(employe=self.emp).count(), 1)
        pointage = Pointage.objects.get(employe=self.emp)
        self.assertIsNotNone(pointage.heure_depart)

    def test_pin_inconnu_404_neutre(self):
        token, _ = self._emettre_device(self.rh)
        client = APIClient()
        client.credentials(HTTP_X_KIOSQUE_TOKEN=token)
        resp = client.post(KIOSQUE, {'pin': '9999'})
        self.assertEqual(resp.status_code, 404)

    def test_token_inconnu_401(self):
        client = APIClient()
        client.credentials(HTTP_X_KIOSQUE_TOKEN='kio_bogus')
        resp = client.post(KIOSQUE, {'pin': '1234'})
        self.assertEqual(resp.status_code, 401)

    def test_token_revoque_401(self):
        token, device_id = self._emettre_device(self.rh)
        resp = auth(self.rh).post(f'{DEVICES}{device_id}/revoquer/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['actif'])

        client = APIClient()
        client.credentials(HTTP_X_KIOSQUE_TOKEN=token)
        resp = client.post(KIOSQUE, {'pin': '1234'})
        self.assertEqual(resp.status_code, 401)

    def test_isolation_societe_pin(self):
        # Un employé de la société B avec le même PIN n'est jamais résolu
        # par un device de la société A.
        DossierEmploye.objects.create(
            company=self.co_b, matricule='K900', nom='Autre', prenom='Emp',
            code_pointage='1234')
        token, _ = self._emettre_device(self.rh)
        client = APIClient()
        client.credentials(HTTP_X_KIOSQUE_TOKEN=token)
        resp = client.post(KIOSQUE, {'pin': '1234'})
        self.assertEqual(resp.status_code, 201)
        # C'est bien l'employé de la société A qui a été pointé.
        self.assertEqual(
            Pointage.objects.filter(company=self.co_a).count(), 1)
        self.assertEqual(
            Pointage.objects.filter(company=self.co_b).count(), 0)

    def test_throttle_configure(self):
        """Le throttle kiosque est bien câblé à 30/min (pas au défaut anon)."""
        from apps.rh.views import _KiosqueThrottle
        self.assertEqual(_KiosqueThrottle().get_rate(), '30/min')

    def test_service_resoudre_device_kiosque_token_vide(self):
        self.assertIsNone(services.resoudre_device_kiosque(''))
        self.assertIsNone(services.resoudre_device_kiosque(None))

    def test_definir_code_pointage_et_doublon_refuse(self):
        emp2 = DossierEmploye.objects.create(
            company=self.co_a, matricule='K002', nom='Bennani', prenom='Sami')
        url = f'/api/django/rh/employes/{emp2.id}/definir-code-pointage/'
        resp = auth(self.rh).post(url, {'code': '5555'})
        self.assertEqual(resp.status_code, 200, resp.data)
        emp2.refresh_from_db()
        self.assertEqual(emp2.code_pointage, '5555')

        # Doublon avec self.emp (PIN 1234) refusé.
        resp = auth(self.rh).post(
            f'/api/django/rh/employes/{self.emp.id}/definir-code-pointage/',
            {'code': '5555'})
        self.assertEqual(resp.status_code, 400)

    def test_pin_jamais_expose_en_liste(self):
        """XRH10 — ``code_pointage`` n'apparaît jamais en liste employés."""
        resp = auth(self.rh).get('/api/django/rh/employes/')
        payload = resp.data
        results = payload['results'] if isinstance(payload, dict) \
            and 'results' in payload else payload
        for row in results:
            self.assertNotIn('code_pointage', row)
