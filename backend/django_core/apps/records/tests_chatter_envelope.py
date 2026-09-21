"""ARC9 — enveloppe de lecture UNIFORME des chatters historiques (étape 1).

Vérifie que les selectors ``lead_chatter_envelope`` (crm) et
``ticket_chatter_envelope`` (sav) projettent leurs modèles ``*Activity``
maison — de formes différentes — vers UN seul format, sérialisable par
``records.serializers.UniformChatterSerializer`` (le contrat consommé par
VX23 ChatterTimeline). Purement additif : aucune table modifiée, aucun
modèle legacy touché.

SOLMVP20 — l'exemple ``contrats.ContratActivity`` (app PARQUÉE, Groupe
SOLMVP) a été retiré ; ``sav.TicketActivity`` suffit à prouver l'uniformité
inter-apps.
"""
from testkit.base import TenantAPITestCase
from testkit.factories import ClientFactory

from apps.records.serializers import UniformChatterSerializer

# Les clés du contrat de lecture commun (l'enveloppe).
ENVELOPE_KEYS = {
    'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
    'body', 'user_username', 'created_at', 'source',
}


class TestUniformChatterEnvelope(TenantAPITestCase):
    def _assert_envelope(self, rows, source):
        """Sérialise via UniformChatterSerializer et vérifie le contrat."""
        data = UniformChatterSerializer(rows, many=True).data
        self.assertGreaterEqual(len(data), 1)
        for entry in data:
            self.assertEqual(set(entry.keys()), ENVELOPE_KEYS)
            self.assertEqual(entry['source'], source)
        return data

    def test_crm_lead_envelope(self):
        from apps.crm.models import Lead, LeadActivity
        from apps.crm.selectors import lead_chatter_envelope
        lead = Lead.objects.create(company=self.company, nom='Prospect')
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.NOTE, body='Appel passé')
        rows = lead_chatter_envelope(lead)
        data = self._assert_envelope(rows, 'crm.leadactivity')
        # La création du Lead auto-logge déjà une activité 'modification'
        # (chatter CRM existant) — on cible la note manuelle, pas l'index 0.
        notes = [r for r in data if r['kind'] == 'note']
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['body'], 'Appel passé')
        self.assertEqual(notes[0]['user_username'], self.user.username)

    def test_sav_ticket_envelope(self):
        from apps.sav.models import Ticket, TicketActivity
        from apps.sav.selectors import ticket_chatter_envelope
        client = ClientFactory(company=self.company)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-0001', client=client)
        TicketActivity.objects.create(
            company=self.company, ticket=ticket, user=self.user,
            kind=TicketActivity.Kind.MODIFICATION,
            field='statut', field_label='Statut',
            old_value='nouveau', new_value='en_cours')
        rows = ticket_chatter_envelope(ticket)
        data = self._assert_envelope(rows, 'sav.ticketactivity')
        self.assertEqual(data[0]['kind'], 'modification')
        self.assertEqual(data[0]['field_label'], 'Statut')
        self.assertEqual(data[0]['old_value'], 'nouveau')
        self.assertEqual(data[0]['new_value'], 'en_cours')

    def test_envelope_is_uniform_across_apps(self):
        """La MÊME forme sort des deux apps — le point de l'étape 1."""
        from apps.crm.models import Lead, LeadActivity
        from apps.crm.selectors import lead_chatter_envelope
        from apps.sav.models import Ticket, TicketActivity
        from apps.sav.selectors import ticket_chatter_envelope
        lead = Lead.objects.create(company=self.company, nom='P2')
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.NOTE, body='n1')
        client = ClientFactory(company=self.company)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-0002', client=client)
        TicketActivity.objects.create(
            company=self.company, ticket=ticket, user=self.user,
            kind=TicketActivity.Kind.NOTE, body='n2')
        d1 = UniformChatterSerializer(
            lead_chatter_envelope(lead), many=True).data
        d2 = UniformChatterSerializer(
            ticket_chatter_envelope(ticket), many=True).data
        self.assertEqual(set(d1[0].keys()), set(d2[0].keys()))
