"""ZMKT19 — Badge d'inscrit imprimable (PDF).

Couvre : le badge PDF d'un inscrit contient nom+événement+QR scannable par
la borne, l'impression en lot produit un PDF multi-pages, aucune donnée
interne (jamais prix_achat), tests (contenu, lot).
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import EvenementMarketing
from apps.compta.pdf_badge_evenement import render_badge_html, render_badges_html


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class BadgeInscritPdfTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt19', 'ZMKT19')
        self.evt = EvenementMarketing.objects.create(
            company=self.co, nom='Salon', date_debut=timezone.now())

    def test_html_contient_nom_et_evenement(self):
        html = render_badge_html(
            nom_inscrit='Ahmed Benali', nom_evenement='Salon SIAM',
            qr_svg='<svg></svg>')
        self.assertIn('Ahmed Benali', html)
        self.assertIn('Salon SIAM', html)
        self.assertIn('<svg>', html)

    def test_html_jamais_prix_achat(self):
        html = render_badge_html(
            nom_inscrit='X', nom_evenement='Y', qr_svg='')
        self.assertNotIn('prix_achat', html)

    def test_lot_multi_pages(self):
        html = render_badges_html([
            {'nom_inscrit': 'A', 'nom_evenement': 'Salon', 'nom_societe': '',
             'qr_svg': ''},
            {'nom_inscrit': 'B', 'nom_evenement': 'Salon', 'nom_societe': '',
             'qr_svg': ''},
        ])
        self.assertEqual(html.count('class="badge"'), 2)

    @patch('apps.compta.pdf_badge_evenement._html_to_pdf')
    def test_generer_badge_pdf_appelle_weasyprint(self, mock_pdf):
        mock_pdf.return_value = b'%PDF-FAKE'
        inscription = services.inscrire_evenement(self.evt, nom='Karim')
        pdf_bytes = services.generer_badge_pdf(inscription)
        self.assertEqual(pdf_bytes, b'%PDF-FAKE')

    @patch('apps.compta.pdf_badge_evenement._html_to_pdf')
    def test_generer_badges_lot_appelle_weasyprint(self, mock_pdf):
        mock_pdf.return_value = b'%PDF-LOT'
        services.inscrire_evenement(self.evt, nom='A')
        services.inscrire_evenement(self.evt, nom='B')
        pdf_bytes = services.generer_badges_pdf_lot(self.evt)
        self.assertEqual(pdf_bytes, b'%PDF-LOT')

    def test_endpoint_badge_individuel(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        inscription = services.inscrire_evenement(self.evt, nom='Endpoint')
        user = User.objects.create_user(
            username='zmkt19-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        with patch(
                'apps.compta.pdf_badge_evenement._html_to_pdf',
                return_value=b'%PDF-OK'):
            resp = api.get(
                f'/api/django/compta/inscriptions-evenement/{inscription.id}/badge/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
