"""CIQ211 — réglages société C&I SANS valeur par défaut (D-CIQ-15,
convention 16) : scénarios de sensibilité saisis par Reda, chacun avec sa
source (au plus 4), et autorisation de nommer le crédit-bail seulement avec
la référence de l'avis juridique. Migration additive et réversible."""
import unittest
from importlib import import_module
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import migrations
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres import tariff
from authentication.models import Company

User = get_user_model()

URL = '/api/django/parametres/tarification/'
URL_MAJ = '/api/django/parametres/tarification/update/'
SCENARIO = {'cle': 'tarif_kwh', 'variation_pct': -10,
            'source': 'Historique des tarifs ONEE publiés 2015-2025'}


class ValidationPureTest(unittest.TestCase):
    def test_vierge_valide(self):
        vierge = SimpleNamespace(sensibilites_ci=[],
                                 mention_credit_bail_autorisee=False,
                                 mention_credit_bail_source='')
        self.assertEqual(tariff.erreurs_reglages_tarif(vierge), {})

    def test_scenario_sans_source_nomme_le_champ(self):
        erreurs = tariff.erreurs_sensibilites_ci(
            [SCENARIO, {'cle': 'degradation', 'variation_pct': 5,
                        'source': ' '}])
        self.assertIn('sensibilites_ci', erreurs)
        self.assertIn('sensibilites_ci[1].source', erreurs['sensibilites_ci'])

    def test_formes_refusees(self):
        for faute in ([{**SCENARIO, 'cle': 'inflation'}],
                      [{**SCENARIO, 'variation_pct': 'abc'}],
                      [{**SCENARIO, 'variation_pct': -100}],
                      [{**SCENARIO, 'montant': 3}],
                      [SCENARIO] * (tariff.SENSIBILITES_CI_MAX + 1),
                      {'cle': 'tarif_kwh'}):
            with self.subTest(faute=faute):
                self.assertIn('sensibilites_ci',
                              tariff.erreurs_sensibilites_ci(faute))

    def test_quatre_scenarios_sources_acceptes(self):
        scenarios = [{**SCENARIO, 'cle': cle}
                     for cle in tariff.SENSIBILITE_CI_CLES]
        self.assertEqual(len(scenarios), tariff.SENSIBILITES_CI_MAX)
        self.assertEqual(tariff.erreurs_sensibilites_ci(scenarios), {})

    def test_credit_bail_sans_source_refuse(self):
        self.assertIn('mention_credit_bail_source',
                      tariff.erreurs_mention_credit_bail(True, ''))
        self.assertEqual(
            tariff.erreurs_mention_credit_bail(True, 'Avis Me X 2026-10-01'),
            {})
        self.assertEqual(tariff.erreurs_mention_credit_bail(False, ''), {})


class ApiReglagesCiTest(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ciq211-co', defaults={'nom': 'CIQ211 Co'})[0]
        self.admin = User.objects.create_user(
            username='ciq211_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_lecture_vierge(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['sensibilites_ci'], [])
        self.assertIs(resp.data['mention_credit_bail_autorisee'], False)
        self.assertEqual(resp.data['mention_credit_bail_source'], '')

    def test_scenario_sans_source_400_nommant_le_champ(self):
        resp = self.api.patch(URL_MAJ, {'sensibilites_ci': [
            {'cle': 'production', 'variation_pct': -5, 'source': ''}]},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('sensibilites_ci', resp.data)
        self.assertIn('sensibilites_ci[0].source',
                      str(resp.data['sensibilites_ci']))

    def test_credit_bail_vrai_sans_source_400(self):
        resp = self.api.patch(
            URL_MAJ, {'mention_credit_bail_autorisee': True}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('mention_credit_bail_source', resp.data)

    def test_saisie_valide_aller_retour_identique(self):
        corps = {'sensibilites_ci': [SCENARIO],
                 'mention_credit_bail_autorisee': True,
                 'mention_credit_bail_source': 'Avis juridique du 01/10/2026'}
        resp = self.api.patch(URL_MAJ, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lu = self.api.get(URL).data
        self.assertEqual(lu['sensibilites_ci'], [SCENARIO])
        resp = self.api.patch(URL_MAJ, {c: lu[c] for c in corps},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        relu = self.api.get(URL).data
        for champ in corps:
            self.assertEqual(relu[champ], lu[champ])

    def test_migration_additive_donc_reversible(self):
        module = import_module(
            'apps.parametres.migrations.0120_ciq211_reglages_ci')
        noms = set()
        for op in module.Migration.operations:
            self.assertIsInstance(op, migrations.AddField)
            self.assertTrue(op.reversible)
            noms.add(op.name)
        self.assertEqual(noms, {'sensibilites_ci',
                                'mention_credit_bail_autorisee',
                                'mention_credit_bail_source'})
