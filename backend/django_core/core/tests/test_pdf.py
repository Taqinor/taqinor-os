"""Tests ARC11 — service de rendu PDF PARTAGÉ ``core.pdf`` (hors devis).

Couvre la plomberie centralisée (WeasyPrint mocké via ``sys.modules``, même
patron que ``apps.qhse.tests.test_xqhs27`` — rapide, sans la lib native) :

* ``render_pdf(html=...)`` rend des octets PDF à partir d'un HTML final ;
* ``render_pdf(template=..., context=...)`` rend depuis un gabarit Django ;
* garde-fous d'API : ni html ni template → ``ValueError`` ; les deux → erreur ;
* branding OPT-IN : header/footer désactivés par défaut (HTML inchangé), activés
  ils injectent un bandeau depuis ``CompanyProfile`` (résolution paresseuse —
  ``core`` n'importe jamais ``apps.parametres``) ; sans société → pas de bandeau ;
* upload MinIO optionnel : ``upload_to`` → tuple ``(bytes, key)``, client mocké ;
* WeasyPrint absent → ``RuntimeError`` explicite (contrat des pilotes).

Un test de rendu RÉEL (WeasyPrint natif) est étiqueté ``pdf`` (palier lourd)."""
import sys
import types
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, tag

from authentication.models import Company
from core import pdf


def _fake_weasyprint(captured=None):
    """Faux module ``weasyprint`` : ``HTML(string=...).write_pdf(buf)`` écrit un
    PDF factice ; ``captured`` (liste) reçoit le string passé pour assertion."""
    fake_module = types.ModuleType('weasyprint')

    class _FakeHTML:
        def __init__(self, string=None):
            if captured is not None:
                captured.append(string)

        def write_pdf(self, target=None):
            data = b'%PDF-1.4 fake render'
            if target is not None:
                target.write(data)
                return None
            return data

    fake_module.HTML = _FakeHTML
    return fake_module


class RenderPdfPlumbingTests(SimpleTestCase):
    def test_render_from_html_returns_bytes(self):
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}):
            out = pdf.render_pdf(html='<html><body>Bonjour</body></html>')
        self.assertIsInstance(out, bytes)
        self.assertTrue(out.startswith(b'%PDF-'))

    def test_render_from_template(self):
        captured = []
        # Gabarit Django minimal via un loader en mémoire.
        rendered = '<html><body>Rendu template</body></html>'
        with patch('django.template.loader.render_to_string',
                   return_value=rendered), \
                patch.dict(sys.modules,
                           {'weasyprint': _fake_weasyprint(captured)}):
            out = pdf.render_pdf(template='x.html', context={'a': 1})
        self.assertTrue(out.startswith(b'%PDF-'))
        self.assertEqual(captured[0], rendered)

    def test_requires_html_or_template(self):
        with self.assertRaises(ValueError):
            pdf.render_pdf()

    def test_rejects_both_html_and_template(self):
        with self.assertRaises(ValueError):
            pdf.render_pdf(html='<p>x</p>', template='x.html')

    def test_missing_weasyprint_raises_runtimeerror(self):
        # Simule l'absence de la lib : import weasyprint lève ImportError.
        import builtins
        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == 'weasyprint':
                raise ImportError('pas de weasyprint')
            return real_import(name, *args, **kwargs)

        with patch.dict(sys.modules, {}, clear=False):
            sys.modules.pop('weasyprint', None)
            with patch('builtins.__import__', side_effect=_fake_import):
                with self.assertRaises(RuntimeError):
                    pdf.render_pdf(html='<p>x</p>')


class BrandingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Solar')

    def _profile(self, **kw):
        from django.apps import apps as django_apps
        Profile = django_apps.get_model('parametres', 'CompanyProfile')
        defaults = {'company': self.company, 'nom': 'ACME Solar',
                    'ice': '001234567', 'identifiant_fiscal': 'IF-99',
                    'adresse': 'Casablanca', 'telephone': '0522',
                    'email': 'x@acme.ma'}
        defaults.update(kw)
        return Profile.objects.create(**defaults)

    def test_header_off_by_default_leaves_html_unchanged(self):
        captured = []
        html_in = '<html><body>Corps</body></html>'
        with patch.dict(sys.modules,
                        {'weasyprint': _fake_weasyprint(captured)}):
            pdf.render_pdf(html=html_in, company=self.company)
        # Header/footer désactivés → HTML rendu strictement identique.
        self.assertEqual(captured[0], html_in)

    def test_header_on_injects_branding(self):
        self._profile()
        captured = []
        html_in = '<html><body>Corps</body></html>'
        with patch.dict(sys.modules,
                        {'weasyprint': _fake_weasyprint(captured)}):
            pdf.render_pdf(html=html_in, company=self.company, header=True,
                           footer=True)
        rendered = captured[0]
        self.assertIn('ACME Solar', rendered)
        self.assertIn('ICE : 001234567', rendered)
        self.assertIn('pdf-brand-header', rendered)
        self.assertIn('pdf-brand-footer', rendered)

    def test_header_without_company_is_noop(self):
        captured = []
        html_in = '<html><body>Corps</body></html>'
        with patch.dict(sys.modules,
                        {'weasyprint': _fake_weasyprint(captured)}):
            pdf.render_pdf(html=html_in, company=None, header=True)
        # Pas de société → aucun bandeau, HTML inchangé.
        self.assertEqual(captured[0], html_in)

    def test_branded_header_helper_empty_without_profile(self):
        # Société sans profil → pas de bandeau (jamais de crash).
        self.assertEqual(pdf.branded_header_html(self.company), '')


class UploadTests(SimpleTestCase):
    def test_upload_to_returns_bytes_and_key(self):
        fake_client = MagicMock()
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}), \
                patch('core.pdf._minio_client', return_value=fake_client):
            result = pdf.render_pdf(
                html='<html><body>x</body></html>',
                upload_to='terrain/doc-1.pdf', upload_bucket='erp-uploads')
        self.assertIsInstance(result, tuple)
        pdf_bytes, key = result
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        self.assertEqual(key, 'terrain/doc-1.pdf')
        # put_object a bien été appelé avec le content-type PDF.
        fake_client.put_object.assert_called_once()
        _, kwargs = fake_client.put_object.call_args
        self.assertEqual(kwargs['Bucket'], 'erp-uploads')
        self.assertEqual(kwargs['Key'], 'terrain/doc-1.pdf')
        self.assertEqual(kwargs['ContentType'], 'application/pdf')

    def test_no_upload_returns_bytes_only(self):
        with patch.dict(sys.modules, {'weasyprint': _fake_weasyprint()}):
            out = pdf.render_pdf(html='<html><body>x</body></html>')
        self.assertIsInstance(out, bytes)


@tag('pdf')
class RealRenderSmokeTests(SimpleTestCase):
    """Rendu RÉEL via WeasyPrint natif (palier lourd, exclu du tier rapide)."""

    def test_real_render_produces_pdf(self):
        out = pdf.render_pdf(
            html='<html><body><h1>Test ARC11</h1></body></html>')
        self.assertTrue(out.startswith(b'%PDF'))
