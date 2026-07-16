"""Tests YDOCF4 — `facture_paid` (core/events.py) est émis EXACTEMENT une fois
au passage résiduel→0 d'une facture, sur les trois chemins d'encaissement
(enregistrer-paiement, record_payment_from_link, marquer-payee) ; un paiement
PARTIEL n'émet rien ; distinct de `payment_captured`."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes import services as ventes_services
from apps.ventes.models import Facture, LigneFacture, PaymentLink
from core.events import facture_paid

User = get_user_model()


def make_company(slug='ydocf4-co', nom='YDOCF4 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Listener:
    def __init__(self):
        self.calls = []

    def __call__(self, sender, facture, montant, company, **kwargs):
        self.calls.append((facture.id, montant, company.id))


class TestFacturePaidOnEnregistrerPaiement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ydocf4_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='F4',
            email='ydocf4@example.com', telephone='+212600000005')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YDOCF4',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YDOCF4-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        self.listener = _Listener()
        facture_paid.connect(self.listener, dispatch_uid='test_ydocf4_listener')
        self.addCleanup(
            facture_paid.disconnect, dispatch_uid='test_ydocf4_listener')

    def _pay(self, montant):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            f'enregistrer-paiement/',
            {'montant': montant, 'date_paiement': date.today().isoformat(),
             'mode': 'virement'}, format='json')

    def test_full_payment_emits_facture_paid_once(self):
        r = self._pay('6000')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(self.listener.calls), 1)
        fid, montant, cid = self.listener.calls[0]
        self.assertEqual(fid, self.facture.id)
        self.assertEqual(montant, Decimal('6000'))
        self.assertEqual(cid, self.company.id)

    def test_partial_payment_emits_nothing(self):
        r = self._pay('1000')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(self.listener.calls), 0)

    def test_marquer_payee_emits_facture_paid(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/marquer-payee/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(self.listener.calls), 1)
        self.assertEqual(self.listener.calls[0][0], self.facture.id)


class TestFacturePaidOnPaymentLink(TestCase):
    def setUp(self):
        self.company = make_company(slug='ydocf4-co2', nom='YDOCF4 Co2')
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='Link',
            email='ydocf4link@example.com', telephone='+212600000006')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie', sku='BAT-YDOCF4',
            prix_vente=Decimal('3000'), quantite_stock=10, tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YDOCF4-0002',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Batterie',
            quantite=Decimal('1'), prix_unitaire=Decimal('3000'),
            taux_tva=Decimal('20.00'))
        self.link = PaymentLink.objects.create(
            company=self.company, facture=self.facture, provider='noop',
            montant=self.facture.montant_du)
        self.listener = _Listener()
        facture_paid.connect(
            self.listener, dispatch_uid='test_ydocf4_link_listener')
        self.addCleanup(
            facture_paid.disconnect, dispatch_uid='test_ydocf4_link_listener')

    def test_record_payment_from_link_emits_facture_paid_once(self):
        # QX3 — NoOp est désormais fail-closed ; on simule un VRAI fournisseur
        # qui confirme le paiement (montant serveur) pour tester l'événement.
        from unittest import mock
        fake = mock.Mock()
        fake.verify_webhook.return_value = {
            'paid': True, 'provider_ref': 'REAL', 'montant': None}
        with mock.patch(
                'apps.ventes.payments.providers.get_provider',
                return_value=fake):
            paiement, err = ventes_services.record_payment_from_link(
                link=self.link, payload={})
            self.assertIsNone(err)
            self.assertIsNotNone(paiement)
            self.facture.refresh_from_db()
            self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
            self.assertEqual(len(self.listener.calls), 1)
            self.assertEqual(self.listener.calls[0][0], self.facture.id)

            # Idempotent re-verification (webhook retry) must not re-emit.
            paiement2, err2 = ventes_services.record_payment_from_link(
                link=self.link, payload={})
            self.assertIsNone(err2)
            self.assertEqual(paiement2.id, paiement.id)
            self.assertEqual(len(self.listener.calls), 1)
