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


class ProvenanceTests(TenantAPITestCase):
    """AMET22 (D-PROVENANCE) — `records.provenance` : une saisie humaine n'est
    jamais écrasée par un écrivain automatique ; le refus est journalisé."""

    def _cible(self):
        cible = ClientFactory(company=self.company)
        cible.telephone_whatsapp = '0611111111'
        cible.saisies_humaines = ['telephone_whatsapp']
        return cible

    def test_ecrire_si_libre_refuse_une_cle_saisie_et_journalise(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity
        from apps.records.provenance import MESSAGE_REFUS, ecrire_si_libre
        cible = self._cible()
        self.assertFalse(
            ecrire_si_libre(cible, 'telephone_whatsapp', '0600000000'))
        self.assertEqual(cible.telephone_whatsapp, '0611111111')
        journal = Activity.objects.filter(
            company=self.company, object_id=cible.pk, body=MESSAGE_REFUS,
            content_type=ContentType.objects.get_for_model(type(cible)))
        self.assertEqual(journal.count(), 1)
        self.assertEqual(journal.get().field, 'telephone_whatsapp')
        self.assertEqual(journal.get().new_value, '0600000000')

    def test_ecrire_si_libre_ecrit_un_champ_libre_sans_save(self):
        from apps.records.provenance import ecrire_si_libre
        cible = self._cible()
        nom_avant = type(cible).objects.get(pk=cible.pk).nom
        self.assertTrue(ecrire_si_libre(cible, 'nom', 'Nouveau nom'))
        self.assertEqual(cible.nom, 'Nouveau nom')
        # Aucun save() implicite : la base garde l'ancienne valeur.
        self.assertEqual(type(cible).objects.get(pk=cible.pk).nom, nom_avant)

    def test_marquer_saisie_humaine_trie_sans_doublon(self):
        from apps.records.provenance import marquer_saisie_humaine
        cible = self._cible()
        marquer_saisie_humaine(cible, ['email', 'telephone_whatsapp', 'email'])
        self.assertEqual(cible.saisies_humaines,
                         ['email', 'telephone_whatsapp'])

    def test_contrat_partage_provenance(self):
        import json
        from pathlib import Path

        from apps.records.provenance import (
            MESSAGE_REFUS, ecrire_si_libre, marquer_saisie_humaine)
        chemin = (Path(__file__).resolve().parent / 'contract_samples'
                  / 'provenance.json')
        exemple = json.loads(chemin.read_text(encoding='utf-8'))['exemple']
        cible = ClientFactory(company=self.company)
        marquer_saisie_humaine(cible, ['telephone_whatsapp', 'email'])
        self.assertEqual(cible.saisies_humaines, exemple['saisies_humaines'])
        self.assertEqual(MESSAGE_REFUS, exemple['message_refus'])
        self.assertEqual(
            ecrire_si_libre(cible, 'email', 'x@exemple.ma', journal=False),
            exemple['ecrire_si_libre']['champ_saisi'])
        self.assertEqual(
            ecrire_si_libre(cible, 'nom', 'Libre', journal=False),
            exemple['ecrire_si_libre']['champ_libre'])
