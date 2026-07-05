"""Tests YLEDG1 — ventes émet ``paiement_enregistre``/``avoir_cree`` (M6) aux
points de création réels d'un Paiement/Avoir (pose du seam pour
compta.ecriture_pour_paiement/avoir, jamais d'import de compta ici)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, LigneFacture, Paiement
from core.events import avoir_cree, paiement_enregistre

User = get_user_model()


def make_company(slug='yledg1v-co', nom='YLEDG1V Co'):
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


class TestPaiementAvoirEvents(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='yledg1v_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L1V',
            email='yledg1v@example.com', telephone='+212600000031')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG1V',
            prix_vente=Decimal('5000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG1V-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('5000'), taux_tva=Decimal('20.00'))

    def test_enregistrer_paiement_emits_paiement_enregistre_once(self):
        catcher = _Catcher()
        paiement_enregistre.connect(
            catcher, dispatch_uid='test_yledg1v_paiement')
        try:
            r = self.api.post(
                f'/api/django/ventes/factures/{self.facture.id}/'
                f'enregistrer-paiement/',
                {'montant': '3000', 'date_paiement': date.today().isoformat(),
                 'mode': 'virement'}, format='json')
        finally:
            paiement_enregistre.disconnect(
                dispatch_uid='test_yledg1v_paiement')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(catcher.calls), 1)
        paiement_id = Paiement.objects.get(facture=self.facture).id
        self.assertEqual(catcher.calls[0], (paiement_id, self.company.id))

    def test_creer_avoir_emits_avoir_cree_once(self):
        catcher = _Catcher()
        avoir_cree.connect(catcher, dispatch_uid='test_yledg1v_avoir')
        try:
            r = self.api.post(
                f'/api/django/ventes/factures/{self.facture.id}/'
                f'creer-avoir/',
                {'motif': 'Retour matériel'}, format='json')
        finally:
            avoir_cree.disconnect(dispatch_uid='test_yledg1v_avoir')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(catcher.calls), 1)
        avoir_id = Avoir.objects.get(facture=self.facture).id
        self.assertEqual(catcher.calls[0], (avoir_id, self.company.id))

    def test_pos_enregistrer_paiement_service_emits_once(self):
        from apps.ventes.services import enregistrer_paiement
        catcher = _Catcher()
        paiement_enregistre.connect(
            catcher, dispatch_uid='test_yledg1v_pos_paiement')
        try:
            paiement = enregistrer_paiement(
                facture=self.facture, montant=Decimal('1000'),
                mode='virement', date_paiement=date.today(), user=None)
        finally:
            paiement_enregistre.disconnect(
                dispatch_uid='test_yledg1v_pos_paiement')
        self.assertEqual(len(catcher.calls), 1)
        self.assertEqual(catcher.calls[0], (paiement.id, self.company.id))
