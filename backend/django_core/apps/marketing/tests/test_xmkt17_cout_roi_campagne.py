"""XMKT17 — Coût & ROI MAD par campagne.

Couvre : saisie des coûts, le ROI affiche dépensé vs revenu signé attribué
+ coût/lead, drill-down vers les leads sources.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne
from apps.crm.models import Lead
from apps.crm import stages
from testkit.factories import LigneDevisFactory


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CoutRoiCampagneTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt17', 'XMKT17')

    def test_cout_total_depuis_cout_reel(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            cout_reel_mad=Decimal('1500.00'))
        self.assertEqual(services.cout_total_campagne(camp), Decimal('1500.00'))

    def test_cout_total_depuis_lignes_libres(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL,
            lignes_cout=[
                {'libelle': 'Ads Meta', 'montant_mad': 300},
                {'libelle': 'Impression', 'montant_mad': 200},
            ])
        self.assertEqual(services.cout_total_campagne(camp), Decimal('500'))

    def test_cout_total_zero_sans_saisie(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL)
        self.assertEqual(services.cout_total_campagne(camp), Decimal('0'))

    def test_roi_rapproche_revenu_attribue(self):
        camp = Campagne.objects.create(
            company=self.co, nom='Promo Été', canal=Campagne.Canal.EMAIL,
            cout_reel_mad=Decimal('1000'))
        lead = Lead.objects.create(
            company=self.co, nom='Lead1', utm_campaign='Promo Été',
            stage=stages.SIGNED)
        ligne = LigneDevisFactory(
            devis__company=self.co, devis__lead=lead, devis__statut='accepte',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'))
        self.assertIsNotNone(ligne.devis_id)
        resultat = services.roi_campagne(camp)
        self.assertEqual(resultat['nb_leads'], 1)
        self.assertEqual(resultat['nb_signes'], 1)
        # HT 5000 x TVA 20% = 6000 TTC.
        self.assertEqual(Decimal(resultat['revenu_ttc_mad']), Decimal('6000'))
        self.assertGreater(resultat['roi_pct'], 0)

    def test_roi_division_par_zero_sans_leads(self):
        camp = Campagne.objects.create(
            company=self.co, nom='Vide', canal=Campagne.Canal.EMAIL,
            cout_reel_mad=Decimal('100'))
        resultat = services.roi_campagne(camp)
        self.assertEqual(resultat['nb_leads'], 0)
        self.assertEqual(resultat['cout_par_lead_mad'], 0.0)

    def test_drill_down_leads_sources(self):
        camp = Campagne.objects.create(
            company=self.co, nom='Drill', canal=Campagne.Canal.EMAIL)
        Lead.objects.create(
            company=self.co, nom='LeadDrill', utm_campaign='Drill')
        resultat = services.leads_source_roi(camp)
        self.assertEqual(len(resultat), 1)
        self.assertIn('LeadDrill', resultat[0]['nom'])

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt17-b', 'XMKT17-B')
        Lead.objects.create(
            company=other, nom='AutreSociete', utm_campaign='Fuite')
        camp = Campagne.objects.create(
            company=self.co, nom='Fuite', canal=Campagne.Canal.EMAIL)
        resultat = services.roi_campagne(camp)
        self.assertEqual(resultat['nb_leads'], 0)
