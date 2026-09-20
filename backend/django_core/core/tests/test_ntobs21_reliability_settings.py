"""Tests NTOBS21 — réglages de fiabilité par société (schéma).

Ce que le modèle doit garantir au lecteur (``core/usage_limits.py``, qui lit
ces réglages défensivement) : des DÉFAUTS égaux au comportement actuel, UNE
seule ligne par société, et un filtre de région vide qui veut dire « toutes ».
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company

from core.models import ReliabilitySettings


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ReliabilitySettingsTests(TestCase):

    def setUp(self):
        self.company = make_company('ntobs21-co', 'NTOBS21 Co')

    def test_defauts_egaux_au_comportement_actuel(self):
        reglages = ReliabilitySettings.objects.create(company=self.company)

        self.assertTrue(reglages.notifier_maintenance_email)
        self.assertTrue(reglages.notifier_quota_email)
        self.assertTrue(reglages.afficher_badge_sla_dashboard)
        self.assertEqual(reglages.notifier_incident_region, '')
        self.assertIsNotNone(reglages.created_at)
        self.assertIsNotNone(reglages.updated_at)

    def test_une_seule_ligne_par_societe(self):
        ReliabilitySettings.objects.create(company=self.company)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReliabilitySettings.objects.create(company=self.company)

    def test_accesseur_inverse_nomme(self):
        reglages = ReliabilitySettings.objects.create(company=self.company)
        self.company.refresh_from_db()
        self.assertEqual(self.company.reliability_settings.pk, reglages.pk)

    def test_region_est_un_filtre_optionnel(self):
        reglages = ReliabilitySettings.objects.create(
            company=self.company, notifier_incident_region='eu-west')
        self.assertEqual(reglages.notifier_incident_region, 'eu-west')

        reglages.notifier_incident_region = ''
        reglages.save(update_fields=['notifier_incident_region', 'updated_at'])
        reglages.refresh_from_db()
        self.assertEqual(reglages.notifier_incident_region, '')

    def test_scope_par_societe(self):
        voisine = make_company('ntobs21-voisine', 'NTOBS21 Voisine')
        ReliabilitySettings.objects.create(
            company=self.company, notifier_quota_email=False)
        ReliabilitySettings.objects.create(company=voisine)

        self.assertFalse(
            ReliabilitySettings.objects.get(
                company=self.company).notifier_quota_email)
        self.assertTrue(
            ReliabilitySettings.objects.get(
                company=voisine).notifier_quota_email)
