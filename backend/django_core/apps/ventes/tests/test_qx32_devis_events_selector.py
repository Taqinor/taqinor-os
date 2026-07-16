"""QX32be — selector devis_events_for_lead (timeline devis pour un lead).

Expose UNIQUEMENT le selector (la fusion dans l'historique crm est faite dans
la lane CRM/frontend). Sent/opened/signed/refused + résumé d'engagement.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, ShareLink
from apps.ventes.selectors import devis_events_for_lead

MONTH = timezone.now().strftime('%Y%m')


class Qx32DevisEventsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX32 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX32',
            telephone='+212600000058')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', telephone='+212600000058')

    def _devis(self, ref, **kw):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            lead=self.lead, taux_tva=Decimal('20'), **kw)

    def test_sent_and_signed_events(self):
        d = self._devis(
            f'DEV-{MONTH}-QX3201', statut=Devis.Statut.ACCEPTE,
            date_envoi=timezone.now(),
            date_acceptation=timezone.localdate())
        events = devis_events_for_lead(self.lead.id, self.company)
        kinds = {e['kind'] for e in events}
        self.assertIn('sent', kinds)
        self.assertIn('signed', kinds)
        self.assertTrue(all(e['devis_id'] == d.id for e in events))

    def test_opened_event_carries_engagement(self):
        d = self._devis(
            f'DEV-{MONTH}-QX3202', statut=Devis.Statut.ENVOYE,
            date_envoi=timezone.now())
        ShareLink.objects.create(
            company=self.company, devis=d,
            first_viewed_at=timezone.now(),
            engagement={'prix': {'seconds': 30, 'hits': 2}})
        events = devis_events_for_lead(self.lead.id, self.company)
        opened = [e for e in events if e['kind'] == 'opened']
        self.assertEqual(len(opened), 1)
        self.assertIn('prix', opened[0]['engagement'])

    def test_refused_event(self):
        self._devis(
            f'DEV-{MONTH}-QX3203', statut=Devis.Statut.REFUSE,
            date_envoi=timezone.now(), date_refus=timezone.localdate())
        events = devis_events_for_lead(self.lead.id, self.company)
        self.assertTrue(any(e['kind'] == 'refused' for e in events))

    def test_cross_company_isolation(self):
        other = Company.objects.create(nom='Other')
        events = devis_events_for_lead(self.lead.id, other)
        self.assertEqual(events, [])

    def test_no_prix_achat_in_events(self):
        self._devis(f'DEV-{MONTH}-QX3204', statut=Devis.Statut.ENVOYE,
                    date_envoi=timezone.now())
        events = devis_events_for_lead(self.lead.id, self.company)
        self.assertNotIn('prix_achat', str(events))
        self.assertNotIn('marge', str(events))
