"""ALEA29 — un PATCH lead sans changement réel n'avance ni
``date_modification`` ni ``updated_by`` (C-ALEA-017, sonde V3 LFICHE-4e).

Aucun mock : ``perform_update`` et ``_save_borne_aux_champs`` réels.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead

User = get_user_model()


class PatchSansChangementTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA29', slug='taqinor-alea29')
        self.u1 = User.objects.create_user(
            username='alea29-u1', password='x', company=self.company,
            role_legacy='admin')
        self.u2 = User.objects.create_user(
            username='alea29-u2', password='x', company=self.company,
            role_legacy='admin')
        self.lead = Lead.objects.create(
            company=self.company, nom='Stable', prenom='Lead',
            telephone='+212661290001', ville='Casablanca')
        self.t0 = timezone.now() - datetime.timedelta(days=2)
        Lead.objects.filter(pk=self.lead.pk).update(
            date_modification=self.t0, updated_by=self.u1)
        self.api = APIClient()
        self.api.force_authenticate(self.u2)
        self.url = f'/api/django/crm/leads/{self.lead.pk}/'

    def _etat(self):
        self.lead.refresh_from_db()
        return self.lead.date_modification, self.lead.updated_by_id

    def _assert_get_identique(self, avant):
        apres = self.api.get(self.url).json()
        self.assertEqual(apres['date_modification'],
                         avant['date_modification'])
        self.assertEqual(apres.get('updated_by_nom'),
                         avant.get('updated_by_nom'))

    def test_corps_vide_n_avance_pas(self):
        avant = self.api.get(self.url).json()
        r = self.api.patch(self.url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._etat(), (self.t0, self.u1.pk))
        self._assert_get_identique(avant)

    def test_valeur_identique_n_avance_pas(self):
        avant = self.api.get(self.url).json()
        r = self.api.patch(self.url, {'ville': 'Casablanca'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._etat(), (self.t0, self.u1.pk))
        self._assert_get_identique(avant)

    def test_vrai_changement_avance(self):
        r = self.api.patch(self.url, {'ville': 'Rabat'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        date, par = self._etat()
        self.assertGreater(date, self.t0)
        self.assertEqual(par, self.u2.pk)
        self.assertEqual(self.lead.ville, 'Rabat')
