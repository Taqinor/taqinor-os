"""
Tests for PDF generation pipeline.

Run with:
    docker exec erp-agentique-django_core-1 \
        python manage.py test apps.ventes.tests.test_pdf -v 2
"""
import base64
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, tag
from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
from apps.parametres.models import CompanyProfile

User = get_user_model()

# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_company():
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug='test-pdf-co', defaults={'nom': 'Test PDF Co'},
    )
    return company


def make_user(company=None):
    company = company or make_company()
    return User.objects.create_user(
        username='test_pdf_user',
        password='testpass',
        role_legacy='responsable',
        company=company,
    )


def make_client():
    return Client.objects.create(
        nom='Dupont',
        prenom='Jean',
        email='jean.dupont@example.com',
        telephone='0600000000',
        adresse='12 rue de la Paix, Paris',
    )


def make_produit():
    return Produit.objects.create(
        nom='Produit Test',
        sku='TEST-001',
        prix_vente=Decimal('100.00'),
        prix_achat=Decimal('60.00'),
        quantite_stock=50,
    )


def make_devis(user, client, produit):
    devis = Devis.objects.create(
        reference='DEV-TEST-0001',
        client=client,
        statut='brouillon',
        taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'),
        created_by=user,
        company=user.company,
    )
    LigneDevis.objects.create(
        devis=devis,
        produit=produit,
        designation='Produit Test',
        quantite=Decimal('2'),
        prix_unitaire=Decimal('100.00'),
        remise=Decimal('0'),
    )
    return devis


def make_facture(user, client, produit):
    facture = Facture.objects.create(
        reference='FAC-TEST-0001',
        client=client,
        statut='emise',
        taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'),
        created_by=user,
        company=user.company,
    )
    LigneFacture.objects.create(
        facture=facture,
        produit=produit,
        designation='Produit Test',
        quantite=Decimal('2'),
        prix_unitaire=Decimal('100.00'),
        remise=Decimal('0'),
    )
    return facture


# ── Unit tests — pdf utils ────────────────────────────────────────────────────

@tag('pdf')  # rendu WeasyPrint — lourd → palier release-verify (exclu par-merge)
class TestPdfRender(TestCase):
    """Test HTML rendering and WeasyPrint conversion in isolation."""

    def setUp(self):
        self.user = make_user()
        self.client_obj = make_client()
        self.produit = make_produit()

    def tearDown(self):
        User.objects.filter(username='test_pdf_user').delete()

    def test_render_html_devis(self):
        """Jinja2 template renders to valid HTML with devis data."""
        from apps.ventes.utils.pdf import _render_html
        devis = make_devis(self.user, self.client_obj, self.produit)
        ctx = {
            'devis': devis,
            'entreprise_nom': 'ACME SAS',
            'entreprise_adresse': '1 rue Test, Paris',
            'entreprise_email': 'contact@acme.fr',
            'entreprise_telephone': '0100000000',
            'entreprise_siret': '12345678901234',
            'entreprise_tva_intra': 'FR12345678901',
            'couleur_principale': '#2563EB',
            'logo_uri': None,
            'signature_uri': None,
            'rib': 'FR76 3000 6000 0112 3456 7890 189',
            'banque': 'BNP Paribas',
        }
        html = _render_html('devis.html', ctx)
        self.assertIn('DEV-TEST-0001', html)
        self.assertIn('Dupont', html)
        self.assertIn('Produit Test', html)
        self.assertIn('ACME SAS', html)
        self.assertIn('200.00', html)   # 2 × 100

    def test_render_html_facture(self):
        """Facture template renders with all sections."""
        from apps.ventes.utils.pdf import _render_html
        facture = make_facture(self.user, self.client_obj, self.produit)
        ctx = {
            'facture': facture,
            'entreprise_nom': 'ACME SAS',
            'entreprise_adresse': '1 rue Test',
            'entreprise_email': '',
            'entreprise_telephone': '',
            'entreprise_siret': '',
            'entreprise_tva_intra': '',
            'couleur_principale': '#059669',
            'logo_uri': None,
            'signature_uri': None,
            'rib': '',
            'banque': '',
        }
        html = _render_html('facture.html', ctx)
        self.assertIn('FAC-TEST-0001', html)
        self.assertIn('Dupont', html)
        self.assertIn('FACTURE', html)

    def test_html_to_pdf_returns_bytes(self):
        """WeasyPrint converts HTML to non-empty PDF bytes."""
        from apps.ventes.utils.pdf import _html_to_pdf
        html = '<html><body><p>Test PDF</p></body></html>'
        pdf_bytes = _html_to_pdf(html)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        # PDF magic bytes
        self.assertTrue(pdf_bytes[:4] == b'%PDF')

    def test_logo_embedded_as_data_uri(self):
        """Logo bytes are correctly encoded to data-URI."""
        from apps.ventes.utils.pdf import _to_data_uri
        fake_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        uri = _to_data_uri(fake_png, 'logos/test.png')
        self.assertTrue(uri.startswith('data:image/png;base64,'))
        # Decode and verify
        b64_part = uri.split(',', 1)[1]
        decoded = base64.b64decode(b64_part)
        self.assertEqual(decoded, fake_png)


