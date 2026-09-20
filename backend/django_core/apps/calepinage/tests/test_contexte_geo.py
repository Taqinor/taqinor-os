"""CAL15 — le pré-remplissage géographique : réel, ou absent. Jamais deviné.

Ce qui est prouvé ici :

* les CINQ clés (``pin``, ``outline``, ``adresse``, ``ville``, ``source``)
  sont TOUJOURS présentes — nulles quand la donnée est inconnue ;
* un calepinage sur un lead SANS aucune coordonnée rend ``pin: None`` et
  ``source: None`` — pas un centre du Maroc inventé ;
* l'épingle POSÉE par le client (``Lead.roof_point``) prime sur les
  coordonnées GPS saisies, et ``source`` dit LAQUELLE a servi ;
* un lead avec contour rend son contour TEL QUEL (aucune reprojection) ;
* un calepinage sur un client seul rend son adresse, sans géométrie ;
* un lead d'une autre société n'est pas lu (le sélecteur crm le borne).

Run :
    python manage.py test apps.calepinage.tests.test_contexte_geo -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.selectors import (
    CLES_CONTEXTE_GEO,
    SOURCE_GPS_LEAD,
    SOURCE_ROOF_POINT,
    contexte_geographique,
)
from apps.crm.models import Client, Lead
from authentication.models import Company

CONTOUR = [[33.5731, -7.5898], [33.5734, -7.5898], [33.5734, -7.5893]]


class BaseGeo(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Géo Co', slug='geo-co')
        self.autre = Company.objects.create(nom='Autre Co',
                                            slug='autre-co-15')
        self.client_a = Client.objects.create(
            company=self.company, nom='Bâtiment Atlas',
            adresse='12 rue des Panneaux, Casablanca')


class FormeTest(BaseGeo):
    def test_les_cinq_cles_toujours_presentes(self):
        lead = Lead.objects.create(company=self.company, nom='Sans données')
        pivot = Calepinage.objects.create(company=self.company,
                                          lead_id=lead.pk)
        contexte = contexte_geographique(pivot)
        self.assertEqual(sorted(contexte), sorted(CLES_CONTEXTE_GEO))

    def test_calepinage_absent_rend_le_contexte_vide(self):
        contexte = contexte_geographique(None)
        self.assertEqual(sorted(contexte), sorted(CLES_CONTEXTE_GEO))
        self.assertTrue(all(valeur is None for valeur in contexte.values()))


class AucuneCoordonneeInventeeTest(BaseGeo):
    def test_lead_sans_gps_rend_pin_none_et_source_none(self):
        lead = Lead.objects.create(company=self.company, nom='Sans GPS',
                                   ville='Casablanca')
        pivot = Calepinage.objects.create(company=self.company,
                                          lead_id=lead.pk)
        contexte = contexte_geographique(pivot)
        self.assertIsNone(contexte['pin'])
        self.assertIsNone(contexte['source'])
        self.assertEqual(contexte['ville'], 'Casablanca')

    def test_gps_incomplet_ne_produit_pas_d_epingle(self):
        lead = Lead.objects.create(company=self.company, nom='Moitié',
                                   gps_lat=Decimal('33.5731000'))
        pivot = Calepinage.objects.create(company=self.company,
                                          lead_id=lead.pk)
        contexte = contexte_geographique(pivot)
        self.assertIsNone(contexte['pin'])
        self.assertIsNone(contexte['source'])

    def test_roof_point_incomplet_replie_sur_le_gps(self):
        lead = Lead.objects.create(
            company=self.company, nom='Point cassé',
            roof_point={'lat': 33.5731}, gps_lat=Decimal('33.5000000'),
            gps_lng=Decimal('-7.6000000'))
        contexte = contexte_geographique(
            Calepinage.objects.create(company=self.company, lead_id=lead.pk))
        self.assertEqual(contexte['source'], SOURCE_GPS_LEAD)
        self.assertEqual(contexte['pin'], {'lat': 33.5, 'lng': -7.6})


class SourcesTest(BaseGeo):
    def test_roof_point_prime_sur_le_gps(self):
        lead = Lead.objects.create(
            company=self.company, nom='Pointé',
            roof_point={'lat': 33.5731, 'lng': -7.5898},
            gps_lat=Decimal('33.5000000'), gps_lng=Decimal('-7.6000000'))
        contexte = contexte_geographique(
            Calepinage.objects.create(company=self.company, lead_id=lead.pk))
        self.assertEqual(contexte['source'], SOURCE_ROOF_POINT)
        self.assertEqual(contexte['pin'], {'lat': 33.5731, 'lng': -7.5898})

    def test_repli_sur_le_gps(self):
        lead = Lead.objects.create(company=self.company, nom='GPS seul',
                                   gps_lat=Decimal('33.5731000'),
                                   gps_lng=Decimal('-7.5898000'))
        contexte = contexte_geographique(
            Calepinage.objects.create(company=self.company, lead_id=lead.pk))
        self.assertEqual(contexte['source'], SOURCE_GPS_LEAD)
        self.assertEqual(contexte['pin']['lat'], 33.5731)


class ContourTest(BaseGeo):
    def test_contour_rendu_tel_quel(self):
        lead = Lead.objects.create(company=self.company, nom='Dessiné',
                                   roof_outline=CONTOUR)
        contexte = contexte_geographique(
            Calepinage.objects.create(company=self.company, lead_id=lead.pk))
        self.assertEqual(contexte['outline'], CONTOUR)

    def test_contour_vide_vaut_none(self):
        lead = Lead.objects.create(company=self.company, nom='Vide',
                                   roof_outline=[])
        contexte = contexte_geographique(
            Calepinage.objects.create(company=self.company, lead_id=lead.pk))
        self.assertIsNone(contexte['outline'])


class ClientSeulTest(BaseGeo):
    def test_adresse_du_client_sans_geometrie(self):
        pivot = Calepinage.objects.create(company=self.company,
                                          client=self.client_a)
        contexte = contexte_geographique(pivot)
        self.assertEqual(contexte['adresse'],
                         '12 rue des Panneaux, Casablanca')
        self.assertIsNone(contexte['pin'])
        self.assertIsNone(contexte['outline'])
        self.assertIsNone(contexte['source'])

    def test_adresse_du_lead_prime_sur_celle_du_client(self):
        lead = Lead.objects.create(company=self.company, nom='Avec adresse',
                                   adresse='5 boulevard Anfa, Casablanca')
        pivot = Calepinage.objects.create(company=self.company,
                                          lead_id=lead.pk,
                                          client=self.client_a)
        self.assertEqual(contexte_geographique(pivot)['adresse'],
                         '5 boulevard Anfa, Casablanca')


class IsolationTest(BaseGeo):
    def test_lead_d_une_autre_societe_n_est_pas_lu(self):
        etranger = Lead.objects.create(
            company=self.autre, nom='Étranger',
            roof_point={'lat': 35.0, 'lng': -5.0})
        pivot = Calepinage.objects.create(company=self.company,
                                          lead_id=etranger.pk,
                                          client=self.client_a)
        contexte = contexte_geographique(pivot)
        self.assertIsNone(contexte['pin'])
        self.assertIsNone(contexte['source'])
