"""XMKT28 — Événements marketing légers (salons, portes ouvertes, webinaires).

Couvre : créer un événement, inscrire (public), pointer les présences,
leads créés sans doublon, segment « présents événement X » ciblable.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import (
    EvenementMarketing, InscriptionEvenement, SegmentMarketing,
)
from apps.crm.models import Lead


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class EvenementsMarketingTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt28', 'XMKT28')
        self.evt = EvenementMarketing.objects.create(
            company=self.co, nom='SIAM 2026',
            type_evenement=EvenementMarketing.Type.SALON,
            date_debut=timezone.now() + datetime.timedelta(days=10))

    def test_creation_evenement(self):
        self.assertEqual(
            EvenementMarketing.objects.filter(company=self.co).count(), 1)

    def test_inscription_publique_cree_lead(self):
        inscription = services.inscrire_evenement(
            self.evt, nom='Ahmed', email='ahmed@x.ma', telephone='0612345678')
        self.assertIsNotNone(inscription.lead_id)
        self.assertTrue(Lead.objects.filter(id=inscription.lead_id).exists())

    def test_inscription_publique_endpoint(self):
        resp = self.client.post(
            f'/api/django/compta/evenements-marketing/{self.evt.id}/'
            'inscription-publique/',
            data={'nom': 'Fatima', 'email': 'fatima@x.ma'},
            content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.json()['qr_token'])

    def test_inscription_dedupliquee_meme_email(self):
        insc1 = services.inscrire_evenement(
            self.evt, nom='Karim', email='karim@x.ma')
        insc2 = services.inscrire_evenement(
            self.evt, nom='Karim K.', email='karim@x.ma')
        self.assertEqual(insc1.lead_id, insc2.lead_id)
        self.assertEqual(
            Lead.objects.filter(company=self.co, email='karim@x.ma').count(), 1)

    def test_pointer_presence(self):
        inscription = services.inscrire_evenement(self.evt, nom='Sara')
        services.pointer_presence(inscription)
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, InscriptionEvenement.Statut.PRESENT)
        self.assertIsNotNone(inscription.date_pointage)

    def test_pointer_presence_idempotent(self):
        inscription = services.inscrire_evenement(self.evt, nom='Sara2')
        services.pointer_presence(inscription)
        premier_pointage = inscription.date_pointage
        services.pointer_presence(inscription)
        inscription.refresh_from_db()
        self.assertEqual(inscription.date_pointage, premier_pointage)

    def test_cloturer_marque_absents_non_pointes(self):
        insc_present = services.inscrire_evenement(self.evt, nom='Present')
        services.pointer_presence(insc_present)
        insc_absent = services.inscrire_evenement(self.evt, nom='Absent')
        nb = services.cloturer_presences_evenement(self.evt)
        self.assertEqual(nb, 1)
        insc_absent.refresh_from_db()
        self.assertEqual(insc_absent.statut, InscriptionEvenement.Statut.ABSENT)
        insc_present.refresh_from_db()
        self.assertEqual(insc_present.statut, InscriptionEvenement.Statut.PRESENT)

    def test_segment_cible_presents_evenement(self):
        inscription = services.inscrire_evenement(
            self.evt, nom='PresentSegment', email='presentseg@x.ma')
        services.pointer_presence(inscription)
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Présents SIAM',
            regles={'evenement_present': self.evt.id})
        lead_ids = services.evaluer_segment(segment)
        self.assertIn(inscription.lead_id, lead_ids)

    def test_segment_evenement_absent_exclut_presents(self):
        inscription = services.inscrire_evenement(
            self.evt, nom='PresentSegment2', email='presentseg2@x.ma')
        services.pointer_presence(inscription)
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Absents SIAM',
            regles={'evenement_absent': self.evt.id})
        lead_ids = services.evaluer_segment(segment)
        self.assertNotIn(inscription.lead_id, lead_ids)
