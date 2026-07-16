"""QX9 — preuve de signature électronique réelle + exemplaire signé (loi 43-20).

Avant QX9, la signature manuscrite, ``consent_esign``, ``signed_at_client`` et
``on_behalf_of`` étaient jetés par ``proposal_accept`` (qui lisait une clé
``consentement`` que le front n'envoie pas → consentement à True par défaut),
et l'email « ci-joint votre exemplaire signé » partait souvent SANS PDF.

Ces tests prouvent :
  * les quatre artefacts persistent sur ``DevisSignature`` ;
  * le consentement explicite est exigé côté serveur (400 sinon) ;
  * l'email d'acceptation joint le PDF signé quand il existe.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, DevisSignature, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _make_devis(company, client, ref):
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
    produit = Produit.objects.create(
        company=company, nom='Panneau', sku=f'{ref}-PV',
        prix_vente=Decimal('1000'), quantite_stock=100)
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Panneau',
        quantite=Decimal('5'), prix_unitaire=Decimal('1000'),
        remise=Decimal('0'))
    return devis


class Qx9EsignEvidenceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX9 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Salma',
            email='salma@example.com', telephone='+212600000044')
        self.api = APIClient()

    def _url(self, token):
        return f'/api/django/public/proposal/{token}/accept/'

    def test_all_four_artifacts_persist(self):
        devis = _make_devis(self.company, self.client_obj, f'DEV-{MONTH}-QX901')
        link = ShareLink.for_devis(devis)
        ts = '2026-07-10T12:34:56+00:00'
        resp = self.api.post(self._url(link.token), {
            'nom': 'Salma Bennani',
            'consent_esign': True,
            'signature_data_url': 'data:image/png;base64,AAAA',
            'signed_at_client': ts,
            'on_behalf_of': 'mon foyer',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.signature_image, 'data:image/png;base64,AAAA')
        self.assertTrue(sig.consent_esign)
        self.assertIsNotNone(sig.signed_at_client)
        self.assertEqual(sig.on_behalf_of, 'mon foyer')

    def test_consent_required(self):
        devis = _make_devis(self.company, self.client_obj, f'DEV-{MONTH}-QX902')
        link = ShareLink.for_devis(devis)
        # Aucun consentement → 400, aucune acceptation.
        resp = self.api.post(self._url(link.token), {
            'nom': 'Salma Bennani'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertFalse(DevisSignature.objects.filter(devis=devis).exists())

    def test_consent_explicit_false_rejected(self):
        devis = _make_devis(self.company, self.client_obj, f'DEV-{MONTH}-QX903')
        link = ShareLink.for_devis(devis)
        resp = self.api.post(self._url(link.token), {
            'nom': 'Salma Bennani', 'consent_esign': False}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_acceptance_email_carries_signed_pdf(self):
        """Le PDF SIGNÉ (signed_pdf_key) est préféré comme pièce jointe."""
        from apps.ventes import email_service
        devis = _make_devis(self.company, self.client_obj, f'DEV-{MONTH}-QX904')
        # Simule une signature déjà porteuse d'une clé de PDF signé.
        DevisSignature.objects.create(
            company=self.company, devis=devis,
            signataire_nom='Salma', consentement_explicite=True,
            signed_at=timezone.now(), signed_pdf_key='signed/devis-qx904.pdf',
            consent_esign=True)
        with mock.patch(
                'apps.ventes.utils.pdf.download_pdf',
                return_value=b'%PDF-signed') as dl:
            data, name = email_service._document_pdf(devis)
        dl.assert_called_once_with('signed/devis-qx904.pdf')
        self.assertEqual(data, b'%PDF-signed')
        self.assertTrue(name.endswith('.pdf'))

    def test_blank_attachment_branch_logs(self):
        """Aucune clé de PDF → (None, None) + un warning journalisé (QX9)."""
        from apps.ventes import email_service
        devis = _make_devis(self.company, self.client_obj, f'DEV-{MONTH}-QX905')
        with self.assertLogs('apps.ventes.email_service', level='WARNING'):
            data, name = email_service._document_pdf(devis)
        self.assertIsNone(data)
        self.assertIsNone(name)
