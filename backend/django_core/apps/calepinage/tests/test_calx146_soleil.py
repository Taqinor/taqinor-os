# -*- coding: utf-8 -*-
"""CALX146 — la position solaire horaire du noyau, confrontée à du RÉEL.

CE QUI EST PROUVÉ ICI
---------------------
1. **Contre PVGIS** : sur les 288 points de la réponse PVGIS réelle
   ``fixtures_pvgis/seriescalc_casablanca_sud.json``, l'élévation calculée
   s'écarte de la colonne ``H_sun`` DE LA FIXTURE de moins de 1,5° partout où
   ``H_sun > 5``. La référence est donc la réponse du JRC elle-même, jamais un
   chiffre recopié à la main. **1,5° est un SEUIL DE TEST** choisi pour
   absorber l'arrondi horaire de PVGIS (écart mesuré le 21/09/2026 : 0,44°) —
   aucune valeur métier n'en dépend.
2. **Contre `pvlib`** (CALX198, l'oracle indépendant) : le même calcul, comparé
   à ``pvlib.solarposition.get_solarposition`` (implémentation NREL SPA), sur
   les mêmes instants. Seuils de test 0,05° en élévation et 0,1° en azimut
   (écarts mesurés le 21/09/2026 : 0,009° et 0,017°).
3. **Contre l'ancienne fonction** : au 21 décembre à 10 h SOLAIRE,
   ``position_solaire`` rend la même élévation que
   ``politique_pas.position_solaire_solstice`` à 0,2° près (seuil de test).
   Le même essai ÉPINGLE la divergence connue sur l'AZIMUT : les deux
   fonctions le comptent en sens INVERSE, et rien ne doit les mélanger.
4. **Le signe de l'azimut**, contre les fixtures EST et OUEST : négatif le
   matin (convention PVGIS, ``aspect`` −90 = est), et c'est bien le plan dont
   l'angle d'incidence est le plus faible qui reçoit le plus de ``G(i)`` dans
   la réponse PVGIS — un signe inversé casserait cette concordance.

AUCUN RÉSEAU, AUCUNE BASE
-------------------------
Les trois fixtures sont les réponses PVGIS v5_3 RÉELLES enregistrées le
20/09/2026 pour le point 33,5 / −7,6 (donnée publique du JRC, jamais un
chiffre de client). Aucun appel sortant ; ``SimpleTestCase`` : aucune base de
données, donc hors du gate migrations.

Run :
    python manage.py test apps.calepinage.tests.test_calx146_soleil -v2
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from django.test import SimpleTestCase

from core.calepinage.exceptions import EntreeInvalide
from core.calepinage.politique_pas import (
    ELEVATION_PLANCHER_DEG,
    position_solaire_solstice,
)
from core.calepinage.soleil import PositionSolaire, position_solaire

FIXTURES = Path(__file__).resolve().parent / 'fixtures_pvgis'

#: Seuils de TEST (aucune valeur métier n'en dépend) — cf. docstring.
TOLERANCE_PVGIS_DEG = 1.5
TOLERANCE_PVLIB_ELEVATION_DEG = 0.05
TOLERANCE_PVLIB_AZIMUT_DEG = 0.1
TOLERANCE_SOLSTICE_DEG = 0.2

#: Sous cette hauteur, PVGIS et nous ne parlons plus de la même chose (arrondi
#: horaire + réfraction) : la tâche borne la comparaison à ``H_sun > 5``.
HAUTEUR_COMPARABLE_DEG = 5.0

#: Écart d'incidence au-delà duquel les deux plans (est / ouest) reçoivent
#: vraiment des choses différentes — sous cet écart, le diffus domine.
ECART_INCIDENCE_SIGNIFICATIF_DEG = 20.0


def charger(nom):
    """La réponse PVGIS enregistrée, telle quelle."""
    return json.loads((FIXTURES / nom).read_text(encoding='utf-8'))


def instant(ligne):
    """``'20200115:1009'`` -> ``(annee, mois, jour, heure_utc décimale)``.

    Les minutes comptent : PVGIS-SARAH3 horodate à ``HH:09``, et arrondir à
    l'heure ronde coûterait jusqu'à 2,3° d'élévation.
    """
    horodatage = ligne['time']
    return (int(horodatage[0:4]), int(horodatage[4:6]), int(horodatage[6:8]),
            int(horodatage[9:11]) + int(horodatage[11:13]) / 60.0)


class SocleFixture(SimpleTestCase):
    """Charge les trois fixtures une fois pour toutes les classes filles."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sud = charger('seriescalc_casablanca_sud.json')
        cls.est = charger('seriescalc_casablanca_est.json')
        cls.ouest = charger('seriescalc_casablanca_ouest.json')
        lieu = cls.sud['inputs']['location']
        cls.latitude = float(lieu['latitude'])
        cls.longitude = float(lieu['longitude'])

    def position(self, ligne):
        annee, mois, jour, heure = instant(ligne)
        return position_solaire(self.latitude, self.longitude,
                                annee=annee, mois=mois, jour=jour,
                                heure_utc=heure)


