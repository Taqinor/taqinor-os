"""WIR91 — Rattacher `education.Famille` à `crm.Client` (jamais dupliquer
les coordonnées).

`Famille` (téléphones/emails x2 parents/adresse) était un doublon
indépendant de `crm.Client`. `services.resoudre_client_pour_famille` suit le
pattern `crm.services.resolve_client_for_lead` /
`sante.resoudre_client_pour_patient` (lien existant, sinon email
société-scopée, sinon création) et est appelé à la création via
`FamilleViewSet.perform_create` (même patron que `sante.PatientViewSet`,
WIR54).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.education.models import Famille
from apps.education.services import resoudre_client_pour_famille

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


class FamilleClientResolutionTests(TestCase):
    def setUp(self):
        self.company = make_company('edu-fam-client-co', 'École Client')

    def test_resolve_reuses_existing_client_by_email(self):
        from apps.crm.models import Client

        existing = Client.objects.create(
            company=self.company, nom='Alami', email='alami@example.com')
        famille = Famille.objects.create(
            company=self.company, nom='Alami', parent1_email='alami@example.com')

        client = resoudre_client_pour_famille(famille)

        self.assertEqual(client.id, existing.id)
        famille.refresh_from_db()
        self.assertEqual(famille.client_id, existing.id)

    def test_resolve_creates_client_when_none_found(self):
        famille = Famille.objects.create(
            company=self.company, nom='Bennani', parent1_email='bennani@example.com',
            parent1_telephone='0600000000')

        client = resoudre_client_pour_famille(famille)

        self.assertIsNotNone(client)
        self.assertEqual(client.company_id, self.company.id)
        self.assertEqual(client.email, 'bennani@example.com')
        famille.refresh_from_db()
        self.assertEqual(famille.client_id, client.id)

    def test_resolve_reuses_already_linked_client_without_lookup(self):
        from apps.crm.models import Client

        linked = Client.objects.create(company=self.company, nom='Chraibi')
        famille = Famille.objects.create(
            company=self.company, nom='Chraibi', client=linked)

        client = resoudre_client_pour_famille(famille)

        self.assertEqual(client.id, linked.id)

    def test_resolve_never_crosses_tenant_on_email_match(self):
        """Un email identique dans une AUTRE société ne doit jamais être
        réutilisé — un nouveau client est créé, scopé à la bonne société."""
        from apps.crm.models import Client

        other = make_company('edu-fam-client-co-b', 'École B')
        foreign = Client.objects.create(
            company=other, nom='Idrissi', email='idrissi@example.com')
        famille = Famille.objects.create(
            company=self.company, nom='Idrissi', parent1_email='idrissi@example.com')

        client = resoudre_client_pour_famille(famille)

        self.assertNotEqual(client.id, foreign.id)
        self.assertEqual(client.company_id, self.company.id)

    def test_famille_sans_email_cree_un_client_sans_lookup(self):
        """Une famille sans email de parent 1 ne lève jamais — crée
        directement un client (pas de recherche possible)."""
        famille = Famille.objects.create(company=self.company, nom='Saidi')

        client = resoudre_client_pour_famille(famille)

        self.assertIsNotNone(client)
        self.assertEqual(client.nom, 'Saidi')


class FamilleApiTests(TestCase):
    BASE = '/api/django/education/familles/'

    def setUp(self):
        self.company = make_company('edu-fam-api-co', 'École API')
        self.user = make_user(self.company, 'edu-fam-api')

    def test_create_resolves_and_creates_crm_client_server_side(self):
        """WIR91 — `FamilleViewSet.perform_create` appelle désormais
        `resoudre_client_pour_famille` : une famille créée sans client CRM
        connu en obtient automatiquement un (jamais un doublon non
        rattaché)."""
        from apps.crm.models import Client

        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {'nom': 'Fassi', 'parent1_email': 'fassi-famille@example.com'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Famille.objects.get(id=resp.data['id'])
        self.assertIsNotNone(obj.client_id)
        client = Client.objects.get(id=obj.client_id)
        self.assertEqual(client.company_id, self.company.id)
        self.assertEqual(client.email, 'fassi-famille@example.com')

    def test_create_reuses_existing_crm_client_by_email(self):
        """Même société + même email de parent 1 déjà connu en CRM =>
        réutilisation du client existant, jamais un doublon."""
        from apps.crm.models import Client

        existing = Client.objects.create(
            company=self.company, nom='Idrissi', email='idrissi-famille@example.com')

        api = auth(self.user)
        resp = api.post(
            self.BASE,
            {'nom': 'Idrissi', 'parent1_email': 'idrissi-famille@example.com'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Famille.objects.get(id=resp.data['id'])
        self.assertEqual(obj.client_id, existing.id)

    def test_client_field_is_read_only_from_request_body(self):
        """`client` n'est jamais accepté du corps de requête : posé UNIQUEMENT
        par `resoudre_client_pour_famille` côté serveur."""
        from apps.crm.models import Client

        rogue = Client.objects.create(company=self.company, nom='Autre client')

        api = auth(self.user)
        resp = api.post(
            self.BASE, {'nom': 'Cherkaoui', 'client': rogue.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Famille.objects.get(id=resp.data['id'])
        # Résolu par le service (création, aucun email fourni) — jamais la
        # valeur "rogue" envoyée dans le corps.
        self.assertNotEqual(obj.client_id, rogue.id)

    def test_response_exposes_client_id(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {'nom': 'Tazi'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('client', resp.data)
        self.assertIsNotNone(resp.data['client'])
