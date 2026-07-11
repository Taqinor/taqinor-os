"""FG53 — Lien « Payer en ligne » (PaymentLink) + provider NoOp + webhook.

Couvre :
  * l'action « lien-paiement » crée un lien (montant figé = reste à payer),
    réutilise un lien valide existant, et refuse une facture soldée/annulée,
  * la page publique « pay » expose le minimum (montant/référence/statut),
    jamais de prix d'achat,
  * le webhook (provider NoOp) enregistre un Paiement, solde la facture, et est
    IDEMPOTENT (un double appel ne crée pas deux paiements),
  * le provider par défaut est NoOp (aucune dépendance externe).

Run :
    python manage.py test apps.ventes.tests.test_payment_link -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Facture, LigneFacture, Paiement, PaymentLink,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='pl-co', nom='PL Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


# Le throttle public s'appuie sur le cache (Redis en prod) ; en test on bascule
# sur un cache LocMem en mémoire pour ne dépendre d'aucun service externe.
@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PaymentLinkTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='pluser', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.public = APIClient()  # sans auth — endpoints publics
        self.cl = Client.objects.create(
            company=self.company, nom='PL', prenom='Client',
            email='pl@example.com', telephone='+212600000002',
            adresse='Rabat')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-PL',
            prix_vente=Decimal('1000'), quantite_stock=10)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        # total_ttc = 1000 + 200 = 1200

    def _create_link(self):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/lien-paiement/')

    def test_create_link_freezes_amount(self):
        resp = self._create_link()
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['provider'], 'noop')
        self.assertEqual(Decimal(resp.data['montant']), Decimal('1200.00'))
        self.assertIn('/api/django/public/pay/', resp.data['pay_url'])
        self.assertTrue(PaymentLink.objects.filter(
            facture=self.facture).exists())

    def test_create_link_reuses_valid(self):
        r1 = self._create_link()
        r2 = self._create_link()
        self.assertEqual(r1.data['token'], r2.data['token'])
        self.assertEqual(PaymentLink.objects.filter(
            facture=self.facture).count(), 1)

    def test_create_link_refuses_paid_facture(self):
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200.00'), date_paiement=timezone.localdate(),
            mode=Paiement.Mode.VIREMENT)
        resp = self._create_link()
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_pay_page_exposes_minimum(self):
        link_token = self._create_link().data['token']
        resp = self.public.get(f'/api/django/public/pay/{link_token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['reference'], self.facture.reference)
        self.assertEqual(Decimal(resp.data['montant']), Decimal('1200.00'))
        self.assertFalse(resp.data['paye'])
        # Jamais de prix d'achat / marge dans la charge utile publique.
        self.assertNotIn('prix_achat', resp.data)

    def test_webhook_noop_never_confirms_payment(self):
        """QX3 [SÉCURITÉ] — le webhook public NoOp ne solde JAMAIS une facture.

        Sans passerelle réelle vérifiant une signature, un POST non authentifié
        (même avec un ``provider_ref`` ou un ``montant`` forgé) ne peut pas
        fabriquer un ``Paiement`` ni faire passer la facture à PAYEE."""
        link_token = self._create_link().data['token']
        # POST forgé : provider_ref ET montant fabriqués — doit être refusé.
        resp = self.public.post(
            f'/api/django/public/pay/{link_token}/webhook/',
            {'provider_ref': 'FORGED', 'montant': '1200.00'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(Paiement.objects.filter(
            facture=self.facture).count(), 0)
        self.facture.refresh_from_db()
        self.assertNotEqual(self.facture.statut, Facture.Statut.PAYEE)
        link = PaymentLink.objects.get(token=link_token)
        self.assertNotEqual(link.statut, PaymentLink.Statut.PAYE)

    def test_webhook_empty_body_cannot_mark_paid(self):
        """QX3 [SÉCURITÉ] — ``POST {}`` ne peut jamais marquer payé."""
        link_token = self._create_link().data['token']
        resp = self.public.post(
            f'/api/django/public/pay/{link_token}/webhook/', {},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(Paiement.objects.filter(
            facture=self.facture).count(), 0)
        self.facture.refresh_from_db()
        self.assertNotEqual(self.facture.statut, Facture.Statut.PAYEE)

    def test_noop_verify_webhook_is_fail_closed(self):
        """QX3 — l'unité ``NoOpProvider.verify_webhook`` renvoie paid=False."""
        from apps.ventes.payments.providers import NoOpProvider
        link = self._create_link()
        link_obj = PaymentLink.objects.get(token=link.data['token'])
        result = NoOpProvider().verify_webhook(
            link_obj, {'paid': True, 'montant': '9999', 'provider_ref': 'X'})
        self.assertFalse(result['paid'])
        self.assertIsNone(result['montant'])

    def test_real_provider_path_still_confirms(self):
        """QX3 — un vrai fournisseur (mocké paid=True) enregistre bien un
        paiement, avec le montant SERVEUR (link.montant), jamais le payload."""
        from unittest import mock
        link_token = self._create_link().data['token']
        fake = mock.Mock()
        # Le fournisseur confirme mais ne renvoie PAS de montant → serveur.
        fake.verify_webhook.return_value = {
            'paid': True, 'provider_ref': 'REAL-TX', 'montant': None}
        with mock.patch(
                'apps.ventes.payments.providers.get_provider',
                return_value=fake):
            resp = self.public.post(
                f'/api/django/public/pay/{link_token}/webhook/',
                {'montant': '999999'}, format='json')  # payload forgé ignoré
        self.assertEqual(resp.status_code, 200, resp.content)
        paiements = Paiement.objects.filter(facture=self.facture)
        self.assertEqual(paiements.count(), 1)
        # Montant = reste à payer serveur (1200), jamais le 999999 forgé.
        self.assertEqual(paiements.first().montant, Decimal('1200.00'))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)

    def test_webhook_bad_token_404(self):
        resp = self.public.post(
            '/api/django/public/pay/deadbeefnope/webhook/', {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_noop_provider_is_default(self):
        from apps.ventes.payments.providers import get_provider
        self.assertEqual(get_provider(None).key, 'noop')
        self.assertEqual(get_provider('inconnu').key, 'noop')
