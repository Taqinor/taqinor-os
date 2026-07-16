"""ARC2 — pilote ``CauseDefaillanceViewSet`` converti à
``CompanyScopedModelViewSet``.

Prouve l'isolation multi-tenant et le comportement INCHANGÉ après bascule sur la
base transverse unique : (a) la société B ne voit jamais une cause de la société
A (liste + détail 404, jamais 403) ; (b) ``company`` reste forcée côté serveur
(jamais lue du corps) ; (c) la matrice de droits est identique (lecture tout
rôle, écriture responsable/admin).
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.sav.models import CauseDefaillance

URL = '/api/django/sav/causes-defaillance/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestCauseDefaillanceIsolationARC2(TestCase):
    def setUp(self):
        self.company_a, _ = Company.objects.get_or_create(
            slug='arc2-cause-a', defaults={'nom': 'Société A'})
        self.company_b, _ = Company.objects.get_or_create(
            slug='arc2-cause-b', defaults={'nom': 'Société B'})
        self.admin_a = CustomUser.objects.create_user(
            username='arc2_cause_admin_a', password='x',
            role_legacy=CustomUser.ROLE_ADMIN, company=self.company_a)
        self.cause_b = CauseDefaillance.objects.create(
            company=self.company_b, nom='Cause B')

    @staticmethod
    def _rows(resp):
        return resp.data['results'] if isinstance(resp.data, dict) else resp.data

    def test_list_scoped_to_company(self):
        """La société A ne voit PAS la cause de la société B."""
        r = _api(self.admin_a).get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        ids = {row['id'] for row in self._rows(r)}
        self.assertNotIn(self.cause_b.id, ids)

    def test_detail_of_other_company_is_404(self):
        """Détail d'un objet d'une autre société → 404 (jamais 403)."""
        r = _api(self.admin_a).get(f'{URL}{self.cause_b.id}/')
        self.assertEqual(r.status_code, 404, r.data)

    def test_company_forced_server_side(self):
        """POST : société forcée serveur (B injecté ignoré)."""
        r = _api(self.admin_a).post(
            URL, {'nom': 'Défaut composant', 'company': self.company_b.id},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        obj = CauseDefaillance.objects.get(nom='Défaut composant')
        self.assertEqual(obj.company, self.company_a)


class TestCauseDefaillancePermissionsARC2(TestCase):
    """La matrice de droits (401/403) reste identique après ARC2."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='arc2-cause-perm', defaults={'nom': 'Société P'})

    def test_unauthenticated_is_401(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_non_privileged_cannot_write(self):
        """Écriture réservée responsable/admin : un compte Normal → 403."""
        member = CustomUser.objects.create_user(
            username='arc2_cause_member', password='x',
            role_legacy=CustomUser.ROLE_NORMAL, company=self.company)
        r = _api(member).post(URL, {'nom': 'X'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
