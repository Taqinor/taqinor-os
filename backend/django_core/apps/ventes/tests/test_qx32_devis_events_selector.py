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

    def test_acal1233_signe_porte_l_heure_de_l_activite_d_acceptation(self):
        """ACAL1233 — « Devis signé » = horodatage de l'activité (15 h 20),
        jamais minuit UTC d'une date ; sans activité, la date seule."""
        from datetime import datetime, timezone as dt_tz
        from apps.ventes.activity import log_devis_acceptance
        from apps.ventes.models import DevisActivity
        d = self._devis(
            f'DEV-{MONTH}-QX3205', statut=Devis.Statut.ACCEPTE,
            date_acceptation=timezone.localdate())
        sans = devis_events_for_lead(self.lead.id, self.company)
        self.assertEqual(
            [e['at'] for e in sans if e['kind'] == 'signed'],
            [d.date_acceptation.isoformat()])
        act = log_devis_acceptance(d, None, 'Reda K.', d.date_acceptation)
        quand = datetime(2026, 11, 22, 15, 20, tzinfo=dt_tz.utc)
        DevisActivity.objects.filter(pk=act.pk).update(created_at=quand)
        events = devis_events_for_lead(self.lead.id, self.company)
        signed = [e for e in events if e['kind'] == 'signed']
        self.assertEqual(signed[0]['at'], quand.isoformat())

    def test_acal1235_signe_porte_le_nom_de_l_acteur(self):
        """ACAL1235 — `user_nom` = nom de l'utilisateur de l'acceptation."""
        from django.contrib.auth import get_user_model
        from apps.ventes.activity import log_devis_acceptance
        u = get_user_model().objects.create_user(
            username='acal1235', password='x', company=self.company)

        d = self._devis(
            f'DEV-{MONTH}-QX3206', statut=Devis.Statut.ACCEPTE,
            date_acceptation=timezone.localdate())
        log_devis_acceptance(d, u, '', d.date_acceptation)
        events = devis_events_for_lead(self.lead.id, self.company)
        signed = [e for e in events if e['kind'] == 'signed'][0]
        self.assertEqual(signed['user_nom'], 'acal1235')

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
