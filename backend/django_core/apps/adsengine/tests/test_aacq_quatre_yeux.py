"""AACQ14 — Quatre yeux sur TOUS les chemins de proposition humaine.

Chaque proposition humaine (proposition curée, commentaire, Instagram,
annulation) naît avec ``proposed_by`` = l'appelant ; quatre-yeux actif, il ne
peut pas l'approuver lui-même (403), un autre approbateur le peut ; une
proposition machine reste approuvable. ``require_four_eyes`` est réglable sur
``garde-fous/`` par le seul porteur d'``adsengine_autonomy_toggle``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.models import CommentMirror, EngineAction, GuardrailConfig

User = get_user_model()
BASE = '/api/django/adsengine'
APPROVE = ['adsengine_view', 'adsengine_manage', 'adsengine_approve']


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


class QuatreYeuxTousCheminsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='4Y', slug='aacq14-4y')
        self.admin = make_user(
            self.company, 'aacq14-admin',
            APPROVE + ['adsengine_autonomy_toggle'])
        self.autre = make_user(self.company, 'aacq14-autre', APPROVE)
        self.cfg = GuardrailConfig.objects.create(
            company=self.company, require_four_eyes=True)
        self.comment = CommentMirror.objects.create(
            company=self.company, meta_id='c-aacq14', message='Bonjour',
            created_time=timezone.now())

    def _chemins(self):
        api = auth(self.admin)
        applied = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.RENAME,
            reason_fr='Renommer.', status=EngineAction.Statut.APPLIQUEE,
            payload={'object_id': '1209', 'name': 'Nouveau',
                     'previous_name': 'Ancien'})
        return [
            ('proposer/pause_for_month', lambda: api.post(
                f'{BASE}/actions/proposer/pause_for_month/',
                {'target_meta_id': 'cmp-1'}, format='json')),
            ('commentaire/repondre', lambda: api.post(
                f'{BASE}/commentaires/{self.comment.pk}/repondre/',
                {'message': 'Merci !'}, format='json')),
            ('instagram/publier', lambda: api.post(
                f'{BASE}/instagram/publier/',
                {'media_type': 'IMAGE',
                 'image_url': 'https://example.test/i.jpg'}, format='json')),
            ('actions/annuler', lambda: api.post(
                f'{BASE}/actions/{applied.pk}/annuler/', {}, format='json')),
        ]

    def test_chaque_chemin_porte_le_proposeur_et_refuse_l_auto_approbation(self):
        for nom, appel in self._chemins():
            with self.subTest(chemin=nom):
                resp = appel()
                self.assertIn(resp.status_code, (200, 201), resp.data)
                action_id = (resp.data.get('id')
                             or (resp.data.get('inverse') or {}).get('id'))
                self.assertIsNotNone(action_id, resp.data)
                action = EngineAction.objects.get(pk=action_id)
                self.assertEqual(action.proposed_by_id, self.admin.pk)
                refus = auth(self.admin).post(
                    f'{BASE}/actions/{action.pk}/approve/')
                self.assertEqual(refus.status_code, 403, refus.data)
                action.refresh_from_db()
                self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
                ok = auth(self.autre).post(
                    f'{BASE}/actions/{action.pk}/approve/')
                self.assertEqual(ok.status_code, 200, ok.data)

    def test_proposition_machine_reste_approuvable(self):
        action = services.propose_pause_for_month(
            self.company, target_meta_id='cmp-2')
        self.assertIsNone(action.proposed_by_id)
        resp = auth(self.admin).post(f'{BASE}/actions/{action.pk}/approve/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_service_relaie_le_proposeur(self):
        action = services.propose_manual_curated(
            self.company, kind='pause_for_month',
            params={'target_meta_id': 'cmp-3'}, proposed_by=self.admin)
        self.assertEqual(action.proposed_by_id, self.admin.pk)
        # Hors du bloc, le contexte est rendu : une proposition suivante est
        # de nouveau machine.
        machine = services.propose_pause_for_month(
            self.company, target_meta_id='cmp-4')
        self.assertIsNone(machine.proposed_by_id)

    def test_require_four_eyes_reglable_par_autonomy_toggle_seul(self):
        url = f'{BASE}/garde-fous/{self.cfg.pk}/'
        resp = auth(self.autre).patch(
            url, {'require_four_eyes': False}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.cfg.refresh_from_db()
        self.assertTrue(self.cfg.require_four_eyes)
        resp = auth(self.admin).patch(
            url, {'require_four_eyes': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cfg.refresh_from_db()
        self.assertFalse(self.cfg.require_four_eyes)
