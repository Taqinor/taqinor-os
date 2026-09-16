"""STKCAT27 — `GET /api/django/stock/produits/?search=` sans les accents.

Ce que ces tests verrouillent :

  * LE REPLI, TOUJOURS TESTÉ : quand `unaccent`/`pg_trgm`/`f_unaccent` ne sont
    pas là (rôle de base sans droit `CREATE EXTENSION`, SQLite), `?search=`
    garde EXACTEMENT le comportement `SearchFilter` d'aujourd'hui — « cable »
    ne trouve pas « Câble », « câble » le trouve, et les termes multiples
    restent en ET ;
  * LA SONDE N'EST PAS PAYÉE SANS RECHERCHE : une liste produits sans
    `?search=` ne déclenche aucune requête supplémentaire (le budget de
    `docs/query-budgets.yml` doit rester intact) ;
  * L'IDEMPOTENCE DE LA MIGRATION : son SQL rejoué deux fois de suite ne lève
    pas — c'est la garantie qui rend un redéploiement sûr ;
  * LES ACCENTS, quand la base porte réellement les extensions.

POURQUOI PAS UN `skipUnless` DE MODULE POUR LA PRÉSENCE DES EXTENSIONS : le
lanceur de tests Django IMPORTE les modules de test AVANT de créer la base de
test (`build_suite()` précède `setup_databases()`). Une sonde au moment de la
décoration interrogerait donc la mauvaise base, voire aucune. Le `skipUnless`
de module ne porte que sur le VENDOR (lu dans les réglages, sans connexion) et
la présence réelle des extensions est constatée dans `setUp`, qui tourne, lui,
sur la base de test.
"""
import unittest
from decimal import Decimal
from importlib import import_module
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
from apps.stock import selectors as stock_selectors
from apps.stock.models import Categorie, Produit
from authentication.models import Company

User = get_user_model()

URL_PRODUITS = '/api/django/stock/produits/'

MIGRATION = 'apps.stock.migrations.0148_stkcat27_recherche_unaccent_trgm'

CABLE = 'STKCAT27 Câble solaire 6mm2'
HYBRIDE = 'STKCAT27 Onduleur Deye Hybride 5kW'
RESEAU = 'STKCAT27 Onduleur Deye Réseau 3kW'
REGULATEUR = 'STKCAT27 Régulateur MPPT'


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def noms(reponse):
    """Les désignations rendues, quelle que soit l'enveloppe (paginée ou non)."""
    data = reponse.data
    lignes = data['results'] if isinstance(data, dict) else data
    return [ligne['nom'] for ligne in lignes]


class STKCAT27Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='stkcat27-accents-co',
            defaults={'nom': 'STKCAT27 Accents Co'})[0]
        cls.other_company = Company.objects.get_or_create(
            slug='stkcat27-accents-co-other',
            defaults={'nom': 'STKCAT27 Accents Other Co'})[0]
        cls.roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            cls.roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.user = User.objects.create_user(
            username='stkcat27_dir', password='x', company=cls.company,
            role=cls.roles['Directeur'])

        cls.categorie = Categorie.objects.create(
            company=cls.company, nom='STKCAT27 Câblerie', ordre=10)
        cls.cat_voisine = Categorie.objects.create(
            company=cls.other_company, nom='STKCAT27 Câblerie voisine',
            ordre=10)

        cls.cable = Produit.objects.create(
            company=cls.company, nom=CABLE, categorie=cls.categorie,
            prix_vente=Decimal('12'))
        cls.hybride = Produit.objects.create(
            company=cls.company, nom=HYBRIDE, categorie=cls.categorie,
            prix_vente=Decimal('14000'))
        cls.reseau = Produit.objects.create(
            company=cls.company, nom=RESEAU, categorie=cls.categorie,
            prix_vente=Decimal('9000'))
        cls.regulateur = Produit.objects.create(
            company=cls.company, nom=REGULATEUR, categorie=cls.categorie,
            prix_vente=Decimal('800'))
        cls.produit_voisin = Produit.objects.create(
            company=cls.other_company, nom='STKCAT27 Câble voisin',
            categorie=cls.cat_voisine, prix_vente=Decimal('13'))

    def setUp(self):
        super().setUp()
        # La sonde est mise en cache POUR TOUT LE PROCESSUS : sans remise à
        # zéro, un test qui la force à False empoisonnerait les suivants.
        stock_selectors.reinitialiser_cache_recherche_sans_accents()
        self.addCleanup(
            stock_selectors.reinitialiser_cache_recherche_sans_accents)

    def chercher(self, terme, **extra):
        params = {'search': terme, 'page_size': 200}
        params.update(extra)
        reponse = api_for(self.user).get(URL_PRODUITS, params)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return noms(reponse)


