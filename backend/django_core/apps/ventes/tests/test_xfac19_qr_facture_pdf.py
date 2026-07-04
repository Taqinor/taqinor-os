"""
XFAC19 — QR code de paiement/vérification sur le PDF facture (legacy).

Une facture avec un lien de paiement actif rend un QR scannable vers la page
de paiement ; sans lien, le QR pointe vers le document public ; le PDF sans
aucun lien reste identique à aujourd'hui (ajout silencieux).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac19_qr_facture_pdf -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, PaymentLink, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac19-co', nom='XFAC19 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company):
    return User.objects.create_user(
        username='xfac19_user', password='x', role_legacy='responsable',
        company=company,
    )


def make_client(company):
    return Client.objects.create(
        company=company, nom='QR', prenom='Client',
        email='xfac19@example.com', telephone='+212600000065',
        adresse='Casablanca',
    )


def make_facture(user, client_obj, produit):
    facture = Facture.objects.create(
        company=user.company, reference=f'FAC-{MONTH}-9101',
        client=client_obj, statut=Facture.Statut.EMISE,
        taux_tva=Decimal('20.00'), created_by=user,
    )
    LigneFacture.objects.create(
        facture=facture, produit=produit, designation='Panneau',
        quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
    )
    return facture


class XFAC19QrServiceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='SKU-XFAC19',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=10,
        )
        self.facture = make_facture(self.user, self.client_obj, self.produit)

    def test_no_link_renders_share_link_qr(self):
        from apps.ventes.services import qr_svg_for_facture_pdf
        svg = qr_svg_for_facture_pdf(self.facture)
        self.assertIsNotNone(svg)
        self.assertIn('<svg', svg)
        share = ShareLink.objects.get(facture=self.facture)
        self.assertTrue(PaymentLink.objects.filter(
            facture=self.facture).exists() is False)
        self.assertIsNotNone(share)

    def test_active_payment_link_takes_priority(self):
        from apps.ventes.services import create_payment_link, \
            qr_svg_for_facture_pdf
        link = create_payment_link(facture=self.facture)
        with patch('apps.ventes.services.qr_svg_for') as mock_qr:
            mock_qr.return_value = '<svg>fake</svg>'
            qr_svg_for_facture_pdf(self.facture)
            called_url = mock_qr.call_args[0][0]
        self.assertIn(link.token, called_url)
        self.assertIn('/pay/', called_url)

    def test_no_payment_link_uses_document_share_url(self):
        from apps.ventes.services import qr_svg_for_facture_pdf
        with patch('apps.ventes.services.qr_svg_for') as mock_qr:
            mock_qr.return_value = '<svg>fake</svg>'
            qr_svg_for_facture_pdf(self.facture)
            called_url = mock_qr.call_args[0][0]
        share = ShareLink.objects.get(facture=self.facture)
        self.assertIn(share.token, called_url)
        self.assertIn('/document/', called_url)

    def test_expired_payment_link_falls_back_to_share_link(self):
        from datetime import timedelta
        from apps.ventes.services import create_payment_link, \
            qr_svg_for_facture_pdf
        link = create_payment_link(facture=self.facture)
        PaymentLink.objects.filter(pk=link.pk).update(
            expires_at=timezone.now() - timedelta(days=1))
        with patch('apps.ventes.services.qr_svg_for') as mock_qr:
            mock_qr.return_value = '<svg>fake</svg>'
            qr_svg_for_facture_pdf(self.facture)
            called_url = mock_qr.call_args[0][0]
        self.assertIn('/document/', called_url)


class XFAC19PdfPipelineTests(TestCase):
    """Le PDF facture legacy embarque le QR sans casser le rendu existant."""

    def setUp(self):
        self.company = make_company(slug='xfac19-co2', nom='XFAC19 Co2')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='SKU-XFAC19B',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=10,
        )
        self.facture = make_facture(self.user, self.client_obj, self.produit)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_pdf_pipeline_embeds_qr_svg_in_html(self, mock_dl, mock_upload):
        from apps.ventes.utils.pdf import generate_facture_pdf
        with patch('apps.ventes.utils.pdf._html_to_pdf') as mock_wp:
            mock_wp.return_value = b'%PDF-fake'
            generate_facture_pdf(self.facture.id)
            html_arg = mock_wp.call_args[0][0]
        self.assertIn('<svg', html_arg)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_pdf_pipeline_survives_qr_failure_silently(self, mock_dl, mock_upload):
        """Ajout silencieux : une panne du QR ne casse jamais le rendu PDF."""
        from apps.ventes.utils.pdf import generate_facture_pdf
        patch_target = 'apps.ventes.services.qr_svg_for_facture_pdf'
        with patch(patch_target, side_effect=RuntimeError('boom')):
            with patch('apps.ventes.utils.pdf._html_to_pdf') as mock_wp:
                mock_wp.return_value = b'%PDF-fake'
                key = generate_facture_pdf(self.facture.id)
                html_arg = mock_wp.call_args[0][0]
        self.assertEqual(key, f'factures/{self.facture.reference}.pdf')
        self.assertNotIn('<div class="footer-qr">', html_arg)
