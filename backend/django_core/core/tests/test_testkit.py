"""YTEST1/YTEST2 — self-tests for the shared testkit (factories + base).

Lives here (``core/tests``) rather than inside an app under ``apps/`` because
``testkit`` is shared, app-agnostic infra — ``core`` is the foundation app
(exempt from the cross-app boundary rule) and already hosts its own test
suite, so this is the natural place for the scaffolding's own coverage.
"""
from decimal import Decimal

from django.test import TestCase

from testkit.base import TenantAPITestCase
from testkit.factories import (
    ClientFactory,
    CompanyFactory,
    DevisFactory,
    LigneDevisFactory,
    ProduitFactory,
    UserFactory,
    another_tenant,
)


class TestFactories(TestCase):
    """Building blocks: each factory produces a persistable, valid graph."""

    def test_company_factory_creates_unique_companies(self):
        c1, c2 = CompanyFactory(), CompanyFactory()
        self.assertNotEqual(c1.pk, c2.pk)
        self.assertNotEqual(c1.slug, c2.slug)

    def test_user_factory_attaches_default_company_and_hashed_password(self):
        user = UserFactory()
        self.assertIsNotNone(user.company_id)
        self.assertTrue(user.check_password('x'))
        self.assertNotEqual(user.password, 'x')  # never stored in clear

    def test_user_factory_role_is_parameterizable(self):
        from authentication.models import CustomUser
        user = UserFactory(role_legacy=CustomUser.ROLE_ADMIN)
        self.assertEqual(user.role_legacy, CustomUser.ROLE_ADMIN)

    def test_client_factory_scopes_to_a_company(self):
        client_obj = ClientFactory()
        self.assertIsNotNone(client_obj.company_id)

    def test_devis_factory_produces_a_consistent_tenant_graph(self):
        """The devis and its client must share the same company — no
        factory should ever produce a cross-tenant graph by accident."""
        devis = DevisFactory()
        self.assertEqual(devis.company_id, devis.client.company_id)
        self.assertEqual(devis.statut, 'brouillon')

    def test_ligne_devis_factory_keeps_produit_in_the_devis_company(self):
        ligne = LigneDevisFactory()
        self.assertEqual(ligne.devis.company_id, ligne.produit.company_id)
        self.assertEqual(ligne.prix_unitaire, Decimal('100.00'))

    def test_build_does_not_hit_the_database(self):
        produit = ProduitFactory.build()
        self.assertIsNone(produit.pk)

    def test_another_tenant_builds_an_independent_company_and_user(self):
        company, user = another_tenant()
        self.assertEqual(user.company_id, company.pk)


class TestTenantAPITestCaseDemo(TenantAPITestCase):
    """Demonstrates the convention: reading company A's data as company B's
    user must never leak it (404, never a cross-tenant 200)."""

    def setUp(self):
        super().setUp()
        self.client_obj = ClientFactory(company=self.company)

    def test_owner_can_read_their_own_client(self):
        r = self.client_as().get(f'/api/django/crm/clients/{self.client_obj.id}/')
        self.assertEqual(r.status_code, 200)

    def test_other_company_cannot_read_it(self):
        r = self.client_as(user=self.other_user).get(
            f'/api/django/crm/clients/{self.client_obj.id}/')
        self.assertIn(r.status_code, (403, 404))
