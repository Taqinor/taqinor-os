"""ARC2 — pilote ``TransporteurViewSet`` converti à ``CompanyScopedModelViewSet``.

Prouve l'isolation multi-tenant et le comportement INCHANGÉ après bascule sur la
base transverse unique : (a) la société B ne voit jamais un transporteur de la
société A (liste + détail 404, jamais 403) ; (b) ``company`` et ``created_by``
restent forcés côté serveur (jamais lus du corps) ; (c) la matrice de droits est
identique (lecture tout rôle, écriture responsable/admin).
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.installations.models import Transporteur

URL = '/api/django/installations/transporteurs/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestTransporteurIsolationARC2(TestCase):
    def setUp(self):
        self.company_a, _ = Company.objects.get_or_create(
            slug='arc2-transp-a', defaults={'nom': 'Société A'})
        self.company_b, _ = Company.objects.get_or_create(
            slug='arc2-transp-b', defaults={'nom': 'Société B'})
        self.admin_a = CustomUser.objects.create_user(
            username='arc2_transp_admin_a', password='x',
            role_legacy=CustomUser.ROLE_ADMIN, company=self.company_a)
        self.admin_b = CustomUser.objects.create_user(
            username='arc2_transp_admin_b', password='x',
            role_legacy=CustomUser.ROLE_ADMIN, company=self.company_b)
        # Un transporteur appartenant à la société B.
        self.transp_b = Transporteur.objects.create(
            company=self.company_b, nom='Transport B')

    @staticmethod
    def _rows(resp):
        return resp.data['results'] if isinstance(resp.data, dict) else resp.data

    def test_list_scoped_to_company(self):
        """La société A ne voit PAS le transporteur de la société B."""
        r = _api(self.admin_a).get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        ids = {row['id'] for row in self._rows(r)}
        self.assertNotIn(self.transp_b.id, ids)

    def test_detail_of_other_company_is_404(self):
        """Détail d'un objet d'une autre société → 404 (jamais 403)."""
        r = _api(self.admin_a).get(f'{URL}{self.transp_b.id}/')
        self.assertEqual(r.status_code, 404, r.data)

    def test_company_and_created_by_forced_server_side(self):
        """POST : société forcée serveur (B injecté ignoré) + created_by posé."""
        api = _api(self.admin_a)
        r = api.post(
            URL, {'nom': 'Mon transporteur', 'company': self.company_b.id},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        obj = Transporteur.objects.get(nom='Mon transporteur')
        self.assertEqual(obj.company, self.company_a)
        self.assertEqual(obj.created_by, self.admin_a)


class TestTransporteurPermissionsARC2(TestCase):
    """La matrice de droits (401/403) reste identique après ARC2."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='arc2-transp-perm', defaults={'nom': 'Société P'})

    def test_unauthenticated_is_401(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_non_privileged_cannot_write(self):
        """Écriture réservée responsable/admin : un compte Normal → 403."""
        member = CustomUser.objects.create_user(
            username='arc2_transp_member', password='x',
            role_legacy=CustomUser.ROLE_NORMAL, company=self.company)
        r = _api(member).post(URL, {'nom': 'X'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
