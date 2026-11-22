"""CAL237 — la suggestion de pente/azimut IGN : gatée, sourcée, jamais subie.

CE QUI EST PROUVÉ ICI
---------------------
* **GATAGE AVANT LE RÉSEAU** — une société dont le pays n'est pas ``fr`` (ou
  qui n'a rien réglé) n'a pas ce service, et l'altimètre ESPION compte ZÉRO
  appel : le refus tombe avant toute sortie réseau, pas après ;
* **une suggestion reste une suggestion** — ``suggerer_pentes`` ne modifie
  AUCUN document ; c'est ``accepter_suggestion`` qui écrit la pente sur le
  pan, et ``refuser_suggestion`` ne touche à rien : la valeur SAISIE reste la
  seule vérité ;
* **la provenance suit le chiffre** — une suggestion validée produit
  « source IGN (suggestion validée le … ) » ; une suggestion en attente ou
  refusée ne produit AUCUN libellé (on ne cite une source que pour un chiffre
  qui en vient) ;
* **zéro chiffre inventé** — pan sans altitude, altitudes hors couverture
  (``-99999``), points alignés ou géométrie trop pauvre ⇒ AUCUNE suggestion ;
  un toit quasi plat reçoit une pente mais PAS d'azimut ;
* **la géométrie est juste** — un plan artificiel de pente connue est
  retrouvé, et l'azimut pointe bien la descente (sud, est, ouest, nord) ;
* l'endpoint rend 403 avec le champ « pays » nommé hors France, 400 sans
  document, et la société vient TOUJOURS de l'appelant.

Aucun test ne sort sur le réseau : l'altimètre est injecté.

Run :
    python manage.py test apps.calepinage.tests.test_lidar_ign -v2
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.services.lidar_ign import (
    REFUSEE,
    SOURCE,
    SUGGEREE,
    VALIDEE,
    ServiceIndisponible,
    _ajuster_plan,
    _altitudes_de_la_reponse,
    accepter_suggestion,
    _libelle_source,
    refuser_suggestion,
    service_disponible,
    suggerer_pentes,
)
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

User = get_user_model()

URL = '/api/django/calepinage/parametres/suggestion-pente/'

#: Un pan carré de ~20 m de côté près de Lyon.
LON, LAT = 4.8357, 45.7640
COTE = 0.00025          # ≈ 20 m en latitude

PAN = {
    'id': 'pan-sud',
    'label': 'Versant sud',
    'vertices': [
        [LON, LAT],
        [LON + COTE, LAT],
        [LON + COTE, LAT + COTE],
        [LON, LAT + COTE],
    ],
}
DOCUMENT = {'version': 2, 'zones': [PAN]}


class AltimetreEspion:
    """Un altimètre qui COMPTE ses appels et ne sort jamais sur le réseau."""

    def __init__(self, plan=None, altitudes=None):
        #: ``plan`` = (a, b, c) : z = a·x + b·y + c, x/y en degrés.
        self.plan = plan
        self.altitudes = altitudes
        self.appels = 0
        self.points = []

    def __call__(self, points):
        self.appels += 1
        points = list(points)
        self.points.extend(points)
        if self.altitudes is not None:
            return list(self.altitudes)[:len(points)] \
                + [None] * max(0, len(points) - len(self.altitudes))
        a, b, c = self.plan
        return [a * (lon - LON) + b * (lat - LAT) + c for lon, lat in points]


def _plan_descendant_vers(direction, pente_m_par_m=0.2):
    """(a, b, c) d'un plan qui DESCEND vers ``direction``, en degrés.

    Les coefficients sont exprimés par DEGRÉ (c'est l'unité des sommets), donc
    la pente métrique est multipliée par l'échelle locale.
    """
    import math

    ex = (math.pi / 180.0 * 6378137.0) * math.cos(math.radians(LAT))
    ey = (math.pi / 180.0 * 6378137.0)
    vers = {
        'sud': (0.0, +pente_m_par_m),      # z croît vers le nord
        'nord': (0.0, -pente_m_par_m),
        'ouest': (+pente_m_par_m, 0.0),    # z croît vers l'est
        'est': (-pente_m_par_m, 0.0),
    }[direction]
    return vers[0] * ex, vers[1] * ey, 200.0


def _societe(pays):
    company = Company.objects.create(
        nom=f'LiDAR {pays or "sans"}',
        slug=f'lidar-{pays or "sans"}-237')
    if pays:
        enregistrer_parametres(company, {'imagerie': {'pays': pays}})
    return company


class GatagePaysTest(TestCase):
    """Hors France : service ABSENT, et ZÉRO requête sortante."""

    def test_societe_francaise_a_le_service(self):
        self.assertTrue(service_disponible(_societe('fr')))

    def test_societe_marocaine_ne_l_a_pas(self):
        self.assertFalse(service_disponible(_societe('ma')))

    def test_societe_sans_reglage_ne_l_a_pas(self):
        """On ne SUPPOSE pas un pays : sans réglage, pas de service."""
        self.assertFalse(service_disponible(_societe(None)))

    def test_sans_societe_pas_de_service(self):
        self.assertFalse(service_disponible(None))

    def test_hors_france_aucune_requete_sortante(self):
        espion = AltimetreEspion(plan=_plan_descendant_vers('sud'))
        with self.assertRaises(ServiceIndisponible) as capture:
            suggerer_pentes(_societe('ma'), DOCUMENT, altimetre=espion)
        self.assertEqual(capture.exception.champ, 'pays')
        self.assertIn('France', str(capture.exception))
        self.assertEqual(espion.appels, 0)

    def test_sans_reglage_aucune_requete_sortante(self):
        espion = AltimetreEspion(plan=_plan_descendant_vers('sud'))
        with self.assertRaises(ServiceIndisponible):
            suggerer_pentes(_societe(None), DOCUMENT, altimetre=espion)
        self.assertEqual(espion.appels, 0)


class SuggestionTest(TestCase):
    """La suggestion est produite, sourcée, et ne touche à RIEN."""

    def setUp(self):
        self.company = _societe('fr')
        self.espion = AltimetreEspion(plan=_plan_descendant_vers('sud'))

    def _suggestions(self, document=None, **kwargs):
        return suggerer_pentes(self.company, document or DOCUMENT,
                               altimetre=self.espion,
                               maintenant='2026-03-12T10:00:00+00:00',
                               **kwargs)

    def test_une_suggestion_par_pan(self):
        suggestions = self._suggestions()
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]['zoneId'], 'pan-sud')

    def test_la_suggestion_porte_sa_source_et_sa_date(self):
        suggestion = self._suggestions()[0]
        self.assertEqual(suggestion['source'], SOURCE)
        self.assertIn('IGN', suggestion['source'])
        self.assertTrue(suggestion['sourceUrl'].startswith('https://'))
        self.assertEqual(suggestion['suggestedAt'][:10], '2026-03-12')
        self.assertEqual(suggestion['status'], SUGGEREE)

    def test_le_document_n_est_jamais_modifie(self):
        """Rien n'est appliqué sans validation humaine."""
        document = {'version': 2, 'zones': [dict(PAN)]}
        self._suggestions(document)
        self.assertNotIn('pitchDeg', document['zones'][0])
        self.assertNotIn('pitchSuggestion', document['zones'][0])

    def test_une_seule_requete_par_pan(self):
        self._suggestions()
        self.assertEqual(self.espion.appels, 1)

    def test_pente_retrouvee(self):
        """Une pente de 0,2 m/m vaut ~11,3°."""
        suggestion = self._suggestions()[0]
        self.assertAlmostEqual(suggestion['pitchDeg'], 11.3, delta=0.3)

    def test_azimut_pointe_la_descente(self):
        for direction, attendu in (('sud', 180.0), ('nord', 0.0),
                                   ('est', 90.0), ('ouest', 270.0)):
            self.espion = AltimetreEspion(
                plan=_plan_descendant_vers(direction))
            azimut = self._suggestions()[0]['facingAzimuthDeg']
            ecart = min(abs(azimut - attendu), 360.0 - abs(azimut - attendu))
            self.assertLess(ecart, 1.0, f'{direction} -> {azimut}')


