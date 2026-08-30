"""Tests NTDATA38 — cadences fines & fenêtre d'envoi des rapports planifiés.

Couvre :
  * un rapport MENSUEL part le jour du mois configuré, à l'heure configurée ;
  * il ne part pas un autre jour, ni à une autre heure ;
  * un mois = un envoi (anti-doublon sur ``last_sent_at``) ;
  * ``heure_envoi`` vide = comportement HISTORIQUE inchangé (daily/weekly) ;
  * ``heure_envoi`` posée borne aussi le quotidien ;
  * les deux champs sont exposés en écriture par l'API.
"""
from datetime import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import SavedReport
from .scheduled_reports import email_saved_reports

User = get_user_model()

try:  # pragma: no cover - zoneinfo présent partout en pratique
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo('Africa/Casablanca')
except Exception:  # pragma: no cover
    TZ = None


def _a(annee, mois, jour, heure):
    return datetime(annee, mois, jour, heure, 0, tzinfo=TZ)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ANYMAIL={'SENDINBLUE_API_KEY': 'test-key'})
class CadenceMensuelleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='MensuelCo')

    def _rapport(self, **kw):
        params = dict(company=self.company, name='Mensuel',
                      target_kind='sales', schedule='monthly',
                      recipients='boss@example.com')
        params.update(kw)
        return SavedReport.objects.create(**params)

    def _lancer(self, quand):
        with mock.patch('apps.reporting.scheduled_reports._casablanca_now',
                        return_value=quand):
            return email_saved_reports()

    def test_mensuel_part_le_jour_et_a_lheure_configures(self):
        self._rapport(jour_du_mois=1, heure_envoi=9)
        self.assertEqual(self._lancer(_a(2026, 6, 1, 9)), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_mensuel_ne_part_pas_un_autre_jour(self):
        self._rapport(jour_du_mois=1, heure_envoi=9)
        self.assertEqual(self._lancer(_a(2026, 6, 2, 9)), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_mensuel_ne_part_pas_a_une_autre_heure(self):
        self._rapport(jour_du_mois=1, heure_envoi=9)
        self.assertEqual(self._lancer(_a(2026, 6, 1, 6)), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_jour_du_mois_personnalise(self):
        self._rapport(jour_du_mois=15, heure_envoi=7)
        self.assertEqual(self._lancer(_a(2026, 6, 1, 7)), 0)
        self.assertEqual(self._lancer(_a(2026, 6, 15, 7)), 1)

    def test_un_mois_un_seul_envoi(self):
        self._rapport(jour_du_mois=1, heure_envoi=9)
        self.assertEqual(self._lancer(_a(2026, 6, 1, 9)), 1)
        # Le planificateur repasse le même jour : aucun doublon.
        self.assertEqual(self._lancer(_a(2026, 6, 1, 9)), 0)
        self.assertEqual(len(mail.outbox), 1)
        # Le mois suivant, il repart.
        self.assertEqual(self._lancer(_a(2026, 7, 1, 9)), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_mensuel_sans_heure_part_au_passage_du_planificateur(self):
        self._rapport(jour_du_mois=3)
        self.assertEqual(self._lancer(_a(2026, 6, 3, 6)), 1)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ANYMAIL={'SENDINBLUE_API_KEY': 'test-key'})
class FenetreHoraireTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='HeureCo')

    def _lancer(self, quand):
        with mock.patch('apps.reporting.scheduled_reports._casablanca_now',
                        return_value=quand):
            return email_saved_reports()

    def test_quotidien_sans_heure_inchange(self):
        SavedReport.objects.create(
            company=self.company, name='Quotidien', target_kind='sales',
            schedule='daily', recipients='boss@example.com')
        # Historique : aucune contrainte d'heure — dû quelle que soit l'heure.
        self.assertEqual(self._lancer(_a(2026, 6, 17, 3)), 1)

    def test_quotidien_avec_heure_borne_lenvoi(self):
        SavedReport.objects.create(
            company=self.company, name='Quotidien 18h', target_kind='sales',
            schedule='daily', recipients='boss@example.com', heure_envoi=18)
        self.assertEqual(self._lancer(_a(2026, 6, 17, 6)), 0)
        self.assertEqual(self._lancer(_a(2026, 6, 17, 18)), 1)

    def test_hebdo_avec_heure_reste_le_lundi(self):
        SavedReport.objects.create(
            company=self.company, name='Hebdo', target_kind='service',
            schedule='weekly', recipients='boss@example.com', heure_envoi=8)
        # Mardi 8 h : non dû.
        self.assertEqual(self._lancer(_a(2026, 6, 16, 8)), 0)
        # Lundi 8 h : dû.
        self.assertEqual(self._lancer(_a(2026, 6, 15, 8)), 1)

    def test_defauts_du_modele(self):
        rapport = SavedReport.objects.create(
            company=self.company, name='Défauts', target_kind='sales')
        self.assertIsNone(rapport.heure_envoi)
        self.assertEqual(rapport.jour_du_mois, 1)


class CadenceApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ApiCo')
        self.user = User.objects.create_user(
            username='cadence', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_cadence_mensuelle_configurable_par_api(self):
        res = self.api.post('/api/django/reporting/saved-reports/', {
            'name': 'Mensuel', 'target_kind': 'sales', 'schedule': 'monthly',
            'heure_envoi': 9, 'jour_du_mois': 5,
            'recipients': 'a@b.com',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        rapport = SavedReport.objects.get(id=res.data['id'])
        self.assertEqual(rapport.schedule, 'monthly')
        self.assertEqual(rapport.heure_envoi, 9)
        self.assertEqual(rapport.jour_du_mois, 5)

    def test_heure_hors_bornes_refusee(self):
        res = self.api.post('/api/django/reporting/saved-reports/', {
            'name': 'KO', 'target_kind': 'sales', 'schedule': 'monthly',
            'heure_envoi': 30,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_jour_du_mois_hors_bornes_refuse(self):
        res = self.api.post('/api/django/reporting/saved-reports/', {
            'name': 'KO', 'target_kind': 'sales', 'schedule': 'monthly',
            'jour_du_mois': 31,
        }, format='json')
        self.assertEqual(res.status_code, 400)
