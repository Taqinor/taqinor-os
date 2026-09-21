"""Garde-fou tenant transverse : aucun sérialiseur du module `apps.sante`
n'accepte une FK (patient/praticien/salle/convention/etc.) appartenant à une
AUTRE société depuis le corps de requête — miroir du helper `_meme_societe`
déjà établi dans `apps/rh`/`apps/qhse`/`apps/compta`/`apps/paie`/
`apps/gestion_projet`.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import Patient, Praticien, Salle

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CrossTenantFkGuardTests(TestCase):
    def setUp(self):
        self.co_a = make_company('sante-tenant-a', 'Clinique A')
        self.co_b = make_company('sante-tenant-b', 'Clinique B')
        self.user_a = make_user(self.co_a, 'sante-tenant-a-user')

    def test_rendezvous_rejects_patient_from_another_company(self):
        patient_b = Patient.objects.create(company=self.co_b, nom='Étranger')
        praticien_a = Praticien.objects.create(company=self.co_a, nom='Dr. A')

        api = auth(self.user_a)
        resp = api.post(
            '/api/django/sante/rendezvous/',
            {
                'patient': patient_b.id,
                'praticien': praticien_a.id,
                'date_heure_debut': dt.datetime(2026, 9, 1, 9, 0).isoformat(),
                'duree_min': 30,
            },
            format='json')

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('patient', resp.data)

    def test_rendezvous_rejects_praticien_from_another_company(self):
        patient_a = Patient.objects.create(company=self.co_a, nom='Local')
        praticien_b = Praticien.objects.create(company=self.co_b, nom='Dr. B')

        api = auth(self.user_a)
        resp = api.post(
            '/api/django/sante/rendezvous/',
            {
                'patient': patient_a.id,
                'praticien': praticien_b.id,
                'date_heure_debut': dt.datetime(2026, 9, 1, 9, 0).isoformat(),
                'duree_min': 30,
            },
            format='json')

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('praticien', resp.data)

    def test_rendezvous_rejects_salle_from_another_company(self):
        patient_a = Patient.objects.create(company=self.co_a, nom='Local')
        praticien_a = Praticien.objects.create(company=self.co_a, nom='Dr. A')
        salle_b = Salle.objects.create(company=self.co_b, nom='Salle B')

        api = auth(self.user_a)
        resp = api.post(
            '/api/django/sante/rendezvous/',
            {
                'patient': patient_a.id,
                'praticien': praticien_a.id,
                'salle': salle_b.id,
                'date_heure_debut': dt.datetime(2026, 9, 1, 9, 0).isoformat(),
                'duree_min': 30,
            },
            format='json')

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('salle', resp.data)

    def test_rendezvous_accepts_same_company_references(self):
        patient_a = Patient.objects.create(company=self.co_a, nom='Local')
        praticien_a = Praticien.objects.create(company=self.co_a, nom='Dr. A')

        api = auth(self.user_a)
        resp = api.post(
            '/api/django/sante/rendezvous/',
            {
                'patient': patient_a.id,
                'praticien': praticien_a.id,
                'date_heure_debut': dt.datetime(2026, 9, 1, 9, 0).isoformat(),
                'duree_min': 30,
            },
            format='json')

        self.assertEqual(resp.status_code, 201, resp.data)

    def test_patient_rejects_client_from_another_company(self):
        from apps.crm.models import Client

        client_b = Client.objects.create(company=self.co_b, nom='Client B')

        api = auth(self.user_a)
        resp = api.post(
            '/api/django/sante/patients/',
            {'nom': 'Test', 'client': client_b.id},
            format='json')

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('client', resp.data)
