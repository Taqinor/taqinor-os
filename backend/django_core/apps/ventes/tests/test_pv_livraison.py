"""FG51 — Preuve de livraison (PV/signature) avant facturation.

Couvre :
  * « marquer-livre » capture le signataire / la note (et horodate la livraison),
  * `has_proof_of_delivery` reflète la présence d'une preuve,
  * « creer-facture » renvoie un avertissement DOUX (jamais bloquant) quand le BC
    n'a pas de preuve de livraison, et n'en renvoie pas quand la preuve existe,
  * la facture est toujours créée (201) dans les deux cas — la facturation n'est
    jamais bloquée.

Run :
    python manage.py test apps.ventes.tests.test_pv_livraison -v 2
"""
import io
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, Facture, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='pv-co', nom='PV Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PvLivraisonTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='pvuser', password='x', role_legacy='responsable',
            company=self.company)
        self.client_api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.client_api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.cl = Client.objects.create(
            company=self.company, nom='PV', prenom='Client',
            email='pv@example.com', telephone='+212600000001',
            adresse='Casablanca')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND-PV',
            prix_vente=Decimal('5000'), quantite_stock=50)
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-7001',
            client=self.cl, statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Onduleur 5kW',
            quantite=Decimal('2'), prix_unitaire=Decimal('5000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))

    def _bc(self, statut=BonCommande.Statut.CONFIRME):
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-7001',
            devis=self.devis, client=self.cl, statut=statut)

    def test_marquer_livre_captures_pv(self):
        bc = self._bc()
        resp = self.client_api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/',
            {'signataire': 'M. Client', 'note_pv': 'Reçu conforme'},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommande.Statut.LIVRE)
        self.assertTrue(bc.has_proof_of_delivery)
        self.assertEqual(bc.pv_livraison['signataire'], 'M. Client')
        self.assertIn('signed_at', bc.pv_livraison)
        self.assertIsNotNone(bc.date_livraison_reelle)
        self.assertTrue(resp.data['has_proof_of_delivery'])

    def test_marquer_livre_without_pv_has_no_proof(self):
        bc = self._bc()
        resp = self.client_api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/',
            {}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommande.Statut.LIVRE)
        self.assertFalse(bc.has_proof_of_delivery)
        # date de livraison réelle horodatée même sans preuve.
        self.assertIsNotNone(bc.date_livraison_reelle)

    def test_marquer_livre_stores_attachment(self):
        bc = self._bc()
        pdf = io.BytesIO(b'%PDF-1.4 fake pv')
        pdf.name = 'pv.pdf'
        fake_meta = {'file_key': 'attachments/abc.pdf', 'filename': 'pv.pdf',
                     'size': 16, 'mime': 'application/pdf'}
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=(fake_meta, None)) as m:
            resp = self.client_api.post(
                f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/',
                {'pv': pdf}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        m.assert_called_once()
        bc.refresh_from_db()
        self.assertTrue(bc.has_proof_of_delivery)
        self.assertEqual(bc.pv_livraison['file_key'], 'attachments/abc.pdf')

    def test_creer_facture_warns_without_proof(self):
        """Pas de preuve → facture créée (201) AVEC un avertissement doux."""
        bc = self._bc()
        resp = self.client_api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIn('warnings', resp.data)
        self.assertTrue(resp.data['warnings'])
        self.assertTrue(Facture.objects.filter(bon_commande=bc).exists())

    def test_creer_facture_no_warning_with_proof(self):
        """Preuve présente → facture créée (201) SANS avertissement."""
        bc = self._bc()
        bc.pv_livraison = {'signataire': 'M. Client',
                           'signed_at': timezone.now().isoformat()}
        bc.statut = BonCommande.Statut.LIVRE
        bc.save()
        resp = self.client_api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertNotIn('warnings', resp.data)

    def test_pv_not_settable_via_put(self):
        """pv_livraison est read-only : un PUT du corps ne le pose pas."""
        bc = self._bc()
        resp = self.client_api.patch(
            f'/api/django/ventes/bons-commande/{bc.id}/',
            {'pv_livraison': {'signataire': 'pirate'}}, format='json')
        self.assertIn(resp.status_code, (200, 400), resp.content)
        bc.refresh_from_db()
        self.assertFalse(bc.has_proof_of_delivery)
