"""NTSAN9 — Modèle `Convention` (mutuelle/CNOPS/CNSS/cash) : liste
paramétrable par clinique, aucune convention codée en dur ; `Patient.
convention`/`numero_affiliation`.
"""
from django.test import TestCase

from authentication.models import Company

from apps.sante.models import Convention, Patient


class ConventionModelTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-conv-co', defaults={'nom': 'Clinique Convention'})

    def test_conventions_are_configurable_per_company_not_hardcoded(self):
        """Aucune convention codée en dur : une société peut créer la liste
        qu'elle veut (même un type non standard « autre »)."""
        c1 = Convention.objects.create(
            company=self.company, nom='CNOPS', type=Convention.Type.CNOPS,
            taux_tiers_payant_pct='80.00')
        c2 = Convention.objects.create(
            company=self.company, nom='Ma mutuelle maison',
            type=Convention.Type.AUTRE)

        self.assertEqual(
            set(Convention.objects.filter(company=self.company)
                .values_list('id', flat=True)),
            {c1.id, c2.id})

    def test_patient_convention_and_numero_affiliation(self):
        convention = Convention.objects.create(
            company=self.company, nom='CNSS', type=Convention.Type.CNSS)
        patient = Patient.objects.create(
            company=self.company, nom='Alami', convention=convention,
            numero_affiliation='AFF-001')

        patient.refresh_from_db()
        self.assertEqual(patient.convention_id, convention.id)
        self.assertEqual(patient.numero_affiliation, 'AFF-001')
