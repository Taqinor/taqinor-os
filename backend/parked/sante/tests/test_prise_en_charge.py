"""NTSAN12 — Prise en charge / entente préalable `PriseEnCharge` : une
`ActeRealise` liée à une prise en charge refusée ou expirée bascule
automatiquement en reste-à-charge patient total, tracé dans l'historique.
"""
import datetime as dt

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.sante.models import (
    ActeMedical, Admission, Convention, Patient, Praticien, PriseEnCharge)
from apps.sante.services import (
    realiser_acte, reste_a_charge_total, verifier_prise_en_charge)
from apps.records.models import Activity

DATE_REALISATION = timezone.make_aware(dt.datetime(2026, 8, 10, 9, 0))


class PriseEnChargeTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-pec-co', defaults={'nom': 'Clinique PEC'})
        self.patient = Patient.objects.create(company=self.company, nom='A')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Lahlou')
        self.convention = Convention.objects.create(
            company=self.company, nom='CNOPS', type=Convention.Type.CNOPS)
        self.admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_admission=DATE_REALISATION)
        self.acte = ActeMedical.objects.create(
            company=self.company, libelle='Chirurgie', tarif_base_ttc='2000.00')

    def _pec(self, statut, date_expiration=None):
        return PriseEnCharge.objects.create(
            company=self.company, patient=self.patient,
            convention=self.convention, admission=self.admission,
            date_demande=dt.date(2026, 7, 1), statut=statut,
            date_expiration=date_expiration)

    def test_reste_a_charge_total_when_refusee(self):
        pec = self._pec(PriseEnCharge.Statut.REFUSEE)
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)
        acte_realise.prise_en_charge = pec
        acte_realise.save(update_fields=['prise_en_charge'])

        self.assertTrue(reste_a_charge_total(acte_realise))

    def test_reste_a_charge_total_when_expiree_by_date(self):
        pec = self._pec(
            PriseEnCharge.Statut.ACCORDEE, date_expiration=dt.date(2020, 1, 1))
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)
        acte_realise.prise_en_charge = pec
        acte_realise.save(update_fields=['prise_en_charge'])

        self.assertTrue(reste_a_charge_total(acte_realise))

    def test_accordee_and_not_expired_is_not_reste_a_charge(self):
        pec = self._pec(
            PriseEnCharge.Statut.ACCORDEE, date_expiration=dt.date(2099, 1, 1))
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)
        acte_realise.prise_en_charge = pec
        acte_realise.save(update_fields=['prise_en_charge'])

        self.assertFalse(reste_a_charge_total(acte_realise))

    def test_verifier_traces_history_once_per_acte(self):
        pec = self._pec(PriseEnCharge.Statut.ACCORDEE)
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)
        acte_realise.prise_en_charge = pec
        acte_realise.save(update_fields=['prise_en_charge'])

        pec.statut = PriseEnCharge.Statut.REFUSEE
        pec.save(update_fields=['statut'])

        touched = verifier_prise_en_charge(pec)

        self.assertEqual(len(touched), 1)
        self.assertEqual(
            Activity.objects.filter(
                object_id=acte_realise.pk,
                content_type__model='acterealise').count(),
            1)

    def test_verifier_no_op_when_not_refused_or_expired(self):
        pec = self._pec(PriseEnCharge.Statut.ACCORDEE)

        touched = verifier_prise_en_charge(pec)

        self.assertEqual(touched, [])
