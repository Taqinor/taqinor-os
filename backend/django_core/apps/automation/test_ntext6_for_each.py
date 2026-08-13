"""NTEXT6 — boucle FOR_EACH sur une liste dans une automatisation.

Une étape/règle ``FOR_EACH`` itère une liste résolue depuis le registre FERMÉ
``automation.list_sources`` (jamais un accès modèle arbitraire) et exécute ses
sous-actions par élément, avec une borne dure anti-DoS (200 itérations,
troncature dite dans le message du run).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.customfields.models import CustomFieldDef, CustomObjectDef, CustomRecord

from apps.automation import engine, list_sources
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ForEachActionTests(TestCase):
    def setUp(self):
        self.co = make_company('ntext6-a', 'NTEXT6 A')
        self.objet = CustomObjectDef.objects.create(
            company=self.co, code='reservation', libelle='Réservation stock')
        CustomFieldDef.objects.create(
            company=self.co, module='custom:reservation', code='titre',
            libelle='Titre', type='text', obligatoire=True)
        self.lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')

    def _rule(self, **cfg):
        return AutomationRule.objects.create(
            company=self.co, nom='Boucle lignes',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.FOR_EACH, action_config=cfg)

    def test_iterates_context_list_and_runs_sub_actions(self):
        rule = self._rule(
            source='contexte:lignes',
            sous_actions=[{
                'action_type': ActionType.CREATE_CUSTOM_RECORD,
                'action_config': {
                    'object_code': 'reservation',
                    'data': {'titre': 'Réserver {designation}'},
                },
            }])
        status, message = engine.run_action(
            rule, self.lead, self.co,
            context={'lignes': [
                {'designation': 'Panneau'}, {'designation': 'Onduleur'}]})
        self.assertEqual(status, AutomationRun.Status.SUCCESS)
        titres = sorted(
            r.data['titre']
            for r in CustomRecord.objects.filter(company=self.co))
        self.assertEqual(titres, ['Réserver Onduleur', 'Réserver Panneau'])
        self.assertIn('2 élément(s)', message)

    def test_hard_bound_truncates_and_is_logged(self):
        rule = self._rule(
            source='contexte:lignes',
            sous_actions=[{
                'action_type': ActionType.CREATE_CUSTOM_RECORD,
                'action_config': {
                    'object_code': 'reservation',
                    'data': {'titre': 'L{element_index}'},
                },
            }])
        trop = [{'designation': f'L{i}'}
                for i in range(list_sources.MAX_ITERATIONS + 25)]
        status, message = engine.run_action(
            rule, self.lead, self.co, context={'lignes': trop})
        self.assertEqual(status, AutomationRun.Status.SUCCESS)
        self.assertEqual(
            CustomRecord.objects.filter(company=self.co).count(),
            list_sources.MAX_ITERATIONS)
        self.assertIn('tronquée', message)

    def test_unknown_source_is_refused_without_effect(self):
        rule = self._rule(
            source='apps.ventes.models.Devis',
            sous_actions=[{
                'action_type': ActionType.CREATE_CUSTOM_RECORD,
                'action_config': {'object_code': 'reservation',
                                  'data': {'titre': 'x'}},
            }])
        status, message = engine.run_action(rule, self.lead, self.co)
        self.assertEqual(status, AutomationRun.Status.SKIPPED)
        self.assertIn('non autorisée', message)
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_empty_list_is_noop(self):
        rule = self._rule(
            source='contexte:lignes',
            sous_actions=[{'action_type': ActionType.SET_FIELD,
                           'action_config': {'field': 'priorite',
                                             'value': 'haute'}}])
        status, _message = engine.run_action(
            rule, self.lead, self.co, context={'lignes': []})
        self.assertEqual(status, AutomationRun.Status.NOOP)

    def test_no_sub_actions_is_noop(self):
        rule = self._rule(source='contexte:lignes')
        status, _message = engine.run_action(
            rule, self.lead, self.co, context={'lignes': [{'a': 1}]})
        self.assertEqual(status, AutomationRun.Status.NOOP)

    def test_nested_loop_is_refused(self):
        rule = self._rule(
            source='contexte:lignes',
            sous_actions=[{'action_type': ActionType.FOR_EACH,
                           'action_config': {'source': 'contexte:lignes'}}])
        status, _message = engine.run_action(
            rule, self.lead, self.co, context={'lignes': [{'a': 1}]})
        self.assertEqual(status, AutomationRun.Status.FAILED)
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_custom_object_source_is_company_scoped(self):
        CustomRecord.objects.create(
            company=self.co, objet=self.objet, data={'titre': 'A'})
        autre = make_company('ntext6-b', 'NTEXT6 B')
        objet_autre = CustomObjectDef.objects.create(
            company=autre, code='reservation', libelle='Réservation stock')
        CustomRecord.objects.create(
            company=autre, objet=objet_autre, data={'titre': 'B'})
        elements, tronquee, erreur = list_sources.resolve_list(
            'objet_custom:reservation', self.lead, self.co, {})
        self.assertIsNone(erreur)
        self.assertFalse(tronquee)
        self.assertEqual([e['titre'] for e in elements], ['A'])
