"""CAL123 — les températures de dimensionnement portent LEUR SOURCE.

Les trois chemins sont testés, et le troisième est le plus important : sans
source, le verdict de tension est RENDU (refuser serait pire) mais il porte la
mention « températures de référence, non sourcées ». C'est cette mention qui
interdit de présenter −5 °C comme une donnée mesurée du site.

Aucune base de données : le service prend une épingle et une saisie, pas un
enregistrement — donc ce test tourne hors du gate migrations.

Run :
    python manage.py test apps.calepinage.tests.test_elec_temperatures_site -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    MENTION_NON_SOURCEE,
    SOURCE_SAISIE,
    SOURCE_TMY,
    TemperaturesInvalides,
    enregistrer_fournisseur_temperatures,
    fournisseur_temperatures,
    temperatures_site,
)
from core.electrique.types import TEMP_CHAUD_DEFAUT_C, TEMP_FROID_DEFAUT_C

PIN = {'lat': 33.5731, 'lng': -7.5898}


def _fournisseur_tmy(lat, lon):
    return {'temperature_min_c': 1.4, 'temperature_max_c': 62.0,
            'base': 'SARAH3', 'fenetre_annees': '2005-2023'}


class TemperaturesSourceesTest(SimpleTestCase):
    """Les trois chemins : saisie, TMY, aucune source."""

    def test_saisie_prime_et_est_nommee(self):
        temperatures = temperatures_site(
            pin=PIN,
            saisie={'temperature_min_c': -2.0, 'temperature_max_c': 65.0},
            fournisseur=_fournisseur_tmy)

        self.assertEqual(temperatures.source, SOURCE_SAISIE)
        self.assertEqual(temperatures.froid_c, -2.0)
        self.assertEqual(temperatures.chaud_c, 65.0)
        self.assertTrue(temperatures.sourcees)
        self.assertEqual(temperatures.mention, '')

    def test_tmy_quand_rien_n_est_saisi(self):
        temperatures = temperatures_site(pin=PIN, saisie=None,
                                         fournisseur=_fournisseur_tmy)

        self.assertEqual(temperatures.source, SOURCE_TMY)
        self.assertEqual(temperatures.froid_c, 1.4)
        self.assertEqual(temperatures.chaud_c, 62.0)
        self.assertEqual(temperatures.mention, '')
        # La BASE météo employée est citée : un chiffre de production ou de
        # tension sans sa base n'est pas défendable (CAL136).
        self.assertIn('SARAH3', temperatures.detail)

    def test_sans_source_le_verdict_est_rendu_mais_il_le_dit(self):
        temperatures = temperatures_site(pin=None, saisie=None,
                                         fournisseur=None)

        self.assertIsNone(temperatures.source)
        self.assertFalse(temperatures.sourcees)
        self.assertEqual(temperatures.mention, MENTION_NON_SOURCEE)
        # Les valeurs de repli sont celles du NOYAU, jamais un troisième jeu
        # de constantes écrit dans l'app.
        self.assertEqual(temperatures.froid_c, TEMP_FROID_DEFAUT_C)
        self.assertEqual(temperatures.chaud_c, TEMP_CHAUD_DEFAUT_C)

    def test_fournisseur_muet_ou_en_panne_ne_casse_pas_le_calcul(self):
        def muet(lat, lon):
            raise RuntimeError('PVGIS injoignable')

        temperatures = temperatures_site(pin=PIN, fournisseur=muet)

        self.assertIsNone(temperatures.source)
        self.assertEqual(temperatures.mention, MENTION_NON_SOURCEE)

    def test_sans_epingle_le_fournisseur_n_est_pas_appele(self):
        appels = []

        def espion(lat, lon):
            appels.append((lat, lon))
            return _fournisseur_tmy(lat, lon)

        temperatures = temperatures_site(pin=None, fournisseur=espion)

        self.assertEqual(appels, [])
        self.assertIsNone(temperatures.source)

    def test_en_dict_porte_toujours_les_cinq_cles(self):
        rendu = temperatures_site(pin=None).en_dict()

        self.assertEqual(
            sorted(rendu), ['chaud_c', 'detail', 'froid_c', 'mention',
                            'source'])


class SaisieRefuseeTest(SimpleTestCase):
    """Une saisie à moitié faite est refusée EN NOMMANT le champ."""

    def test_saisie_partielle_refusee(self):
        with self.assertRaises(TemperaturesInvalides) as capture:
            temperatures_site(saisie={'temperature_min_c': -2.0})

        self.assertEqual(capture.exception.champ, 'temperature_max_c')
        self.assertIn('Température maximale', str(capture.exception))

    def test_min_au_dessus_du_max_refuse(self):
        with self.assertRaises(TemperaturesInvalides) as capture:
            temperatures_site(saisie={'temperature_min_c': 70.0,
                                      'temperature_max_c': -5.0})

        self.assertEqual(capture.exception.champ, 'temperature_min_c')
        self.assertIn('inversés', str(capture.exception))


class FournisseurEnregistreTest(SimpleTestCase):
    """Le fournisseur TMY (CAL136) se branche, se débranche et se restaure."""

    def test_enregistrement_et_restauration(self):
        precedent = enregistrer_fournisseur_temperatures(_fournisseur_tmy)
        try:
            self.assertIs(fournisseur_temperatures(), _fournisseur_tmy)
            temperatures = temperatures_site(pin=PIN)
            self.assertEqual(temperatures.source, SOURCE_TMY)
        finally:
            enregistrer_fournisseur_temperatures(precedent)

        self.assertIs(fournisseur_temperatures(), precedent)
