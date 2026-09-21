"""NTSAN8 — Tarifs par convention `GrilleTarifaire` : la facturation lit la
grille de la convention du patient si elle existe, sinon retombe sur
`tarif_base_ttc`.
"""
from django.test import TestCase

from authentication.models import Company

from apps.sante.models import ActeMedical, Convention, GrilleTarifaire
from apps.sante.selectors import tarif_applicable


class GrilleTarifaireSelectorTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-grille-co', defaults={'nom': 'Clinique Grille'})
        self.acte = ActeMedical.objects.create(
            company=self.company, libelle='Consultation', tarif_base_ttc='150.00')
        self.convention = Convention.objects.create(
            company=self.company, nom='CNOPS', type=Convention.Type.CNOPS)

    def test_falls_back_to_tarif_base_when_no_grille(self):
        result = tarif_applicable(self.acte, self.convention)

        self.assertEqual(result['tarif_ttc'], self.acte.tarif_base_ttc)
        self.assertEqual(result['source'], 'base')

    def test_uses_grille_tarifaire_when_present(self):
        GrilleTarifaire.objects.create(
            company=self.company, convention=self.convention, acte=self.acte,
            tarif_convention_ttc='90.00', taux_prise_charge_pct='80.00')

        result = tarif_applicable(self.acte, self.convention)

        self.assertEqual(str(result['tarif_ttc']), '90.00')
        self.assertEqual(result['source'], 'grille')

    def test_no_convention_uses_tarif_base(self):
        result = tarif_applicable(self.acte, None)

        self.assertEqual(result['tarif_ttc'], self.acte.tarif_base_ttc)
        self.assertEqual(result['source'], 'base')

    def test_unique_constraint_one_row_per_convention_acte(self):
        GrilleTarifaire.objects.create(
            company=self.company, convention=self.convention, acte=self.acte,
            tarif_convention_ttc='90.00')

        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GrilleTarifaire.objects.create(
                    company=self.company, convention=self.convention,
                    acte=self.acte, tarif_convention_ttc='95.00')
