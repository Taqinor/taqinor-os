"""ASEC4 — ``/api/django/token/`` compte chaque échec et arme le verrou.

Les tests passent par l'URL RÉELLE (jamais par ``register_failed_login``
direct) : mauvais mot de passe, code OTP faux, seuil société, plancher
plateforme quand la société n'a pas armé de seuil, remise à zéro au succès.

ASEC4-revue (décision fondateur « verrou par compte+IP ») : le plancher
plateforme verrouille le couple (compte, IP) — l'IP attaquante est bloquée,
le titulaire depuis une autre IP ne l'est pas ; le superuser suit la même
règle. Le throttle IP (5/min, couvert ailleurs) est neutralisé par patch, et
non plus par ``cache.clear()`` qui effacerait aussi les compteurs du plancher.
"""
from unittest import mock

import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.parametres.models import CompanyProfile
from authentication.models import Company
from authentication.throttles import LoginRateThrottle

User = get_user_model()

_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}
_URL = '/api/django/token/'
_BON = 'Bon-mdp-123!'


def _corps(resp):
    """Corps de la réponse sans ``error.request_id`` — identifiant de
    corrélation unique PAR requête (ACAL315 : jamais null, uuid4 sinon) ;
    tout le reste doit être identique."""
    corps = dict(resp.data)
    if isinstance(corps.get('error'), dict):
        corps['error'] = {
            k: v for k, v in corps['error'].items() if k != 'request_id'}
    return corps


@override_settings(CACHES=_LOCMEM_CACHE)
class VerrouLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch.object(
            LoginRateThrottle, 'allow_request', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.co3 = Company.objects.create(nom='ASEC4 seuil 3', slug='asec4-3')
        CompanyProfile.objects.create(
            company=self.co3, lockout_max_attempts=3,
            lockout_duration_minutes=15)
        self.co0 = Company.objects.create(nom='ASEC4 seuil 0', slug='asec4-0')
        CompanyProfile.objects.create(company=self.co0, lockout_max_attempts=0)
        self.u3 = User.objects.create_user(
            username='asec4_u3', password=_BON, company=self.co3)
        self.u0 = User.objects.create_user(
            username='asec4_u0', password=_BON, company=self.co0)
        self.api = APIClient()

    def _post(self, ip='10.0.0.1', **corps):
        return self.api.post(_URL, corps, format='json', REMOTE_ADDR=ip)

    def _relu(self, u):
        return User.objects.get(pk=u.pk)

    def test_mauvais_mdp_compte_via_endpoint(self):
        r = self._post(username='asec4_u3', password='faux')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self._relu(self.u3).failed_login_count, 1)
        # Identifiant inconnu : même statut, même corps.
        r2 = self._post(username='asec4_inconnu', password='faux')
        self.assertEqual(r2.status_code, 401)
        self.assertEqual(_corps(r), _corps(r2))

    def test_seuil_societe_verrouille(self):
        for _ in range(3):
            self.assertEqual(
                self._post(username='asec4_u3', password='faux').status_code,
                401)
        u = self._relu(self.u3)
        self.assertIsNotNone(u.locked_until)
        # Verrouillé : même le bon mot de passe est refusé — ASEC14-revue :
        # EXACTEMENT le 401 d'un mauvais mot de passe.
        faux = self._post(username='asec4_inconnu', password='faux')
        r = self._post(username='asec4_u3', password=_BON)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(_corps(r), _corps(faux))

    def test_otp_faux_compte(self):
        self.u3.totp_secret = pyotp.random_base32()
        self.u3.totp_enabled = True
        self.u3.save()
        for _ in range(3):
            r = self._post(username='asec4_u3', password=_BON, otp='000000')
            self.assertEqual(r.status_code, 401)
        self.assertIsNotNone(self._relu(self.u3).locked_until)

    def test_plancher_plateforme_societe_a_zero(self):
        for _ in range(10):
            self._post(username='asec4_u0', password='faux')
        # Verrou du couple (compte, IP) — jamais du compte entier.
        self.assertIsNone(self._relu(self.u0).locked_until)
        r = self._post(username='asec4_u0', password=_BON)
        self.assertNotEqual(r.status_code, 200)

    def test_plancher_ip_attaquante_verrouillee_titulaire_autre_ip_ok(self):
        for _ in range(10):
            self._post(ip='203.0.113.9', username='asec4_u0', password='faux')
        # L'IP attaquante est verrouillée, même avec le bon mot de passe —
        # même 401 qu'un mauvais mot de passe (ASEC14-revue).
        faux = self._post(ip='203.0.113.9', username='asec4_x', password='y')
        r = self._post(ip='203.0.113.9', username='asec4_u0', password=_BON)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(_corps(r), _corps(faux))
        # Le titulaire, depuis une autre IP, se connecte normalement.
        r2 = self._post(ip='198.51.100.7', username='asec4_u0', password=_BON)
        self.assertEqual(r2.status_code, 200, r2.data)

    def test_plancher_neuf_echecs_ne_verrouille_pas(self):
        for _ in range(9):
            self._post(ip='203.0.113.10', username='asec4_u0', password='faux')
        r = self._post(ip='203.0.113.10', username='asec4_u0', password=_BON)
        self.assertEqual(r.status_code, 200, r.data)

    def test_plancher_echecs_repartis_sur_deux_ip_ne_verrouillent_pas(self):
        # Le compteur est PAR IP : 5 + 5 depuis deux IP ≠ 10 consécutifs.
        for _ in range(5):
            self._post(ip='203.0.113.11', username='asec4_u0', password='faux')
            self._post(ip='203.0.113.12', username='asec4_u0', password='faux')
        r = self._post(ip='203.0.113.11', username='asec4_u0', password=_BON)
        self.assertEqual(r.status_code, 200, r.data)

    def test_plancher_superuser_meme_regle(self):
        su = User.objects.create_superuser(
            username='asec4_su', password=_BON, email='su@asec4.ma')
        for _ in range(10):
            self._post(ip='203.0.113.20', username='asec4_su', password='faux')
        r = self._post(ip='203.0.113.20', username='asec4_su', password=_BON)
        self.assertNotEqual(r.status_code, 200)
        r2 = self._post(ip='198.51.100.20', username='asec4_su', password=_BON)
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertIsNone(self._relu(su).locked_until)

    def test_seuil_societe_garde_sa_semantique_compte_entier(self):
        # Verrou SOCIÉTÉ (opt-in) : sur le COMPTE, toutes IP confondues.
        for _ in range(3):
            self._post(ip='203.0.113.30', username='asec4_u3', password='faux')
        self.assertIsNotNone(self._relu(self.u3).locked_until)
        r = self._post(ip='198.51.100.30', username='asec4_u3', password=_BON)
        self.assertNotEqual(r.status_code, 200)

    def test_succes_remet_a_zero(self):
        self._post(username='asec4_u0', password='faux')
        self._post(username='asec4_u0', password='faux')
        self.assertEqual(self._relu(self.u0).failed_login_count, 2)
        r = self._post(username='asec4_u0', password=_BON)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._relu(self.u0).failed_login_count, 0)
