"""Tests FG370 — passerelle de paiement carte en ligne (CMI / Payzone).

Couvre :
  * création : company imposée côté serveur (jamais du corps), initiation
    no-op propre tant qu'aucun compte marchand n'est configuré ;
  * isolation société : aucune transaction d'une autre société ;
  * statut/redirect en lecture seule (pas réécrits par PATCH) ;
  * connecteurs gated : non configurés → aucun appel réseau, statut « initié » ;
  * capture : ``marquer_paye`` émet ``payment_captured`` (idempotent) ;
  * découplage : aucun import d'app domaine.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import payment as payment_infra
from core.events import payment_captured
from core.integrations import TYPE_PAYMENT, get_provider_class
from core.models import PaymentTransaction
from core.views import PaymentTransactionViewSet

User = get_user_model()


class PaymentProviderRegistryTests(TestCase):
    def test_cmi_and_payzone_registered(self):
        self.assertIsNotNone(get_provider_class(TYPE_PAYMENT, 'cmi'))
        self.assertIsNotNone(get_provider_class(TYPE_PAYMENT, 'payzone'))

    def test_unconfigured_provider_is_noop(self):
        cls = get_provider_class(TYPE_PAYMENT, 'cmi')
        provider = cls()  # aucune config / secret
        self.assertFalse(provider.is_configured())
        res = provider.create_payment(transaction=None)
        self.assertFalse(res['ok'])


class PaymentTransactionFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.user = User.objects.create_user(
            username='u1', password='x', company=cls.company)

    def test_creer_transaction_imposes_company_and_defaults_cmi(self):
        tx = payment_infra.creer_transaction(
            self.company, montant=Decimal('1000.00'))
        self.assertEqual(tx.company, self.company)
        self.assertEqual(tx.provider, 'cmi')
        self.assertEqual(tx.statut, PaymentTransaction.STATUT_INITIE)

    def test_initier_noop_when_unconfigured(self):
        tx = payment_infra.creer_transaction(
            self.company, montant=Decimal('500.00'))
        payment_infra.initier(tx)
        tx.refresh_from_db()
        # Pas de compte marchand → reste initié, jamais d'appel réseau.
        self.assertEqual(tx.statut, PaymentTransaction.STATUT_INITIE)
        self.assertIn('non configuré', tx.detail.get('detail', ''))

    def test_marquer_paye_emits_event_once(self):
        tx = payment_infra.creer_transaction(
            self.company, montant=Decimal('200.00'))
        received = []

        def _handler(sender, transaction, company, **kwargs):
            received.append(transaction.pk)

        payment_captured.connect(_handler)
        try:
            payment_infra.marquer_paye(tx, external_ref='PSP-1')
            payment_infra.marquer_paye(tx)  # idempotent : pas de ré-émission
        finally:
            payment_captured.disconnect(_handler)
        tx.refresh_from_db()
        self.assertEqual(tx.statut, PaymentTransaction.STATUT_PAYE)
        self.assertEqual(tx.external_ref, 'PSP-1')
        self.assertIsNotNone(tx.paye_le)
        self.assertEqual(received, [tx.pk])


class PaymentTransactionViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other_co = Company.objects.create(nom='Autre')
        cls.user = User.objects.create_user(
            username='u1', password='x', company=cls.company)
        cls.factory = APIRequestFactory()

    def test_create_sets_company_and_initiates(self):
        req = self.factory.post(
            '/paiements-en-ligne/',
            {'montant': '750.00', 'provider': 'cmi'}, format='json')
        force_authenticate(req, user=self.user)
        view = PaymentTransactionViewSet.as_view({'post': 'create'})
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        tx = PaymentTransaction.objects.get(pk=resp.data['id'])
        self.assertEqual(tx.company, self.company)
        # statut en lecture seule + initiation no-op : reste « initié ».
        self.assertEqual(tx.statut, PaymentTransaction.STATUT_INITIE)

    def test_company_isolation(self):
        PaymentTransaction.objects.create(
            company=self.other_co, montant=Decimal('1'), provider='cmi')
        req = self.factory.get('/paiements-en-ligne/')
        force_authenticate(req, user=self.user)
        view = PaymentTransactionViewSet.as_view({'get': 'list'})
        resp = view(req)
        ids = [row['id'] for row in resp.data.get('results', resp.data)]
        self.assertEqual(ids, [])
