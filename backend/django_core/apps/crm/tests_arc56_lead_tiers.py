"""ARC56 — Pont Tiers : crm.Lead (identité pré-conversion).

On prouve :
  - résoudre le client d'un lead rattache le lead au MÊME Tiers que le client
    (celui posé par le miroir ARC18 crm.Client → Tiers) ;
  - un lead déjà lié à un client hérite du même Tiers (chemin early-return) ;
  - aucun champ de NOM du lead n'est modifié (QW7) ;
  - isolation multi-société.
"""
from django.test import TestCase

from testkit.factories import CompanyFactory, another_tenant

from apps.crm.models import Client, Lead
from apps.crm.services import resolve_client_for_lead


class Arc56LeadTiersTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other_company, _ = another_tenant()

    def test_resolve_attaches_same_tiers_as_client(self):
        lead = Lead.objects.create(
            company=self.company, nom='Prospect', prenom='Amine',
            email='amine@example.ma')
        client = resolve_client_for_lead(lead)
        client.refresh_from_db()
        lead.refresh_from_db()
        self.assertIsNotNone(client.tiers_id)
        # Le lead pointe le MÊME Tiers que le client résolu.
        self.assertEqual(lead.tiers_id, client.tiers_id)

    def test_already_linked_lead_inherits_client_tiers(self):
        client = Client.objects.create(
            company=self.company, nom='Déjà', email='deja@example.ma')
        client.refresh_from_db()  # miroir ARC18 → client.tiers posé
        lead = Lead.objects.create(
            company=self.company, nom='Prospect', client=client)
        # Chemin early-return (lead.client_id déjà présent).
        resolve_client_for_lead(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.tiers_id, client.tiers_id)

    def test_lead_name_fields_untouched(self):
        # QW7 : le pont ne modifie AUCUN champ de nom du lead.
        lead = Lead.objects.create(
            company=self.company, nom='NomOriginal', prenom='PrenomOriginal',
            email='qw7@example.ma')
        resolve_client_for_lead(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'NomOriginal')
        self.assertEqual(lead.prenom, 'PrenomOriginal')

    def test_lead_tiers_is_company_scoped(self):
        lead = Lead.objects.create(
            company=self.company, nom='P', email='scoped@example.ma')
        client = resolve_client_for_lead(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.tiers.company_id, self.company.id)
        self.assertEqual(client.tiers.company_id, self.company.id)
