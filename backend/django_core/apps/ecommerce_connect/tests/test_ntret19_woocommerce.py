"""NTRET19 — connecteur WooCommerce [GATED: WooCommerce REST API].

Même architecture que NTRET18 (Shopify) : sans clé, structure + no-op TOTAL.
Le mapping commande→facture est PARTAGÉ via ``common.py`` (jamais dupliqué
entre ``shopify.py``/``woocommerce.py`` — testé explicitement ci-dessous)."""
import base64
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.ecommerce_connect import common, shopify, woocommerce
from apps.ecommerce_connect.models import (
    CommandeSync, ConnexionEcommerce, ProduitSync,
)
from apps.stock.models import Produit
from authentication.models import Company


def _company(nom='Société WooCommerce'):
    return Company.objects.create(nom=nom)


class SansCleApiNoOpTests(TestCase):
    def setUp(self):
        self.company = _company()

    @override_settings(
        WOOCOMMERCE_CONSUMER_KEY='', WOOCOMMERCE_CONSUMER_SECRET='')
    def test_is_configured_false_sans_cle(self):
        self.assertFalse(woocommerce.is_configured())

    @override_settings(WOOCOMMERCE_CONSUMER_KEY='ck_test_only')
    def test_is_configured_false_avec_une_seule_moitie_de_cle(self):
        # Consumer key SANS secret : toujours pas configuré (pas de demi-clé).
        self.assertFalse(woocommerce.is_configured())

    @override_settings(
        WOOCOMMERCE_CONSUMER_KEY='', WOOCOMMERCE_CONSUMER_SECRET='')
    @patch('httpx.put')
    def test_sync_catalogue_no_op_sans_cle_aucun_appel_reseau(self, mock_put):
        resultat = woocommerce.sync_catalogue(self.company)

        self.assertTrue(resultat['skipped'])
        self.assertEqual(resultat['reason'], 'no_api_key')
        mock_put.assert_not_called()

    @override_settings(
        WOOCOMMERCE_CONSUMER_KEY='', WOOCOMMERCE_CONSUMER_SECRET='')
    def test_webhook_signature_false_sans_secret(self):
        self.assertFalse(
            woocommerce.verify_webhook_signature(b'{}', 'peu-importe'))

    @override_settings(
        WOOCOMMERCE_CONSUMER_KEY='', WOOCOMMERCE_CONSUMER_SECRET='')
    def test_endpoint_webhook_503_sans_cle(self):
        resp = self.client.post(
            '/api/django/ecommerce-connect/woocommerce/webhook/commande/',
            data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 503)


@override_settings(
    WOOCOMMERCE_CONSUMER_KEY='ck_test_fake', WOOCOMMERCE_CONSUMER_SECRET='cs_test_fake')
class SyncCatalogueTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.connexion = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.WOOCOMMERCE,
            boutique_url='https://ma-boutique-woo-test.example.com', actif=True)
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh',
            prix_vente=Decimal('9000.00'), quantite_stock=7, seuil_alerte=1)
        self.mapping = ProduitSync.objects.create(
            company=self.company, connexion=self.connexion,
            produit_id=self.produit.id, vendable_en_ligne=True,
            external_product_id='42')

    def test_sans_connexion_active_no_op(self):
        self.connexion.actif = False
        self.connexion.save(update_fields=['actif'])

        resultat = woocommerce.sync_catalogue(self.company)
        self.assertTrue(resultat['skipped'])
        self.assertEqual(resultat['reason'], 'no_connexion')

    @patch('httpx.put')
    def test_push_catalogue_avec_mock_http_basic_auth(self, mock_put):
        mock_put.return_value = MagicMock(status_code=200)

        resultat = woocommerce.sync_catalogue(self.company)

        self.assertFalse(resultat['skipped'])
        self.assertEqual(resultat['pushed'], 1)
        _, kwargs = mock_put.call_args
        self.assertEqual(kwargs['auth'], ('ck_test_fake', 'cs_test_fake'))
        self.assertEqual(kwargs['json']['regular_price'], '9000.00')
        self.mapping.refresh_from_db()
        self.assertEqual(self.mapping.dernier_statut, ProduitSync.Statut.OK)

    @patch('httpx.put')
    def test_echec_http_marque_erreur_sans_lever(self, mock_put):
        mock_put.return_value = MagicMock(status_code=500)

        resultat = woocommerce.sync_catalogue(self.company)

        self.assertEqual(resultat['errors'], 1)
        self.mapping.refresh_from_db()
        self.assertEqual(self.mapping.dernier_statut, ProduitSync.Statut.ERREUR)


class VerifyWebhookSignatureTests(TestCase):
    @override_settings(WOOCOMMERCE_WEBHOOK_SECRET='secret-woo-test')
    def test_signature_valide_acceptee(self):
        body = b'{"id": 1}'
        digest = hmac.new(b'secret-woo-test', body, hashlib.sha256).digest()
        header = base64.b64encode(digest).decode('utf-8')

        self.assertTrue(woocommerce.verify_webhook_signature(body, header))

    @override_settings(WOOCOMMERCE_WEBHOOK_SECRET='secret-woo-test')
    def test_signature_invalide_rejetee(self):
        self.assertFalse(
            woocommerce.verify_webhook_signature(b'{"id": 1}', 'faux'))


