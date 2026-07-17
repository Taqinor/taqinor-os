"""NTCRD28 — une demande de dérogation soumise notifie le(s) Directeur(s) avec
les infos nécessaires à la décision."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.credit.models import DerogationCredit
from apps.crm.models import Client
from apps.notifications.models import Notification

User = get_user_model()


def make_company(slug='ntcrd28-co', nom='NTCRD28 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD28DemandeNotifieTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.directeur = User.objects.create_user(
            username='ntcrd28_dir', password='x', role_legacy='admin',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='ntcrd28_com', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd28@example.com')

    def test_derogation_request_notifies_director(self):
        r = auth(self.commercial).post('/api/django/credit/derogations/', {
            'client': self.client_obj.id, 'montant_demande': '5000',
            'motif': 'Client stratégique, commande urgente à honorer.',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(
            DerogationCredit.objects.filter(client=self.client_obj).exists())
        self.assertTrue(
            Notification.objects.filter(recipient=self.directeur).exists())
