"""
QJR585 (Groupe QJR5) — un seul résolveur « quel lead lit ce devis » :
``crm.selectors.lead_du_devis(devis)`` = devis.lead, sinon le lead le plus
récent du client (borné société). Un devis client-sans-lead lit désormais la
ville, le GPS, les équipements et l'occupation du MÊME lead que ses factures.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_lead_du_devis"
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm import selectors
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from authentication.models import Company


class TestLeadDuDevis(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR585 Co', slug='qjr585-co')
        self.autre = Company.objects.create(
            nom='QJR585 Autre', slug='qjr585-autre')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR585')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead QJR585', client=self.client_obj,
            ville='Berrechid', gps_lat=Decimal('33.26'),
            gps_lng=Decimal('-7.58'), adresse='Douar X',
            equip_clim=True, occupation_jour='present',
            facture_hiver=Decimal('900'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR585-1',
            client=self.client_obj, statut='brouillon')

    def test_resolveur_repli_sur_le_lead_du_client(self):
        self.assertEqual(selectors.lead_du_devis(self.devis), self.lead)

    def test_lead_lie_prime(self):
        autre_lead = Lead.objects.create(company=self.company, nom='Lié')
        self.devis.lead = autre_lead
        self.assertEqual(selectors.lead_du_devis(self.devis), autre_lead)

    def test_borne_societe(self):
        etranger = Devis.objects.create(
            company=self.autre, reference='DEV-QJR585-X',
            client=self.client_obj, statut='brouillon')
        self.assertIsNone(selectors.lead_du_devis(etranger))

    def test_equipements_site_occupation_rendent_ce_lead(self):
        self.assertTrue(selectors.equipements_pour_devis(self.devis)['clim'])
        site = selectors.site_location_for_devis(self.devis)
        self.assertEqual(site['site_ville'], 'Berrechid')
        self.assertEqual(Decimal(str(site['gps_lat'])), Decimal('33.26'))
        self.assertEqual(
            selectors.occupation_jour_pour_devis(self.devis), 'present')
        # Les factures suivaient déjà ce lead : désormais le reste aussi.
        self.assertEqual(
            selectors.lead_bills_for_devis(self.devis)['facture_hiver'], 900.0)

    def test_attribution_comparaison_reste_stricte(self):
        # Devis ACCEPTÉ sans lead lié : pas de repli pour l'attribution.
        self.devis.statut = 'accepte'
        self.assertIsNone(
            selectors.attribution_comparaison_devis(self.devis))
