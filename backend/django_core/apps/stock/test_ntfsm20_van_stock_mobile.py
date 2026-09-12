"""NTFSM20 — Écran mobile van-stock technicien (backend).

Critère d'acceptation testé : un technicien voit UNIQUEMENT le stock de sa
propre camionnette, jamais celui d'un collègue (filtré par emplacement
affecté, résolu côté serveur via la chaîne flotte — jamais un id
d'emplacement accepté depuis le client).

Run :
    python manage.py test apps.stock.test_ntfsm20_van_stock_mobile -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.flotte.models import AffectationConducteur, Conducteur, Vehicule
from apps.stock.models import (
    EmplacementStock, Produit, StockEmplacement, TransfertStock,
)
from apps.stock.selectors import emplacement_camionnette_technicien

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    user, _ = User.objects.get_or_create(
        username=username, defaults={'company': company, 'role_legacy': role})
    return user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def affecter_camionnette(company, technicien, emplacement, immat):
    vehicule = Vehicule.objects.create(
        company=company, immatriculation=immat,
        emplacement_stock_id=emplacement.id)
    conducteur = Conducteur.objects.create(
        company=company, user=technicien, nom=technicien.username, actif=True)
    AffectationConducteur.objects.create(
        company=company, conducteur=conducteur, vehicule=vehicule,
        date_debut=datetime.date(2026, 1, 1), actif=True)
    return vehicule, conducteur


class TestEmplacementCamionnetteTechnicien(TestCase):
    def setUp(self):
        self.company = make_company('ntfsm20-co', 'NTFSM20 Co')
        self.tech = make_user(self.company, 'ntfsm20_tech')
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.van = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette Tech', is_principal=False)

    def test_no_assignment_returns_none(self):
        result = emplacement_camionnette_technicien(self.company, self.tech)
        self.assertIsNone(result)

    def test_resolves_assigned_camionnette(self):
        affecter_camionnette(self.company, self.tech, self.van, 'AA-1-BB')
        result = emplacement_camionnette_technicien(self.company, self.tech)
        self.assertEqual(result.id, self.van.id)

    def test_ended_assignment_is_not_resolved(self):
        vehicule, conducteur = affecter_camionnette(
            self.company, self.tech, self.van, 'AA-2-BB')
        affectation = AffectationConducteur.objects.get(
            conducteur=conducteur, vehicule=vehicule)
        affectation.date_fin = datetime.date(2025, 12, 31)
        affectation.save(update_fields=['date_fin'])
        result = emplacement_camionnette_technicien(self.company, self.tech)
        self.assertIsNone(result)


class TestVanStockMobileEndpoints(TestCase):
    def setUp(self):
        self.company = make_company('ntfsm20-view-co', 'NTFSM20 View Co')
        self.tech1 = make_user(self.company, 'ntfsm20_tech1')
        self.tech2 = make_user(self.company, 'ntfsm20_tech2')
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.van1 = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette 1', is_principal=False)
        self.van2 = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette 2', is_principal=False)
        self.produit1 = Produit.objects.create(
            company=self.company, nom='Onduleur A',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=10)
        self.produit2 = Produit.objects.create(
            company=self.company, nom='Onduleur B',
            prix_vente=Decimal('1200'), prix_achat=Decimal('800'),
            quantite_stock=10)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit1,
            emplacement=self.van1, quantite=4, seuil_min=2, seuil_max=8)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit2,
            emplacement=self.van2, quantite=5, seuil_min=2, seuil_max=8)
        affecter_camionnette(self.company, self.tech1, self.van1, 'T1-VAN')
        affecter_camionnette(self.company, self.tech2, self.van2, 'T2-VAN')

    def test_mon_stock_sans_affectation_est_propre(self):
        tech3 = make_user(self.company, 'ntfsm20_tech3')
        r = auth(tech3).get('/api/django/stock/emplacements/van-stock/mon-stock/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['emplacement'])
        self.assertEqual(r.data['produits'], [])

    def test_technicien_voit_uniquement_sa_propre_camionnette(self):
        r1 = auth(self.tech1).get(
            '/api/django/stock/emplacements/van-stock/mon-stock/')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data['emplacement']['id'], self.van1.id)
        produits1 = [p['produit_id'] for p in r1.data['produits']]
        self.assertIn(self.produit1.id, produits1)
        self.assertNotIn(self.produit2.id, produits1)

        r2 = auth(self.tech2).get(
            '/api/django/stock/emplacements/van-stock/mon-stock/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['emplacement']['id'], self.van2.id)
        produits2 = [p['produit_id'] for p in r2.data['produits']]
        self.assertIn(self.produit2.id, produits2)
        self.assertNotIn(self.produit1.id, produits2)

    def test_signaler_manquant_cree_une_demande_sur_sa_propre_camionnette(self):
        r = auth(self.tech1).post(
            '/api/django/stock/emplacements/van-stock/signaler-manquant/',
            {'produit_id': self.produit1.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['destination'], self.van1.id)
        self.assertEqual(r.data['source'], self.principal.id)
        self.assertEqual(r.data['statut'], TransfertStock.Statut.DEMANDE)

    def test_signaler_manquant_ne_duplique_pas(self):
        r1 = auth(self.tech1).post(
            '/api/django/stock/emplacements/van-stock/signaler-manquant/',
            {'produit_id': self.produit1.id}, format='json')
        r2 = auth(self.tech1).post(
            '/api/django/stock/emplacements/van-stock/signaler-manquant/',
            {'produit_id': self.produit1.id}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(TransfertStock.objects.count(), 1)

    def test_signaler_manquant_sans_affectation_refuse(self):
        tech3 = make_user(self.company, 'ntfsm20_tech3')
        r = auth(tech3).post(
            '/api/django/stock/emplacements/van-stock/signaler-manquant/',
            {'produit_id': self.produit1.id}, format='json')
        self.assertEqual(r.status_code, 400)
