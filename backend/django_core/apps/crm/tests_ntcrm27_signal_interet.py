"""NTCRM27 — Signal d'intérêt automatique depuis la salle de vente.

3 vues simulées en moins de 48h génèrent la note automatiquement ; une 4e vue
ne duplique pas la note du jour. Jamais un changement de stage automatique.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, LeadActivity, SalleVente, SalleVenteVue
from apps.crm.services import detecter_signal_interet_salle_vente


class SignalInteretServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM27', slug='taqinor-ntcrm27')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead QS27', stage=stages.QUOTE_SENT)
        self.salle = SalleVente.objects.create(
            company=self.company, lead=self.lead, titre='Salle NTCRM27')

    def test_3_vues_en_48h_generent_la_note(self):
        for _ in range(3):
            SalleVenteVue.objects.create(salle=self.salle)
        note = detecter_signal_interet_salle_vente(self.salle)
        self.assertIsNotNone(note)
        self.assertEqual(note.kind, LeadActivity.Kind.NOTE)
        self.assertIn("signal d'intérêt fort", note.body)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead, kind=LeadActivity.Kind.NOTE).count(), 1)
        # Le stage du lead n'est JAMAIS modifié automatiquement.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_4e_vue_meme_jour_ne_duplique_pas_la_note(self):
        for _ in range(4):
            SalleVenteVue.objects.create(salle=self.salle)
            detecter_signal_interet_salle_vente(self.salle)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead, kind=LeadActivity.Kind.NOTE).count(), 1)

    def test_moins_de_3_vues_ne_genere_rien(self):
        SalleVenteVue.objects.create(salle=self.salle)
        SalleVenteVue.objects.create(salle=self.salle)
        note = detecter_signal_interet_salle_vente(self.salle)
        self.assertIsNone(note)
        self.assertFalse(LeadActivity.objects.filter(lead=self.lead).exists())

    def test_lead_pas_en_quote_sent_ne_genere_rien(self):
        self.lead.stage = stages.NEW
        self.lead.save(update_fields=['stage'])
        for _ in range(3):
            SalleVenteVue.objects.create(salle=self.salle)
        note = detecter_signal_interet_salle_vente(self.salle)
        self.assertIsNone(note)

    def test_salle_sans_lead_ne_leve_jamais(self):
        salle_client = SalleVente.objects.create(company=self.company, titre='Sans lead')
        for _ in range(3):
            SalleVenteVue.objects.create(salle=salle_client)
        note = detecter_signal_interet_salle_vente(salle_client)
        self.assertIsNone(note)


class SignalInteretEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM27 API', slug='taqinor-ntcrm27-api')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead QS27 API', stage=stages.QUOTE_SENT)
        self.salle = SalleVente.objects.create(
            company=self.company, lead=self.lead, titre='Salle NTCRM27 API')

    def test_3_visites_publiques_generent_la_note_via_endpoint(self):
        anon = APIClient()
        for _ in range(3):
            resp = anon.get(f'/api/django/crm/salle-vente/{self.salle.token}/')
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead, kind=LeadActivity.Kind.NOTE).count(), 1)
