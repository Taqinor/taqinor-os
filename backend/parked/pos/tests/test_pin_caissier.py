"""NTRET3 — Multi-caissiers avec PIN de session (verrouillage rapide).

Couvre : PIN correct déverrouille (renvoie l'utilisateur), PIN erroné refusé,
throttle applicatif (5 tentatives/5 min), changement de caissier journalisé
via apps.audit quand l'utilisateur déverrouillé diffère du précédent,
isolation multi-tenant (un PIN d'une société ne déverrouille jamais un
user_id d'une autre société).
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.pos import services
from apps.pos.models import CodePinCaissier

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PinCaissierServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret3', 'NTRET3 Co')
        self.caissier1 = make_user(self.co, 'caissier1-ntret3')
        self.caissier2 = make_user(self.co, 'caissier2-ntret3')

    def test_definir_pin_requires_4_to_6_digits(self):
        with self.assertRaises(services.PinCaissierError):
            services.definir_pin(
                company=self.co, user=self.caissier1, raw_pin='12')
        with self.assertRaises(services.PinCaissierError):
            services.definir_pin(
                company=self.co, user=self.caissier1, raw_pin='abcd')
        services.definir_pin(
            company=self.co, user=self.caissier1, raw_pin='1234')
        self.assertTrue(
            CodePinCaissier.objects.filter(
                company=self.co, user=self.caissier1).exists())

    def test_pin_never_stored_plaintext(self):
        services.definir_pin(
            company=self.co, user=self.caissier1, raw_pin='4321')
        code = CodePinCaissier.objects.get(company=self.co, user=self.caissier1)
        self.assertNotEqual(code.pin_hash, '4321')
        self.assertNotIn('4321', code.pin_hash)

    def test_verifier_pin_correct_unlocks(self):
        services.definir_pin(
            company=self.co, user=self.caissier1, raw_pin='1111')
        user = services.verifier_pin(
            company=self.co, user_id=self.caissier1.id, raw_pin='1111')
        self.assertEqual(user.id, self.caissier1.id)

    def test_verifier_pin_wrong_refused(self):
        services.definir_pin(
            company=self.co, user=self.caissier1, raw_pin='1111')
        with self.assertRaises(services.PinCaissierError):
            services.verifier_pin(
                company=self.co, user_id=self.caissier1.id, raw_pin='0000')

    def test_verifier_pin_unknown_user_refused(self):
        with self.assertRaises(services.PinCaissierError):
            services.verifier_pin(
                company=self.co, user_id=self.caissier1.id, raw_pin='1111')

    def test_changement_caissier_journalise(self):
        services.definir_pin(
            company=self.co, user=self.caissier2, raw_pin='2222')
        services.verifier_pin(
            company=self.co, user_id=self.caissier2.id, raw_pin='2222',
            caissier_precedent=self.caissier1.id,
            acting_user=self.caissier1,
        )
        from apps.audit.models import AuditLog
        self.assertTrue(
            AuditLog.objects.filter(company=self.co, action='update')
            .filter(detail__icontains='Changement de caissier').exists())

    def test_same_caissier_reverrouillage_not_journalise_as_change(self):
        services.definir_pin(
            company=self.co, user=self.caissier1, raw_pin='3333')
        from apps.audit.models import AuditLog
        before = AuditLog.objects.filter(
            detail__icontains='Changement de caissier').count()
        services.verifier_pin(
            company=self.co, user_id=self.caissier1.id, raw_pin='3333',
            caissier_precedent=self.caissier1.id,
        )
        after = AuditLog.objects.filter(
            detail__icontains='Changement de caissier').count()
        self.assertEqual(before, after)


class PinCaissierApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.co_a = make_company('ntret3-a', 'A')
        self.co_b = make_company('ntret3-b', 'B')
        self.user_a = make_user(self.co_a, 'ntret3-a-user')
        self.user_b = make_user(self.co_b, 'ntret3-b-user')

    def tearDown(self):
        cache.clear()

    def test_definir_puis_verifier_pin_via_api(self):
        api = auth(self.user_a)
        define_resp = api.post(
            '/api/django/pos/definir-pin/', {'pin': '5678'}, format='json')
        self.assertEqual(define_resp.status_code, 200, define_resp.data)

        verify_resp = api.post(
            '/api/django/pos/verifier-pin/',
            {'user_id': self.user_a.id, 'pin': '5678'}, format='json')
        self.assertEqual(verify_resp.status_code, 200, verify_resp.data)
        self.assertEqual(verify_resp.data['id'], self.user_a.id)

    def test_wrong_pin_refused_via_api(self):
        api = auth(self.user_a)
        api.post('/api/django/pos/definir-pin/', {'pin': '5678'}, format='json')
        resp = api.post(
            '/api/django/pos/verifier-pin/',
            {'user_id': self.user_a.id, 'pin': '0000'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_pin_isolated_per_company(self):
        """Le PIN d'un utilisateur de la société A ne peut jamais être
        vérifié en se faisant passer pour un user_id de la société B."""
        api_a = auth(self.user_a)
        api_a.post('/api/django/pos/definir-pin/', {'pin': '1234'}, format='json')

        api_b = auth(self.user_b)
        resp = api_b.post(
            '/api/django/pos/verifier-pin/',
            {'user_id': self.user_a.id, 'pin': '1234'}, format='json')
        # user_id appartient à la société A : la société B ne trouve aucun
        # CodePinCaissier scopé chez elle pour cet id → refusé.
        self.assertEqual(resp.status_code, 400)

    def test_throttled_after_5_wrong_attempts(self):
        api = auth(self.user_a)
        api.post('/api/django/pos/definir-pin/', {'pin': '9999'}, format='json')
        for _ in range(5):
            resp = api.post(
                '/api/django/pos/verifier-pin/',
                {'user_id': self.user_a.id, 'pin': '0000'}, format='json')
            self.assertEqual(resp.status_code, 400)
        throttled = api.post(
            '/api/django/pos/verifier-pin/',
            {'user_id': self.user_a.id, 'pin': '9999'}, format='json')
        self.assertEqual(throttled.status_code, 429)
