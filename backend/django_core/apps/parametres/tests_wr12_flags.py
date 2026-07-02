"""WR12 — exposition des flags backend-only en Paramètres.

Les quatre flags — commission (N99), parrainage (N98), SLA premier contact
(FG28), interrupteur maître DGI (N105) — sont désormais réglables via
l'endpoint du profil entreprise (``/api/django/parametres/update/``). On
vérifie :
  * la PERSISTANCE des quatre valeurs par un directeur/admin ;
  * le GATE d'écriture : un utilisateur du palier limité (normal) ne peut pas
    modifier le profil (403), donc ne peut pas toucher ces flags.
Les champs sont exposés par ``CompanyProfileSerializer`` (fields='__all__').
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()

UPDATE_URL = '/api/django/parametres/update/'


class WR12FlagsBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='wr12-co', defaults={'nom': 'WR12 Co'})[0]
        self.admin = User.objects.create_user(
            username='wr12_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='wr12_normal', password='x', role_legacy='normal',
            company=self.company)

    def _client(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api


class TestFlagsPersistence(WR12FlagsBase):
    def test_admin_can_set_all_four_flags(self):
        api = self._client(self.admin)
        resp = api.patch(UPDATE_URL, {
            'commission_mode': 'pct_devis',   # N99
            'commission_valeur': '5',
            'referral_enabled': True,         # N98
            'referral_reward': '750',
            'lead_sla_hours': 48,             # FG28
            'dgi_export_actif': True,         # N105
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['commission_mode'], 'pct_devis')
        self.assertEqual(str(resp.data['commission_valeur']), '5.00')
        self.assertTrue(resp.data['referral_enabled'])
        self.assertEqual(str(resp.data['referral_reward']), '750.00')
        self.assertEqual(resp.data['lead_sla_hours'], 48)
        self.assertTrue(resp.data['dgi_export_actif'])

    def test_flags_persist_in_db(self):
        api = self._client(self.admin)
        api.patch(UPDATE_URL, {
            'lead_sla_hours': 0,               # 0 = SLA désactivé
            'dgi_export_actif': True,
            'referral_enabled': True,
            'referral_reward': '100',
        }, format='json')
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.get(company=self.company)
        self.assertEqual(profile.lead_sla_hours, 0)
        self.assertTrue(profile.dgi_export_actif)
        self.assertTrue(profile.referral_enabled)

    def test_dgi_toggle_arms_capability(self):
        # N105 — l'interrupteur maître lu par la capacité DGI suit le flag.
        from apps.ventes.dgi.toggle import is_dgi_enabled
        self.assertFalse(is_dgi_enabled(self.company))
        api = self._client(self.admin)
        api.patch(UPDATE_URL, {'dgi_export_actif': True}, format='json')
        self.assertTrue(is_dgi_enabled(self.company))


class TestFlagsGate(WR12FlagsBase):
    def test_normal_user_cannot_update_profile_flags(self):
        # Palier limité : l'endpoint du profil est refusé (403) → aucun des
        # quatre flags ne peut être modifié par un rôle non autorisé.
        api = self._client(self.normal)
        resp = api.patch(UPDATE_URL, {
            'commission_mode': 'pct_devis', 'commission_valeur': '5',
            'lead_sla_hours': 1, 'dgi_export_actif': True,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_normal_user_change_does_not_persist(self):
        api = self._client(self.normal)
        api.patch(UPDATE_URL, {'dgi_export_actif': True}, format='json')
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=self.company).first()
        # Soit aucun profil créé, soit le flag reste au défaut (False).
        self.assertFalse(bool(profile and profile.dgi_export_actif))
