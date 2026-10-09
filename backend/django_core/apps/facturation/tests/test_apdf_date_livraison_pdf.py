"""APDF26 (C-APDF-008) — la date de livraison / prestation est imprimée dans
la rangée méta du PDF facture dès qu'elle est renseignée (libellé via
``L()``, traduit en arabe) : la date contrôlée par ``mentions_manquantes``
et exportée à la DGI est celle que le client lit.

Rejoue la sonde PFAC-1 (« 15/07/2026 » absent, texte identique pour deux
dates). Rendu WeasyPrint RÉEL (``generate_facture_pdf``) ; seul l'upload
MinIO est neutralisé, le HTML rendu est capturé autour du vrai
``_render_html``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_apdf_date_livraison_pdf"
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

LIBELLE = 'Date de livraison / prestation'
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _texte(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class DateLivraisonPdfTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.utils import pdf as pdf_mod
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'APDF26 {n}', slug=f'apdf26-{n}')
        self.client_fr = Client.objects.create(
            company=self.company, nom='Idrissi', prenom='Karim',
            email=f'apdf26-{n}@example.invalid')
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

    def _facture(self, livraison=None, client=None):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-APDF26-{_nxt():04d}',
            client=client or self.client_fr, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            date_livraison=livraison)

    def _pdf(self, facture):
        from apps.ventes.utils.pdf import generate_facture_pdf
        return _texte(self.objets[generate_facture_pdf(facture.id)])

    def test_date_imprimee(self):
        texte = self._pdf(self._facture(date(2026, 7, 15)))
        self.assertIn(LIBELLE, texte)
        self.assertIn('15/07/2026', texte)

    def test_changement_date_change_texte(self):
        from apps.ventes.models import Facture
        facture = self._facture(date(2026, 7, 15))
        avant = self._pdf(facture)
        Facture.objects.filter(pk=facture.pk).update(
            date_livraison=date(2026, 8, 20))
        apres = self._pdf(Facture.objects.get(pk=facture.pk))
        self.assertIn('20/08/2026', apres)
        self.assertNotIn('15/07/2026', apres)
        self.assertNotEqual(avant, apres)

    def test_sans_date_aucune_ligne(self):
        texte = self._pdf(self._facture(None))
        self.assertNotIn(LIBELLE, texte)
        self.assertNotIn('Date de livraison', self.html[-1])

    def test_libelle_ar(self):
        from apps.crm.models import Client
        from apps.ventes.utils.libelles_ar import LIBELLES
        client_ar = Client.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            email=f'apdf26-ar-{_nxt()}@example.invalid',
            langue_document='ar')
        texte = self._pdf(self._facture(date(2026, 7, 15), client=client_ar))
        self.assertIn('15/07/2026', texte)
        self.assertNotIn(LIBELLE, texte)
        self.assertIn(LIBELLES['ar']['date_livraison'], self.html[-1])
