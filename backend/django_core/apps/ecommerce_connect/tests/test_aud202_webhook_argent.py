"""AUD202 — le webhook e-commerce ne facture plus faux.

Quatre défauts d'argent, tous ROUGES avant le correctif :

1. taux de TVA figé à ``Decimal('20.00')`` dans ``common.py`` — jamais dérivé
   de ``Produit.tva``, alors que le catalogue solaire porte 10 % sur les
   panneaux PV ;
2. topic WooCommerce générique ``order.updated`` traité comme un paiement sans
   jamais lire ``status`` — une commande ANNULÉE produisait une Facture émise,
   un Paiement encaissé et une sortie de stock (idem Shopify sans
   ``financial_status``) ;
3. devise du payload injectée telle quelle dans une facture MAD ;
4. sortie de stock TRONQUÉE (``max(avant - quantite, 0)``) au lieu d'être
   refusée — le registre devenait incohérent avec lui-même
   (``quantite ≠ quantite_avant − quantite_apres``).
"""
import base64
import hashlib
import hmac
import json
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.ecommerce_connect import common, shopify, woocommerce
from apps.ecommerce_connect.models import CommandeSync, ConnexionEcommerce
from apps.stock.models import MouvementStock, Produit
from apps.ventes.models import Facture
from authentication.models import Company

WOO_URL = 'https://boutique-aud202.example.com'
SHOP_URL = 'https://boutique-aud202.myshopify.com'


def _signer(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode('utf-8')


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Société AUD202')
        self.connexion_woo = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.WOOCOMMERCE,
            boutique_url=WOO_URL, actif=True)
        self.connexion_shopify = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
            boutique_url=SHOP_URL, actif=True)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Bennani', email='aud202@example.com')
        # Panneau PV : TVA 10 % (le taux imposé par `seed_catalogue`).
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550W', prix_vente=Decimal('1100.00'),
            quantite_stock=20, seuil_alerte=2, tva=Decimal('10.00'))
        # Accessoire : TVA 20 %.
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble solaire 6mm²',
            prix_vente=Decimal('120.00'), quantite_stock=50, seuil_alerte=5,
            tva=Decimal('20.00'))


class TvaDeriveeDuProduitTests(_Base):
    """Défaut n°1 — la TVA vient de ``Produit.tva``, plus de 20 % en dur."""

    def test_panneau_pv_facture_a_10_pourcent(self):
        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='AUD202-TVA-1',
            montant_ttc=Decimal('1100.00'),
            email_client='aud202@example.com',
            lignes=[{'produit_id': self.panneau.id, 'quantite': 1}])

        self.assertEqual(commande.statut, CommandeSync.Statut.TRAITEE)
        facture = Facture.objects.get(id=commande.facture_id)
        self.assertEqual(facture.taux_tva, Decimal('10.00'))
        # 1100 TTC à 10 % → 1000,00 HT + 100,00 TVA (et non 916,67 + 183,33).
        self.assertEqual(facture.montant_ht, Decimal('1000.00'))
        self.assertEqual(facture.montant_tva, Decimal('100.00'))

    def test_accessoire_reste_a_20_pourcent(self):
        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='AUD202-TVA-2',
            montant_ttc=Decimal('120.00'),
            email_client='aud202@example.com',
            lignes=[{'produit_id': self.cable.id, 'quantite': 1}])

        facture = Facture.objects.get(id=commande.facture_id)
        self.assertEqual(facture.taux_tva, Decimal('20.00'))
        self.assertEqual(facture.montant_ht, Decimal('100.00'))

    def test_produit_sans_taux_replie_sur_le_defaut_du_modele(self):
        sans_taux = Produit.objects.create(
            company=self.company, nom='Prestation pose', prix_vente=Decimal('600.00'),
            quantite_stock=0, seuil_alerte=0)

        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='AUD202-TVA-3',
            montant_ttc=Decimal('120.00'),
            email_client='aud202@example.com',
            lignes=[{'produit_id': sans_taux.id, 'quantite': 0}])

        facture = Facture.objects.get(id=commande.facture_id)
        self.assertEqual(facture.taux_tva, common.TAUX_TVA_DEFAUT)

    def test_taux_mixtes_sans_montant_de_ligne_refuse(self):
        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='AUD202-TVA-4',
            montant_ttc=Decimal('1220.00'),
            email_client='aud202@example.com',
            lignes=[{'produit_id': self.panneau.id, 'quantite': 1},
                    {'produit_id': self.cable.id, 'quantite': 1}])

        self.assertEqual(commande.statut, CommandeSync.Statut.ERREUR)
        self.assertIsNone(commande.facture_id)
        self.assertIn('mixtes', commande.message)
        self.assertFalse(
            Facture.objects.filter(company=self.company).exists())

    def test_taux_mixtes_avec_montants_de_ligne_ventiles(self):
        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='AUD202-TVA-5',
            montant_ttc=Decimal('1220.00'),
            email_client='aud202@example.com',
            lignes=[
                {'produit_id': self.panneau.id, 'quantite': 1,
                 'montant_ttc': '1100.00'},
                {'produit_id': self.cable.id, 'quantite': 1,
                 'montant_ttc': '120.00'},
            ])

        self.assertEqual(commande.statut, CommandeSync.Statut.TRAITEE)
        facture = Facture.objects.get(id=commande.facture_id)
        # 1000,00 (panneau HT) + 100,00 (câble HT) = 1100,00 HT ; TVA 120,00.
        self.assertEqual(facture.montant_ht, Decimal('1100.00'))
        self.assertEqual(facture.montant_tva, Decimal('120.00'))
        self.assertEqual(
            facture.montant_ht + facture.montant_tva, Decimal('1220.00'))


