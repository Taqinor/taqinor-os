"""Tests du modèle ``CampagneInnovation`` (NTIDE25).

Couvre : création company-scopée, statut par défaut (brouillon), segment
JSON par défaut (liste vide), ``cible_departement`` opaque (jamais un FK
cross-app), isolation multi-société via le manager standard.
"""
from django.test import TestCase

from authentication.models import Company

from apps.innovation.models import ROLES_CIBLABLES, CampagneInnovation


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CampagneInnovationModelTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide25-a', 'A')
        self.co_b = make_company('innov-ntide25-b', 'B')

    def test_create_defaults(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Idées pompage')
        self.assertEqual(camp.statut, CampagneInnovation.Statut.BROUILLON)
        self.assertEqual(camp.segment, [])
        self.assertEqual(camp.cible_departement, '')
        self.assertIsNone(camp.date_debut)
        self.assertIsNone(camp.date_fin)

    def test_segment_stores_role_list(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Multi-rôles',
            segment=['Technicien', 'Commercial'])
        camp.refresh_from_db()
        self.assertEqual(camp.segment, ['Technicien', 'Commercial'])

    def test_cible_departement_is_opaque_string(self):
        camp = CampagneInnovation.objects.create(
            company=self.co_a, nom='Cible unique', cible_departement='Pompage')
        self.assertEqual(camp.cible_departement, 'Pompage')

    def test_roles_ciblables_matches_ntide7_fallback(self):
        self.assertEqual(
            ROLES_CIBLABLES, ['Technicien', 'Commercial', 'Directeur'])

    def test_str_is_nom(self):
        camp = CampagneInnovation.objects.create(company=self.co_a, nom='Ma campagne')
        self.assertEqual(str(camp), 'Ma campagne')

    def test_isolated_per_company(self):
        CampagneInnovation.objects.create(company=self.co_a, nom='A')
        CampagneInnovation.objects.create(company=self.co_b, nom='B')
        self.assertEqual(
            CampagneInnovation.objects.filter(company=self.co_a).count(), 1)
