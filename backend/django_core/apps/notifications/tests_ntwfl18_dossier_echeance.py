"""NTWFL18 — DOSSIERS-NOTIF : ``apps.notifications`` s'abonne à
``core.events.dossier_echeance_depassee`` (émis par le balayage quotidien
``core.dossiers.notifier_echeances_depassees``) et notifie le propriétaire
du dossier en retard."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.models import EventType, Notification
from authentication.models import Company
from core.models import Dossier

User = get_user_model()


class DossierEcheanceDepasseeNotifTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            slug='ntwfl18-co', nom='NTWFL18 Co')
        self.proprietaire = User.objects.create_user(
            username='ntwfl18_owner', password='x', company=self.company)

    def test_dossier_en_retard_notifie_le_proprietaire(self):
        hier = date.today() - timedelta(days=1)
        dossier = Dossier.objects.create(
            company=self.company, titre='Litige Bennani',
            proprietaire=self.proprietaire, echeance=hier)

        from core import dossiers

        alertes = dossiers.notifier_echeances_depassees(
            self.company, date.today())

        self.assertEqual(len(alertes), 1)
        notif = Notification.objects.get(
            recipient=self.proprietaire,
            event_type=EventType.DOSSIER_ECHEANCE_DEPASSEE)
        self.assertIn('Litige Bennani', notif.body)
        dossier.refresh_from_db()
        self.assertEqual(dossier.dernier_rappel_echeance_le, date.today())

    def test_rejoue_le_meme_jour_ne_renotifie_pas(self):
        hier = date.today() - timedelta(days=1)
        Dossier.objects.create(
            company=self.company, titre='Onboarding X',
            proprietaire=self.proprietaire, echeance=hier)

        from core import dossiers

        dossiers.notifier_echeances_depassees(self.company, date.today())
        Notification.objects.all().delete()
        alertes = dossiers.notifier_echeances_depassees(
            self.company, date.today())

        self.assertEqual(alertes, [])
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.DOSSIER_ECHEANCE_DEPASSEE).count(), 0)

    def test_dossier_sans_proprietaire_n_emet_aucune_notification(self):
        hier = date.today() - timedelta(days=1)
        from core import dossiers

        Dossier.objects.create(
            company=self.company, titre='Sans owner', echeance=hier)

        dossiers.notifier_echeances_depassees(self.company, date.today())

        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.DOSSIER_ECHEANCE_DEPASSEE).count(), 0)
