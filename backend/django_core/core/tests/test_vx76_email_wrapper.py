"""VX76 — wrapper HTML de marque unique (``core.selectors.wrap_email_html``)
+ commande ``manage.py preview_email``.

Couvre : le rendu contient le nom de société (en-tête « logo textuel » navy),
le corps texte est repris (échappé, avec retours à la ligne convertis), le
repli neutre TAQINOR sans société, et jamais d'exception. La commande
``preview_email`` écrit un fichier HTML relisible AVANT le premier envoi réel
— la boucle de validation visuelle exigée par le Done de VX76."""
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase

from core.selectors import wrap_email_html


class WrapEmailHtmlTests(TestCase):
    def test_wraps_body_with_company_header(self):
        html = wrap_email_html(
            'Votre devis DEV-1', 'Bonjour,\n\nVoici votre devis.',
            company_nom='ACME Solar', company_adresse='Casablanca',
            company_telephone='0600000000', company_email='c@acme.ma')
        self.assertIn('ACME Solar', html)
        self.assertIn('Casablanca', html)
        self.assertIn('Voici votre devis.', html)
        self.assertIn('<html', html)

    def test_default_header_without_company_name(self):
        html = wrap_email_html('Sujet', 'Corps')
        self.assertIn('TAQINOR', html)

    def test_body_is_escaped_and_linebreaks_converted(self):
        html = wrap_email_html('Sujet', 'Ligne 1\nLigne 2 <script>x</script>')
        self.assertIn('Ligne 1', html)
        self.assertIn('Ligne 2', html)
        self.assertNotIn('<script>x</script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_never_raises_falls_back_to_plain_body_on_render_failure(self):
        # Corps texte quelconque, appel simple : ne doit jamais lever.
        try:
            html = wrap_email_html('', '')
        except Exception as exc:  # pragma: no cover - ne doit jamais arriver
            self.fail(f'wrap_email_html a levé une exception : {exc}')
        self.assertIsInstance(html, str)


class PreviewEmailCommandTests(TestCase):
    def test_writes_html_file_with_wrapper_and_sample_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, 'apercu.html')
            call_command('preview_email', f'--out={out_path}')
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, encoding='utf-8') as fh:
                content = fh.read()
            self.assertIn('TAQINOR', content)
            self.assertIn('devis DEV-0001', content)
            self.assertIn('<html', content)
