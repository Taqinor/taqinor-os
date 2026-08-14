"""NTRET18 — connecteur Shopify [GATED: Shopify API].

Sans clé configurée : structure + no-op TOTAL (aucun appel réseau). Les
chemins « avec clé » sont testés avec une clé FACTICE (jamais une vraie
credential) + HTTP entièrement MOQUÉ (``unittest.mock``) — jamais un appel
réseau réel, y compris dans ces tests."""
import base64
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.ecommerce_connect import shopify
from apps.ecommerce_connect.models import (
    CommandeSync, ConnexionEcommerce, ProduitSync,
)
from apps.stock.models import Produit
from authentication.models import Company


def _company(nom='Société Shopify'):
    return Company.objects.create(nom=nom)


class SansCleApiNoOpTests(TestCase):
    """Motif du dépôt : sans clé, l'intégration ne fait RIEN et ne casse rien."""

    def setUp(self):
        self.company = _company()

    @override_settings(SHOPIFY_ADMIN_TOKEN='')
    def test_is_configured_false_sans_cle(self):
        self.assertFalse(shopify.is_configured())

    @override_settings(SHOPIFY_ADMIN_TOKEN='')
    @patch('httpx.put')
    def test_sync_catalogue_no_op_sans_cle_aucun_appel_reseau(self, mock_put):
        resultat = shopify.sync_catalogue(self.company)

        self.assertTrue(resultat['skipped'])
        self.assertEqual(resultat['reason'], 'no_api_key')
        mock_put.assert_not_called()

    @override_settings(SHOPIFY_ADMIN_TOKEN='')
    def test_webhook_hmac_false_sans_secret(self):
        self.assertFalse(shopify.verify_webhook_hmac(b'{}', 'peu-importe'))

    @override_settings(SHOPIFY_ADMIN_TOKEN='')
    def test_endpoint_webhook_503_sans_cle(self):
        resp = self.client.post(
            '/api/django/ecommerce-connect/shopify/webhook/commande/',
            data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 503)


@override_settings(SHOPIFY_ADMIN_TOKEN='fake-test-token-never-real')
class SyncCatalogueTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.connexion = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
            boutique_url='https://ma-boutique-test.myshopify.com', actif=True)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 500W',
            prix_vente=Decimal('1500.00'), quantite_stock=42, seuil_alerte=5)
        self.mapping = ProduitSync.objects.create(
            company=self.company, connexion=self.connexion,
            produit_id=self.produit.id, vendable_en_ligne=True,
            external_product_id='999')

    def test_sans_connexion_active_no_op(self):
        self.connexion.actif = False
        self.connexion.save(update_fields=['actif'])

        resultat = shopify.sync_catalogue(self.company)
        self.assertTrue(resultat['skipped'])
        self.assertEqual(resultat['reason'], 'no_connexion')

    @patch('httpx.put')
    def test_push_catalogue_avec_mock_http(self, mock_put):
        mock_put.return_value = MagicMock(status_code=200)

        resultat = shopify.sync_catalogue(self.company)

        self.assertFalse(resultat['skipped'])
        self.assertEqual(resultat['pushed'], 1)
        mock_put.assert_called_once()
        _, kwargs = mock_put.call_args
        self.assertEqual(
            kwargs['json']['product']['variants'][0]['price'], '1500.00')
        self.mapping.refresh_from_db()
        self.assertEqual(self.mapping.dernier_statut, ProduitSync.Statut.OK)

    @patch('httpx.put')
    def test_produit_non_vendable_en_ligne_jamais_pousse(self, mock_put):
        self.mapping.vendable_en_ligne = False
        self.mapping.save(update_fields=['vendable_en_ligne'])

        shopify.sync_catalogue(self.company)
        mock_put.assert_not_called()

    @patch('httpx.put')
    def test_echec_http_marque_erreur_sans_lever(self, mock_put):
        mock_put.return_value = MagicMock(status_code=500)

        resultat = shopify.sync_catalogue(self.company)

        self.assertEqual(resultat['errors'], 1)
        self.mapping.refresh_from_db()
        self.assertEqual(self.mapping.dernier_statut, ProduitSync.Statut.ERREUR)


class VerifyWebhookHmacTests(TestCase):
    @override_settings(SHOPIFY_WEBHOOK_SECRET='secret-de-test')
    def test_signature_valide_acceptee(self):
        body = b'{"id": 1}'
        digest = hmac.new(
            b'secret-de-test', body, hashlib.sha256).digest()
        header = base64.b64encode(digest).decode('utf-8')

        self.assertTrue(shopify.verify_webhook_hmac(body, header))

    @override_settings(SHOPIFY_WEBHOOK_SECRET='secret-de-test')
    def test_signature_invalide_rejetee(self):
        self.assertFalse(shopify.verify_webhook_hmac(b'{"id": 1}', 'faux'))