class ElevationContrePvgis(SocleFixture):
    """La colonne ``H_sun`` de PVGIS est la référence — elle est CITÉE."""

    def test_ecart_sous_le_seuil_sur_toute_la_serie(self):
        pires = []
        compares = 0
        for ligne in self.sud['outputs']['hourly']:
            hauteur_pvgis = float(ligne['H_sun'])
            if hauteur_pvgis <= HAUTEUR_COMPARABLE_DEG:
                continue
            compares += 1
            ecart = abs(self.position(ligne).elevation_deg - hauteur_pvgis)
            if ecart >= TOLERANCE_PVGIS_DEG:
                pires.append((ligne['time'], round(ecart, 3)))
        self.assertEqual(
            pires, [],
            "élévation trop éloignée de la colonne H_sun de PVGIS : %r" % (pires,))
        # La série doit VRAIMENT avoir été parcourue (une fixture tronquée
        # rendrait ce test vert sans rien prouver).
        self.assertEqual(len(self.sud['outputs']['hourly']), 288)
        self.assertGreater(compares, 100)

    def test_la_nuit_est_rendue_negative_et_sous_le_plancher(self):
        nuits = [ligne for ligne in self.sud['outputs']['hourly']
                 if float(ligne['H_sun']) == 0.0
                 and ligne['time'].endswith('0009')]
        self.assertTrue(nuits, "la fixture n'a aucune heure de minuit")
        for ligne in nuits:
            position = self.position(ligne)
            self.assertLess(position.elevation_deg, 0.0, ligne['time'])
            self.assertTrue(position.sous_le_plancher, ligne['time'])
            self.assertAlmostEqual(
                position.elevation_deg + position.zenith_deg, 90.0, places=9)

    def test_le_plancher_est_celui_de_la_politique_de_pas(self):
        """Aucun plancher local : c'est ``politique_pas.py:58`` qui décide."""
        haute = [ligne for ligne in self.sud['outputs']['hourly']
                 if float(ligne['H_sun']) > 20.0][0]
        position = self.position(haute)
        self.assertFalse(position.sous_le_plancher)
        self.assertGreater(position.elevation_deg, ELEVATION_PLANCHER_DEG)


class OracleIndependantPvlib(SocleFixture):
    """CALX198 — la dépendance adoptée sert d'oracle, pas de moteur."""

    def test_accord_avec_pvlib_solarposition(self):
        try:
            import pandas
            from pvlib import solarposition
        except ImportError as exc:                     # pragma: no cover
            self.skipTest("pvlib/pandas absent de cet environnement : %s" % exc)

        lignes = self.sud['outputs']['hourly']
        horodatages = []
        for ligne in lignes:
            annee, mois, jour, heure = instant(ligne)
            horodatages.append(pandas.Timestamp(
                annee, mois, jour, int(heure), int(round((heure % 1) * 60)),
                tz='UTC'))
        reference = solarposition.get_solarposition(
            pandas.DatetimeIndex(horodatages), self.latitude, self.longitude)

        ecart_elevation = 0.0
        ecart_azimut = 0.0
        compares = 0
        for rang, ligne in enumerate(lignes):
            elevation_pvlib = float(reference['elevation'].iloc[rang])
            if elevation_pvlib <= HAUTEUR_COMPARABLE_DEG:
                continue
            compares += 1
            # pvlib compte l'azimut DEPUIS LE NORD, sens horaire.
            azimut_pvlib = float(reference['azimuth'].iloc[rang]) - 180.0
            if azimut_pvlib <= -180.0:
                azimut_pvlib += 360.0
            position = self.position(ligne)
            ecart_elevation = max(
                ecart_elevation, abs(position.elevation_deg - elevation_pvlib))
            ecart_azimut = max(
                ecart_azimut,
                abs(position.azimut_depuis_sud_deg - azimut_pvlib))
        self.assertGreater(compares, 100)
        self.assertLess(ecart_elevation, TOLERANCE_PVLIB_ELEVATION_DEG,
                        "écart d'élévation contre pvlib : %.4f°" % ecart_elevation)
        self.assertLess(ecart_azimut, TOLERANCE_PVLIB_AZIMUT_DEG,
                        "écart d'azimut contre pvlib : %.4f°" % ecart_azimut)


