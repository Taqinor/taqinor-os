"""ASEC12 — la connexion à l'admin Django exige la même porte que l'API.

Superuser 2FA : sans code / code faux → formulaire en erreur et compteur
d'échecs incrémenté ; bon code → accès et une ``UserSession`` tracée. Un
compte ``is_staff`` non superuser est refusé.
"""
import pyotp
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.parametres.models import CompanyProfile
from authentication.models import Company, UserSession

User = get_user_model()
_MDP = 'Admin-mdp-123!'


class AdminDjango2faTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASEC12', slug='asec12-co')
        CompanyProfile.objects.create(company=self.company,
                                      lockout_max_attempts=3)
        self.secret = pyotp.random_base32()
        self.su = User.objects.create_superuser(
            username='asec12_su', password=_MDP, email='su@asec12.ma')
        self.su.company = self.company
        self.su.totp_secret = self.secret
        self.su.totp_enabled = True
        self.su.save()
        self.staff = User.objects.create_user(
            username='asec12_staff', password=_MDP, company=self.company,
            is_staff=True)
        self.url = reverse('admin:login')
        self.index = reverse('admin:index')

    def _post(self, username, **extra):
        client = Client()
        corps = {'username': username, 'password': _MDP,
                 'next': self.index}
        corps.update(extra)
        return client, client.post(self.url, corps)

    def _relu(self, u):
        return User.objects.get(pk=u.pk)

    def test_sans_code_refuse(self):
        client, resp = self._post('asec12_su')
        self.assertEqual(resp.status_code, 200)  # formulaire réaffiché
        self.assertTrue(resp.context['form'].errors)
        self.assertEqual(client.get(self.index).status_code, 302)
        self.assertEqual(self._relu(self.su).failed_login_count, 1)

    def test_code_faux_compte(self):
        _, resp = self._post('asec12_su', otp='000000')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._relu(self.su).failed_login_count, 1)
        self._post('asec12_su', otp='000001')
        self._post('asec12_su', otp='000002')
        self.assertIsNotNone(self._relu(self.su).locked_until)

    def test_bon_code_cree_session(self):
        avant = UserSession.objects.filter(user=self.su).count()
        client, resp = self._post(
            'asec12_su', otp=pyotp.TOTP(self.secret).now())
        self.assertEqual(resp.status_code, 302, getattr(resp, 'context', None))
        self.assertEqual(client.get(self.index).status_code, 200)
        self.assertEqual(
            UserSession.objects.filter(user=self.su).count(), avant + 1)
        self.assertEqual(self._relu(self.su).failed_login_count, 0)

    def test_staff_non_superuser_refuse(self):
        client, resp = self._post('asec12_staff')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['form'].errors)
        # Même avec une session ouverte autrement, le site admin reste fermé.
        client.force_login(self.staff)
        self.assertNotEqual(client.get(self.index).status_code, 200)
