"""Tests YLEDG2 — stock émet ``facture_fournisseur_creee``/
``paiement_fournisseur_enregistre`` (M6) aux points de création canoniques
(FactureFournisseurViewSet.perform_create / PaiementFournisseurViewSet.
perform_create), pose du seam pour compta.ecriture_pour_facture_fournisseur/
ecriture_pour_paiement_fournisseur — jamais d'import de compta ici.

Run:
    python manage.py test apps.stock.test_yledg2_events -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import FactureFournisseur, Fournisseur, PaiementFournisseur
from core.events import facture_fournisseur_creee, paiement_fournisseur_enregistre

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Catcher:
    def __init__(self):
        self.calls = []

    def __call__(self, sender, instance, company, **kwargs):
        self.calls.append((instance.pk, company.id))


class TestYledg2Events(TestCase):
    def setUp(self):
        self.company = _company('yledg2-stock-co')
        self.user = _user(
            self.company, 'yledg2-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YLEDG2')

    def test_creating_facture_fournisseur_emits_event_once(self):
        catcher = _Catcher()
        facture_fournisseur_creee.connect(
            catcher, dispatch_uid='test_yledg2_ff')
        try:
            resp = self.api.post(
                '/api/django/stock/factures-fournisseur/', {
                    'fournisseur': self.fournisseur.id,
                    'montant_ht': '1000', 'montant_tva': '200',
                    'montant_ttc': '1200', 'date_facture': '2026-07-01',
                }, format='json')
        finally:
            facture_fournisseur_creee.disconnect(
                dispatch_uid='test_yledg2_ff')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(catcher.calls), 1)
        facture = FactureFournisseur.objects.get(
            company=self.company, fournisseur=self.fournisseur)
        self.assertEqual(catcher.calls[0], (facture.id, self.company.id))

    def test_creating_paiement_fournisseur_emits_event_once(self):
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-YLEDG2S-0001',
            fournisseur=self.fournisseur, montant_ttc=Decimal('1200'))
        catcher = _Catcher()
        paiement_fournisseur_enregistre.connect(
            catcher, dispatch_uid='test_yledg2_paiement')
        try:
            resp = self.api.post(
                '/api/django/stock/paiements-fournisseur/', {
                    'facture': facture.id, 'montant': '1200',
                }, format='json')
        finally:
            paiement_fournisseur_enregistre.disconnect(
                dispatch_uid='test_yledg2_paiement')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(catcher.calls), 1)
        paiement = PaiementFournisseur.objects.get(facture=facture)
        self.assertEqual(catcher.calls[0], (paiement.id, self.company.id))
