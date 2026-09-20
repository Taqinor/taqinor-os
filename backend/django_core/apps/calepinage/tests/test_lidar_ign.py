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
    libelle_source,
    refuser_suggestion,
    service_disponible,
    suggerer_pentes,
)
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
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

    ex = 111320.0 * math.cos(math.radians(LAT))
    ey = 110540.0
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


class DecisionHumaineTest(SimpleTestCase):
    """Accepter écrit ; refuser ne touche à rien."""

    def _suggestion(self):
        return {'zoneId': 'pan-sud', 'pitchDeg': 22.5,
                'facingAzimuthDeg': 180.0, 'source': SOURCE,
                'sourceUrl': 'https://data.geopf.fr/altimetrie/',
                'suggestedAt': '2026-03-12T10:00:00+00:00',
                'status': SUGGEREE, 'points': 5}

    def test_accepter_ecrit_la_pente_et_garde_la_trace(self):
        pan = accepter_suggestion({'id': 'pan-sud'}, self._suggestion(),
                                  maintenant='2026-03-12T11:00:00+00:00')
        self.assertEqual(pan['pitchDeg'], 22.5)
        self.assertEqual(pan['facingAzimuthDeg'], 180.0)
        self.assertFalse(pan['facingManual'])
        self.assertEqual(pan['pitchSuggestion']['status'], VALIDEE)
        self.assertEqual(pan['pitchSuggestion']['source'], SOURCE)

    def test_accepter_un_toit_plat_n_ecrit_aucun_azimut(self):
        suggestion = self._suggestion()
        suggestion.update(pitchDeg=0.4, facingAzimuthDeg=None)
        pan = accepter_suggestion({'id': 'plat'}, suggestion,
                                  maintenant='2026-03-12')
        self.assertEqual(pan['pitchDeg'], 0.4)
        self.assertNotIn('facingAzimuthDeg', pan)

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
        self.assertEqual(libelle_source(pan['pitchSuggestion']),
                         'source IGN (suggestion validée le 12/03/2026)')

    def test_aucun_libelle_avant_decision_ni_apres_refus(self):
        self.assertEqual(libelle_source(self._suggestion()), '')
        pan = refuser_suggestion({}, self._suggestion(),
                                 maintenant='2026-03-12')
        self.assertEqual(libelle_source(pan['pitchSuggestion']), '')


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
