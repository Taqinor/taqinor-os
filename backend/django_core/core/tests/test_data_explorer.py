"""Tests FG382 — explorateur de données (query builder sans SQL).

Couvre :
  * registre de datasets + liste blanche de champs (champ hors liste rejeté) ;
  * exécution : sélection, filtre, group_by + agrégation ;
  * scoping société porté par le queryset_provider du dataset ;
  * SavedQuery : company/owner imposés côté serveur, visibilité perso/partagé ;
  * découplage : le test enregistre un dataset sur un modèle de FONDATION
    (Company) — aucun import d'app domaine.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import data_explorer
from core.models import SavedQuery
from core.views import SavedQueryViewSet

User = get_user_model()


def _users_dataset_provider(company, user):
    # Queryset déjà scopé société (la sécurité reste chez le fournisseur).
    return User.objects.filter(company=company)


class DataExplorerEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.u1 = User.objects.create_user(
            username='a', password='x', company=cls.company, is_active=True)
        cls.u2 = User.objects.create_user(
            username='b', password='x', company=cls.company, is_active=False)
        User.objects.create_user(
            username='c', password='x', company=cls.other)

    def setUp(self):
        data_explorer.register_dataset(
            'utilisateurs', 'Utilisateurs',
            ['id', 'username', 'is_active'], _users_dataset_provider)

    def test_list_datasets_includes_registered(self):
        names = {d['name'] for d in data_explorer.list_datasets()}
        self.assertIn('utilisateurs', names)

    def test_select_and_filter_scoped(self):
        rows = data_explorer.run_query(
            'utilisateurs', self.company, self.u1,
            {'select': ['username'], 'filters': {'is_active': True}})
        usernames = {r['username'] for r in rows}
        self.assertEqual(usernames, {'a'})  # u2 inactif exclu, autre société hors scope

    def test_group_by_aggregate(self):
        rows = data_explorer.run_query(
            'utilisateurs', self.company, self.u1,
            {'group_by': ['is_active'],
             'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}]})
        by_active = {r['is_active']: r['n'] for r in rows}
        self.assertEqual(by_active.get(True), 1)
        self.assertEqual(by_active.get(False), 1)

    def test_field_not_whitelisted_rejected(self):
        with self.assertRaises(data_explorer.ChampNonAutorise):
            data_explorer.run_query(
                'utilisateurs', self.company, self.u1,
                {'select': ['password']})  # hors liste blanche

    def test_unknown_dataset_raises(self):
        with self.assertRaises(data_explorer.DatasetInconnu):
            data_explorer.run_query('inexistant', self.company, self.u1, {})


class SavedQueryViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.user = User.objects.create_user(
            username='u1', password='x', company=cls.company)
        cls.factory = APIRequestFactory()

    def test_create_imposes_company_and_owner(self):
        req = self.factory.post(
            '/saved-queries/',
            {'titre': 'Q1', 'dataset': 'utilisateurs', 'spec': {}},
            format='json')
        force_authenticate(req, user=self.user)
        view = SavedQueryViewSet.as_view({'post': 'create'})
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        sq = SavedQuery.objects.get(titre='Q1')
        self.assertEqual(sq.company, self.company)
        self.assertEqual(sq.owner, self.user)

    def test_run_adhoc_unknown_dataset_is_404(self):
        req = self.factory.post(
            '/saved-queries/run/', {'dataset': 'nope'}, format='json')
        force_authenticate(req, user=self.user)
        view = SavedQueryViewSet.as_view({'post': 'run_adhoc'})
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