class TestRepliSansExtensions(STKCAT27Base):
    """Le chemin TOUJOURS exercé, sur PostgreSQL comme sur SQLite : sonde
    forcée à False = comportement `SearchFilter` historique, à l'octet près."""

    def setUp(self):
        super().setUp()
        patcheur = patch.object(
            stock_selectors, 'recherche_sans_accents_disponible',
            return_value=False)
        patcheur.start()
        self.addCleanup(patcheur.stop)

    def test_sans_accent_ne_trouve_pas_le_mot_accentue(self):
        self.assertNotIn(CABLE, self.chercher('cable'))

    def test_avec_accent_trouve(self):
        self.assertIn(CABLE, self.chercher('câble'))

    def test_recherche_non_accentuee_fonctionne_toujours(self):
        rendus = self.chercher('onduleur')
        self.assertIn(HYBRIDE, rendus)
        self.assertIn(RESEAU, rendus)
        self.assertNotIn(CABLE, rendus)

    def test_termes_multiples_restent_en_et(self):
        rendus = self.chercher('deye hybride')
        self.assertIn(HYBRIDE, rendus)
        self.assertNotIn(RESEAU, rendus)

    def test_insensible_a_la_casse_comme_avant(self):
        self.assertIn(HYBRIDE, self.chercher('DEYE'))

    def test_aucun_resultat_d_une_autre_societe(self):
        for terme in ('cable', 'câble', 'STKCAT27'):
            self.assertNotIn('STKCAT27 Câble voisin', self.chercher(terme))


class TestRechercheSansAccents(STKCAT27Base):
    """Le chemin insensible aux accents — sauté tel quel si la base de test
    n'a pas pu recevoir les extensions (c'est un cas NORMAL, pas un échec)."""

    def setUp(self):
        super().setUp()
        if not stock_selectors.recherche_sans_accents_disponible():
            self.skipTest(
                'unaccent / pg_trgm / public.f_unaccent absentes de cette '
                'base de test — la recherche reste sensible aux accents '
                '(dégradation gracieuse vérifiée par TestRepliSansExtensions).')

    def test_sans_accent_trouve_le_mot_accentue(self):
        self.assertIn(CABLE, self.chercher('cable'))

    def test_en_majuscules_sans_accent_trouve_aussi(self):
        self.assertIn(CABLE, self.chercher('CABLE'))

    def test_avec_accent_trouve_toujours(self):
        self.assertIn(CABLE, self.chercher('câble'))

    def test_reseau_sans_accent(self):
        rendus = self.chercher('reseau')
        self.assertIn(RESEAU, rendus)
        self.assertNotIn(HYBRIDE, rendus)

    def test_termes_multiples_restent_en_et(self):
        rendus = self.chercher('deye hybride')
        self.assertIn(HYBRIDE, rendus)
        self.assertNotIn(RESEAU, rendus)
        self.assertNotIn(CABLE, rendus)

    def test_un_terme_qui_ne_matche_rien_rend_une_liste_vide(self):
        self.assertEqual(self.chercher('zzzintrouvable'), [])

    def test_les_jokers_like_restent_litteraux(self):
        """Parité avec `icontains` : `%` tapé par l'utilisateur ne doit pas
        devenir un joker qui ramènerait tout le catalogue."""
        self.assertEqual(self.chercher('cable%solaire'), [])

    def test_recherche_sur_la_categorie_aussi_sans_accent(self):
        # `categorie__nom` fait partie des `search_fields` : « cablerie »
        # (sans accent) doit ramener les produits de « Câblerie ».
        rendus = self.chercher('cablerie')
        self.assertIn(CABLE, rendus)
        self.assertIn(REGULATEUR, rendus)

    def test_aucun_resultat_d_une_autre_societe(self):
        """Le scoping société est posé EN AMONT par `get_queryset()` : la
        recherche ne peut rien faire fuiter, accents ou pas."""
        for terme in ('cable', 'câble', 'cablerie'):
            self.assertNotIn('STKCAT27 Câble voisin', self.chercher(terme))


