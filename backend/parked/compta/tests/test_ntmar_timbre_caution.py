"""NTMAR20/24 — Timbre électronique (mode d'acquittement + synthèse) &
cautions à restituer.

Critères : le rapport mensuel liste les timbres par mode d'acquittement ; une
caution provisoire arrivant à échéance apparaît dans « à restituer » avec sa
date de mainlevée."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import CautionBancaire

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TimbreSyntheseTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-timbre', 'NTMAR Timbre')

    def test_synthese_ventilated_by_mode(self):
        services.enregistrer_timbre_fiscal(
            self.company, date_encaissement=date(2026, 6, 5),
            base=Decimal('4000'), mode_reglement='especes',
            mode_acquittement='electronique', facture_ref='FAC-1')
        services.enregistrer_timbre_fiscal(
            self.company, date_encaissement=date(2026, 6, 10),
            base=Decimal('8000'), mode_reglement='especes',
            mode_acquittement='papier', facture_ref='FAC-2')
        data = selectors.synthese_timbre_mensuelle(self.company, 2026, 6)
        self.assertEqual(len(data['lignes']), 2)
        self.assertIn('electronique', data['total_par_mode'])
        self.assertIn('papier', data['total_par_mode'])
        # 0,25 % de 4000 = 10 ; de 8000 = 20.
        self.assertEqual(data['total'], Decimal('30.00'))


class CautionsARestituerTests(TestCase):
    def setUp(self):
        self.company = make_company('ntmar-caution', 'NTMAR Caution')

    def test_active_caution_with_echeance_listed(self):
        today = timezone.localdate()
        CautionBancaire.objects.create(
            company=self.company, reference='CB-1',
            type_caution=CautionBancaire.TypeCaution.PROVISOIRE,
            marche_ref='AO-2026-01', montant=Decimal('50000'),
            date_emission=today - timedelta(days=90),
            date_echeance=today + timedelta(days=10),
            date_mainlevee=today + timedelta(days=10),
            statut=CautionBancaire.Statut.ACTIVE)
        data = selectors.cautions_a_restituer(self.company)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['reference'], 'CB-1')
        self.assertEqual(data[0]['date_mainlevee'], today + timedelta(days=10))

    def test_within_filter_excludes_far_echeance(self):
        today = timezone.localdate()
        CautionBancaire.objects.create(
            company=self.company, reference='CB-2',
            type_caution=CautionBancaire.TypeCaution.DEFINITIVE,
            montant=Decimal('10000'), date_emission=today,
            date_echeance=today + timedelta(days=200),
            statut=CautionBancaire.Statut.ACTIVE)
        self.assertEqual(
            selectors.cautions_a_restituer(self.company, within=30), [])
        self.assertEqual(
            len(selectors.cautions_a_restituer(self.company)), 1)

    def test_lifted_caution_excluded(self):
        today = timezone.localdate()
        CautionBancaire.objects.create(
            company=self.company, reference='CB-3',
            type_caution=CautionBancaire.TypeCaution.PROVISOIRE,
            montant=Decimal('10000'), date_emission=today,
            date_echeance=today + timedelta(days=5),
            statut=CautionBancaire.Statut.LEVEE)
        self.assertEqual(selectors.cautions_a_restituer(self.company), [])
