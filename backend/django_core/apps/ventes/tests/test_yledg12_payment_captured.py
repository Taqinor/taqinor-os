"""Tests YLEDG12 — ventes s'abonne à `payment_captured` (core FG370) :
marquer payée une transaction ciblant une facture crée le paiement une seule
fois (recapture idempotente), statut facture recalculé, transaction sans
cible facture ignorée proprement, cross-company refusé."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from core import payment as core_payment
from core.models import PaymentTransaction

User = get_user_model()


def make_company(slug='yledg12-co', nom='YLEDG12 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestPaymentCapturedMaterializesPaiement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L12',
            email='yledg12@example.com', telephone='+212600000009')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG12',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG12-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def test_capture_targeting_facture_creates_paiement_once(self):
        tx = core_payment.creer_transaction(
            self.company, montant=Decimal('6000'), target=self.facture)
        core_payment.marquer_paye(tx, external_ref='PSP-REF-1')

        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        paiements = Paiement.objects.filter(facture=self.facture)
        self.assertEqual(paiements.count(), 1)
        self.assertEqual(paiements.first().montant, Decimal('6000'))

        # Recapture (idempotent) — marquer_paye elle-même est déjà
        # idempotente (statut déjà « paye »), mais on vérifie aussi qu'un
        # second envoi manuel du signal ne duplique pas le paiement.
        from core.events import payment_captured
        payment_captured.send(
            sender=PaymentTransaction, transaction=tx, company=self.company)
        self.assertEqual(
            Paiement.objects.filter(facture=self.facture).count(), 1)

    def test_capture_without_facture_target_ignored(self):
        tx = core_payment.creer_transaction(
            self.company, montant=Decimal('1000'))
        core_payment.marquer_paye(tx, external_ref='PSP-REF-2')
        self.assertEqual(Paiement.objects.count(), 0)

    def test_capture_bounds_montant_to_reste_du(self):
        tx = core_payment.creer_transaction(
            self.company, montant=Decimal('999999'), target=self.facture)
        core_payment.marquer_paye(tx, external_ref='PSP-REF-3')
        self.facture.refresh_from_db()
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(paiement.montant, Decimal('6000'))
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)

    def test_cross_company_target_ignored(self):
        other = make_company(slug='yledg12-co2', nom='YLEDG12 Co2')
        tx = core_payment.creer_transaction(
            self.company, montant=Decimal('6000'), target=self.facture)
        # Force la transaction dans une AUTRE société que sa cible.
        tx.company = other
        tx.save(update_fields=['company'])
        core_payment.marquer_paye(tx, external_ref='PSP-REF-4')
        self.assertEqual(Paiement.objects.filter(facture=self.facture).count(), 0)
