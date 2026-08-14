"""NTDST18 — catalogue B2B temps réel (endpoint données).

Critère d'acceptation testé : DEUX CLIENTS avec des ``ListePrix`` différentes
reçoivent des PRIX DIFFÉRENTS pour le MÊME produit, sur le même appel
paramétré par client — et ``prix_achat`` n'apparaît JAMAIS dans la réponse.

Run :
    python manage.py test apps.stock.test_ntdst18_catalogue_b2b -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Categorie, Produit
from apps.stock.selectors_negoce import catalogue_b2b

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntdst18Base(TestCase):
    URL = '/api/django/stock/catalogue-b2b/'

    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import LignePrixListe, ListePrix

        self.company = make_company('ntdst18-co', 'NTDST18 Co')
        self.autre = make_company('ntdst18-autre', 'NTDST18 Autre')
        self.admin = User.objects.create_user(
            username='ntdst18_admin', password='x', role_legacy='admin',
            company=self.company)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs NTDST18')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5 kW', sku='OND5-NTDST18',
            categorie=self.categorie, marque='Deye',
            prix_achat=Decimal('7000'), prix_vente=Decimal('10000'),
            quantite_stock=15)
        self.autre_produit = Produit.objects.create(
            company=self.company, nom='Câble 6 mm²', sku='CAB6-NTDST18',
            prix_achat=Decimal('10'), prix_vente=Decimal('18'),
            quantite_stock=500)

        # Deux clients, deux listes de prix DIFFÉRENTES pour le même produit.
        liste_revendeur = ListePrix.objects.create(
            company=self.company, nom='Revendeur NTDST18')
        LignePrixListe.objects.create(
            liste=liste_revendeur, produit=self.produit,
            prix_unitaire=Decimal('8500'))
        liste_detail = ListePrix.objects.create(
            company=self.company, nom='Détail NTDST18')
        LignePrixListe.objects.create(
            liste=liste_detail, produit=self.produit,
            prix_unitaire=Decimal('9800'))

        self.client_revendeur = Client.objects.create(
            company=self.company, nom='Revendeur SARL',
            liste_prix=liste_revendeur)
        self.client_detail = Client.objects.create(
            company=self.company, nom='Client Détail',
            liste_prix=liste_detail)


class Ntdst18PrixTests(Ntdst18Base):
    def test_deux_clients_recoivent_deux_prix_differents(self):
        revendeur = catalogue_b2b(self.company, self.client_revendeur)
        detail = catalogue_b2b(self.company, self.client_detail)

        prix_revendeur = next(
            p['prix'] for p in revendeur['produits']
            if p['id'] == self.produit.id)
        prix_detail = next(
            p['prix'] for p in detail['produits']
            if p['id'] == self.produit.id)

        self.assertNotEqual(prix_revendeur, prix_detail)
        self.assertEqual(Decimal(prix_revendeur), Decimal('8500'))
        self.assertEqual(Decimal(prix_detail), Decimal('9800'))

    def test_sans_client_le_prix_standard_sapplique(self):
        res = catalogue_b2b(self.company, None)
        prix = next(p['prix'] for p in res['produits']
                    if p['id'] == self.produit.id)
        self.assertEqual(Decimal(prix), Decimal('10000'))

    def test_le_prix_dachat_napparait_jamais(self):
        res = catalogue_b2b(self.company, self.client_revendeur)
        for ligne in res['produits']:
            self.assertNotIn('prix_achat', ligne)
        self.assertNotIn('7000', str(res))

    def test_latp_accompagne_chaque_ligne(self):
        res = catalogue_b2b(self.company, self.client_revendeur)
        ligne = next(p for p in res['produits'] if p['id'] == self.produit.id)
        self.assertEqual(ligne['disponible_maintenant'], 15)
        self.assertIn('disponible_le', ligne)

    def test_filtres_categorie_marque_et_recherche(self):
        par_categorie = catalogue_b2b(
            self.company, None, categorie=self.categorie.id)
        self.assertEqual(len(par_categorie['produits']), 1)

        par_marque = catalogue_b2b(self.company, None, marque='deye')
        self.assertEqual(len(par_marque['produits']), 1)

        par_texte = catalogue_b2b(self.company, None, recherche='CAB6')
        self.assertEqual(par_texte['produits'][0]['sku'], 'CAB6-NTDST18')

    def test_la_pagination_est_bornee(self):
        res = catalogue_b2b(self.company, None, limite=1, offset=0)
        self.assertEqual(res['total'], 2)
        self.assertEqual(len(res['produits']), 1)
        suivant = catalogue_b2b(self.company, None, limite=1, offset=1)
        self.assertNotEqual(res['produits'][0]['id'],
                            suivant['produits'][0]['id'])

    def test_un_produit_archive_est_exclu(self):
        self.autre_produit.is_archived = True
        self.autre_produit.save(update_fields=['is_archived'])
        res = catalogue_b2b(self.company, None)
        self.assertEqual(res['total'], 1)

    def test_aucun_produit_dune_autre_societe(self):
        Produit.objects.create(
            company=self.autre, nom='Voisin', sku='VOISIN-DST18',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=1)
        res = catalogue_b2b(self.company, None)
        self.assertEqual(res['total'], 2)


class Ntdst18ApiTests(Ntdst18Base):
    def test_endpoint_parametre_par_client(self):
        api = auth(self.admin)
        revendeur = api.get(self.URL, {'client': self.client_revendeur.id})
        detail = api.get(self.URL, {'client': self.client_detail.id})
        self.assertEqual(revendeur.status_code, 200)

        prix_revendeur = next(
            p['prix'] for p in revendeur.data['produits']
            if p['id'] == self.produit.id)
        prix_detail = next(
            p['prix'] for p in detail.data['produits']
            if p['id'] == self.produit.id)
        self.assertNotEqual(prix_revendeur, prix_detail)

    def test_client_dune_autre_societe_renvoie_404(self):
        from apps.crm.models import Client

        voisin = Client.objects.create(company=self.autre, nom='Voisin')
        res = auth(self.admin).get(self.URL, {'client': voisin.id})
        self.assertEqual(res.status_code, 404)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self.URL).status_code, 401)
