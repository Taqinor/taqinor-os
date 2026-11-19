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
    ETAT_CHANTIER,
    LISTE_CHANTIERS,
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
        # Objets nommés : le relais n'affiche que le LABEL en 1re ligne de
        # l'aperçu (confirm_summary écarté) — il dit dans la journée de qui.
        self.assertIn('journée du technicien désigné', a.label)
        self.assertLessEqual(len(a.label), 90)
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
        # Servie à TOUS (hors lot) : ne cite aucun outil du lot copilote, que
        # le compte peut ne pas avoir.
        du_lot = {x.key for x in all_actions() if x.lot == 'copilote'}
        for action in INSTALLATIONS_ACTIONS:
            if action.lot is None:
                self.assertFalse([k for k in du_lot if k in action.description],
                                 action.key)

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
        # Le LABEL seul (1re ligne de l'aperçu nommé) dit les deux effets.
        self.assertIn('BROUILLONS', a.label)
        self.assertIn('Matériel commandé', a.label)
        self.assertLessEqual(len(a.label), 90)
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

    def test_etat_chantier_metadata(self):
        """CHTA2 — lecture du lot copilote : carte, objet nommé, code de
        lecture du module que la route exige (LectureDuModule)."""
        from apps.agent.tests.test_registry import _gardes_de_la_route
        from authentication.permissions import codes_du_module
        a = self._by_key('installations.chantier.etat')
        self.assertEqual(a, ETAT_CHANTIER)
        self.assertEqual((a.method, a.risk, a.lot, a.carte),
                         ('GET', 'internal', 'copilote', 'fiche_chantier'))
        self.assertEqual(
            a.endpoint, '/api/django/installations/chantiers/{id}/etat-assistant/')
        self.assertEqual(a.objets, {'id': 'chantier'})
        self.assertEqual(a.inputs['required'], ['id'])
        self.assertTrue(a.description.startswith('Sert à'))
        for section in ('Ne pas utiliser pour', 'Exemple', 'Résultat'):
            self.assertIn(section, a.description)
        _codes, _admin, modules = _gardes_de_la_route(a)
        self.assertIn('installations', modules)
        self.assertIn(a.required_permission, codes_du_module('installations'))

    def test_liste_chantiers_metadata(self):
        """CHTA3 — lecture du lot copilote ; les statuts offerts au modèle
        sont exactement ceux que la route accepte."""
        from apps.installations.views.assistant import STATUTS_LISTE
        a = self._by_key('installations.chantiers.liste')
        self.assertEqual(a, LISTE_CHANTIERS)
        self.assertEqual((a.method, a.risk, a.lot, a.carte),
                         ('GET', 'internal', 'copilote', 'liste_chantiers'))
        self.assertEqual(a.endpoint, '/api/django/installations/chantiers/assistant/')
        props = a.inputs['properties']
        self.assertEqual(props['vue']['enum'], ['en_cours', 'bloques', 'poses_semaine'])
        self.assertEqual(tuple(props['statut']['enum']), STATUTS_LISTE)
        self.assertEqual(props['limite']['maximum'], 25)
        self.assertEqual(a.inputs['required'], [])
        self.assertEqual(a.required_permission, 'installation_voir')

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
            self.assertEqual(d['method'], a.method.upper())
            self.assertEqual(d['required_permission'], a.required_permission)
            self.assertIn('endpoint', d)


class InstallationsLibellesAssistantTest(TestCase):
    """Copilote vague 2 — l'aperçu d'une proposition NOMME le chantier et
    l'intervention (``selectors_libelles.libelles_installations`` via la
    table de l'agent) : société, droit de lecture du module et portée des
    listes ; sinon absent."""

    def test_objets_declares_et_nommes_dans_la_portee(self):
        from datetime import date

        from django.contrib.auth import get_user_model

        from authentication.models import Company
        from apps.agent.libelles import libelles_objets
        from apps.crm.models import Client
        from apps.installations.models import Installation, Intervention
        from apps.roles.models import Role
        from apps.roles.permissions_registre import SCOPE_SELF
        self.assertEqual(PLANIFIER_VISITE_MAINTENANCE.objets,
                         {'installation': 'chantier', 'technicien': 'utilisateur'})
        self.assertEqual(BROUILLON_COMMANDE_CHANTIER.objets,
                         {'id': 'chantier', 'fournisseur': 'fournisseur'})
        company = Company.objects.create(nom='AG9 Lib', slug='ag9-lib')
        client = Client.objects.create(company=company, nom='Benali')
        chantier = Installation.objects.create(
            company=company, reference='CHT-LIB-1', client=client, site_ville='Casablanca')
        intervention = Intervention.objects.create(
            company=company, installation=chantier, date_prevue=date(2026, 11, 25),
            type_intervention=Intervention.Type.CONTROLE)
        ids = {'chantier': chantier.pk, 'intervention': intervention.pk}

        def libelles(permissions, societe=company):
            user = get_user_model().objects.create_user(
                username=f'ag9_lib_{len(permissions)}_{societe.pk}', password='x', company=societe,
                role=Role.objects.create(company=societe, nom=f'L{len(permissions)}',
                                         permissions=permissions))
            return libelles_objets(user, ids)
        self.assertEqual(libelles(['intervention_gerer']), {
            'chantier': 'CHT-LIB-1 — Benali, Casablanca (Signé)',
            'intervention': 'Contrôle — chantier CHT-LIB-1, 25/11/2026'})
        self.assertEqual(libelles(['crm_voir', 'ventes_voir']), {})
        self.assertEqual(libelles(['intervention_gerer', 'installation_gerer', SCOPE_SELF]), {})
        autre = Company.objects.create(nom='AG9 Lib 2', slug='ag9-lib-2')
        self.assertEqual(libelles(['intervention_gerer'], autre), {})
