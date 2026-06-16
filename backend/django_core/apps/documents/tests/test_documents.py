"""
Tests des générateurs de PDF après-vente (N21–N24).

Chaque endpoint :
  - renvoie un PDF valide (application/pdf, non vide) pour un chantier de la
    société du user ;
  - renvoie 404 pour un chantier d'une autre société ;
  - ne laisse JAMAIS fuiter un prix d'achat dans le PDF.

MinIO est mocké (pas de logo/signature à télécharger).
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.installations.models import Installation

User = get_user_model()

# Chaîne de prix d'achat à NE JAMAIS retrouver dans un PDF client.
BUY_PRICE_MARKER = '777.77'


def _company(slug='doc-co', nom='Doc Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _user(company, username):
    return User.objects.create_user(
        username=username, password='pw',
        role_legacy='responsable', company=company,
    )


def _client_obj(company):
    return Client.objects.create(
        nom='Bennani', prenom='Karim', email=None,
        telephone='0600000000', adresse='10 rue Test, Casablanca',
        company=company,
    )


def _produit(company):
    return Produit.objects.create(
        nom='Panneau 550W', sku='PV-550',
        prix_vente=Decimal('1500.00'),
        prix_achat=Decimal(BUY_PRICE_MARKER),
        quantite_stock=100, company=company,
        marque='JA Solar',
        garantie='25 ans performance / 12 ans produit',
    )


def _devis(company, user, client, produit):
    devis = Devis.objects.create(
        reference='DEV-DOC-0001', client=client, statut='accepte',
        taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
        created_by=user, company=company,
    )
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Panneau 550W',
        quantite=Decimal('12'), prix_unitaire=Decimal('1500.00'),
        remise=Decimal('0'),
    )
    return devis


def _chantier(company, user, client, devis):
    return Installation.objects.create(
        company=company, reference='CH-DOC-0001', client=client, devis=devis,
        puissance_installee_kwc=Decimal('6.60'),
        type_installation=Installation.TypeInstallation.RESIDENTIEL,
        raccordement=Installation.Raccordement.MONOPHASE,
        technicien_responsable=user,
        date_mise_en_service='2026-06-10',
        date_pose_reelle='2026-06-05',
        site_adresse='10 rue Test', site_ville='Casablanca',
    )


@patch('apps.ventes.utils.pdf._download', return_value=None)
class DocumentEndpointsTest(TestCase):

    def setUp(self):
        self.company = _company()
        self.user = _user(self.company, 'doc_user')
        self.client_obj = _client_obj(self.company)
        self.produit = _produit(self.company)
        self.devis = _devis(
            self.company, self.user, self.client_obj, self.produit)
        self.chantier = _chantier(
            self.company, self.user, self.client_obj, self.devis)

        # Société étrangère + chantier étranger (tenant isolation).
        self.other_company = _company(slug='other-co', nom='Other Co')
        self.other_user = _user(self.other_company, 'other_user')
        self.other_client = _client_obj(self.other_company)
        self.other_chantier = Installation.objects.create(
            company=self.other_company, reference='CH-OTHER-0001',
            client=self.other_client,
        )

        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _assert_valid_pdf(self, resp):
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        body = resp.content
        self.assertTrue(len(body) > 1000)
        self.assertEqual(body[:4], b'%PDF')

    def _url(self, kind, pk):
        return f'/api/django/documents/chantiers/{pk}/{kind}/'

    # ── N21 ──
    def test_pv_reception_ok(self, _dl):
        resp = self.api.get(self._url('pv-reception', self.chantier.id))
        self._assert_valid_pdf(resp)

    def test_pv_reception_foreign_404(self, _dl):
        resp = self.api.get(self._url('pv-reception', self.other_chantier.id))
        self.assertEqual(resp.status_code, 404)

    # ── N22 ──
    def test_bon_livraison_ok(self, _dl):
        resp = self.api.get(self._url('bon-livraison', self.chantier.id))
        self._assert_valid_pdf(resp)

    def test_bon_livraison_foreign_404(self, _dl):
        resp = self.api.get(self._url('bon-livraison', self.other_chantier.id))
        self.assertEqual(resp.status_code, 404)

    # ── N23 ──
    def test_dossier_remise_ok(self, _dl):
        resp = self.api.get(self._url('dossier-remise', self.chantier.id))
        self._assert_valid_pdf(resp)

    def test_dossier_remise_foreign_404(self, _dl):
        resp = self.api.get(self._url('dossier-remise', self.other_chantier.id))
        self.assertEqual(resp.status_code, 404)

    # ── N24 ──
    def test_attestation_installation_ok(self, _dl):
        resp = self.api.get(
            self._url('attestation', self.chantier.id) + '?type=installation')
        self._assert_valid_pdf(resp)

    def test_attestation_fin_travaux_ok(self, _dl):
        resp = self.api.get(
            self._url('attestation', self.chantier.id) + '?type=fin_travaux')
        self._assert_valid_pdf(resp)

    def test_attestation_default_type_ok(self, _dl):
        resp = self.api.get(self._url('attestation', self.chantier.id))
        self._assert_valid_pdf(resp)

    def test_attestation_unknown_type_400(self, _dl):
        resp = self.api.get(
            self._url('attestation', self.chantier.id) + '?type=bidon')
        self.assertEqual(resp.status_code, 400)

    def test_attestation_foreign_404(self, _dl):
        resp = self.api.get(self._url('attestation', self.other_chantier.id))
        self.assertEqual(resp.status_code, 404)


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class DocumentHtmlContentTest(TestCase):
    """Vérifie le HTML rendu : contenu attendu présent, prix d'achat absent.

    On capture le HTML passé à WeasyPrint (le PDF compresse ses flux texte, on
    ne peut donc pas chercher une chaîne dans les octets du PDF de façon
    fiable). C'est la garde anti-fuite de prix d'achat.
    """

    def setUp(self):
        from apps.documents import builders
        self.builders = builders
        self.company = _company(slug='html-co', nom='HTML Co')
        self.user = _user(self.company, 'html_user')
        self.client_obj = _client_obj(self.company)
        self.produit = _produit(self.company)
        self.devis = _devis(
            self.company, self.user, self.client_obj, self.produit)
        self.chantier = _chantier(
            self.company, self.user, self.client_obj, self.devis)

    def _captured_html(self, mock_html_to_pdf):
        return mock_html_to_pdf.call_args[0][0]

    def test_no_buy_price_leak_in_any_document(self, mock_pdf, _dl):
        mock_pdf.return_value = b'%PDF-fake'
        gens = [
            lambda: self.builders.generate_pv_reception(self.chantier),
            lambda: self.builders.generate_bon_livraison(self.chantier),
            lambda: self.builders.generate_dossier_remise(self.chantier),
            lambda: self.builders.generate_attestation(
                self.chantier, 'installation'),
            lambda: self.builders.generate_attestation(
                self.chantier, 'fin_travaux'),
        ]
        for gen in gens:
            mock_pdf.reset_mock()
            gen()
            html = self._captured_html(mock_pdf)
            self.assertNotIn(BUY_PRICE_MARKER, html)

    def test_dossier_remise_reuses_product_warranty(self, mock_pdf, _dl):
        mock_pdf.return_value = b'%PDF-fake'
        self.builders.generate_dossier_remise(self.chantier)
        html = self._captured_html(mock_pdf)
        self.assertIn('25 ans', html)
        self.assertIn('Panneau 550W', html)

    def test_pv_reception_has_bon_pour_accord(self, mock_pdf, _dl):
        mock_pdf.return_value = b'%PDF-fake'
        self.builders.generate_pv_reception(self.chantier)
        html = self._captured_html(mock_pdf)
        self.assertIn('Bon pour accord', html)
        self.assertIn('6.60', html)  # puissance kWc

    def test_attestation_company_identity(self, mock_pdf, _dl):
        mock_pdf.return_value = b'%PDF-fake'
        self.builders.generate_attestation(self.chantier, 'installation')
        html = self._captured_html(mock_pdf)
        # L'apostrophe est échappée par Jinja (autoescape) → &#39;.
        self.assertIn('Attestation d', html)
        self.assertIn('installation', html)
        self.assertIn(self.company.nom, html)
