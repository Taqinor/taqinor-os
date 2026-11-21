"""CAL135 — le client ``seriescalc`` : zéro appel réseau, aucun repli.

ACAL329 — ``serie_horaire`` (le modèle PV de PVGIS, pertes passées en
``loss``) est supprimée : la cadence, le cache et les refus du client sont
prouvés ici sur ``serie_irradiance``, LA porte de la chaîne de pertes.

Les réponses rejouées ici sont des réponses PVGIS **RÉELLES**, enregistrées le
20/09/2026 depuis cette machine (``tests/fixtures_pvgis/*.json``, chacune
portant son bloc ``_provenance`` : l'URL exacte, la date, et le fait que seules
les lignes du 15 de chaque mois ont été gardées pour ne pas committer 830 ko).
AUCUNE irradiation n'a été fabriquée à la main — la règle « zéro chiffre
inventé » vaut aussi pour une fixture.
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.pvgis_serie import (
    BASE_PAR_DEFAUT, ClientPvgis, EntreeInvalide, PvgisIndisponible,
    _Cache, _horodatage, _Limiteur, azimut_pvgis, cle_de_cache,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'


def charger(nom):
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


class TransportEnregistre:
    """Transport INJECTÉ : rejoue une réponse enregistrée, jamais le réseau."""

    def __init__(self, charge=None, statut=200, erreur=None):
        self.charge = charge
        self.statut = statut
        self.erreur = erreur
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        if self.erreur is not None:
            raise self.erreur
        return self.statut, json.dumps(self.charge or {})


def client(transport, **kwargs):
    """Un client au cache PRIVÉ (un test ne pollue jamais un autre)."""
    kwargs.setdefault('cache', _Cache())
    kwargs.setdefault('dormir', lambda _s: None)
    return ClientPvgis(transport, **kwargs)


def appel(cli, **extra):
    params = dict(lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
                  annee_debut=2020, annee_fin=2020)
    params.update(extra)
    return cli.serie_irradiance(**params)


def serie_enregistree(nom='seriescalc_casablanca_sud.json', **extra):
    """ACAL329 — la série RÉELLE d'une fixture, lue par ``serie_irradiance``.

    Véhicule partagé des tests qui ont besoin de points horaires réels (le
    défunt ``serie_horaire`` jouait ce rôle). Chaque point reçoit en plus
    ``p_w`` : la colonne ``P`` de la MÊME réponse enregistrée, à la même
    heure — aucune valeur fabriquée, l'énergie que ces tests faisaient déjà
    circuler dans la chaîne.
    """
    charge = charger(nom)
    resultat = appel(client(TransportEnregistre(charge)), **extra)
    puissances = [ligne.get('P') for ligne in charge['outputs']['hourly']
                  if _horodatage(ligne.get('time')) is not None]
    for point, puissance in zip(resultat['points'], puissances):
        point['p_w'] = float(puissance) if puissance is not None else None
    return resultat


class SerieHoraireTest(unittest.TestCase):
    """La série est lue, publiée avec sa provenance, et jamais inventée."""

    def test_reponse_reelle_rejouee_donne_la_serie_et_sa_provenance(self):
        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud.json'))
        resultat = appel(client(transport))

        self.assertEqual(len(resultat['points']), 288)  # 12 mois × 24 h
        self.assertEqual(
            sorted({p['mois'] for p in resultat['points']}),
            list(range(1, 13)))
        premier = resultat['points'][0]
        self.assertEqual((premier['annee'], premier['mois'], premier['jour']),
                         (2020, 1, 15))
        self.assertIsNotNone(premier['gi_w_m2'])
        self.assertIsNotNone(premier['t2m_c'])
        # La provenance vient de la RÉPONSE, pas de la demande.
        self.assertEqual(resultat['meteo']['base_rayonnement'],
                         'PVGIS-SARAH3')
        self.assertEqual(resultat['meteo']['fenetre_annees'], '2020-2020')
        self.assertEqual(len(transport.appels), 1)

    def test_aucune_perte_n_est_passee_a_pvgis(self):
        """ACAL329 — la chaîne de pertes possède chaque poste : la requête ne
        porte ni ``loss`` ni modèle PV."""
        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud.json'))
        appel(client(transport))
        url = transport.appels[0]
        self.assertNotIn('loss=', url)
        self.assertIn('pvcalculation=0', url)

    def test_le_choix_de_base_est_explicite_dans_la_requete(self):
        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud.json'))
        appel(client(transport))
        self.assertIn(f'raddatabase={BASE_PAR_DEFAUT}', transport.appels[0])

    def test_base_inconnue_refusee_en_nommant_le_champ(self):
        transport = TransportEnregistre({})
        with self.assertRaises(EntreeInvalide) as capture:
            appel(client(transport), base='PVGIS-INEXISTANTE')
        self.assertEqual(capture.exception.champ, 'base')
        self.assertEqual(transport.appels, [])

    def test_fenetre_annees_a_lenvers_refusee(self):
        transport = TransportEnregistre({})
        with self.assertRaises(EntreeInvalide) as capture:
            appel(client(transport), annee_debut=2020, annee_fin=2018)
        self.assertEqual(capture.exception.champ, 'annee_fin')
        self.assertEqual(transport.appels, [])

    def test_le_cache_evite_le_second_appel(self):
        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud.json'))
        cli = client(transport)
        appel(cli)
        second = appel(cli, lat=33.50001)  # même plan arrondi
        self.assertEqual(len(transport.appels), 1)
        self.assertTrue(second['depuis_cache'])

    def test_un_plan_different_nest_pas_servi_par_le_cache(self):
        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud.json'))
        cli = client(transport)
        appel(cli)
        appel(cli, aspect_deg=-90.0)
        self.assertEqual(len(transport.appels), 2)


class AucunRepliSilencieuxTest(unittest.TestCase):
    """PVGIS indisponible ⇒ AUCUNE production, jamais une valeur de repli."""

    def test_reseau_injoignable_refuse_sans_production(self):
        transport = TransportEnregistre(erreur=OSError('réseau coupé'))
        with self.assertRaises(PvgisIndisponible) as capture:
            appel(client(transport))
        self.assertIn('aucune production', str(capture.exception).lower())

    def test_529_retente_un_nombre_borne_de_fois_puis_refuse(self):
        transport = TransportEnregistre({}, statut=529)
        with self.assertRaises(PvgisIndisponible) as capture:
            appel(client(transport, retentatives_529=2))
        self.assertEqual(len(transport.appels), 3)  # 1 essai + 2 retentatives
        self.assertIn('surchargé', str(capture.exception))

    def test_reponse_sans_serie_refusee(self):
        transport = TransportEnregistre({'outputs': {'hourly': []}})
        with self.assertRaises(PvgisIndisponible):
            appel(client(transport))

    def test_json_illisible_refuse(self):
        class Casse(TransportEnregistre):
            def __call__(self, url, timeout_s):
                self.appels.append(url)
                return 200, '<html>maintenance</html>'

        with self.assertRaises(PvgisIndisponible):
            appel(client(Casse()))


class CadenceEtCleTest(unittest.TestCase):
    """La cadence publiée par PVGIS (30 appels/s) est tenue."""

    def test_le_limiteur_attend_au_dela_de_trente_appels_par_seconde(self):
        temps = [0.0]
        attentes = []

        def horloge():
            return temps[0]

        def dormir(duree):
            attentes.append(duree)
            temps[0] += duree

        limiteur = _Limiteur(par_seconde=30, horloge=horloge, dormir=dormir)
        for _ in range(30):
            limiteur.attendre_son_tour()
        self.assertEqual(attentes, [])
        limiteur.attendre_son_tour()  # le 31ᵉ dans la même seconde
        self.assertEqual(len(attentes), 1)
        self.assertGreater(attentes[0], 0)

    def test_la_cle_de_cache_arrondit_le_plan(self):
        params = {'lat': 33.500004, 'lon': -7.600002, 'angle': 15.04,
                  'aspect': 0.02, 'raddatabase': 'PVGIS-SARAH3'}
        voisin = {'lat': 33.5, 'lon': -7.6, 'angle': 15.0, 'aspect': 0.0,
                  'raddatabase': 'PVGIS-SARAH3'}
        self.assertEqual(cle_de_cache('seriescalc', params),
                         cle_de_cache('seriescalc', voisin))


class AzimutTest(unittest.TestCase):
    """Azimut de FACE du document de toiture → ``aspect`` PVGIS."""

    def test_conversion_des_quatre_points_cardinaux(self):
        self.assertEqual(azimut_pvgis(180), 0.0)     # Sud
        self.assertEqual(azimut_pvgis(90), -90.0)    # Est
        self.assertEqual(azimut_pvgis(270), 90.0)    # Ouest
        self.assertEqual(abs(azimut_pvgis(0)), 180.0)  # Nord

    def test_azimut_absent_refuse_en_nommant_le_champ(self):
        with self.assertRaises(EntreeInvalide) as capture:
            azimut_pvgis(None)
        self.assertEqual(capture.exception.champ, 'facingAzimuthDeg')


# ---------------------------------------------------------------------------
# ACAL466 — lecteur Copernicus GLO-30 sur mini-tuile (DB-free, réseau injecté)
# ---------------------------------------------------------------------------

#: Neuf altitudes RÉELLES lues le 20/11/2026 sur la tuile
#: ``Copernicus_DSM_COG_10_N33_00_W008_00_DEM`` (Casablanca, lignes du nord au
#: sud, colonnes d'ouest en est ; coin nord-ouest = ligne 1535, colonne 1475).
ALTITUDES_CASABLANCA = (
    (42.09, 43.44, 47.82),
    (41.70, 42.40, 45.77),
    (41.09, 44.19, 46.73),
)


def _mini_geotiff(altitudes, *, predicteur=True):
    """GeoTIFF tuilé, Deflate, prédicteur 3 — MÊMES tags que la vraie tuile."""
    import struct
    import zlib
    import numpy as np

    tw = th = 16
    plan = np.zeros((th, tw), dtype='>f4')
    for i, ligne in enumerate(altitudes):
        plan[i, :len(ligne)] = ligne
    lignes = []
    for ligne in plan:
        octets = np.frombuffer(ligne.tobytes(), np.uint8).reshape(tw, 4)
        brut = np.ascontiguousarray(octets.T).reshape(-1)
        if predicteur:
            brut = np.concatenate(
                ([brut[0]], (np.diff(brut.astype(np.int16)) % 256)
                 .astype(np.uint8))).astype(np.uint8)
        lignes.append(brut.tobytes())
    tuile = zlib.compress(b''.join(lignes))

    echelle = struct.pack('<3d', 1 / 3600, 1 / 3600, 0.0)
    attache = struct.pack('<6d', 0.0, 0.0, 0.0, -8.0 + 1475 / 3600,
                          34.0 - 1535 / 3600, 0.0)
    cles = struct.pack('<16H', 1, 1, 0, 3, 1025, 0, 1, 2,
                       2048, 0, 1, 4326, 2054, 0, 1, 9102)
    n = 16
    debut_extra = 8 + 2 + 12 * n + 4
    o_echelle, o_attache = debut_extra, debut_extra + 24
    o_cles = o_attache + 48
    o_tuile = o_cles + len(cles)
    entrees = [
        (256, 3, 1, 3), (257, 3, 1, 3), (258, 3, 1, 32), (259, 3, 1, 8),
        (262, 3, 1, 1), (277, 3, 1, 1), (284, 3, 1, 1),
        (317, 3, 1, 3 if predicteur else 1), (322, 3, 1, tw), (323, 3, 1, th),
        (324, 4, 1, o_tuile), (325, 4, 1, len(tuile)), (339, 3, 1, 3),
        (33550, 12, 3, o_echelle), (33922, 12, 6, o_attache),
        (34735, 3, 8, o_cles),
    ]
    ifd = struct.pack('<H', n)
    for tag, typ, nb, val in entrees:
        if typ == 3 and nb == 1:
            champ = struct.pack('<HH', val, 0)
        else:
            champ = struct.pack('<I', val)
        ifd += struct.pack('<HHI', tag, typ, nb) + champ
    ifd += struct.pack('<I', 0)
    return (b'II*\x00' + struct.pack('<I', 8) + ifd + echelle + attache
            + cles + tuile)


def _lecteur_de(octets, appels=None):
    def lecteur(url, debut, fin):
        if appels is not None:
            appels.append(url)
        return octets[debut:fin + 1]
    return lecteur


class TerrainGlo30Test(unittest.TestCase):
    """ACAL466 — pente du relief d'un champ au sol (GLO-30), sans réseau."""

    @staticmethod
    def _sommets():
        # Centres des pixels (0,0), (2,0), (2,2), (0,2) de la mini-tuile.
        lon0, lat0, p = -8.0 + 1475 / 3600, 34.0 - 1535 / 3600, 1 / 3600
        return [[lon0, lat0], [lon0 + 2 * p, lat0],
                [lon0 + 2 * p, lat0 - 2 * p], [lon0, lat0 - 2 * p]]

    def test_lecteur_glo30_sur_mini_tuile(self):
        import math
        import numpy as np
        from apps.calepinage.services.terrain_glo30 import (
            ATTRIBUTION_MODELE, _lire_pente_terrain,
        )
        appels = []
        r = _lire_pente_terrain(
            'S1', self._sommets(), maintenant='2026-11-21T10:00:00Z',
            lecteur=_lecteur_de(_mini_geotiff(ALTITUDES_CASABLANCA), appels))
        self.assertEqual(r['motif'], '')
        # Les cinq points échantillonnés (4 sommets + centroïde) rendent les
        # altitudes RÉELLES — le prédicteur est bien inversé.
        z = sorted(p['altitude_m'] for p in r['points'])
        self.assertEqual(z, sorted([42.09, 47.82, 46.73, 41.09, 42.40]))
        self.assertTrue(all('N33_00_W008_00' in u for u in appels))
        # Oracle indépendant : moindres carrés numpy en mètres locaux.
        m_lat = 6378137 * math.radians(1 / 3600)
        m_lon = m_lat * math.cos(math.radians(33.57))
        pts = [(0, 0, 42.09), (2, 0, 47.82), (2, -2, 46.73), (0, -2, 41.09),
               (1, -1, 42.40)]
        A = np.array([[x * m_lon, y * m_lat, 1] for x, y, _ in pts])
        a, b, _ = np.linalg.lstsq(A, np.array([p[2] for p in pts]),
                                  rcond=None)[0]
        self.assertAlmostEqual(r['pente_deg'],
                               math.degrees(math.atan(math.hypot(a, b))),
                               delta=0.15)
        self.assertAlmostEqual(
            r['azimut_pente_deg'],
            math.degrees(math.atan2(-a, -b)) % 360, delta=1.0)
        self.assertIn('2026-11-21', r['attribution'])
        self.assertTrue(r['attribution'].startswith(
            ATTRIBUTION_MODELE.split('DATE')[0]))

    def test_predicteur_non_inverse_ne_rend_pas_les_vraies_altitudes(self):
        # Mutant : fichier écrit SANS prédicteur mais déclaré prédicteur 3 (=
        # l'inversion appliquée à des octets bruts) : les altitudes lues ne
        # sont PLUS les vraies — l'assertion du test précédent échouerait.
        from apps.calepinage.services.terrain_glo30 import _lire_pente_terrain
        octets = _mini_geotiff(ALTITUDES_CASABLANCA, predicteur=False)
        import struct
        i = octets.index(struct.pack('<HHI', 317, 3, 1))
        octets = octets[:i + 8] + b'\x03' + octets[i + 9:]
        r = _lire_pente_terrain('S1', self._sommets(),
                                lecteur=_lecteur_de(octets))
        lues = sorted(p['altitude_m'] for p in r['points'])
        self.assertNotEqual(lues, sorted([42.09, 47.82, 46.73, 41.09, 42.40]))

    def test_reseau_coupe_ou_trop_petit_jamais_une_altitude_de_repli(self):
        from apps.calepinage.services.terrain_glo30 import (
            TerrainIndisponible, _lire_pente_terrain,
        )

        def coupe(url, debut, fin):
            raise TerrainIndisponible("Le relief n'est pas joignable.")

        r = _lire_pente_terrain('S1', self._sommets(), lecteur=coupe)
        self.assertIsNone(r['pente_deg'])
        self.assertIsNone(r['azimut_pente_deg'])
        self.assertEqual(r['points'], [])
        self.assertIn('joignable', r['motif'])
        # Trois sommets dans le MÊME pixel : moins de trois pixels distincts.
        s = self._sommets()[0]
        petit = [s, [s[0] + 1e-6, s[1]], [s[0], s[1] - 1e-6]]
        r = _lire_pente_terrain(
            'S1', petit,
            lecteur=_lecteur_de(_mini_geotiff(ALTITUDES_CASABLANCA)))
        self.assertIsNone(r['pente_deg'])
        self.assertIn('trois pixels', r['motif'])

    def test_contour_en_metres_ancre_sur_l_epingle_du_site(self):
        """ACAL466 — le champ enregistre par l'ecran Terrain n'a que
        ``contourM`` : il est centre sur ``roof_layout.pin``."""
        import math
        from apps.calepinage.services.terrain_glo30 import (
            _contour_m_vers_lnglat, lire_pente_surface,
        )
        pin = {'lat': 33.5725, 'lng': -7.589167}
        carre = [[0, 0], [60, 0], [60, 60], [0, 60]]
        v = _contour_m_vers_lnglat(carre, pin)
        # Centre exact sur l'epingle ; cote est-ouest = 60 m, nord-sud = 60 m.
        self.assertAlmostEqual(sum(p[0] for p in v) / 4, pin['lng'], 9)
        self.assertAlmostEqual(sum(p[1] for p in v) / 4, pin['lat'], 9)
        m_lat = 6378137 * math.radians(1)
        self.assertAlmostEqual((v[2][1] - v[0][1]) * m_lat, 60, delta=0.01)
        self.assertAlmostEqual(
            (v[1][0] - v[0][0]) * m_lat * math.cos(math.radians(33.5725)),
            60, delta=0.01)
        self.assertIsNone(_contour_m_vers_lnglat(carre, None))
        self.assertIsNone(_contour_m_vers_lnglat([[0, 0], [1, 1]], pin))
        # Le service lit alors la mini-tuile (4 sommets + centroide sur
        # l'epingle : pixels de la tuile) et dit d'ou vient l'emplacement.
        octets = _mini_geotiff(ALTITUDES_CASABLANCA)
        centre = {'lat': 34.0 - 1536 / 3600, 'lng': -8.0 + 1476 / 3600}
        r = lire_pente_surface(
            'S1', {'contourM': [[0, 0], [60, 0], [60, 60], [0, 60]]}, centre,
            lecteur=_lecteur_de(octets))
        self.assertEqual(r['ancrage'], 'epingle_du_site')
        self.assertIsNotNone(r['pente_deg'], r['motif'])

    def test_sans_epingle_ni_sommets_le_motif_nomme_la_donnee_manquante(self):
        from apps.calepinage.services.terrain_glo30 import lire_pente_surface

        def jamais(url, debut, fin):
            raise AssertionError('aucune lecture reseau attendue')

        r = lire_pente_surface(
            'S1', {'contourM': [[0, 0], [60, 0], [60, 60]]}, None,
            lecteur=jamais)
        self.assertIsNone(r['pente_deg'])
        self.assertIn('pingle', r['motif'])
        self.assertNotIn('tracez son contour sur la carte.', r['motif'])
        r = lire_pente_surface('S1', {}, {'lat': 1, 'lng': 1}, lecteur=jamais)
        self.assertIsNone(r['pente_deg'])
        self.assertIn('dimensions', r['motif'])

    def test_nom_de_tuile_hemispheres(self):
        from apps.calepinage.services.terrain_glo30 import _nom_tuile
        self.assertTrue(_nom_tuile(-7.6, 33.57)[0].endswith(
            'Copernicus_DSM_COG_10_N33_00_W008_00_DEM/'
            'Copernicus_DSM_COG_10_N33_00_W008_00_DEM.tif'))
        self.assertIn('S01_00_E002_00', _nom_tuile(2.3, -0.5)[1])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
