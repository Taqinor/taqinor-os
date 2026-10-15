"""XPLT18 — Tests de la proposition de règle d'automatisation par l'agent.

Couvre :
- l'action est déclarée dans le registre, risk=outward, no `required_permission`
  (ouverte à tout authentifié — la validation métier fait le reste) ;
- l'endpoint crée une AutomationRule TOUJOURS désactivée quand le brouillon
  est valide (trigger/action du catalogue fermé) ;
- un trigger_type/action_type hors catalogue est rejeté (jamais de code libre) ;
- la société est TOUJOURS imposée côté serveur (jamais lue du corps) ;
- un nom vide est rejeté.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.agent.registry import RISK_OUTWARD, all_actions

User = get_user_model()
URL = '/api/django/agent/actions/automation-draft/'


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class RegistryEntryTest(TestCase):
    def test_action_registered_outward_open(self):
        catalogue = {a.key: a for a in all_actions()}
        action = catalogue['automation.rule.propose_draft']
        self.assertEqual(action.risk, RISK_OUTWARD)
        self.assertEqual(action.method.upper(), 'POST')
        self.assertIn('nom', action.inputs.get('required', []))
        self.assertIn('trigger_type', action.inputs.get('required', []))
        self.assertIn('action_type', action.inputs.get('required', []))


class AutomationDraftEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Draft Co', slug='draft-co')
        self.other_company = Company.objects.create(
            nom='Other Co', slug='other-co')
        # ASEC43 — le brouillon exige le droit du viewset canonique des
        # automatisations (IsAdminRole : `roles_gerer`) ; le refus d'un rôle
        # sans ce droit est couvert par tests_asec43_automation_draft.
        self.role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=['crm_creer', 'roles_gerer'])
        self.user = User.objects.create_user(
            username='drafter', password='x', role=self.role,
            company=self.company)

    def test_requires_authentication(self):
        resp = APIClient().post(URL, {}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_valid_draft_creates_disabled_rule(self):
        resp = _auth(self.user).post(URL, {
            'nom': 'Relance J+2 après devis accepté',
            'trigger_type': 'devis_accepted',
            'trigger_config': {},
            'action_type': 'create_activity',
            'action_config': {'delai_jours': 2},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data['enabled'])
        self.assertEqual(resp.data['trigger_type'], 'devis_accepted')
        self.assertEqual(resp.data['action_type'], 'create_activity')

        from apps.automation.models import AutomationRule
        rule = AutomationRule.objects.get(pk=resp.data['id'])
        self.assertEqual(rule.company_id, self.company.id)
        self.assertFalse(rule.enabled)

    def test_unknown_trigger_type_rejected(self):
        resp = _auth(self.user).post(URL, {
            'nom': 'Brouillon invalide',
            'trigger_type': 'declencheur_invente_par_le_llm',
            'action_type': 'create_activity',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unknown_action_type_rejected(self):
        resp = _auth(self.user).post(URL, {
            'nom': 'Brouillon invalide',
            'trigger_type': 'devis_accepted',
            'action_type': 'action_inventee_par_le_llm',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_empty_nom_rejected(self):
        resp = _auth(self.user).post(URL, {
            'nom': '   ',
            'trigger_type': 'devis_accepted',
            'action_type': 'create_activity',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_company_forced_server_side_never_from_body(self):
        resp = _auth(self.user).post(URL, {
            'nom': 'Tentative de fuite société',
            'trigger_type': 'devis_accepted',
            'action_type': 'create_activity',
            'company': self.other_company.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        from apps.automation.models import AutomationRule
        rule = AutomationRule.objects.get(pk=resp.data['id'])
        self.assertEqual(rule.company_id, self.company.id)
        self.assertNotEqual(rule.company_id, self.other_company.id)

    def test_corps_hors_schema_rejete_400(self):
        # ERR-ENF11-FUZZ-AGENT — le corps est validé contre le schéma publié.
        base = {'nom': 'Brouillon', 'trigger_type': 'devis_accepted',
                'action_type': 'create_activity'}
        for corps in ({**base, 'action_type': '0'},
                      {**base, 'trigger_config': ['pas', 'un', 'objet']},
                      {**base, 'nom': 'x' * 256},
                      # CI #1003 (fuzz) — ``nom`` est une chaîne : ``0`` n'est
                      # plus converti en ``"0"`` (le brouillon était créé, 201).
                      {**base, 'nom': 0}, {**base, 'nom': True}):
            with self.subTest(corps=corps):
                resp = _auth(self.user).post(URL, corps, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)

    def test_schema_publie_le_catalogue_ferme(self):
        # Le schéma énumère exactement le catalogue fermé (parqués exclus) :
        # une valeur conforme au schéma n'est jamais refusée par le service.
        from apps.automation.selectors import closed_rule_catalogue
        from drf_spectacular.drainage import get_override

        from apps.agent.views import BrouillonAutomationSerializer

        catalogue = closed_rule_catalogue()
        champs = BrouillonAutomationSerializer().fields
        for nom, cle in (('trigger_type', 'trigger_types'),
                         ('action_type', 'action_types')):
            schema = get_override(champs[nom], 'field')
            self.assertEqual(schema['allOf'][0]['enum'], catalogue[cle])

    def test_octet_nul_nettoye_sans_500(self):
        # jsonb et varchar refusent l'octet NUL (500) alors que le schéma
        # l'annonce valide : il est retiré avant validation.
        resp = _auth(self.user).post(URL, {
            'nom': 'Br\x00ouillon', 'trigger_type': 'devis_accepted',
            'action_type': 'create_activity',
            'trigger_config': {'a\x00': 'b\x00c', 'liste': ['\x00x']},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['nom'], 'Brouillon')
        from apps.automation.models import AutomationRule
        regle = AutomationRule.objects.get(pk=resp.data['id'])
        self.assertEqual(regle.trigger_config, {'a': 'bc', 'liste': ['x']})
