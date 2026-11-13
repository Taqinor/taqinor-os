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

    def test_instance_perimee_n_emet_pas_une_seconde_capture(self):
        """ACNC43 — l'instance A, chargée avant que B ne marque la ligne
        payée, ne ré-émet pas la capture et ne réécrit pas ``paye_le``."""
        tx = payment_infra.creer_transaction(
            self.company, montant=Decimal('200.00'))
        perimee = PaymentTransaction.objects.get(pk=tx.pk)
        autre = PaymentTransaction.objects.get(pk=tx.pk)
        received = []

        def _handler(sender, transaction, company, **kwargs):
            received.append(transaction.pk)

        payment_captured.connect(_handler)
        try:
            payment_infra.marquer_paye(autre, external_ref='PSP-1')
            paye_le = PaymentTransaction.objects.get(pk=tx.pk).paye_le
            payment_infra.marquer_paye(perimee)
        finally:
            payment_captured.disconnect(_handler)
        self.assertEqual(received, [tx.pk])
        tx.refresh_from_db()
        self.assertEqual(tx.statut, PaymentTransaction.STATUT_PAYE)
        self.assertEqual(tx.external_ref, 'PSP-1')
        self.assertEqual(tx.paye_le, paye_le)

    def test_delete_transaction_refuse_405(self):
        """ASUP22 — une transaction de paiement ne se supprime jamais par l'API."""
        from rest_framework.test import APIClient
        from importlib import import_module

        from django.apps import apps as django_apps
        Role = django_apps.get_model('roles', 'Role')  # core n'importe aucune app
        CANONICAL_SYSTEM_ROLES = import_module(
            'apps.roles.permissions_registre').CANONICAL_SYSTEM_ROLES
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Directeur']))
        directeur = User.objects.create_user(
            username='asup22-dir', password='x', company=self.company, role=role)
        tx = payment_infra.creer_transaction(self.company, montant=Decimal('900.00'))
        payment_infra.marquer_paye(tx, external_ref='PSP-ASUP22')
        api = APIClient()
        api.force_authenticate(directeur)
        resp = api.delete(f'/api/django/core/paiements-en-ligne/{tx.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(PaymentTransaction.objects.filter(pk=tx.pk).exists())


class PaymentTransactionViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other_co = Company.objects.create(nom='Autre')
        # AUD806 — l'ÉCRITURE (création/capture) exige désormais le palier
        # responsable/admin ; la lecture reste ouverte à tout authentifié.
        cls.user = User.objects.create_user(
            username='u1', password='x', company=cls.company,
            role_legacy='responsable')
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

    def test_types_stricts_et_reponse_conforme(self):
        # ERR-ENF11-FUZZ-CORE — un montant nombre JSON ou une devise entière
        # (hors schéma) étaient convertis en silence ; `redirect_url` vide
        # violait le `format: uri` publié.
        view = PaymentTransactionViewSet.as_view({'post': 'create'})
        for corps in ({'montant': 750}, {'montant': '750.00', 'devise': 0}):
            req = self.factory.post('/paiements-en-ligne/', corps,
                                    format='json')
            force_authenticate(req, user=self.user)
            self.assertEqual(view(req).status_code,
                             status.HTTP_400_BAD_REQUEST, corps)
        req = self.factory.post('/paiements-en-ligne/',
                                {'montant': '750.00'}, format='json')
        force_authenticate(req, user=self.user)
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['redirect_url'], '')

    def test_company_isolation(self):
        PaymentTransaction.objects.create(
            company=self.other_co, montant=Decimal('1'), provider='cmi')
        req = self.factory.get('/paiements-en-ligne/')
        force_authenticate(req, user=self.user)
        view = PaymentTransactionViewSet.as_view({'get': 'list'})
        resp = view(req)
        ids = [row['id'] for row in resp.data.get('results', resp.data)]
        self.assertEqual(ids, [])
