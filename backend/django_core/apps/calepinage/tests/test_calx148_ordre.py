"""CALX148 — l'ordre de la chaîne est déclaré UNE fois, et il se tient.

Ce qui est gardé ici n'est pas un calcul, c'est une DÉCLARATION : l'ordre des
vingt-quatre étapes, la correspondance à double sens avec le catalogue des
postes saisis, les trois exclusivités d'ombrage, et les étapes que la v1
assume ne pas modéliser. Une étape orpheline d'un côté ou de l'autre est
exactement la faute que ce fichier existe pour voir.

Aucune base de données, aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_calx148_ordre
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import etapes
from apps.calepinage.services.chaine_pertes import (
    ALBEDO_FACE_AVANT, ETAPES_HORS_CATALOGUE, EXCLUSIVITES, LIBELLES,
    ORDRE_ETAPES, POSTE_PAR_ETAPE, POSTES_HORS_CHAINE, TOUJOURS_OMISES,
    appliquer_chaine)
from apps.calepinage.services.pertes import CATALOGUE_PAR_POSTE

SERIE = {
    'pas_minutes': 60,
    'points': [{'p_w': 1000.0}, {'p_w': 2000.0}],
}


def cascade(contexte):
    _, bloc = appliquer_chaine(SERIE, contexte)
    return {etape['etape']: etape for etape in bloc['etapes']}


class OrdreTest(unittest.TestCase):
    """L'ordre lui-même : sans doublon, et aux rangs que la doctrine fixe."""

    def test_vingt_quatre_etapes_sans_doublon(self):
        self.assertEqual(len(ORDRE_ETAPES), 24)
        self.assertEqual(len(set(ORDRE_ETAPES)), len(ORDRE_ETAPES),
                         'une étape est déclarée deux fois : son rang '
                         'deviendrait ambigu.')

    def test_la_fenetre_mppt_precede_le_rendement_puis_l_ecretage(self):
        rang = {nom: i for i, nom in enumerate(ORDRE_ETAPES)}
        self.assertLess(rang['mppt'], rang['onduleur'],
                        'PV*SOL place le clipping de la fenêtre MPP AVANT '
                        'la conversion DC/AC.')
        self.assertLess(rang['onduleur'], rang['ecretage'])

    def test_le_bifacial_entre_en_gain_juste_apres_l_auto_ombrage(self):
        rang = {nom: i for i, nom in enumerate(ORDRE_ETAPES)}
        self.assertEqual(rang['bifacial'], rang['inter_rangees'] + 1)

    def test_les_trois_lectures_d_ombrage_precedent_l_optique(self):
        rang = {nom: i for i, nom in enumerate(ORDRE_ETAPES)}
        for ombre in ('horizon', 'ombrage_proche', 'acces_module',
                      'inter_rangees'):
            self.assertLess(rang[ombre], rang['iam'], ombre)


class GardeCatalogueTest(unittest.TestCase):
    """À double sens : aucune étape orpheline, aucun poste orphelin."""

    def test_chaque_etape_est_mappee_ou_declaree_hors_catalogue(self):
        for nom in ORDRE_ETAPES:
            dans_le_catalogue = nom in POSTE_PAR_ETAPE
            hors_catalogue = nom in ETAPES_HORS_CATALOGUE
            self.assertTrue(
                dans_le_catalogue != hors_catalogue,
                f'étape « {nom} » : elle doit être SOIT reliée à un poste du '
                'catalogue, SOIT déclarée dans ETAPES_HORS_CATALOGUE avec sa '
                'raison — jamais les deux, jamais aucune.')

    def test_chaque_poste_du_catalogue_a_une_etape_ou_sa_raison(self):
        cibles = set(POSTE_PAR_ETAPE.values())
        for poste in CATALOGUE_PAR_POSTE:
            servi = poste in cibles
            hors_chaine = poste in POSTES_HORS_CHAINE
            self.assertTrue(
                servi != hors_chaine,
                f'poste « {poste} » : il doit être SOIT recouvert par une '
                'étape, SOIT déclaré dans POSTES_HORS_CHAINE avec sa raison.')

    def test_les_postes_vises_existent_vraiment_au_catalogue(self):
        for nom, poste in POSTE_PAR_ETAPE.items():
            self.assertIn(poste, CATALOGUE_PAR_POSTE,
                          f'étape « {nom} » vise un poste inconnu.')

    def test_aucun_poste_n_est_recouvert_par_deux_etapes(self):
        cibles = list(POSTE_PAR_ETAPE.values())
        self.assertEqual(len(cibles), len(set(cibles)),
                         'deux étapes qui visent le même poste saisi '
                         'écarteraient la même saisie deux fois.')

    def test_les_raisons_declarees_ne_sont_jamais_vides(self):
        for table in (ETAPES_HORS_CATALOGUE, POSTES_HORS_CHAINE,
                      TOUJOURS_OMISES):
            for nom, raison in table.items():
                self.assertTrue(raison.strip(), nom)

    def test_les_tables_ne_nomment_que_des_etapes_declarees(self):
        for table in (POSTE_PAR_ETAPE, ETAPES_HORS_CATALOGUE, EXCLUSIVITES,
                      TOUJOURS_OMISES, LIBELLES):
            for nom in table:
                self.assertIn(nom, ORDRE_ETAPES,
                              f'« {nom} » n’est pas une étape de la chaîne.')


