"""CAD121 — la case WhatsApp du formulaire part DÉCOCHÉE.

Décision fondateur du 21/09/2026 (section CAD-K). ``whatsappOptIn`` était
rendue PRÉ-COCHÉE, alimentait ``whatsapp_opt_in`` et valait +3 points de
score : or la loi 09-08 (art. 10) exige un consentement « libre, spécifique
et informé », qu'une case pré-cochée n'est pas — et ce faux consentement
POLLUAIT le registre que CAD90 remplit. Effets assumés : -3 points sur les
leads web qui ne la cochent pas, et un taux d'opt-in affiché plus bas mais
VRAI.

Ce fichier verrouille la moitié serveur : ``whatsapp_opt_in`` reste FAUX tant
que le client ne coche pas, le score ne reçoit pas les 3 points, et le
registre trace un REFUS (jamais un accord supposé). La moitié écran est
verrouillée par ``apps/web/src/components/DiagnosticForm.optin.test.ts``.
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company
from core.models import ConsentRecord

from apps.crm.models import Lead
from apps.crm.scoring import compute_score

SECRET = 'test-secret-cad121'
CONSENT_ISO = '2026-09-21T10:30:00+00:00'


def _payload(**extra):
    base = {
        'fullName': 'Salma Idrissi',
        'phoneE164': '+212661778899',
        'email': 'salma@example.com',
        'city': 'Casablanca',
        'billRange': '1500-3000',
        'qualified': True,
        'consentTimestamp': CONSENT_ISO,
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class OptInDecocheTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CAD121', slug='taqinor-cad121')
        self.url = reverse('website-lead-webhook')
        self._idem = 0

    def post(self, data):
        self._idem += 1
        data = dict(data)
        data.setdefault('idempotencyKey', f'cad121-{self._idem}')
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_case_non_cochee_laisse_optin_faux(self):
        """Le client n'a pas coché : aucun consentement WhatsApp n'existe."""
        resp = self.post(_payload(whatsappOptIn=False))
        self.assertIn(resp.status_code, (200, 201), resp.content)
        lead = Lead.objects.get(company=self.company)
        self.assertIs(lead.whatsapp_opt_in, False)

    def test_case_non_cochee_ne_donne_pas_les_trois_points(self):
        self.post(_payload(whatsappOptIn=False))
        lead = Lead.objects.get(company=self.company)
        sans = compute_score(lead)
        lead.whatsapp_opt_in = True
        avec = compute_score(lead)
        self.assertGreater(avec, sans)

    def test_case_non_cochee_trace_un_refus_au_registre(self):
        """Le registre dit « refusé », jamais un accord supposé (CAD90)."""
        self.post(_payload(whatsappOptIn=False))
        entree = ConsentRecord.objects.get(
            company=self.company, purpose='whatsapp')
        self.assertFalse(entree.granted)

    def test_case_cochee_reste_un_accord(self):
        """Décocher par défaut ne casse pas le chemin du vrai consentement."""
        self.post(_payload(whatsappOptIn=True))
        lead = Lead.objects.get(company=self.company)
        self.assertIs(lead.whatsapp_opt_in, True)
        self.assertTrue(ConsentRecord.objects.get(
            company=self.company, purpose='whatsapp').granted)

    def test_question_non_posee_reste_indeterminee(self):
        """Trois états, jamais deux : `None` n'est ni un accord ni un refus."""
        self.post(_payload())
        lead = Lead.objects.get(company=self.company)
        self.assertIsNone(lead.whatsapp_opt_in)
        self.assertFalse(ConsentRecord.objects.filter(
            company=self.company, purpose='whatsapp').exists())
