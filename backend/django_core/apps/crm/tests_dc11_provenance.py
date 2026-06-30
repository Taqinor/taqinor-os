"""DC11 — provenance des valeurs énergie/toiture reprises du lead.

Les valeurs énergie/toiture recopiées dans ``Devis.etude_params`` portent une
estampille ``{source_lead_id, captured_at, valeurs}`` ; un changement du lead
APRÈS capture est détecté (bannière « valeurs du lead modifiées depuis »).
Multi-tenant : la détection est scopée société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm import selectors


class TestLeadProvenance(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='dc11-co', defaults={'nom': 'DC11 Co'})[0]
        self.other = Company.objects.create(slug='dc11-other', nom='Autre')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect',
            facture_hiver=Decimal('1200'), facture_ete=Decimal('800'),
            ete_differente=True, type_toiture='tuiles', orientation='sud',
            surface_toiture_m2=Decimal('60'))

    def test_stamp_carries_source_lead_and_valeurs(self):
        stamp = selectors.lead_provenance_stamp(self.lead)
        self.assertEqual(stamp['source_lead_id'], self.lead.pk)
        self.assertIn('captured_at', stamp)
        self.assertEqual(stamp['valeurs']['facture_hiver'], '1200')
        self.assertEqual(stamp['valeurs']['facture_ete'], '800')
        self.assertEqual(stamp['valeurs']['ete_differente'], True)
        self.assertEqual(stamp['valeurs']['type_toiture'], 'tuiles')

    def test_stamp_none_without_lead(self):
        self.assertIsNone(selectors.lead_provenance_stamp(None))

    def test_no_change_returns_empty(self):
        stamp = selectors.lead_provenance_stamp(self.lead)
        self.assertEqual(
            selectors.lead_values_changed_since(stamp, company=self.company),
            [])

    def test_detects_changed_fields(self):
        stamp = selectors.lead_provenance_stamp(self.lead)
        self.lead.facture_hiver = Decimal('1500')
        self.lead.orientation = 'est'
        self.lead.save(update_fields=['facture_hiver', 'orientation'])
        changed = selectors.lead_values_changed_since(
            stamp, company=self.company)
        self.assertIn('facture_hiver', changed)
        self.assertIn('orientation', changed)
        self.assertNotIn('facture_ete', changed)

    def test_empty_stamp_no_false_alert(self):
        self.assertEqual(selectors.lead_values_changed_since(None), [])
        self.assertEqual(selectors.lead_values_changed_since({}), [])

    def test_scoped_to_company(self):
        # Un stamp d'un lead d'une autre société ne lève pas de fausse alerte
        # quand on filtre sur la société courante (lead introuvable → []).
        stamp = selectors.lead_provenance_stamp(self.lead)
        self.lead.facture_hiver = Decimal('9999')
        self.lead.save(update_fields=['facture_hiver'])
        self.assertEqual(
            selectors.lead_values_changed_since(stamp, company=self.other),
            [])
