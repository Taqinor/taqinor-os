"""Tests N87 (intégration email Brevo) + N88 (capture entrante) + G9 (jobs
planifiés Celery Beat).

Garanties testées :
  - Envoi d'un document = NO-OP sans clé configurée : aucune exception, backend
    locmem/console utilisé, EmailLog consigné + note de chatter sur le devis.
  - L'endpoint facture envoyer-email passe par l'intégration et consigne.
  - La relance (relancer) envoie un email de relance via l'intégration.
  - La capture entrante rattache une réponse au bon document via une référence
    reconnaissable, sinon au client par email, et reste un no-op si rien n'est
    reconnu — sans clé vivante.
  - Le job quotidien bascule une facture impayée échue en `en_retard`, est
    idempotent, et respecte l'échéance par défaut (émission + 30 j).
  - Toute la logique de temps raisonne en Africa/Casablanca.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Devis, DevisActivity, EmailLog, Facture, FollowupLevel, LigneFacture,
    Paiement, RelanceLog,
)

User = get_user_model()

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def make_company(slug='email-co', nom='Email Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


@override_settings(EMAIL_BACKEND=LOCMEM)
class TestEmailService(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='emresp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Acheteur', email='acheteur@example.ma',
            telephone='+212600000001')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-E',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-EM-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-EM-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=10))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def test_send_document_no_key_is_noop_but_logged(self):
        """Sans clé configurée (backend locmem), l'envoi ne lève pas, consigne
        l'EmailLog et ajoute une note au chatter du devis."""
        from apps.ventes.email_service import send_document_email
        log = send_document_email(self.devis, user=self.user)
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(log.direction, EmailLog.Direction.SORTANT)
        self.assertEqual(log.to_email, 'acheteur@example.ma')
        self.assertEqual(log.devis_id, self.devis.id)
        self.assertEqual(log.company_id, self.company.id)
        # Le backend locmem a « reçu » le message (no-op réseau).
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('DEV-EM-0001', mail.outbox[0].subject)
        # Note de chatter posée sur le devis.
        self.assertTrue(DevisActivity.objects.filter(
            devis=self.devis, kind=DevisActivity.Kind.NOTE).exists())

    def test_send_document_without_email_is_echec_no_crash(self):
        self.client_obj.email = ''
        self.client_obj.save(update_fields=['email'])
        from apps.ventes.email_service import send_document_email
        log = send_document_email(self.facture, user=self.user)
        self.assertEqual(log.statut, EmailLog.Statut.ECHEC)
        self.assertEqual(len(mail.outbox), 0)

    def test_is_email_configured_false_on_console_and_locmem(self):
        from apps.ventes import email_service
        # locmem (test) et console (défaut) ne comptent pas comme « configuré ».
        self.assertFalse(email_service.is_email_configured())

    @override_settings(
        EMAIL_BACKEND='anymail.backends.sendinblue.EmailBackend',
        ANYMAIL={'SENDINBLUE_API_KEY': 'brevo-key'})
    def test_is_email_configured_true_with_brevo_key(self):
        from apps.ventes import email_service
        self.assertTrue(email_service.is_email_configured())

    def test_facture_envoyer_email_endpoint_routes_through_integration(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/envoyer-email/',
            {}, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertTrue(EmailLog.objects.filter(
            facture=self.facture,
            direction=EmailLog.Direction.SORTANT).exists())

    def test_relancer_sends_relance_email(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Rappel', delai_jours=7,
            message='Merci de régulariser.')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/relancer/',
            {'niveau': 1, 'note': 'rappel'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(RelanceLog.objects.filter(facture=self.facture).exists())
        self.assertTrue(EmailLog.objects.filter(
            facture=self.facture,
            direction=EmailLog.Direction.SORTANT).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_emails_thread_endpoint(self):
        from apps.ventes.email_service import send_document_email
        send_document_email(self.facture, user=self.user)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.get(
            f'/api/django/ventes/factures/{self.facture.id}/emails/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)


class TestInboundEmail(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Répondeur', email='client@example.ma')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-IN-0007',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))

    def test_extract_reference(self):
        from apps.ventes.inbound_email import extract_reference
        self.assertEqual(
            extract_reference('Re: votre FAC-IN-0007 reçue'), 'FAC-IN-0007')
        self.assertEqual(extract_reference('rien ici'), '')

    def test_capture_attaches_to_document_by_reference(self):
        from apps.ventes.inbound_email import capture_inbound_email
        log = capture_inbound_email(
            from_email='client@example.ma',
            subject='Re: FAC-IN-0007', body='Merci, bien reçue.',
            company=self.company)
        self.assertIsNotNone(log)
        self.assertEqual(log.facture_id, self.facture.id)
        self.assertEqual(log.client_id, self.client_obj.id)
        self.assertEqual(log.direction, EmailLog.Direction.ENTRANT)
        self.assertEqual(log.statut, EmailLog.Statut.RECU)

    def test_capture_falls_back_to_client_email(self):
        from apps.ventes.inbound_email import capture_inbound_email
        log = capture_inbound_email(
            from_email='client@example.ma', subject='Bonjour',
            body='Sans référence', company=self.company)
        self.assertIsNotNone(log)
        self.assertIsNone(log.facture_id)
        self.assertEqual(log.client_id, self.client_obj.id)

    def test_capture_noop_when_nothing_recognized(self):
        from apps.ventes.inbound_email import capture_inbound_email
        log = capture_inbound_email(
            from_email='inconnu@nowhere.test', subject='?', body='?',
            company=self.company)
        self.assertIsNone(log)
        self.assertEqual(EmailLog.objects.count(), 0)

    def test_inbound_not_configured_by_default(self):
        from apps.ventes import inbound_email
        self.assertFalse(inbound_email.is_inbound_configured())


@override_settings(EMAIL_BACKEND=LOCMEM)
class TestScheduledJobs(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Débiteur', email='deb@example.ma')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-S',
            prix_vente=Decimal('1000'), quantite_stock=10, tva=Decimal('20.00'))

    def _facture(self, ref, echeance, statut=Facture.Statut.EMISE):
        f = Facture.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20.00'), date_echeance=echeance)
        LigneFacture.objects.create(
            facture=f, produit=self.produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        return f

    def test_overdue_job_flips_unpaid_overdue_facture(self):
        from apps.ventes.scheduled import check_overdue_factures
        f = self._facture('FAC-OV-0001', date.today() - timedelta(days=5))
        n = check_overdue_factures()
        self.assertEqual(n, 1)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.EN_RETARD)

    def test_overdue_job_is_idempotent(self):
        from apps.ventes.scheduled import check_overdue_factures
        self._facture('FAC-OV-0002', date.today() - timedelta(days=5))
        self.assertEqual(check_overdue_factures(), 1)
        # Deuxième passage : déjà en retard → 0 nouvelle bascule.
        self.assertEqual(check_overdue_factures(), 0)

    def test_overdue_job_ignores_paid_facture(self):
        from apps.ventes.scheduled import check_overdue_factures
        f = self._facture('FAC-OV-0003', date.today() - timedelta(days=5))
        Paiement.objects.create(
            company=self.company, facture=f, montant=Decimal('1200'),
            date_paiement=date.today())
        self.assertEqual(check_overdue_factures(), 0)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.EMISE)

    def test_overdue_default_echeance_is_issue_plus_30_days(self):
        """Sans date_echeance, l'échéance par défaut = émission + 30 j.

        date_emission est auto_now_add (= aujourd'hui) → l'échéance par défaut
        est dans le futur → la facture ne doit PAS basculer."""
        from apps.ventes.scheduled import check_overdue_factures
        f = self._facture('FAC-OV-0004', None)
        self.assertEqual(check_overdue_factures(), 0)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.EMISE)
        # En forçant l'émission à il y a 31 jours, la facture devient échue.
        Facture.objects.filter(pk=f.pk).update(
            date_emission=date.today() - timedelta(days=31))
        self.assertEqual(check_overdue_factures(), 1)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.EN_RETARD)

    def test_relance_reminders_sends_and_consumes_date(self):
        from apps.ventes.scheduled import relance_reminders
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Rappel', delai_jours=7,
            message='Merci de régler.')
        f = self._facture('FAC-RM-0001', date.today() - timedelta(days=20))
        Facture.objects.filter(pk=f.pk).update(
            prochaine_relance=date.today() - timedelta(days=1))
        n = relance_reminders()
        self.assertEqual(n, 1)
        f.refresh_from_db()
        self.assertIsNone(f.prochaine_relance)
        self.assertTrue(RelanceLog.objects.filter(facture=f).exists())
        self.assertEqual(len(mail.outbox), 1)
        # Idempotence : la date consommée → pas de second envoi.
        self.assertEqual(relance_reminders(), 0)

    def test_casablanca_today_is_a_date(self):
        from apps.ventes.scheduled import casablanca_today, CASABLANCA_TZ
        self.assertEqual(CASABLANCA_TZ, 'Africa/Casablanca')
        self.assertIsInstance(casablanca_today(), date)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
