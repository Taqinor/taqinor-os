"""SCA22 — Console fondateur des tenants (staff-only, sans billing).

Vérifie que :
* un non-staff reçoit 403 sur tous les endpoints console ;
* la liste renvoie les compteurs d'usage (users/devis/factures) ;
* suspendre depuis la console bloque le tenant (test API) ;
* la note plan_flag se pose.
"""
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory, UserFactory, DevisFactory
from authentication.models import Company


def _staff_client():
    su = UserFactory(username='founder-su')
    su.is_superuser = True
    su.is_staff = True
    su.save()
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(su)}')
    return api, su


class TenantConsoleAccessTest(TenantAPITestCase):
    def test_non_staff_recoit_403_liste(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        r = api.get('/api/django/auth/console/tenants/')
        self.assertEqual(r.status_code, 403)

    def test_non_staff_recoit_403_statut(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        r = api.post(
            f'/api/django/auth/console/tenants/{self.company.id}/statut/',
            {'statut': 'suspendu'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_staff_voit_la_liste_avec_compteurs(self):
        DevisFactory(company=self.company)
        api, _ = _staff_client()
        r = api.get('/api/django/auth/console/tenants/')
        self.assertEqual(r.status_code, 200)
        ligne = next(t for t in r.data if t['id'] == self.company.id)
        self.assertIn('usage', ligne)
        self.assertGreaterEqual(ligne['usage']['users'], 1)
        self.assertGreaterEqual(ligne['usage']['devis'], 1)


class TenantConsoleActionsTest(TenantAPITestCase):
    def test_suspendre_depuis_console_bloque_tenant(self):
        cible = CompanyFactory(nom='ASuspendre', slug='asuspendre')
        user_cible = UserFactory(username='u-cible', company=cible)
        api, _ = _staff_client()
        r = api.post(
            f'/api/django/auth/console/tenants/{cible.id}/statut/',
            {'statut': 'suspendu'}, format='json')
        self.assertEqual(r.status_code, 200)
        cible.refresh_from_db()
        self.assertEqual(cible.statut, Company.STATUT_SUSPENDU)
        self.assertFalse(cible.actif)
        # Le tenant est bien bloqué (test API réel via le middleware SCA18).
        api2 = APIClient()
        api2.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user_cible)}')
        r2 = api2.get('/api/django/crm/clients/')
        self.assertEqual(r2.status_code, 403)

    def test_note_plan_flag_se_pose(self):
        cible = CompanyFactory(nom='Annoter', slug='annoter')
        api, _ = _staff_client()
        r = api.post(
            f'/api/django/auth/console/tenants/{cible.id}/note/',
            {'plan_flag': 'Plan Pro — à surveiller'}, format='json')
        self.assertEqual(r.status_code, 200)
        cible.refresh_from_db()
        self.assertEqual(cible.plan_flag, 'Plan Pro — à surveiller')

    def test_statut_invalide_refuse(self):
        api, _ = _staff_client()
        r = api.post(
            f'/api/django/auth/console/tenants/{self.company.id}/statut/',
            {'statut': 'nimportequoi'}, format='json')
        self.assertEqual(r.status_code, 400)
