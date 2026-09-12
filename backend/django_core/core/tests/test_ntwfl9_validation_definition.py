"""Tests NTWFL9 — validation d'une définition de workflow AVANT sauvegarde.

Couvre l'acceptance criteria : sauvegarder une définition à 0 étape est
rejeté avec un message clair, une boucle de garde (``etape_alternative_si_echec``)
est détectée et bloquée ; une étape manuelle sans ``role_requis`` est
également rejetée ; une définition valide continue de fonctionner.
"""
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase

from core import workflow
from core.models import WorkflowDefinition

BASE = '/api/django/core/workflow-definitions/'


class ValiderDefinitionStepsPureTests(TenantAPITestCase):
    """Fonction pure ``core.workflow.valider_definition_steps`` — sans DB."""

    def test_liste_vide_rejetee(self):
        erreurs = workflow.valider_definition_steps([])
        self.assertEqual(len(erreurs), 1)
        self.assertIn('au moins une étape', erreurs[0])

    def test_etape_manuelle_sans_role_rejetee(self):
        erreurs = workflow.valider_definition_steps([
            {'ordre': 1, 'nom': 'Étape 1', 'type_approbation': 'manuelle',
             'role_requis': ''},
        ])
        self.assertTrue(any('rôle requis' in e for e in erreurs))

    def test_etape_manuelle_avec_role_valide(self):
        erreurs = workflow.valider_definition_steps([
            {'ordre': 1, 'nom': 'Étape 1', 'type_approbation': 'manuelle',
             'role_requis': 'Responsable'},
        ])
        self.assertEqual(erreurs, [])

    def test_etape_auto_sans_role_valide(self):
        # Une étape AUTO n'a pas besoin de role_requis (seule 'manuelle' est
        # concernée par l'exigence NTWFL9).
        erreurs = workflow.valider_definition_steps([
            {'ordre': 1, 'nom': 'Auto', 'type_approbation': 'auto',
             'role_requis': ''},
        ])
        self.assertEqual(erreurs, [])

    def test_boucle_infinie_detectee(self):
        steps = [
            {'ordre': 1, 'nom': 'A', 'type_approbation': 'auto',
             'etape_alternative_si_echec': 2},
            {'ordre': 2, 'nom': 'B', 'type_approbation': 'auto',
             'etape_alternative_si_echec': 1},
        ]
        erreurs = workflow.valider_definition_steps(steps)
        self.assertTrue(any('boucle infinie' in e for e in erreurs))

    def test_auto_reference_valide_sans_boucle(self):
        steps = [
            {'ordre': 1, 'nom': 'A', 'type_approbation': 'auto',
             'etape_alternative_si_echec': 2},
            {'ordre': 2, 'nom': 'B', 'type_approbation': 'auto'},
        ]
        erreurs = workflow.valider_definition_steps(steps)
        self.assertEqual(erreurs, [])


class WorkflowDefinitionApiValidationTests(TenantAPITestCase):
    """Intégration API — le rejet est bien renvoyé en 400 par le CRUD."""

    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def test_creation_a_zero_etape_rejetee(self):
        r = self._admin().post(BASE, {
            'nom': 'Vide', 'description': '', 'steps': [],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('steps', r.json())
        self.assertEqual(WorkflowDefinition.objects.count(), 0)

    def test_creation_sans_champ_steps_du_tout_rejetee(self):
        r = self._admin().post(BASE, {
            'nom': 'Sans steps', 'description': '',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_creation_avec_boucle_rejetee(self):
        payload = {
            'nom': 'Boucle',
            'steps': [
                {'ordre': 1, 'nom': 'A', 'type_approbation': 'auto',
                 'etape_alternative_si_echec': 2},
                {'ordre': 2, 'nom': 'B', 'type_approbation': 'auto',
                 'etape_alternative_si_echec': 1},
            ],
        }
        r = self._admin().post(BASE, payload, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_creation_valide_toujours_acceptee(self):
        payload = {
            'nom': 'Valide',
            'steps': [
                {'ordre': 1, 'nom': 'Étape 1', 'type_approbation': 'manuelle',
                 'role_requis': 'Responsable'},
            ],
        }
        r = self._admin().post(BASE, payload, format='json')
        self.assertEqual(r.status_code, 201, r.content)

    def test_update_sans_toucher_aux_steps_ne_revalide_pas(self):
        # PACT124 : renommer une définition SANS envoyer `steps` ne doit
        # jamais être bloqué par cette validation (comportement historique
        # préservé — voir WorkflowsScreen.jsx).
        cr = self._admin().post(BASE, {
            'nom': 'Def', 'steps': [
                {'ordre': 1, 'nom': 'Étape 1', 'type_approbation': 'manuelle',
                 'role_requis': 'Responsable'},
            ],
        }, format='json').json()
        r = self._admin().put(
            f"{BASE}{cr['id']}/", {'nom': 'Def renommée'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
