"""NTWMS33 — simulateur de capacité entrepôt (what-if).

Critère d'acceptation testé : simuler l'ajout de 200 unités dans une zone à
90 % de capacité affiche un AVERTISSEMENT DE DÉPASSEMENT — avant la réception
réelle, et sans rien réserver ni écrire.

Run :
    python manage.py test apps.stock.test_ntwms33_simuler_capacite -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, Produit
from apps.stock.selectors import simuler_capacite

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms33Base(TestCase):
    def setUp(self):
        from apps.installations.models import (
            BinAffectation, BinLocation, CategorieStockage,
        )

        self.company = make_company('ntwms33-co', 'NTWMS33 Co')
        self.autre = make_company('ntwms33-autre', 'NTWMS33 Autre')
        self.admin = User.objects.create_user(
            username='ntwms33_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS33', is_principal=True)
        categorie = CategorieStockage.objects.create(
            company=self.company, nom='Rayonnage 1000', qte_max=1000)
        self.bin_a = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-01', zone='A', allee='01', casier='01', ordre=10,
            categorie=categorie)
        # Zone sans catégorie : capacité INCONNUE, jamais devinée.
        self.bin_sans = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='S-01-01', zone='S', allee='01', casier='01', ordre=20)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550 Wc', sku='PAN550-NTWMS33',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=2000)
        # Zone A à 900/1000 = 90 %.
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_a, produit=self.produit,
            quantite=900)
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_sans, produit=self.produit,
            quantite=50)


class Ntwms33SimulationTests(Ntwms33Base):
    def test_ajouter_200_dans_une_zone_a_90pct_avertit_du_depassement(self):
        res = simuler_capacite(
            self.company, zone='A', quantite_supplementaire=200)

        self.assertEqual(res['taux_actuel_pct'], '90')
        self.assertEqual(res['occupe_projete'], 1100)
        self.assertEqual(res['taux_projete_pct'], '110')
        self.assertTrue(res['depassement'])
        self.assertEqual(res['unites_en_trop'], 100)
        self.assertIn('dépasserait sa capacité', res['avertissement'])

    def test_ajout_qui_tient_dans_la_zone_navertit_pas(self):
        res = simuler_capacite(
            self.company, zone='A', quantite_supplementaire=50)
        self.assertFalse(res['depassement'])
        self.assertEqual(res['unites_en_trop'], 0)
        self.assertEqual(res['avertissement'], '')
        self.assertEqual(res['taux_projete_pct'], '95')

    def test_simulation_nempile_aucune_ecriture(self):
        from apps.installations.models import BinAffectation

        avant = BinAffectation.objects.get(bin=self.bin_a).quantite
        simuler_capacite(self.company, zone='A', quantite_supplementaire=500)
        self.assertEqual(
            BinAffectation.objects.get(bin=self.bin_a).quantite, avant)

    def test_zone_sans_capacite_declaree_ne_declare_jamais_de_depassement(self):
        res = simuler_capacite(
            self.company, zone='S', quantite_supplementaire=10_000)
        self.assertIsNone(res['capacite'])
        self.assertIsNone(res['taux_projete_pct'])
        self.assertFalse(res['depassement'])

    def test_zone_inconnue_et_quantite_negative_sont_refusees(self):
        with self.assertRaises(ValueError):
            simuler_capacite(self.company, zone='ZZZ',
                             quantite_supplementaire=1)
        with self.assertRaises(ValueError):
            simuler_capacite(self.company, zone='A',
                             quantite_supplementaire=-5)
        with self.assertRaises(ValueError):
            simuler_capacite(self.company, zone='', quantite_supplementaire=1)

    def test_la_zone_dune_autre_societe_est_invisible(self):
        from apps.installations.models import BinLocation

        autre_emplacement = EmplacementStock.objects.create(
            company=self.autre, nom='Dépôt voisin', is_principal=True)
        BinLocation.objects.create(
            company=self.autre, emplacement=autre_emplacement,
            code='X-01-01', zone='X', allee='01', casier='01', ordre=10)

        with self.assertRaises(ValueError):
            simuler_capacite(self.company, zone='X',
                             quantite_supplementaire=1)


class Ntwms33EndpointTests(Ntwms33Base):
    URL = '/api/django/stock/simuler-capacite/'

    def test_endpoint_renvoie_lavertissement(self):
        res = auth(self.admin).get(
            self.URL, {'zone': 'A', 'quantite': 200})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['depassement'])
        self.assertEqual(res.data['taux_projete_pct'], '110')

    def test_zone_absente_renvoie_400_et_jamais_500(self):
        res = auth(self.admin).get(self.URL, {'quantite': 10})
        self.assertEqual(res.status_code, 400)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(
            APIClient().get(self.URL, {'zone': 'A'}).status_code, 401)
