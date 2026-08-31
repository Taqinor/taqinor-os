"""Tests NTDATA40 — historique de diffusion des rapports.

Couvre :
  * un ÉCHEC d'envoi est visible dans l'historique AVEC son motif ;
  * un envoi réussi est journalisé « envoyé » sans motif ;
  * canal non configuré / aucun destinataire ont chacun leur statut propre ;
  * le canal WhatsApp non armé laisse une trace explicite ;
  * la company est posée côté serveur, l'historique est borné à la société ;
  * l'API est en LECTURE seule et filtrable par rapport et par statut.
"""
from datetime import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import EnvoiRapport, SavedReport
from .scheduled_reports import email_saved_reports

User = get_user_model()

try:  # pragma: no cover
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo('Africa/Casablanca')
except Exception:  # pragma: no cover
    TZ = None

QUAND = datetime(2026, 6, 17, 6, 0, tzinfo=TZ)


def _lancer():
    with mock.patch('apps.reporting.scheduled_reports._casablanca_now',
                    return_value=QUAND):
        return email_saved_reports()


class JournalDiffusionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='JournalCo')

    def _rapport(self, **kw):
        params = dict(company=self.company, name='Ventes',
                      target_kind='sales', schedule='daily',
                      recipients='boss@example.com')
        params.update(kw)
        return SavedReport.objects.create(**params)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_canal_email_non_configure_trace_avec_motif(self):
        rapport = self._rapport()
        self.assertEqual(_lancer(), 0)
        envoi = EnvoiRapport.objects.get(saved_report=rapport)
        self.assertEqual(envoi.statut, 'non_configure')
        self.assertEqual(envoi.canal, 'email')
        self.assertIn('Email non configuré', envoi.erreur)
        self.assertEqual(envoi.destinataires, 'boss@example.com')
        self.assertEqual(envoi.company, self.company)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ANYMAIL={'SENDINBLUE_API_KEY': 'test-key'})
    def test_envoi_reussi_journalise_sans_motif(self):
        rapport = self._rapport()
        self.assertEqual(_lancer(), 1)
        envoi = EnvoiRapport.objects.get(saved_report=rapport)
        self.assertEqual(envoi.statut, 'envoye')
        self.assertEqual(envoi.erreur, '')
        self.assertIsNotNone(envoi.envoye_le)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ANYMAIL={'SENDINBLUE_API_KEY': 'test-key'})
    def test_echec_denvoi_visible_avec_le_motif(self):
        rapport = self._rapport()
        with mock.patch('apps.reporting.scheduled_reports._send_report_email',
                        return_value=False):
            self.assertEqual(_lancer(), 0)
        envoi = EnvoiRapport.objects.get(saved_report=rapport)
        self.assertEqual(envoi.statut, 'echec')
        self.assertIn('refusé', envoi.erreur)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ANYMAIL={'SENDINBLUE_API_KEY': 'test-key'})
    def test_rendu_impossible_trace_un_echec(self):
        rapport = self._rapport()
        with mock.patch('apps.reporting.scheduled_reports.render_report_xlsx',
                        return_value=(None, None)):
            self.assertEqual(_lancer(), 0)
        envoi = EnvoiRapport.objects.get(saved_report=rapport)
        self.assertEqual(envoi.statut, 'echec')
        self.assertIn('Rendu', envoi.erreur)

    def test_sans_destinataire_a_son_propre_statut(self):
        rapport = self._rapport(recipients='')
        _lancer()
        envoi = EnvoiRapport.objects.get(saved_report=rapport)
        self.assertEqual(envoi.statut, 'sans_destinataire')

    def test_whatsapp_non_arme_laisse_une_trace(self):
        rapport = self._rapport(canal='whatsapp', recipients='',
                                destinataires_whatsapp='+212600000000')
        with mock.patch('apps.notifications.services.whatsapp_bsp_actif',
                        return_value=False):
            self.assertEqual(_lancer(), 0)
        envoi = EnvoiRapport.objects.get(saved_report=rapport)
        self.assertEqual(envoi.canal, 'whatsapp')
        self.assertEqual(envoi.statut, 'non_configure')
        self.assertEqual(envoi.destinataires, '+212600000000')

    def test_whatsapp_arme_journalise_un_envoi(self):
        rapport = self._rapport(canal='whatsapp', recipients='',
                                destinataires_whatsapp='+212600000000')
        with mock.patch('apps.notifications.services.whatsapp_bsp_actif',
                        return_value=True):
            with mock.patch('apps.notifications.services.'
                            'send_whatsapp_campaign_message',
                            return_value={'provider': 'bsp'}):
                self.assertEqual(_lancer(), 1)
        envoi = EnvoiRapport.objects.get(saved_report=rapport)
        self.assertEqual(envoi.statut, 'envoye')


class EnvoiRapportApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ApiJournalCo')
        self.autre = Company.objects.create(nom='AutreCo')
        self.user = User.objects.create_user(
            username='journal', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.rapport = SavedReport.objects.create(
            company=self.company, name='Ventes', target_kind='sales')
        self.autre_rapport = SavedReport.objects.create(
            company=self.autre, name='Étranger', target_kind='sales')
        self.ok = EnvoiRapport.objects.create(
            company=self.company, saved_report=self.rapport, canal='email',
            destinataires='a@b.com', statut='envoye')
        self.ko = EnvoiRapport.objects.create(
            company=self.company, saved_report=self.rapport, canal='email',
            destinataires='a@b.com', statut='echec',
            erreur='Backend email injoignable.')
        EnvoiRapport.objects.create(
            company=self.autre, saved_report=self.autre_rapport,
            canal='email', destinataires='x@y.com', statut='echec')

    def _lignes(self, res):
        return res.data['results'] if 'results' in res.data else res.data

    def test_historique_borne_a_la_societe(self):
        res = self.api.get('/api/django/reporting/envois-rapports/')
        self.assertEqual(res.status_code, 200)
        lignes = self._lignes(res)
        self.assertEqual({ligne['id'] for ligne in lignes},
                         {self.ok.pk, self.ko.pk})

    def test_filtre_par_statut_montre_les_echecs_avec_motif(self):
        res = self.api.get(
            '/api/django/reporting/envois-rapports/?statut=echec')
        lignes = self._lignes(res)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['statut'], 'echec')
        self.assertIn('injoignable', lignes[0]['erreur'])
        self.assertEqual(lignes[0]['rapport_nom'], 'Ventes')

    def test_filtre_par_rapport(self):
        res = self.api.get(
            f'/api/django/reporting/envois-rapports/'
            f'?saved_report={self.rapport.pk}')
        self.assertEqual(len(self._lignes(res)), 2)

    def test_lecture_seule(self):
        res = self.api.post('/api/django/reporting/envois-rapports/', {
            'saved_report': self.rapport.pk, 'canal': 'email',
            'statut': 'envoye'}, format='json')
        self.assertEqual(res.status_code, 405)
