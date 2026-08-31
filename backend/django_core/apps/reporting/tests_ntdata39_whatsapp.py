"""Tests NTDATA39 — diffusion WhatsApp d'un LIEN tokenisé (GATED fondateur).

Couvre :
  * SANS clé WhatsApp : aucun envoi, aucun log de message, ``last_sent_at``
    intact — no-op total ;
  * AVEC le canal armé : un message part, et il contient le LIEN (jamais la
    pièce jointe) ;
  * le lien est signé, expirant, et résout le bon rapport ;
  * le rendu public refuse un jeton invalide/expiré (404 générique) ;
  * le canal email reste STRICTEMENT inchangé.
"""
from datetime import datetime
from unittest import mock

from django.core import signing
from django.test import TestCase, override_settings

from authentication.models import Company

from . import diffusion_views
from .models import SavedReport
from .scheduled_reports import email_saved_reports

try:  # pragma: no cover
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo('Africa/Casablanca')
except Exception:  # pragma: no cover
    TZ = None


class LienTokeniseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='LienCo')
        self.report = SavedReport.objects.create(
            company=self.company, name='Ventes', target_kind='sales')

    def test_jeton_resout_le_bon_rapport(self):
        token = diffusion_views.make_report_token(self.report)
        self.assertEqual(diffusion_views.resolve_report_token(token),
                         self.report)

    def test_jeton_invalide_ne_resout_rien(self):
        self.assertIsNone(diffusion_views.resolve_report_token('n-importe-quoi'))
        self.assertIsNone(diffusion_views.resolve_report_token(''))

    def test_jeton_expire_ne_resout_plus(self):
        token = diffusion_views.make_report_token(self.report)
        self.assertIsNone(
            diffusion_views.resolve_report_token(token, max_age=-1))

    def test_jeton_signe_non_forgeable(self):
        faux = signing.dumps(self.report.pk, salt='mauvais-sel')
        self.assertIsNone(diffusion_views.resolve_report_token(faux))

    def test_lien_porte_le_jeton(self):
        lien = diffusion_views.lien_rapport(self.report)
        self.assertTrue(lien.startswith('/api/django/reporting/'
                                        'rapports-partages/'))
        token = lien.rstrip('/').rsplit('/', 1)[-1]
        self.assertEqual(diffusion_views.resolve_report_token(token),
                         self.report)

    def test_rendu_public_refuse_un_jeton_invalide(self):
        res = self.client.get(
            '/api/django/reporting/rapports-partages/pas-un-jeton/')
        self.assertEqual(res.status_code, 404)

    def test_rendu_public_sert_le_xlsx_avec_un_jeton_valide(self):
        token = diffusion_views.make_report_token(self.report)
        res = self.client.get(
            f'/api/django/reporting/rapports-partages/{token}/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml', res['Content-Type'])


class DiffusionWhatsAppGateTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='WaCo')
        self.report = SavedReport.objects.create(
            company=self.company, name='Ventes', target_kind='sales',
            schedule='daily', canal='whatsapp',
            destinataires_whatsapp='+212600000000')

    def test_sans_cle_aucun_envoi(self):
        with mock.patch('apps.notifications.services.whatsapp_bsp_actif',
                        return_value=False):
            with mock.patch(
                    'apps.notifications.services.'
                    'send_whatsapp_campaign_message') as envoi:
                envoyes, detail = diffusion_views.diffuser_whatsapp(self.report)
                envoi.assert_not_called()
        self.assertEqual(envoyes, 0)
        self.assertIn('non configuré', detail)

    def test_sans_numero_aucun_envoi(self):
        self.report.destinataires_whatsapp = ''
        envoyes, detail = diffusion_views.diffuser_whatsapp(self.report)
        self.assertEqual(envoyes, 0)
        self.assertIn('Aucun numéro', detail)

    def test_avec_canal_arme_un_message_avec_le_lien_part(self):
        captures = []

        def _faux_envoi(company, *, recipient, body, **kw):
            captures.append((recipient, body))
            return {'provider': 'bsp', 'log': None, 'url': None}

        with mock.patch('apps.notifications.services.whatsapp_bsp_actif',
                        return_value=True):
            with mock.patch('apps.notifications.services.'
                            'send_whatsapp_campaign_message', _faux_envoi):
                envoyes, detail = diffusion_views.diffuser_whatsapp(self.report)
        self.assertEqual(envoyes, 1)
        self.assertIn('WhatsApp', detail)
        recipient, body = captures[0]
        self.assertEqual(recipient, '+212600000000')
        self.assertIn('rapports-partages/', body)
        # Le message porte un LIEN, jamais la pièce jointe.
        self.assertNotIn('.xlsx', body)

    def test_tache_planifiee_no_op_sans_cle(self):
        with mock.patch('apps.notifications.services.whatsapp_bsp_actif',
                        return_value=False):
            self.assertEqual(email_saved_reports(), 0)
        self.report.refresh_from_db()
        self.assertIsNone(self.report.last_sent_at)

    def test_tache_planifiee_envoie_quand_le_canal_est_arme(self):
        with mock.patch('apps.notifications.services.whatsapp_bsp_actif',
                        return_value=True):
            with mock.patch(
                    'apps.notifications.services.'
                    'send_whatsapp_campaign_message',
                    return_value={'provider': 'bsp'}):
                self.assertEqual(email_saved_reports(), 1)
        self.report.refresh_from_db()
        self.assertIsNotNone(self.report.last_sent_at)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ANYMAIL={'SENDINBLUE_API_KEY': 'test-key'})
class CanalEmailInchangeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='MailCo')

    def test_defaut_email_et_piece_jointe_conservee(self):
        rapport = SavedReport.objects.create(
            company=self.company, name='Quotidien', target_kind='sales',
            schedule='daily', recipients='boss@example.com')
        self.assertEqual(rapport.canal, 'email')
        from django.core import mail
        with mock.patch('apps.reporting.scheduled_reports._casablanca_now',
                        return_value=datetime(2026, 6, 17, 6, 0, tzinfo=TZ)):
            self.assertEqual(email_saved_reports(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(mail.outbox[0].attachments), 1)

    def test_liste_des_numeros_nettoyee(self):
        rapport = SavedReport.objects.create(
            company=self.company, name='R', target_kind='sales',
            destinataires_whatsapp=' +212600000001, +212600000002 ;\n'
                                   '+212600000003 ')
        self.assertEqual(rapport.whatsapp_list(),
                         ['+212600000001', '+212600000002', '+212600000003'])
