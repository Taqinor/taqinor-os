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
        # REP4 — garde réelle (ASEC72) ; une intervention datée entre dans la
        # journée d'un technicien : proposition à confirmer.
        self.assertEqual(a.required_permission, 'intervention_gerer')
        self.assertEqual(a.risk, 'outward')
        self.assertTrue(a.confirm_summary)
        # Le relais n'applique pas un ``default`` : type REQUIS, valeur unique
        # exacte du modèle (Intervention.Type.CONTROLE).
        from apps.installations.models import Intervention
        props = a.inputs['properties']
        self.assertNotIn('default', props['type_intervention'])
        self.assertEqual(props['type_intervention']['enum'],
                         [Intervention.Type.CONTROLE.value])
        self.assertEqual(props['date_prevue']['format'], 'date')
        self.assertEqual(
            set(a.inputs['required']),
            {'installation', 'type_intervention', 'date_prevue'})
        # Vrai : sans technicien, personne n'est notifié.
        self.assertIn('sans technicien', a.description)
        self.assertLessEqual(len(a.description), 600)

    def test_commander_besoin_metadata(self):
        a = self._by_key('installations.chantier.commander_besoin')
        self.assertIsNotNone(a)
        self.assertEqual(a, BROUILLON_COMMANDE_CHANTIER)
        self.assertEqual(a.method, 'POST')
        self.assertEqual(
            a.endpoint,
            '/api/django/installations/chantiers/{id}/commander-besoin/')
        # REP3 — garde réelle de la route (ACHT54) ; deux effets sur des
        # données existantes (BCF brouillons + chantier Signé → Matériel
        # commandé) : proposition à confirmer qui dit les deux.
        self.assertEqual(a.required_permission, 'achats_commander')
        self.assertEqual(a.risk, 'outward')
        self.assertIn('BROUILLONS', a.confirm_summary)
        self.assertIn('Matériel commandé', a.confirm_summary)
        self.assertIn('Matériel commandé', a.description)
        # Le <id> chantier est un input requis consommé par le gabarit de chemin.
        self.assertIn('id', a.inputs['properties'])
        self.assertIn('id', a.inputs['required'])
        props = a.inputs['properties']
        self.assertEqual(props['produits']['items'], {'type': 'integer'})
        self.assertEqual(props['fournisseurs']['additionalProperties'],
                         {'type': 'integer'})

    def test_permission_du_catalogue_est_la_garde_de_la_route(self):
        """REP3/REP4 — chaque code du catalogue est un code que la route
        EXIGE (gardes lues sur la vue, comme le test de parité de l'agent)."""
        from apps.agent.tests.test_registry import _gardes_de_la_route
        for a in (BROUILLON_COMMANDE_CHANTIER, PLANIFIER_VISITE_MAINTENANCE):
            codes, _admin, _modules = _gardes_de_la_route(a)
            self.assertIn(a.required_permission, codes, a.key)

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
            self.assertEqual(d['required_permission'], a.required_permission)
            self.assertIn('endpoint', d)
