"""NTADM8 — gestion des licences/sièges : sieges_utilises(), statut d'usage
(endpoint), alerte de franchissement (jamais bloquant)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from authentication.services import sieges_utilises

User = get_user_model()


def _company(nom='NTADM8Co'):
    return Company.objects.create(nom=nom)


def _admin(company, username='admin'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy='admin', is_staff=True)


class SiegesUtilisesTests(TestCase):
    def test_compte_seulement_les_actifs(self):
        company = _company()
        _admin(company, 'u1')
        inactif = User.objects.create_user(
            username='u2', password='pw', company=company, role_legacy='normal')
        inactif.is_active = False
        inactif.save(update_fields=['is_active'])
        self.assertEqual(sieges_utilises(company), 1)

    def test_sans_company(self):
        self.assertEqual(sieges_utilises(None), 0)

    def test_isolation_par_societe(self):
        c1, c2 = _company('A57281'), _company('B60492')
        _admin(c1, 'admin-a')
        _admin(c2, 'admin-b')
        self.assertEqual(sieges_utilises(c1), 1)
        self.assertEqual(sieges_utilises(c2), 1)


class LicenceStatutEndpointTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.admin)

    def test_illimite_par_defaut(self):
        resp = self.client_api.get('/api/django/adminops/licences/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['sieges_max'])
        self.assertFalse(resp.data['quota_atteint'])
        self.assertIsNone(resp.data['plan'])

    def test_quota_atteint(self):
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=self.company)
        profile.nb_sieges_max = 1
        profile.save(update_fields=['nb_sieges_max'])
        resp = self.client_api.get('/api/django/adminops/licences/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['sieges_utilises'], 1)
        self.assertEqual(resp.data['sieges_max'], 1)
        self.assertTrue(resp.data['quota_atteint'])


class QuotaAlertReceiverTests(TestCase):
    """NTADM8 — franchissement du quota : notifie, mais NE BLOQUE JAMAIS la
    création d'un compte au-delà du quota."""

    def test_franchissement_notifie_sans_bloquer(self):
        from apps.parametres.models import CompanyProfile
        from apps.notifications.models import Notification

        company = _company()
        admin = _admin(company)
        profile = CompanyProfile.get(company=company)
        profile.nb_sieges_max = 1
        profile.save(update_fields=['nb_sieges_max'])

        # Le premier compte actif (admin) atteint déjà le quota (1/1) : un
        # DEUXIÈME compte actif ci-dessous dépasse le quota — et doit malgré
        # tout être créé avec succès (jamais de blocage).
        second = User.objects.create_user(
            username='depasse', password='pw', company=company,
            role_legacy='normal')
        self.assertTrue(User.objects.filter(pk=second.pk).exists())
        self.assertEqual(sieges_utilises(company), 2)

        notifs = Notification.objects.filter(
            company=company, recipient=admin, title='Quota de sièges atteint')
        self.assertTrue(notifs.exists())

    def test_sans_quota_configure_aucune_alerte(self):
        from apps.notifications.models import Notification

        company = _company()
        admin = _admin(company)
        User.objects.create_user(
            username='u2', password='pw', company=company, role_legacy='normal')
        self.assertFalse(
            Notification.objects.filter(
                company=company, recipient=admin,
                title='Quota de sièges atteint').exists())
