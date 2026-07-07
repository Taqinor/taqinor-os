"""ODX12 — le portail self-service client (FG228–233) est relogé de compta vers
``apps.portail``, tables physiques préservées (``compta_<model>``), nouvelles
routes ``/api/django/portail/…`` + anciennes routes ``/api/django/compta/…``
conservées, scoping société côté serveur, surface AUTH inchangée (token généré
serveur, client lié par FK dans la même société).

Run :
    python manage.py test apps.portail.tests.test_odx12_portail_split -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client

User = get_user_model()


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


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return [x['id'] for x in rows]


class TestODX12Relocation(TestCase):
    def test_models_live_in_portail_with_preserved_db_tables(self):
        from apps.portail.models import (
            ComptePortailClient, AcceptationDevisPortail,
            PaiementFacturePortail, DocumentClientPortail,
            JalonChantierPortail, DemandeTicketPortail)
        from apps.compta.models import (
            ComptePortailClient as ComptaShimCompte)
        # Le shim compta ré-exporte EXACTEMENT la même classe (ODX22 le retirera).
        self.assertIs(ComptePortailClient, ComptaShimCompte)
        expected = {
            ComptePortailClient: 'compta_compteportailclient',
            AcceptationDevisPortail: 'compta_acceptationdevisportail',
            PaiementFacturePortail: 'compta_paiementfactureportail',
            DocumentClientPortail: 'compta_documentclientportail',
            JalonChantierPortail: 'compta_jalonchantierportail',
            DemandeTicketPortail: 'compta_demandeticketportail',
        }
        for model, table in expected.items():
            self.assertEqual(model._meta.db_table, table)
            self.assertEqual(model._meta.app_label, 'portail')


class TestODX12Routes(TestCase):
    def setUp(self):
        self.company = make_company('odx12-co', 'ODX12 Co')
        self.user = make_user(self.company, 'odx12_resp')
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Portail',
            email='portail-odx12@example.invalid')

    def test_new_portail_route_creates_scoped_token_serverside(self):
        r = self.api.post('/api/django/portail/comptes-portail/', {
            'client': self.client_obj.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        from apps.portail.models import ComptePortailClient
        obj = ComptePortailClient.objects.get(id=r.data['id'])
        self.assertEqual(obj.company_id, self.company.id)
        # Token généré côté serveur (surface AUTH inchangée) — jamais du corps.
        self.assertTrue(obj.token_acces)

    def test_new_portail_route_rejects_client_of_other_company(self):
        other = make_company('odx12-other', 'Autre Co')
        other_client = Client.objects.create(
            company=other, nom='Autre', prenom='Client',
            email='autre-odx12@example.invalid')
        r = self.api.post('/api/django/portail/comptes-portail/', {
            'client': other_client.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_legacy_compta_route_still_serves_same_data(self):
        from apps.portail.models import DemandeTicketPortail
        obj = DemandeTicketPortail.objects.create(
            company=self.company, client_id=self.client_obj.id,
            sujet='Onduleur en défaut')
        r = self.api.get('/api/django/compta/demandes-ticket-portail/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(obj.id, ids_of(r))