class TestSondeNonPayeeSansRecherche(STKCAT27Base):
    def test_liste_sans_search_ne_sonde_pas(self):
        """Sans `?search=`, la disponibilité n'est jamais sondée : la liste
        produits ne paie aucune requête de plus (budget YOPSB13 intact)."""
        with patch.object(
                stock_selectors, 'recherche_sans_accents_disponible',
                return_value=False) as sonde:
            reponse = api_for(self.user).get(URL_PRODUITS, {'page_size': 200})
            self.assertEqual(reponse.status_code, 200, reponse.data)
            sonde.assert_not_called()

    def test_search_vide_ne_sonde_pas_non_plus(self):
        with patch.object(
                stock_selectors, 'recherche_sans_accents_disponible',
                return_value=False) as sonde:
            reponse = api_for(self.user).get(
                URL_PRODUITS, {'search': '', 'page_size': 200})
            self.assertEqual(reponse.status_code, 200, reponse.data)
            sonde.assert_not_called()


@unittest.skipUnless(connection.vendor == 'postgresql',
                     'SQL PostgreSQL (bloc DO + extensions).')
class TestMigrationIdempotente(TestCase):
    """Rejouer le SQL de la migration 0148 ne doit JAMAIS lever.

    C'est la propriété qui rend le déploiement sûr : sur une base dont le rôle
    n'a pas le droit de créer des extensions, le bloc `DO` écrit des NOTICE et
    rend la main — la migration passe, et un second passage aussi.
    """

    def _executer(self, sql):
        with connection.cursor() as curseur:
            curseur.execute(sql)

    def test_le_sql_avant_rejoue_deux_fois_ne_leve_pas(self):
        module = import_module(MIGRATION)
        self._executer(module.SQL_AVANT)
        self._executer(module.SQL_AVANT)

    def test_le_sql_arriere_rejoue_deux_fois_ne_leve_pas(self):
        module = import_module(MIGRATION)
        self._executer(module.SQL_ARRIERE)
        self._executer(module.SQL_ARRIERE)
        # Et on remet l'état d'origine : la transaction de test est de toute
        # façon annulée, mais laisser la base « dans l'état d'après » serait
        # un piège pour un futur lecteur.
        self._executer(module.SQL_AVANT)

    def test_l_index_porte_bien_le_nom_annonce(self):
        """Si les extensions SONT là, l'index doit exister sous le nom que le
        module publie (c'est ce nom que le retour arrière supprime)."""
        module = import_module(MIGRATION)
        self._executer(module.SQL_AVANT)
        with connection.cursor() as curseur:
            curseur.execute(
                "SELECT to_regprocedure('public.f_unaccent(text)') "
                "IS NOT NULL")
            enveloppe_presente = bool(curseur.fetchone()[0])
            curseur.execute(
                'SELECT COUNT(*) FROM pg_indexes WHERE indexname = %s',
                [module.NOM_INDEX])
            nb_index = curseur.fetchone()[0]
        if not enveloppe_presente:
            self.skipTest(
                'Extensions non installables sur cette base — le bloc DO a '
                'correctement dégradé sans lever.')
        self.assertEqual(nb_index, 1)
