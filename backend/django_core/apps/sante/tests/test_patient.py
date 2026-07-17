"""NTSAN3 — Modèle `Patient` : scope tenant + numérotation sans collision,
résolution du client CRM lié.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import Patient
from apps.sante.services import (
    attribuer_numero_dossier, resoudre_client_pour_patient)

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


class PatientNumberingTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-pat-co', 'Clinique Patient')

    def test_numero_dossier_no_collision_on_delete(self):
        """Le plus-haut-utilisé+1 (jamais count()+1) : supprimer un dossier
        ne fait jamais réutiliser un numéro déjà attribué."""
        p1 = Patient.objects.create(company=self.company, nom='Alami')
        attribuer_numero_dossier(p1)
        p2 = Patient.objects.create(company=self.company, nom='Bennani')
        attribuer_numero_dossier(p2)
        self.assertNotEqual(p1.numero_dossier, p2.numero_dossier)

        p1_dossier = p1.numero_dossier
        p1.delete()

        p3 = Patient.objects.create(company=self.company, nom='Chraibi')
        attribuer_numero_dossier(p3)
        self.assertNotIn(p3.numero_dossier, {p1_dossier, p2.numero_dossier})
        self.assertNotEqual(p3.numero_dossier, p2.numero_dossier)

    def test_scope_tenant(self):
        other = make_company('sante-pat-co-b', 'Clinique B')
        Patient.objects.create(company=self.company, nom='Alami')
        Patient.objects.create(company=other, nom='Autre')
        self.assertEqual(Patient.objects.filter(company=self.company).count(), 1)


class PatientClientResolutionTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-pat-client-co', 'Clinique Client')

    def test_resolve_reuses_existing_client_by_email(self):
        from apps.crm.models import Client

        existing = Client.objects.create(
            company=self.company, nom='Alami', email='alami@example.com')
        patient = Patient.objects.create(
            company=self.company, nom='Alami', email='alami@example.com')

        client = resoudre_client_pour_patient(patient)

        self.assertEqual(client.id, existing.id)
        patient.refresh_from_db()
        self.assertEqual(patient.client_id, existing.id)

    def test_resolve_creates_client_when_none_found(self):
        patient = Patient.objects.create(
            company=self.company, nom='Bennani', email='bennani@example.com')

        client = resoudre_client_pour_patient(patient)

        self.assertIsNotNone(client)
        self.assertEqual(client.company_id, self.company.id)
        patient.refresh_from_db()
        self.assertEqual(patient.client_id, client.id)

    def test_resolve_reuses_already_linked_client_without_lookup(self):
        from apps.crm.models import Client

        linked = Client.objects.create(company=self.company, nom='Chraibi')
        patient = Patient.objects.create(
            company=self.company, nom='Chraibi', client=linked)

        client = resoudre_client_pour_patient(patient)

        self.assertEqual(client.id, linked.id)


class PatientApiTests(TestCase):
    BASE = '/api/django/sante/patients/'

    def setUp(self):
        self.company = make_company('sante-pat-api-co', 'Clinique API')
        self.user = make_user(self.company, 'sante-pat-api')

    def test_create_assigns_numero_dossier_server_side(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {'nom': 'Idrissi'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Patient.objects.get(id=resp.data['id'])
        self.assertTrue(obj.numero_dossier)
        self.assertEqual(obj.company, self.company)
