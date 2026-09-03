"""CRX39 (DRAFT165-57) — le consentement recueilli par le formulaire du site
atterrit dans le REGISTRE ``core.ConsentRecord``, finalité par finalité.

Avant : ``consentTimestamp`` et ``whatsappOptIn`` ne vivaient que sur la fiche
``Lead``. Le registre — celui qu'interroge une demande CNDP, celui que lisent
le DSR et les filtres marketing — restait VIDE pour la source de leads n°1.

Contrat vérifié ici :
  - une soumission consentie écrit la finalité ``marketing`` (accordée), datée
    du ``consentTimestamp`` du SITE, pas de l'instant serveur ;
  - l'opt-in WhatsApp écrit la finalité ``whatsapp`` — accordée OU refusée ;
  - la question NON POSÉE (``whatsappOptIn`` absent) n'écrit RIEN : un silence
    n'est pas un refus, et un consentement supposé n'est jamais inventé ;
  - ``ip_confirmation``/``version_texte`` restent vides à dessein (le site ne
    pratique pas de double opt-in et ne transmet aucune version de texte).
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.models import Company
from core.models import ConsentRecord

from apps.crm.models import Lead

SECRET = 'test-secret-crx39'
CONSENT_ISO = '2026-09-01T10:30:00+00:00'


def _payload(**extra):
    base = {
        'fullName': 'Salma Idrissi',
        'phoneE164': '+212661778899',
        'email': 'salma@example.com',
        'city': 'Casablanca',
        'billRange': '1500-3000',
        'qualified': True,
        'consentTimestamp': CONSENT_ISO,
        'whatsappOptIn': True,
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class ConsentementIntakeWebTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX39', slug='taqinor-crx39')
        self.url = reverse('website-lead-webhook')
        self._idem = 0

    def post(self, data):
        self._idem += 1
        data = dict(data)
        data.setdefault('idempotencyKey', f'crx39-{self._idem}')
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_soumission_consentie_ecrit_les_deux_finalites(self):
        resp = self.post(_payload())
        self.assertIn(resp.status_code, (200, 201), resp.content)
        lead = Lead.objects.get(company=self.company)

        entrees = {
            e.purpose: e for e in ConsentRecord.objects.filter(
                company=self.company)}
        self.assertEqual(set(entrees), {'marketing', 'whatsapp'})

        marketing = entrees['marketing']
        self.assertTrue(marketing.granted)
        # Identifiant = e-mail quand il existe (sinon téléphone).
        self.assertEqual(marketing.subject_identifier, lead.email)
        self.assertEqual(marketing.source, 'formulaire site web')
        # Horodatage = celui du SITE, pas l'instant serveur.
        self.assertEqual(marketing.occurred_at, lead.consent_timestamp)
        self.assertNotEqual(marketing.occurred_at, None)
        # Pas de double opt-in ni de version de texte inventés.
        self.assertIsNone(marketing.ip_confirmation)
        self.assertEqual(marketing.version_texte, '')

        self.assertTrue(entrees['whatsapp'].granted)

    def test_optin_whatsapp_refuse_est_trace_comme_refus(self):
        self.post(_payload(whatsappOptIn=False))
        whatsapp = ConsentRecord.objects.get(
            company=self.company, purpose='whatsapp')
        self.assertFalse(whatsapp.granted)
        # Le consentement marketing, lui, reste accordé.
        self.assertTrue(ConsentRecord.objects.get(
            company=self.company, purpose='marketing').granted)

    def test_question_non_posee_n_ecrit_rien(self):
        """``whatsappOptIn`` absent = question jamais posée : aucune entrée
        WhatsApp (ni accordée, ni refusée)."""
        payload = _payload()
        payload.pop('whatsappOptIn')
        self.post(payload)
        self.assertFalse(ConsentRecord.objects.filter(
            company=self.company, purpose='whatsapp').exists())
        self.assertTrue(ConsentRecord.objects.filter(
            company=self.company, purpose='marketing').exists())

    def test_sans_consent_timestamp_aucun_consentement_marketing(self):
        """Aucun consentement supposé : sans horodatage transmis, la finalité
        marketing n'est PAS écrite."""
        payload = _payload()
        payload.pop('consentTimestamp')
        self.post(payload)
        self.assertFalse(ConsentRecord.objects.filter(
            company=self.company, purpose='marketing').exists())

    def test_service_pose_l_horodatage_reel(self):
        """Le point d'entrée unique accepte désormais ``occurred_at`` — sans
        lui, le registre daterait le consentement du moment où l'ERP l'a
        enregistré, pas de celui où la personne l'a donné."""
        from apps.crm.services import enregistrer_consentement_lead

        quand = timezone.now() - timezone.timedelta(days=3)
        lead = Lead.objects.create(
            company=self.company, nom='Réda Test',
            email='reda@example.com', telephone='+212600000009')
        entree = enregistrer_consentement_lead(
            lead, purpose='marketing', source='devis', occurred_at=quand)
        self.assertEqual(entree.occurred_at, quand)

        # Appelant historique (sans occurred_at) : comportement inchangé.
        avant = timezone.now()
        entree2 = enregistrer_consentement_lead(lead, purpose='sms')
        self.assertGreaterEqual(entree2.occurred_at, avant)