class AccordAvecLAncienneFonction(SimpleTestCase):
    """Le solstice : le nouveau moteur ne déplace pas ce qui est publié."""

    LATITUDES = (33.5, 30.4, 35.8, 21.0)
    LONGITUDE = -7.6
    HEURE_SOLAIRE = 10.0

    def _au_solstice_a_dix_heures_solaires(self, latitude):
        """L'heure UTC dont l'heure solaire VRAIE vaut 10 h, ce 21 décembre.

        Une seule itération suffit : le décalage (longitude + équation du
        temps) ne bouge pas de façon mesurable dans la journée.
        """
        depart = position_solaire(latitude, self.LONGITUDE, annee=2020,
                                  mois=12, jour=21, heure_utc=self.HEURE_SOLAIRE)
        decalage = depart.heure_solaire_vraie_h - self.HEURE_SOLAIRE
        position = position_solaire(latitude, self.LONGITUDE, annee=2020,
                                    mois=12, jour=21,
                                    heure_utc=self.HEURE_SOLAIRE - decalage)
        self.assertAlmostEqual(position.heure_solaire_vraie_h,
                               self.HEURE_SOLAIRE, places=3)
        return position

    def test_meme_elevation_que_position_solaire_solstice(self):
        for latitude in self.LATITUDES:
            with self.subTest(latitude=latitude):
                position = self._au_solstice_a_dix_heures_solaires(latitude)
                ancienne, _ = position_solaire_solstice(latitude,
                                                        self.HEURE_SOLAIRE)
                self.assertLess(abs(position.elevation_deg - ancienne),
                                TOLERANCE_SOLSTICE_DEG,
                                "élévation %r vs %r" % (position.elevation_deg,
                                                        ancienne))

    def test_les_deux_conventions_d_azimut_sont_opposees(self):
        """Divergence CONNUE, épinglée pour qu'on ne les mélange jamais."""
        for latitude in self.LATITUDES:
            with self.subTest(latitude=latitude):
                position = self._au_solstice_a_dix_heures_solaires(latitude)
                _, ancien_azimut = position_solaire_solstice(latitude,
                                                             self.HEURE_SOLAIRE)
                # Matin : la nouvelle convention (PVGIS) dit EST = négatif ;
                # l'ancienne rend la valeur opposée, au signe près.
                self.assertLess(position.azimut_depuis_sud_deg, 0.0)
                self.assertGreater(ancien_azimut, 0.0)
                self.assertLess(
                    abs(position.azimut_depuis_sud_deg + ancien_azimut),
                    TOLERANCE_SOLSTICE_DEG)


