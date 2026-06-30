"""Tests FG392 — thème white-label par société (singleton).

Couvre :
  * GET courant sans thème → défauts vides (jamais 404) ;
  * PUT courant crée le thème (company imposée), re-PUT met à jour (pas de
    doublon — OneToOne) ;
  * écriture réservée admin/responsable ; lecture ouverte ;
  * isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core.models import TenantTheme
from core.views import TenantThemeViewSet

User = get_user_model()


class TenantThemeViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.admin = User.objects.create_user(
            username='th_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='th_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def _get(self, user):
        req = self.factory.get('/theme/courant/')
        force_authenticate(req, user=user)
        return TenantThemeViewSet.as_view({'get': 'courant'})(req)

    def _put(self, user, body):
        req = self.factory.put('/theme/courant/', body, format='json')
        force_authenticate(req, user=user)
        return TenantThemeViewSet.as_view({'put': 'courant'})(req)

    def test_get_without_theme_returns_defaults(self):
        resp = self._get(self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['couleur_primaire'], '')

    def test_put_requires_admin_tier(self):
        resp = self._put(self.user, {'couleur_primaire': '#fff'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_creates_then_updates_singleton(self):
        resp = self._put(self.admin, {'couleur_primaire': '#111111'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(TenantTheme.objects.filter(company=self.company).count(), 1)
        theme = TenantTheme.objects.get(company=self.company)
        self.assertEqual(theme.couleur_primaire, '#111111')
        # re-PUT met à jour la même ligne (pas de doublon).
        self._put(self.admin, {'couleur_primaire': '#222222'})
        self.assertEqual(TenantTheme.objects.filter(company=self.company).count(), 1)
        theme.refresh_from_db()
        self.assertEqual(theme.couleur_primaire, '#222222')

    def test_company_isolation(self):
        TenantTheme.objects.create(company=self.other, couleur_primaire='#999')
        resp = self._get(self.user)
        # L'utilisateur d'ACME ne voit pas le thème de l'autre société.
        self.assertEqual(resp.data['couleur_primaire'], '')
