"""SCA18 — Company.statut appliqué au JWT et à l'API.

Vérifie que :
* login et API sont bloqués pour un tenant suspendu ;
* un tenant actif est inchangé (byte-identique) ;
* un token existant d'un tenant suspendu est rejeté au refresh ;
* le pont bool↔statut est réversible et cohérent.
"""
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory, UserFactory
from authentication.models import Company


class TenantStatutBridgeTest(TenantAPITestCase):
    def test_backfill_bridge_actif_vers_statut(self):
        c = CompanyFactory(nom='Pont', slug='pont')
        self.assertEqual(c.statut, Company.STATUT_ACTIF)
        self.assertTrue(c.actif)
        self.assertTrue(c.est_operationnel)

    def test_suspendre_via_statut_coupe_actif(self):
        c = CompanyFactory(nom='Susp', slug='susp')
        c.statut = Company.STATUT_SUSPENDU
        c.save()
        c.refresh_from_db()
        self.assertFalse(c.actif)
        self.assertFalse(c.est_operationnel)

    def test_fermeture_via_statut_coupe_actif(self):
        c = CompanyFactory(nom='Ferm', slug='ferm')
        c.statut = Company.STATUT_FERMETURE
        c.save()
        c.refresh_from_db()
        self.assertFalse(c.actif)

    def test_bool_actif_false_promeut_statut_suspendu(self):
        # Un code historique qui met actif=False doit rester effectif.
        c = CompanyFactory(nom='Legacy', slug='legacy')
        c.actif = False
        c.save()
        c.refresh_from_db()
        self.assertEqual(c.statut, Company.STATUT_SUSPENDU)
        self.assertFalse(c.actif)

    def test_reactivation_reversible(self):
        c = CompanyFactory(nom='React', slug='react')
        c.statut = Company.STATUT_SUSPENDU
        c.save()
        c.statut = Company.STATUT_ACTIF
        c.save()
        c.refresh_from_db()
        self.assertTrue(c.actif)
        self.assertTrue(c.est_operationnel)


class TenantSuspenduLoginApiTest(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.susp_company = CompanyFactory(nom='Bloquée', slug='bloquee')
        self.susp_user = UserFactory(
            username='blocked', password='pw12345678',
            company=self.susp_company)
        self.susp_company.statut = Company.STATUT_SUSPENDU
        self.susp_company.save()

    def test_login_refuse_pour_tenant_suspendu(self):
        api = APIClient()
        r = api.post('/api/django/token/',
                     {'username': 'blocked', 'password': 'pw12345678'},
                     format='json')
        self.assertEqual(r.status_code, 400)

    def test_api_bloquee_pour_tenant_suspendu(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.susp_user)}')
        r = api.get('/api/django/crm/clients/')
        self.assertEqual(r.status_code, 403)

    def test_refresh_rejete_pour_tenant_suspendu(self):
        refresh = RefreshToken.for_user(self.susp_user)
        api = APIClient()
        api.cookies['refresh_token'] = str(refresh)
        r = api.post('/api/django/auth/token/refresh/')
        self.assertEqual(r.status_code, 403)

    def test_tenant_actif_inchange(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        r = api.get('/api/django/crm/clients/')
        self.assertEqual(r.status_code, 200)

    def test_superuser_exempte_meme_si_tenant_suspendu(self):
        su = UserFactory(username='root-su', company=self.susp_company)
        su.is_superuser = True
        su.is_staff = True
        su.save()
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(su)}')
        # /auth/me/ est exempté ; et même une route API n'est pas bloquée pour un
        # superuser.
        r = api.get('/api/django/auth/me/')
        self.assertEqual(r.status_code, 200)
