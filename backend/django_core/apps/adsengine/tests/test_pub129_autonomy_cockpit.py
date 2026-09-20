"""PUB129 — Cockpit d'autonomie : les 8 portes + cérémonie d'activation.

``preflight.status`` agrégeait les 8 portes go-live mais AUCUNE route ne les
exposait avec de quoi les réparer, et ``preflight.activate`` /
``acknowledge_simulation`` n'avaient aucun point d'entrée HTTP : l'autonomie
était invisible ET inactivable depuis la console.

Prouve :
  * ``GET plans-vol/autonomie/`` rend les 8 portes de ``preflight.status`` — les
    MÊMES, dans le même ordre — chacune avec sa remédiation FR (écran, commande
    serveur ou acquittement en place) et l'état RÉEL de l'autonomie ;
  * ``POST autonomie/activer/`` refuse tant qu'UNE porte est rouge et renvoie le
    message d'``AutonomyNotReady`` TEL QUEL, sans poser le drapeau ;
  * toutes les portes vertes ⇒ activation réelle + journal ``AuditLog`` ;
  * ``POST autonomie/desactiver/`` coupe TOUJOURS, sans exiger aucune porte
    (sécurité), et reste idempotent ;
  * ``POST autonomie/acquitter-simulation/`` ouvre la porte ``simulation``
    (remédiation en place) et est journalisé ;
  * RBAC : basculer l'autonomie exige ``adsengine_autonomy_toggle`` (admin-seul,
    ADSENG47) — ``adsengine_view`` seul lit le cockpit mais ne bascule rien.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import preflight
from apps.adsengine.models import (
    CreativeAsset, CreativeBacklogItem, FlightPlan, GuardrailConfig,
    MetaConnection, RulePolicy,
)

User = get_user_model()
BASE = '/api/django/adsengine/plans-vol/'
COCKPIT = BASE + 'autonomie/'
ACTIVER = BASE + 'autonomie/activer/'
DESACTIVER = BASE + 'autonomie/desactiver/'
ACQUITTER = BASE + 'autonomie/acquitter-simulation/'

TODAY = datetime.date(2026, 9, 20)


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


class AutonomyCockpitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Cockpit Co', slug='cockpit-co')
        self.admin = make_user(self.company, 'admin', [
            'adsengine_view', 'adsengine_manage', 'adsengine_autonomy_toggle'])
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def tearDown(self):
        cache.clear()

    # ── Helpers : rendre les portes vertes (mêmes fixtures qu'ADSENG38) ──────
    def _all_green(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'})
        GuardrailConfig.objects.create(company=self.company)
        RulePolicy.objects.create(
            company=self.company, template_key='zero_results', enabled=True)
        for i in range(12):
            asset = CreativeAsset.objects.create(
                company=self.company,
                asset_type=CreativeAsset.AssetType.STATIC,
                hook_id=f'H{i % 4}', policy_stamp={'passed': True})
            CreativeBacklogItem.objects.create(
                company=self.company, asset=asset,
                status=CreativeBacklogItem.Statut.EN_FILE)
        FlightPlan.objects.create(
            company=self.company, name='Plan', start_date=TODAY,
            status=FlightPlan.Statut.ACTIF)
        preflight.acknowledge_simulation(self.company)

    def _audit_details(self):
        from apps.audit.models import AuditLog
        return [row.detail for row in AuditLog.objects.filter(
            company=self.company)]

    # ── Lecture du cockpit ──────────────────────────────────────────────────
    def test_cockpit_shows_the_same_gates_as_preflight_with_remediation(self):
        resp = auth(self.viewer).get(COCKPIT)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        attendues = [g['key'] for g in preflight.status(self.company)['gates']]
        self.assertEqual([p['key'] for p in data['portes']], attendues)
        self.assertEqual(len(data['portes']), 8)
        self.assertFalse(data['pret'])
        self.assertFalse(data['actif'])
        self.assertTrue(data['manquantes'])
        # Chaque porte connue porte une remédiation FR non vide.
        for porte in data['portes']:
            self.assertTrue(porte['remediation'].get('texte'), porte['key'])
            self.assertTrue(porte['remediation'].get('route'), porte['key'])
        par_cle = {p['key']: p for p in data['portes']}
        self.assertEqual(par_cle['field_tests']['remediation']['route'],
                         '/publicite/tests-terrain')
        self.assertEqual(par_cle['simulation']['remediation']['action'],
                         'acquitter_simulation')
        self.assertIn('seed_adsengine',
                      par_cle['alerts']['remediation']['commande'])
        # Le détail FR de la porte vient de preflight, jamais reformulé ici.
        self.assertIn('Backlog insuffisant',
                      par_cle['backlog_volume']['detail'])

    def test_cockpit_reflects_the_real_autonomy_flag(self):
        with mock.patch.object(preflight.field_tests, 'pending_keys',
                               return_value=[]):
            self._all_green()
            preflight.activate(self.company)
            data = auth(self.viewer).get(COCKPIT).data
        self.assertTrue(data['actif'])
        self.assertTrue(data['pret'])
        self.assertEqual(data['manquantes'], [])

    # ── Activation : refus TEL QUEL tant qu'une porte est rouge ──────────────
    def test_activation_refused_with_the_untouched_refusal_message(self):
        resp = auth(self.admin).post(ACTIVER)
        self.assertEqual(resp.status_code, 400, resp.data)
        # Le message est EXACTEMENT celui d'AutonomyNotReady.
        expected = str(preflight.AutonomyNotReady(
            preflight.status(self.company)['missing_fr']))
        self.assertEqual(resp.data['detail'], expected)
        self.assertTrue(resp.data['detail'].startswith(
            'Autonomie non activable :'))
        # Le drapeau n'est PAS posé, et le cockpit accompagne le refus.
        self.assertFalse(preflight.is_active(self.company))
        self.assertFalse(resp.data['actif'])
        self.assertEqual(len(resp.data['portes']), 8)
        # Un refus ne journalise AUCUNE bascule d'autonomie (rien n'a bougé).
        self.assertFalse([d for d in self._audit_details()
                          if 'utonomie' in d])

    def test_activation_when_all_green_activates_and_is_journaled(self):
        with mock.patch.object(preflight.field_tests, 'pending_keys',
                               return_value=[]):
            self._all_green()
            resp = auth(self.admin).post(ACTIVER)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['actif'])
        self.assertTrue(preflight.is_active(self.company))
        self.assertIn('ACTIVÉE', resp.data['detail'])
        self.assertTrue(any('ACTIVÉE' in d for d in self._audit_details()),
                        self._audit_details())

    # ── Désactivation : toujours libre, aucune porte requise ─────────────────
    def test_deactivation_never_requires_a_single_green_gate(self):
        # Autonomie posée par le chemin bas-niveau, puis TOUTES les portes sont
        # rouges (aucune fixture) : la coupure doit passer quand même.
        from apps.adsengine import flightrunner
        flightrunner.set_autonomy_active(self.company, True)
        self.assertTrue(preflight.is_active(self.company))

        resp = auth(self.admin).post(DESACTIVER)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['actif'])
        self.assertFalse(resp.data['pret'])  # portes rouges : sans effet
        self.assertFalse(preflight.is_active(self.company))
        self.assertTrue(any('DÉSACTIVÉE' in d for d in self._audit_details()),
                        self._audit_details())

    def test_deactivation_is_idempotent_and_never_an_error(self):
        resp = auth(self.admin).post(DESACTIVER)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['actif'])
        resp2 = auth(self.admin).post(DESACTIVER)
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertFalse(resp2.data['actif'])

    # ── Remédiation EN PLACE : acquitter la simulation ───────────────────────
    def test_simulation_gate_opens_through_its_own_endpoint(self):
        GuardrailConfig.objects.create(company=self.company)
        before = {p['key']: p['ok']
                  for p in auth(self.viewer).get(COCKPIT).data['portes']}
        self.assertFalse(before['simulation'])

        resp = auth(self.admin).post(ACQUITTER)
        self.assertEqual(resp.status_code, 200, resp.data)
        par_cle = {p['key']: p['ok'] for p in resp.data['portes']}
        self.assertTrue(par_cle['simulation'])
        self.assertTrue(preflight.simulation_acknowledged(self.company))
        self.assertTrue(any('acquitt' in d.lower()
                            for d in self._audit_details()),
                        self._audit_details())

    # ── RBAC (ADSENG47) ─────────────────────────────────────────────────────
    def test_toggle_requires_the_autonomy_permission(self):
        for url in (ACTIVER, DESACTIVER):
            resp = auth(self.viewer).post(url)
            self.assertEqual(resp.status_code, 403, (url, resp.status_code))
        self.assertFalse(preflight.is_active(self.company))

    def test_reading_the_cockpit_only_needs_adsengine_view(self):
        resp = auth(self.viewer).get(COCKPIT)
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_is_rejected_everywhere(self):
        api = APIClient()
        for url in (COCKPIT, ACTIVER, DESACTIVER, ACQUITTER):
            resp = api.get(url) if url == COCKPIT else api.post(url)
            self.assertIn(resp.status_code, (401, 403), url)