@override_settings(
    WOOCOMMERCE_CONSUMER_KEY='ck_test_fake', WOOCOMMERCE_CONSUMER_SECRET='cs_test_fake')
class TraiterWebhookCommandeTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.connexion = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.WOOCOMMERCE,
            boutique_url='https://ma-boutique-woo-test.example.com', actif=True)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Idrissi', email='woo-client@example.com')
        self.produit = Produit.objects.create(
            company=self.company, nom='Régulateur MPPT',
            prix_vente=Decimal('1200.00'), quantite_stock=15, seuil_alerte=2)

    def test_commande_payee_cree_facture_paiement_et_decremente_stock(self):
        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='WOO-1001',
            montant_ttc=Decimal('1200.00'),
            email_client='woo-client@example.com',
            lignes=[{'produit_id': self.produit.id, 'quantite': 3}])

        self.assertEqual(commande.statut, CommandeSync.Statut.TRAITEE)
        self.assertIsNotNone(commande.facture_id)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 12)

    def test_webhook_rejoue_idempotent_pas_de_doublon(self):
        c1 = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='WOO-2002',
            montant_ttc=Decimal('1200.00'),
            email_client='woo-client@example.com', lignes=[])
        c2 = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='WOO-2002',
            montant_ttc=Decimal('1200.00'),
            email_client='woo-client@example.com', lignes=[])

        self.assertEqual(c1.id, c2.id)
        self.assertEqual(
            CommandeSync.objects.filter(
                connexion=self.connexion, external_order_id='WOO-2002',
            ).count(), 1)

    def test_client_introuvable_erreur_sans_facture(self):
        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='WOO-3003',
            montant_ttc=Decimal('100.00'),
            email_client='inconnu-woo@example.com', lignes=[])

        self.assertEqual(commande.statut, CommandeSync.Statut.ERREUR)
        self.assertIsNone(commande.facture_id)

    def test_endpoint_webhook_signature_bout_en_bout(self):
        payload = {
            'id': 'WOO-4004', 'total': '100.00',
            'billing': {'email': 'woo-client@example.com'}, 'line_items': [],
        }
        body = json.dumps(payload).encode('utf-8')
        with override_settings(WOOCOMMERCE_WEBHOOK_SECRET='secret-e2e-woo'):
            digest = hmac.new(b'secret-e2e-woo', body, hashlib.sha256).digest()
            header = base64.b64encode(digest).decode('utf-8')
            resp = self.client.post(
                '/api/django/ecommerce-connect/woocommerce/webhook/commande/',
                data=body, content_type='application/json',
                HTTP_X_WC_WEBHOOK_SIGNATURE=header,
                HTTP_X_WC_WEBHOOK_SOURCE='ma-boutique-woo-test.example.com')

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            CommandeSync.objects.filter(
                connexion=self.connexion, external_order_id='WOO-4004',
            ).exists())

    def test_endpoint_webhook_signature_invalide_401(self):
        body = json.dumps({'id': 'WOO-5005'}).encode('utf-8')
        with override_settings(WOOCOMMERCE_WEBHOOK_SECRET='secret-e2e-woo'):
            resp = self.client.post(
                '/api/django/ecommerce-connect/woocommerce/webhook/commande/',
                data=body, content_type='application/json',
                HTTP_X_WC_WEBHOOK_SIGNATURE='signature-invalide')

        self.assertEqual(resp.status_code, 401)
        self.assertFalse(
            CommandeSync.objects.filter(external_order_id='WOO-5005').exists())


class LogiquePartageeNonDupliqueeTests(TestCase):
    """NTRET19 — preuve que ``shopify.py``/``woocommerce.py`` appellent LA
    MÊME fonction ``common.traiter_commande_payee`` (jamais dupliquée) : un
    seul patch sur ``common`` affecte les DEUX connecteurs."""

    def setUp(self):
        self.company = _company()
        self.connexion_shopify = ConnexionEcommerce.objects.create(
            company=self.company, plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
            boutique_url='https://x.myshopify.com', actif=True)
        self.connexion_woo = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.WOOCOMMERCE,
            boutique_url='https://x-woo.example.com', actif=True)

    def test_shopify_et_woocommerce_delegue_a_common(self):
        sentinel = object()
        with patch.object(
                common, 'traiter_commande_payee',
                return_value=sentinel) as mocked:
            resultat_shopify = shopify.traiter_webhook_commande(
                company=self.company, external_order_id='X1',
                montant_ttc=Decimal('10.00'))
            resultat_woo = woocommerce.traiter_webhook_commande(
                company=self.company, external_order_id='X2',
                montant_ttc=Decimal('10.00'))

        self.assertIs(resultat_shopify, sentinel)
        self.assertIs(resultat_woo, sentinel)
        self.assertEqual(mocked.call_count, 2)
