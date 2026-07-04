"""XPLT22 — classeur léger embarqué avec données live (mini-spreadsheet BI)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.reporting.classeur import evaluate_formula, resolve_range
from apps.reporting.models import Classeur, ClasseurPartageInterne
from authentication.models import Company
from core import data_explorer
from core.models import SavedQuery

User = get_user_model()


def _stock_dataset_provider(company, user):
    return User.objects.filter(company=company)


class ClasseurBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='xplt22-co', defaults={'nom': 'XPLT22 Co'})[0]
        self.other_company = Company.objects.get_or_create(
            slug='xplt22-other', defaults={'nom': 'XPLT22 Other'})[0]
        self.owner = User.objects.create_user(
            username='xplt22_owner', password='x', company=self.company)
        self.viewer = User.objects.create_user(
            username='xplt22_viewer', password='x', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.owner)}')
        data_explorer.register_dataset(
            'xplt22_utilisateurs', 'Utilisateurs XPLT22',
            ['id', 'is_active'], _stock_dataset_provider)


class TestFormulaEvaluation(ClasseurBase):
    def test_somme_on_raw_cells(self):
        classeur = Classeur.objects.create(
            company=self.company, proprietaire=self.owner,
            cellules={
                'A1': {'valeur': 10}, 'A2': {'valeur': 20},
                'A3': {'valeur': 5},
            })
        valeur = evaluate_formula(classeur, '=SOMME(A1:A3)', user=self.owner)
        self.assertEqual(valeur, 35)

    def test_cell_reference_formula(self):
        classeur = Classeur.objects.create(
            company=self.company, proprietaire=self.owner,
            cellules={
                'A1': {'valeur': 4}, 'B1': {'valeur': 6},
                'C1': {'formule': '=A1+B1'},
            })
        valeur = evaluate_formula(classeur, '=A1+B1', user=self.owner)
        self.assertEqual(valeur, 10)
        # La cellule dérivée se résout aussi via rafraîchissement complet.
        resolved = {}
        from apps.reporting.classeur import _cell_value
        resolved['C1'] = _cell_value(classeur, 'C1', user=self.owner)
        self.assertEqual(resolved['C1'], 10)

    def test_illegal_formula_raises(self):
        classeur = Classeur.objects.create(
            company=self.company, proprietaire=self.owner, cellules={})
        with self.assertRaises(Exception):
            evaluate_formula(
                classeur, '=__import__("os")', user=self.owner)


class TestLiveLinkedRange(ClasseurBase):
    def test_insert_pivot_range_reads_live_data(self):
        sq = SavedQuery.objects.create(
            company=self.company, owner=self.owner, titre='Actifs',
            dataset='xplt22_utilisateurs',
            spec={'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}]})
        classeur = Classeur.objects.create(
            company=self.company, proprietaire=self.owner,
            liens={'A1:A1': {'saved_query_id': sq.id}})
        vals = resolve_range(classeur, 'A1:A1', user=self.owner)
        self.assertEqual(vals, [2])  # owner + viewer, même société

    def test_reopen_refreshes_live_data(self):
        """XPLT22 — rouvrir (rafraîchir) reflète l'état ACTUEL du dataset."""
        sq = SavedQuery.objects.create(
            company=self.company, owner=self.owner, titre='Actifs',
            dataset='xplt22_utilisateurs',
            spec={'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}]})
        classeur = Classeur.objects.create(
            company=self.company, proprietaire=self.owner,
            liens={'A1:A1': {'saved_query_id': sq.id}})
        self.assertEqual(
            resolve_range(classeur, 'A1:A1', user=self.owner), [2])
        User.objects.create_user(
            username='xplt22_new', password='x', company=self.company)
        # Ré-ouverture -> re-exécution -> reflète le nouvel utilisateur.
        self.assertEqual(
            resolve_range(classeur, 'A1:A1', user=self.owner), [3])

    def test_user_without_dataset_access_sees_empty_range(self):
        """Un utilisateur SANS droit sur le dataset (SavedQuery personnelle
        d'autrui, non partagée) voit la plage VIDE — jamais une fuite."""
        sq = SavedQuery.objects.create(
            company=self.company, owner=self.owner, titre='Privée',
            dataset='xplt22_utilisateurs', partage=False,
            spec={'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}]})
        classeur = Classeur.objects.create(
            company=self.company, proprietaire=self.owner,
            liens={'A1:A1': {'saved_query_id': sq.id}})
        vals = resolve_range(classeur, 'A1:A1', user=self.viewer)
        self.assertEqual(vals, [])

    def test_shared_query_visible_to_other_users(self):
        sq = SavedQuery.objects.create(
            company=self.company, owner=self.owner, titre='Partagée',
            dataset='xplt22_utilisateurs', partage=True,
            spec={'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}]})
        classeur = Classeur.objects.create(
            company=self.company, proprietaire=self.owner,
            liens={'A1:A1': {'saved_query_id': sq.id}})
        vals = resolve_range(classeur, 'A1:A1', user=self.viewer)
        self.assertEqual(vals, [2])


class TestClasseurApi(ClasseurBase):
    def test_insert_write_formula_reopen_refreshes(self):
        sq = SavedQuery.objects.create(
            company=self.company, owner=self.owner, titre='Actifs',
            dataset='xplt22_utilisateurs',
            spec={'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}]})
        resp = self.api.post('/api/django/reporting/classeurs/', {
            'titre': 'Mon classeur',
            'cellules': {'A1': {'valeur': 100}},
            'liens': {'B1:B1': {'saved_query_id': sq.id}},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        classeur_id = resp.data['id']

        resp2 = self.api.post(
            f'/api/django/reporting/classeurs/{classeur_id}/evaluer/',
            {'formule': '=SOMME(A1:A1)'}, format='json')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data['valeur'], 100)

        resp3 = self.api.get(
            f'/api/django/reporting/classeurs/{classeur_id}/rafraichir/')
        self.assertEqual(resp3.status_code, 200)

    def test_other_company_classeurs_not_visible(self):
        Classeur.objects.create(
            company=self.other_company, titre='Autre société', cellules={})
        resp = self.api.get('/api/django/reporting/classeurs/')
        self.assertEqual(resp.status_code, 200)
        titres = [c['titre'] for c in resp.data.get('results', resp.data)]
        self.assertNotIn('Autre société', titres)

    def test_personal_classeur_hidden_from_non_shared_user(self):
        Classeur.objects.create(
            company=self.company, proprietaire=self.owner, titre='Privé',
            cellules={})
        viewer_api = APIClient()
        viewer_api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.viewer)}')
        resp = viewer_api.get('/api/django/reporting/classeurs/')
        titres = [c['titre'] for c in resp.data.get('results', resp.data)]
        self.assertNotIn('Privé', titres)

    def test_internal_share_grants_visibility(self):
        classeur = Classeur.objects.create(
            company=self.company, proprietaire=self.owner, titre='Partagé fin',
            cellules={})
        ClasseurPartageInterne.objects.create(
            company=self.company, classeur=classeur, utilisateur=self.viewer)
        viewer_api = APIClient()
        viewer_api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.viewer)}')
        resp = viewer_api.get('/api/django/reporting/classeurs/')
        titres = [c['titre'] for c in resp.data.get('results', resp.data)]
        self.assertIn('Partagé fin', titres)
