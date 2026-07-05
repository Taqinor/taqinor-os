"""Shared multi-tenant/auth test base for DRF API tests (YTEST2).

Every test file was re-deriving the same boilerplate (create a company, a
user, authenticate a client) by hand. ``TenantAPITestCase`` centralizes it on
top of the YTEST1 factories:

    from testkit.base import TenantAPITestCase

    class TestDevisApi(TenantAPITestCase):
        def test_list_is_company_scoped(self):
            r = self.client_as().get('/api/django/ventes/devis/')
            self.assertEqual(r.status_code, 200)

        def test_other_company_cannot_see_it(self):
            r = self.client_as(user=self.other_user).get(
                f'/api/django/ventes/devis/{self.devis.id}/')
            self.assertIn(r.status_code, (403, 404))

Convention (see docs/TESTING.md): every new API test inherits from
``TenantAPITestCase``; build objects through the ``testkit.factories``
factories, never ``objects.create`` by hand.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit.factories import CompanyFactory, UserFactory, another_tenant


class TenantAPITestCase(TestCase):
    """Base class for authenticated, multi-tenant DRF API tests.

    ``setUp`` builds:
      - ``self.company`` / ``self.user`` — the primary tenant + its user.
      - ``self.other_company`` / ``self.other_user`` — a second, unrelated
        tenant for isolation assertions ("does reading company A's object as
        company B's user 404/403, never leak data?").
      - ``self.client_as(user=None, role=None)`` — an ``APIClient`` bearing a
        valid JWT for the given user (defaults to ``self.user``). Pass
        ``role=`` to get a fresh user with that ``role_legacy`` in the SAME
        company as ``self.user`` (handy for role-gating tests without
        manually constructing another user).
    """

    def setUp(self):
        super().setUp()
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        self.other_company, self.other_user = another_tenant()

    def client_as(self, user=None, role=None):
        if role is not None:
            user = UserFactory(company=self.company, role_legacy=role)
        if user is None:
            user = self.user
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api