class ExclusiviteTest(unittest.TestCase):
    """Trois lectures d'un même ombrage : une seule s'applique."""

    def test_un_document_avec_solar_access_omet_l_ombrage_proche(self):
        etape = cascade({'ombrage': {'solar_access': {'par_module': []}}})
        etape = etape['ombrage_proche']
        self.assertIn('module par module', etape['motif_omission'].lower())
        self.assertIsNone(etape['perte_pct'])

    def test_un_document_sans_solar_access_ne_l_omet_pas_pour_cette_raison(
            self):
        etape = cascade({})['ombrage_proche']
        self.assertIn('Étape non livrée', etape['motif_omission'],
                      'sans lecture par module, l’ombrage proche n’est pas '
                      'écarté par exclusivité : il attend son module.')

    def test_l_inter_rangees_n_est_ecarte_que_si_l_acces_le_declare(self):
        sans = cascade({'ombrage': {'solar_access': {'method': {}}}})
        self.assertIn('Étape non livrée',
                      sans['inter_rangees']['motif_omission'])
        avec = cascade(
            {'ombrage': {'solar_access': {'method': {'rangees': True}}}})
        self.assertIn('rangées', avec['inter_rangees']['motif_omission'])

    def test_l_horizon_est_ecarte_quand_pvgis_l_a_deja_retranche(self):
        etape = cascade(
            {'meteo': {'horizon': {'origine': 'dem_pvgis'}}})['horizon']
        self.assertIn('PVGIS', etape['motif_omission'])
        self.assertIn('modèle de terrain', etape['motif_omission'])
        autre = cascade(
            {'meteo': {'horizon': {'origine': 'profil_mesure'}}})['horizon']
        # CALX156 : un profil MESURÉ n'est pas le modèle de terrain de PVGIS.
        # L'exclusivité de l'ordonnanceur ne le vise donc pas — c'est l'étape
        # elle-même qui publie alors son propre motif.
        self.assertNotIn('modèle de terrain', autre['motif_omission'])


class ToujoursOmisesTest(unittest.TestCase):
    """Spectral, diodes et neige FIGURENT dans la cascade — à ``null``."""

    def setUp(self):
        self.par_nom = cascade({})

    def test_les_trois_figurent_dans_la_cascade(self):
        for nom in ('spectral', 'diodes', 'neige'):
            self.assertIn(nom, self.par_nom,
                          'une étape absente se lirait « oubliée ».')

    def test_elles_sont_omises_avec_leur_motif_et_perte_pct_null(self):
        for nom in ('spectral', 'diodes', 'neige'):
            etape = self.par_nom[nom]
            self.assertEqual(etape['motif_omission'], TOUJOURS_OMISES[nom])
            self.assertIsNone(etape['perte_pct'],
                              f'{nom} : 0 % se lirait « gratuite ».')
            self.assertIsNone(etape['perte_kwh'])
            self.assertIsNone(etape['kwh_apres'])

    def test_leur_motif_ne_forfaitise_jamais_le_chiffre_du_concurrent(self):
        self.assertIn('0,5 %', TOUJOURS_OMISES['diodes'])
        self.assertIn('aucun forfait', TOUJOURS_OMISES['diodes'])

    def test_un_module_livre_ne_les_reveille_pas_tout_seul(self):
        appelle = []

        def espion(serie, contexte):
            appelle.append('spectral')
            return serie, etapes.etape_appliquee('x', source='fiche',
                                                 entree='x')

        import types
        from unittest import mock
        faux = {'spectral': types.SimpleNamespace(appliquer=espion)}
        with mock.patch.object(etapes, 'charger',
                               side_effect=lambda p: faux.get(p)):
            _, bloc = appliquer_chaine(SERIE, {})
        self.assertEqual(appelle, [],
                         'une étape assumée non modélisée ne se calcule pas '
                         'parce qu’un module est apparu.')
        etape = next(e for e in bloc['etapes'] if e['etape'] == 'spectral')
        self.assertEqual(etape['motif_omission'], TOUJOURS_OMISES['spectral'])


class AlbedoTest(unittest.TestCase):
    """L'albédo de face avant reste ``null``, avec son motif."""

    def test_valeur_nulle_et_motif_qui_dit_pourquoi(self):
        self.assertIsNone(ALBEDO_FACE_AVANT['valeur'])
        self.assertIn('PVGIS', ALBEDO_FACE_AVANT['motif'])
        self.assertIn('non publiée', ALBEDO_FACE_AVANT['motif'])


if __name__ == '__main__':
    unittest.main()
