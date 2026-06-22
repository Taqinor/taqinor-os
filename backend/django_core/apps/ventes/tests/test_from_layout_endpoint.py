"""B1/B2 — HTTP endpoints around build_devis_from_layout.

POST /api/django/ventes/devis/from-layout/  → builds a brouillon Devis from a
finalised roof layout + mints a public proposal link.
POST /api/django/ventes/devis/<id>/share-link/ → (re)mints a proposal link.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_from_layout_endpoint -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x',
        role_legacy=role, company=company)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def seed_catalogue(company):
    """Minimal seeded catalogue mirroring seed_catalogue naming."""
    def mk(nom, sku, prix):
        return Produit.objects.create(
            company=company, nom=nom, sku=sku,
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)
    mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
    mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)
    mk('Onduleur hybride Deye 5kW Monophasé', f'ONDH-{company.pk}', 17000)
    mk('Batterie Deyness 5 kWh', f'BAT-{company.pk}', 17000)


SAMPLE_LAYOUT = {
    'areas': [{
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'flat',
        'pitch': 10,
        'azimuth': 180,
    }],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
    'renderPlan': {'cells': 12},
}

FROM_LAYOUT_URL = '/api/django/ventes/devis/from-layout/'


class TestFromLayoutEndpoint(TestCase):
    def setUp(self):
        self.company = make_company('b1-co')
        self.user = make_user(self.company, 'b1user')
        self.api = auth_client(self.user)
        seed_catalogue(self.company)

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Layout', prenom='Lead',
            email='layout@ex.com', **extra)

    def test_creates_devis_with_lines_and_proposal_link(self):
        lead = self._lead()
        resp = self.api.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # Response shape.
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['statut'], 'brouillon')
        self.assertTrue(resp.data['reference'].startswith('DEV-'))
        token = resp.data['proposal_token']
        self.assertTrue(token)
        self.assertEqual(resp.data['proposal_path'], f'/proposition/{token}')
        # The Devis is company-scoped with lines off the layout.
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.company_id, self.company.id)
        self.assertEqual(devis.statut, 'brouillon')
        desigs = [li.designation for li in devis.lignes.all()]
        self.assertTrue(any('Panneau' in d for d in desigs))
        self.assertTrue(any('réseau' in d for d in desigs))
        # A ShareLink really exists for that token.
        from apps.ventes.models import ShareLink
        link = ShareLink.objects.get(token=token)
        self.assertEqual(link.devis_id, devis.id)
        self.assertEqual(link.company_id, self.company.id)

    def test_client_only_also_works(self):
        client = Client.objects.create(
            company=self.company, nom='Cli', prenom='Direct',
            email='cli@ex.com')
        resp = self.api.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'client': client.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.client_id, client.id)

    def test_company_forced_server_side_not_from_body(self):
        # A 'company' in the body is ignored — the devis is scoped to the
        # authenticated user's company.
        other = make_company('b1-other-co')
        lead = self._lead()
        resp = self.api.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'lead': lead.id, 'company': other.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.company_id, self.company.id)

    def test_cross_tenant_lead_rejected(self):
        other = make_company('b1-other')
        other_lead = Lead.objects.create(
            company=other, nom='Foreign', email='foreign@ex.com')
        resp = self.api.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'lead': other_lead.id},
            format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_cross_tenant_client_rejected(self):
        other = make_company('b1-other2')
        other_client = Client.objects.create(
            company=other, nom='ForeignCli', email='fcli@ex.com')
        resp = self.api.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'client': other_client.id},
            format='json')
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_missing_lead_and_client_rejected(self):
        resp = self.api.post(
            FROM_LAYOUT_URL, {'layout': SAMPLE_LAYOUT}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_missing_layout_rejected(self):
        lead = self._lead()
        resp = self.api.post(
            FROM_LAYOUT_URL, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_status_is_brouillon_never_changed(self):
        # Rule #4 — from-layout yields a brouillon; nothing flips a status.
        lead = self._lead()
        resp = self.api.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
            format='json')
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_optional_taux_and_remise_applied(self):
        lead = self._lead()
        resp = self.api.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'lead': lead.id,
             'taux_tva': 7, 'remise_globale': 5},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.taux_tva, Decimal('7'))
        self.assertEqual(devis.remise_globale, Decimal('5'))

    def test_requires_auth(self):
        lead = self._lead()
        anon = APIClient()
        resp = anon.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'lead': lead.id},
            format='json')
        self.assertIn(resp.status_code, (401, 403))


class TestShareLinkAction(TestCase):
    def setUp(self):
        self.company = make_company('b2-co')
        self.user = make_user(self.company, 'b2user')
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='Share',
            email='share@ex.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-B2-0001',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20'), remise_globale=Decimal('0'))

    def _url(self, devis_id):
        return f'/api/django/ventes/devis/{devis_id}/share-link/'

    def test_mints_token_and_path(self):
        resp = self.api.post(self._url(self.devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        token = resp.data['token']
        self.assertTrue(token)
        self.assertEqual(resp.data['path'], f'/proposition/{token}')
        from apps.ventes.models import ShareLink
        link = ShareLink.objects.get(token=token)
        self.assertEqual(link.devis_id, self.devis.id)

    def test_reuses_existing_valid_link(self):
        first = self.api.post(self._url(self.devis.id), {}, format='json')
        second = self.api.post(self._url(self.devis.id), {}, format='json')
        self.assertEqual(first.data['token'], second.data['token'])

    def test_cross_tenant_404(self):
        other = make_company('b2-other')
        other_api = auth_client(make_user(other, 'b2other'))
        resp = other_api.post(self._url(self.devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 404)
