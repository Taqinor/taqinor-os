"""DC32 — le compte portail client se lie à ``crm.Client`` PAR FK et réutilise
l'email du client (pas de 2ᵉ copie d'identité).

Couvre :
  * création via l'API en passant ``client`` (FK) : token posé serveur, email
    lu depuis le client, aucune colonne email dupliquée ;
  * un client d'une autre société est rejeté ;
  * le service de provisionnement idempotent lie par FK sans stocker d'email.

Run :
    python manage.py test apps.compta.tests.test_dc32_compte_portail_fk -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services
from apps.compta.models import ComptePortailClient
from apps.crm.models import Client

User = get_user_model()
BASE = '/api/django/compta'


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


class TestDC32ComptePortailFK(TestCase):
    def setUp(self):
        self.company = make_company('dc32-co', 'DC32 Co')
        self.user = make_user(self.company, 'dc32-user')
        self.api = auth(self.user)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Client Portail',
            email='client@dc32.ma')

    def test_no_stored_email_column(self):
        """DC32 — l'email n'est plus un champ concret (source unique = client)."""
        champs = {f.name for f in ComptePortailClient._meta.get_fields()}
        self.assertIn('client', champs)
        concrets = {
            f.name for f in ComptePortailClient._meta.get_fields()
            if getattr(f, 'concrete', False)}
        self.assertNotIn('email', concrets)

    def test_create_links_client_by_fk_and_reuses_email(self):
        r = self.api.post(f'{BASE}/comptes-portail/',
                          {'client': self.client_crm.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['client'], self.client_crm.id)
        # L'email provient du client (source unique).
        self.assertEqual(r.data['email'], 'client@dc32.ma')
        self.assertTrue(r.data['token_acces'])
        compte = ComptePortailClient.objects.get(id=r.data['id'])
        self.assertEqual(compte.client_id, self.client_crm.id)
        self.assertEqual(compte.email, 'client@dc32.ma')

    def test_email_follows_client_updates(self):
        """Changer l'email du client change celui vu au portail (pas de copie)."""
        compte = ComptePortailClient.objects.create(
            company=self.company, client=self.client_crm, token_acces='tok-a')
        self.client_crm.email = 'nouveau@dc32.ma'
        self.client_crm.save(update_fields=['email'])
        compte.refresh_from_db()
        self.assertEqual(compte.email, 'nouveau@dc32.ma')

    def test_foreign_company_client_rejected(self):
        autre = make_company('dc32-other', 'Autre')
        client_autre = Client.objects.create(
            company=autre, nom='Intrus', email='x@a.ma')
        r = self.api.post(f'{BASE}/comptes-portail/',
                          {'client': client_autre.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('client', r.data)

    def test_provisionner_idempotent_by_client(self):
        c1 = services.provisionner_compte_portail(
            self.company, client_id=self.client_crm.id)
        c2 = services.provisionner_compte_portail(
            self.company, client_id=self.client_crm.id)
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(c1.client_id, self.client_crm.id)
        self.assertEqual(c1.email, 'client@dc32.ma')
