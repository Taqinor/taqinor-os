"""AUD806 — `PaymentTransaction.rafraichir` n'émettait JAMAIS
`payment_captured` ; et montant/cible restaient modifiables jusqu'à capture.

Constat d'origine :

* `core/payment.marquer_paye` — SEUL émetteur de `payment_captured`, seul à
  poser `paye_le` — n'avait AUCUN appelant de production (grep exhaustif :
  seulement des tests). Le seul chemin qui écrivait `statut` était
  `core/views.rafraichir`, par écriture DIRECTE
  (`save(update_fields=['statut','updated_at'])`), sans `paye_le` ni
  événement : `apps/ventes/receivers._materialize_paiement_on_payment_captured`
  ne s'exécutait donc JAMAIS en production. Le PSP confirmait, l'opérateur
  cliquait « Rafraîchir » → transaction « payée » mais aucun `Paiement` créé,
  la facture restait « émise » et partait en relance ;
* `core/serializers` laissait `montant`/`content_type`/`object_id` modifiables
  (`IsAuthenticated` seul) jusqu'à capture — un PATCH avant capture repointait
  la transaction sur une AUTRE facture de la même société : l'argent de Dupont
  soldait la facture d'Alami.

Corriger l'un sans l'autre ARME le défaut : si `statut='paye'` est posé
d'abord, le garde d'idempotence de `marquer_paye` (statut déjà PAYÉ → return)
avale l'événement à jamais. `rafraichir` appelle donc `marquer_paye` À LA PLACE
de l'écriture directe, jamais « en plus ».

La MATÉRIALISATION du `Paiement` (couture côté ventes, AUD102) est vérifiée
dans `apps/ventes/tests/test_aud806_capture_rafraichir_bout_en_bout.py` :
`core` n'importe jamais une app métier, pas même depuis ses tests.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import payment as payment_infra
from core.event_coverage import ALLOWED_UNCONSUMED
from core.events import payment_captured
from core.models import PaymentTransaction
from core.views import PaymentTransactionViewSet

User = get_user_model()


class _ProviderPaye:
    """Bouchon PSP : la transaction est confirmée « payée »."""

    def fetch_status(self, transaction):
        return {'ok': True, 'statut': PaymentTransaction.STATUT_PAYE,
                'external_ref': 'PSP-AUD806'}


class _ProviderEnAttente:
    def fetch_status(self, transaction):
        return {'ok': True, 'statut': PaymentTransaction.STATUT_EN_ATTENTE}


class Aud806RafraichirCaptureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUD806 SARL')
        cls.responsable = User.objects.create_user(
            username='aud806_resp', password='x', company=cls.company,
            role_legacy='responsable')
        cls.simple = User.objects.create_user(
            username='aud806_simple', password='x', company=cls.company,
            role_legacy='normal')
        cls.factory = APIRequestFactory()

    def setUp(self):
        self.tx = PaymentTransaction.objects.create(
            company=self.company, provider='cmi', montant=Decimal('1200.00'),
            statut=PaymentTransaction.STATUT_EN_ATTENTE)
        self.recus = []
        payment_captured.connect(
            lambda sender, **kw: self.recus.append(kw),
            dispatch_uid='aud806_spy')
        self.addCleanup(payment_captured.disconnect,
                        dispatch_uid='aud806_spy')

    def _rafraichir(self, acteur, provider):
        req = self.factory.post(f'/paiements-en-ligne/{self.tx.pk}/rafraichir/')
        force_authenticate(req, user=acteur)
        with mock.patch.object(payment_infra, '_provider_for',
                               return_value=provider):
            return PaymentTransactionViewSet.as_view(
                {'post': 'rafraichir'})(req, pk=self.tx.pk)

    # ── 1. La capture émet enfin l'événement ──────────────────────────────
    def test_rafraichir_paye_emet_exactement_un_payment_captured(self):
        resp = self._rafraichir(self.responsable, _ProviderPaye())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(self.recus), 1)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.statut, PaymentTransaction.STATUT_PAYE)
        self.assertIsNotNone(self.tx.paye_le)
        self.assertEqual(self.tx.external_ref, 'PSP-AUD806')

    def test_second_rafraichir_ne_re_emet_pas(self):
        self._rafraichir(self.responsable, _ProviderPaye())
        self.recus.clear()
        self._rafraichir(self.responsable, _ProviderPaye())
        self.assertEqual(self.recus, [])

    def test_un_statut_non_paye_reste_une_ecriture_directe(self):
        resp = self._rafraichir(self.responsable, _ProviderEnAttente())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.recus, [])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.statut,
                         PaymentTransaction.STATUT_EN_ATTENTE)
        self.assertIsNone(self.tx.paye_le)

    # ── 2. Montant et cible figés après l'initiation ──────────────────────
    def _patch(self, acteur, corps):
        req = self.factory.patch(
            f'/paiements-en-ligne/{self.tx.pk}/', corps, format='json')
        force_authenticate(req, user=acteur)
        return PaymentTransactionViewSet.as_view(
            {'patch': 'partial_update'})(req, pk=self.tx.pk)

    def test_patch_object_id_sur_transaction_en_attente_refuse(self):
        avant = self.tx.object_id
        resp = self._patch(self.responsable, {'object_id': 4242})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.object_id, avant)

    def test_patch_montant_sur_transaction_en_attente_refuse(self):
        resp = self._patch(self.responsable, {'montant': '1.00'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.montant, Decimal('1200.00'))

    def test_patch_montant_reste_possible_tant_que_la_transaction_est_initiee(
            self):
        self.tx.statut = PaymentTransaction.STATUT_INITIE
        self.tx.save(update_fields=['statut'])
        resp = self._patch(self.responsable, {'montant': '999.00'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.montant, Decimal('999.00'))

    # ── 3. Garde de rôle remontée ─────────────────────────────────────────
    def test_un_compte_sans_palier_ne_capture_plus(self):
        resp = self._rafraichir(self.simple, _ProviderPaye())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.recus, [])

    def test_la_lecture_reste_ouverte(self):
        req = self.factory.get('/paiements-en-ligne/')
        force_authenticate(req, user=self.simple)
        resp = PaymentTransactionViewSet.as_view({'get': 'list'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ── 4. Commentaire de couverture d'événements corrigé ─────────────────
    def test_payment_captured_n_est_plus_reserve_sans_abonne(self):
        """`apps/ventes` s'y abonne depuis YLEDG12 : le laisser en
        `ALLOWED_UNCONSUMED` masquait l'absence d'ÉMETTEUR de production."""
        self.assertNotIn('payment_captured', ALLOWED_UNCONSUMED)
