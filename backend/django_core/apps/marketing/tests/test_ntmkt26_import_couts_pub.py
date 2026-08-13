"""NTMKT26 — Import de coûts publicitaires externes (Meta/Google Ads).

Aucun appel API externe : un CSV exporté à la main est réconcilié par nom de
campagne avec ``Campagne.cout_reel_mad``. Un rapport matché/non-matché est
toujours renvoyé, jamais une exception sur une ligne malformée.
"""
from django.test import TestCase

from authentication.models import Company

from apps.marketing import services as mkt_services
from apps.marketing.models import Campagne


class ImporterCoutsPublicitairesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt26', nom='NTMKT26')
        self.c1 = Campagne.objects.create(company=self.co, nom='Promo Rentree')
        self.c2 = Campagne.objects.create(company=self.co, nom='Newsletter Juin')

    def _csv(self, lignes):
        header = 'nom_campagne,cout\n'
        return (header + '\n'.join(lignes)).encode('utf-8')

    def test_met_a_jour_le_cout_reel_par_nom(self):
        csv = self._csv(['Promo Rentree,1500.50', 'Newsletter Juin,320'])
        rapport = mkt_services.importer_couts_publicitaires(
            self.co, csv, 'export.csv')
        self.assertEqual(len(rapport['matched']), 2)
        self.assertEqual(len(rapport['unmatched']), 0)
        self.c1.refresh_from_db()
        self.c2.refresh_from_db()
        self.assertEqual(str(self.c1.cout_reel_mad), '1500.50')
        self.assertEqual(str(self.c2.cout_reel_mad), '320')

    def test_campagne_inconnue_est_rapportee_non_matchee(self):
        csv = self._csv(['Campagne Fantome,100'])
        rapport = mkt_services.importer_couts_publicitaires(
            self.co, csv, 'export.csv')
        self.assertEqual(len(rapport['matched']), 0)
        self.assertEqual(len(rapport['unmatched']), 1)
        self.assertEqual(rapport['unmatched'][0]['nom_campagne'],
                         'Campagne Fantome')

    def test_cout_illisible_ne_leve_jamais(self):
        csv = self._csv(['Promo Rentree,pas-un-nombre'])
        rapport = mkt_services.importer_couts_publicitaires(
            self.co, csv, 'export.csv')
        self.assertEqual(len(rapport['matched']), 0)
        self.assertEqual(len(rapport['unmatched']), 1)

    def test_scoping_societe_aucune_fuite(self):
        autre = Company.objects.create(slug='ntmkt26b', nom='Autre')
        Campagne.objects.create(company=autre, nom='Promo Rentree')
        csv = self._csv(['Promo Rentree,999'])
        rapport = mkt_services.importer_couts_publicitaires(
            self.co, csv, 'export.csv')
        self.assertEqual(len(rapport['matched']), 1)
        self.assertEqual(rapport['matched'][0]['campagne_id'], self.c1.id)

    def test_endpoint_exige_une_authentification(self):
        res = self.client.post('/api/django/marketing/campagnes/importer-couts/')
        self.assertIn(res.status_code, (401, 403))
