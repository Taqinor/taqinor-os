"""APDF50 (C-APDF-002) — le BL chantier arabe reste lisible : aucun
``@font-face`` arabe vendorisé, le contexte ne porte plus
``arabic_font_face_css`` et la page rastérisée relit le nom du client
« QA-CAL-PUB-OFF » (sonde PLANG-1c : « QAÎCALÎPUBÎOFF » avec l'ancienne
police embarquée).

Rendu WeasyPrint RÉEL (``generate_bon_livraison`` → ``core.pdf.render_pdf``),
aucun mock de la source : seul le HTML et le contexte sont CAPTURÉS en
enveloppant les vraies fonctions.

Test-du-test : réintroduire ``ctx['arabic_font_face_css']`` avec l'ancien CSS
(@font-face Noto Sans Arabic woff2) ⇒ ``test_nom_client_lisible`` échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.documents.tests.test_apdf_bl_arabe_lisible"
"""
import re
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

FONT_FACE_ARABE = re.compile(
    r'@font-face\s*\{[^}]*Noto Sans Arabic', re.IGNORECASE)
NOM_CLIENT = 'QA-CAL-PUB-OFF'


class BlArabeLisibleTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.documents import builders
        from apps.installations.models import Installation
        from authentication.models import Company

        self.company = Company.objects.create(
            nom='APDF50 Co', slug='apdf50-co')
        client_ar = Client.objects.create(
            company=self.company, nom=NOM_CLIENT, prenom='',
            telephone='+212600000050', adresse='5 rue Test, Rabat',
            langue_document='ar')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-APDF50-AR', client=client_ar,
            puissance_installee_kwc=Decimal('5.00'),
            date_mise_en_service='2026-06-01', date_pose_reelle='2026-05-28',
            site_adresse='5 rue Test', site_ville='Rabat')

        self.html = []
        self.contextes = []
        vrai_html_to_pdf = builders._html_to_pdf
        vrai_get_template = builders.get_template

        def _capture_html(html):
            self.html.append(html)
            return vrai_html_to_pdf(html)

        def _capture_gabarit(nom):
            gabarit = vrai_get_template(nom)
            test = self

            class _Enveloppe:
                def render(self, ctx=None, request=None):
                    test.contextes.append(dict(ctx or {}))
                    return gabarit.render(ctx, request)
            return _Enveloppe()

        for cible, effet in (
                ('apps.documents.builders._html_to_pdf', _capture_html),
                ('apps.documents.builders.get_template', _capture_gabarit)):
            p = patch(cible, side_effect=effet)
            p.start()
            self.addCleanup(p.stop)
        p_dl = patch('apps.ventes.utils.pdf._download', return_value=None)
        p_dl.start()
        self.addCleanup(p_dl.stop)

    def _rendre(self):
        from apps.documents.builders import generate_bon_livraison
        return generate_bon_livraison(self.chantier)

    def test_aucun_font_face(self):
        self._rendre()
        html = self.html[-1]
        self.assertIn('dir="rtl"', html)
        self.assertIsNone(FONT_FACE_ARABE.search(html))
        self.assertNotIn('NotoSansArabic', html)
        self.assertNotIn('arabic_font_face_css', self.contextes[-1])

    def test_nom_client_lisible(self):
        import fitz
        pdf = self._rendre()
        doc = fitz.open(stream=pdf, filetype='pdf')
        try:
            page = doc[0]
            pix = page.get_pixmap(dpi=72)
            self.assertGreater(pix.width, 0)
            texte = ' '.join(page.get_text().split())
        finally:
            doc.close()
        self.assertIn(NOM_CLIENT, texte)
        self.assertNotIn('QAÎCALÎPUBÎOFF', texte)