class TestQW8EmailConfigBugfix(TestCase):
    """QW8 — is_email_configured() checked a key (ANYMAIL['BREVO_API_KEY'])
    that settings/base.py NEVER sets (the env var BREVO_API_KEY is stored
    under ANYMAIL['SENDINBLUE_API_KEY']). Even with EMAIL_BACKEND left on
    console (the actual default), a real Brevo key must be detected as
    configured."""

    @override_settings(ANYMAIL={'SENDINBLUE_API_KEY': 'real-brevo-key', 'SENDGRID_API_KEY': ''})
    def test_sendinblue_key_detected_even_on_console_backend(self):
        from apps.ventes import email_service
        # Avant le correctif QW8 : is_email_configured() cherchait
        # ANYMAIL['BREVO_API_KEY'] (jamais posée), retombait sur le backend
        # (console → False) — un vrai déploiement Brevo configuré via
        # BREVO_API_KEY seul (sans changer EMAIL_BACKEND) restait "non
        # configuré".
        self.assertTrue(email_service.is_email_configured())

    @override_settings(ANYMAIL={'SENDINBLUE_API_KEY': '', 'SENDGRID_API_KEY': 'sg-key'})
    def test_sendgrid_key_also_detected(self):
        from apps.ventes import email_service
        self.assertTrue(email_service.is_email_configured())

    @override_settings(ANYMAIL={'SENDINBLUE_API_KEY': '', 'SENDGRID_API_KEY': ''})
    def test_no_key_stays_unconfigured_on_console(self):
        from apps.ventes import email_service
        self.assertFalse(email_service.is_email_configured())


