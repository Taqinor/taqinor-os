"""
ZSAL5 — Reçu/accusé d'envoi de devis : gabarit d'email de devis éditable +
trace d'envoi dans le chatter du lead.

L'envoi de devis utilise le gabarit effectif (défaut inchangé), une ligne
« devis envoyé » apparaît dans le chatter du lead, gabarit sans clé d'envoi
= no-op propre, jamais de prix d'achat, tests couvrent rendu gabarit + trace
chatter + no-leak.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zsal5_envoi_devis_template -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, EmailLog

User = get_user_model()


def make_company(slug='zsal5-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': 'ZSAL5 Co'})[0]


def make_user(company, username='zsal5_user'):
    return User.objects.create_user(
        username=username, password='x',
        role_legacy='responsable', company=company)


def make_client(company, email='client@zsal5.ma'):
    return Client.objects.create(
        company=company, nom='ZSAL5', prenom='Client',
        email=email, telephone='+212611000010')


def make_api(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def url(devis_id):
    return f'/api/django/ventes/devis/{devis_id}/envoyer-email/'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEnvoiDevisTemplate(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = make_api(self.user)
        self.client_obj = make_client(self.company)

    def test_default_template_renders_devis_reference_and_link(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ZSAL5-0001',
            client=self.client_obj, statut='brouillon', created_by=self.user)
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        log = EmailLog.objects.filter(devis=devis).first()
        self.assertIsNotNone(log)
        self.assertIn('DEV-ZSAL5-0001', log.corps)
        self.assertIn(devis.reference, log.sujet)
        # Jamais de prix d'achat dans le rendu.
        self.assertNotIn('prix_achat', log.corps)

    def test_custom_template_overrides_default(self):
        from apps.parametres.models_email import EmailTemplate
        EmailTemplate.objects.create(
            company=self.company, cle='envoi_devis',
            sujet='Devis perso {reference}',
            corps='Corps personnalisé {reference} — {lien}')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ZSAL5-0002',
            client=self.client_obj, statut='brouillon', created_by=self.user)
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        log = EmailLog.objects.filter(devis=devis).first()
        self.assertEqual(log.sujet, 'Devis perso DEV-ZSAL5-0002')
        self.assertIn('Corps personnalisé DEV-ZSAL5-0002', log.corps)

    def test_lead_chatter_gets_devis_envoye_note(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead ZSAL5', stage='QUOTE_SENT')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ZSAL5-0003',
            client=self.client_obj, lead=lead, statut='brouillon',
            created_by=self.user)
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        from apps.crm.models import LeadActivity
        note = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__icontains='envoyé par email').first()
        self.assertIsNotNone(note)
        self.assertIn('DEV-ZSAL5-0003', note.body)
        self.assertIsNone(note.user)

    def test_devis_without_lead_no_chatter_crash(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ZSAL5-0004',
            client=self.client_obj, statut='brouillon', created_by=self.user)
        self.assertIsNone(devis.lead_id)
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