@override_settings(SHOPIFY_ADMIN_TOKEN='fake-test-token-never-real')
class TraiterWebhookCommandeTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.connexion = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
            boutique_url='https://ma-boutique-test.myshopify.com', actif=True)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Alaoui', email='client@example.com')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW',
            prix_vente=Decimal('4000.00'), quantite_stock=10, seuil_alerte=1)

    def test_commande_payee_cree_facture_paiement_et_decremente_stock(self):
        commande = shopify.traiter_webhook_commande(
            company=self.company, external_order_id='SHOP-1001',
            montant_ttc=Decimal('4000.00'),
            email_client='client@example.com',
            lignes=[{'produit_id': self.produit.id, 'quantite': 2}])

        self.assertEqual(commande.statut, CommandeSync.Statut.TRAITEE)
        self.assertIsNotNone(commande.facture_id)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 8)

    def test_webhook_rejoue_idempotent_pas_de_doublon(self):
        c1 = shopify.traiter_webhook_commande(
            company=self.company, external_order_id='SHOP-2002',
            montant_ttc=Decimal('4000.00'),
            email_client='client@example.com', lignes=[])
        c2 = shopify.traiter_webhook_commande(
            company=self.company, external_order_id='SHOP-2002',
            montant_ttc=Decimal('4000.00'),
            email_client='client@example.com', lignes=[])

        self.assertEqual(c1.id, c2.id)
        self.assertEqual(
            CommandeSync.objects.filter(
                connexion=self.connexion, external_order_id='SHOP-2002',
            ).count(), 1)

    def test_client_introuvable_erreur_sans_facture(self):
        commande = shopify.traiter_webhook_commande(
            company=self.company, external_order_id='SHOP-3003',
            montant_ttc=Decimal('100.00'),
            email_client='inconnu@example.com', lignes=[])

        self.assertEqual(commande.statut, CommandeSync.Statut.ERREUR)
        self.assertIsNone(commande.facture_id)

    def test_endpoint_webhook_signature_hmac_bout_en_bout(self):
        payload = {
            'id': 'SHOP-4004', 'total_price': '100.00',
            'email': 'client@example.com', 'line_items': [],
        }
        body = json.dumps(payload).encode('utf-8')
        with override_settings(SHOPIFY_WEBHOOK_SECRET='secret-e2e'):
            digest = hmac.new(b'secret-e2e', body, hashlib.sha256).digest()
            header = base64.b64encode(digest).decode('utf-8')
            resp = self.client.post(
                '/api/django/ecommerce-connect/shopify/webhook/commande/',
                data=body, content_type='application/json',
                HTTP_X_SHOPIFY_HMAC_SHA256=header,
                HTTP_X_SHOPIFY_SHOP_DOMAIN='ma-boutique-test.myshopify.com')

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            CommandeSync.objects.filter(
                connexion=self.connexion, external_order_id='SHOP-4004',
            ).exists())

    def test_endpoint_webhook_signature_invalide_401(self):
        body = json.dumps({'id': 'SHOP-5005'}).encode('utf-8')
        with override_settings(SHOPIFY_WEBHOOK_SECRET='secret-e2e'):
            resp = self.client.post(
                '/api/django/ecommerce-connect/shopify/webhook/commande/',
                data=body, content_type='application/json',
                HTTP_X_SHOPIFY_HMAC_SHA256='signature-invalide')

        self.assertEqual(resp.status_code, 401)
        self.assertFalse(
            CommandeSync.objects.filter(
                external_order_id='SHOP-5005').exists())

    def test_isolation_multi_tenant(self):
        autre_company = _company('Autre Société Shopify')
        ConnexionEcommerce.objects.create(
            company=autre_company,
            plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
            boutique_url='https://autre-boutique.myshopify.com', actif=True)

        commande = shopify.traiter_webhook_commande(
            company=autre_company, external_order_id='SHOP-9009',
            montant_ttc=Decimal('50.00'), email_client='', lignes=[])

        # Aucun client dans `autre_company` (email vide) : erreur propre,
        # ET surtout jamais rattaché à la connexion de `self.company`.
        self.assertEqual(commande.statut, CommandeSync.Statut.ERREUR)
        self.assertNotEqual(commande.connexion_id, self.connexion.id)
