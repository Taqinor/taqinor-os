"""SOLMVP15b — le moteur VILLA vit dans ``apps.calepinage``, plus dans AO.

AO sort du produit. Ce test prouve que la capacité de recomptage dont
``apps.ventes`` dépend (``compte_moteur_du_layout`` → ``peremption_layout_devis``
/ ``comparaison_calepinage_devis``) survit au déménagement SANS changer de
forme : mêmes clés de sortie, même type de résultat, même empreinte d'entrée et
même compte que le chemin « surface libre » sur la MÊME géométrie, ordre lat/lng
toujours EXPLICITE. Porté du test « pont villa » d'AO — et il n'importe AUCUN
module AO : c'est précisément le point.

Run : python manage.py test
    apps.calepinage.tests.test_solmvp15b_moteur_villa -v2
"""
from django.test import SimpleTestCase

from apps.calepinage import selectors, villa_service
from core.calepinage.adaptateurs.villa import RETRAIT_VILLA_M, Projection
from core.calepinage.politique_pas import AntiOmbrage
from core.calepinage.serialisation import ResultatCalepinage
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.types import KIT_VILLA_720, Axe, Parametres, Rives

#: Ancre (Casablanca) + rectangle CENTRÉ dessus, 14 m × 10 m. Le centrage rend
#: l'aller-retour mètres -> degrés -> mètres exact au flottant près : les deux
#: chemins doivent tomber sur la MÊME empreinte, pas « à peu près la même ».
LAT0, LNG0 = 33.5731, -7.5898
DEMI_L_M, DEMI_H_M = 7.0, 5.0
REPERE = 'VILLA_SOLMVP15B'
CONTOUR = ((-DEMI_L_M, -DEMI_H_M), (DEMI_L_M, -DEMI_H_M),
           (DEMI_L_M, DEMI_H_M), (-DEMI_L_M, DEMI_H_M))
CLES_SORTIE = {'entree', 'resultat', 'preuve', 'rangees', 'tables',
               'projection', 'politique', 'kit', 'panneaux'}
CLES_PREUVE = {'methode', 'pas_recherche_m', 'compte_retenu', 'compte_optimal',
               'borne_superieure', 'nb_plans_optimaux', 'ecart_a_l_optimum',
               'politique_pas'}


def _area(ordre='lnglat'):
    """L'``AreaRecord`` du lecteur de cartes pour cette toiture plate."""
    projection = Projection(lat0_deg=LAT0, lng0_deg=LNG0)
    points = []
    for est, nord in CONTOUR:
        lat, lng = projection.vers_geo(est, nord)
        points.append([lng, lat] if ordre == 'lnglat' else [lat, lng])
    return {'id': REPERE, 'flat': True, 'tilt': 0.0, 'azimuth': 180.0,
            'polygon': points, 'obstacles': []}


def _chemin_surface_libre():
    """La MÊME toiture par ``calepiner_surface`` — format canonique, objets."""
    rives = Rives(laterale_m=RETRAIT_VILLA_M, extremite_m=RETRAIT_VILLA_M)
    surface = SurfacePolygone(
        repere=REPERE, contour=CONTOUR, rives=rives, axe_rangee=Axe.EST_OUEST,
        pente_deg=0.0, azimut_deg=180.0)
    parametres = Parametres(kits=(KIT_VILLA_720,), rives=rives,
                            axe_rangee=Axe.EST_OUEST, allee_m=0.0,
                            pas_recherche_m=0.01)
    return villa_service.calepiner_surface(
        surface=surface, kits=(KIT_VILLA_720,), parametres=parametres,
        politique=AntiOmbrage(), repere=REPERE)


class LeMoteurVillaEstDansCalepinage(SimpleTestCase):
    """LECTURE PURE — ``SimpleTestCase`` : rien n'est lu ni écrit en base."""

    def test_le_selector_rend_la_structure_d_avant(self):
        sortie = selectors.calepinage_villa(_area())
        self.assertEqual(set(sortie), CLES_SORTIE)
        self.assertIsInstance(sortie['resultat'], ResultatCalepinage)
        self.assertGreater(sortie['resultat'].modules, 0)
        self.assertTrue(sortie['resultat'].hash_entree)
        self.assertTrue(sortie['resultat'].version_moteur)
        self.assertEqual(set(sortie['preuve']), CLES_PREUVE)
        self.assertEqual(sortie['preuve']['politique_pas'], 'ANTI_OMBRAGE')
        self.assertEqual(len(sortie['panneaux']), len(sortie['tables']))

    def test_meme_compte_et_meme_empreinte_que_la_surface_libre(self):
        villa = selectors.calepinage_villa(_area())
        libre = _chemin_surface_libre()
        self.assertEqual(villa['resultat'].modules, libre['resultat'].modules)
        self.assertEqual(villa['resultat'].hash_entree,
                         libre['resultat'].hash_entree)
        self.assertEqual(villa['preuve']['methode'],
                         libre['preuve']['methode'])
        self.assertEqual(villa['preuve']['compte_optimal'],
                         libre['preuve']['compte_optimal'])

    def test_l_ordre_latlng_reste_explicite_et_jamais_devine(self):
        droit = selectors.calepinage_villa(_area('lnglat'), ordre='lnglat')
        inverse = selectors.calepinage_villa(_area('latlng'), ordre='latlng')
        self.assertEqual(droit['resultat'].modules,
                         inverse['resultat'].modules)
        with self.assertRaises(ValueError):
            selectors.calepinage_villa(_area(), ordre='xy')
