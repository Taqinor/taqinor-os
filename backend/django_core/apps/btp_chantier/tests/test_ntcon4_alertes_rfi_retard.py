"""Tests NTCON4 — Alerte RFI en retard (sweep quotidien, idempotent)."""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.btp_chantier.models import RFI
from apps.notifications.models import Notification

from .helpers import make_chantier, make_company, make_user


class AlertesRfiRetardTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.pose_par = make_user(self.co, username='pose-par')
        self.destinataire = make_user(self.co, username='destinataire')
        self.chantier = make_chantier(self.co)
        self.hier = timezone.localdate() - timedelta(days=1)

    def _run(self):
        out = StringIO()
        call_command('alertes_rfi_retard', stdout=out)
        return out.getvalue()

    def test_sweep_notifies_destinataire_and_createur(self):
        rfi = RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1,
            question='Q', pose_par=self.pose_par,
            destinataire_user=self.destinataire,
            date_limite_reponse=self.hier)
        self._run()
        rfi.refresh_from_db()
        self.assertEqual(rfi.derniere_alerte_retard, timezone.localdate())
        self.assertTrue(
            Notification.objects.filter(user=self.pose_par).exists())
        self.assertTrue(
            Notification.objects.filter(user=self.destinataire).exists())

    def test_sweep_idempotent_same_day(self):
        RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1,
            question='Q', pose_par=self.pose_par,
            date_limite_reponse=self.hier)
        self._run()
        count_after_first = Notification.objects.filter(
            user=self.pose_par).count()
        self._run()
        count_after_second = Notification.objects.filter(
            user=self.pose_par).count()
        self.assertEqual(count_after_first, count_after_second)

    def test_rfi_repondu_ou_clos_exclus(self):
        RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1,
            question='Q', pose_par=self.pose_par,
            date_limite_reponse=self.hier, statut=RFI.Statut.REPONDU)
        RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=2,
            question='Q2', pose_par=self.pose_par,
            date_limite_reponse=self.hier, statut=RFI.Statut.CLOS)
        self._run()
        self.assertFalse(
            Notification.objects.filter(user=self.pose_par).exists())

    def test_rfi_dans_les_temps_exclu(self):
        demain = timezone.localdate() + timedelta(days=2)
        RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1,
            question='Q', pose_par=self.pose_par, date_limite_reponse=demain)
        self._run()
        self.assertFalse(
            Notification.objects.filter(user=self.pose_par).exists())
