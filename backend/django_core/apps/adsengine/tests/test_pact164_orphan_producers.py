"""PACT164 — Câblage des 6 producteurs d'actions orphelins (ADSDEEP36/50/51/52) :
``propose_internal_dayparting_pause`` / ``propose_pause_for_month`` /
``propose_edit_post`` / ``propose_create_post`` / ``propose_boost_post`` /
``propose_keyword_hides`` n'avaient AUCUN appelant hors tests. Ils sont
désormais atteignables :
  * les cinq premiers via le dispatch curé existant (PUB22)
    ``services.propose_manual_curated`` / ``POST /actions/proposer/<kind>/`` ;
  * ``propose_keyword_hides`` via un nouveau ViewSet CRUD
    ``CommentKeywordRuleViewSet`` + son action ``proposer/``.

Chaque test vérifie qu'une ``EngineAction`` PROPOSÉE (jamais appliquée) est
matérialisée par un chemin RÉEL (endpoint HTTP), pas seulement par un appel
direct de fonction.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.models import (
    AdSetMirror, CommentKeywordRule, CommentMirror, EngineAction,
    PagePostMirror,
)

User = get_user_model()


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


ALL_ALLOWED_GRID = {
    day: [1] * 24
    for day in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
}
ALL_BLOCKED_GRID = {
    day: [0] * 24
    for day in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
}


class Pact164ManualCuratedServiceTests(TestCase):
    """Niveau service : ``propose_manual_curated`` pour les 5 nouveaux kinds."""

    def setUp(self):
        self.company = Company.objects.create(nom='Pact164 Co', slug='p164')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-164', name='AdSet',
            status='ACTIVE')
        self.post = PagePostMirror.objects.create(
            company=self.company, meta_id='post-164', message='Bonjour',
            created_by_app=True)

    def test_pause_for_month_requires_target(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.propose_manual_curated(
                self.company, kind=services.KIND_PAUSE_FOR_MONTH, params={})

    def test_pause_for_month_creates_proposed_action(self):
        action = services.propose_manual_curated(
            self.company, kind=services.KIND_PAUSE_FOR_MONTH,
            params={'target_meta_id': 'camp-164', 'target_type': 'campaign'})
        self.assertEqual(action.kind, services.KIND_PAUSE_FOR_MONTH)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(action.payload['target_meta_id'], 'camp-164')

    def test_dayparting_pause_interne_requires_grid(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.propose_manual_curated(
                self.company, kind=services.KIND_DAYPARTING_PAUSE_INTERNE,
                params={'adset_id': 'as-164'})

    def test_dayparting_pause_interne_out_of_window_proposes_pause(self):
        action = services.propose_manual_curated(
            self.company, kind=services.KIND_DAYPARTING_PAUSE_INTERNE,
            params={'adset_id': 'as-164', 'grid': ALL_BLOCKED_GRID})
        self.assertEqual(action.kind, EngineAction.Kind.PAUSE)
        self.assertEqual(action.payload['target_meta_id'], 'as-164')

    def test_dayparting_pause_interne_in_window_rejected(self):
        # Grille 100 % ouverte : jamais hors fenêtre → rien à proposer.
        with self.assertRaises(services.ActionPayloadInvalid):
            services.propose_manual_curated(
                self.company, kind=services.KIND_DAYPARTING_PAUSE_INTERNE,
                params={'adset_id': 'as-164', 'grid': ALL_ALLOWED_GRID})
        self.assertEqual(EngineAction.objects.count(), 0)

    def test_dayparting_pause_interne_unknown_adset_rejected(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.propose_manual_curated(
                self.company, kind=services.KIND_DAYPARTING_PAUSE_INTERNE,
                params={'adset_id': 'inconnu', 'grid': ALL_BLOCKED_GRID})

    def test_edit_post_creates_proposed_action(self):
        action = services.propose_manual_curated(
            self.company, kind=services.KIND_EDIT_POST,
            params={'post_id': 'post-164', 'message': 'Nouveau texte'})
        self.assertEqual(action.kind, services.KIND_EDIT_POST)
        self.assertEqual(action.payload['message'], 'Nouveau texte')

    def test_edit_post_not_created_by_app_rejected(self):
        PagePostMirror.objects.create(
            company=self.company, meta_id='post-foreign',
            created_by_app=False)
        with self.assertRaises(ValueError):
            services.propose_manual_curated(
                self.company, kind=services.KIND_EDIT_POST,
                params={'post_id': 'post-foreign', 'message': 'x'})

    def test_edit_post_unknown_post_rejected(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.propose_manual_curated(
                self.company, kind=services.KIND_EDIT_POST,
                params={'post_id': 'inconnu', 'message': 'x'})

    def test_create_post_creates_proposed_action(self):
        action = services.propose_manual_curated(
            self.company, kind=services.KIND_CREATE_POST,
            params={'message': 'Nouveau post', 'mode': 'published'})
        self.assertEqual(action.kind, services.KIND_CREATE_POST)
        self.assertEqual(action.payload['message'], 'Nouveau post')

    def test_create_post_bad_mode_rejected(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.propose_manual_curated(
                self.company, kind=services.KIND_CREATE_POST,
                params={'message': 'x', 'mode': 'pas-un-mode'})

    def test_boost_post_creates_proposed_action(self):
        action = services.propose_manual_curated(
            self.company, kind=services.KIND_BOOST_POST,
            params={'post_id': 'post-164', 'adset_id': 'as-164'})
        self.assertEqual(action.kind, services.KIND_BOOST_POST)
        self.assertEqual(action.payload['post_id'], 'post-164')
        self.assertEqual(action.payload['adset_id'], 'as-164')

    def test_boost_post_unknown_adset_rejected(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.propose_manual_curated(
                self.company, kind=services.KIND_BOOST_POST,
                params={'post_id': 'post-164', 'adset_id': 'inconnu'})


class Pact164CuratedApiTests(TestCase):
    """Niveau HTTP : ``POST /actions/proposer/<kind>/`` — le chemin RÉEL
    (jamais un appel de test direct au service)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Pact164 Api Co', slug='p164a')
        self.manager = make_user(
            self.company, 'mgr164', ['adsengine_view', 'adsengine_manage'])
        self.viewer = make_user(self.company, 'viewer164', ['adsengine_view'])
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-api-164', status='ACTIVE')
        self.post = PagePostMirror.objects.create(
            company=self.company, meta_id='post-api-164', created_by_app=True)

    def _url(self, kind):
        return f'/api/django/adsengine/actions/proposer/{kind}/'

    def test_pause_for_month_requires_manage_permission(self):
        resp = auth(self.viewer).post(
            self._url('pause_for_month'),
            {'target_meta_id': 'camp-x', 'reason_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_pause_for_month_via_api(self):
        resp = auth(self.manager).post(
            self._url('pause_for_month'),
            {'target_meta_id': 'camp-api-164', 'target_type': 'campaign',
             'reason_fr': 'Franchissement imminent.'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        action = EngineAction.objects.get(pk=resp.data['id'])
        self.assertEqual(action.kind, services.KIND_PAUSE_FOR_MONTH)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_dayparting_pause_interne_via_api(self):
        resp = auth(self.manager).post(
            self._url('dayparting_pause_interne'),
            {'adset_id': 'as-api-164', 'grid': ALL_BLOCKED_GRID,
             'reason_fr': 'Hors fenêtre.'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        action = EngineAction.objects.get(pk=resp.data['id'])
        self.assertEqual(action.kind, EngineAction.Kind.PAUSE)

    def test_edit_post_via_api(self):
        resp = auth(self.manager).post(
            self._url('edit_post'),
            {'post_id': 'post-api-164', 'message': 'Texte édité',
             'reason_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        action = EngineAction.objects.get(pk=resp.data['id'])
        self.assertEqual(action.kind, services.KIND_EDIT_POST)

    def test_create_post_via_api(self):
        resp = auth(self.manager).post(
            self._url('create_post'),
            {'message': 'Nouveau post', 'reason_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        action = EngineAction.objects.get(pk=resp.data['id'])
        self.assertEqual(action.kind, services.KIND_CREATE_POST)

    def test_boost_post_via_api(self):
        resp = auth(self.manager).post(
            self._url('boost_post'),
            {'post_id': 'post-api-164', 'adset_id': 'as-api-164',
             'reason_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        action = EngineAction.objects.get(pk=resp.data['id'])
        self.assertEqual(action.kind, services.KIND_BOOST_POST)


class Pact164CommentKeywordRuleApiTests(TestCase):
    """CRUD ``regles-mot-cle/`` + action ``proposer/`` — chemin RÉEL de
    ``services.propose_keyword_hides`` (auparavant zéro appelant hors tests,
    zéro admin, zéro serializer, zéro vue)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Pact164 Kw Co', slug='p164k')
        self.other_company = Company.objects.create(
            nom='Autre société', slug='p164k-autre')
        self.manager = make_user(
            self.company, 'mgrkw', ['adsengine_view', 'adsengine_manage'])
        self.viewer = make_user(self.company, 'viewerkw', ['adsengine_view'])

    def _list_url(self):
        return '/api/django/adsengine/regles-mot-cle/'

    def test_create_rule_forces_company_server_side(self):
        resp = auth(self.manager).post(
            self._list_url(),
            {'keyword': 'spam', 'enabled': True, 'auto': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rule = CommentKeywordRule.objects.get(pk=resp.data['id'])
        self.assertEqual(rule.company_id, self.company.id)

    def test_list_is_company_scoped(self):
        CommentKeywordRule.objects.create(
            company=self.company, keyword='insulte')
        CommentKeywordRule.objects.create(
            company=self.other_company, keyword='autre-societe')
        resp = auth(self.manager).get(self._list_url())
        self.assertEqual(resp.status_code, 200)
        # La liste est PAGINEE : resp.data est un dict {count, results...},
        # pas un tableau — iterer dessus donnerait les CLES (des chaines).
        lignes = (resp.data['results'] if isinstance(resp.data, dict)
                  else resp.data)
        keywords = [r['keyword'] for r in lignes]
        self.assertIn('insulte', keywords)
        self.assertNotIn('autre-societe', keywords)

    def test_write_requires_manage_permission(self):
        resp = auth(self.viewer).post(
            self._list_url(), {'keyword': 'spam'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_proposer_creates_hide_actions_for_matching_visible_comments(self):
        CommentKeywordRule.objects.create(
            company=self.company, keyword='spam', enabled=True, auto=False)
        CommentMirror.objects.create(
            company=self.company, meta_id='c1', object_meta_id='post-1',
            message='Ceci est du SPAM évident', is_hidden=False)
        CommentMirror.objects.create(
            company=self.company, meta_id='c2', object_meta_id='post-1',
            message='Commentaire normal', is_hidden=False)
        resp = auth(self.manager).post(
            self._list_url() + 'proposer/', {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 1)
        action = EngineAction.objects.get(pk=resp.data[0]['id'])
        self.assertEqual(action.kind, 'hide_comment')
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(action.payload['comment_id'], 'c1')

    def test_proposer_requires_manage_permission(self):
        resp = auth(self.viewer).post(
            self._list_url() + 'proposer/', {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_proposer_no_match_returns_empty_list(self):
        resp = auth(self.manager).post(
            self._list_url() + 'proposer/', {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data, [])
