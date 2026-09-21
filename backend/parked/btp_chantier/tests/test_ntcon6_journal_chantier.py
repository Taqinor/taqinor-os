"""Tests NTCON6 — Journal de chantier quotidien.

Couvre :
* création d'une entrée + posée côté serveur (redacteur/company) ;
* contrainte unique (une entrée par jour par chantier) → 400 sur doublon ;
* filtres ``?chantier=&du=&au=`` ;
* export PDF sur une période (contenu-type application/pdf) ;
* cross-tenant refusé.
"""
from datetime import date, timedelta

from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import JournalChantier

from .helpers import auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/journal-chantier/'


class JournalChantierApiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

    def test_create_entry(self):
        api = auth(self.user)
        resp = api.post(BASE, {
            'chantier': self.chantier.id,
            'date': str(date.today()),
            'meteo': 'ensoleille',
            'effectif_interne': {'macon': 4, 'electricien': 2},
            'materiel_present': 'Grue mobile',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        entry = JournalChantier.objects.get(pk=resp.data['id'])
        self.assertEqual(entry.company_id, self.co.id)
        self.assertEqual(entry.redacteur_id, self.user.id)

    def test_duplicate_same_day_rejected(self):
        JournalChantier.objects.create(
            company=self.co, chantier=self.chantier, date=date.today(),
            redacteur=self.user)
        api = auth(self.user)
        resp = api.post(BASE, {
            'chantier': self.chantier.id, 'date': str(date.today()),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_chantier_and_period(self):
        d1 = date.today() - timedelta(days=10)
        d2 = date.today() - timedelta(days=1)
        j1 = JournalChantier.objects.create(
            company=self.co, chantier=self.chantier, date=d1,
            redacteur=self.user)
        j2 = JournalChantier.objects.create(
            company=self.co, chantier=self.chantier, date=d2,
            redacteur=self.user)

        api = auth(self.user)
        resp = api.get(BASE, {
            'chantier': self.chantier.id,
            'du': str(date.today() - timedelta(days=5)),
        })
        ids = [row['id'] for row in resp.data['results']] \
            if 'results' in resp.data else [row['id'] for row in resp.data]
        self.assertIn(j2.id, ids)
        self.assertNotIn(j1.id, ids)

    def test_export_pdf_over_period(self):
        JournalChantier.objects.create(
            company=self.co, chantier=self.chantier,
            date=date.today() - timedelta(days=2), redacteur=self.user,
            meteo='ensoleille', effectif_interne={'macon': 3})
        api = auth(self.user)
        resp = api.get(f'{BASE}export-pdf/', {
            'chantier': self.chantier.id,
            'du': str(date.today() - timedelta(days=7)),
            'au': str(date.today()),
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertGreater(len(resp.content), 0)

    def test_export_pdf_without_chantier_400(self):
        api = auth(self.user)
        resp = api.get(f'{BASE}export-pdf/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_tenant_refused(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        other_entry = JournalChantier.objects.create(
            company=other_co, chantier=other_chantier, date=date.today())
        api = auth(self.user)
        resp = api.get(f'{BASE}{other_entry.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        resp = api.get(f'{BASE}export-pdf/', {'chantier': other_chantier.id})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class JournalChantierPlatformTests(TestCase):
    def test_registered_as_record_target(self):
        from apps.records.models import ALLOWED_TARGETS
        self.assertIn(('btp_chantier', 'journalchantier'), ALLOWED_TARGETS)
