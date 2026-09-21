"""Tests XFSM24 — Check-in travailleur isolé avec escalade.

Couvre :

* le cycle check-in / check-out ;
* la détection de dépassement (``en_retard``) ;
* l'escalade idempotente (jamais deux fois pour le même check-in) ;
* le scoping société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.qhse.models import CheckinSecurite
from apps.qhse.services import escalader_checkins_en_retard

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='technicien'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class EnRetardTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xfsm24-retard', 'CoXfsm24Retard')
        self.tech = make_user(self.company, 'tech-xfsm24-retard')

    def test_pas_en_retard_si_checkout_reel(self):
        now = timezone.now()
        checkin = CheckinSecurite.objects.create(
            company=self.company, technicien=self.tech,
            heure_checkout_prevue=now - timedelta(hours=1),
            heure_checkout_reelle=now)
        self.assertFalse(checkin.en_retard(now=now))

    def test_pas_en_retard_avant_delai(self):
        now = timezone.now()
        checkin = CheckinSecurite.objects.create(
            company=self.company, technicien=self.tech,
            heure_checkout_prevue=now - timedelta(minutes=10),
            delai_escalade_min=30)
        self.assertFalse(checkin.en_retard(now=now))

    def test_en_retard_apres_delai(self):
        now = timezone.now()
        checkin = CheckinSecurite.objects.create(
            company=self.company, technicien=self.tech,
            heure_checkout_prevue=now - timedelta(minutes=45),
            delai_escalade_min=30)
        self.assertTrue(checkin.en_retard(now=now))

    def test_pas_en_retard_sans_heure_prevue(self):
        checkin = CheckinSecurite.objects.create(
            company=self.company, technicien=self.tech)
        self.assertFalse(checkin.en_retard())


class EscaladerCheckinsEnRetardTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xfsm24-esc', 'CoXfsm24Esc')
        self.tech = make_user(self.company, 'tech-xfsm24-esc')

    def test_escalade_checkin_en_retard(self):
        now = timezone.now()
        checkin = CheckinSecurite.objects.create(
            company=self.company, technicien=self.tech,
            heure_checkout_prevue=now - timedelta(minutes=45),
            delai_escalade_min=30)
        escalades = escalader_checkins_en_retard(company=self.company, now=now)
        self.assertEqual(len(escalades), 1)
        checkin.refresh_from_db()
        self.assertTrue(checkin.escalade_declenchee)
        self.assertIsNotNone(checkin.escalade_le)

    def test_escalade_idempotente(self):
        now = timezone.now()
        CheckinSecurite.objects.create(
            company=self.company, technicien=self.tech,
            heure_checkout_prevue=now - timedelta(minutes=45),
            delai_escalade_min=30)
        escalader_checkins_en_retard(company=self.company, now=now)
        # Deuxième passage plus tard : aucune nouvelle escalade.
        second = escalader_checkins_en_retard(
            company=self.company, now=now + timedelta(hours=1))
        self.assertEqual(len(second), 0)

    def test_pas_escalade_si_checkout_a_temps(self):
        now = timezone.now()
        checkin = CheckinSecurite.objects.create(
            company=self.company, technicien=self.tech,
            heure_checkout_prevue=now - timedelta(minutes=45),
            heure_checkout_reelle=now - timedelta(minutes=40),
            delai_escalade_min=30)
        escalades = escalader_checkins_en_retard(company=self.company, now=now)
        self.assertEqual(len(escalades), 0)
        checkin.refresh_from_db()
        self.assertFalse(checkin.escalade_declenchee)

    def test_isolation_societe(self):
        autre = make_company('co-xfsm24-esc-autre', 'CoXfsm24EscAutre')
        now = timezone.now()
        CheckinSecurite.objects.create(
            company=self.company, technicien=self.tech,
            heure_checkout_prevue=now - timedelta(minutes=45),
            delai_escalade_min=30)
        escalades = escalader_checkins_en_retard(company=autre, now=now)
        self.assertEqual(len(escalades), 0)
