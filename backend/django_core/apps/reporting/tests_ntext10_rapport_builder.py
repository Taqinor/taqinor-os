"""NTEXT10 — report-builder : définitions de rapport croisé sauvegardées.

Couvre : la portée société imposée CÔTÉ SERVEUR (company + owner jamais lus du
corps), la visibilité perso/société, le rejeu (``POST <id>/executer/``) via
``core.data_explorer.run_query`` puis ``core.pivot.build_pivot`` quand un
``pivot_spec`` est présent, et les erreurs (dataset inconnu → 404, champ hors
liste blanche → 400, pivot_spec invalide → 400).

Le dataset de test est enregistré sur un modèle de CETTE app
(``reporting.WebVitalMetric``) : aucun import d'app domaine.
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core import data_explorer

from .models import RapportDefinition, WebVitalMetric

User = get_user_model()

URL = '/api/django/reporting/rapport-definitions/'

_seq = itertools.count(1)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT10 Co {next(_seq)}')


def make_user(company, username=None, role='responsable'):
    return User.objects.create_user(
        username=username or f'ntext10-u{next(_seq)}', password='x',
        role_legacy=role, company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _vitals_provider(company, user):
    """Queryset DÉJÀ scopé société — la sécurité reste chez le fournisseur."""
    return WebVitalMetric.objects.filter(company=company)


class RapportDefinitionCrudTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT10 Scope')
        self.other = make_company('NTEXT10 Autre')
        self.user = make_user(self.company, 'ntext10-owner')
        self.api = _auth(self.user)

    def test_create_forces_company_and_owner_server_side(self):
        res = self.api.post(URL, {
            'titre': 'CA par commercial × mois',
            'dataset': 'vitals_ntext10',
            'spec': {'group_by': ['route']},
            'company': self.other.id,   # doit être IGNORÉ
            'owner': 999,               # doit être IGNORÉ
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        obj = RapportDefinition.objects.get(id=res.data['id'])
        self.assertEqual(obj.company, self.company)
        self.assertEqual(obj.owner, self.user)

    def test_dataset_is_required(self):
        res = self.api.post(URL, {'titre': 'Sans dataset', 'dataset': '  '},
                            format='json')
        self.assertEqual(res.status_code, 400)

    def test_list_is_company_scoped(self):
        RapportDefinition.objects.create(
            company=self.company, owner=self.user, titre='À moi',
            dataset='vitals_ntext10',
            partage=RapportDefinition.Partage.SOCIETE)
        RapportDefinition.objects.create(
            company=self.other, titre='Pas à moi', dataset='vitals_ntext10',
            partage=RapportDefinition.Partage.SOCIETE)
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200)
        results = res.data['results'] if 'results' in res.data else res.data
        titres = {r['titre'] for r in results}
        self.assertIn('À moi', titres)
        self.assertNotIn('Pas à moi', titres)

    def test_private_report_is_invisible_to_a_colleague(self):
        prive = RapportDefinition.objects.create(
            company=self.company, owner=self.user, titre='Privé',
            dataset='vitals_ntext10')
        partage = RapportDefinition.objects.create(
            company=self.company, owner=self.user, titre='Partagé',
            dataset='vitals_ntext10',
            partage=RapportDefinition.Partage.SOCIETE)
        collegue = _auth(make_user(self.company, 'ntext10-collegue'))
        res = collegue.get(URL)
        results = res.data['results'] if 'results' in res.data else res.data
        titres = {r['titre'] for r in results}
        self.assertNotIn('Privé', titres)
        self.assertIn('Partagé', titres)
        self.assertEqual(
            collegue.get(f'{URL}{prive.id}/').status_code, 404)
        self.assertEqual(
            collegue.get(f'{URL}{partage.id}/').status_code, 200)

    def test_report_of_another_company_is_not_reachable(self):
        etranger = RapportDefinition.objects.create(
            company=self.other, titre='Étranger', dataset='vitals_ntext10',
            partage=RapportDefinition.Partage.SOCIETE)
        self.assertEqual(
            self.api.get(f'{URL}{etranger.id}/').status_code, 404)
        self.assertEqual(
            self.api.post(f'{URL}{etranger.id}/executer/',
                          format='json').status_code, 404)


class RapportDefinitionExecutionTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT10 Exec')
        self.other = make_company('NTEXT10 Exec Autre')
        self.user = make_user(self.company, 'ntext10-exec')
        self.api = _auth(self.user)
        data_explorer.register_dataset(
            'vitals_ntext10', 'Vitals (test NTEXT10)',
            ['id', 'route', 'metric', 'value'], _vitals_provider)
        for route, metric, value in (
                ('/devis', 'LCP', 10), ('/devis', 'LCP', 5),
                ('/devis', 'INP', 2), ('/leads', 'LCP', 7)):
            WebVitalMetric.objects.create(
                company=self.company, route=route, metric=metric, value=value)
        # Données d'une AUTRE société : ne doivent jamais apparaître.
        WebVitalMetric.objects.create(
            company=self.other, route='/devis', metric='LCP', value=999)

    def _definition(self, **kwargs):
        kwargs.setdefault('titre', 'Valeur par route × métrique')
        kwargs.setdefault('dataset', 'vitals_ntext10')
        kwargs.setdefault('spec', {
            'group_by': ['route', 'metric'],
            'aggregates': [{'alias': 'total', 'fn': 'sum', 'field': 'value'}],
        })
        return RapportDefinition.objects.create(
            company=self.company, owner=self.user, **kwargs)

    def test_executer_returns_flat_rows_scoped_to_company(self):
        obj = self._definition()
        res = self.api.post(f'{URL}{obj.id}/executer/', format='json')
        self.assertEqual(res.status_code, 200, res.data)
        rows = res.data['rows']
        self.assertNotIn('pivot', res.data)
        totals = {(r['route'], r['metric']): r['total'] for r in rows}
        self.assertEqual(totals[('/devis', 'LCP')], 15)
        self.assertEqual(totals[('/devis', 'INP')], 2)
        self.assertEqual(totals[('/leads', 'LCP')], 7)
        # La ligne à 999 de l'autre société n'est jamais agrégée.
        self.assertNotIn(999, [r['total'] for r in rows])

    def test_executer_applies_pivot_spec_when_present(self):
        obj = self._definition(pivot_spec={
            'rows': ['route'], 'columns': ['metric'],
            'measure': 'total', 'agg': 'sum',
        })
        res = self.api.post(f'{URL}{obj.id}/executer/', format='json')
        self.assertEqual(res.status_code, 200, res.data)
        pivot = res.data['pivot']
        self.assertEqual(pivot['cells']['/devis']['LCP'], 15)
        self.assertEqual(pivot['cells']['/devis']['INP'], 2)
        self.assertEqual(pivot['cells']['/leads']['LCP'], 7)
        self.assertEqual(pivot['row_totals']['/devis'], 17)
        self.assertEqual(pivot['grand_total'], 24)

    def test_report_is_replayable_and_reflects_fresh_data(self):
        obj = self._definition(pivot_spec={
            'rows': ['route'], 'columns': ['metric'],
            'measure': 'total', 'agg': 'sum',
        })
        first = self.api.post(f'{URL}{obj.id}/executer/', format='json')
        self.assertEqual(first.data['pivot']['grand_total'], 24)
        WebVitalMetric.objects.create(
            company=self.company, route='/devis', metric='LCP', value=6)
        second = self.api.post(f'{URL}{obj.id}/executer/', format='json')
        self.assertEqual(second.data['pivot']['grand_total'], 30)

    def test_unknown_dataset_returns_404(self):
        obj = self._definition(dataset='dataset-inexistant', spec={})
        res = self.api.post(f'{URL}{obj.id}/executer/', format='json')
        self.assertEqual(res.status_code, 404)

    def test_field_outside_whitelist_returns_400(self):
        obj = self._definition(spec={'select': ['navigation_id']})
        res = self.api.post(f'{URL}{obj.id}/executer/', format='json')
        self.assertEqual(res.status_code, 400)

    def test_invalid_pivot_spec_returns_400(self):
        obj = self._definition(pivot_spec={'agg': 'sum'})  # aucun axe
        res = self.api.post(f'{URL}{obj.id}/executer/', format='json')
        self.assertEqual(res.status_code, 400)

    def test_unknown_pivot_key_returns_400(self):
        obj = self._definition(pivot_spec={'rows': ['route'], 'inconnu': 1})
        res = self.api.post(f'{URL}{obj.id}/executer/', format='json')
        self.assertEqual(res.status_code, 400)
