"""XMKT16 — Touches marketing sur le chatter du lead (vue 360°).

Couvre : l'envoi de campagne, l'ouverture, le clic et l'exécution d'une
étape de séquence écrivent chacun UNE LeadActivity + UN PointContact
(FG204) ; volumétrie maîtrisée (jamais par batch, jamais de doublon sur un
rejeu de webhook) ; jamais d'import du modèle crm depuis compta.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Campagne, EtapeSequence, SequenceRelance
from apps.crm.models import Lead, LeadActivity, PointContact

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ChatterMarketingTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt16', 'XMKT16')

    def test_envoi_campagne_note_le_chatter(self):
        lead = Lead.objects.create(company=self.co, nom='A')
        camp = Campagne.objects.create(
            company=self.co, nom='Réveil', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=[
            {'destinataire': 'a@x.ma', 'contact_ref': f'lead:{lead.id}'},
        ])
        activites = LeadActivity.objects.filter(lead=lead, kind='note')
        self.assertEqual(activites.count(), 1)
        self.assertIn('Réveil', activites.first().body)
        self.assertEqual(
            PointContact.objects.filter(lead=lead).count(), 1)

    def test_envoi_sans_contact_ref_ne_cree_rien(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['sans-ref@x.ma'])
        self.assertEqual(LeadActivity.objects.count(), 0)
        self.assertEqual(PointContact.objects.count(), 0)

    def test_ouverture_note_une_seule_fois_meme_rejoue(self):
        lead = Lead.objects.create(company=self.co, nom='A')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=[
            {'destinataire': 'a@x.ma', 'contact_ref': f'lead:{lead.id}'},
        ])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='a@x.ma',
            evenement='opened')
        # Rejeu du même événement (webhook idempotent côté fournisseur).
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='a@x.ma',
            evenement='opened')
        activites_ouverture = LeadActivity.objects.filter(
            lead=lead, body__icontains='ouverte')
        self.assertEqual(activites_ouverture.count(), 1)

    def test_clic_note_le_chatter(self):
        lead = Lead.objects.create(company=self.co, nom='A')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=[
            {'destinataire': 'a@x.ma', 'contact_ref': f'lead:{lead.id}'},
        ])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='a@x.ma',
            evenement='click')
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=lead, body__icontains='cliquée').exists())

    def test_etape_sequence_executee_note_le_chatter(self):
        lead = Lead.objects.create(company=self.co, nom='A')
        seq = SequenceRelance.objects.create(company=self.co, nom='Drip')
        EtapeSequence.objects.create(
            company=self.co, sequence=seq, ordre=1, delai_jours=0)
        services.inscrire_lead_sequence(self.co, seq, lead_id=lead.id)
        services.executer_etapes_dues(self.co)
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=lead, body__icontains='Drip').exists())

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt16-b', 'XMKT16-B')
        lead_a = Lead.objects.create(company=self.co, nom='A')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=[
            {'destinataire': 'a@x.ma', 'contact_ref': f'lead:{lead_a.id}'},
        ])
        self.assertEqual(
            LeadActivity.objects.filter(lead__company=other).count(), 0)
