"""Group Q — Devis ↔ Toiture 3D pipeline (Q1 layout storage, Q4 roof image,
Q6 tokenized proposal data, Q7 e-signature acceptance).

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_roof_pipeline -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x',
        role_legacy='responsable', company=company)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_devis(company, ref='DEV-ROOF-0001', with_lines=True):
    client = Client.objects.create(
        company=company, nom='Toiti', prenom='Cli',
        email=f'{ref}@ex.com', telephone='+212600000000',
        adresse='Anfa, Casablanca')
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'))
    if with_lines:
        for desig, qty, pu in [
            ('Panneau mono 550W', '12', '1100'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Structures acier', '12', '375'),
        ]:
            p = Produit_create(company, desig, pu)
            LigneDevis.objects.create(
                devis=devis, produit=p, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
    return devis


def Produit_create(company, nom, pu):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, sku=f'{nom[:8]}-{company.pk}',
        prix_vente=Decimal(pu), prix_achat=Decimal('1'), quantite_stock=50)


SAMPLE_LAYOUT = {
    'areas': [{
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'flat',
        'pitch': 10,
        'azimuth': 180,
    }],
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
    'renderPlan': {'cells': 12},
}


class TestQ1Layout(TestCase):
    def setUp(self):
        self.company = make_company('q1-co')
        self.api = auth_client(make_user(self.company, 'q1user'))
        self.devis = make_devis(self.company)

    def test_save_then_load_round_trip(self):
        url = f'/api/django/ventes/devis/{self.devis.id}/layout/'
        resp = self.api.post(url, SAMPLE_LAYOUT, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.roof_layout['result']['kwc'], 6.6)
        got = self.api.get(url)
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.data['roof_layout'], SAMPLE_LAYOUT)

    def test_wrapper_form_accepted(self):
        url = f'/api/django/ventes/devis/{self.devis.id}/layout/'
        resp = self.api.post(url, {'roof_layout': SAMPLE_LAYOUT}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.roof_layout, SAMPLE_LAYOUT)

    def test_status_unchanged(self):
        url = f'/api/django/ventes/devis/{self.devis.id}/layout/'
        self.api.post(url, SAMPLE_LAYOUT, format='json')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')

    def test_cross_tenant_404(self):
        other = make_company('q1-other')
        other_api = auth_client(make_user(other, 'q1other'))
        url = f'/api/django/ventes/devis/{self.devis.id}/layout/'
        self.assertEqual(other_api.post(url, SAMPLE_LAYOUT, format='json')
                         .status_code, 404)
        self.assertEqual(other_api.get(url).status_code, 404)


class TestQ4RoofImage(TestCase):
    def setUp(self):
        self.company = make_company('q4-co')
        self.api = auth_client(make_user(self.company, 'q4user'))
        self.devis = make_devis(self.company, ref='DEV-ROOF-Q4-0001')

    def _post_image(self, api, devis, data=PNG_BYTES):
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        up = SimpleUploadedFile('snap.png', data, content_type='image/png')
        with mock.patch(
            'apps.ventes.quote_engine.builder._ensure_pdf_bucket'
        ), mock.patch(
            'apps.ventes.utils.pdf.upload_roof_image'
        ), mock.patch(
            'apps.ventes.utils.pdf.roof_image_signed_url',
            return_value='https://minio/signed?x=1',
        ):
            return api.post(
                f'/api/django/ventes/devis/{devis.id}/roof-image/',
                {'image': up}, format='multipart')

    def test_upload_sets_key_and_returns_signed_url(self):
        resp = self._post_image(self.api, self.devis)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.roof_image,
            f'roofs/{self.company.id}/{self.devis.reference}.png')
        self.assertIn('url', resp.data)

    def test_reject_non_image(self):
        resp = self._post_image(self.api, self.devis, data=b'not an image')
        self.assertEqual(resp.status_code, 400)

    def test_cross_tenant_404(self):
        other = make_company('q4-other')
        other_api = auth_client(make_user(other, 'q4other'))
        resp = self._post_image(other_api, self.devis)
        self.assertEqual(resp.status_code, 404)

    def test_signed_url_helper_scopes_pdf_bucket(self):
        from apps.ventes.utils import pdf as pdfmod
        captured = {}

        class FakeClient:
            def generate_presigned_url(self, op, Params, ExpiresIn):
                captured.update(Params)
                return 'http://signed'
        with mock.patch.object(pdfmod, 'get_minio_client',
                               return_value=FakeClient()):
            url = pdfmod.roof_image_signed_url('roofs/1/x.png')
        self.assertEqual(url, 'http://signed')
        self.assertEqual(captured['Key'], 'roofs/1/x.png')
