"""PUB128 — Harnais des tests terrain FT1-7.

``field_tests.py`` portait les 7 inconnues en CONSTANTES et la porte de préflight
``field_tests`` ne pouvait basculer que par un EDIT DE CODE. Prouve, sur
fixtures :

  * ``pending_keys`` consulte la DB d'abord (un ``FieldTestResult`` tranche son
    micro-test) ; les constantes restent le repli (sans société, comportement
    historique byte-identique) ;
  * enregistrer les 7 résultats fait passer la porte de préflight au VERT ;
  * l'écran liste les 7 micro-tests avec leur protocole, leur statut et le
    plafond de budget lu en config (jamais un littéral) ;
  * les structures de test passent par le circuit propose→approve NORMAL : des
    ``EngineAction`` PROPOSÉES, aucun ``status`` dans le payload, aucun ad set au
    ``campaign_id`` creux ; re-cliquer ne double pas la proposition ;
  * la saisie refuse une mesure vide et un micro-test inconnu ;
  * AUCUNE valeur en dur n'est modifiée ailleurs (les constantes restent en
    ``source='research'`` même quand la porte est verte).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from authentication.models import Company

from apps.adsengine import field_tests as ft, preflight
from apps.adsengine.models import (
    AdCampaignMirror, EngineAction, FieldTestResult,
)

User = get_user_model()
LIST_URL = '/api/django/adsengine/tests-terrain/'
TODAY = datetime.date(2026, 7, 13)


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FieldTestHarnessBase(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='PUB128 Co', slug='pub128')
        self.manager = make_user(
            self.company, 'manager', ['adsengine_view', 'adsengine_manage'])
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def tearDown(self):
        cache.clear()

    def _record(self, ftid, value='mesuré'):
        return ft.record_result(
            self.company, ftid, measured_value=value,
            evidence='capture jointe', measured_on=TODAY)

    def _record_all(self):
        for ftid in ft.FIELD_TESTS:
            self._record(ftid)


class PendingKeysReadsTheDbFirstTests(FieldTestHarnessBase):
    def test_without_a_company_the_constants_remain_the_only_source(self):
        # Comportement historique préservé : un appel PUR ne touche pas la DB.
        self.assertEqual(sorted(ft.pending_keys()),
                         sorted(ft.CONSTANTS.keys()))
        self.assertEqual(ft.settled_tests(None), frozenset())

    def test_a_recorded_result_settles_every_constant_of_its_test(self):
        constants_ft1 = ft.constants_for('FT1')
        self.assertTrue(constants_ft1)
        self._record('FT1')
        pending = ft.pending_keys(self.company)
        for key in constants_ft1:
            self.assertNotIn(key, pending)
        # Les autres restent ouvertes.
        self.assertIn('split_test_min_budget_mad', pending)
        self.assertEqual(ft.settled_tests(self.company), frozenset({'FT1'}))

    def test_results_are_company_scoped(self):
        other = Company.objects.create(nom='Autre', slug='pub128-autre')
        self._record('FT1')
        self.assertEqual(ft.settled_tests(other), frozenset())
        self.assertEqual(sorted(ft.pending_keys(other)),
                         sorted(ft.CONSTANTS.keys()))

    def test_recording_twice_updates_instead_of_duplicating(self):
        self._record('FT1', value='20 %')
        self._record('FT1', value='15 %')
        results = FieldTestResult.objects.filter(
            company=self.company, ft='FT1')
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().measured_value, '15 %')

    def test_an_empty_measure_is_refused(self):
        with self.assertRaises(ValueError):
            ft.record_result(self.company, 'FT1', measured_value='   ')
        self.assertFalse(FieldTestResult.objects.exists())

    def test_an_unknown_field_test_is_refused(self):
        with self.assertRaises(ValueError):
            ft.record_result(self.company, 'FT9', measured_value='x')


class PreflightGateTests(FieldTestHarnessBase):
    def test_the_gate_is_red_until_the_seven_results_are_recorded(self):
        gate = next(g for g in preflight.gates(self.company, today=TODAY)
                    if g.key == 'field_tests')
        self.assertFalse(gate.ok)
        self.assertIn('non tranchées', gate.detail_fr)

        self._record_all()

        gate = next(g for g in preflight.gates(self.company, today=TODAY)
                    if g.key == 'field_tests')
        self.assertTrue(gate.ok)
        self.assertEqual(gate.detail_fr, '')
        self.assertTrue(preflight.field_tests_complete(self.company))

    def test_no_hardcoded_constant_is_changed_anywhere(self):
        self._record_all()
        # La porte est verte, MAIS les constantes du code restent des bornes
        # documentaires : la valeur lue par le moteur n'a pas bougé.
        for key in ft.CONSTANTS:
            self.assertFalse(ft.is_field_tested(key), key)
        self.assertEqual(ft.value('learning_reset_budget_pct'), 20)

    def test_a_pure_call_keeps_the_historic_behaviour(self):
        self._record_all()
        # Sans société : les constantes décident (rien n'est tranché).
        self.assertFalse(preflight.field_tests_complete())


class FieldTestScreenApiTests(FieldTestHarnessBase):
    def test_the_list_serves_the_seven_tests_with_their_protocol(self):
        response = auth(self.viewer).get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['plafond_mad'],
                         ft.MICRO_TEST_MAX_DAILY_BUDGET_MAD)
        self.assertEqual(body['runbook'], 'docs/engine/field-tests.md')
        self.assertFalse(body['toutes_tranchees'])
        self.assertEqual([t['ft'] for t in body['tests']],
                         list(ft.FIELD_TESTS))
        first = body['tests'][0]
        self.assertTrue(first['label_fr'])
        self.assertTrue(first['question_fr'])
        self.assertTrue(first['protocole_fr'])
        self.assertTrue(first['mesure_fr'])
        self.assertFalse(first['tranche'])
        self.assertEqual(first['valeur_mesuree'], '')
        self.assertTrue(first['constantes'])
        self.assertIn('cle', first['constantes'][0])

    def test_recording_through_the_api_turns_the_test_settled(self):
        response = auth(self.manager).post(
            f'{LIST_URL}FT1/resultat/',
            {'measured_value': '12 %', 'evidence': 'capture',
             'measured_on': TODAY.isoformat()}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['ft'], 'FT1')
        self.assertTrue(body['tranche'])
        self.assertEqual(body['valeur_mesuree'], '12 %')
        self.assertEqual(body['mesure_le'], TODAY.isoformat())
        self.assertFalse(body['toutes_tranchees'])
        self.assertNotIn('learning_reset_budget_pct',
                         body['constantes_en_attente'])

        listing = auth(self.viewer).get(LIST_URL).json()
        ft1 = next(t for t in listing['tests'] if t['ft'] == 'FT1')
        self.assertTrue(ft1['tranche'])
        self.assertEqual(ft1['valeur_mesuree'], '12 %')

    def test_recording_the_seven_reports_all_settled(self):
        for ftid in ft.FIELD_TESTS:
            auth(self.manager).post(
                f'{LIST_URL}{ftid}/resultat/',
                {'measured_value': 'ok', 'measured_on': TODAY.isoformat()},
                format='json')
        body = auth(self.viewer).get(LIST_URL).json()
        self.assertTrue(body['toutes_tranchees'])
        self.assertEqual(body['constantes_en_attente'], [])

    def test_recording_without_any_date_falls_back_to_today(self):
        # PUB-P8/C4 — la clé ``measured_on`` est OMISE (case optionnelle laissée
        # vide côté écran) : l'enregistrement PASSE et le serveur date au jour
        # courant — jamais un 400 qui perdrait la mesure réelle.
        response = auth(self.manager).post(
            f'{LIST_URL}FT1/resultat/',
            {'measured_value': '12 %', 'evidence': 'capture'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['mesure_le'],
                         datetime.date.today().isoformat())
        self.assertEqual(FieldTestResult.objects.get(ft='FT1').measured_on,
                         datetime.date.today())

    def test_recording_with_an_empty_date_string_falls_back_to_today(self):
        # PUB-P8/C4, seconde ceinture : un ``''`` (formulaire qui envoie la clé
        # vide) vaut « omise », jamais « ce n'est pas une date ».
        response = auth(self.manager).post(
            f'{LIST_URL}FT2/resultat/',
            {'measured_value': '9', 'measured_on': ''}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['mesure_le'],
                         datetime.date.today().isoformat())

    def test_an_empty_measure_is_a_400(self):
        response = auth(self.manager).post(
            f'{LIST_URL}FT1/resultat/',
            {'measured_value': '', 'measured_on': TODAY.isoformat()},
            format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(FieldTestResult.objects.exists())

    def test_an_unknown_field_test_is_a_400(self):
        response = auth(self.manager).post(
            f'{LIST_URL}FT9/resultat/',
            {'measured_value': 'x', 'measured_on': TODAY.isoformat()},
            format='json')
        self.assertEqual(response.status_code, 400)

    def test_a_viewer_cannot_record(self):
        response = auth(self.viewer).post(
            f'{LIST_URL}FT1/resultat/',
            {'measured_value': 'x', 'measured_on': TODAY.isoformat()},
            format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(FieldTestResult.objects.exists())


class MicroTestStructuresTests(FieldTestHarnessBase):
    def test_structures_are_proposed_never_created(self):
        actions = ft.propose_micro_test_structures(self.company, 'FT1')

        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(action.kind, EngineAction.Kind.CREATE_CAMPAIGN)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(action.payload['field_test'], 'FT1')
        self.assertTrue(action.payload['name'].startswith('TEST-TERRAIN FT1'))
        self.assertTrue(action.payload['objective'])
        # Naissance PAUSED : aucun statut ne voyage jamais dans le payload.
        self.assertNotIn('status', action.payload)
        self.assertIn(str(ft.MICRO_TEST_MAX_DAILY_BUDGET_MAD),
                      action.reason_fr)

    def test_the_adset_is_only_proposed_once_the_campaign_exists(self):
        first = ft.propose_micro_test_structures(self.company, 'FT1')
        campaign_name = first[0].payload['name']
        # La campagne a été approuvée puis créée : son miroir existe.
        AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-ft1', name=campaign_name,
            status='PAUSED')
        EngineAction.objects.filter(pk=first[0].pk).update(
            status=EngineAction.Statut.APPLIQUEE)

        actions = ft.propose_micro_test_structures(self.company, 'FT1')

        self.assertEqual(len(actions), 1)
        adset = actions[0]
        self.assertEqual(adset.kind, EngineAction.Kind.CREATE_ADSET)
        # Jamais un ``campaign_id`` creux (classe de défaut PUB119).
        self.assertEqual(adset.payload['campaign_id'], 'cmp-ft1')
        self.assertEqual(
            adset.payload['extra_fields']['daily_budget'],
            ft.MICRO_TEST_MAX_DAILY_BUDGET_MAD * 100)
        self.assertNotIn('status', adset.payload)

    def test_clicking_twice_does_not_duplicate_the_proposal(self):
        first = ft.propose_micro_test_structures(self.company, 'FT1')
        again = ft.propose_micro_test_structures(self.company, 'FT1')
        self.assertEqual([a.pk for a in first], [a.pk for a in again])
        self.assertEqual(EngineAction.objects.filter(
            company=self.company).count(), 1)

    def test_an_unknown_field_test_is_refused(self):
        with self.assertRaises(ValueError):
            ft.propose_micro_test_structures(self.company, 'FT9')
        with self.assertRaises(ValueError):
            ft.propose_micro_test_structures(
                self.company, 'FT1', template_key='gabarit-inconnu')

    def test_the_api_proposes_and_reports_the_cap(self):
        response = auth(self.manager).post(
            f'{LIST_URL}FT1/structures/', {'city': 'Casablanca'},
            format='json')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['ft'], 'FT1')
        self.assertEqual(body['plafond_mad'],
                         ft.MICRO_TEST_MAX_DAILY_BUDGET_MAD)
        self.assertEqual(len(body['actions']), 1)
        self.assertEqual(body['actions'][0]['kind'], 'create_campaign')
        self.assertEqual(
            EngineAction.objects.get(
                company=self.company).payload['city'], 'Casablanca')

    def test_a_viewer_cannot_propose_structures(self):
        response = auth(self.viewer).post(
            f'{LIST_URL}FT1/structures/', {}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(EngineAction.objects.exists())


class MicroTestBudgetCurrencyTests(FieldTestHarnessBase):
    """PUB-P8/C5 — le plafond 30 MAD s'écrit en unités MINEURES de la devise DU
    COMPTE : sur un compte non-MAD il ne veut RIEN dire (30 × 100 = 30 USD,
    ≈ 10× le plafond). Refus fail-closed, raison FR, aucun taux inventé."""

    def _connection(self, currency):
        from apps.adsengine.models import MetaConnection
        return MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', currency=currency,
            enabled=True, credentials={'access_token': 'tok'})

    def test_a_usd_account_is_refused_with_the_reason(self):
        self._connection('USD')
        with self.assertRaises(ValueError) as ctx:
            ft.propose_micro_test_structures(self.company, 'FT1')
        message = str(ctx.exception)
        self.assertIn('Devise du compte USD', message)
        self.assertIn('décision fondateur', message)
        self.assertIn(str(ft.MICRO_TEST_MAX_DAILY_BUDGET_MAD), message)
        self.assertFalse(EngineAction.objects.exists())

    def test_the_api_renders_that_refusal_as_a_400_in_french(self):
        self._connection('EUR')
        response = auth(self.manager).post(
            f'{LIST_URL}FT1/structures/', {}, format='json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Devise du compte EUR', response.json()['detail'])
        self.assertFalse(EngineAction.objects.exists())

    def test_a_mad_account_still_proposes(self):
        self._connection('MAD')
        actions = ft.propose_micro_test_structures(self.company, 'FT1')
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, EngineAction.Kind.CREATE_CAMPAIGN)


class ProtocolsAlignedWithTheRunbookTests(TestCase):
    def test_every_field_test_declares_a_protocol(self):
        for ftid in ft.FIELD_TESTS:
            protocol = ft.protocol_for(ftid)
            self.assertIsNotNone(protocol, ftid)
            self.assertTrue(protocol['label_fr'], ftid)
            self.assertTrue(protocol['question_fr'], ftid)
            self.assertGreaterEqual(len(protocol['protocol_fr']), 2, ftid)
            self.assertTrue(protocol['measure_fr'], ftid)

    def test_an_unknown_field_test_has_no_protocol(self):
        self.assertIsNone(ft.protocol_for('FT9'))
