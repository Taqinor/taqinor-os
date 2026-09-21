"""NTRET20 — exports marketplace (Avito CSV, Google Shopping XML).

Critère d'acceptation testé : le flux généré est VALIDE au format cible (test
de STRUCTURE), il ne contient AUCUN prix d'achat, et un produit non marqué
vendable en ligne est EXCLU.

GATED : aucune intégration API n'est testée ici — la tâche ne livre que le
fichier prêt à importer (les comptes marchands Avito/Google restent une étape
manuelle du fondateur). Aucun appel réseau, aucune clé.

SOLMVP-sweep (2026-09-21) — apps.ecommerce_connect est sorti du MVP solaire
(Groupe SOLMVP, coquille) : ``ConnexionEcommerce``/``ProduitSync`` (le
mécanisme qui marquait un produit « vendable en ligne ») n'existent plus.
``produits_vendables_en_ligne`` DÉGRADE DÉJÀ en production vers une liste VIDE
(try/except autour de ``apps.get_model``, jamais un crash — règle dure : un
flux PUBLIC ne part jamais « tout coché » par accident) ; c'est cette
dégradation que ``Ntret20DegradationTests`` couvre désormais, à la place des
anciens tests de sélection qui créaient de vraies lignes ``ProduitSync``
(impossible depuis que le modèle est sorti de l'état Django). Les tests de
FORME du flux CSV/XML/endpoint restent : ils simulent la sélection via
``unittest.mock.patch`` sur ``produits_vendables_en_ligne`` plutôt que de
dépendre du modèle disparu — ils couvrent donc toujours le vrai critère
d'acceptation NTRET20 (structure du flux, aucun prix d'achat, exclusion des
non-vendables).

Run :
    python manage.py test apps.stock.test_ntret20_marketplace -v 2
"""
import csv
import io
from decimal import Decimal
from unittest import mock
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


def patch_vendables(*produits):
    """Simule la sélection « vendable en ligne » (ex-ecommerce_connect) sans
    dépendre du modèle disparu : renvoie exactement ``produits`` au lieu de
    lire ``ProduitSync``."""
    ids = [p.pk for p in produits]
    return mock.patch(
        'apps.stock.marketplace_feeds.produits_vendables_en_ligne',
        side_effect=lambda company: Produit.objects.filter(
            company=company, pk__in=ids).select_related('categorie'))


class Ntret20Base(TestCase):
    def setUp(self):
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


class Ntret20DegradationTests(Ntret20Base):
    """ecommerce_connect absent ⇒ dégradation VIDE, jamais un crash ni « tout
    le catalogue » exporté par accident (règle dure du module)."""

    def test_sans_ecommerce_connect_le_flux_est_vide_jamais_tout_le_catalogue(
            self):
        self.assertEqual(list(produits_vendables_en_ligne(self.company)), [])

    def test_aucun_produit_dune_autre_societe_non_plus(self):
        self.assertEqual(list(produits_vendables_en_ligne(self.autre)), [])

    def test_le_csv_par_defaut_ne_contient_que_len_tete(self):
        contenu = flux_avito_csv(self.company)
        lignes = list(csv.reader(io.StringIO(contenu)))
        self.assertEqual(len(lignes), 1)

    def test_le_xml_par_defaut_ne_contient_aucun_article(self):
        racine = ElementTree.fromstring(flux_google_shopping_xml(self.company))
        self.assertEqual(racine.find('channel').findall('item'), [])


class Ntret20AvitoTests(Ntret20Base):
    def test_le_csv_a_len_tete_et_une_ligne_par_produit_publie(self):
        with patch_vendables(self.publie):
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
        with patch_vendables(self.publie):
            contenu = flux_avito_csv(self.company)
        self.assertNotIn('7000', contenu)
        self.assertNotIn('Pièce interne', contenu)


class Ntret20GoogleTests(Ntret20Base):
    def test_le_xml_est_un_rss_google_shopping_valide(self):
        with patch_vendables(self.publie):
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
        with patch_vendables(self.publie):
            racine = ElementTree.fromstring(
                flux_google_shopping_xml(self.company))
        article = racine.find('channel').find('item')
        self.assertEqual(
            article.find(f'{NS_G}availability').text, 'out of stock')

    def test_le_xml_ne_contient_aucun_prix_dachat(self):
        with patch_vendables(self.publie):
            contenu = flux_google_shopping_xml(self.company)
        self.assertNotIn('7000', contenu)

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
