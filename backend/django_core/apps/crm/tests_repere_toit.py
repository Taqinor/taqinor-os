"""QJR598 — un seul repère toit du lead (D-QJR5-15).

Le GPS du lead, quand il est renseigné et DIFFÉRENT de ``roof_point``, vient
toujours d'une correction (équipe ou questionnaire) : il prime partout. Le
contour du client n'est un toit à calepiner que si ce repère tombe dedans ;
sinon il n'est plus qu'un calque affiché.

Run :
    python manage.py test apps.crm.tests_repere_toit -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.selectors import (
    SOURCE_GPS_LEAD,
    SOURCE_ROOF_POINT,
    contexte_geographique,
)
from apps.crm.models import Lead
from apps.crm.selectors import (
    REPERE_SOURCE_GPS,
    REPERE_SOURCE_ROOF_POINT,
    repere_toit,
)
from apps.ventes.domain.geometrie import zone_toit_depuis_contour
from authentication.models import Company

# Un carré d'environ 30 m autour de A, en [lat, lng] (forme du webhook).
CONTOUR = [[33.5730, -7.5900], [33.5730, -7.5896],
           [33.5734, -7.5896], [33.5734, -7.5900]]
POINT_A = {'lat': 33.5732, 'lng': -7.5898}          # dans le contour
GPS_DEDANS = (Decimal('33.5733000'), Decimal('-7.5897000'))
GPS_DEHORS = (Decimal('33.6000000'), Decimal('-7.6500000'))


class RepereToitTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Repère Co',
                                              slug='repere-co-598')

    def _lead(self, gps=(None, None), **extra):
        return Lead.objects.create(
            company=self.company, nom='Toit', roof_point=POINT_A,
            roof_outline=CONTOUR, gps_lat=gps[0], gps_lng=gps[1], **extra)

    def test_gps_hors_du_contour_prime_et_contour_inutilisable(self):
        pin, source, utilisable = repere_toit(self._lead(GPS_DEHORS))
        self.assertEqual(pin, {'lat': 33.6, 'lng': -7.65})
        self.assertEqual(source, REPERE_SOURCE_GPS)
        self.assertFalse(utilisable)

    def test_gps_dans_le_contour_prime_et_contour_utilisable(self):
        pin, source, utilisable = repere_toit(self._lead(GPS_DEDANS))
        self.assertEqual(pin, {'lat': 33.5733, 'lng': -7.5897})
        self.assertEqual(source, REPERE_SOURCE_GPS)
        self.assertTrue(utilisable)

    def test_gps_vide_rend_l_epingle(self):
        pin, source, utilisable = repere_toit(self._lead())
        self.assertEqual(pin, POINT_A)
        self.assertEqual(source, REPERE_SOURCE_ROOF_POINT)
        self.assertTrue(utilisable)

    def test_gps_egal_a_l_epingle_rend_l_epingle(self):
        lead = self._lead((Decimal('33.5732000'), Decimal('-7.5898000')))
        _pin, source, _ = repere_toit(lead)
        self.assertEqual(source, REPERE_SOURCE_ROOF_POINT)

    def test_lead_sans_aucune_coordonnee(self):
        lead = Lead.objects.create(company=self.company, nom='Rien')
        self.assertEqual(repere_toit(lead), (None, None, False))
        self.assertEqual(repere_toit(None), (None, None, False))

    def test_calepinage_et_ventes_rendent_le_meme_pin(self):
        lead = self._lead(GPS_DEHORS)
        contexte = contexte_geographique(
            Calepinage.objects.create(company=self.company, lead_id=lead.pk))
        self.assertEqual(contexte['pin'], {'lat': 33.6, 'lng': -7.65})
        self.assertEqual(contexte['source'], SOURCE_GPS_LEAD)

        from apps.crm.models import Client
        from apps.ventes.models import Devis
        from apps.ventes.selectors import contexte_conception_devis
        client = Client.objects.create(company=self.company, nom='C598')
        devis = Devis.objects.create(company=self.company, client=client,
                                     lead=lead, reference='DEV-QJR598-1')
        contexte_ventes = contexte_conception_devis(devis, self.company)
        self.assertEqual(contexte_ventes['geometrie']['pin'],
                         {'lat': 33.6, 'lng': -7.65})

    def test_epingle_seule_cote_calepinage(self):
        lead = self._lead()
        contexte = contexte_geographique(
            Calepinage.objects.create(company=self.company, lead_id=lead.pk))
        self.assertEqual(contexte['source'], SOURCE_ROOF_POINT)

    def test_auto_calepinage_seulement_si_contour_utilisable(self):
        self.assertEqual(
            zone_toit_depuis_contour(self._lead(GPS_DEHORS), panneaux=8), {})
        zone = zone_toit_depuis_contour(self._lead(GPS_DEDANS), panneaux=8)
        self.assertEqual(zone['pin'], {'lat': 33.5733, 'lng': -7.5897})
