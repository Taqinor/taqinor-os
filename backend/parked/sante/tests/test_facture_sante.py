"""NTSAN13 — Facturation patient/tiers payant `FactureSante` : split
tiers payant/patient depuis `GrilleTarifaire`/`PriseEnCharge`, invariant
`part_tiers_payant + part_patient == total_ttc`. Complète aussi la garde de
clôture d'admission (NTSAN6) avec le critère « facturé ».
"""
import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.sante.models import (
    ActeMedical, Admission, Convention, GrilleTarifaire, Patient, Praticien,
    PriseEnCharge)
from apps.sante.services import (
    cloturer_admission, creer_facture_sante, realiser_acte)

DATE_REALISATION = timezone.make_aware(dt.datetime(2026, 8, 12, 9, 0))


class FactureSanteSplitTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-fact-co', defaults={'nom': 'Clinique Facture'})
        self.patient = Patient.objects.create(company=self.company, nom='A')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Naciri')
        self.admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_admission=DATE_REALISATION)
        self.acte = ActeMedical.objects.create(
            company=self.company, libelle='Consultation', tarif_base_ttc='200.00')

    def test_split_via_grille_tarifaire_sums_to_total(self):
        convention = Convention.objects.create(
            company=self.company, nom='CNOPS', type=Convention.Type.CNOPS)
        self.patient.convention = convention
        self.patient.save(update_fields=['convention'])
        GrilleTarifaire.objects.create(
            company=self.company, convention=convention, acte=self.acte,
            tarif_convention_ttc='150.00', taux_prise_charge_pct='80.00')
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)

        facture = creer_facture_sante(
            admission=self.admission, actes_realises=[acte_realise],
            convention=convention)

        self.assertEqual(
            facture.part_tiers_payant_ttc + facture.part_patient_ttc,
            facture.total_ttc)
        # tarif appliqué (snapshotté) = 150.00 (via grille) ; 80% tiers payant.
        self.assertEqual(facture.part_tiers_payant_ttc, Decimal('120.00'))
        self.assertEqual(facture.part_patient_ttc, Decimal('30.00'))

    def test_no_coverage_patient_pays_all_sums_to_total(self):
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)

        facture = creer_facture_sante(
            admission=self.admission, actes_realises=[acte_realise])

        self.assertEqual(
            facture.part_tiers_payant_ttc + facture.part_patient_ttc,
            facture.total_ttc)
        self.assertEqual(facture.part_tiers_payant_ttc, Decimal('0'))
        self.assertEqual(facture.part_patient_ttc, facture.total_ttc)

    def test_refused_prise_en_charge_forces_patient_pays_all(self):
        convention = Convention.objects.create(
            company=self.company, nom='CNSS', type=Convention.Type.CNSS)
        pec = PriseEnCharge.objects.create(
            company=self.company, patient=self.patient, convention=convention,
            date_demande=dt.date(2026, 8, 1),
            statut=PriseEnCharge.Statut.REFUSEE)
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)
        acte_realise.prise_en_charge = pec
        acte_realise.save(update_fields=['prise_en_charge'])

        facture = creer_facture_sante(
            admission=self.admission, actes_realises=[acte_realise])

        self.assertEqual(facture.part_tiers_payant_ttc, Decimal('0'))
        self.assertEqual(facture.part_patient_ttc, facture.total_ttc)
        self.assertEqual(
            facture.part_tiers_payant_ttc + facture.part_patient_ttc,
            facture.total_ttc)

    def test_multiple_lignes_sums_to_total(self):
        acte_2 = ActeMedical.objects.create(
            company=self.company, libelle='Pansement', tarif_base_ttc='50.00')
        a1 = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)
        a2 = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=acte_2,
            date_realisation=DATE_REALISATION)

        facture = creer_facture_sante(
            admission=self.admission, actes_realises=[a1, a2])

        self.assertEqual(facture.total_ttc, Decimal('250.00'))
        self.assertEqual(
            facture.part_tiers_payant_ttc + facture.part_patient_ttc,
            facture.total_ttc)

    def test_facturer_lignes_links_acte_realise_to_facture(self):
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)

        facture = creer_facture_sante(
            admission=self.admission, actes_realises=[acte_realise])

        acte_realise.refresh_from_db()
        self.assertEqual(acte_realise.facture_sante_id, facture.id)


class AdmissionClosureWithBillingTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-fact-adm-co', defaults={'nom': 'Clinique Facture Adm'})
        self.patient = Patient.objects.create(company=self.company, nom='B')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Ouahbi')
        self.acte = ActeMedical.objects.create(
            company=self.company, libelle='Radio', tarif_base_ttc='100.00')

    def test_cloture_allowed_once_acte_is_billed(self):
        admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_admission=DATE_REALISATION)
        acte_realise = realiser_acte(
            admission=admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)

        with self.assertRaises(ValueError):
            cloturer_admission(admission)

        creer_facture_sante(admission=admission, actes_realises=[acte_realise])

        cloturer_admission(admission)
        admission.refresh_from_db()
        self.assertEqual(admission.statut, Admission.Statut.CLOTUREE)
