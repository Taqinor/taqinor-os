"""Tests XRH2 — seed des types d'absence légaux marocains.

Couvre : la commande crée les types statutaires, est idempotente (2 exécutions
ne dupliquent rien), ne modifie jamais un type déjà présent (règle et
``jours_legaux`` figées), et respecte le filtre ``--company-slug``.
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.rh.models import TypeAbsence


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class SeedTypesAbsenceTests(TestCase):
    def setUp(self):
        self.co = make_company('seed-abs-a', 'A')

    def _run(self, **kwargs):
        out = StringIO()
        call_command('seed_types_absence', stdout=out, **kwargs)
        return out.getvalue()

    def test_seed_creates_legal_types(self):
        self._run()
        codes = set(
            TypeAbsence.objects.filter(company=self.co)
            .values_list('code', flat=True))
        self.assertEqual(
            codes, {'MAT', 'PAT', 'MAR', 'NAI', 'DEC', 'CIRC', 'AT', 'MAP'})

    def test_maternite_rule_correct(self):
        self._run()
        mat = TypeAbsence.objects.get(company=self.co, code='MAT')
        self.assertFalse(mat.deduit_solde)
        self.assertFalse(mat.decompte_jours_ouvres)
        self.assertTrue(mat.remunere)
        self.assertEqual(mat.jours_legaux, Decimal('98'))

    def test_idempotent_no_duplicates(self):
        self._run()
        self._run()
        count = TypeAbsence.objects.filter(company=self.co, code='MAT').count()
        self.assertEqual(count, 1)

    def test_never_modifies_existing_type(self):
        # Un type MAT existant, avec une règle personnalisée par le fondateur.
        TypeAbsence.objects.create(
            company=self.co, code='MAT', libelle='Maternité (custom)',
            decompte_jours_ouvres=True, deduit_solde=True,
            remunere=False, jours_legaux=Decimal('60'))
        self._run()
        mat = TypeAbsence.objects.get(company=self.co, code='MAT')
        # Inchangé : la personnalisation du fondateur n'est jamais écrasée.
        self.assertEqual(mat.libelle, 'Maternité (custom)')
        self.assertTrue(mat.decompte_jours_ouvres)
        self.assertTrue(mat.deduit_solde)
        self.assertFalse(mat.remunere)
        self.assertEqual(mat.jours_legaux, Decimal('60'))

    def test_company_slug_filter(self):
        co_b = make_company('seed-abs-b', 'B')
        self._run(company_slug='seed-abs-a')
        self.assertTrue(
            TypeAbsence.objects.filter(company=self.co, code='MAT').exists())
        self.assertFalse(
            TypeAbsence.objects.filter(company=co_b, code='MAT').exists())
