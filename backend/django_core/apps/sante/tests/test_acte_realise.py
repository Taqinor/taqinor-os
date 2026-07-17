"""NTSAN10 — Acte réalisé `ActeRealise` : tarif snapshotté (jamais recalculé
rétroactivement), complète les gardes NTSAN6 (clôture admission) et NTSAN7
(suppression ActeMedical) maintenant que ce modèle existe.
"""
import datetime as dt

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.sante.models import (
    Admission, ActeMedical, ActeRealise, Convention, GrilleTarifaire, Patient,
    Praticien)
from apps.sante.services import cloturer_admission, realiser_acte

DATE_REALISATION = timezone.make_aware(dt.datetime(2026, 8, 5, 10, 0))


class ActeRealiseSnapshotTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-acte-real-co', defaults={'nom': 'Clinique Acte Réalisé'})
        self.patient = Patient.objects.create(company=self.company, nom='X')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Ghali')
        self.admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_admission=DATE_REALISATION)
        self.acte = ActeMedical.objects.create(
            company=self.company, libelle='Consultation', tarif_base_ttc='150.00')

    def test_tarif_frozen_even_if_grille_changes_later(self):
        """Critère d'acceptation NTSAN10 : test de non-régression — le tarif
        facturé reste figé même si `GrilleTarifaire` change ensuite."""
        convention = Convention.objects.create(
            company=self.company, nom='CNOPS', type=Convention.Type.CNOPS)
        self.patient.convention = convention
        self.patient.save(update_fields=['convention'])
        GrilleTarifaire.objects.create(
            company=self.company, convention=convention, acte=self.acte,
            tarif_convention_ttc='90.00')

        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)
        self.assertEqual(str(acte_realise.tarif_applique_ttc), '90.00')

        # La grille change ensuite.
        grille = GrilleTarifaire.objects.get(convention=convention, acte=self.acte)
        grille.tarif_convention_ttc = '200.00'
        grille.save(update_fields=['tarif_convention_ttc'])

        acte_realise.refresh_from_db()
        self.assertEqual(str(acte_realise.tarif_applique_ttc), '90.00')

    def test_no_convention_snapshots_tarif_base(self):
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)

        self.assertEqual(acte_realise.tarif_applique_ttc, self.acte.tarif_base_ttc)


class AdmissionClosureGuardTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-adm-guard-co', defaults={'nom': 'Clinique Guard'})
        self.patient = Patient.objects.create(company=self.company, nom='Y')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Idrissi')
        self.acte = ActeMedical.objects.create(
            company=self.company, libelle='Radio', tarif_base_ttc='300.00')

    def test_cloture_refused_with_unbilled_facturable_acte(self):
        admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_admission=DATE_REALISATION)
        realiser_acte(
            admission=admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION, facturable=True)

        with self.assertRaises(ValueError):
            cloturer_admission(admission)

    def test_cloture_allowed_when_acte_marked_non_facturable(self):
        admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_admission=DATE_REALISATION)
        realiser_acte(
            admission=admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION, facturable=False)

        cloturer_admission(admission)

        admission.refresh_from_db()
        self.assertEqual(admission.statut, Admission.Statut.CLOTUREE)


class ActeMedicalDestroyGuardTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-acte-destroy-co', defaults={'nom': 'Clinique Destroy'})

    def test_used_acte_cannot_be_deleted(self):
        from apps.sante.viewsets import ActeMedicalViewSet

        acte = ActeMedical.objects.create(
            company=self.company, libelle='Suture', tarif_base_ttc='200.00')
        patient = Patient.objects.create(company=self.company, nom='Z')
        praticien = Praticien.objects.create(company=self.company, nom='Dr. Kabbaj')
        admission = Admission.objects.create(
            company=self.company, patient=patient, praticien=praticien,
            date_admission=DATE_REALISATION)
        ActeRealise.objects.create(
            company=self.company, admission=admission, patient=patient,
            praticien=praticien, acte=acte, date_realisation=DATE_REALISATION,
            tarif_applique_ttc='200.00')

        viewset = ActeMedicalViewSet()
        message = viewset.destroy_guard_message(acte)

        self.assertIsNotNone(message)

    def test_unused_acte_has_no_guard_message(self):
        from apps.sante.viewsets import ActeMedicalViewSet

        acte = ActeMedical.objects.create(
            company=self.company, libelle='Pansement', tarif_base_ttc='20.00')

        viewset = ActeMedicalViewSet()
        message = viewset.destroy_guard_message(acte)

        self.assertIsNone(message)
