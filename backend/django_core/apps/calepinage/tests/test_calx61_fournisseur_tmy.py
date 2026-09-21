"""CALX61 — le fournisseur TMY est branché, et il ne ment jamais sur sa source.

CE QUI EST PROUVÉ ICI
---------------------
1. les deux températures rendues sont les extrêmes de la série ``T2m``
   REÇUE de PVGIS — pas une constante, pas une moyenne, pas un arrondi ;
2. la base de rayonnement et la fenêtre d'années voyagent jusqu'à
   ``TemperaturesSite.detail``, avec ``source='tmy'`` et une mention VIDE ;
3. PVGIS injoignable ⇒ ``source is None`` et la mention « non sourcées »,
   c'est-à-dire le rendu OCTET POUR OCTET d'avant ce branchement (comparé au
   rendu sans aucun fournisseur, dans le même test) ;
4. une température SAISIE prime toujours : le fournisseur n'est même pas
   appelé ;
5. enregistrer le fournisseur n'appelle PAS PVGIS — l'appel est paresseux,
   sinon ``ready()`` ouvrirait une connexion au démarrage de Django.

AUCUN RÉSEAU
------------
La réponse PVGIS est celle, RÉELLE, enregistrée le 20/09/2026 dans
``tests/fixtures_pvgis/tmy_casablanca.json`` (déjà utilisée par
``test_pvgis_tmy`` et ``test_prod2_modele_thermique``) : donnée publique du
JRC pour le point 33,5 / −7,6, jamais un chiffre de client. Elle est rejouée
par le transport injecté de ``ClientPvgis`` ; les cas de panne passent par un
``mock`` de ``ClientPvgis.tmy``. Aucun appel sortant, dans aucun test.

Les valeurs attendues sont RELUES de la fixture (min/max, base, fenêtre) et
jamais recopiées en dur : un chiffre épinglé à la main ici serait exactement
le genre de constante que CAL123 combat.

Aucune base de données : ces essais tournent hors du gate migrations.

Run :
    python manage.py test apps.calepinage.tests.test_calx61_fournisseur_tmy -v2
"""
from __future__ import annotations

import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    MENTION_NON_SOURCEE,
    SOURCE_SAISIE,
    SOURCE_TMY,
    enregistrer_fournisseur_temperatures,
    fournisseur_temperatures,
    temperatures_site,
)
from apps.calepinage.services.pvgis_serie import ClientPvgis, PvgisIndisponible
from apps.calepinage.services.temperatures_tmy import temperatures_tmy
from apps.calepinage.tests.test_pvgis_serie import (
    TransportEnregistre, charger, client as client_a_cache_prive,
)
from core.electrique.types import TEMP_CHAUD_DEFAUT_C, TEMP_FROID_DEFAUT_C

#: Le point de la fixture (Casablanca) — celui pour lequel la réponse PVGIS
#: a été enregistrée, donc le seul que ce fichier a le droit d'employer.
LAT, LON = 33.5, -7.6
PIN = {'lat': LAT, 'lng': LON}


def _sans_donnee(lat, lon):
    """Un fournisseur qui n'a rien pour ce point — le cas d'avant CALX61."""
    return None


class _Socle(SimpleTestCase):
    """Le rejoueur de la réponse enregistrée, monté une fois."""

    def setUp(self):
        self.charge = charger('tmy_casablanca.json')
        self.meteo = self.charge['inputs']['meteo_data']
        self.t2m = [ligne['T2m']
                    for ligne in self.charge['outputs']['tmy_hourly']
                    if isinstance(ligne.get('T2m'), (int, float))]

    def fenetre_attendue(self):
        return f"{self.meteo['year_min']}-{self.meteo['year_max']}"

    def rejoueur(self):
        """Un ``ClientPvgis`` qui rejoue la fixture, au cache PRIVÉ.

        Surtout pas ``self.client`` : ``SimpleTestCase`` pose déjà là le
        client HTTP de Django, et le nom serait écrasé en silence.
        """
        return client_a_cache_prive(TransportEnregistre(self.charge))

    def fournisseur(self, rejoueur=None):
        """Le fournisseur tel qu'il sera appelé : ``fournisseur(lat, lon)``."""
        pvgis = rejoueur if rejoueur is not None else self.rejoueur()

        def _fournisseur(lat, lon):
            return temperatures_tmy(lat, lon, client=pvgis)

        return _fournisseur


class ExtremesDeLAnneeTypeTest(_Socle):
    """Les températures rendues SONT celles de la série reçue."""

    def test_les_extremes_sont_ceux_de_la_serie_t2m(self):
        rendu = temperatures_tmy(LAT, LON, client=self.rejoueur())

        self.assertEqual(rendu['temperature_min_c'], min(self.t2m))
        self.assertEqual(rendu['temperature_max_c'], max(self.t2m))

    def test_la_base_et_la_fenetre_sont_celles_que_pvgis_renvoie(self):
        rendu = temperatures_tmy(LAT, LON, client=self.rejoueur())

        self.assertEqual(rendu['base'], self.meteo['radiation_db'])
        self.assertEqual(rendu['fenetre_annees'], self.fenetre_attendue())

    def test_la_forme_rendue_est_celle_qu_attend_le_consommateur(self):
        """``_depuis_fournisseur`` lit EXACTEMENT ces quatre clés."""
        rendu = temperatures_tmy(LAT, LON, client=self.rejoueur())

        self.assertEqual(sorted(rendu),
                         ['base', 'fenetre_annees', 'temperature_max_c',
                          'temperature_min_c'])


