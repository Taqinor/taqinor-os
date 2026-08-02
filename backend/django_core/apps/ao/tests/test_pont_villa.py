"""AOF163 — point d'entrée VILLA du moteur PARTAGÉ, SANS projet AO.

Le moteur ``core/calepinage`` a deux consommateurs qui ne peuvent pas
s'importer l'un l'autre (``apps.ao`` et ``apps.ventes``). Ce module prouve
trois choses, et rien d'autre :

  1. **Un appel villa ne crée AUCUNE ligne AO.** Une villa n'a pas d'appel
     d'offres : si la simulation résidentielle déposait un ``AppelOffre``, un
     ``BatimentAO`` ou une ``VarianteCalepinage`` fantôme, elle fausserait
     chaque compteur du module ET ferait fuiter des toitures de particuliers
     dans le tableau de bord des marchés publics.
  2. **Le résultat est le MÊME objet** que le chemin AO : un
     ``ResultatCalepinage`` portant le couple ``(hash_entree, version_moteur)``
     + un dict de preuve — jamais un dict maison propre à la villa.
  3. **Le compte est le MÊME** que celui du chemin AO sur la MÊME géométrie :
     la villa passe par l'adaptateur d'AOF162 pour arriver au format canonique
     AO, elle n'a pas de moteur à elle.

Run :
    python manage.py test apps.ao.tests.test_pont_villa -v2
"""
import math

from django.test import SimpleTestCase, TestCase

from apps.ao import selectors, services
from apps.ao.models import (
    AppelOffre, BatimentAO, ObstacleAO, ToitureAO, VarianteCalepinage,
)
from core.calepinage.adaptateurs.villa import (
    DEGAGEMENT_VILLA_M, RETRAIT_VILLA_M, Projection,
)
from core.calepinage.politique_pas import AntiOmbrage
from core.calepinage.serialisation import ResultatCalepinage
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.types import (
    KIT_VILLA_720, Axe, Obstacle, Parametres, Provenance, Rives, TypeObstacle,
)

#: Ancre géographique de la villa d'essai (Casablanca) — le point d'ancrage
#: n'a aucune importance métier : il ne sert qu'à faire l'aller-retour
#: mètres -> degrés -> mètres et à prouver que rien ne se perd en route.
LAT0, LNG0 = 33.5731, -7.5898

#: Rectangle de toiture CENTRÉ sur l'ancre (14 m est-ouest × 10 m nord-sud).
#: Le centrage est délibéré : le barycentre local vaut (0, 0), donc la
#: projection que l'adaptateur re-dérive lui-même retombe sur la même ancre et
#: l'aller-retour est exact au flottant près.
DEMI_LARGEUR_M, DEMI_HAUTEUR_M = 7.0, 5.0

#: Un obstacle unique, déclaré par le client (édicule d'escalier).
OBSTACLE_CENTRE_M = (2.0, 1.0)
OBSTACLE_LARGEUR_M, OBSTACLE_PROFONDEUR_M = 1.6, 1.2


def _projection():
    return Projection(lat0_deg=LAT0, lng0_deg=LNG0)


def _contour_local():
    """Les 4 sommets du rectangle, en mètres locaux (est, nord)."""
    return (
        (-DEMI_LARGEUR_M, -DEMI_HAUTEUR_M),
        (DEMI_LARGEUR_M, -DEMI_HAUTEUR_M),
        (DEMI_LARGEUR_M, DEMI_HAUTEUR_M),
        (-DEMI_LARGEUR_M, DEMI_HAUTEUR_M),
    )


def _area_villa(ordre='lnglat'):
    """L'``AreaRecord`` du lecteur de cartes pour cette même toiture."""
    projection = _projection()
    points = []
    for est, nord in _contour_local():
        lat, lng = projection.vers_geo(est, nord)
        points.append([lng, lat] if ordre == 'lnglat' else [lat, lng])
    lat_c, lng_c = projection.vers_geo(*OBSTACLE_CENTRE_M)
    centre = [lng_c, lat_c] if ordre == 'lnglat' else [lat_c, lng_c]
    return {
        'id': 'VILLA_ESSAI',
        'polygon': points,
        'flat': True,
        'tilt': 0.0,
        'azimuth': 180.0,
        'obstacles': [{
            'id': 'EDICULE',
            'center': centre,
            'widthM': OBSTACLE_LARGEUR_M,
            'heightM': OBSTACLE_PROFONDEUR_M,
        }],
    }


def _chemin_ao():
    """La MÊME toiture exprimée dans le format CANONIQUE (celui de l'AO).

    Aucune ligne de base n'est touchée : le chemin AO est ici son format
    d'entrée, pas sa persistance — c'est précisément ce que le moteur partagé
    consomme des deux côtés.
    """
    rives = Rives(laterale_m=RETRAIT_VILLA_M, extremite_m=RETRAIT_VILLA_M)
    surface = SurfacePolygone(
        repere='VILLA_ESSAI', contour=_contour_local(), rives=rives,
        axe_rangee=Axe.EST_OUEST, pente_deg=0.0, azimut_deg=180.0)
    cx, cy = OBSTACLE_CENTRE_M
    obstacle = Obstacle(
        repere='EDICULE',
        x0=cx - OBSTACLE_LARGEUR_M / 2.0, x1=cx + OBSTACLE_LARGEUR_M / 2.0,
        y0=cy - OBSTACLE_PROFONDEUR_M / 2.0,
        y1=cy + OBSTACLE_PROFONDEUR_M / 2.0,
        type_obstacle=TypeObstacle.NATURE_INCONNUE,
        provenance=Provenance.DECLARE_CLIENT,
        degagement_m=DEGAGEMENT_VILLA_M)
    parametres = Parametres(kits=(KIT_VILLA_720,), rives=rives,
                            axe_rangee=Axe.EST_OUEST, allee_m=0.0,
                            pas_recherche_m=0.01)
    return services.calepiner_surface(
        surface=surface, kits=(KIT_VILLA_720,), parametres=parametres,
        obstacles=(obstacle,), politique=AntiOmbrage(), repere='VILLA_ESSAI')


