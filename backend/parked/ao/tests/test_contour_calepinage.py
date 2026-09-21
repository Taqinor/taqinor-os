"""CAL31 — la conversion de contour AO ↔ calepinage 3D (ENU ↔ repère local).

Ce que ce module VERROUILLE :

  1. **L'aller-retour retombe sur le même contour**, à la tolérance DÉCLARÉE
     (``services.TOLERANCE_ALLER_RETOUR_M``, 1 mm), dans les deux sens.
  2. **Une toiture sans ancre géographique est REFUSÉE**, avec un message
     français qui NOMME le champ manquant — jamais une origine devinée : le
     GPS du site placerait le bâtiment à côté de lui-même.
  3. **L'ordre des axes est tenu** : ``outline`` est en ``[lat, lng]``
     (l'inverse de ``zones[].vertices``). Une inversion serait SILENCIEUSE —
     les nombres restent plausibles, le bâtiment part à 500 km.
  4. **Seul le contour voyage** : les deux services sont PURS (ils ne
     modifient ni la toiture, ni ses obstacles, ni ses cotes, ni ses zones).

Run :
    python manage.py test apps.ao.tests.test_contour_calepinage -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BatimentAO, ChaineCotes, ObstacleAO, ToitureAO, ZoneAO,
)
from authentication.models import Company

#: Casablanca — une ancre RÉELLE, à la 7ᵉ décimale (≈ 1 cm).
LAT, LNG = Decimal('33.5731245'), Decimal('-7.5898431')

#: Un rectangle de 30 m × 18 m dans le repère local, plus un décrochement :
#: une enveloppe plausible de bâtiment industriel, pas un carré d'école.
CONTOUR_M = [[0.0, 0.0], [30.0, 0.0], [30.0, 12.0], [18.0, 12.0],
             [18.0, 18.0], [0.0, 18.0]]


def _ecart_max_m(attendu, obtenu):
    """Le plus grand écart, en mètres, entre deux contours LOCAUX."""
    assert len(attendu) == len(obtenu), 'nombre de sommets différent'
    return max(max(abs(a[0] - b[0]), abs(a[1] - b[1]))
               for a, b in zip(attendu, obtenu))


class BaseCal31(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CAL31 Co', slug='cal31-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-CAL31-1', objet='Contours')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')

    def _toiture(self, *, contour=None, ancree=True, code='05H'):
        return ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document=code,
            forme=ToitureAO.Forme.POLYGONE,
            contour_local_m=CONTOUR_M if contour is None else contour,
            origine_lat=LAT if ancree else None,
            origine_lng=LNG if ancree else None)


class LAllerRetourRetombeSurLeMemeContour(BaseCal31):
    def test_ao_vers_3d_vers_ao(self):
        toiture = self._toiture()

        outline = services.contour_ao_vers_outline_latlng(toiture)
        retour = services.outline_latlng_vers_contour_ao(outline, toiture)

        self.assertLessEqual(_ecart_max_m(CONTOUR_M, retour),
                             services.TOLERANCE_ALLER_RETOUR_M)

    def test_3d_vers_ao_vers_3d(self):
        """L'autre sens : un tracé 3D importé puis ré-exporté ne dérive pas."""
        toiture = self._toiture()
        outline = services.contour_ao_vers_outline_latlng(toiture)

        local = services.outline_latlng_vers_contour_ao(outline, toiture)
        toiture.contour_local_m = local
        re_exporte = services.contour_ao_vers_outline_latlng(toiture)

        ecart_deg = max(max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                        for a, b in zip(outline, re_exporte))
        # 1 mm en degrés de latitude ≈ 9e-9 ° : la borne reste métrique.
        self.assertLess(ecart_deg, 1e-8)

    def test_le_nombre_de_sommets_est_conserve(self):
        toiture = self._toiture()
        outline = services.contour_ao_vers_outline_latlng(toiture)
        self.assertEqual(len(outline), len(CONTOUR_M))


