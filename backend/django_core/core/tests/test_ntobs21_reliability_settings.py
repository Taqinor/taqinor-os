"""Tests NTOBS21 — réglages de fiabilité par société (schéma).

Ce que le modèle doit garantir au lecteur (``core/usage_limits.py``, qui lit
ces réglages défensivement) : des DÉFAUTS égaux au comportement actuel, UNE
seule ligne par société, et un filtre de région vide qui veut dire « toutes ».
"""
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from core.maintenance_windows import MaintenanceWindow, notifier_fenetres_a_venir
from core.models import ReliabilitySettings

URL = '/api/django/core/fiabilite/reglages/'


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


class ReliabilitySettingsApiTests(TestCase):
    """NTOBS21 — GET/PATCH ``fiabilite/reglages/`` : singleton par société,
    lecture ``fiabilite_voir``, écriture ``fiabilite_administration``."""

    def setUp(self):
        Role = django_apps.get_model('roles', 'Role')
        User = get_user_model()
        self.company = make_company('ntobs21-api', 'NTOBS21 Api')
        self.voisine = make_company('ntobs21-api-v', 'NTOBS21 Api V')
        self.directeur = User.objects.create_user(
            'ntobs21dir', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Directeur'))
        self.lecteur = User.objects.create_user(
            'ntobs21voir', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Lecture Fiab',
                permissions=['fiabilite_voir']))
        self.sans_droit = User.objects.create_user(
            'ntobs21aucun', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Sans droit', permissions=[]))

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_get_cree_les_defauts_a_la_premiere_lecture(self):
        resp = self._client(self.directeur).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['notifier_quota_email'], True)
        self.assertEqual(resp.data['notifier_maintenance_email'], True)
        self.assertEqual(resp.data['afficher_badge_sla_dashboard'], True)
        self.assertEqual(resp.data['notifier_incident_region'], '')
        self.assertNotIn('company', resp.data)
        self.assertTrue(ReliabilitySettings.objects.filter(
            company=self.company).exists())

    def test_patch_borne_a_la_societe_de_l_appelant(self):
        resp = self._client(self.directeur).patch(
            URL, {'notifier_quota_email': False,
                  'notifier_incident_region': '  Casablanca ',
                  'company': self.voisine.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        reglages = ReliabilitySettings.objects.get(company=self.company)
        self.assertFalse(reglages.notifier_quota_email)
        self.assertEqual(reglages.notifier_incident_region, 'Casablanca')
        self.assertFalse(ReliabilitySettings.objects.filter(
            company=self.voisine).exists())

    def test_booleen_strict(self):
        resp = self._client(self.directeur).patch(
            URL, {'notifier_quota_email': 0}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_put_refuse(self):
        resp = self._client(self.directeur).put(URL, {}, format='json')
        self.assertEqual(resp.status_code, 405)

    def test_lecteur_lit_mais_n_ecrit_pas(self):
        client = self._client(self.lecteur)
        self.assertEqual(client.get(URL).status_code, 200)
        resp = client.patch(URL, {'notifier_quota_email': False}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_sans_droit_refuse(self):
        self.assertEqual(self._client(self.sans_droit).get(URL).status_code, 403)


class ReliabilitySettingsMaintenanceTests(TestCase):
    """NTOBS21 x NTOBS9 — l'annonce de fenêtre de maintenance respecte
    ``notifier_maintenance_email`` et la région suivie, société par société."""

    def setUp(self):
        Role = django_apps.get_model('roles', 'Role')
        User = get_user_model()
        self.a = make_company('ntobs21-mw-a', 'MW A')
        self.b = make_company('ntobs21-mw-b', 'MW B')
        for company, nom in ((self.a, 'mwdira'), (self.b, 'mwdirb')):
            User.objects.create_user(
                nom, password='x', company=company,
                role=Role.objects.create(company=company, nom='Directeur'))

    def _annoncer(self, company=None, region=''):
        now = timezone.now()
        MaintenanceWindow.objects.create(
            company=company, region=region,
            debute_le=now + timezone.timedelta(hours=23),
            termine_le=now + timezone.timedelta(hours=24))
        with mock.patch('core.notify_registry.notify') as notify_mock:
            notifier_fenetres_a_venir(now=now)
        return sorted(c.kwargs['company'].pk for c in notify_mock.call_args_list)

    def test_desactiver_coupe_seulement_cette_societe(self):
        ReliabilitySettings.objects.create(
            company=self.a, notifier_maintenance_email=False)
        destinataires = self._annoncer(company=None)
        self.assertNotIn(self.a.pk, destinataires)
        self.assertIn(self.b.pk, destinataires)

    def test_region_suivie_ecarte_une_autre_region(self):
        ReliabilitySettings.objects.create(
            company=self.a, notifier_incident_region='Casablanca')
        self.assertNotIn(self.a.pk, self._annoncer(region='Rabat'))
        self.assertIn(self.a.pk, self._annoncer(region='casablanca'))
        self.assertIn(self.a.pk, self._annoncer(region=''))
