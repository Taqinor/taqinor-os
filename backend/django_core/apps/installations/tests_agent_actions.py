"""AG9 — Tests des actions agentiques de l'app installations.

Vérifie que le catalogue AG1 porte bien les deux actions remplaçant les outils
FastAPI codés en dur (planifier une visite, brouillonner un BC chantier), avec
le bon endpoint / méthode / permission, le ``<id>`` chantier modélisé en input
requis pour ``commander-besoin``, et SANS jamais exposer ``company`` (forcé
côté serveur).
"""
from django.test import TestCase

from apps.agent.registry import all_actions
from apps.installations.agent_actions import (
    PLANIFIER_VISITE_MAINTENANCE,
    BROUILLON_COMMANDE_CHANTIER,
    INSTALLATIONS_ACTIONS,
    register_installation_actions,
)


class InstallationsAgentActionsTest(TestCase):
    def _by_key(self, key):
        return {a.key: a for a in all_actions()}.get(key)

    def test_both_actions_registered(self):
        keys = {a.key for a in all_actions()}
        self.assertIn('installations.intervention.planifier_visite', keys)
        self.assertIn('installations.chantier.commander_besoin', keys)

    def test_planifier_visite_metadata(self):
        a = self._by_key('installations.intervention.planifier_visite')
        self.assertIsNotNone(a)
        self.assertEqual(a, PLANIFIER_VISITE_MAINTENANCE)
        self.assertEqual(a.method, 'POST')
        self.assertEqual(
            a.endpoint, '/api/django/installations/interventions/')
        self.assertEqual(a.required_permission, 'installation_gerer')
        self.assertEqual(a.risk, 'internal')
        # Reproduit le comportement FastAPI : type controle + date_prevue.
        props = a.inputs['properties']
        self.assertEqual(props['type_intervention']['default'], 'controle')
        self.assertIn('date_prevue', props)
        self.assertEqual(
            set(a.inputs['required']), {'installation', 'date_prevue'})

    def test_commander_besoin_metadata(self):
        a = self._by_key('installations.chantier.commander_besoin')
        self.assertIsNotNone(a)
        self.assertEqual(a, BROUILLON_COMMANDE_CHANTIER)
        self.assertEqual(a.method, 'POST')
        self.assertEqual(
            a.endpoint,
            '/api/django/installations/chantiers/{id}/commander-besoin/')
        self.assertEqual(a.required_permission, 'installation_gerer')
        self.assertEqual(a.risk, 'internal')
        # Le <id> chantier est un input requis consommé par le gabarit de chemin.
        self.assertIn('id', a.inputs['properties'])
        self.assertIn('id', a.inputs['required'])

    def test_company_never_in_inputs(self):
        for a in INSTALLATIONS_ACTIONS:
            self.assertNotIn(
                'company', a.inputs.get('properties', {}),
                f"{a.key} ne doit jamais exposer company (forcé serveur)")

    def test_register_is_idempotent(self):
        before = len(all_actions())
        register_installation_actions()
        register_installation_actions()
        self.assertEqual(len(all_actions()), before)

    def test_as_dict_serialisable(self):
        for a in INSTALLATIONS_ACTIONS:
            d = a.as_dict()
            self.assertEqual(d['method'], 'POST')
            self.assertEqual(d['required_permission'], 'installation_gerer')
            self.assertIn('endpoint', d)
