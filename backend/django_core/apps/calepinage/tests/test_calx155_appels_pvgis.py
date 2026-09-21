"""CALX155 — une requête météo par PLAN, jamais par module.

`services/production.py` demande aujourd'hui une série PAR PAN et met à
l'échelle côté client ; la simulation module par module (CALX182) en
demanderait une par MODULE. La mémoire installée par l'ordonnanceur est keyée
exactement comme le cache de `services/pvgis_serie.py` — c'est ce que ce
fichier garde, en COMPTANT les appels réels.

Aucun réseau : le fournisseur est un compteur.

Run :
    python manage.py test apps.calepinage.tests.test_calx155_appels_pvgis
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.chaine_pertes import (
    CLE_FOURNISSEUR_METEO, CLE_METEO_PARTAGEE, ChaineInvalide,
    appliquer_chaine)

SERIE = {'pas_minutes': 60, 'points': [{'p_w': 1000.0}]}
SITE = {'lat': 33.5731, 'lon': -7.5898}


class Compteur:
    """Le fournisseur injecté par CALX5 — ici, un simple compteur d'appels."""

    def __init__(self):
        self.appels = []

    def __call__(self, plan):
        self.appels.append(plan.get('cle'))
        return {'pas_minutes': 60, 'points': [{'p_w': 1.0}],
                'pan': plan.get('cle')}


def contexte_de(plans, fournisseur):
    return {'site': dict(SITE), 'plans': list(plans),
            CLE_FOURNISSEUR_METEO: fournisseur}


class UneRequeteParPlanTest(unittest.TestCase):
    """Deux pans de mêmes angles = un seul appel."""

    def test_trois_pans_dont_deux_identiques_font_deux_appels(self):
        plans = [
            {'cle': 'A', 'inclinaison_deg': 20.0, 'azimut_pvgis_deg': 0.0},
            {'cle': 'B', 'inclinaison_deg': 20.0, 'azimut_pvgis_deg': 0.0},
            {'cle': 'C', 'inclinaison_deg': 35.0, 'azimut_pvgis_deg': -90.0},
        ]
        fournisseur = Compteur()
        contexte = contexte_de(plans, fournisseur)
        appliquer_chaine(SERIE, contexte)

        acces = contexte[CLE_METEO_PARTAGEE]
        for plan in plans:
            acces(plan)
        self.assertEqual(len(fournisseur.appels), 2,
                         'les pans A et B partagent inclinaison et azimut : '
                         'ils partagent la requête.')
        self.assertEqual(contexte['meteo']['appels_pvgis'], 2)

    def test_cinq_cents_modules_d_un_seul_plan_font_un_appel(self):
        plans = [{'cle': 'A', 'inclinaison_deg': 20.0,
                  'azimut_pvgis_deg': 0.0}]
        fournisseur = Compteur()
        contexte = contexte_de(plans, fournisseur)
        appliquer_chaine(SERIE, contexte)

        acces = contexte[CLE_METEO_PARTAGEE]
        for _ in range(500):
            acces('A')
        self.assertEqual(len(fournisseur.appels), 1,
                         'la météo se demande par PLAN : cinq cents modules '
                         'du même pan ne font pas cinq cents requêtes.')
        self.assertEqual(contexte['meteo']['appels_pvgis'], 1)

    def test_la_serie_rendue_est_bien_celle_du_pan(self):
        plans = [{'cle': 'A', 'inclinaison_deg': 20.0,
                  'azimut_pvgis_deg': 0.0}]
        contexte = contexte_de(plans, Compteur())
        appliquer_chaine(SERIE, contexte)
        self.assertEqual(contexte[CLE_METEO_PARTAGEE]('A')['pan'], 'A')


class CleDeCachePartageeTest(unittest.TestCase):
    """La clé est celle du cache existant : arrondie, pas exacte."""

    def test_deux_pans_au_dixieme_de_degre_pres_partagent_l_appel(self):
        plans = [
            {'cle': 'A', 'inclinaison_deg': 20.01, 'azimut_pvgis_deg': 0.02},
            {'cle': 'B', 'inclinaison_deg': 20.04, 'azimut_pvgis_deg': 0.01},
        ]
        fournisseur = Compteur()
        contexte = contexte_de(plans, fournisseur)
        appliquer_chaine(SERIE, contexte)
        for plan in plans:
            contexte[CLE_METEO_PARTAGEE](plan)
        self.assertEqual(len(fournisseur.appels), 1)

    def test_un_dixieme_de_degre_d_ecart_fait_bien_deux_appels(self):
        plans = [
            {'cle': 'A', 'inclinaison_deg': 20.0, 'azimut_pvgis_deg': 0.0},
            {'cle': 'B', 'inclinaison_deg': 20.4, 'azimut_pvgis_deg': 0.0},
        ]
        fournisseur = Compteur()
        contexte = contexte_de(plans, fournisseur)
        appliquer_chaine(SERIE, contexte)
        for plan in plans:
            contexte[CLE_METEO_PARTAGEE](plan)
        self.assertEqual(len(fournisseur.appels), 2)


class RefusTest(unittest.TestCase):
    """Un pan sans angle ne se partage pas en silence : il est NOMMÉ."""

    def test_un_pan_sans_inclinaison_est_refuse_en_nommant_le_champ(self):
        plans = [{'cle': 'A', 'azimut_pvgis_deg': 0.0}]
        contexte = contexte_de(plans, Compteur())
        appliquer_chaine(SERIE, contexte)
        with self.assertRaises(ChaineInvalide) as capture:
            contexte[CLE_METEO_PARTAGEE]('A')
        self.assertIn('inclinaison_deg', str(capture.exception))

    def test_un_site_sans_coordonnees_est_refuse_en_les_nommant(self):
        contexte = {'site': {}, 'plans': [], CLE_FOURNISSEUR_METEO: Compteur()}
        appliquer_chaine(SERIE, contexte)
        with self.assertRaises(ChaineInvalide) as capture:
            contexte[CLE_METEO_PARTAGEE](
                {'cle': 'A', 'inclinaison_deg': 20.0,
                 'azimut_pvgis_deg': 0.0})
        self.assertIn('site.lat', str(capture.exception))

    def test_un_pan_inconnu_du_document_est_refuse(self):
        contexte = contexte_de([], Compteur())
        appliquer_chaine(SERIE, contexte)
        with self.assertRaises(ChaineInvalide) as capture:
            contexte[CLE_METEO_PARTAGEE]('fantome')
        self.assertIn('fantome', str(capture.exception))


class SansFournisseurTest(unittest.TestCase):
    """Sans fournisseur, la chaîne tourne — elle n'invente pas de météo."""

    def test_aucun_acces_n_est_installe(self):
        contexte = {'site': dict(SITE)}
        _, cascade = appliquer_chaine(SERIE, contexte)
        self.assertNotIn(CLE_METEO_PARTAGEE, contexte)
        self.assertTrue(cascade['etapes'])

    def test_un_acces_deja_pose_n_est_pas_remplace(self):
        temoin = []

        def deja_la(pan):
            temoin.append(pan)
            return SERIE

        contexte = {'site': dict(SITE), CLE_METEO_PARTAGEE: deja_la,
                    CLE_FOURNISSEUR_METEO: Compteur()}
        appliquer_chaine(SERIE, contexte)
        contexte[CLE_METEO_PARTAGEE]('A')
        self.assertEqual(temoin, ['A'])


if __name__ == '__main__':
    unittest.main()
