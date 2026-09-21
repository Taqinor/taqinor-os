"""CAL55 (moitié backend) — altitude et fuseau du site, SOURCÉS.

Le « Done » de la tâche : « altitude affichée avec "source PVGIS" ; PVGIS muet
→ champ vide et mention "non renseignée", jamais un nombre de repli » — et la
règle qui l'accompagne : le fuseau vient de la base IANA ou est SAISI, JAMAIS
dérivé de la longitude (un fuseau est une décision politique : le Maroc a vécu
à UTC+1 de 2018 au 19/09/2026, où une dérivation par la longitude — -7,6° ⇒
UTC+0 — se serait trompée d'une heure pleine sur toute la course du soleil ;
il est repassé à UTC+0 le 20/09/2026, décret n° 2.26.530, sans qu'aucune
longitude ne bouge).

Tests PURS : la réponse PVGIS est un dictionnaire ENREGISTRÉ, aucun appel
réseau — jamais.
"""
from __future__ import annotations

import datetime
import inspect
import unittest

from apps.calepinage.services import site
from apps.calepinage.services.parametres import ReglageInvalide

#: Un extrait FIDÈLE de la réponse PVGIS : c'est bien ``inputs.location`` qui
#: porte ``elevation`` (mètres).
REPONSE_PVGIS = {
    'inputs': {
        'location': {'latitude': 33.57, 'longitude': -7.59,
                     'elevation': 56.0},
        'meteo_data': {'radiation_db': 'PVGIS-SARAH3'},
    },
    'outputs': {},
}


class AltitudeTest(unittest.TestCase):

    def test_altitude_lue_dans_la_reponse_pvgis_avec_sa_source(self):
        resultat = site.altitude_du_site({}, charge_pvgis=REPONSE_PVGIS)
        self.assertEqual(resultat['altitude_m'], 56.0)
        self.assertEqual(resultat['source'], site.SOURCE_PVGIS)
        self.assertEqual(resultat['mention'], '')

    def test_pvgis_muet_ne_produit_aucun_nombre_de_repli(self):
        for charge in (None, {}, {'inputs': {}},
                       {'inputs': {'location': {}}},
                       {'inputs': {'location': {'elevation': 'quelque part'}}}):
            resultat = site.altitude_du_site({}, charge_pvgis=charge)
            self.assertIsNone(resultat['altitude_m'], charge)
            self.assertIsNone(resultat['source'], charge)
            self.assertIn('non renseignée', resultat['mention'])

    def test_valeur_saisie_l_emporte_sur_pvgis(self):
        section = {'altitude_m': 120.0,
                   'source_altitude': 'Relevé GPS du 12/09/2026'}
        resultat = site.altitude_du_site(section, charge_pvgis=REPONSE_PVGIS)
        self.assertEqual(resultat['altitude_m'], 120.0)
        self.assertEqual(resultat['source'], 'Relevé GPS du 12/09/2026')

    def test_altitude_saisie_sans_source_est_refusee_a_l_ecriture(self):
        with self.assertRaises(ReglageInvalide) as capture:
            site.normaliser_section_imagerie({'altitude_m': 120.0})
        self.assertEqual(capture.exception.champ, 'source_altitude')

    def test_altitude_pvgis_isolee(self):
        self.assertEqual(site.altitude_pvgis(REPONSE_PVGIS), 56.0)
        self.assertIsNone(site.altitude_pvgis({'inputs': {'location': None}}))


class FuseauTest(unittest.TestCase):

    def test_fuseau_saisi_est_servi_avec_sa_source(self):
        resultat = site.fuseau_du_site({'fuseau': 'Africa/Casablanca'})
        self.assertEqual(resultat['fuseau'], 'Africa/Casablanca')
        self.assertIn('IANA', resultat['source'])
        self.assertEqual(resultat['mention'], '')

    def test_sans_fuseau_aucun_fuseau_n_est_devine(self):
        resultat = site.fuseau_du_site({})
        self.assertIsNone(resultat['fuseau'])
        self.assertIn('longitude', resultat['mention'])

    def test_le_fuseau_ne_peut_pas_etre_derive_de_la_longitude(self):
        # Garantie STRUCTURELLE : la fonction ne prend AUCUNE coordonnée, donc
        # aucune dérivation par la longitude n'est possible par distraction.
        parametres = inspect.signature(site.fuseau_du_site).parameters
        self.assertEqual(list(parametres), ['section'])
        source = inspect.getsource(site.fuseau_du_site)
        for interdit in ('lon', 'longitude'):
            self.assertNotIn(f'{interdit} /', source)
            self.assertNotIn(f'{interdit}/', source)

    def test_fuseau_inconnu_refuse_a_l_ecriture(self):
        with self.assertRaises(ReglageInvalide) as capture:
            site.normaliser_section_imagerie({'fuseau': 'Africa/Casablancaa'})
        self.assertEqual(capture.exception.champ, 'fuseau')

    def test_decalage_utc_vient_de_la_base_de_fuseaux(self):
        # En janvier 2026 le Maroc est à UTC+1 — c'est la base IANA qui le
        # dit, et c'est précisément ce qu'une formule sur la longitude
        # (-7,6° ⇒ UTC+0) manquerait. La date est CHOISIE avant le 20/09/2026,
        # jour où le décret n° 2.26.530 a ramené le pays à UTC+0 : l'attendu
        # porte sur ce que dit la base à CETTE date, jamais sur un « +1 »
        # supposé permanent.
        janvier = datetime.datetime(2026, 1, 15, 12, 0)
        decalage = site.decalage_utc_minutes('Africa/Casablanca', janvier)
        if decalage is not None:        # base tzdata absente : on n'invente pas
            self.assertEqual(decalage, 60)

    def test_fuseau_inconnu_ne_produit_aucun_decalage(self):
        self.assertIsNone(site.decalage_utc_minutes(
            'Nowhere/Noplace', datetime.datetime(2026, 1, 15, 12, 0)))
        self.assertIsNone(site.decalage_utc_minutes(None, None))