class RienNEstInventeTest(TestCase):
    """Pas de donnée ⇒ pas de suggestion. Jamais un chiffre de repli."""

    def setUp(self):
        self.company = _societe('fr')

    def _suggestions(self, espion, document=None):
        return suggerer_pentes(self.company, document or DOCUMENT,
                               altimetre=espion, maintenant='2026-03-12')

    def test_altitudes_absentes_aucune_suggestion(self):
        self.assertEqual(
            self._suggestions(AltimetreEspion(altitudes=[None] * 5)), [])

    def test_altitudes_partielles_insuffisantes(self):
        self.assertEqual(
            self._suggestions(AltimetreEspion(altitudes=[210.0, None, None,
                                                         None, None])), [])

    def test_points_de_meme_altitude_donnent_un_toit_plat_sans_azimut(self):
        suggestion = self._suggestions(
            AltimetreEspion(altitudes=[200.0] * 5))[0]
        self.assertEqual(suggestion['pitchDeg'], 0.0)
        self.assertIsNone(suggestion['facingAzimuthDeg'])

    def test_pan_sans_assez_de_sommets(self):
        document = {'zones': [{'id': 'x', 'vertices': [[LON, LAT]]}]}
        self.assertEqual(
            self._suggestions(AltimetreEspion(altitudes=[200.0]), document),
            [])

    def test_document_sans_pan(self):
        self.assertEqual(
            self._suggestions(AltimetreEspion(altitudes=[]), {'zones': []}),
            [])


