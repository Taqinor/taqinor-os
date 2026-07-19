"""PUB57 — Tuile Dashboard « score d'audit » auto-chargée + tendance hebdo.

Prouve : le score est TRANSPARENT (dérivé des 5 sections RÉELLES de
``run_account_audit``, jamais un chiffre inventé, jamais 'inconnu' compté) ;
le delta hebdomadaire compare au score mis en cache il y a ~7 jours (aucune
migration — cache Django, jamais persisté en base) et dégrade proprement en
``None`` sans historique ; l'endpoint ``reporting/audit/`` expose la tuile en
plus des 5 sections existantes (additif, jamais une régression).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import audit

User = get_user_model()
AUDIT_URL = '/api/django/adsengine/reporting/audit/'


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


def _audit(sections):
    return {'genere_le': '2026-07-19', 'sections': sections}


class AuditScoreUnitTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Score Co', slug='score-co')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_all_ok_gives_100(self):
        result = audit.account_audit_score(self.company, audit=_audit({
            'a': {'statut': 'ok'}, 'b': {'statut': 'ok'},
        }))
        self.assertEqual(result['score'], 100)
        self.assertEqual(result['ok_count'], 2)
        self.assertEqual(result['attention_count'], 0)
        self.assertEqual(result['total_sections'], 2)

    def test_mixed_sections_gives_transparent_percentage(self):
        result = audit.account_audit_score(self.company, audit=_audit({
            'a': {'statut': 'ok'}, 'b': {'statut': 'attention'},
            'c': {'statut': 'ok'}, 'd': {'statut': 'attention'},
        }))
        self.assertEqual(result['score'], 50)
        self.assertEqual(result['ok_count'], 2)
        self.assertEqual(result['attention_count'], 2)

    def test_inconnu_sections_never_counted(self):
        result = audit.account_audit_score(self.company, audit=_audit({
            'a': {'statut': 'ok'}, 'b': {'statut': 'inconnu'},
        }))
        # « inconnu » n'entre ni au numérateur ni au dénominateur.
        self.assertEqual(result['total_sections'], 1)
        self.assertEqual(result['score'], 100)

    def test_all_unknown_gives_no_score(self):
        result = audit.account_audit_score(self.company, audit=_audit({
            'a': {'statut': 'inconnu'},
        }))
        self.assertIsNone(result['score'])

    def test_first_run_has_no_delta(self):
        result = audit.account_audit_score(
            self.company, now=datetime.date(2026, 7, 19),
            audit=_audit({'a': {'statut': 'ok'}}))
        self.assertIsNone(result['delta_hebdo'])

    def test_weekly_delta_computed_from_cached_prior_score(self):
        # Simule le score d'il y a 7 jours déjà en cache (ex. posé par le
        # calcul de ce jour-là).
        seven_days_ago = datetime.date(2026, 7, 12)
        today = datetime.date(2026, 7, 19)
        cache.set(audit._audit_score_cache_key(self.company, seven_days_ago), 60,
                  audit.AUDIT_SCORE_CACHE_TTL)

        result = audit.account_audit_score(
            self.company, now=today, audit=_audit({
                'a': {'statut': 'ok'}, 'b': {'statut': 'ok'},
            }))  # score = 100 aujourd'hui
        self.assertEqual(result['score'], 100)
        self.assertEqual(result['delta_hebdo'], 40)  # 100 - 60

    def test_score_never_leaks_across_company(self):
        other = Company.objects.create(nom='Score Other', slug='score-other')
        seven_days_ago = datetime.date(2026, 7, 12)
        today = datetime.date(2026, 7, 19)
        cache.set(audit._audit_score_cache_key(other, seven_days_ago), 10,
                  audit.AUDIT_SCORE_CACHE_TTL)
        result = audit.account_audit_score(
            self.company, now=today, audit=_audit({'a': {'statut': 'ok'}}))
        self.assertIsNone(result['delta_hebdo'])


class AuditScoreApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Score API Co', slug='score-api-co')
        self.viewer = make_user(self.company, 'scoreviewer', ['adsengine_view'])
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_endpoint_exposes_score_tile_alongside_sections(self):
        resp = auth(self.viewer).get(AUDIT_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('sections', resp.data)
        self.assertIn('score_tile', resp.data)
        tile = resp.data['score_tile']
        for key in ('score', 'ok_count', 'attention_count', 'total_sections', 'delta_hebdo'):
            self.assertIn(key, tile)

    def test_endpoint_still_requires_permission(self):
        no_perm = make_user(self.company, 'scorenoperm', [])
        resp = auth(no_perm).get(AUDIT_URL)
        self.assertEqual(resp.status_code, 403, resp.data)