class LOrdreDesAxesEstTenu(BaseCal31):
    """``outline`` est en ``[lat, lng]`` — l'INVERSE de ``zones[].vertices``."""

    def test_le_premier_sommet_est_l_ancre_elle_meme(self):
        """Le sommet (0, 0) du repère local EST l'ancre, par construction."""
        toiture = self._toiture()

        lat, lng = services.contour_ao_vers_outline_latlng(toiture)[0]

        self.assertAlmostEqual(lat, float(LAT), places=9)
        self.assertAlmostEqual(lng, float(LNG), places=9)

    def test_un_deplacement_vers_l_est_augmente_la_longitude(self):
        """x pointe vers l'EST : c'est la LONGITUDE qui bouge, pas la latitude."""
        toiture = self._toiture(contour=[[0.0, 0.0], [30.0, 0.0]])

        (lat0, lng0), (lat1, lng1) = \
            services.contour_ao_vers_outline_latlng(toiture)

        self.assertGreater(lng1, lng0)
        self.assertAlmostEqual(lat1, lat0, places=9)

    def test_un_deplacement_vers_le_nord_augmente_la_latitude(self):
        toiture = self._toiture(contour=[[0.0, 0.0], [0.0, 18.0]])

        (lat0, lng0), (lat1, lng1) = \
            services.contour_ao_vers_outline_latlng(toiture)

        self.assertGreater(lat1, lat0)
        self.assertAlmostEqual(lng1, lng0, places=9)

    def test_une_inversion_d_axes_serait_detectee(self):
        """Filet explicite : importer un outline INVERSÉ ne retombe pas dessus.

        C'est la raison d'être des noms ``..._latlng`` / ``..._lnglat``.
        """
        toiture = self._toiture()
        outline = services.contour_ao_vers_outline_latlng(toiture)
        inverse = [[lng, lat] for lat, lng in outline]

        faux = services.outline_latlng_vers_contour_ao(inverse, toiture)

        self.assertGreater(_ecart_max_m(CONTOUR_M, faux), 1000.0)


class UneToitureSansAncreEstRefusee(BaseCal31):
    def test_l_export_refuse_en_nommant_les_deux_champs(self):
        toiture = self._toiture(ancree=False)

        with self.assertRaises(services.ContourSansAncre) as refus:
            services.contour_ao_vers_outline_latlng(toiture)

        message = str(refus.exception)
        self.assertIn("Latitude de l'origine du repère local", message)
        self.assertIn("Longitude de l'origine du repère local", message)
        self.assertEqual(refus.exception.champ, 'origine_lat')

    def test_l_import_refuse_de_la_meme_facon(self):
        toiture = self._toiture(ancree=False)

        with self.assertRaises(services.ContourSansAncre):
            services.outline_latlng_vers_contour_ao([[33.5, -7.6]], toiture)

    def test_une_ancre_a_moitie_renseignee_nomme_le_champ_manquant(self):
        toiture = self._toiture()
        toiture.origine_lng = None

        with self.assertRaises(services.ContourSansAncre) as refus:
            services.contour_ao_vers_outline_latlng(toiture)

        self.assertEqual(refus.exception.champ, 'origine_lng')
        self.assertIn("Longitude de l'origine du repère local",
                      str(refus.exception))
        self.assertNotIn("Latitude de l'origine", str(refus.exception))

    def test_aucune_toiture_du_tout_est_refusee_aussi(self):
        with self.assertRaises(services.ContourSansAncre) as refus:
            services.contour_ao_vers_outline_latlng(None)
        self.assertEqual(refus.exception.champ, 'toiture')


class UneToitureSansTraceNEstPasUneErreur(BaseCal31):
    def test_un_contour_vide_donne_un_outline_vide(self):
        toiture = self._toiture(contour=[])
        self.assertEqual(services.contour_ao_vers_outline_latlng(toiture), [])

    def test_un_outline_vide_donne_un_contour_vide(self):
        toiture = self._toiture()
        self.assertEqual(
            services.outline_latlng_vers_contour_ao([], toiture), [])


class SeulLeContourVoyage(BaseCal31):
    """Les deux services sont PURS : la géométrie opposable est intouchée."""

    def setUp(self):
        super().setUp()
        self.toiture = self._toiture()
        self.obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            rect_x0_m=Decimal('5.000'), rect_x1_m=Decimal('6.000'),
            rect_y0_m=Decimal('4.000'), rect_y1_m=Decimal('5.000'))
        self.zone = ZoneAO.objects.create(
            company=self.company, toiture=self.toiture, repere='Z1',
            sommets=[[0, 0], [5, 0], [5, 5]])
        self.chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture,
            libelle='Façade sud', segments=[])

    def test_l_export_n_ecrit_rien(self):
        services.contour_ao_vers_outline_latlng(self.toiture)

        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.contour_local_m, CONTOUR_M)
        self.assertEqual(ObstacleAO.objects.filter(
            toiture=self.toiture).count(), 1)

    def test_l_import_ne_touche_ni_obstacle_ni_zone_ni_cote(self):
        outline = services.contour_ao_vers_outline_latlng(self.toiture)
        sommets_avant = list(self.zone.sommets)

        services.outline_latlng_vers_contour_ao(outline, self.toiture)

        self.toiture.refresh_from_db()
        self.obstacle.refresh_from_db()
        self.zone.refresh_from_db()
        self.assertEqual(self.toiture.contour_local_m, CONTOUR_M)
        self.assertEqual(self.obstacle.rect_x0_m, Decimal('5.000'))
        self.assertEqual(self.zone.sommets, sommets_avant)
        self.assertEqual(ChaineCotes.objects.filter(
            toiture=self.toiture).count(), 1)
