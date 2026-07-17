"""Tests du modèle ``Idee`` (NTIDE1).

Couvre : statut par défaut, votes_count dénormalisé initialisé à zéro,
company-scoping (héritage ``TenantModel``), lien opaque devis/ticket/chantier
(string-FK, jamais un import cross-app), et ``__str__``.
"""
from django.test import TestCase

from authentication.models import Company

from apps.innovation.models import Idee


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class IdeeModelTests(TestCase):
    def setUp(self):
        self.company = make_company('innov-model-a', 'A')

    def test_default_statut_ouvert(self):
        idee = Idee.objects.create(company=self.company, titre='Une idée')
        self.assertEqual(idee.statut, Idee.Statut.OUVERT)

    def test_votes_count_defaults_to_zero(self):
        idee = Idee.objects.create(company=self.company, titre='Une idée')
        self.assertEqual(idee.votes_count, 0)

    def test_company_scoped_via_tenant_model(self):
        idee = Idee.objects.create(company=self.company, titre='Une idée')
        self.assertEqual(idee.company, self.company)
        self.assertIsNotNone(idee.created_at)
        self.assertIsNotNone(idee.updated_at)

    def test_linked_type_and_id_opaque(self):
        idee = Idee.objects.create(
            company=self.company, titre='Idée liée',
            linked_type=Idee.LinkedType.DEVIS, linked_id=42)
        self.assertEqual(idee.linked_type, 'devis')
        self.assertEqual(idee.linked_id, 42)

    def test_linked_fields_optional(self):
        idee = Idee.objects.create(company=self.company, titre='Sans lien')
        self.assertEqual(idee.linked_type, '')
        self.assertIsNone(idee.linked_id)

    def test_str_returns_titre(self):
        idee = Idee.objects.create(company=self.company, titre='Mon titre')
        self.assertEqual(str(idee), 'Mon titre')

    def test_ordering_most_recent_first(self):
        first = Idee.objects.create(company=self.company, titre='Première')
        second = Idee.objects.create(company=self.company, titre='Seconde')
        ids = list(Idee.objects.filter(company=self.company).values_list('id', flat=True))
        self.assertEqual(ids, [second.id, first.id])
