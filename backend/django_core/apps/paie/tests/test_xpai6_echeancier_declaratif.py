"""Tests XPAI6 — Échéancier déclaratif paie.

Couvre : ``generer_echeances_periode`` crée le calendrier (BDS/IR mensuel/
CIMR/9421 en décembre uniquement) de façon idempotente, la clôture avance les
échéances ``a_generer`` -> ``generee``, ``notifier_echeances_en_retard``
notifie une fois une échéance dépassée non déposée (idempotence), et
l'isolation tenant.
"""
from datetime import date, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.paie.models import EcheanceDeclarative, PeriodePaie
from apps.paie.services import (
    cloturer_periode_paie,
    echeances_attendues,
    ensure_defaults,
    generer_echeances_periode,
    notifier_echeances_en_retard,
)


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class EcheancesAttenduesTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai6-attendues')

    def test_mois_normal_trois_types(self):
        periode = PeriodePaie.objects.create(company=self.co, annee=2026, mois=6)
        echeances = echeances_attendues(periode)
        types = {t for t, _d in echeances}
        self.assertEqual(types, {'bds', 'ir_mensuel', 'cimr'})

    def test_decembre_ajoute_9421(self):
        periode = PeriodePaie.objects.create(company=self.co, annee=2026, mois=12)
        echeances = echeances_attendues(periode)
        types = {t for t, _d in echeances}
        self.assertIn('etat_9421', types)
        date_9421 = next(d for t, d in echeances if t == 'etat_9421')
        self.assertEqual(date_9421, date(2027, 2, 28))

    def test_dates_limites_mois_suivant(self):
        periode = PeriodePaie.objects.create(company=self.co, annee=2026, mois=6)
        echeances = dict(echeances_attendues(periode))
        self.assertEqual(echeances['bds'], date(2026, 7, 10))
        self.assertEqual(echeances['ir_mensuel'], date(2026, 7, 20))
        self.assertEqual(echeances['cimr'], date(2026, 7, 10))


class GenererEcheancesPeriodeTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai6-gen')
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_cree_echeances(self):
        creees = generer_echeances_periode(self.periode)
        self.assertEqual(len(creees), 3)
        self.assertEqual(
            EcheanceDeclarative.objects.filter(periode=self.periode).count(), 3)

    def test_idempotent(self):
        generer_echeances_periode(self.periode)
        creees_2 = generer_echeances_periode(self.periode)
        self.assertEqual(len(creees_2), 0)
        self.assertEqual(
            EcheanceDeclarative.objects.filter(periode=self.periode).count(), 3)

    def test_ne_touche_pas_statut_existant(self):
        generer_echeances_periode(self.periode)
        echeance = EcheanceDeclarative.objects.filter(
            periode=self.periode, type_echeance='bds').first()
        echeance.statut = EcheanceDeclarative.STATUT_DEPOSEE
        echeance.save()
        generer_echeances_periode(self.periode)
        echeance.refresh_from_db()
        self.assertEqual(echeance.statut, EcheanceDeclarative.STATUT_DEPOSEE)


class ClotureAvanceEcheancesTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai6-cloture')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        generer_echeances_periode(self.periode)

    def test_cloture_avance_a_generee(self):
        cloturer_periode_paie(self.periode)
        statuts = set(
            EcheanceDeclarative.objects.filter(
                periode=self.periode).values_list('statut', flat=True))
        self.assertEqual(statuts, {EcheanceDeclarative.STATUT_GENEREE})

    def test_ne_retrograde_jamais_une_echeance_deposee(self):
        echeance = EcheanceDeclarative.objects.filter(
            periode=self.periode, type_echeance='bds').first()
        echeance.statut = EcheanceDeclarative.STATUT_DEPOSEE
        echeance.save()
        cloturer_periode_paie(self.periode)
        echeance.refresh_from_db()
        self.assertEqual(echeance.statut, EcheanceDeclarative.STATUT_DEPOSEE)


class NotifierEcheancesEnRetardTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai6-notif')
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2020, mois=1)

    def test_echeance_en_retard_notifiee_une_fois(self):
        hier = timezone.localdate() - timedelta(days=1)
        echeance = EcheanceDeclarative.objects.create(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS, date_limite=hier)
        with mock.patch(
                'apps.notifications.services.resolve_recipients',
                return_value=[]):
            notifiees = notifier_echeances_en_retard(self.co)
        self.assertEqual(len(notifiees), 1)
        echeance.refresh_from_db()
        self.assertIsNotNone(echeance.date_notification)

        # Re-run : déjà notifiée, ne renotifie pas.
        with mock.patch(
                'apps.notifications.services.resolve_recipients',
                return_value=[]) as resolve_mock:
            notifiees_2 = notifier_echeances_en_retard(self.co)
        self.assertEqual(len(notifiees_2), 0)
        resolve_mock.assert_not_called()

    def test_echeance_deposee_pas_de_retard(self):
        hier = timezone.localdate() - timedelta(days=1)
        EcheanceDeclarative.objects.create(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS, date_limite=hier,
            statut=EcheanceDeclarative.STATUT_DEPOSEE)
        notifiees = notifier_echeances_en_retard(self.co)
        self.assertEqual(len(notifiees), 0)

    def test_echeance_future_pas_de_retard(self):
        demain = timezone.localdate() + timedelta(days=1)
        EcheanceDeclarative.objects.create(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS, date_limite=demain)
        notifiees = notifier_echeances_en_retard(self.co)
        self.assertEqual(len(notifiees), 0)

    def test_isolation_tenant(self):
        autre = make_company('xpai6-notif-autre')
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2020, mois=1)
        hier = timezone.localdate() - timedelta(days=1)
        EcheanceDeclarative.objects.create(
            company=autre, periode=periode_autre,
            type_echeance=EcheanceDeclarative.TYPE_BDS, date_limite=hier)
        notifiees = notifier_echeances_en_retard(self.co)
        self.assertEqual(len(notifiees), 0)
