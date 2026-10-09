"""PUB62 — city_heatmap : CPL / coût-par-signature / ticket moyen PAR VILLE,
croisant le breakdown RÉGION Meta avec les villes réelles des leads + le
total TTC des devis acceptés. Villes sans donnée OMISES (jamais un « 0 »)."""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm.stages import NEW, SIGNED
from apps.ventes.models import Devis

from apps.adsengine import reporting
from apps.adsengine.models import AdCampaignMirror, InsightBreakdown


class CityHeatmapTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB62 Heatmap Co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_ville', name='Solaire MA',
            status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _breakdown(self, key, spend, day=datetime.date(2026, 7, 1)):
        InsightBreakdown.objects.create(
            company=self.company, content_type=self.ct,
            object_id=self.camp.pk, date=day,
            dimension=InsightBreakdown.Dimension.REGION, key=key,
            spend=Decimal(spend))

    def _lead(self, ville, *, signed=False, montant=None,
              canal=Lead.Canal.META_ADS):
        lead = Lead.objects.create(
            company=self.company, nom='Prospect', ville=ville,
            canal=canal, stage=SIGNED if signed else NEW)
        if signed and montant is not None:
            client = Client.objects.create(
                company=self.company, nom='C', prenom=ville)
            Devis.objects.create(
                company=self.company, reference=f'DEV-{lead.id}',
                client=client, lead=lead, taux_tva=Decimal('20'),
                statut=Devis.Statut.ACCEPTE)
        return lead

    def test_no_leads_no_regions_empty_table(self):
        result = reporting.city_heatmap(self.company)
        self.assertEqual(result['villes'], [])

    def test_city_without_region_match_has_no_cpl(self):
        self._lead('VilleInconnueXYZ')
        result = reporting.city_heatmap(self.company)
        v = result['villes'][0]
        self.assertEqual(v['ville'], 'VilleInconnueXYZ')
        self.assertIsNone(v['cpl'])
        self.assertIsNone(v['region_meta'])
        self.assertIsNone(v['spend'])

    def test_city_matched_to_region_computes_cpl(self):
        self._breakdown('Casablanca-Settat', '400.00')
        self._lead('Casablanca')
        self._lead('Casablanca')
        result = reporting.city_heatmap(self.company)
        v = result['villes'][0]
        self.assertEqual(v['region_meta'], 'Casablanca-Settat')
        self.assertEqual(v['leads'], 2)
        self.assertEqual(v['cpl'], '200.00')

    def test_signed_ticket_moyen_and_cout_par_signature(self):
        self._breakdown('Marrakech-Safi', '1000.00')
        self._lead('Marrakech', signed=True, montant=True)
        result = reporting.city_heatmap(self.company)
        v = result['villes'][0]
        self.assertEqual(v['signed'], 1)
        self.assertIsNotNone(v['ticket_moyen_ttc'])
        self.assertEqual(v['cout_par_signature'], '1000.00')

    def test_city_never_shows_fabricated_zero(self):
        # Une ville sans lead ET sans région correspondante n'apparaît pas.
        self._breakdown('Rabat-Salé-Kénitra', '50.00')
        result = reporting.city_heatmap(self.company)
        self.assertEqual(result['villes'], [])

    def test_period_filter_applied(self):
        self._breakdown('Fès-Meknès', '100.00', day=datetime.date(2026, 6, 1))
        lead = self._lead('Fès')
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=datetime.datetime(
                2026, 7, 15, 10, 0, tzinfo=datetime.timezone.utc))
        result = reporting.city_heatmap(
            self.company, date_start=datetime.date(2026, 7, 1),
            date_end=datetime.date(2026, 7, 31))
        v = result['villes'][0]
        # La dépense de juin est hors fenêtre juillet -> pas de correspondance.
        self.assertIsNone(v['cpl'])

    def test_depense_jamais_comptee_deux_fois(self):
        """AACQ11 — la dépense d'une région n'est comptée qu'une fois : seules
        les villes ayant des leads Meta DANS la fenêtre en reçoivent."""
        hier = datetime.date(2026, 7, 10)
        self._breakdown('Casablanca-Settat', '1000.00', day=hier)
        vieux = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        for _ in range(4):
            lead = self._lead('Casablanca', canal=Lead.Canal.SITE_WEB)
            Lead.objects.filter(pk=lead.pk).update(date_creation=vieux)
        for _ in range(6):
            lead = self._lead('Settat')
            Lead.objects.filter(pk=lead.pk).update(
                date_creation=datetime.datetime(
                    2026, 7, 10, 9, 0, tzinfo=datetime.timezone.utc))
        result = reporting.city_heatmap(
            self.company, date_start=hier, date_end=hier)
        villes = {v['ville']: v for v in result['villes']}
        self.assertNotIn('Casablanca', villes)
        self.assertEqual(villes['Settat']['leads'], 6)
        self.assertEqual(villes['Settat']['spend'], '1000.00')
        self.assertEqual(villes['Settat']['cpl'], '166.67')
        total = sum(Decimal(v['spend']) for v in result['villes'] if v['spend'])
        self.assertEqual(total, Decimal('1000.00'))
