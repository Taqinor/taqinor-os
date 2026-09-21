"""NTSAN6 — Parcours administratif patient `Admission`.

Le critère « clôture impossible tant que des actes ne sont ni facturés ni
marqués non-facturables » est complété/testé dans `test_acte_realise.py`
(NTSAN10) une fois `ActeRealise` posé — avant cela, une admission sans acte se
clôture toujours (vacuously vraie), ce que ce fichier couvre.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.sante.models import Admission, Patient, Praticien
from apps.sante.services import cloturer_admission

User = get_user_model()


class AdmissionModelTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sante-adm-co', defaults={'nom': 'Clinique Admission'})
        self.patient = Patient.objects.create(company=self.company, nom='Z')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Fassi')

    def test_cloture_sans_acte_toujours_autorisee(self):
        admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien,
            date_admission=timezone.make_aware(dt.datetime(2026, 8, 1, 9, 0)))

        cloturer_admission(admission)

        admission.refresh_from_db()
        self.assertEqual(admission.statut, Admission.Statut.CLOTUREE)
        self.assertIsNotNone(admission.date_sortie)

    def test_cloture_deja_cloturee_refusee(self):
        admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien,
            date_admission=timezone.make_aware(dt.datetime(2026, 8, 1, 9, 0)),
            statut=Admission.Statut.CLOTUREE)

        with self.assertRaises(ValueError):
            cloturer_admission(admission)