@override_settings(
    WOOCOMMERCE_CONSUMER_KEY='ck_fake', WOOCOMMERCE_CONSUMER_SECRET='cs_fake',
    WOOCOMMERCE_WEBHOOK_SECRET='secret-aud202-woo')
class StatutWooCommerceTests(_Base):
    """Défaut n°2 — `order.updated` n'est PAS un signal de paiement."""

    URL = '/api/django/ecommerce-connect/woocommerce/webhook/commande/'

    def _post(self, payload):
        body = json.dumps(payload).encode('utf-8')
        return self.client.post(
            self.URL, data=body, content_type='application/json',
            HTTP_X_WC_WEBHOOK_SIGNATURE=_signer('secret-aud202-woo', body),
            HTTP_X_WC_WEBHOOK_SOURCE='boutique-aud202.example.com')

    def test_commande_annulee_refusee_sans_facture_ni_paiement_ni_stock(self):
        resp = self._post({
            'id': 'AUD202-WOO-CANCEL', 'status': 'cancelled', 'total': '1100.00',
            'billing': {'email': 'aud202@example.com'},
            'line_items': [{'produit_id': self.panneau.id, 'quantity': 1}],
        })

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(CommandeSync.objects.filter(
            external_order_id='AUD202-WOO-CANCEL').exists())
        self.assertFalse(Facture.objects.filter(company=self.company).exists())
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)

    def test_commande_remboursee_refusee(self):
        resp = self._post({
            'id': 'AUD202-WOO-REFUND', 'status': 'refunded', 'total': '10.00',
            'billing': {'email': 'aud202@example.com'}, 'line_items': [],
        })
        self.assertEqual(resp.status_code, 400)

    def test_statut_absent_refuse_fail_closed(self):
        resp = self._post({
            'id': 'AUD202-WOO-NOSTATUS', 'total': '10.00',
            'billing': {'email': 'aud202@example.com'}, 'line_items': [],
        })
        self.assertEqual(resp.status_code, 400)

    def test_commande_completed_traitee(self):
        resp = self._post({
            'id': 'AUD202-WOO-OK', 'status': 'completed', 'total': '1100.00',
            'billing': {'email': 'aud202@example.com'},
            'line_items': [{'produit_id': self.panneau.id, 'quantity': 1}],
        })

        self.assertEqual(resp.status_code, 200)
        commande = CommandeSync.objects.get(external_order_id='AUD202-WOO-OK')
        self.assertEqual(commande.statut, CommandeSync.Statut.TRAITEE)

    def test_devise_etrangere_refusee(self):
        resp = self._post({
            'id': 'AUD202-WOO-EUR', 'status': 'completed', 'total': '100.00',
            'currency': 'EUR',
            'billing': {'email': 'aud202@example.com'}, 'line_items': [],
        })

        self.assertEqual(resp.status_code, 400)
        self.assertIn('EUR', resp.json()['detail'])
        self.assertFalse(CommandeSync.objects.filter(
            external_order_id='AUD202-WOO-EUR').exists())

    def test_devise_mad_acceptee(self):
        resp = self._post({
            'id': 'AUD202-WOO-MAD', 'status': 'completed', 'total': '100.00',
            'currency': 'MAD',
            'billing': {'email': 'aud202@example.com'}, 'line_items': [],
        })
        self.assertEqual(resp.status_code, 200)


@override_settings(
    SHOPIFY_ADMIN_TOKEN='fake-token', SHOPIFY_WEBHOOK_SECRET='secret-aud202-shop')
