"""AUD212 — webhook e-commerce non forgeable d'une société vers une autre.

Le défaut : le secret HMAC était une variable ``.env`` UNIQUE pour TOUTE la
plateforme (``SHOPIFY_WEBHOOK_SECRET`` / ``WOOCOMMERCE_WEBHOOK_SECRET``) et le
tenant était résolu depuis un EN-TÊTE CLIENT
(``_company_from_boutique_url``, ``boutique_url__icontains`` + ``.first()``
sans ordre déterministe). La société A, qui connaît légitimement ce secret
partagé, pouvait donc signer un POST valide et le faire atterrir dans le
tenant de B en changeant simplement l'en-tête — vraie Facture, vrai Paiement,
vraie sortie de stock chez B.

Le correctif : un secret PROPRE par ``ConnexionEcommerce`` et un tenant résolu
EXCLUSIVEMENT depuis la connexion dont ce secret a validé la signature.
L'en-tête de boutique n'est plus lu du tout (les tests le fournissent quand
même, pointé vers la MAUVAISE société, pour le prouver).
"""
import base64
import hashlib
import hmac
import json
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.ecommerce_connect import common, shopify, woocommerce
from apps.ecommerce_connect.models import CommandeSync, ConnexionEcommerce
from apps.stock.models import Produit
from apps.ventes.models import Facture
from authentication.models import Company

URL_WOO = '/api/django/ecommerce-connect/woocommerce/webhook/commande/'
URL_SHOPIFY = '/api/django/ecommerce-connect/shopify/webhook/commande/'


