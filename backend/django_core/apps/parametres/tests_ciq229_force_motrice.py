"""CIQ229 — la classe « force motrice » (atelier, chambre froide) se lit à la
grille officielle ONEE BT (trois tranches, lecture progressive étiquetée),
plus aux 0,95 DH/kWh non sourcés ; « agricole » est inchangé.

Calcul à la main (grille ``tarifs_officiels.BT_FORCE_MOTRICE``, TTC publiés) :
0-100 kWh à 1,3639 ; 100-500 à 1,4663 ; au-delà à 1,6758.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres import tariff
from apps.parametres.models_tariff import TariffSettings
from authentication.models import Company

User = get_user_model()

T1, T2, T3 = Decimal('1.3639'), Decimal('1.4663'), Decimal('1.6758')


def _kwh_a_la_main(mad):
    """kWh d'une facture d'énergie TTC aux trois tranches (au-delà de 500)."""
    cumul_500 = 100 * T1 + 400 * T2  # 136,39 + 586,52 = 722,91
    return Decimal('500') + (Decimal(mad) - cumul_500) / T3


def _reglages(**champs):
    return TariffSettings(redevance_compteur_mad_mois=Decimal('0.00'),
                          **champs)


class InversionForceMotriceTest(SimpleTestCase):
    def test_2000_mad_par_mois_aux_tranches_officielles(self):
        res = tariff.kwh_depuis_facture(_reglages(), Decimal('2000.00'),
                                        classe='force_motrice')
        attendu = _kwh_a_la_main('2000.00').quantize(
            Decimal('0.1'), rounding=ROUND_HALF_UP)
        self.assertEqual(attendu, Decimal('1262.1'))
        self.assertEqual(res['kwh'], attendu)
        self.assertIn('grille officielle ONEE BT force motrice',
                      res['motif'])
        self.assertIn('2026-10-03', res['motif'])
        self.assertIn('à confirmer sur facture', res['motif'])

    def test_facture_progressive_aux_trois_tranches(self):
        self.assertEqual(tariff.monthly_bill(_reglages(), 50, 'force_motrice'),
                         (50 * T1).quantize(Decimal('0.01')))
        self.assertEqual(
            tariff.monthly_bill(_reglages(), 600, 'force_motrice'),
            (100 * T1 + 400 * T2 + 100 * T3).quantize(Decimal('0.01')))

    def test_plus_jamais_095(self):
        s = _reglages(force_motrice_prix_kwh_ttc=Decimal('0.9500'))
        self.assertNotEqual(tariff.monthly_bill(s, 1000, 'force_motrice'),
                            Decimal('950.00'))


class AgricoleInchangeTest(SimpleTestCase):
    def test_agricole_identique_a_hier(self):
        s = _reglages(force_motrice_prix_kwh_ttc=Decimal('0.9500'))
        res = tariff.kwh_depuis_facture(s, Decimal('950.00'),
                                        classe='agricole')
        self.assertEqual(res['kwh'], Decimal('1000.0'))
        self.assertEqual(res['motif'], '')
        self.assertEqual(tariff.monthly_bill(s, 1000, 'agricole'),
                         Decimal('950.00'))
        self.assertEqual(tariff.monthly_bill(s, 1000, 'agricole'),
                         tariff.monthly_bill_force_motrice(s, 1000))


class SimulateurForceMotriceTest(TestCase):
    def setUp(self):
        company = Company.objects.get_or_create(
            slug='ciq229-co', defaults={'nom': 'CIQ229 Co'})[0]
        user = User.objects.create_user(
            username='ciq229_admin', password='x', role_legacy='admin',
            company=company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def test_simulateur_lit_la_grille_officielle(self):
        kwh = _kwh_a_la_main('2000.00')
        resp = self.api.post('/api/django/parametres/tarification/roi/', {
            'kwc': 0, 'conso_mensuelle_kwh': str(kwh), 'cout_total_ttc': 0,
            'classe': 'force_motrice'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertAlmostEqual(
            Decimal(resp.data['facture_mensuelle_ttc']), Decimal('2000.00'),
            delta=Decimal('0.01'))
        self.assertIn('grille officielle ONEE BT force motrice',
                      resp.data['motif_tarif'])
