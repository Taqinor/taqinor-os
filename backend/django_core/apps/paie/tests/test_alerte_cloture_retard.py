"""Tests ZPAI12 — Action planifiée : alerte de clôture de paie en retard.

Couvre :
* ``periodes_cloture_en_retard`` — une période dont le mois SUIVANT est déjà
  entamé et encore en ``brouillon``/``calculee`` est en retard ; une période
  ``validee``/``cloturee``, ou dont le mois suivant n'est pas encore entamé,
  n'y figure pas.
* ``notifier_cloture_en_retard`` — notifie UNE SEULE FOIS (marqueur
  ``date_alerte_cloture_retard``) ; un re-run le lendemain ne renotifie pas ;
  isolation tenant.
* ``apps.automation.beat_tasks._trigger_paie_cloture_retard`` — délègue au
  service paie et renvoie le compte.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.paie.models import PeriodePaie
from apps.paie.services import (
    notifier_cloture_en_retard,
    periodes_cloture_en_retard,
)


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class PeriodesClotureEnRetardTests(TestCase):
    def setUp(self):
        self.co = make_company('cloture-retard')

    def test_periode_ancienne_en_brouillon_est_en_retard(self):
        # Janvier 2020 : le mois suivant (février 2020) est très largement
        # entamé aujourd'hui.
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2020, mois=1,
            statut=PeriodePaie.STATUT_BROUILLON)
        en_retard = periodes_cloture_en_retard(self.co)
        self.assertIn(periode, en_retard)

    def test_periode_cloturee_pas_en_retard(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2020, mois=1,
            statut=PeriodePaie.STATUT_CLOTUREE)
        en_retard = periodes_cloture_en_retard(self.co)
        self.assertNotIn(periode, en_retard)

    def test_periode_validee_pas_en_retard(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2020, mois=1,
            statut=PeriodePaie.STATUT_VALIDEE)
        en_retard = periodes_cloture_en_retard(self.co)
        self.assertNotIn(periode, en_retard)

    def test_periode_mois_courant_pas_en_retard(self):
        today = timezone.localdate()
        periode = PeriodePaie.objects.create(
            company=self.co, annee=today.year, mois=today.month,
            statut=PeriodePaie.STATUT_BROUILLON)
        en_retard = periodes_cloture_en_retard(self.co)
        self.assertNotIn(periode, en_retard)


class NotifierClotureEnRetardTests(TestCase):
    def setUp(self):
        self.co = make_company('cloture-retard-notif')
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2020, mois=1,
            statut=PeriodePaie.STATUT_BROUILLON)

    def test_notifie_une_fois(self):
        notifiees = notifier_cloture_en_retard(self.co)
        self.assertEqual(len(notifiees), 1)
        self.periode.refresh_from_db()
        self.assertIsNotNone(self.periode.date_alerte_cloture_retard)

    def test_idempotent_pas_de_re_notification(self):
        notifier_cloture_en_retard(self.co)
        self.periode.refresh_from_db()
        premiere = self.periode.date_alerte_cloture_retard
        notifier_cloture_en_retard(self.co)
        self.periode.refresh_from_db()
        self.assertEqual(self.periode.date_alerte_cloture_retard, premiere)

    def test_isolation_tenant(self):
        autre_co = make_company('cloture-retard-autre')
        autre_periode = PeriodePaie.objects.create(
            company=autre_co, annee=2020, mois=1,
            statut=PeriodePaie.STATUT_BROUILLON)
        notifier_cloture_en_retard(self.co)
        autre_periode.refresh_from_db()
        self.assertIsNone(autre_periode.date_alerte_cloture_retard)


class BeatTaskWiringTests(TestCase):
    def setUp(self):
        self.co = make_company('cloture-retard-beat')
        PeriodePaie.objects.create(
            company=self.co, annee=2020, mois=1,
            statut=PeriodePaie.STATUT_BROUILLON)

    def test_trigger_delegue_au_service_paie(self):
        from apps.automation.beat_tasks import _trigger_paie_cloture_retard

        count = _trigger_paie_cloture_retard(self.co)
        self.assertEqual(count, 1)