# ── Integration tests — full pipeline with mocked MinIO ──────────────────────

class TestGeneratePdfMocked(TestCase):
    """
    Full generate_devis_pdf / generate_facture_pdf pipeline.
    MinIO calls are mocked — tests run without a running MinIO server.
    """

    def setUp(self):
        self.user = make_user()
        self.client_obj = make_client()
        self.produit = make_produit()

    def tearDown(self):
        User.objects.filter(username='test_pdf_user').delete()

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_generate_devis_pdf(self, mock_dl, mock_upload):
        """generate_devis_pdf renders PDF, calls _upload_pdf, saves fichier_pdf."""
        from apps.ventes.utils.pdf import generate_devis_pdf
        devis = make_devis(self.user, self.client_obj, self.produit)

        key = generate_devis_pdf(devis.id)

        # ERR75 — legacy fallback key is now company-scoped (mirrors premium).
        self.assertEqual(key, f'devis/{devis.company_id}/{devis.reference}.pdf')
        mock_upload.assert_called_once()

        # Check upload received real PDF bytes
        pdf_bytes_arg = mock_upload.call_args[0][0]
        self.assertTrue(pdf_bytes_arg[:4] == b'%PDF')

        # fichier_pdf persisted on model
        devis.refresh_from_db()
        self.assertEqual(devis.fichier_pdf, key)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_generate_facture_pdf(self, mock_dl, mock_upload):
        """generate_facture_pdf renders PDF, calls _upload_pdf, saves fichier_pdf."""
        from apps.ventes.utils.pdf import generate_facture_pdf
        facture = make_facture(self.user, self.client_obj, self.produit)

        key = generate_facture_pdf(facture.id)

        self.assertEqual(key, f'factures/{facture.reference}.pdf')
        mock_upload.assert_called_once()
        facture.refresh_from_db()
        self.assertEqual(facture.fichier_pdf, key)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download')
    def test_logo_and_signature_embedded(self, mock_dl, mock_upload):
        """Logo and signature are fetched from MinIO and embedded as data-URI."""
        from apps.ventes.utils.pdf import generate_devis_pdf

        # Minimal valid PNG bytes
        fake_img = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        mock_dl.return_value = fake_img

        profile = CompanyProfile.get(self.user.company)
        profile.logo_key = 'logos/logo.png'
        profile.signature_key = 'signatures/sig.png'
        profile.save()

        devis = make_devis(self.user, self.client_obj, self.produit)

        # Capture the HTML passed to WeasyPrint
        with patch('apps.ventes.utils.pdf._html_to_pdf') as mock_wp:
            mock_wp.return_value = b'%PDF-fake'
            generate_devis_pdf(devis.id)
            html_arg = mock_wp.call_args[0][0]

        self.assertIn('data:image/png;base64,', html_arg)

        # Reset profile
        profile.logo_key = ''
        profile.signature_key = ''
        profile.save()

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_company_context_from_profile(self, mock_dl, mock_upload):
        """Company branding from CompanyProfile appears in rendered HTML."""
        from apps.ventes.utils.pdf import generate_devis_pdf

        profile = CompanyProfile.get(self.user.company)
        profile.nom = 'Super Société SARL'
        profile.adresse = '99 avenue des Tests'
        profile.siret = '98765432100019'
        profile.save()

        devis = make_devis(self.user, self.client_obj, self.produit)

        with patch('apps.ventes.utils.pdf._html_to_pdf') as mock_wp:
            mock_wp.return_value = b'%PDF-fake'
            generate_devis_pdf(devis.id)
            html_arg = mock_wp.call_args[0][0]

        self.assertIn('Super Société SARL', html_arg)
        self.assertIn('99 avenue des Tests', html_arg)
        self.assertIn('98765432100019', html_arg)

        # Reset
        profile.nom = 'Mon Entreprise'
        profile.adresse = ''
        profile.siret = ''
        profile.save()


# ── API endpoint tests ────────────────────────────────────────────────────────