def _signer(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode('utf-8')


@override_settings(
    WOOCOMMERCE_CONSUMER_KEY='ck_fake', WOOCOMMERCE_CONSUMER_SECRET='cs_fake',
    SHOPIFY_ADMIN_TOKEN='fake-token')
class WebhookNonForgeableInterSocieteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.societe_a = Company.objects.create(nom='Société A (attaquante)')
        self.societe_b = Company.objects.create(nom='Société B (victime)')

        self.connexion_a = ConnexionEcommerce.objects.create(
            company=self.societe_a,
            plateforme=ConnexionEcommerce.Plateforme.WOOCOMMERCE,
            boutique_url='https://boutique-a.example.com', actif=True,
            webhook_secret='secret-propre-de-A')
        self.connexion_b = ConnexionEcommerce.objects.create(
            company=self.societe_b,
            plateforme=ConnexionEcommerce.Plateforme.WOOCOMMERCE,
            boutique_url='https://boutique-b.example.com', actif=True,
            webhook_secret='secret-propre-de-B')

        self.client_a = Client.objects.create(
            company=self.societe_a, nom='Client A', email='a@example.com')
        self.client_b = Client.objects.create(
            company=self.societe_b, nom='Client B', email='b@example.com')
        self.produit_b = Produit.objects.create(
            company=self.societe_b, nom='Onduleur B', prix_vente=Decimal('100.00'),
            quantite_stock=10, seuil_alerte=1, tva=Decimal('20.00'))

    def _post_woo(self, secret, payload, source_header):
        body = json.dumps(payload).encode('utf-8')
        return self.client.post(
            URL_WOO, data=body, content_type='application/json',
            HTTP_X_WC_WEBHOOK_SIGNATURE=_signer(secret, body),
            HTTP_X_WC_WEBHOOK_SOURCE=source_header)

    def test_a_signe_avec_son_secret_mais_pointe_b_atterrit_chez_a(self):
        """LE scénario de la fiche : la commande ne doit JAMAIS toucher B."""
        resp = self._post_woo(
            'secret-propre-de-A',
            {'id': 'FORGE-1', 'status': 'completed', 'total': '100.00',
             'billing': {'email': 'b@example.com'},
             'line_items': [{'produit_id': self.produit_b.id, 'quantity': 5}]},
            # En-tête pointé vers la boutique de B — délibérément mensonger.
            'boutique-b.example.com')

        self.assertEqual(resp.status_code, 200)
        commande = CommandeSync.objects.get(external_order_id='FORGE-1')
        # Le tenant vient du SECRET, pas de l'en-tête.
        self.assertEqual(commande.company_id, self.societe_a.id)
        self.assertEqual(commande.connexion_id, self.connexion_a.id)
        # Et comme le client visé (b@example.com) n'existe pas chez A, la
        # commande finit en ERREUR pour rapprochement manuel — jamais une
        # facture posée d'autorité dans un tenant tiers.
        self.assertEqual(commande.statut, CommandeSync.Statut.ERREUR)
        # Rien n'a été créé chez B : ni commande, ni facture, ni sortie de stock.
        self.assertFalse(
            CommandeSync.objects.filter(company=self.societe_b).exists())
        self.assertFalse(
            Facture.objects.filter(company=self.societe_b).exists())
        self.produit_b.refresh_from_db()
        self.assertEqual(self.produit_b.quantite_stock, 10)

    def test_b_signe_avec_son_propre_secret_atterrit_chez_b(self):
        resp = self._post_woo(
            'secret-propre-de-B',
            {'id': 'LEGIT-B', 'status': 'completed', 'total': '100.00',
             'billing': {'email': 'b@example.com'}, 'line_items': []},
            # En-tête pointé vers A cette fois : toujours ignoré.
            'boutique-a.example.com')

        self.assertEqual(resp.status_code, 200)
        commande = CommandeSync.objects.get(external_order_id='LEGIT-B')
        self.assertEqual(commande.company_id, self.societe_b.id)
        self.assertEqual(commande.connexion_id, self.connexion_b.id)

    def test_secret_inconnu_401_sans_effet_de_bord(self):
        resp = self._post_woo(
            'secret-qui-nexiste-nulle-part',
            {'id': 'FORGE-2', 'status': 'completed', 'total': '100.00',
             'billing': {'email': 'b@example.com'}, 'line_items': []},
            'boutique-b.example.com')

        self.assertEqual(resp.status_code, 401)
        self.assertFalse(CommandeSync.objects.exists())

    def test_connexion_sans_secret_nest_jamais_signataire(self):
        """Fail-closed : la migration laisse les connexions existantes à ''."""
        self.connexion_b.webhook_secret = ''
        self.connexion_b.save(update_fields=['webhook_secret'])

        resp = self._post_woo(
            '',
            {'id': 'FORGE-3', 'status': 'completed', 'total': '100.00',
             'billing': {'email': 'b@example.com'}, 'line_items': []},
            'boutique-b.example.com')

        self.assertEqual(resp.status_code, 401)
        self.assertFalse(CommandeSync.objects.exists())

    def test_connexion_inactive_nest_jamais_signataire(self):
        self.connexion_a.actif = False
        self.connexion_a.save(update_fields=['actif'])

        resp = self._post_woo(
            'secret-propre-de-A',
            {'id': 'FORGE-4', 'status': 'completed', 'total': '100.00',
             'billing': {'email': 'a@example.com'}, 'line_items': []},
            'boutique-a.example.com')

        self.assertEqual(resp.status_code, 401)
        self.assertFalse(CommandeSync.objects.exists())

    def test_entete_absent_ne_bloque_plus_un_webhook_signe(self):
        """L'en-tête n'entre plus dans la résolution : son absence est inerte."""
        body = json.dumps(
            {'id': 'SANS-ENTETE', 'status': 'completed', 'total': '100.00',
             'billing': {'email': 'a@example.com'}, 'line_items': []},
        ).encode('utf-8')
        resp = self.client.post(
            URL_WOO, data=body, content_type='application/json',
            HTTP_X_WC_WEBHOOK_SIGNATURE=_signer('secret-propre-de-A', body))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            CommandeSync.objects.get(
                external_order_id='SANS-ENTETE').company_id,
            self.societe_a.id)

    def test_meme_isolation_cote_shopify(self):
        ConnexionEcommerce.objects.create(
            company=self.societe_a,
            plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
            boutique_url='https://a.myshopify.com', actif=True,
            webhook_secret='shop-secret-A')
        ConnexionEcommerce.objects.create(
            company=self.societe_b,
            plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
            boutique_url='https://b.myshopify.com', actif=True,
            webhook_secret='shop-secret-B')
        body = json.dumps(
            {'id': 'SHOP-FORGE', 'financial_status': 'paid',
             'total_price': '100.00', 'email': 'b@example.com',
             'line_items': []},
        ).encode('utf-8')

        resp = self.client.post(
            URL_SHOPIFY, data=body, content_type='application/json',
            HTTP_X_SHOPIFY_HMAC_SHA256=_signer('shop-secret-A', body),
            HTTP_X_SHOPIFY_SHOP_DOMAIN='b.myshopify.com')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            CommandeSync.objects.get(
                external_order_id='SHOP-FORGE').company_id,
            self.societe_a.id)


class ConnexionParSignatureUniteTests(TestCase):
    """Unités de ``common.connexion_par_signature`` (AUD212)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Société unité AUD212')
        self.connexion = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.SHOPIFY,
            boutique_url='https://u.myshopify.com', actif=True,
            webhook_secret='u-secret')

    def test_entete_vide_refuse(self):
        self.assertIsNone(common.connexion_par_signature(
            shopify.PLATEFORME, b'{}', ''))

    def test_plateforme_croisee_refusee(self):
        body = b'{"id": 1}'
        header = _signer('u-secret', body)

        self.assertIsNone(common.connexion_par_signature(
            woocommerce.PLATEFORME, body, header))
        self.assertEqual(
            common.connexion_par_signature(shopify.PLATEFORME, body, header),
            self.connexion)

    def test_corps_modifie_invalide_la_signature(self):
        body = b'{"id": 1}'
        header = _signer('u-secret', body)

        self.assertIsNone(common.connexion_par_signature(
            shopify.PLATEFORME, b'{"id": 2}', header))
