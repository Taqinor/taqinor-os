"""AUD806 (couture ventes, @after AUD102) — « Rafraîchir » sur une transaction
confirmée par le PSP crée enfin le `Paiement` et solde la facture.

Le récepteur `_materialize_paiement_on_payment_captured` (YLEDG12) existait,
mais `core/views.rafraichir` écrivait `statut` DIRECTEMENT au lieu d'appeler
`core.payment.marquer_paye` : `payment_captured` n'était jamais émis en
production, donc AUCUN `Paiement` n'était créé et la facture restait « émise »
puis partait en relance.

Ce module vérifie la chaîne COMPLÈTE depuis l'endpoint, côté ventes (le test
`core/tests/test_aud806_capture_rafraichir.py` couvre l'émission elle-même —
`core` n'importe jamais une app métier). AUD102 est consommé tel quel : le
récepteur solde la facture par le service unique
`domain.encaissements.marquer_facture_soldee`.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from authentication.models import Company
from core import payment as core_payment
from core.models import PaymentTransaction
from core.views import PaymentTransactionViewSet

User = get_user_model()


class _ProviderPaye:
    def fetch_status(self, transaction):
        return {'ok': True, 'statut': PaymentTransaction.STATUT_PAYE,
                'external_ref': 'PSP-AUD806-E2E'}


class Aud806CaptureBoutEnBoutTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aud806-ventes-co', defaults={'nom': 'AUD806 Ventes Co'})[0]
        self.operateur = User.objects.create_user(
            username='aud806_operateur', password='x', company=self.company,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alami', prenom='S',
            email='aud806@example.com', telephone='+212600000806')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-AUD806',
            prix_vente=Decimal('5000'), quantite_stock=5,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD806-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('5000'), taux_tva=Decimal('20.00'))
        self.tx = core_payment.creer_transaction(
            self.company, montant=Decimal('6000'), target=self.facture)
        self.tx.statut = PaymentTransaction.STATUT_EN_ATTENTE
        self.tx.save(update_fields=['statut'])
        self.factory = APIRequestFactory()

    def _rafraichir(self):
        req = self.factory.post(
            f'/paiements-en-ligne/{self.tx.pk}/rafraichir/')
        force_authenticate(req, user=self.operateur)
        with mock.patch.object(core_payment, '_provider_for',
                               return_value=_ProviderPaye()):
            return PaymentTransactionViewSet.as_view(
                {'post': 'rafraichir'})(req, pk=self.tx.pk)

    def test_rafraichir_cree_le_paiement_et_solde_la_facture(self):
        resp = self._rafraichir()
        self.assertEqual(resp.status_code, 200)

        paiements = Paiement.objects.filter(facture=self.facture)
        self.assertEqual(paiements.count(), 1)
        self.assertEqual(paiements.first().montant, Decimal('6000'))
        self.assertEqual(paiements.first().mode, Paiement.Mode.CARTE)

        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)

        self.tx.refresh_from_db()
        self.assertEqual(self.tx.statut, PaymentTransaction.STATUT_PAYE)
        self.assertIsNotNone(self.tx.paye_le)

    def test_un_second_rafraichir_ne_duplique_pas_le_paiement(self):
        self._rafraichir()
        self._rafraichir()
        self.assertEqual(
            Paiement.objects.filter(facture=self.facture).count(), 1)
