"""NTLOG24 — tableau de bord logistique : coût/kg transporté, taux de
service, litiges ouverts, répartition flotte propre/affrètement, CO2 total
estimé. Filtrable par `?periode=YYYY-MM`, exclut toujours les ordres
annulés."""
from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.transport.models import (
    CoutFretReel, EtapeTransport, FacteurEmissionCO2, LigneOrdreTransport,
    LitigeTransport, OrdreTransport,
)

from ._helpers import auth, make_company, make_user

BASE = '/api/django/transport/ordres-transport/tableau-bord-logistique/'


class TableauBordLogistiqueTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-tbl-a', 'A')
        self.user_a = make_user(self.co_a, 'transport-tbl-a')

    def _ordre_livre(self, *, poids_kg, date_prevue, date_reelle,
                     mode=OrdreTransport.ModeTransport.AFFRETEMENT):
        ordre = OrdreTransport.objects.create(
            company=self.co_a, statut=OrdreTransport.Statut.LIVRE,
            mode_transport=mode, date_livraison_prevue=date_prevue)
        LigneOrdreTransport.objects.create(
            company=self.co_a, ordre=ordre, poids_kg=Decimal(str(poids_kg)))
        EtapeTransport.objects.create(
            company=self.co_a, ordre=ordre, sequence=1,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON,
            statut_etape=EtapeTransport.StatutEtape.FAIT,
            date_reelle=date_reelle)
        return ordre

    def test_cout_par_kg_et_repartition_mode(self):
        o1 = self._ordre_livre(
            poids_kg='1000.00', date_prevue=date(2026, 1, 10),
            date_reelle=date(2026, 1, 9),
            mode=OrdreTransport.ModeTransport.AFFRETEMENT)
        self._ordre_livre(
            poids_kg='500.00', date_prevue=date(2026, 1, 10),
            date_reelle=date(2026, 1, 10),
            mode=OrdreTransport.ModeTransport.FLOTTE_PROPRE)
        CoutFretReel.objects.create(
            company=self.co_a, ordre_transport=o1, montant_ht=Decimal('300.00'))

        resp = auth(self.user_a).get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(data['nb_livres'], 2)
        self.assertEqual(Decimal(str(data['poids_livre_kg'])), Decimal('1500.00'))
        self.assertEqual(Decimal(str(data['total_fret_ht'])), Decimal('300.00'))
        self.assertEqual(Decimal(str(data['cout_par_kg_transporte'])), Decimal('0.2'))
        self.assertEqual(data['repartition_mode_transport']['affretement'], 1)
        self.assertEqual(data['repartition_mode_transport']['flotte_propre'], 1)

    def test_taux_service_exclut_les_retards(self):
        # Livré à temps.
        self._ordre_livre(
            poids_kg='10', date_prevue=date(2026, 2, 5),
            date_reelle=date(2026, 2, 4))
        # Livré en retard.
        self._ordre_livre(
            poids_kg='10', date_prevue=date(2026, 2, 5),
            date_reelle=date(2026, 2, 8))

        resp = auth(self.user_a).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['taux_service_pct'], 50.0)

    def test_exclut_les_ordres_annules(self):
        self._ordre_livre(
            poids_kg='100', date_prevue=date(2026, 3, 1),
            date_reelle=date(2026, 3, 1))
        OrdreTransport.objects.create(
            company=self.co_a, statut=OrdreTransport.Statut.ANNULE)

        resp = auth(self.user_a).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_ordres'], 1)

    def test_litiges_ouverts_compte_et_montant(self):
        ordre = OrdreTransport.objects.create(company=self.co_a)
        LitigeTransport.objects.create(
            company=self.co_a, ordre_transport=ordre,
            statut=LitigeTransport.Statut.OUVERT,
            montant_conteste=Decimal('400.00'))
        LitigeTransport.objects.create(
            company=self.co_a, ordre_transport=ordre,
            statut=LitigeTransport.Statut.RESOLU,
            montant_conteste=Decimal('999.00'))

        resp = auth(self.user_a).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['litiges_ouverts_count'], 1)
        self.assertEqual(
            Decimal(str(resp.data['litiges_ouverts_montant_conteste'])),
            Decimal('400.00'))

    def test_filtre_par_periode(self):
        dedans = self._ordre_livre(
            poids_kg='200', date_prevue=date(2026, 4, 1),
            date_reelle=date(2026, 4, 1))
        dedans.created_at = timezone.make_aware(datetime(2026, 4, 15))
        dedans.save(update_fields=['created_at'])

        dehors = self._ordre_livre(
            poids_kg='999', date_prevue=date(2026, 5, 1),
            date_reelle=date(2026, 5, 1))
        dehors.created_at = timezone.make_aware(datetime(2026, 5, 15))
        dehors.save(update_fields=['created_at'])

        resp = auth(self.user_a).get(BASE, {'periode': '2026-04'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_ordres'], 1)
        self.assertEqual(
            Decimal(str(resp.data['poids_livre_kg'])), Decimal('200.00'))

    def test_co2_total_estime_agrege_les_ordres_avec_distance(self):
        ordre = OrdreTransport.objects.create(
            company=self.co_a,
            mode_acheminement_physique=OrdreTransport.ModeAcheminementPhysique.ROUTE,
            distance_km=Decimal('50.0'))
        LigneOrdreTransport.objects.create(
            company=self.co_a, ordre=ordre, poids_kg=Decimal('1000.00'))
        FacteurEmissionCO2.objects.create(
            company=self.co_a, mode=FacteurEmissionCO2.Mode.ROUTE,
            facteur_kg_co2_par_tonne_km=Decimal('0.1000'))

        resp = auth(self.user_a).get(BASE)
        self.assertEqual(resp.status_code, 200)
        # 1 tonne x 50 km x 0.1 = 5 kgCO2.
        self.assertEqual(
            Decimal(str(resp.data['co2_total_estime_kg'])), Decimal('5.000'))
