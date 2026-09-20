"""CAL135 — le client ``seriescalc`` : pertes explicites, zéro appel réseau.

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

from apps.calepinage.services.pertes_politique import politique_de_pertes
from apps.calepinage.services.pvgis_serie import (
    BASE_PAR_DEFAUT, ClientPvgis, EntreeInvalide, PvgisIndisponible,
    _Cache, _Limiteur, azimut_pvgis, cle_de_cache,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'

#: Postes d'ESSAI — la mécanique, pas des pertes réelles (CAL139 les possède).
POSTES_ESSAI = [
    {'poste': 'shading', 'pct': 3.5, 'source': 'mesure'},
    {'poste': 'soiling', 'pct': 2.25, 'source': 'societe'},
    {'poste': 'inverter', 'pct': 1.5, 'source': 'fiche'},
]


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
                  politique=politique_de_pertes(POSTES_ESSAI),
                  annee_debut=2020, annee_fin=2020)
    params.update(extra)
    return cli.serie_horaire(**params)


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
        self.assertEqual(resultat['base'], 'PVGIS-SARAH3')
        self.assertEqual(resultat['fenetre_annees'], '2020-2020')
        self.assertEqual(len(transport.appels), 1)

    def test_la_chaine_de_requete_porte_exactement_la_somme_publiee(self):
        """CAL238 — ce que publie le résultat est ce qui est parti dans l'URL."""
        transport = TransportEnregistre(
            charger('seriescalc_casablanca_sud.json'))
        resultat = appel(client(transport))

        url = transport.appels[0]
        # La somme des postes d'essai, calculée ici — jamais un pourcentage
        # écrit en dur (le balayage de surface de CAL238 l'interdit, et il a
        # raison : une perte en dur dans un test est une perte en dur).
        somme = sum(poste['pct'] for poste in POSTES_ESSAI)
        self.assertEqual(resultat['loss_passee_pct'], somme)
        self.assertIn('loss=' + str(somme), url)
        self.assertEqual([p['poste'] for p in resultat['pertes']],
                         ['shading', 'soiling', 'inverter'])
        # …et aucune perte par défaut ne s'est glissée dans la requête.
        self.assertEqual(url.count('loss='), 1)

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

    def test_sans_politique_de_pertes_aucun_appel(self):
        transport = TransportEnregistre({})
        with self.assertRaises(EntreeInvalide) as capture:
            appel(client(transport), politique=None)
        self.assertEqual(capture.exception.champ, 'pertes')
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


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
