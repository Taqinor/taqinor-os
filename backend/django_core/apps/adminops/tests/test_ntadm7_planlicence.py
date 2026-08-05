"""NTADM7 — catalogue PlanLicence (GLOBAL, pas de scoping société)."""
from django.test import TestCase

from ..models import PlanLicence


class PlanLicenceTests(TestCase):
    def test_seed_migration_a_cree_les_3_paliers(self):
        codes = set(PlanLicence.objects.values_list('code', flat=True))
        self.assertEqual(codes, {'starter', 'pro', 'enterprise'})

    def test_pas_de_champ_company(self):
        """SCA4 — catalogue GLOBAL : aucune FK company (jamais de scoping
        société sur ce modèle)."""
        self.assertNotIn(
            'company', [f.name for f in PlanLicence._meta.get_fields()])

    def test_str(self):
        plan = PlanLicence.objects.get(code='starter')
        self.assertEqual(str(plan), plan.nom)
