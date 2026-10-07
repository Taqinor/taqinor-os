"""ALEA2 (D-ALEA-2, option a) — un lead Froid OU Perdu est réveillé quand il
refait le formulaire du site.

Constat C-ALEA-027 : la réactivation (`reactivate_lead_on_new_touch`) n'était
appelée par AUCUN point d'entrée vivant du site (le test YLEAD11 appelait la
fonction feuille — mock-vs-réel). Ces tests passent par le POINT D'ENTRÉE
RÉEL : le webhook du site, sans aucun mock.
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from core import events

SECRET = 'test-secret-alea2'
NOTE = 'Nouvelle demande reçue (site web)'


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class ReactivationPointEntreeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA2', slug='taqinor-alea2')
        self.url = reverse('website-lead-webhook')
        self.changements = []

        def _ecoute(sender, **kw):
            self.changements.append(
                (getattr(kw.get('lead'), 'pk', None), kw.get('old_stage'),
                 kw.get('new_stage')))

        events.lead_stage_changed.connect(_ecoute, weak=False)
        self.addCleanup(events.lead_stage_changed.disconnect, _ecoute)

    def _lead(self, telephone, **kw):
        lead = Lead.objects.create(
            company=self.company, nom='Bennis', prenom='Nadia',
            telephone=telephone, source=Lead.Source.SITE_WEB,
            canal=Lead.Canal.SITE_WEB, **kw)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.now() - timezone.timedelta(days=40))
        lead.refresh_from_db()
        return lead

    def _post(self, telephone, cle):
        return self.client.post(
            self.url, data=json.dumps({
                'fullName': 'Nadia Bennis',
                'phoneE164': telephone,
                'city': 'Marrakech',
                'roofType': 'villa',
                'billRange': '1500-3000',
                'qualified': True,
                'idempotencyKey': cle,
            }),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def _notes(self, lead):
        return LeadActivity.objects.filter(lead=lead, body__contains=NOTE)

    def test_formulaire_reveille_froid(self):
        froid = self._lead('+212662100001', stage=stages.COLD)

        resp = self._post('+212662100001', 'alea2-froid')

        self.assertEqual(resp.status_code, 201, resp.content)
        froid.refresh_from_db()
        self.assertNotEqual(froid.stage, stages.COLD)
        self.assertFalse(froid.perdu)
        self.assertTrue(self._notes(froid).exists())
        # Sortie par le point de passage canonique : signal émis.
        self.assertIn((froid.pk, stages.COLD, froid.stage), self.changements)
        # Reprise CAD107 posée.
        self.assertTrue(RelanceEtape.objects.filter(lead=froid).exists())

    def test_formulaire_reveille_perdu(self):
        perdu = self._lead('+212662100002', stage=stages.COLD, perdu=True,
                           motif_perte='Trop cher')

        resp = self._post('+212662100002', 'alea2-perdu')

        self.assertEqual(resp.status_code, 201, resp.content)
        perdu.refresh_from_db()
        self.assertFalse(perdu.perdu)
        self.assertNotEqual(perdu.stage, stages.COLD)
        self.assertTrue(self._notes(perdu).exists())
        self.assertTrue(RelanceEtape.objects.filter(lead=perdu).exists())

    def test_lead_ouvert_note_seule(self):
        ouvert = self._lead('+212662100003', stage=stages.QUOTE_SENT)

        resp = self._post('+212662100003', 'alea2-ouvert')

        self.assertEqual(resp.status_code, 201, resp.content)
        ouvert.refresh_from_db()
        self.assertEqual(ouvert.stage, stages.QUOTE_SENT)
        self.assertFalse(self._notes(ouvert).exists())
        self.assertNotIn(ouvert.pk, [c[0] for c in self.changements])
        # Le seul signal reste la note « Doublon possible » sur la NOUVELLE
        # fiche, comme avant.
        nouveau = Lead.objects.get(pk=resp.json()['lead_id'])
        self.assertTrue(LeadActivity.objects.filter(
            lead=nouveau, body__startswith='Doublon possible').exists())

    def test_rejeu_idempotent(self):
        froid = self._lead('+212662100004', stage=stages.COLD)

        self._post('+212662100004', 'alea2-rejeu')
        froid.refresh_from_db()
        etape_apres = froid.stage
        touches_apres = RelanceEtape.objects.filter(lead=froid).count()
        self._post('+212662100004', 'alea2-rejeu')

        froid.refresh_from_db()
        self.assertEqual(froid.stage, etape_apres)
        self.assertFalse(froid.perdu)
        self.assertEqual(self._notes(froid).count(), 1)
        self.assertEqual(
            RelanceEtape.objects.filter(lead=froid).count(), touches_apres)
        self.assertGreaterEqual(touches_apres, 1)