class SourceTmyPublieeTest(_Socle):
    """Ce que la chaîne électrique publie, fournisseur branché."""

    def test_sans_saisie_la_source_est_tmy_et_la_mention_est_vide(self):
        temperatures = temperatures_site(pin=PIN, saisie=None,
                                         fournisseur=self.fournisseur())

        self.assertEqual(temperatures.source, SOURCE_TMY)
        self.assertEqual(temperatures.mention, '')
        self.assertTrue(temperatures.sourcees)
        self.assertEqual(temperatures.froid_c, min(self.t2m))
        self.assertEqual(temperatures.chaud_c, max(self.t2m))

    def test_la_base_et_la_fenetre_voyagent_jusqu_au_detail(self):
        temperatures = temperatures_site(pin=PIN, saisie=None,
                                         fournisseur=self.fournisseur())

        self.assertIn(self.meteo['radiation_db'], temperatures.detail)
        self.assertIn(self.fenetre_attendue(), temperatures.detail)

    def test_la_saisie_prime_toujours_sur_le_tmy(self):
        appels = []

        def espion(lat, lon):
            appels.append((lat, lon))
            return temperatures_tmy(lat, lon, client=self.rejoueur())

        temperatures = temperatures_site(
            pin=PIN,
            saisie={'temperature_min_c': -2.0, 'temperature_max_c': 65.0},
            fournisseur=espion)

        self.assertEqual(temperatures.source, SOURCE_SAISIE)
        self.assertEqual((temperatures.froid_c, temperatures.chaud_c),
                         (-2.0, 65.0))
        self.assertEqual(appels, [],
                         "Le fournisseur TMY a été interrogé alors qu'une "
                         'température était saisie : une valeur relevée bat '
                         'un modèle, et elle ne coûte aucun appel réseau.')


class PvgisIndisponibleTest(_Socle):
    """Une panne météo ne change RIEN au comportement d'aujourd'hui."""

    def test_injoignable_rend_le_meme_resultat_que_sans_fournisseur(self):
        hors_ligne = client_a_cache_prive(
            TransportEnregistre(erreur=urllib.error.URLError('hors ligne')))

        avec = temperatures_site(pin=PIN,
                                 fournisseur=self.fournisseur(hors_ligne))
        # « Comme aujourd'hui » = comme un fournisseur qui n'a rien pour ce
        # point. On ne passe PAS ``fournisseur=None`` : depuis CALX61, cela
        # veut dire « prends celui qui est enregistré », donc un vrai appel
        # PVGIS — un test ne touche jamais le réseau.
        sans = temperatures_site(pin=PIN, fournisseur=_sans_donnee)

        self.assertIsNone(avec.source)
        self.assertFalse(avec.sourcees)
        self.assertEqual(avec.mention, MENTION_NON_SOURCEE)
        self.assertEqual(avec.froid_c, TEMP_FROID_DEFAUT_C)
        self.assertEqual(avec.chaud_c, TEMP_CHAUD_DEFAUT_C)
        # La preuve du « comportement d'aujourd'hui » : les deux rendus sont
        # le MÊME document, clé pour clé.
        self.assertEqual(avec.en_dict(), sans.en_dict())

    def test_le_fournisseur_rend_none_et_ne_leve_jamais(self):
        with mock.patch.object(
                ClientPvgis, 'tmy',
                side_effect=PvgisIndisponible('PVGIS est injoignable')):
            self.assertIsNone(temperatures_tmy(LAT, LON))

    def test_une_annee_type_sans_temperature_ne_fabrique_aucun_chiffre(self):
        muette = {'temperature_min_c': None, 'temperature_max_c': None,
                  'base': 'PVGIS-SARAH3', 'fenetre_annees': '2005-2023'}
        with mock.patch.object(ClientPvgis, 'tmy', return_value=muette):
            self.assertIsNone(temperatures_tmy(LAT, LON))


class BranchementParesseuxTest(SimpleTestCase):
    """``ready()`` enregistre un appelable — il n'appelle pas PVGIS."""

    def test_le_fournisseur_enregistre_est_celui_du_module(self):
        self.assertIs(
            fournisseur_temperatures(), temperatures_tmy,
            "apps.py::ready() n'a pas branché le fournisseur TMY : les "
            'bornes de tension retomberaient sur la mention « non '
            'sourcées » alors que le point GPS est connu (CALX61).')

    def test_enregistrer_le_fournisseur_n_appelle_pas_pvgis(self):
        with mock.patch.object(ClientPvgis, 'tmy') as appel_tmy:
            precedent = enregistrer_fournisseur_temperatures(temperatures_tmy)
            try:
                # Ni l'enregistrement, ni une résolution qui n'a pas besoin du
                # TMY (saisie présente, ou aucune épingle) ne touchent PVGIS.
                temperatures_site(saisie={'temperature_min_c': -5.0,
                                          'temperature_max_c': 70.0})
                temperatures_site(pin=None)
            finally:
                enregistrer_fournisseur_temperatures(precedent)

        appel_tmy.assert_not_called()
