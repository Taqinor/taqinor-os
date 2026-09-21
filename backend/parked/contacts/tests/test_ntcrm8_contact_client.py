"""NTCRM8 — Modèle Contact multi-rôles par client (organigramme d'achat)."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.contacts.models import ContactClient
from apps.crm.models import Client
from apps.roles.models import Role

User = get_user_model()


class ContactClientModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM8', slug='taqinor-ntcrm8')
        self.client_obj = Client.objects.create(company=self.company, nom='Client Test')

    def test_client_peut_avoir_4_contacts_roles_distincts_un_principal(self):
        roles = [
            ContactClient.RoleAchat.DECIDEUR, ContactClient.RoleAchat.INFLUENCEUR,
            ContactClient.RoleAchat.UTILISATEUR, ContactClient.RoleAchat.GATEKEEPER,
        ]
        for i, role in enumerate(roles):
            ContactClient.objects.create(
                company=self.company, client=self.client_obj, nom=f'Contact {i}',
                role_achat=role, contact_principal=(i == 0))
        self.assertEqual(
            ContactClient.objects.filter(client=self.client_obj).count(), 4)
        principaux = ContactClient.objects.filter(
            client=self.client_obj, contact_principal=True)
        self.assertEqual(principaux.count(), 1)

    def test_second_contact_principal_refuse_proprement(self):
        ContactClient.objects.create(
            company=self.company, client=self.client_obj, nom='Premier',
            contact_principal=True)
        second = ContactClient(
            company=self.company, client=self.client_obj, nom='Second',
            contact_principal=True)
        with self.assertRaises(ValidationError):
            second.save()
        # Le premier reste l'unique principal — rien n'a été altéré.
        self.assertEqual(
            ContactClient.objects.filter(
                client=self.client_obj, contact_principal=True).count(), 1)


class ContactClientApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM8 API', slug='taqinor-ntcrm8-api')
        self.role = Role.objects.create(
            company=self.company, nom='Responsable', permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_ntcrm8', password='x', company=self.company, role=self.role)
        self.client_obj = Client.objects.create(company=self.company, nom='Client API')
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def test_filtre_par_client(self):
        autre_client = Client.objects.create(company=self.company, nom='Autre client')
        ContactClient.objects.create(
            company=self.company, client=self.client_obj, nom='A')
        ContactClient.objects.create(
            company=self.company, client=autre_client, nom='B')
        resp = self.client_api.get(
            '/api/django/contacts/contacts-client/', {'client': self.client_obj.pk})
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['nom'], 'A')

    def test_api_refuse_second_principal_400(self):
        first = self.client_api.post('/api/django/contacts/contacts-client/', {
            'client': self.client_obj.pk, 'nom': 'Premier', 'contact_principal': True,
        })
        self.assertEqual(first.status_code, 201, first.data)
        resp = self.client_api.post('/api/django/contacts/contacts-client/', {
            'client': self.client_obj.pk, 'nom': 'Second', 'contact_principal': True,
        })
        self.assertEqual(resp.status_code, 400)
