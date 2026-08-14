"""NTWMS1 — localisation casier par casier d'un produit (`produits/{id}/casiers/`).

La hiérarchie zone/allée/casier existe DÉJÀ (`installations.BinLocation` /
`BinAffectation`, FG319 ; règles de rangement ZSTK9). NTWMS1 n'en crée pas un
double dans `stock` : il expose cette localisation sur la ressource PRODUIT du
module stock. Ces tests vérifient l'exposition ET l'isolation société.

Run :
    python manage.py test apps.stock.test_ntwms1_casiers -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit, EmplacementStock
from apps.stock.selectors import localisation_casiers

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms1Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation, BinAffectation

        self.company = make_company('ntwms1-co', 'NTWMS1 Co')
        self.autre = make_company('ntwms1-autre', 'NTWMS1 Autre')
        self.admin = User.objects.create_user(
            username='ntwms1_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS1', is_principal=True)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5-NTWMS1',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=20)
        # Deux casiers, volontairement créés dans le DÉSORDRE de parcours pour
        # prouver que la réponse est triée par `ordre`, pas par id.
        self.bin_loin = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement, code='B-02-07',
            zone='B', allee='02', casier='07', ordre=50)
        self.bin_proche = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement, code='A-01-03',
            zone='A', allee='01', casier='03', ordre=10)
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_loin, produit=self.produit,
            quantite=8)
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_proche, produit=self.produit,
            quantite=12)
        self.api = auth(self.admin)


class TestLocalisationCasiers(Ntwms1Base):
    def test_selecteur_trie_par_ordre_de_parcours(self):
        lignes = localisation_casiers(self.produit)
        self.assertEqual([ligne['code'] for ligne in lignes],
                         ['A-01-03', 'B-02-07'])
        self.assertEqual([ligne['quantite'] for ligne in lignes], [12, 8])
        self.assertEqual(lignes[0]['zone'], 'A')
        self.assertEqual(lignes[0]['emplacement_nom'], 'Dépôt NTWMS1')

    def test_produit_sans_casier_renvoie_liste_vide(self):
        vierge = Produit.objects.create(
            company=self.company, nom='Câble 6mm', sku='CAB6-NTWMS1',
            prix_achat=Decimal('5'), prix_vente=Decimal('9'))
        self.assertEqual(localisation_casiers(vierge), [])

    def test_casier_archive_exclu(self):
        self.bin_loin.archived = True
        self.bin_loin.save(update_fields=['archived'])
        codes = [ligne['code'] for ligne in localisation_casiers(self.produit)]
        self.assertEqual(codes, ['A-01-03'])

    def test_endpoint_expose_la_localisation(self):
        resp = self.api.get(f'/api/django/stock/produits/{self.produit.id}/casiers/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([ligne['code'] for ligne in resp.data],
                         ['A-01-03', 'B-02-07'])

    def test_isolation_societe_produit_d_une_autre_societe(self):
        intrus = User.objects.create_user(
            username='ntwms1_intrus', password='x', role_legacy='admin',
            company=self.autre)
        resp = auth(intrus).get(
            f'/api/django/stock/produits/{self.produit.id}/casiers/')
        self.assertEqual(resp.status_code, 404)
