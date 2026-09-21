"""Tests YHIRE13 — Dotation EPI -> décrément de stock (optionnel).

``EpiCatalogue.produit_id`` (référence, jamais de FK cross-app) : quand
renseigné, la création d'une ``DotationEpi`` décrémente le stock du produit
lié via ``apps.stock.services`` ; un catalogue non lié reste sans effet.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import DossierEmploye, EpiCatalogue
from apps.stock.models import MouvementStock, Produit

User = get_user_model()

DOT = '/api/django/rh/dotations-epi/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_produit(company, nom='Gants isolants', quantite_stock=10):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=100, quantite_stock=quantite_stock)


def make_epi(company, produit=None, designation='Gants isolants'):
    return EpiCatalogue.objects.create(
        company=company, type_epi='gants_isolants', designation=designation,
        produit_id=produit.id if produit else None)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DotationEpiStockTests(TestCase):
    def setUp(self):
        self.company = make_company('yh13-a', 'A')
        self.user = make_user(self.company, 'yh13-user')
        self.employe = make_employe(self.company, 'YH13-1')

    def test_epi_lie_decremente_stock(self):
        produit = make_produit(self.company, quantite_stock=10)
        epi = make_epi(self.company, produit=produit)
        resp = auth(self.user).post(DOT, {
            'employe': self.employe.id, 'epi': epi.id, 'quantite': 2,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 8)
        mvt = MouvementStock.objects.filter(produit=produit).first()
        self.assertIsNotNone(mvt)
        self.assertEqual(mvt.type_mouvement, MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(mvt.quantite, 2)

    def test_epi_non_lie_zero_effet(self):
        epi = make_epi(self.company, produit=None)
        resp = auth(self.user).post(DOT, {
            'employe': self.employe.id, 'epi': epi.id, 'quantite': 1,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(MouvementStock.objects.count(), 0)

    def test_service_creer_dotation_epi_idempotence_appel(self):
        produit = make_produit(self.company, quantite_stock=5)
        epi = make_epi(self.company, produit=produit)
        d1 = services.creer_dotation_epi(
            company=self.company, epi=epi, employe=self.employe, quantite=1,
            user=self.user)
        d2 = services.creer_dotation_epi(
            company=self.company, epi=epi, employe=self.employe, quantite=1,
            user=self.user)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 3)
        self.assertNotEqual(d1.id, d2.id)
        self.assertEqual(MouvementStock.objects.filter(produit=produit).count(), 2)

    def test_restitution_reintegre_stock(self):
        produit = make_produit(self.company, quantite_stock=10)
        epi = make_epi(self.company, produit=produit)
        dotation = services.creer_dotation_epi(
            company=self.company, epi=epi, employe=self.employe, quantite=3,
            user=self.user)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 7)

        resp = auth(self.user).post(f'{DOT}{dotation.id}/restituer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 10)
        dotation.refresh_from_db()
        self.assertTrue(dotation.restituee)

    def test_restitution_double_refusee(self):
        produit = make_produit(self.company, quantite_stock=10)
        epi = make_epi(self.company, produit=produit)
        dotation = services.creer_dotation_epi(
            company=self.company, epi=epi, employe=self.employe, quantite=1,
            user=self.user)
        services.restituer_dotation_epi(dotation, user=self.user)
        with self.assertRaises(services.RestitutionEpiError):
            services.restituer_dotation_epi(dotation, user=self.user)

    def test_isolation_tenant_produit_autre_societe(self):
        autre_company = make_company('yh13-b', 'B')
        produit_autre = make_produit(autre_company, quantite_stock=10)
        # produit_id référence une autre société : le sélecteur stock filtre
        # par company -> aucun effet stock (comportement sûr par défaut).
        epi = make_epi(self.company, produit=produit_autre)
        dotation = services.creer_dotation_epi(
            company=self.company, epi=epi, employe=self.employe, quantite=1,
            user=self.user)
        produit_autre.refresh_from_db()
        self.assertEqual(produit_autre.quantite_stock, 10)
        self.assertIsNotNone(dotation.id)
