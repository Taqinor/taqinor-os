"""NTSAN15 — Encaissement & reste à charge `PaiementSante` : une
`FactureSante` peut avoir plusieurs paiements partiels ; `montant_du =
total_ttc - somme(paiements)`, jamais négatif sans flag d'avoir.
"""
import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.sante.models import (
    ActeMedical, Admission, FactureSante, Patient, Praticien)
from apps.sante.services import (
    creer_facture_sante, enregistrer_paiement, montant_du, realiser_acte)

DATE_REALISATION = timezone.make_aware(dt.datetime(2026, 8, 15, 9, 0))
DATE_PAIEMENT = timezone.make_aware(dt.datetime(2026, 8, 15, 11, 0))


class PaiementSanteTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-paiement-co', defaults={'nom': 'Clinique Paiement'})
        self.patient = Patient.objects.create(company=self.company, nom='A')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Sefrioui')
        self.admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien, date_admission=DATE_REALISATION)
        self.acte = ActeMedical.objects.create(
            company=self.company, libelle='Consultation', tarif_base_ttc='300.00')
        acte_realise = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=DATE_REALISATION)
        self.facture = creer_facture_sante(
            admission=self.admission, actes_realises=[acte_realise])

    def test_montant_du_before_any_payment(self):
        self.assertEqual(montant_du(self.facture), self.facture.total_ttc)

    def test_partial_payments_reduce_montant_du_and_never_go_negative(self):
        enregistrer_paiement(
            facture_sante=self.facture, montant=Decimal('100.00'),
            mode='especes', date_paiement=DATE_PAIEMENT)
        self.facture.refresh_from_db()
        self.assertEqual(montant_du(self.facture), Decimal('200.00'))
        self.assertEqual(self.facture.statut, FactureSante.Statut.PAYEE_PARTIEL)

        enregistrer_paiement(
            facture_sante=self.facture, montant=Decimal('200.00'),
            mode='carte', date_paiement=DATE_PAIEMENT)
        self.facture.refresh_from_db()
        self.assertEqual(montant_du(self.facture), Decimal('0'))
        self.assertEqual(self.facture.statut, FactureSante.Statut.PAYEE)

        # Un paiement en trop (overpay) ne fait jamais passer montant_du
        # sous zéro (pas de flag d'avoir posé ici).
        enregistrer_paiement(
            facture_sante=self.facture, montant=Decimal('50.00'),
            mode='especes', date_paiement=DATE_PAIEMENT)
        self.facture.refresh_from_db()
        self.assertEqual(montant_du(self.facture), Decimal('0'))
        self.assertGreaterEqual(montant_du(self.facture), Decimal('0'))

    def test_multiple_partial_payments_sum_correctly(self):
        enregistrer_paiement(
            facture_sante=self.facture, montant=Decimal('50.00'),
            mode='especes', date_paiement=DATE_PAIEMENT)
        enregistrer_paiement(
            facture_sante=self.facture, montant=Decimal('50.00'),
            mode='cheque', date_paiement=DATE_PAIEMENT)

        self.facture.refresh_from_db()
        self.assertEqual(self.facture.paiements.count(), 2)
        self.assertEqual(montant_du(self.facture), Decimal('200.00'))
