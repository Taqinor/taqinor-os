"""YLEAD11 — Réactivation d'un lead perdu/COLD sur nouvelle touche entrante.

Couvre :
  - un 2e POST du webhook site sur un lead PERDU le réactive (perdu=False,
    stage non-COLD) avec une activité de réactivation, sans écraser
    l'attribution first-touch d'origine ;
  - un lead COLD (mais non perdu) est aussi repositionné hors COLD ;
  - un lead ouvert (ni perdu ni COLD) n'est pas affecté par
    ``reactivate_lead_on_new_touch`` (no-op) ;
  - company-scopée (chaque test opère sur une instance déjà résolue dans SA
    société — la fonction ne fait aucune requête cross-company) ;
  - la même règle est appliquée côté inbound WhatsApp (YLEAD8) — testé côté
    ``tests_ylead8_whatsapp_dedupe.py::test_lost_lead_is_reactivated_not_duplicated``,
    référencé ici pour traçabilité.
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.services import reactivate_lead_on_new_touch

SECRET = 'test-secret-ylead11'


class ReactivateLeadOnNewTouchUnitTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD11', slug='taqinor-ylead11')

    def test_lost_lead_is_reactivated(self):
        lead = Lead.objects.create(
            company=self.company, nom='Test', perdu=True,
            motif_perte='Pas de budget', stage=stages.QUOTE_SENT)
        reactivated = reactivate_lead_on_new_touch(lead)
        self.assertTrue(reactivated)
        lead.refresh_from_db()
        self.assertFalse(lead.perdu)
        # Étape déjà >= NEW/CONTACTED (QUOTE_SENT) → l'étape ne recule pas.
        self.assertEqual(lead.stage, stages.QUOTE_SENT)
        notes = LeadActivity.objects.filter(lead=lead)
        self.assertTrue(
            any('réactivation' in (n.body or '') for n in notes))

    def test_cold_lead_is_repositioned_to_new(self):
        lead = Lead.objects.create(
            company=self.company, nom='Test Cold', stage=stages.COLD)
        reactivated = reactivate_lead_on_new_touch(lead)
        self.assertTrue(reactivated)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.NEW)
        self.assertFalse(lead.perdu)

    def test_cold_lead_already_contacted_goes_to_contacted(self):
        lead = Lead.objects.create(
            company=self.company, nom='Test Cold 2', stage=stages.COLD,
            first_contacted_at=timezone.now())
        reactivate_lead_on_new_touch(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_open_lead_is_noop(self):
        lead = Lead.objects.create(
            company=self.company, nom='Test Open', stage=stages.CONTACTED)
        reactivated = reactivate_lead_on_new_touch(lead)
        self.assertFalse(reactivated)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertFalse(
            LeadActivity.objects.filter(lead=lead).exists())


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class WebhookReactivationTests(TestCase):
    """2e POST site sur un lead perdu → réactivation, sans écraser le
    first-touch d'origine."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor YLEAD11 Web', slug='taqinor-ylead11-web')
        self.url = reverse('website-lead-webhook')

    def _payload(self, **extra):
        base = {
            'fullName': 'Nadia Bennis',
            'phoneE164': '+212662000001',
            'city': 'Marrakech',
            'roofType': 'villa',
            'billRange': '1500-3000',
            'qualified': True,
            'utm': {'utm_source': 'facebook', 'utm_campaign': 'campagne_origine'},
        }
        base.update(extra)
        return base

    def _post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_second_post_on_lost_lead_reactivates_without_overwriting_attribution(self):
        lost = Lead.objects.create(
            company=self.company, nom='Nadia Bennis',
            telephone='+212662000001', source=Lead.Source.SITE_WEB,
            canal=Lead.Canal.SITE_WEB, perdu=True,
            motif_perte='Trop cher', utm_source='facebook',
            utm_campaign='campagne_origine', stage=stages.COLD)
        Lead.objects.filter(pk=lost.pk).update(
            date_creation=timezone.now() - timezone.timedelta(days=5))

        resp = self._post(self._payload(
            utm={'utm_source': 'google', 'utm_campaign': 'campagne_nouvelle'}))
        self.assertEqual(resp.status_code, 200)

        lost.refresh_from_db()
        self.assertFalse(lost.perdu)
        self.assertNotEqual(lost.stage, stages.COLD)
        # First-touch d'origine préservé — jamais écrasé par le re-POST.
        self.assertEqual(lost.utm_source, 'facebook')
        self.assertEqual(lost.utm_campaign, 'campagne_origine')

        notes = LeadActivity.objects.filter(lead=lost)
        self.assertTrue(
            any('réactivation' in (n.body or '') for n in notes))

        # Toujours un seul lead pour ce numéro (pas de doublon).
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)

    def test_second_post_on_open_lead_does_not_touch_perdu(self):
        """Contrôle négatif : un lead ouvert (jamais perdu) n'écrit aucune
        activité de réactivation sur un re-POST."""
        open_lead = Lead.objects.create(
            company=self.company, nom='Nadia Bennis',
            telephone='+212662000001', source=Lead.Source.SITE_WEB,
            canal=Lead.Canal.SITE_WEB, stage=stages.CONTACTED)
        Lead.objects.filter(pk=open_lead.pk).update(
            date_creation=timezone.now() - timezone.timedelta(days=5))

        self._post(self._payload())

        open_lead.refresh_from_db()
        self.assertFalse(open_lead.perdu)
        notes = LeadActivity.objects.filter(lead=open_lead)
        self.assertFalse(
            any('réactivation' in (n.body or '') for n in notes))
