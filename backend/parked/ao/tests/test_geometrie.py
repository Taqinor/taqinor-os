"""AOF19 — contrat de géométrie : repère local métrique, degrés en frontière.

Le bug latent que ce module ferme : l'outil de tracé manipule ``[lng, lat]``
alors que le lead CRM stocke son contour en ``[lat, lng]``. L'inversion est
SILENCIEUSE — les nombres restent plausibles, le polygone atterrit à des
centaines de kilomètres. Trois garde-fous sont testés ici :

  1. l'aller-retour degrés → local → degrés est stable à MOINS D'UN CENTIMÈTRE
     sur un cas marocain réel ;
  2. l'inversion vs le format du lead CRM est détectée EXPLICITEMENT ;
  3. chaque fonction de frontière porte l'ordre des axes DANS SON NOM (un
     ``convertir_coordonnees`` rendrait l'inversion indétectable), et la
     docstring du module le déclare.

Run :
    python manage.py test apps.ao.tests.test_geometrie -v2
"""
import inspect
import math

from django.test import SimpleTestCase

from apps.ao import geometrie

#: Cas marocain réel — Benguerir (site de type « écoles / campus »).
ORIGINE_LNGLAT = [-7.951000, 32.236000]
#: Un rectangle d'environ 50 m × 30 m autour de l'origine, en ``[lng, lat]``.
CONTOUR_LNGLAT = [
    [-7.951000, 32.236000],
    [-7.950470, 32.236000],
    [-7.950470, 32.236270],
    [-7.951000, 32.236270],
]

CARRE_10 = [[0, 0], [10, 0], [10, 10], [0, 10]]


class TestContratDOrdreDesAxes(SimpleTestCase):
    def test_le_module_declare_l_ordre(self):
        self.assertEqual(geometrie.ORDRE_AXES_CANONIQUE, 'lng,lat')
        doc = geometrie.__doc__ or ''
        self.assertIn('lng, lat', doc)
        self.assertIn('lat, lng', doc)
        self.assertIn('MÈTRES', doc)

    def test_chaque_fonction_de_frontiere_nomme_son_ordre(self):
        """Une fonction de frontière SANS ordre dans son nom est un piège."""
        for nom in geometrie.__all__:
            objet = getattr(geometrie, nom)
            if not callable(objet):
                continue
            signature = inspect.signature(objet)
            touche_degres = any(
                'lnglat' in p or 'latlng' in p for p in signature.parameters)
            if touche_degres:
                self.assertTrue(
                    'lnglat' in nom or 'latlng' in nom or 'geodesique' in nom,
                    f'{nom} manipule des degrés sans le dire dans son nom')


class TestAllerRetourEnu(SimpleTestCase):
    def test_aller_retour_stable_sous_le_centimetre(self):
        local = geometrie.lnglat_vers_local_m(CONTOUR_LNGLAT, ORIGINE_LNGLAT)
        retour = geometrie.local_m_vers_lnglat(local, ORIGINE_LNGLAT)
        for depart, arrivee in zip(CONTOUR_LNGLAT, retour):
            # Reconvertir l'écart en mètres pour juger en unité MÉTIER.
            ecart = geometrie.lnglat_vers_local_m([arrivee], depart)[0]
            self.assertLess(math.hypot(*ecart), 0.01)

    def test_l_origine_est_bien_le_zero(self):
        local = geometrie.lnglat_vers_local_m([ORIGINE_LNGLAT],
                                              ORIGINE_LNGLAT)
        self.assertAlmostEqual(local[0][0], 0.0, places=9)
        self.assertAlmostEqual(local[0][1], 0.0, places=9)

    def test_x_va_vers_l_est_et_y_vers_le_nord(self):
        est = geometrie.lnglat_vers_local_m(
            [[ORIGINE_LNGLAT[0] + 0.001, ORIGINE_LNGLAT[1]]],
            ORIGINE_LNGLAT)[0]
        nord = geometrie.lnglat_vers_local_m(
            [[ORIGINE_LNGLAT[0], ORIGINE_LNGLAT[1] + 0.001]],
            ORIGINE_LNGLAT)[0]
        self.assertGreater(est[0], 0)
        self.assertAlmostEqual(est[1], 0.0, places=6)
        self.assertGreater(nord[1], 0)
        self.assertAlmostEqual(nord[0], 0.0, places=6)

    def test_dimensions_metriques_plausibles(self):
        local = geometrie.lnglat_vers_local_m(CONTOUR_LNGLAT, ORIGINE_LNGLAT)
        largeur = abs(local[1][0] - local[0][0])
        hauteur = abs(local[2][1] - local[1][1])
        self.assertAlmostEqual(largeur, 50.0, delta=1.0)
        self.assertAlmostEqual(hauteur, 30.0, delta=1.0)