class StatutShopifyTests(_Base):
    """Défaut n°2 (versant Shopify) — `financial_status` est LU."""

    URL = '/api/django/ecommerce-connect/shopify/webhook/commande/'

    def _post(self, payload):
        body = json.dumps(payload).encode('utf-8')
        return self.client.post(
            self.URL, data=body, content_type='application/json',
            HTTP_X_SHOPIFY_HMAC_SHA256=_signer('secret-aud202-shop', body),
            HTTP_X_SHOPIFY_SHOP_DOMAIN='boutique-aud202.myshopify.com')

    def test_commande_pending_refusee(self):
        resp = self._post({
            'id': 'AUD202-SHOP-PENDING', 'financial_status': 'pending',
            'total_price': '1100.00', 'email': 'aud202@example.com',
            'line_items': [{'produit_id': self.panneau.id, 'quantity': 1}],
        })

        self.assertEqual(resp.status_code, 400)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)

    def test_commande_refunded_refusee(self):
        resp = self._post({
            'id': 'AUD202-SHOP-REFUND', 'financial_status': 'refunded',
            'total_price': '10.00', 'email': 'aud202@example.com',
            'line_items': [],
        })
        self.assertEqual(resp.status_code, 400)

    def test_commande_paid_traitee_a_la_tva_du_produit(self):
        resp = self._post({
            'id': 'AUD202-SHOP-PAID', 'financial_status': 'paid',
            'total_price': '1100.00', 'currency': 'MAD',
            'email': 'aud202@example.com',
            'line_items': [{'produit_id': self.panneau.id, 'quantity': 1}],
        })

        self.assertEqual(resp.status_code, 200)
        commande = CommandeSync.objects.get(external_order_id='AUD202-SHOP-PAID')
        facture = Facture.objects.get(id=commande.facture_id)
        self.assertEqual(facture.taux_tva, Decimal('10.00'))


class StockNonTronqueTests(_Base):
    """Défaut n°4 — une commande au-delà du stock est REFUSÉE, pas tronquée."""

    def test_quantite_superieure_au_stock_refusee(self):
        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='AUD202-STOCK-1',
            montant_ttc=Decimal('1100.00'),
            email_client='aud202@example.com',
            lignes=[{'produit_id': self.panneau.id, 'quantite': 25}])

        self.assertEqual(commande.statut, CommandeSync.Statut.ERREUR)
        self.assertIsNone(commande.facture_id)
        self.assertIn('Stock insuffisant', commande.message)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self.assertFalse(MouvementStock.objects.filter(
            reference='ECOM-AUD202-STOCK-1').exists())
        self.assertFalse(Facture.objects.filter(company=self.company).exists())

    def test_mouvement_reste_coherent_quand_le_stock_suffit(self):
        commande = woocommerce.traiter_webhook_commande(
            company=self.company, external_order_id='AUD202-STOCK-2',
            montant_ttc=Decimal('1100.00'),
            email_client='aud202@example.com',
            lignes=[{'produit_id': self.panneau.id, 'quantite': 4}])

        self.assertEqual(commande.statut, CommandeSync.Statut.TRAITEE)
        mouvement = MouvementStock.objects.get(reference='ECOM-AUD202-STOCK-2')
        self.assertEqual(
            mouvement.quantite,
            mouvement.quantite_avant - mouvement.quantite_apres)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 16)


class DeviseCompatibleTests(TestCase):
    def test_devise_absente_nest_pas_un_mismatch(self):
        self.assertTrue(common.devise_compatible(None))
        self.assertTrue(common.devise_compatible(''))

    def test_mad_insensible_a_la_casse(self):
        self.assertTrue(common.devise_compatible('mad'))
        self.assertTrue(common.devise_compatible(' MAD '))

    def test_devise_etrangere_refusee(self):
        self.assertFalse(common.devise_compatible('EUR'))
        self.assertFalse(common.devise_compatible('USD'))


class StatutHelpersTests(TestCase):
    def test_shopify_seul_paid_compte(self):
        self.assertTrue(shopify.commande_est_payee({'financial_status': 'paid'}))
        for statut in ('pending', 'authorized', 'partially_paid', 'refunded',
                       'partially_refunded', 'voided', ''):
            self.assertFalse(
                shopify.commande_est_payee({'financial_status': statut}),
                msg=statut)
        self.assertFalse(shopify.commande_est_payee({}))
        self.assertFalse(shopify.commande_est_payee(None))

    def test_woocommerce_processing_et_completed_seulement(self):
        for statut in ('processing', 'completed'):
            self.assertTrue(
                woocommerce.commande_est_payee({'status': statut}), msg=statut)
        for statut in ('pending', 'on-hold', 'cancelled', 'refunded', 'failed',
                       'trash', ''):
            self.assertFalse(
                woocommerce.commande_est_payee({'status': statut}), msg=statut)
        self.assertFalse(woocommerce.commande_est_payee({}))
        self.assertFalse(woocommerce.commande_est_payee(None))
