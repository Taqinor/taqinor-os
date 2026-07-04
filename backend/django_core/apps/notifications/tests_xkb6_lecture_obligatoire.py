"""XKB6 — Accusé de lecture obligatoire des annonces + rapport de conformité.

Couverture :
  - `acknowledge_annonce` crée un accusé idempotent (un clic ou dix, une
    ligne).
  - `annonce_compliance_report` liste lus/manquants correctement, et renvoie
    des listes vides pour une annonce non `lecture_obligatoire` ou non
    publiée.
  - `sweep_annonce_reminders` relance les non-lecteurs au-delà du seuil,
    jamais un lecteur, jamais deux fois le même jour.
  - endpoints API : accuser-lecture (tout rôle), conformite (admin).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from .models import Annonce, AnnonceLecture, AnnonceRelance, EventType, Notification

User = get_user_model()


def _make_company(name='LectureCo'):
    return Company.objects.create(nom=name)


def _make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class AcknowledgeAnnonceTests(TestCase):

    def setUp(self):
        self.company = _make_company()
        self.user = _make_user(self.company, 'reader1')
        self.annonce = Annonce.objects.create(
            company=self.company, titre='Règlement intérieur',
            lecture_obligatoire=True, publiee=True,
            date_publication_effective=timezone.now())

    def test_acknowledge_creates_lecture(self):
        from .services import acknowledge_annonce
        lecture = acknowledge_annonce(self.annonce, self.user)
        self.assertIsNotNone(lecture)
        self.assertEqual(
            AnnonceLecture.objects.filter(
                annonce=self.annonce, utilisateur=self.user).count(), 1)

    def test_acknowledge_is_idempotent(self):
        from .services import acknowledge_annonce
        acknowledge_annonce(self.annonce, self.user)
        acknowledge_annonce(self.annonce, self.user)
        acknowledge_annonce(self.annonce, self.user)
        self.assertEqual(
            AnnonceLecture.objects.filter(
                annonce=self.annonce, utilisateur=self.user).count(), 1)


class ComplianceReportTests(TestCase):

    def setUp(self):
        self.company = _make_company('ComplianceCo')

    def test_report_lists_read_and_missing(self):
        from .services import acknowledge_annonce, annonce_compliance_report
        u1 = _make_user(self.company, 'c1')
        u2 = _make_user(self.company, 'c2')
        annonce = Annonce.objects.create(
            company=self.company, titre='Consignes QHSE',
            lecture_obligatoire=True, publiee=True,
            date_publication_effective=timezone.now())
        acknowledge_annonce(annonce, u1)

        report = annonce_compliance_report(annonce)
        self.assertEqual(report['total_cibles'], 2)
        self.assertEqual(len(report['lus']), 1)
        self.assertEqual(report['lus'][0]['user_id'], u1.pk)
        self.assertEqual(len(report['manquants']), 1)
        self.assertEqual(report['manquants'][0]['user_id'], u2.pk)

    def test_report_empty_when_not_lecture_obligatoire(self):
        from .services import annonce_compliance_report
        _make_user(self.company, 'c3')
        annonce = Annonce.objects.create(
            company=self.company, titre='Info simple',
            lecture_obligatoire=False, publiee=True,
            date_publication_effective=timezone.now())
        report = annonce_compliance_report(annonce)
        self.assertEqual(report, {'lus': [], 'manquants': [], 'total_cibles': 0})

    def test_report_empty_when_not_published(self):
        from .services import annonce_compliance_report
        annonce = Annonce.objects.create(
            company=self.company, titre='Pas encore publiée',
            lecture_obligatoire=True, publiee=False)
        report = annonce_compliance_report(annonce)
        self.assertEqual(report['total_cibles'], 0)


class ReminderSweepTests(TestCase):

    def setUp(self):
        self.company = _make_company('ReminderCo')

    def test_no_reminder_before_delay_elapsed(self):
        from .services import sweep_annonce_reminders
        _make_user(self.company, 'r1')
        Annonce.objects.create(
            company=self.company, titre='Fraîche', lecture_obligatoire=True,
            publiee=True, date_publication_effective=timezone.now())
        count = sweep_annonce_reminders(self.company, delay_days=2)
        self.assertEqual(count, 0)

    def test_reminder_sent_to_non_readers_only(self):
        from .services import acknowledge_annonce, sweep_annonce_reminders
        reader = _make_user(self.company, 'reader_r')
        non_reader = _make_user(self.company, 'nonreader_r')
        old_pub = timezone.now() - timedelta(days=10)
        annonce = Annonce.objects.create(
            company=self.company, titre='En retard', lecture_obligatoire=True,
            publiee=True, date_publication_effective=old_pub)
        acknowledge_annonce(annonce, reader)

        count = sweep_annonce_reminders(self.company, delay_days=2)
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(
            recipient=non_reader,
            event_type=EventType.ANNONCE_READ_REMINDER).exists())
        self.assertFalse(Notification.objects.filter(
            recipient=reader,
            event_type=EventType.ANNONCE_READ_REMINDER).exists())

    def test_reminder_idempotent_same_day(self):
        from .services import sweep_annonce_reminders
        _make_user(self.company, 'idem_r')
        old_pub = timezone.now() - timedelta(days=10)
        Annonce.objects.create(
            company=self.company, titre='En retard idem',
            lecture_obligatoire=True, publiee=True,
            date_publication_effective=old_pub)

        first = sweep_annonce_reminders(self.company, delay_days=2)
        second = sweep_annonce_reminders(self.company, delay_days=2)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(AnnonceRelance.objects.count(), 1)
        self.assertEqual(AnnonceRelance.objects.first().relances_envoyees, 1)

    def test_reminder_never_creates_fake_lecture_row(self):
        """Une relance ne doit JAMAIS créer une AnnonceLecture (sémantique
        « lu » réservée aux vraies confirmations)."""
        from .services import sweep_annonce_reminders
        _make_user(self.company, 'noleak_r')
        old_pub = timezone.now() - timedelta(days=10)
        annonce = Annonce.objects.create(
            company=self.company, titre='Sans fuite', lecture_obligatoire=True,
            publiee=True, date_publication_effective=old_pub)
        sweep_annonce_reminders(self.company, delay_days=2)
        self.assertEqual(
            AnnonceLecture.objects.filter(annonce=annonce).count(), 0)


class AnnonceReadApiTests(TestCase):

    def setUp(self):
        self.company = _make_company('ApiLectureCo')
        self.admin = _make_user(self.company, 'lecture_admin', role_legacy='admin')
        self.normal = _make_user(self.company, 'lecture_normal')

    def test_accuser_lecture_available_to_any_role(self):
        from rest_framework.test import APIClient
        annonce = Annonce.objects.create(
            company=self.company, titre='À confirmer', lecture_obligatoire=True,
            publiee=True, date_publication_effective=timezone.now())
        client = APIClient()
        client.force_authenticate(self.normal)
        resp = client.post(
            f'/api/django/notifications/annonces/{annonce.pk}/accuser-lecture/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            AnnonceLecture.objects.filter(
                annonce=annonce, utilisateur=self.normal).exists())

    def test_conformite_report_requires_admin(self):
        from rest_framework.test import APIClient
        annonce = Annonce.objects.create(
            company=self.company, titre='Rapport', lecture_obligatoire=True,
            publiee=True, date_publication_effective=timezone.now())
        client = APIClient()
        client.force_authenticate(self.normal)
        resp = client.get(
            f'/api/django/notifications/annonces/{annonce.pk}/conformite/')
        self.assertEqual(resp.status_code, 403)

        client.force_authenticate(self.admin)
        resp = client.get(
            f'/api/django/notifications/annonces/{annonce.pk}/conformite/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('lus', resp.data)
        self.assertIn('manquants', resp.data)
