"""NTFPA2 — apps.compta.selectors.get_exercice_label : lecture minimale pour
l'app FP&A (apps.fpa.CycleBudgetaire.exercice_comptable_id, string-id)."""
from datetime import date

from django.test import TestCase

from authentication.models import Company
from apps.compta.models import ExerciceComptable
from apps.compta.selectors import get_exercice_label


class TestGetExerciceLabel(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa2-sel-co', defaults={'nom': 'NTFPA2 Sel Co'})
        self.autre, _ = Company.objects.get_or_create(
            slug='ntfpa2-sel-autre', defaults={'nom': 'Autre'})
        self.exercice = ExerciceComptable.objects.create(
            company=self.company, libelle='Exercice 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))

    def test_retourne_le_libelle_et_les_bornes(self):
        label = get_exercice_label(self.company, self.exercice.pk)
        self.assertEqual(label['libelle'], 'Exercice 2027')
        self.assertEqual(label['date_debut'], date(2027, 1, 1))

    def test_none_si_absent(self):
        self.assertIsNone(get_exercice_label(self.company, None))
        self.assertIsNone(get_exercice_label(self.company, 999999))

    def test_none_si_hors_societe(self):
        self.assertIsNone(get_exercice_label(self.autre, self.exercice.pk))
