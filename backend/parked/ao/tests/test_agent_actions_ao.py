"""AOF167 — actions agentiques AO : câblées, en lecture, et bornées.

Trois garanties, chacune écrite pour SURVIVRE à l'ajout d'une action par un
futur agent pressé (le test lit ``ACTIONS``, il ne liste pas les cinq à la
main) :

  1. **Chaque action déclarée est RÉELLEMENT câblée** — son endpoint résout une
     route AO existante. Une action qui pointe dans le vide est exactement la
     dérive qu'ARC41 interdit.
  2. **Aucune action n'écrit un montant, ne déclenche un dépôt, ni ne touche
     l'économie directeur.** Toutes sont des ``GET``, toutes sont sous
     ``/api/django/ao/``, aucune ne contient un fragment interdit.
  3. **La permission est vérifiée ACTION PAR ACTION** : chacune déclare
     ``ao_voir``, le code de LECTURE réel du domaine — jamais un code
     d'écriture, jamais ``None``.

Run :
    python manage.py test apps.ao.tests.test_agent_actions_ao -v2
"""
import re

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from apps.ao.agent_actions import (
    ACTIONS, FRAGMENTS_INTERDITS, PREFIXE_ENDPOINT, register_actions,
)
from apps.ao.permissions import AO_GERER, AO_RENTABILITE_VOIR, AO_VOIR
from apps.ao.platform import PLATFORM
from apps.agent.registry import RISK_INTERNAL

#: Valeurs d'échantillon pour instancier un gabarit d'endpoint.
ECHANTILLON = {'id': '1', 'lead_id': '1', 'toiture_id': '1'}


def _chemin_concret(endpoint):
    """Gabarit -> chemin résolvable : ``{id}`` remplacé, requête retirée."""
    chemin = endpoint.split('?', 1)[0]
    return re.sub(r'\{(\w+)\}',
                  lambda m: ECHANTILLON.get(m.group(1), '1'), chemin)


class ChaqueActionDeclareeEstReellementCablee(SimpleTestCase):
    def test_il_y_a_des_actions(self):
        self.assertTrue(ACTIONS)

    def test_chaque_endpoint_resout_une_route_reelle(self):
        for action in ACTIONS:
            chemin = _chemin_concret(action.endpoint)
            try:
                resolve(chemin)
            except Resolver404:  # pragma: no cover - message d'échec explicite
                self.fail(
                    "action %s : l'endpoint %s ne résout AUCUNE route — "
                    'action déclarée mais non câblée (ARC41).'
                    % (action.key, chemin))

    def test_le_manifeste_pointe_ce_module(self):
        self.assertEqual(PLATFORM['agent_actions_module'],
                         'apps.ao.agent_actions')

    def test_l_enregistrement_est_idempotent(self):
        from apps.agent.registry import _REGISTRY

        register_actions()
        avant = dict(_REGISTRY)
        register_actions()
        self.assertEqual(set(_REGISTRY), set(avant))
        for action in ACTIONS:
            self.assertIn(action.key, _REGISTRY, action.key)

    def test_chaque_cle_est_unique_et_prefixee_ao(self):
        cles = [a.key for a in ACTIONS]
        self.assertEqual(len(cles), len(set(cles)))
        for cle in cles:
            self.assertTrue(cle.startswith('ao.'), cle)


class AucuneActionNEcritNiNeDepose(SimpleTestCase):
    def test_toutes_les_actions_sont_en_lecture(self):
        for action in ACTIONS:
            self.assertEqual(action.method.upper(), 'GET', action.key)

    def test_toutes_les_actions_restent_dans_le_perimetre_ao(self):
        for action in ACTIONS:
            self.assertTrue(action.endpoint.startswith(PREFIXE_ENDPOINT),
                            '%s -> %s' % (action.key, action.endpoint))

    def test_aucun_endpoint_ne_porte_un_fragment_interdit(self):
        """Montant, dépôt, économie : trois portes qui restent fermées."""
        for action in ACTIONS:
            cible = action.endpoint.lower()
            for fragment in FRAGMENTS_INTERDITS:
                self.assertNotIn(
                    fragment, cible,
                    "action %s : l'endpoint %s touche « %s » — écrire un "
                    'montant, déclencher un dépôt ou lire une marge ne sont '
                    "pas des actions d'agent." % (action.key, action.endpoint,
                                                  fragment))

    def test_aucune_action_n_est_irreversible_ou_sortante(self):
        for action in ACTIONS:
            self.assertEqual(action.risk, RISK_INTERNAL, action.key)

    def test_aucune_action_ne_mentionne_un_prix_d_achat(self):
        for action in ACTIONS:
            texte = ('%s %s' % (action.label, action.description)).lower()
            for interdit in ('prix_achat', 'coût de revient', 'marge',
                             'bénéfice'):
                # La description PEUT dire qu'elle n'expose PAS de marge :
                # on n'interdit que la promesse d'en RENDRE une.
                if interdit == 'marge' and 'aucune marge' in texte:
                    continue
                self.assertNotIn(interdit, texte, action.key)


class LaPermissionEstVerifieeActionParAction(SimpleTestCase):
    def test_chaque_action_exige_ao_voir(self):
        for action in ACTIONS:
            self.assertEqual(
                action.required_permission, AO_VOIR,
                "action %s : le domaine AO a un code de LECTURE réel — "
                'omettre la permission serait un mensonge par défaut.'
                % action.key)

    def test_aucune_action_n_exige_un_code_d_ecriture(self):
        for action in ACTIONS:
            self.assertNotEqual(action.required_permission, AO_GERER,
                                action.key)

    def test_aucune_action_ne_touche_la_permission_directeur(self):
        for action in ACTIONS:
            self.assertNotEqual(action.required_permission,
                                AO_RENTABILITE_VOIR, action.key)

    def test_le_catalogue_serialise_porte_la_permission(self):
        for action in ACTIONS:
            self.assertEqual(action.as_dict()['required_permission'], AO_VOIR)
