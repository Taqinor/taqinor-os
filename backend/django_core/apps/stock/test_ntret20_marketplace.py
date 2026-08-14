"""NTRET20 — exports marketplace (Avito CSV, Google Shopping XML).

Critère d'acceptation testé : le flux généré est VALIDE au format cible (test
de STRUCTURE), il ne contient AUCUN prix d'achat, et un produit non marqué
vendable en ligne est EXCLU.

GATED : aucune intégration API n'est testée ici — la tâche ne livre que le
fichier prêt à importer (les comptes marchands Avito/Google restent une étape
manuelle du fondateur). Aucun appel réseau, aucune clé.

Run :
    python manage.py test apps.stock.test_ntret20_marketplace -v 2
"""
import csv
import io
from decimal import Decimal
from xml.etree import ElementTree

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.marketplace_feeds import (
    flux_avito_csv, flux_google_shopping_xml, generer_flux,
    produits_vendables_en_ligne,
)
from apps.stock.models import Categorie, Produit

User = get_user_model()

URL = '/api/django/stock/produits/export-marketplace/'
NS_G = '{http://base.google.com/ns/1.0}'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntret20Base(TestCase):
    def setUp(self):
        from apps.ecommerce_connect.models import (
            ConnexionEcommerce, ProduitSync,
        )

        self.company = make_company('ntret20-co', 'NTRET20 Co')
        self.autre = make_company('ntret20-autre', 'NTRET20 Autre')
        self.admin = User.objects.create_user(
            username='ntret20_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntret20_normal', password='x', role_legacy='normal',
            company=self.company)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs NTRET20')

        self.publie = Produit.objects.create(
            company=self.company, nom='Onduleur 5 kW', sku='OND5-NTRET20',
            categorie=self.categorie, marque='Deye',
            description='Onduleur hybride 5 kW',
            prix_achat=Decimal('7000'), prix_vente=Decimal('9900'),
            quantite_stock=8)
        self.non_publie = Produit.objects.create(
            company=self.company, nom='Pièce interne', sku='INT-NTRET20',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=3)

        self.connexion = ConnexionEcommerce.objects.create(
            company=self.company,
            plateforme=ConnexionEcommerce.Plateforme.values[0])
        ProduitSync.objects.create(
            company=self.company, connexion=self.connexion,
            produit_id=self.publie.id, vendable_en_ligne=True)
        ProduitSync.objects.create(
            company=self.company, connexion=self.connexion,
            produit_id=self.non_publie.id, vendable_en_ligne=False)


class Ntret20SelectionTests(Ntret20Base):
    def test_seuls_les_produits_vendables_en_ligne_sortent(self):
        skus = [p.sku for p in produits_vendables_en_ligne(self.company)]
        self.assertEqual(skus, ['OND5-NTRET20'])

    def test_sans_aucune_synchro_le_flux_est_vide_jamais_tout_le_catalogue(
            self):
        from apps.ecommerce_connect.models import ProduitSync

        ProduitSync.objects.all().delete()
        self.assertEqual(
            list(produits_vendables_en_ligne(self.company)), [])

    def test_un_produit_archive_est_exclu(self):
        self.publie.is_archived = True
        self.publie.save(update_fields=['is_archived'])
        self.assertEqual(
            list(produits_vendables_en_ligne(self.company)), [])

    def test_aucun_produit_dune_autre_societe(self):
        self.assertEqual(list(produits_vendables_en_ligne(self.autre)), [])


class Ntret20AvitoTests(Ntret20Base):
    def test_le_csv_a_len_tete_et_une_ligne_par_produit_publie(self):
        contenu = flux_avito_csv(self.company)
        lignes = list(csv.reader(io.StringIO(contenu)))

        self.assertEqual(lignes[0], [
            'sku', 'titre', 'description', 'prix', 'devise', 'categorie',
            'marque', 'quantite_disponible'])
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[1][0], 'OND5-NTRET20')
        self.assertEqual(lignes[1][3], '9900.00')
        self.assertEqual(lignes[1][4], 'MAD')

    def test_le_csv_ne_contient_aucun_prix_dachat(self):
        contenu = flux_avito_csv(self.company)
        self.assertNotIn('7000', contenu)
        self.assertNotIn('Pièce interne', contenu)


class Ntret20GoogleTests(Ntret20Base):
    def test_le_xml_est_un_rss_google_shopping_valide(self):
        contenu = flux_google_shopping_xml(
            self.company, titre_flux='Catalogue NTRET20')
        racine = ElementTree.fromstring(contenu)

        self.assertEqual(racine.tag, 'rss')
        self.assertEqual(racine.get('version'), '2.0')
        canal = racine.find('channel')
        articles = canal.findall('item')
        self.assertEqual(len(articles), 1)

        article = articles[0]
        self.assertEqual(article.find(f'{NS_G}id').text, 'OND5-NTRET20')
        self.assertEqual(article.find(f'{NS_G}price').text, '9900.00 MAD')
        self.assertEqual(article.find(f'{NS_G}availability').text, 'in stock')
        self.assertEqual(article.find(f'{NS_G}condition').text, 'new')
        self.assertEqual(article.find(f'{NS_G}brand').text, 'Deye')

    def test_un_produit_sans_stock_est_marque_out_of_stock(self):
        self.publie.quantite_stock = 0
        self.publie.save(update_fields=['quantite_stock'])
        racine = ElementTree.fromstring(
            flux_google_shopping_xml(self.company))
        article = racine.find('channel').find('item')
        self.assertEqual(
            article.find(f'{NS_G}availability').text, 'out of stock')

    def test_le_xml_ne_contient_aucun_prix_dachat(self):
        self.assertNotIn('7000', flux_google_shopping_xml(self.company))

    def test_un_format_inconnu_est_refuse(self):
        with self.assertRaises(ValueError):
            generer_flux(self.company, 'ebay')


class Ntret20EndpointTests(Ntret20Base):
    def test_le_parametre_format_nest_pas_avale_par_drf(self):
        # Piège connu : sans négociation de contenu dédiée, `?format=avito`
        # renvoie 404 AVANT même d'entrer dans la vue.
        res = auth(self.admin).get(URL, {'format': 'avito'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res['Content-Type'])
        self.assertIn('flux-avito.csv', res['Content-Disposition'])

    def test_le_flux_google_est_servi_en_xml(self):
        res = auth(self.admin).get(URL, {'format': 'google_shopping'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('application/xml', res['Content-Type'])

    def test_format_absent_ou_inconnu_renvoie_400(self):
        api = auth(self.admin)
        self.assertEqual(api.get(URL).status_code, 400)
        self.assertEqual(api.get(URL, {'format': 'ebay'}).status_code, 400)

    def test_endpoint_refuse_un_role_normal(self):
        res = auth(self.normal).get(URL, {'format': 'avito'})
        self.assertEqual(res.status_code, 403)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(
            APIClient().get(URL, {'format': 'avito'}).status_code, 401)