class SigneDeLAzimut(SocleFixture):
    """Convention PVGIS : 0 = sud, −90 = est, +90 = ouest."""

    def test_negatif_le_matin_positif_l_apres_midi(self):
        incoherents = []
        for ligne in self.sud['outputs']['hourly']:
            if float(ligne['H_sun']) <= HAUTEUR_COMPARABLE_DEG:
                continue
            position = self.position(ligne)
            matin = position.heure_solaire_vraie_h < 12.0
            if matin != (position.azimut_depuis_sud_deg < 0.0):
                incoherents.append((ligne['time'],
                                    position.heure_solaire_vraie_h,
                                    position.azimut_depuis_sud_deg))
        self.assertEqual(incoherents, [],
                         "azimut du mauvais signe : %r" % (incoherents,))

    def test_le_plan_le_mieux_expose_est_celui_que_pvgis_eclaire(self):
        """Le signe est confronté au ``G(i)`` RÉEL des fixtures est et ouest.

        Les deux fixtures ne diffèrent que par ``aspect`` (−90 et +90) ; à
        inclinaison et instant égaux, le plan dont l'angle d'incidence est le
        plus faible doit recevoir au moins autant d'irradiance. Les heures où
        PVGIS rend la MÊME valeur des deux côtés (ciel couvert : plus aucune
        composante directe) ne portent aucune information de direction et
        sont ignorées.
        """
        inclinaison = float(
            self.est['inputs']['mounting_system']['fixed']['slope']['value'])
        azimut_est = float(
            self.est['inputs']['mounting_system']['fixed']['azimuth']['value'])
        azimut_ouest = float(
            self.ouest['inputs']['mounting_system']['fixed']['azimuth']['value'])
        self.assertEqual((azimut_est, azimut_ouest), (-90.0, 90.0))

        par_est = {ligne['time']: ligne for ligne in self.est['outputs']['hourly']}
        par_ouest = {ligne['time']: ligne
                     for ligne in self.ouest['outputs']['hourly']}

        contre_exemples = []
        compares = 0
        for ligne in self.sud['outputs']['hourly']:
            if float(ligne['H_sun']) <= HAUTEUR_COMPARABLE_DEG:
                continue
            position = self.position(ligne)
            incidence_est = position.angle_incidence_deg(inclinaison, azimut_est)
            incidence_ouest = position.angle_incidence_deg(inclinaison,
                                                           azimut_ouest)
            ecart = abs(incidence_est - incidence_ouest)
            if ecart < ECART_INCIDENCE_SIGNIFICATIF_DEG:
                continue
            irradiance_est = float(par_est[ligne['time']]['G(i)'])
            irradiance_ouest = float(par_ouest[ligne['time']]['G(i)'])
            if irradiance_est == irradiance_ouest:
                continue
            compares += 1
            mieux_oriente_est = incidence_est < incidence_ouest
            if mieux_oriente_est != (irradiance_est > irradiance_ouest):
                contre_exemples.append(
                    (ligne['time'], round(incidence_est, 1),
                     round(incidence_ouest, 1), irradiance_est, irradiance_ouest))
        self.assertGreater(compares, 50)
        self.assertEqual(contre_exemples, [],
                         "le signe de l'azimut contredit le G(i) de PVGIS : %r"
                         % (contre_exemples,))


class AngleDIncidence(SimpleTestCase):
    """Deux identités exactes — aucun chiffre attendu n'est inventé."""

    def position(self):
        return position_solaire(33.5, -7.6, annee=2020, mois=6, jour=15,
                                heure_utc=11.5)

    def test_plan_horizontal_rend_l_angle_zenithal(self):
        position = self.position()
        self.assertAlmostEqual(position.angle_incidence_deg(0.0, 0.0),
                               position.zenith_deg, places=9)

    def test_plan_pointe_sur_le_soleil_rend_zero(self):
        position = self.position()
        self.assertAlmostEqual(
            position.angle_incidence_deg(position.zenith_deg,
                                         position.azimut_depuis_sud_deg),
            0.0, places=6)

    def test_le_soleil_derriere_le_plan_depasse_quatre_vingt_dix_degres(self):
        """Une information rendue TELLE QUELLE, jamais tronquée à 90°."""
        position = self.position()
        dos_au_soleil = position.angle_incidence_deg(
            90.0, position.azimut_depuis_sud_deg + 180.0)
        self.assertGreater(dos_au_soleil, 90.0)

    def test_le_resultat_est_immuable(self):
        position = self.position()
        self.assertIsInstance(position, PositionSolaire)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            position.elevation_deg = 0.0


class EntreesRefusees(SimpleTestCase):
    """Le noyau REFUSE en nommant le champ — il ne replie jamais en silence."""

    BASE = dict(annee=2020, mois=6, jour=15, heure_utc=12.0)

    def test_latitude_hors_domaine(self):
        with self.assertRaises(EntreeInvalide) as capture:
            position_solaire(91.0, -7.6, **self.BASE)
        self.assertIn('latitude', str(capture.exception))

    def test_longitude_hors_domaine(self):
        with self.assertRaises(EntreeInvalide) as capture:
            position_solaire(33.5, 181.0, **self.BASE)
        self.assertIn('longitude', str(capture.exception))

    def test_mois_hors_domaine(self):
        parametres = dict(self.BASE, mois=13)
        with self.assertRaises(EntreeInvalide) as capture:
            position_solaire(33.5, -7.6, **parametres)
        self.assertIn('mois', str(capture.exception))

    def test_heure_hors_domaine(self):
        parametres = dict(self.BASE, heure_utc=24.0)
        with self.assertRaises(EntreeInvalide) as capture:
            position_solaire(33.5, -7.6, **parametres)
        self.assertIn('heure_utc', str(capture.exception))
