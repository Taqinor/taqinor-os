"""L-NIV chantier 4 — filigrane PDF DISCRET (niveau standard uniquement).

Founder rule: the internal commercial PDF must NEVER carry the watermark;
only the PUBLIC share-link PDF, and only when the link's niveau is
'standard'. Page counts must stay byte-identical (WeasyPrint page-count
guards — see test_quote_engine_formats.py, the sibling this file mirrors).

Two concerns covered:
  (a) storage — the watermarked render is stored under a SEPARATE MinIO
      key (``__pub-standard`` suffix) and never touches ``devis.fichier_pdf``
      (the key the internal "Télécharger" button reads without regenerating).
  (b) rendering — the watermark text appears in the footer HTML when set,
      the page count is unchanged, and it's absent by default.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_l_niv_pdf_watermark -v 2
"""
import uuid
from unittest.mock import patch

from django.test import Client as DjangoClient, TestCase, tag

from apps.ventes.models import ShareLink
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

FULL_LINES = [
    ('Onduleur réseau 10kW', '1', '11700'),
    ('Onduleur hybride 5kW', '1', '24000'),
    ('Panneau mono 550W', '14', '1100'),
    ('Batterie 5 kWh', '1', '14000'),
    ('Structures acier', '14', '375'),
    ('Socles', '30', '67'),
    ('Accessoires', '1', '1667'),
    ('Tableau De Protection AC/DC', '1', '1667'),
    ('Installation', '1', '4000'),
    ('Transport', '1', '1000'),
]


# ═══════════════════════════════════════════════════════════════════════════
# (a) Storage — separate MinIO key, internal fichier_pdf never overwritten
# ═══════════════════════════════════════════════════════════════════════════

class TestWatermarkStorageKey(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, FULL_LINES,
            etude_params=DEUX_OPTIONS)

    @patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket')
    @patch('apps.ventes.utils.pdf._upload_pdf')
    def test_watermarked_render_uses_a_separate_key(self, mock_upload, mock_bucket):
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        key = generate_premium_devis_pdf(
            self.devis.id, {'watermark': True}, persist=False)
        self.assertEqual(
            key, f'devis/{self.company.id}/{self.devis.reference}__pub-standard.pdf')

    @patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket')
    @patch('apps.ventes.utils.pdf._upload_pdf')
    def test_watermarked_render_never_touches_fichier_pdf(self, mock_upload, mock_bucket):
        """Even if a caller passed persist=True by mistake, the watermarked
        variant must never become the persisted internal key."""
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        generate_premium_devis_pdf(
            self.devis.id, {'watermark': True}, persist=True)
        self.devis.refresh_from_db()
        self.assertFalse(
            (self.devis.fichier_pdf or '').endswith('__pub-standard.pdf'))

    @patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket')
    @patch('apps.ventes.utils.pdf._upload_pdf')
    def test_internal_generation_unaffected_no_suffix(self, mock_upload, mock_bucket):
        """Pinned pre-L-NIV behaviour: no watermark option -> canonical key,
        persisted on the model exactly as before."""
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        key = generate_premium_devis_pdf(self.devis.id)
        self.assertEqual(key, f'devis/{self.company.id}/{self.devis.reference}.pdf')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.fichier_pdf, key)


# ═══════════════════════════════════════════════════════════════════════════
# (b) Rendering — footer text + page count (requires WeasyPrint — heavy)
# ═══════════════════════════════════════════════════════════════════════════

@tag('pdf')  # rendu PDF premium complet — lourd → palier release-verify
class TestWatermarkRendering(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, FULL_LINES,
            etude_params=DEUX_OPTIONS)

    def _render_html(self, watermark_text=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = build_quote_data(self.devis, None)
        if watermark_text is not None:
            data['_watermark_standard'] = watermark_text
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_lniv_watermark_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html']

    def test_no_watermark_by_default(self):
        html = self._render_html(watermark_text=None)
        self.assertNotIn('__pub-standard', html)

    def test_watermark_text_appears_in_footer(self):
        html = self._render_html(watermark_text='M. Karim Alaoui · +212 6 00 00 00 00')
        self.assertIn('M. Karim Alaoui', html)
        self.assertIn('+212 6 00 00 00 00', html)

    def test_watermark_does_not_change_page_count(self):
        """WeasyPrint page-count guard — extended to run WITH watermark on
        (founder requirement: ZERO pagination change)."""
        from weasyprint import HTML
        html_off = self._render_html(watermark_text=None)
        html_on = self._render_html(
            watermark_text='Mme Fatima Zahra Bennani · +212 6 61 11 22 33')
        pages_off = len(HTML(string=html_off).render().pages)
        pages_on = len(HTML(string=html_on).render().pages)
        self.assertEqual(pages_off, 3)
        self.assertEqual(
            pages_on, pages_off,
            'the watermark suffix must never change the page count')


# ═══════════════════════════════════════════════════════════════════════════
# (c) public_views.proposal_pdf wiring — watermark flag posé UNIQUEMENT au
# niveau standard, jamais lu depuis le corps de requête (mocked, léger)
# ═══════════════════════════════════════════════════════════════════════════

class TestProposalPdfWatermarkWiring(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, FULL_LINES,
            etude_params=DEUX_OPTIONS)

    def _link(self, niveau):
        token = str(uuid.uuid4())
        return ShareLink.objects.create(
            company=self.company, devis=self.devis, token=token, niveau=niveau)

    @patch('apps.ventes.public_views.download_pdf', return_value=b'%PDF-fake')
    @patch('apps.ventes.public_views.generate_premium_devis_pdf', return_value='k')
    def test_standard_link_requests_watermark(self, mock_gen, mock_dl):
        link = self._link(ShareLink.NIVEAU_STANDARD)
        resp = DjangoClient().get(f'/api/django/public/proposal/{link.token}/pdf/')
        self.assertEqual(resp.status_code, 200)
        opts_arg = mock_gen.call_args[0][1]
        self.assertTrue(opts_arg.get('watermark'))

    @patch('apps.ventes.public_views.download_pdf', return_value=b'%PDF-fake')
    @patch('apps.ventes.public_views.generate_premium_devis_pdf', return_value='k')
    def test_confiance_link_never_requests_watermark(self, mock_gen, mock_dl):
        link = self._link(ShareLink.NIVEAU_CONFIANCE)
        resp = DjangoClient().get(f'/api/django/public/proposal/{link.token}/pdf/')
        self.assertEqual(resp.status_code, 200)
        opts_arg = mock_gen.call_args[0][1]
        self.assertFalse(opts_arg.get('watermark'))