class ReponseIgnTest(SimpleTestCase):
    """La réponse IGN est lue avec méfiance : ``-99999`` = pas de donnée."""

    def test_hors_couverture_devient_none(self):
        charge = {'elevations': [{'z': -99999.0}, {'z': 212.5}]}
        self.assertEqual(_altitudes_de_la_reponse(charge, 2), [None, 212.5])

    def test_reponse_vide_rend_des_none(self):
        self.assertEqual(_altitudes_de_la_reponse({}, 3), [None, None, None])

    def test_reponse_courte_est_completee_de_none(self):
        charge = {'elevations': [{'z': 200.0}]}
        self.assertEqual(_altitudes_de_la_reponse(charge, 3),
                         [200.0, None, None])

    def test_plan_degenere_rend_none(self):
        """Points alignés : plan indéterminé ⇒ aucune suggestion."""
        alignes = [(0.0, 0.0, 10.0), (0.0, 1e-4, 11.0), (0.0, 2e-4, 12.0)]
        self.assertIsNone(_ajuster_plan(alignes))


class CorpsDuPostJsonSeulTest(SimpleTestCase):
    """CI #1001 : ``roof_layout`` (pans imbriqués) ne se transporte pas dans un
    formulaire — la porte ne prend que du JSON, le schéma publié aussi."""

    def test_le_post_ne_prend_que_du_json(self):
        from rest_framework.parsers import JSONParser

        from apps.calepinage.views.parametres import SuggestionPenteIGNView

        self.assertEqual(SuggestionPenteIGNView.parser_classes, [JSONParser])


class DecisionHumaineTest(SimpleTestCase):
    """Accepter garde la trace ; refuser ne touche à rien."""

    def _suggestion(self):
        return {'zoneId': 'pan-sud', 'pitchDeg': 22.5,
                'facingAzimuthDeg': 180.0, 'source': SOURCE,
                'sourceUrl': 'https://data.geopf.fr/altimetrie/',
                'suggestedAt': '2026-03-12T10:00:00+00:00',
                'status': SUGGEREE, 'points': 5}

    def test_accepter_garde_la_trace_sans_ecrire_la_pente_du_pan(self):
        """D-ACAL-19 (ACAL65) : la pente IGN est celle du TERRAIN."""
        pan = accepter_suggestion(
            {'id': 'pan-sud', 'pitchDeg': 15.0}, self._suggestion(),
            maintenant='2026-03-12T11:00:00+00:00')
        self.assertEqual(pan['pitchDeg'], 15.0)
        self.assertNotIn('facingAzimuthDeg', pan)
        self.assertNotIn('facingManual', pan)
        self.assertEqual(pan['pitchSuggestion']['status'], VALIDEE)
        self.assertEqual(pan['pitchSuggestion']['valeurDeg'], 22.5)
        self.assertEqual(pan['pitchSuggestion']['source'], SOURCE)

    def test_accepter_un_pan_sans_pente_n_en_invente_pas(self):
        pan = accepter_suggestion({'id': 'plat'}, self._suggestion(),
                                  maintenant='2026-03-12')
        self.assertNotIn('pitchDeg', pan)

    def test_refuser_laisse_la_saisie_seule_verite(self):
        pan = refuser_suggestion(
            {'id': 'pan-sud', 'pitchDeg': 30.0, 'facingAzimuthDeg': 175.0,
             'facingManual': True},
            self._suggestion(), maintenant='2026-03-12T11:00:00+00:00')
        self.assertEqual(pan['pitchDeg'], 30.0)
        self.assertEqual(pan['facingAzimuthDeg'], 175.0)
        self.assertTrue(pan['facingManual'])
        self.assertEqual(pan['pitchSuggestion']['status'], REFUSEE)

    def test_libelle_apres_validation(self):
        pan = accepter_suggestion({}, self._suggestion(),
                                  maintenant='2026-03-12T11:00:00+00:00')
        self.assertEqual(_libelle_source(pan['pitchSuggestion']),
                         'source IGN (suggestion validée le 12/03/2026)')

    def test_aucun_libelle_avant_decision_ni_apres_refus(self):
        self.assertEqual(_libelle_source(self._suggestion()), '')
        pan = refuser_suggestion({}, self._suggestion(),
                                 maintenant='2026-03-12')
        self.assertEqual(_libelle_source(pan['pitchSuggestion']), '')


