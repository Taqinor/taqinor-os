"""QJ8 — Déduplication renforcée du webhook site web (visiteur revenant).

Tests :
  - un visiteur revenant (re-POST le lendemain avec le même téléphone) est lié
    au lead existant — pas de doublon créé ;
  - un lead sans téléphone mais avec email déduplique par email ;
  - deux personnes différentes (téléphone ET email différents) créent deux leads ;
  - isolation cross-company : même email dans deux sociétés → deux leads séparés ;
  - l'attribution first-touch (UTM/fbclid) du lead existant est préservée ;
  - le chatter indique « visiteur revenant » (pas « doublon < 1 min »).

N.B. : les tests de la fenêtre < 60 s (dedup double-clic) sont dans
``tests_webhook.py`` (déjà en place) — on ne les duplique pas ici.
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity

SECRET = 'test-secret-qj8'


def payload_site(**extra):
    """Charge utile minimale valide pour le webhook."""
    base = {
        'fullName': 'Karim Alaoui',
        'phoneE164': '+212661000001',
        'whatsappOptIn': False,
        'city': 'Rabat',
        'roofType': 'villa',
        'billRange': '1500-3000',
        'qualified': True,
        'band': {'kwcLabel': '5 à 9 kWc', 'paybackLabel': '4 à 6 ans'},
        'utm': {
            'utm_source': 'facebook',
            'utm_medium': 'cpc',
            'utm_campaign': 'promo_ete',
        },
        'fbclid': 'fb.1.ABC.XYZ',
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class TestQJ8ReturningVisitorDedupe(TestCase):
    """Tests de la déduplication visiteur revenant (couche 2 — au-delà de 60 s)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor QJ8', slug='taqinor-qj8')
        self.url = reverse('website-lead-webhook')

    def post(self, data, secret=SECRET):
        headers = {'HTTP_X_WEBHOOK_SECRET': secret} if secret else {}
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json', **headers)

    def _make_existing_lead(self, telephone='+212661000001', email=None,
                            utm_source='facebook', fbclid='fb.1.ABC.XYZ'):
        """Crée un lead existant simulant une première visite."""
        lead = Lead.objects.create(
            company=self.company,
            nom='Karim Alaoui',
            telephone=telephone,
            email=email,
            source=Lead.Source.SITE_WEB,
            canal=Lead.Canal.SITE_WEB,
            utm_source=utm_source,
            utm_medium='cpc',
            utm_campaign='promo_ete',
            fbclid=fbclid,
        )
        # date_creation est auto_now_add (la valeur passée à create() est
        # ignorée) → on la force >60 s en arrière pour sortir de la fenêtre de
        # dédup courte et exercer la couche 2 (visiteur revenant).
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.now() - timezone.timedelta(days=2))
        lead.refresh_from_db()
        return lead

    # ── Test principal : visiteur revenant par téléphone ─────────────────────

    def test_returning_visitor_links_to_existing_lead(self):
        """Un re-POST avec le même téléphone crée un doublon — le webhook doit
        le détecter et mettre à jour le lead existant."""
        existing = self._make_existing_lead()
        initial_count = Lead.objects.count()

        # Re-POST deux jours plus tard (hors fenêtre de 60 s)
        res = self.post(payload_site(city='Casablanca'))
        self.assertEqual(res.status_code, 200, res.content)
        # Aucun nouveau lead ne doit avoir été créé
        self.assertEqual(Lead.objects.count(), initial_count)
        # Le lead existant a été mis à jour
        existing.refresh_from_db()
        self.assertEqual(existing.ville, 'Casablanca')

    def test_returning_visitor_chatter_note(self):
        """Le chatter indique « visiteur revenant », pas « doublon < 1 min »."""
        existing = self._make_existing_lead()
        res = self.post(payload_site())
        self.assertEqual(res.status_code, 200, res.content)
        note = LeadActivity.objects.filter(
            lead=existing, kind=LeadActivity.Kind.NOTE).last()
        self.assertIsNotNone(note)
        self.assertIn('revenant', note.body.lower())

    def test_returning_visitor_preserves_first_touch_attribution(self):
        """L'attribution first-touch (UTM/fbclid) du lead existant n'est pas écrasée."""
        existing = self._make_existing_lead(
            utm_source='facebook', fbclid='fb.1.ABC.ORIGINAL')
        # Re-POST avec une NOUVELLE attribution (campagne différente)
        res = self.post(payload_site(
            fbclid='fb.2.NEW.FBCLID',
            utm={'utm_source': 'instagram', 'utm_medium': 'organic',
                 'utm_campaign': 'nouvelle_campagne'},
        ))
        self.assertEqual(res.status_code, 200, res.content)
        existing.refresh_from_db()
        # Attribution d'origine préservée
        self.assertEqual(existing.fbclid, 'fb.1.ABC.ORIGINAL')
        self.assertEqual(existing.utm_source, 'facebook')

    # ── Test : lead sans téléphone déduplique par email ───────────────────────

    def test_phoneless_lead_dedupes_by_email(self):
        """Un lead sans téléphone déduplique par email."""
        existing = Lead.objects.create(
            company=self.company,
            nom='Sara Bennis',
            telephone=None,
            email='sara@example.ma',
            source=Lead.Source.SITE_WEB,
            canal=Lead.Canal.SITE_WEB,
            date_creation=timezone.now() - timezone.timedelta(days=1),
        )
        initial_count = Lead.objects.count()
        # Re-POST sans téléphone, même email
        res = self.post(payload_site(
            fullName='Sara Bennis',
            phoneE164='',
            phone='',
            email='sara@example.ma',
            city='Marrakech',
        ))
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(Lead.objects.count(), initial_count)
        existing.refresh_from_db()
        self.assertEqual(existing.ville, 'Marrakech')

    # ── Test : deux personnes différentes → deux leads séparés ───────────────

    def test_different_people_create_separate_leads(self):
        """Deux téléphones différents → deux leads, pas de fusion."""
        self._make_existing_lead(telephone='+212661000001')
        res = self.post(payload_site(
            fullName='Autre Personne',
            phoneE164='+212661000099',
        ))
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(Lead.objects.count(), 2)

    def test_different_email_no_phone_creates_new_lead(self):
        """Email différent → nouveau lead."""
        Lead.objects.create(
            company=self.company,
            nom='Autre Client',
            telephone=None,
            email='autre@example.ma',
            source=Lead.Source.SITE_WEB,
            date_creation=timezone.now() - timezone.timedelta(days=1),
        )
        res = self.post(payload_site(
            fullName='Nouveau Client',
            phoneE164='',
            phone='',
            email='nouveau@example.ma',
        ))
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(Lead.objects.count(), 2)

    # ── Test : isolation cross-company ─────────────────────────────────────────

    def test_cross_company_isolation(self):
        """Même email dans deux sociétés → deux leads séparés, jamais fusionnés."""
        company_b = Company.objects.create(
            nom='Autre Société QJ8', slug='autre-qj8')
        # Lead dans la société B avec le même email
        Lead.objects.create(
            company=company_b,
            nom='Ali Benali',
            telephone='+212661000001',
            email='ali@example.ma',
            source=Lead.Source.SITE_WEB,
            date_creation=timezone.now() - timezone.timedelta(days=1),
        )
        # Le webhook résout toujours `company` = self.company (WEBSITE_LEADS_COMPANY_ID)
        initial_a = Lead.objects.filter(company=self.company).count()
        res = self.post(payload_site(
            fullName='Ali Benali',
            phoneE164='+212661000001',
        ))
        # Un NOUVEAU lead doit être créé dans self.company (pas de dédup cross-company)
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(Lead.objects.filter(company=self.company).count(),
                         initial_a + 1)
        # Le lead de company_b est intact
        self.assertEqual(Lead.objects.filter(company=company_b).count(), 1)

    # ── Test : le lead_id retourné est celui du lead existant ─────────────────

    def test_returning_visitor_response_references_existing_lead(self):
        """La réponse JSON contient le lead_id du lead existant, pas un nouveau."""
        existing = self._make_existing_lead()
        res = self.post(payload_site())
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['lead_id'], existing.pk)