class TestPdfEndpoints(TestCase):
    """Test generer-pdf and telecharger-pdf REST endpoints."""

    def setUp(self):
        self.user = make_user()
        self.client_obj = make_client()
        self.produit = make_produit()
        self.client.force_login(self.user)

    def tearDown(self):
        User.objects.filter(username='test_pdf_user').delete()

    @patch('apps.ventes.tasks.task_generate_devis_pdf')
    def test_generer_pdf_devis_returns_202(self, mock_task):
        """POST generer-pdf triggers Celery task and returns 202."""
        mock_task.delay.return_value = MagicMock(id='fake-task-id')
        devis = make_devis(self.user, self.client_obj, self.produit)

        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        api = APIClient()
        token = str(AccessToken.for_user(self.user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        resp = api.post(f'/api/django/ventes/devis/{devis.id}/generer-pdf/')
        self.assertEqual(resp.status_code, 202)
        self.assertIn('task_id', resp.data)
        # default options = premium 3-page format
        from apps.ventes.quote_engine.builder import DEFAULT_PDF_OPTIONS
        mock_task.delay.assert_called_once_with(devis.id, dict(DEFAULT_PDF_OPTIONS))

    @patch('apps.ventes.tasks.task_generate_devis_pdf')
    def test_generer_pdf_devis_passes_format_options(self, mock_task):
        """The format chosen in the UI reaches the Celery task (whitelisted)."""
        mock_task.delay.return_value = MagicMock(id='fake-task-id')
        devis = make_devis(self.user, self.client_obj, self.produit)

        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        api = APIClient()
        token = str(AccessToken.for_user(self.user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        resp = api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-pdf/',
            {'pdf_mode': 'onepage', 'devis_final': True,
             'payment_mode': 'custom', 'custom_acompte': 15000,
             'not_a_real_option': 'ignored'},
            format='json',
        )
        self.assertEqual(resp.status_code, 202)
        called_options = mock_task.delay.call_args[0][1]
        self.assertEqual(called_options['pdf_mode'], 'onepage')
        self.assertTrue(called_options['devis_final'])
        self.assertEqual(called_options['payment_mode'], 'custom')
        self.assertEqual(called_options['custom_acompte'], 15000.0)
        self.assertNotIn('not_a_real_option', called_options)

    @patch('apps.ventes.tasks.task_generate_facture_pdf')
    def test_generer_pdf_facture_returns_202(self, mock_task):
        """POST generer-pdf on facture triggers task and returns 202."""
        mock_task.delay.return_value = MagicMock(id='fake-task-id')
        facture = make_facture(self.user, self.client_obj, self.produit)

        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        api = APIClient()
        token = str(AccessToken.for_user(self.user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        resp = api.post(f'/api/django/ventes/factures/{facture.id}/generer-pdf/')
        self.assertEqual(resp.status_code, 202)
        mock_task.delay.assert_called_once_with(facture.id)

    def test_telecharger_pdf_404_when_not_generated(self):
        """GET telecharger-pdf returns 404 when fichier_pdf is empty."""
        devis = make_devis(self.user, self.client_obj, self.produit)

        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        api = APIClient()
        token = str(AccessToken.for_user(self.user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        resp = api.get(f'/api/django/ventes/devis/{devis.id}/telecharger-pdf/')
        self.assertEqual(resp.status_code, 404)

    @patch('apps.ventes.utils.pdf.download_pdf', return_value=b'%PDF-1.4 fake')
    def test_telecharger_pdf_streams_bytes(self, mock_dl):
        """GET telecharger-pdf returns PDF bytes when fichier_pdf is set."""
        devis = make_devis(self.user, self.client_obj, self.produit)
        devis.fichier_pdf = 'devis/DEV-TEST-0001.pdf'
        devis.save(update_fields=['fichier_pdf'])

        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        api = APIClient()
        token = str(AccessToken.for_user(self.user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        resp = api.get(f'/api/django/ventes/devis/{devis.id}/telecharger-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('DEV-TEST-0001.pdf', resp['Content-Disposition'])


# ── CompanyProfile singleton ──────────────────────────────────────────────────

class TestCompanyProfile(TestCase):

    def test_get_creates_singleton(self):
        """CompanyProfile.get() always returns pk=1."""
        CompanyProfile.objects.filter(pk=1).delete()
        p1 = CompanyProfile.get()
        p2 = CompanyProfile.get()
        self.assertEqual(p1.pk, p2.pk)
        self.assertEqual(CompanyProfile.objects.count(), 1)

    def test_defaults(self):
        CompanyProfile.objects.filter(pk=1).delete()
        p = CompanyProfile.get()
        self.assertEqual(p.couleur_principale, '#2563EB')
        self.assertEqual(p.logo_key, '')
        self.assertEqual(p.signature_key, '')
