"""NTADM41 — webhook sortant `sieges.quota_atteint`, déclenché par le même
récepteur que l'alerte NTADM8 (franchissement du quota de sièges)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

User = get_user_model()


def _company(nom='NTADM41SiegesCo'):
    return Company.objects.create(nom=nom)


def _admin(company, username='admin'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy='admin', is_staff=True)


class SiegesQuotaWebhookTests(TestCase):
    def test_franchissement_declenche_le_webhook(self):
        from apps.parametres.models import CompanyProfile

        company = _company()
        _admin(company)
        profile = CompanyProfile.get(company=company)
        profile.nb_sieges_max = 1
        profile.save(update_fields=['nb_sieges_max'])

        with mock.patch('apps.publicapi.delivery.dispatch_event') as dispatch:
            # Deuxième compte actif : dépasse le quota (1/1) -> déclenche.
            User.objects.create_user(
                username='depasse', password='pw', company=company,
                role_legacy='normal')

        self.assertTrue(dispatch.called)
        args, _kwargs = dispatch.call_args
        self.assertEqual(args[0], company.id)
        self.assertEqual(args[1], 'sieges.quota_atteint')
        self.assertEqual(args[2]['sieges_max'], 1)
        self.assertEqual(args[2]['sieges_utilises'], 2)
        # JAMAIS de donnée client dans le payload.
        self.assertNotIn('username', args[2])
        self.assertNotIn('email', args[2])

    def test_sous_le_quota_aucun_webhook(self):
        from apps.parametres.models import CompanyProfile

        company = _company('NTADM41SiegesCo2')
        _admin(company)
        profile = CompanyProfile.get(company=company)
        profile.nb_sieges_max = 5
        profile.save(update_fields=['nb_sieges_max'])

        with mock.patch('apps.publicapi.delivery.dispatch_event') as dispatch:
            User.objects.create_user(
                username='sous-quota', password='pw', company=company,
                role_legacy='normal')
        self.assertFalse(dispatch.called)
