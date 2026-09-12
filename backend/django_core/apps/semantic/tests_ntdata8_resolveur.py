"""NTDATA8 — résolveur de métrique (`semantic.services.resolve_metric`).

Couvre :
  * mesure SIMPLE (somme d'un champ) — valeur globale ;
  * mesure FORMULE (plusieurs agrégats combinés) ;
  * DIVISION PAR ZÉRO → None, jamais une exception ni un zéro inventé ;
  * série regroupée (critère d'acceptation : group_by=['mois'] rend une série) ;
  * `group_by=[]` explicite ≠ `group_by=None` (dimensions par défaut) ;
  * filtre de période ;
  * clé inconnue / dataset absent → erreurs FRANÇAISES explicites ;
  * scoping société (la métrique d'une société ne lit jamais l'autre).

Le dataset de test porte sur un modèle de FONDATION (Company/CustomUser) :
aucun import d'app métier.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.semantic import services
from apps.semantic.models import MetricDefinition
from authentication.models import Company
from core import data_explorer

User = get_user_model()

DATASET = 'ntdata8_utilisateurs'


def _provider(company, user):
    from django.db.models.functions import TruncMonth
    return User.objects.filter(company=company).annotate(
        mois=TruncMonth('date_joined'))


class ResolveMetricTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA8 SA',
                                             slug='ntdata8-sa')
        cls.autre = Company.objects.create(nom='NTDATA8 Autre',
                                           slug='ntdata8-autre')
        cls.user = User.objects.create_user(
            username='ntdata8_u', password='x', company=cls.company,
            failed_login_count=10)
        cls.user2 = User.objects.create_user(
            username='ntdata8_u2', password='x', company=cls.company,
            failed_login_count=30)
        User.objects.create_user(
            username='ntdata8_ailleurs', password='x', company=cls.autre,
            failed_login_count=999)

    def setUp(self):
        data_explorer.register_dataset(
            DATASET, 'Utilisateurs NTDATA8',
            ['id', 'username', 'is_active', 'mois', 'failed_login_count'],
            _provider,
            field_meta={'mois': {'label': 'Mois', 'type': 'temps'}})

    def _metrique(self, cle, mesure, **kw):
        defaults = dict(company=self.company, cle=cle, libelle=cle.upper(),
                        dataset=DATASET, mesure=mesure)
        defaults.update(kw)
        return MetricDefinition.objects.create(**defaults)

    def test_mesure_simple_valeur_globale(self):
        self._metrique('total_score', {'field': 'failed_login_count',
                                       'agg': 'sum'})
        res = services.resolve_metric(self.company, self.user, 'total_score')
        self.assertEqual(res['valeur'], 40)
        self.assertEqual(res['cle'], 'total_score')
        # Scoping société : les 999 de l'autre société ne sont pas comptés.

    def test_mesure_formule(self):
        self._metrique('score_moyen', {
            'formula': 'total / nb',
            'aggregates': [
                {'alias': 'total', 'fn': 'sum', 'field': 'failed_login_count'},
                {'alias': 'nb', 'fn': 'count', 'field': 'id'},
            ],
        })
        res = services.resolve_metric(self.company, self.user, 'score_moyen')
        self.assertEqual(res['valeur'], 20)

    def test_division_par_zero_rend_none(self):
        self._metrique('impossible', {
            'formula': 'total / zero',
            'aggregates': [
                {'alias': 'total', 'fn': 'sum', 'field': 'failed_login_count'},
                {'alias': 'zero', 'fn': 'sum', 'field': 'failed_login_count'},
            ],
        })
        # Population vide (filtre impossible) → agrégats NULL → valeur VIDE,
        # jamais une exception ni un zéro inventé.
        res = services.resolve_metric(
            self.company, self.user, 'impossible',
            filters={'username': 'personne-de-ce-nom'})
        self.assertIsNone(res['valeur'])

    def test_denominateur_nul_rend_none(self):
        User.objects.create_user(
            username='ntdata8_zero', password='x', company=self.company,
            failed_login_count=0)
        self._metrique('ratio', {
            'formula': 'nb / total',
            'aggregates': [
                {'alias': 'nb', 'fn': 'count', 'field': 'id'},
                {'alias': 'total', 'fn': 'sum',
                 'field': 'failed_login_count'},
            ],
        })
        res = services.resolve_metric(
            self.company, self.user, 'ratio',
            filters={'username': 'ntdata8_zero'})
        self.assertIsNone(res['valeur'])

    def test_formule_illegale_est_une_erreur(self):
        self._metrique('illegale', {
            'formula': 'nb / inconnue',
            'aggregates': [{'alias': 'nb', 'fn': 'count', 'field': 'id'}],
        })
        with self.assertRaises(services.MetriqueNonResolvable):
            services.resolve_metric(self.company, self.user, 'illegale')

    def test_serie_regroupee(self):
        self._metrique('nb_utilisateurs', {'agg': 'count'})
        res = services.resolve_metric(
            self.company, self.user, 'nb_utilisateurs', group_by=['mois'])
        self.assertIsNone(res['valeur'])
        self.assertTrue(res['lignes'])
        self.assertIn('mois', res['lignes'][0])
        self.assertEqual(sum(ligne['valeur'] for ligne in res['lignes']), 2)

    def test_dimensions_par_defaut_vs_group_by_vide(self):
        self._metrique('nb_defaut', {'agg': 'count'},
                       dimensions_par_defaut=['mois'])
        # Sans group_by → dimensions par défaut ⇒ série.
        par_defaut = services.resolve_metric(
            self.company, self.user, 'nb_defaut')
        self.assertEqual(par_defaut['group_by'], ['mois'])
        # group_by=[] explicite ⇒ valeur globale.
        global_ = services.resolve_metric(
            self.company, self.user, 'nb_defaut', group_by=[])
        self.assertEqual(global_['group_by'], [])
        self.assertEqual(global_['valeur'], 2)

    def test_periode_filtre_sur_l_axe_de_temps(self):
        self._metrique('nb_periode', {'agg': 'count'})
        demain = timezone.now() + timedelta(days=1)
        res = services.resolve_metric(
            self.company, self.user, 'nb_periode',
            period={'debut': demain})
        self.assertIn(res['valeur'], (0, None))

    def test_cle_inconnue(self):
        with self.assertRaises(services.MetriqueInconnue):
            services.resolve_metric(self.company, self.user, 'jamais_definie')

    def test_metrique_inactive_est_inconnue(self):
        self._metrique('eteinte', {'agg': 'count'}, actif=False)
        with self.assertRaises(services.MetriqueInconnue):
            services.resolve_metric(self.company, self.user, 'eteinte')

    def test_dataset_absent_erreur_explicite(self):
        self._metrique('orpheline', {'agg': 'count'},
                       dataset='dataset_qui_n_existe_pas')
        with self.assertRaises(services.MetriqueNonResolvable) as ctx:
            services.resolve_metric(self.company, self.user, 'orpheline')
        self.assertIn('orpheline', str(ctx.exception))

    def test_champ_hors_liste_blanche_erreur_explicite(self):
        self._metrique('fuite', {'field': 'password', 'agg': 'count'})
        with self.assertRaises(services.MetriqueNonResolvable):
            services.resolve_metric(self.company, self.user, 'fuite')

    def test_metrique_d_une_autre_societe_invisible(self):
        MetricDefinition.objects.create(
            company=self.autre, cle='privee', libelle='Privée',
            dataset=DATASET, mesure={'agg': 'count'})
        with self.assertRaises(services.MetriqueInconnue):
            services.resolve_metric(self.company, self.user, 'privee')
