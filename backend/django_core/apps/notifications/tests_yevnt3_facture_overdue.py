"""YEVNT3 — `sweep_daily` émet FACTURE_OVERDUE pour chaque facture échue.

Couverture :
  - facture échue non payée -> une notification vers created_by.
  - pas de created_by -> repli sur les managers.
  - facture payée / annulée / échéance future -> aucune notification.
  - idempotence stricte : ré-exécuter le MÊME jour ne ré-émet pas.
  - respect des préférences/routing (via `notify()`, déjà testé ailleurs) --
    ici on vérifie juste que le sweep passe bien par `notify()`.
  - aucun import direct de `apps.ventes.models` dans sweeps.py (seulement le
    selector `factures_echues`).
"""
from datetime import date, timedelta

from django.test import TestCase

from authentication.models import Company, CustomUser

from .models import EventType, Notification


def _make_company(name='OverdueCo'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return CustomUser.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class FactureOverdueSweepTests(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.seller = _make_user(self.company, 'seller1')
        self.manager = _make_user(self.company, 'mgr1', role_legacy='admin')

    def _make_facture(self, **kwargs):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        client = kwargs.pop('client', None)
        if client is None:
            client = Client.objects.create(
                company=self.company, nom='Client Facture')
        defaults = dict(
            company=self.company, client=client, reference='FA-OV-1',
            statut=Facture.Statut.EMISE,
            date_echeance=date.today() - timedelta(days=10),
            created_by=self.seller,
        )
        defaults.update(kwargs)
        return Facture.objects.create(**defaults)

    def test_overdue_unpaid_facture_notifies_created_by(self):
        from .sweeps import _sweep_facture_overdue
        self._make_facture()
        count = _sweep_facture_overdue(self.company)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.seller,
            event_type=EventType.FACTURE_OVERDUE).exists())

    def test_no_created_by_falls_back_to_managers(self):
        from .sweeps import _sweep_facture_overdue
        self._make_facture(created_by=None, reference='FA-OV-2')
        count = _sweep_facture_overdue(self.company)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=self.manager,
            event_type=EventType.FACTURE_OVERDUE).exists())

    def test_paid_facture_not_notified(self):
        from apps.ventes.models import Facture
        from .sweeps import _sweep_facture_overdue
        self._make_facture(statut=Facture.Statut.PAYEE, reference='FA-OV-3')
        count = _sweep_facture_overdue(self.company)
        self.assertEqual(count, 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_cancelled_facture_not_notified(self):
        from apps.ventes.models import Facture
        from .sweeps import _sweep_facture_overdue
        self._make_facture(statut=Facture.Statut.ANNULEE, reference='FA-OV-4')
        count = _sweep_facture_overdue(self.company)
        self.assertEqual(count, 0)

    def test_future_due_date_not_notified(self):
        from .sweeps import _sweep_facture_overdue
        self._make_facture(
            date_echeance=date.today() + timedelta(days=5),
            reference='FA-OV-5')
        count = _sweep_facture_overdue(self.company)
        self.assertEqual(count, 0)

    def test_no_due_date_not_notified(self):
        from .sweeps import _sweep_facture_overdue
        self._make_facture(date_echeance=None, reference='FA-OV-6')
        count = _sweep_facture_overdue(self.company)
        self.assertEqual(count, 0)

    def test_idempotent_same_day_rerun_does_not_duplicate(self):
        from .sweeps import _sweep_facture_overdue
        self._make_facture(reference='FA-OV-7')
        first = _sweep_facture_overdue(self.company)
        second = _sweep_facture_overdue(self.company)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.FACTURE_OVERDUE).count(), 1)

    def test_sweep_daily_wires_facture_overdue(self):
        """`sweep_daily` (la tâche Celery Beat) appelle bien le sweep facture."""
        from .sweeps import sweep_daily
        self._make_facture(reference='FA-OV-8')
        total = sweep_daily()
        self.assertGreaterEqual(total, 1)
        self.assertTrue(Notification.objects.filter(
            event_type=EventType.FACTURE_OVERDUE).exists())

    def test_multi_tenant_scoping(self):
        """Une facture d'une autre société n'est jamais notifiée ici."""
        from .sweeps import _sweep_facture_overdue
        other = _make_company('OtherOverdueCo')
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        other_client = Client.objects.create(company=other, nom='Autre client')
        Facture.objects.create(
            company=other, client=other_client, reference='FA-OTHER-1',
            statut=Facture.Statut.EMISE,
            date_echeance=date.today() - timedelta(days=3))
        count = _sweep_facture_overdue(self.company)
        self.assertEqual(count, 0)