class EndpointTest(TestCase):
    """La porte HTTP : gatée, française dans ses refus, sans persistance."""

    def setUp(self):
        self.company = _societe('fr')
        self.hors_france = _societe('ma')
        self.api = self._api(self.company, 'cal237_fr')
        self.api_ma = self._api(self.hors_france, 'cal237_ma')

    @staticmethod
    def _api(company, nom):
        role = Role.objects.create(company=company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(username=nom, password='x',
                                        company=company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_get_dit_si_le_service_est_offert(self):
        reponse = self.api.get(URL)
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['disponible'])
        self.assertEqual(reponse.data['suggestions'], [])

    def test_get_hors_france_dit_non(self):
        reponse = self.api_ma.get(URL)
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.data['disponible'])

    def test_post_hors_france_refuse_en_nommant_le_pays(self):
        reponse = self.api_ma.post(URL, {'roof_layout': DOCUMENT},
                                   format='json')
        self.assertEqual(reponse.status_code, 403)
        self.assertIn('pays', reponse.data)
        self.assertFalse(reponse.data['disponible'])

    def test_post_sans_document_refuse(self):
        reponse = self.api.post(URL, {'roof_layout': {}}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('roof_layout', reponse.data)

    def test_post_zones_mal_formees_refusees_avant_tout_appel(self):
        """ERR-ENF11-FUZZ-CALEPINAGE (w4) — UN prédicat avec le schéma publié
        (``zones`` : liste NON VIDE d'objets) : une valeur d'un autre type
        n'est jamais « lue vide » par le service, même en France (200 à tort)."""
        for zones in ([], 'AAA', {}, 0, None, [0], [None], ['AAA'], [{}, 5]):
            reponse = self.api.post(
                URL, {'roof_layout': {'zones': zones}}, format='json')
            self.assertEqual(reponse.status_code, 400, zones)
            self.assertIn('roof_layout', reponse.data)


# ---------------------------------------------------------------------------
# ACAL534 — l'altimètre d'un relief GeoTIFF fourni par l'installateur.
# ---------------------------------------------------------------------------

def _geotiff(*, modele=2, pente_deg=20.0, taille=400, pas=1e-5,
             geo=True, mode='F', sans_donnee=None):
    """Les octets d'un GeoTIFF float32 en degrés, incliné vers le SUD."""
    import io
    import math

    import numpy as np
    from PIL import Image, TiffImagePlugin, TiffTags

    metres_par_degre = math.pi / 180.0 * 6378137.0
    lat_haut = LAT + taille * pas / 2.0
    lignes = np.arange(taille, dtype='float64')[:, None]
    lat = lat_haut - (lignes + 0.5) * pas
    relief = np.tan(math.radians(pente_deg)) * (lat - LAT) * metres_par_degre
    tableau = np.repeat(relief + 200.0, taille, axis=1).astype('float32')
    image = Image.fromarray(tableau, mode=mode)
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    if geo:
        ifd[33550] = (pas, pas, 0.0)
        ifd.tagtype[33550] = TiffTags.DOUBLE
        ifd[33922] = (0.0, 0.0, 0.0, LON - taille * pas / 2.0, lat_haut, 0.0)
        ifd.tagtype[33922] = TiffTags.DOUBLE
        ifd[34735] = (1, 1, 0, 3, 1024, 0, 1, modele, 1025, 0, 1, 1,
                      2048, 0, 1, 4326)
        ifd.tagtype[34735] = TiffTags.SHORT
    tampon = io.BytesIO()
    image.save(tampon, format='TIFF', tiffinfo=ifd)
    return tampon.getvalue()


class AltimetreFichierTest(SimpleTestCase):
    """ACAL534 — pente 20° vers le sud retrouvée ; refus nommés."""

    def _suggestion(self, octets):
        from unittest import mock

        from apps.calepinage.services.altimetre_fichier import (
            altimetre_depuis_geotiff)

        altimetre = altimetre_depuis_geotiff(octets)
        with mock.patch(
                'apps.calepinage.services.lidar_ign.service_disponible',
                return_value=True):
            return suggerer_pentes(
                object(), DOCUMENT, altimetre=altimetre,
                maintenant='2026-03-12T10:00:00+00:00')

    def test_relief_incline_de_20_degres_vers_le_sud(self):
        (suggestion,) = self._suggestion(_geotiff())
        self.assertAlmostEqual(suggestion['pitchDeg'], 20.0, delta=0.1)
        self.assertAlmostEqual(suggestion['facingAzimuthDeg'], 180.0,
                               delta=0.1)

    def test_hors_emprise_rend_none_jamais_un_repli(self):
        from apps.calepinage.services.altimetre_fichier import (
            altimetre_depuis_geotiff)

        altimetre = altimetre_depuis_geotiff(_geotiff())
        dedans, dehors = altimetre([(LON, LAT), (LON + 1.0, LAT)])
        self.assertIsNotNone(dedans)
        self.assertIsNone(dehors)

    def test_projection_en_metres_refusee_en_la_nommant(self):
        from apps.calepinage.services.altimetre_fichier import (
            ReliefIllisible, altimetre_depuis_geotiff)

        with self.assertRaises(ReliefIllisible) as ctx:
            altimetre_depuis_geotiff(_geotiff(modele=1))
        self.assertEqual(
            str(ctx.exception),
            'Le relief est en mètres (projection) : exportez-le en WGS84 '
            '(degrés).')

    def test_sans_georeferencement_ou_illisible_refuse(self):
        from apps.calepinage.services.altimetre_fichier import (
            ReliefIllisible, altimetre_depuis_geotiff)

        with self.assertRaises(ReliefIllisible) as sans_etiquettes:
            altimetre_depuis_geotiff(_geotiff(geo=False))
        self.assertIn('géoréférencement', str(sans_etiquettes.exception))
        with self.assertRaises(ReliefIllisible) as illisible:
            altimetre_depuis_geotiff(b'ceci n est pas un tiff')
        self.assertIn('illisible', str(illisible.exception))

    def test_image_sans_altitudes_lisibles_refusee(self):
        from apps.calepinage.services.altimetre_fichier import (
            ReliefIllisible, altimetre_depuis_geotiff)
        import io

        from PIL import Image

        tampon = io.BytesIO()
        Image.new('RGB', (4, 4)).save(tampon, format='TIFF')
        with self.assertRaises(ReliefIllisible) as ctx:
            altimetre_depuis_geotiff(tampon.getvalue())
        self.assertIn('altitudes', str(ctx.exception))


class ReliefFourniHorsFranceTest(SimpleTestCase):
    """ACAL535 — société hors France : le relief déposé ouvre la porte, l'IGN jamais."""

    def _hors_france(self):
        from unittest import mock

        return mock.patch(
            'apps.calepinage.services.lidar_ign.service_disponible',
            return_value=False)

    def test_depuis_fichier_saute_la_porte_du_pays_et_cite_le_fichier(self):
        from unittest import mock

        from apps.calepinage.services.altimetre_fichier import (
            altimetre_depuis_geotiff)
        from apps.calepinage.services.lidar_ign import SOURCE_RELIEF

        with self._hors_france(), mock.patch(
                'apps.calepinage.services.lidar_ign._altimetre_ign') as ign:
            (suggestion,) = suggerer_pentes(
                object(), DOCUMENT,
                altimetre=altimetre_depuis_geotiff(_geotiff()),
                depuis_fichier=True, maintenant='2026-03-12T10:00:00+00:00')
        ign.assert_not_called()
        self.assertEqual(suggestion['source'], SOURCE_RELIEF)
        self.assertIsNone(suggestion['sourceUrl'])
        self.assertEqual(suggestion['status'], SUGGEREE)
        self.assertAlmostEqual(suggestion['pitchDeg'], 20.0, delta=0.1)

    def test_sans_depuis_fichier_la_porte_reste_fermee(self):
        espion = AltimetreEspion(plan=_plan_descendant_vers('sud'))
        from unittest import mock

        with self._hors_france(), mock.patch(
                'apps.calepinage.selectors.imagerie_site',
                return_value={'pays': 'ma'}),                 self.assertRaises(ServiceIndisponible):
            suggerer_pentes(object(), DOCUMENT, altimetre=espion)
        self.assertEqual(espion.appels, 0)

    def test_depuis_fichier_sans_altimetre_ne_part_jamais_vers_l_ign(self):
        with self._hors_france(), self.assertRaises(ValueError):
            suggerer_pentes(object(), DOCUMENT, depuis_fichier=True)

    def test_libelle_de_la_source_validee(self):
        from apps.calepinage.services.lidar_ign import SOURCE_RELIEF

        self.assertEqual(
            _libelle_source({'status': VALIDEE, 'source': SOURCE_RELIEF,
                             'decidedAt': '2026-03-12T10:00:00+00:00'}),
            "source : relief fourni par l'installateur "
            '(suggestion validée le 12/03/2026)')


class SuggestionReliefApiTest(TestCase):
    """ACAL535 — ``POST suggestions-pente-relief/`` d'une société marocaine."""

    def setUp(self):
        from apps.calepinage.models import Calepinage
        from apps.calepinage.services.layout import enregistrer_layout
        from apps.crm.models import Lead

        self.company = _societe('ma')
        self.api = EndpointTest._api(self.company, 'acal535_ma')
        self.user = User.objects.get(username='acal535_ma')
        # Un calepinage porte un lead ou un client (contrainte
        # ``calepinage_lead_ou_client``).
        lead = Lead.objects.create(company=self.company, nom='QA-ACAL535')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='QA-ACAL535')
        enregistrer_layout(self.calepinage, {
            'version': 2, 'zones': [dict(PAN, pitchDeg=18)]}, user=self.user)
        self.url = ('/api/django/calepinage/calepinages/'
                    f'{self.calepinage.pk}/suggestions-pente-relief/')
        self.base = self.api.get(
            f'/api/django/calepinage/calepinages/{self.calepinage.pk}/layout/'
        ).data['empreinte_document']

    def _poster(self, octets, base=None, nom='relief.tif'):
        from unittest import mock

        from django.core.files.uploadedfile import SimpleUploadedFile

        corps = {'base_empreinte': self.base if base is None else base}
        if octets is not None:
            corps['relief'] = SimpleUploadedFile(nom, octets)
        with mock.patch('apps.calepinage.services.lidar_ign._altimetre_ign',
                        side_effect=AssertionError('appel IGN')) as ign:
            reponse = self.api.post(self.url, corps, format='multipart')
        ign.assert_not_called()
        return reponse

    def test_societe_marocaine_obtient_une_suggestion_du_relief(self):
        reponse = self._poster(_geotiff())
        self.assertEqual(reponse.status_code, 200, reponse.data)
        pan = reponse.data['roof_layout']['zones'][0]
        suggestion = pan['pitchSuggestion']
        self.assertEqual(suggestion['status'], 'suggeree')
        self.assertEqual(suggestion['source'],
                         "relief fourni par l'installateur")
        self.assertAlmostEqual(suggestion['valeurDeg'], 20.0, delta=0.1)
        self.assertEqual(pan['pitchDeg'], 18)   # jamais recopiée (D-ACAL-19)

    def test_fichier_en_metres_ou_absent_refuse_en_nommant_relief(self):
        for octets in (_geotiff(modele=1), b'pas un tiff', None):
            reponse = self._poster(octets)
            self.assertEqual(reponse.status_code, 400, reponse.data)
            self.assertIn('relief', reponse.data)

    def test_jeton_perime_409(self):
        reponse = self._poster(_geotiff(), base='perime')
        self.assertEqual(reponse.status_code, 409, reponse.data)
