"""Tests YEVNT6 — les transitions documentaires ventes en aval du devis
émettent chacune leur événement une fois (facture_emise/facture_payee/
facture_annulee/bon_commande_cree) sans changer aucun statut/PDF existant."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, Facture, LigneFacture
from core.events import (
    bon_commande_cree, facture_annulee, facture_emise, facture_payee,
)

User = get_user_model()


def make_company(slug='yevnt6-co', nom='YEVNT6 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Catcher:
    def __init__(self):
        self.calls = []

    def __call__(self, sender, instance, company, **kwargs):
        self.calls.append((instance.pk, company.id))


class TestFactureDocumentEvents(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='yevnt6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='E6',
            email='yevnt6@example.com', telephone='+212600000011')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YEVNT6',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))

    def _facture_brouillon(self, num=1):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-YEVNT6-{num:04d}',
            client=self.cl, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        return facture

    def test_emettre_emits_facture_emise_once(self):
        facture = self._facture_brouillon(1)
        catcher = _Catcher()
        facture_emise.connect(catcher, dispatch_uid='test_yevnt6_emise')
        try:
            r = self.api.post(
                f'/api/django/ventes/factures/{facture.id}/emettre/')
        finally:
            facture_emise.disconnect(dispatch_uid='test_yevnt6_emise')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(catcher.calls, [(facture.id, self.company.id)])
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)

    def test_enregistrer_paiement_emits_facture_payee_once(self):
        facture = self._facture_brouillon(2)
        facture.statut = Facture.Statut.EMISE
        facture.save(update_fields=['statut'])
        catcher = _Catcher()
        facture_payee.connect(catcher, dispatch_uid='test_yevnt6_payee')
        try:
            from datetime import date
            r = self.api.post(
                f'/api/django/ventes/factures/{facture.id}/'
                f'enregistrer-paiement/',
                {'montant': '6000', 'date_paiement': date.today().isoformat(),
                 'mode': 'virement'}, format='json')
        finally:
            facture_payee.disconnect(dispatch_uid='test_yevnt6_payee')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(catcher.calls), 1)
        self.assertEqual(catcher.calls[0][0], facture.id)

    def test_partial_payment_does_not_emit_facture_payee(self):
        facture = self._facture_brouillon(3)
        facture.statut = Facture.Statut.EMISE
        facture.save(update_fields=['statut'])
        catcher = _Catcher()
        facture_payee.connect(catcher, dispatch_uid='test_yevnt6_payee_partial')
        try:
            from datetime import date
            r = self.api.post(
                f'/api/django/ventes/factures/{facture.id}/'
                f'enregistrer-paiement/',
                {'montant': '1000', 'date_paiement': date.today().isoformat(),
                 'mode': 'virement'}, format='json')
        finally:
            facture_payee.disconnect(dispatch_uid='test_yevnt6_payee_partial')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(catcher.calls), 0)

    def test_annuler_emits_facture_annulee_once(self):
        facture = self._facture_brouillon(4)
        facture.statut = Facture.Statut.EMISE
        facture.save(update_fields=['statut'])
        catcher = _Catcher()
        facture_annulee.connect(catcher, dispatch_uid='test_yevnt6_annulee')
        try:
            r = self.api.post(
                f'/api/django/ventes/factures/{facture.id}/annuler/')
        finally:
            facture_annulee.disconnect(dispatch_uid='test_yevnt6_annulee')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(catcher.calls, [(facture.id, self.company.id)])
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.ANNULEE)


class TestBonCommandeCreeEvent(TestCase):
    def setUp(self):
        self.company = make_company(slug='yevnt6-co2', nom='YEVNT6 Co2')
        self.user = User.objects.create_user(
            username='yevnt6_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='BC',
            email='yevnt6bc@example.com', telephone='+212600000012')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-YEVNT6-0001',
            client=self.cl, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))

    def test_convertir_bc_emits_bon_commande_cree_once(self):
        catcher = _Catcher()
        bon_commande_cree.connect(catcher, dispatch_uid='test_yevnt6_bc')
        try:
            r = self.api.post(
                f'/api/django/ventes/devis/{self.devis.id}/convertir-bc/')
        finally:
            bon_commande_cree.disconnect(dispatch_uid='test_yevnt6_bc')
        self.assertEqual(r.status_code, 201, r.data)
        bc = BonCommande.objects.get(devis=self.devis)
        self.assertEqual(catcher.calls, [(bc.id, self.company.id)])
