"""NTLOG20 — émissions CO2 estimées : facteur d'émission éditable en
Paramètres, recalcul immédiat sur les ordres non clôturés."""
from decimal import Decimal

from django.db.utils import IntegrityError
from django.test import TestCase

from apps.transport.models import (
    FacteurEmissionCO2, LigneOrdreTransport, OrdreTransport,
)

from ._helpers import auth, make_company, make_user

ORDRES_BASE = '/api/django/transport/ordres-transport/'
FACTEURS_BASE = '/api/django/transport/facteurs-emission-co2/'


class Co2EstimationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-co2-a', 'A')
        self.user_a = make_user(self.co_a, 'transport-co2-a')
        self.ordre = OrdreTransport.objects.create(
            company=self.co_a,
            mode_acheminement_physique=OrdreTransport.ModeAcheminementPhysique.ROUTE,
            distance_km=Decimal('100.0'))
        LigneOrdreTransport.objects.create(
            company=self.co_a, ordre=self.ordre, poids_kg=Decimal('2000.00'))
        FacteurEmissionCO2.objects.create(
            company=self.co_a, mode=FacteurEmissionCO2.Mode.ROUTE,
            facteur_kg_co2_par_tonne_km=Decimal('0.1000'))

    def test_estimation_calculee(self):
        from apps.transport import selectors

        data = selectors.estimer_co2_transport(self.ordre.id, company=self.co_a)
        # 2 tonnes x 100 km x 0.1 kgCO2/t.km = 20 kgCO2.
        self.assertEqual(data['estimation_kg_co2'], Decimal('20.000'))

    def test_recalcul_immediat_apres_edition_du_facteur(self):
        from apps.transport import selectors

        facteur = FacteurEmissionCO2.objects.get(
            company=self.co_a, mode=FacteurEmissionCO2.Mode.ROUTE)
        auth(self.user_a).patch(
            f'{FACTEURS_BASE}{facteur.id}/',
            {'facteur_kg_co2_par_tonne_km': '0.2000'}, format='json')
        data = selectors.estimer_co2_transport(self.ordre.id, company=self.co_a)
        self.assertEqual(data['estimation_kg_co2'], Decimal('40.000'))

    def test_sans_distance_renvoie_motif(self):
        self.ordre.distance_km = None
        self.ordre.save(update_fields=['distance_km'])
        from apps.transport import selectors

        data = selectors.estimer_co2_transport(self.ordre.id, company=self.co_a)
        self.assertIsNone(data['estimation_kg_co2'])
        self.assertIn('motif', data)

    def test_sans_facteur_configure_renvoie_motif(self):
        FacteurEmissionCO2.objects.filter(company=self.co_a).delete()
        from apps.transport import selectors

        data = selectors.estimer_co2_transport(self.ordre.id, company=self.co_a)
        self.assertIsNone(data['estimation_kg_co2'])
        self.assertIn('motif', data)

    def test_endpoint_ordre_detail_co2(self):
        resp = auth(self.user_a).get(f'{ORDRES_BASE}{self.ordre.id}/co2/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('libelle', resp.data)
        self.assertIn('non certifiée', resp.data['libelle'])

    def test_facteur_unique_par_societe_et_mode(self):
        with self.assertRaises(IntegrityError):
            FacteurEmissionCO2.objects.create(
                company=self.co_a, mode=FacteurEmissionCO2.Mode.ROUTE,
                facteur_kg_co2_par_tonne_km=Decimal('0.5'))