class LeMoteurEstPartage(SimpleTestCase):
    """Le compte de la villa EST le compte du chemin AO — pas « environ »."""

    def test_meme_compte_sur_la_meme_geometrie(self):
        villa = services.calepiner_villa(_area_villa())
        ao = _chemin_ao()
        self.assertEqual(villa['resultat'].modules, ao['resultat'].modules)
        self.assertGreater(villa['resultat'].modules, 0)

    def test_meme_preuve_et_meme_empreinte_d_entree(self):
        villa = services.calepiner_villa(_area_villa())
        ao = _chemin_ao()
        self.assertEqual(villa['resultat'].hash_entree,
                         ao['resultat'].hash_entree)
        self.assertEqual(villa['preuve']['compte_optimal'],
                         ao['preuve']['compte_optimal'])
        self.assertEqual(villa['preuve']['methode'], ao['preuve']['methode'])

    def test_le_resultat_est_le_meme_TYPE_que_le_chemin_ao(self):
        villa = services.calepiner_villa(_area_villa())
        self.assertIsInstance(villa['resultat'], ResultatCalepinage)
        self.assertTrue(villa['resultat'].hash_entree)
        self.assertTrue(villa['resultat'].version_moteur)

    def test_la_politique_villa_est_l_anti_ombrage_sur_toit_plat(self):
        villa = services.calepiner_villa(_area_villa())
        self.assertEqual(villa['politique'].code, 'ANTI_OMBRAGE')
        self.assertEqual(villa['preuve']['politique_pas'], 'ANTI_OMBRAGE')

    def test_l_ordre_latlng_est_explicite_et_jamais_devine(self):
        """Le même contour lu en ``latlng`` donne le MÊME compte.

        C'est le piège d'AOF162 : le lecteur de cartes sérialise en
        ``[lng, lat]``, le lead CRM en ``[lat, lng]``. Passer l'ordre est un
        ARGUMENT ; se tromper donne une toiture retournée, plausible et fausse.
        """
        droit = services.calepiner_villa(_area_villa('lnglat'),
                                         ordre='lnglat')
        inverse = services.calepiner_villa(_area_villa('latlng'),
                                           ordre='latlng')
        self.assertEqual(droit['resultat'].modules,
                         inverse['resultat'].modules)

    def test_un_ordre_inconnu_est_refuse(self):
        with self.assertRaises(ValueError):
            services.calepiner_villa(_area_villa(), ordre='xy')

    def test_les_panneaux_reviennent_en_lnglat_pour_l_ecran(self):
        villa = services.calepiner_villa(_area_villa())
        self.assertEqual(len(villa['panneaux']), len(villa['tables']))
        for panneau in villa['panneaux']:
            self.assertEqual(len(panneau['corners']), 4)
            for lng, lat in panneau['corners']:
                self.assertTrue(math.isclose(lat, LAT0, abs_tol=0.01))
                self.assertTrue(math.isclose(lng, LNG0, abs_tol=0.01))


class LaVillaNeCreeAucuneLigneAO(TestCase):
    """Une villa n'a pas de projet AO : elle ne doit rien laisser derrière."""

    #: TOUS les modèles que le chemin AO écrirait pour un vrai calepinage.
    MODELES = (AppelOffre, BatimentAO, ToitureAO, ObstacleAO,
               VarianteCalepinage)

    def test_aucune_ligne_ao_apres_un_calepinage_villa(self):
        avant = {m.__name__: m.objects.count() for m in self.MODELES}
        services.calepiner_villa(_area_villa())
        apres = {m.__name__: m.objects.count() for m in self.MODELES}
        self.assertEqual(avant, apres)

    def test_aucune_ligne_ao_apres_un_calepinage_de_surface_libre(self):
        avant = {m.__name__: m.objects.count() for m in self.MODELES}
        _chemin_ao()
        apres = {m.__name__: m.objects.count() for m in self.MODELES}
        self.assertEqual(avant, apres)


class LeSelectorEstLaPorteCrossApp(SimpleTestCase):
    """``apps.ventes`` lit le moteur par ``apps.ao.selectors``, jamais autrement."""

    def test_le_selector_villa_rend_le_meme_compte_que_le_service(self):
        par_selector = selectors.calepinage_villa(_area_villa())
        par_service = services.calepiner_villa(_area_villa())
        self.assertEqual(par_selector['resultat'].modules,
                         par_service['resultat'].modules)

    def test_le_selector_de_surface_libre_existe_et_calcule(self):
        rives = Rives(laterale_m=RETRAIT_VILLA_M, extremite_m=RETRAIT_VILLA_M)
        surface = SurfacePolygone(
            repere='LIBRE', contour=_contour_local(), rives=rives,
            axe_rangee=Axe.EST_OUEST)
        parametres = Parametres(kits=(KIT_VILLA_720,), rives=rives,
                                axe_rangee=Axe.EST_OUEST, allee_m=0.0,
                                pas_recherche_m=0.01)
        sortie = selectors.calepinage_sans_projet(
            surface=surface, kits=(KIT_VILLA_720,), parametres=parametres,
            politique=AntiOmbrage(), repere='LIBRE')
        self.assertGreater(sortie['resultat'].modules, 0)