class TestQW8CallbackEmailDefaultOn(TestCase):
    """QW8 — a phone_ok callback fires an outbound email when configured
    (email channel defaults ON for lead_callback_requested, unlike the
    generic notification default of email=False)."""

    def setUp(self):
        self.company = make_company(slug='qw8-callback-co', nom='QW8 Callback Co')
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commercial QW8', permissions=['crm_voir'])
        self.owner = User.objects.create_user(
            username='qw8_owner', password='x', company=self.company,
            role=role, email='owner@example.com')

    @override_settings(
        EMAIL_BACKEND=LOCMEM,
        ANYMAIL={'SENDINBLUE_API_KEY': 'real-brevo-key', 'SENDGRID_API_KEY': ''})
    def test_configured_prod_fires_callback_email(self):
        from apps.crm.models import Lead
        from apps.crm.services import notify_lead_callback_requested

        lead = Lead.objects.create(
            company=self.company, nom='Prospect QW8', telephone='+212600998877',
            owner=self.owner, contact_preference=Lead.ContactPreference.PHONE_OK)
        notify_lead_callback_requested(lead)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('owner@example.com', mail.outbox[0].to)

    @override_settings(EMAIL_BACKEND=LOCMEM, ANYMAIL={'SENDINBLUE_API_KEY': '', 'SENDGRID_API_KEY': ''})
    def test_unconfigured_never_sends_but_never_crashes(self):
        from apps.crm.models import Lead
        from apps.crm.services import notify_lead_callback_requested

        lead = Lead.objects.create(
            company=self.company, nom='Prospect QW8b', telephone='+212600998866',
            owner=self.owner, contact_preference=Lead.ContactPreference.PHONE_OK)
        notify_lead_callback_requested(lead)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND=LOCMEM,
        ANYMAIL={'SENDINBLUE_API_KEY': 'real-brevo-key', 'SENDGRID_API_KEY': ''})
    def test_generic_new_lead_notification_still_defaults_email_off(self):
        # QW8 n'ouvre le canal email par défaut QUE pour le rappel — le
        # générique lead_new reste email=False par défaut (aucune régression).
        from apps.crm.models import Lead
        from apps.crm.services import notify_new_lead

        lead = Lead.objects.create(
            company=self.company, nom='Prospect générique',
            telephone='+212600998855', owner=self.owner)
        notify_new_lead(lead)
        self.assertEqual(len(mail.outbox), 0)