class TestNonInversionVsLeadCRM(SimpleTestCase):
    """Le format du lead CRM est ``[lat, lng]`` — l'inverse de l'outil."""

    def test_l_adaptateur_echange_bien_les_axes(self):
        latlng = [[32.236000, -7.951000], [32.236270, -7.950470]]
        lnglat = geometrie.latlng_vers_lnglat(latlng)
        self.assertEqual(lnglat, [[-7.951000, 32.236000],
                                  [-7.950470, 32.236270]])

    def test_aller_retour_des_deux_conventions(self):
        latlng = geometrie.lnglat_vers_latlng(CONTOUR_LNGLAT)
        self.assertEqual(geometrie.latlng_vers_lnglat(latlng), CONTOUR_LNGLAT)

    def test_une_inversion_est_detectee_par_l_absurde(self):
        """Interpréter du ``[lat, lng]`` comme du ``[lng, lat]`` déplace le
        site de centaines de kilomètres : le test échouerait bruyamment si
        l'adaptateur disparaissait un jour."""
        latlng_crm = geometrie.lnglat_vers_latlng(CONTOUR_LNGLAT)
        correct = geometrie.lnglat_vers_local_m(
            geometrie.latlng_vers_lnglat(latlng_crm), ORIGINE_LNGLAT)
        inverse = geometrie.lnglat_vers_local_m(latlng_crm, ORIGINE_LNGLAT)
        ecart = math.hypot(inverse[0][0] - correct[0][0],
                           inverse[0][1] - correct[0][1])
        self.assertGreater(ecart, 100_000)


class TestGeometriePlane(SimpleTestCase):
    def test_aire_et_perimetre_du_carre(self):
        self.assertAlmostEqual(geometrie.aire_polygone_m2(CARRE_10), 100.0)
        self.assertAlmostEqual(geometrie.perimetre_polygone_m(CARRE_10), 40.0)

    def test_polygone_simple_et_noeud(self):
        self.assertTrue(geometrie.polygone_est_simple(CARRE_10))
        self.assertFalse(geometrie.polygone_est_simple(
            [[0, 0], [10, 10], [10, 0], [0, 10]]))

    def test_orientation_normalisee_en_trigonometrique(self):
        horaire = list(reversed(CARRE_10))
        normalise = geometrie.normaliser_orientation(horaire)
        self.assertEqual(
            geometrie.aire_polygone_m2(normalise),
            geometrie.aire_polygone_m2(CARRE_10))
        points = [(p[0], p[1]) for p in normalise]
        aire_signee = geometrie._aire_signee(points)
        self.assertGreater(aire_signee, 0)

    def test_normalisation_idempotente(self):
        une_fois = geometrie.normaliser_orientation(CARRE_10)
        deux_fois = geometrie.normaliser_orientation(une_fois)
        self.assertEqual(une_fois, deux_fois)

    def test_aire_geodesique_coherente_avec_le_local(self):
        aire_deg = geometrie.aire_geodesique_m2(CONTOUR_LNGLAT)
        local = geometrie.lnglat_vers_local_m(CONTOUR_LNGLAT,
                                              CONTOUR_LNGLAT[0])
        self.assertAlmostEqual(aire_deg, geometrie.aire_polygone_m2(local),
                               places=6)
        self.assertAlmostEqual(aire_deg, 1500.0, delta=60.0)

    def test_perimetre_geodesique(self):
        perimetre = geometrie.perimetre_geodesique_m(CONTOUR_LNGLAT)
        self.assertAlmostEqual(perimetre, 160.0, delta=6.0)


class TestModulePur(SimpleTestCase):
    def test_aucun_import_django_ni_io(self):
        source = inspect.getsource(geometrie)
        for interdit in ('django', 'import os', 'open(', 'requests',
                         'models.'):
            self.assertNotIn(interdit, source, interdit)

    def test_les_modeles_reexportent_la_meme_implementation(self):
        from apps.ao import models as ao_models

        self.assertIs(ao_models.polygone_est_simple,
                      geometrie.polygone_est_simple)
        self.assertIs(ao_models.aire_polygone_m2, geometrie.aire_polygone_m2)
