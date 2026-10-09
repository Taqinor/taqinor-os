"""APDF25 (C-APDF-002) — la facture (et le BL) arabe n'embarque plus de
``@font-face`` « Noto Sans Arabic » vendorisé : la police système de l'image
sert seule et la colonne Total se lit (« MAD صنعى » aujourd'hui, sonde
PLANG-1). Facture FR inchangée.

Rendu WeasyPrint RÉEL (``generate_facture_pdf``) ; seul l'upload MinIO est
neutralisé, le HTML rendu est capturé en enveloppant ``_render_html`` (il
est appelé tel quel).

Test-du-test : faire renvoyer de nouveau les deux ``@font-face`` par
``arabic_font_face_css`` ⇒ ``test_aucun_font_face_vendorise`` échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_apdf_police_arabe"
"""
import re
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

FONT_FACE_ARABE = re.compile(
    r'@font-face\s*\{[^}]*Noto Sans Arabic', re.IGNORECASE)
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class FacturePoliceArabeTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.utils import pdf as pdf_mod
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'APDF25 {n}', slug=f'apdf25-{n}')
        self.objets = {}
        self.html = []
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)
        vrai_rendu = pdf_mod._render_html

        def _capture(nom, ctx):
            html = vrai_rendu(nom, ctx)
            self.html.append(html)
            return html
        p_html = patch('apps.ventes.utils.pdf._render_html',
                       side_effect=_capture)
        p_html.start()
        self.addCleanup(p_html.stop)
        self.client_ar = Client.objects.create(
            company=self.company, nom='Tazi', prenom='Amal',
            email=f'apdf25-{n}@example.invalid', langue_document='ar')

    def _facture(self):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-APDF25-{_nxt():04d}',
            client=self.client_ar, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('2975'),
            montant_tva=Decimal('595'), montant_ttc=Decimal('3570'))

    def _rendre(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        return self.objets[generate_facture_pdf(facture.id)]

    def test_aucun_font_face_vendorise(self):
        from apps.ventes.utils.libelles_ar import arabic_font_face_css
        self.assertEqual(arabic_font_face_css(), '')
        self._rendre(self._facture())
        html = self.html[-1]
        self.assertIn('dir="rtl"', html)
        self.assertIsNone(FONT_FACE_ARABE.search(html))
        self.assertNotIn('NotoSansArabic', html)

    def test_total_lisible_raster(self):
        import fitz
        pdf = self._rendre(self._facture())
        doc = fitz.open(stream=pdf, filetype='pdf')
        try:
            page = doc[0]
            # La page se rastérise (aucune police manquante qui ferait
            # échouer le rendu) ...
            pix = page.get_pixmap(dpi=72)
            self.assertGreater(pix.width, 0)
            texte = ' '.join(page.get_text().split())
        finally:
            doc.close()
        # ... le total se relit en chiffres latins, et les libellés
        # structurels arabes sont bien ceux rendus (police système seule).
        self.assertIn('3570.00', texte)
        self.assertIn('المُصدر', self.html[-1])
        self.assertIn('موجهة إلى', self.html[-1])
