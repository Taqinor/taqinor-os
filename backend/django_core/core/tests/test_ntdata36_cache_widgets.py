"""Tests NTDATA36 — pré-agrégation / cache des widgets BI lourds.

Couvre :
  * 2e chargement d'un widget lourd = HIT servi depuis le cache (+ journal) ;
  * un widget qui ne demande PAS le cache reste frais (aucune mémorisation) ;
  * la clé dépend de la spec ET des filtres (une période différente recalcule) ;
  * aucune fuite entre utilisateurs par défaut, ni entre sociétés ;
  * un dataset déclaré ``cache_partage`` partage l'entrée dans SA société ;
  * TTL configurable et borné ; TTL nul = cache désactivé.
"""
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.test import TestCase

from authentication.models import Company
from core import bi_cache, dashboard_data, data_explorer
from core.models import ChangelogEntry, Dashboard

User = get_user_model()


def _changelog_dataset(company, user):
    return ChangelogEntry.objects.all()


class TtlTests(TestCase):
    def test_ttl_borne_et_desactivation(self):
        self.assertEqual(bi_cache.ttl_effectif(900), 900)
        self.assertEqual(bi_cache.ttl_effectif(99999), bi_cache.TTL_MAX)
        self.assertEqual(bi_cache.ttl_effectif(0), 0)
        self.assertEqual(bi_cache.ttl_effectif(-5), 0)
        self.assertEqual(bi_cache.ttl_effectif('nawak'), bi_cache.TTL_DEFAUT)

    def test_widget_sans_demande_ne_cache_pas(self):
        self.assertIsNone(bi_cache.ttl_du_widget({'id': 'x'}))
        self.assertEqual(bi_cache.ttl_du_widget({'cache': True}),
                         bi_cache.TTL_DEFAUT)
        self.assertEqual(bi_cache.ttl_du_widget({'cache_ttl': 60}), 60)
        self.assertEqual(bi_cache.ttl_du_widget({'cache_ttl': 0}), 0)


class CleCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.u1 = User.objects.create_user(username='bi1', password='x',
                                          company=cls.company)
        cls.u2 = User.objects.create_user(username='bi2', password='x',
                                          company=cls.company)

    def test_cle_depend_de_la_spec_et_des_filtres(self):
        a = bi_cache.cle_cache('d', {'filters': {'x': 1}}, self.u1)
        b = bi_cache.cle_cache('d', {'filters': {'x': 2}}, self.u1)
        self.assertNotEqual(a, b)

    def test_cle_stable_quel_que_soit_lordre_des_cles(self):
        a = bi_cache.cle_cache('d', {'filters': {'x': 1, 'y': 2}}, self.u1)
        b = bi_cache.cle_cache('d', {'filters': {'y': 2, 'x': 1}}, self.u1)
        self.assertEqual(a, b)

    def test_par_defaut_la_cle_isole_les_utilisateurs(self):
        self.assertNotEqual(bi_cache.cle_cache('d', {}, self.u1),
                            bi_cache.cle_cache('d', {}, self.u2))

    def test_cache_partage_regroupe_les_utilisateurs(self):
        self.assertEqual(bi_cache.cle_cache('d', {}, self.u1, partage=True),
                         bi_cache.cle_cache('d', {}, self.u2, partage=True))


class RunQueryCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.autre = Company.objects.create(nom='Autre')
        cls.user = User.objects.create_user(username='bi_run', password='x',
                                            company=cls.company)
        cls.autre_user = User.objects.create_user(
            username='bi_run2', password='x', company=cls.autre)

    def setUp(self):
        django_cache.clear()
        self.addCleanup(django_cache.clear)
        data_explorer.register_dataset(
            'changelog', 'Nouveautés', ['id', 'titre'], _changelog_dataset)
        ChangelogEntry.objects.create(titre='A')

    def test_second_appel_sert_depuis_le_cache_et_journalise(self):
        spec = {'select': ['titre']}
        rows1, statut1 = bi_cache.run_query_cache(
            'changelog', self.company, self.user, spec, ttl=300)
        self.assertEqual(statut1, 'miss')
        with self.assertLogs('core.bi_cache', level='INFO') as journal:
            rows2, statut2 = bi_cache.run_query_cache(
                'changelog', self.company, self.user, spec, ttl=300)
        self.assertEqual(statut2, 'hit')
        self.assertEqual(rows1, rows2)
        self.assertTrue(any('HIT' in ligne for ligne in journal.output))

    def test_ttl_nul_desactive_le_cache(self):
        spec = {'select': ['titre']}
        _rows, statut = bi_cache.run_query_cache(
            'changelog', self.company, self.user, spec, ttl=0)
        self.assertEqual(statut, '')
        _rows, statut = bi_cache.run_query_cache(
            'changelog', self.company, self.user, spec, ttl=0)
        self.assertEqual(statut, '')

    def test_aucune_fuite_entre_societes(self):
        spec = {'select': ['titre']}
        bi_cache.run_query_cache('changelog', self.company, self.user, spec,
                                 ttl=300)
        _rows, statut = bi_cache.run_query_cache(
            'changelog', self.autre, self.autre_user, spec, ttl=300)
        self.assertEqual(statut, 'miss')

    def test_dataset_partage_sert_le_meme_resultat_aux_collegues(self):
        collegue = User.objects.create_user(username='bi_col', password='x',
                                            company=self.company)
        data_explorer.register_dataset(
            'changelog_partage', 'Nouveautés', ['id', 'titre'],
            _changelog_dataset, cache_partage=True)
        spec = {'select': ['titre']}
        bi_cache.run_query_cache('changelog_partage', self.company, self.user,
                                 spec, ttl=300)
        _rows, statut = bi_cache.run_query_cache(
            'changelog_partage', self.company, collegue, spec, ttl=300)
        self.assertEqual(statut, 'hit')


class DashboardCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.user = User.objects.create_user(username='bi_dash', password='x',
                                            company=cls.company)

    def setUp(self):
        django_cache.clear()
        self.addCleanup(django_cache.clear)
        data_explorer.register_dataset(
            'changelog', 'Nouveautés', ['id', 'titre', 'categorie'],
            _changelog_dataset)
        ChangelogEntry.objects.create(titre='A', categorie='correctif')

    def _dashboard(self, widgets):
        return Dashboard.objects.create(
            company=self.company, titre='Lourd', layout={'widgets': widgets})

    def test_widget_lourd_hit_au_second_chargement(self):
        dash = self._dashboard([
            {'id': 'lourd', 'dataset': 'changelog', 'cache_ttl': 600,
             'spec': {'select': ['titre']}},
            {'id': 'frais', 'dataset': 'changelog',
             'spec': {'select': ['titre']}},
        ])
        premier = dashboard_data.executer_dashboard(
            dash, self.company, self.user)
        widgets = {w['id']: w for w in premier['widgets']}
        self.assertEqual(widgets['lourd']['cache'], 'miss')
        self.assertNotIn('cache', widgets['frais'])

        second = dashboard_data.executer_dashboard(
            dash, self.company, self.user)
        widgets = {w['id']: w for w in second['widgets']}
        self.assertEqual(widgets['lourd']['cache'], 'hit')
        self.assertEqual(widgets['lourd']['rows'],
                         widgets['frais']['rows'])

    def test_changer_les_filtres_globaux_recalcule(self):
        dash = self._dashboard([
            {'id': 'lourd', 'dataset': 'changelog', 'cache': True,
             'spec': {'select': ['titre']},
             'filtres_globaux': {'categorie': 'categorie'}},
        ])
        dashboard_data.executer_dashboard(
            dash, self.company, self.user,
            globaux={'categorie': 'correctif'})
        autre = dashboard_data.executer_dashboard(
            dash, self.company, self.user,
            globaux={'categorie': 'nouveaute'})
        self.assertEqual(autre['widgets'][0]['cache'], 'miss')

    def test_widget_frais_voit_les_nouvelles_donnees(self):
        dash = self._dashboard([
            {'id': 'frais', 'dataset': 'changelog',
             'spec': {'select': ['titre']}},
        ])
        dashboard_data.executer_dashboard(dash, self.company, self.user)
        ChangelogEntry.objects.create(titre='B', categorie='correctif')
        second = dashboard_data.executer_dashboard(
            dash, self.company, self.user)
        self.assertEqual(len(second['widgets'][0]['rows']), 2)

    def test_empreinte_serialisable(self):
        # Une spec contenant des valeurs non-JSON ne doit jamais lever.
        cle = bi_cache.cle_cache('d', {'filters': {'x': object()}}, self.user)
        self.assertTrue(cle.startswith('bi:d:'))
        json.dumps({'ok': True})
