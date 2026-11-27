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

    def test_etapes_sans_doublon(self):
        # 25 + « optimiseur » (ACAL723) = 26 ; le total bouge avec les étapes
        # neuves des autres tâches : le nom du test ne le porte plus.
        self.assertEqual(len(ORDRE_ETAPES), 26)
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


def _avec_acces(methode):
    """ACAL137 — un contexte dont le pan porte un accès solaire par module
    DANS SA GÉOMÉTRIE (``zones[].geometry.solarAccess``), où l'atelier
    l'écrit."""
    layout = {'zones': [{'label': 'PAN-1', 'geometry': {
        'solarAccess': {'values': [0.9, 0.8], 'method': methode}}}]}
    return {'ombrage': {'layout': layout}}


class ExclusiviteTest(unittest.TestCase):
    """Trois lectures d'un même ombrage : une seule s'applique."""

    def test_un_document_avec_solar_access_omet_l_ombrage_proche(self):
        etape = cascade(_avec_acces({'horizon': False, 'rangees': False}))
        etape = etape['ombrage_proche']
        self.assertIn('module par module', etape['motif_omission'].lower())
        self.assertIsNone(etape['perte_pct'])

    def test_un_document_sans_solar_access_ne_l_omet_pas_pour_cette_raison(
            self):
        etape = cascade({})['ombrage_proche']
        # CALX157 : sans lecture par module, l'exclusivité ne s'applique pas
        # — c'est l'étape elle-même qui dit alors ce qui lui manque.
        self.assertNotIn('module par module',
                         etape['motif_omission'].lower())
        self.assertTrue(etape['motif_omission'].strip())

    def test_l_inter_rangees_n_est_ecarte_que_si_l_acces_le_declare(self):
        # Sans la déclaration « rangees », l'EXCLUSIVITÉ ne joue pas :
        # l'étape suit son propre sort (depuis CALX159, elle omet faute de
        # géométrie de rangées dans ce contexte d'essai).
        sans = cascade(_avec_acces({'horizon': False}))
        self.assertNotIn('rangées entre elles',
                         sans['inter_rangees']['motif_omission'])
        avec = cascade(_avec_acces({'horizon': False, 'rangees': True}))
        self.assertIn('rangées entre elles',
                      avec['inter_rangees']['motif_omission'])

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
        # ACAL722 : « diodes » est calculée (sous-chaînes) ; sans données elle
        # est écartée par une EXCLUSIVITÉ, motif d'exclusivité.
        for nom, table in (('spectral', TOUJOURS_OMISES),
                           ('diodes', {'diodes': EXCLUSIVITES['diodes'][1]})):
            etape = self.par_nom[nom]
            self.assertEqual(etape['motif_omission'], table[nom])
            self.assertIsNone(etape['perte_pct'],
                              f'{nom} : 0 % se lirait « gratuite ».')
            self.assertIsNone(etape['perte_kwh'])
            self.assertIsNone(etape['kwh_apres'])

    def test_la_neige_sort_de_la_table_mais_reste_omise_sans_saisie(self):
        # ACAL463 — la neige est CALCULÉE quand douze valeurs sourcées sont
        # saisies ; sans saisie elle reste omise en nommant la clé, à null.
        self.assertNotIn('neige', TOUJOURS_OMISES)
        etape = self.par_nom['neige']
        self.assertIn('simulation.neige_mensuelle_pct',
                      etape['motif_omission'])
        self.assertIsNone(etape['perte_pct'])
        self.assertIsNone(etape['perte_kwh'])
        self.assertIsNone(etape['kwh_apres'])

    def test_leur_motif_ne_forfaitise_jamais_le_chiffre_du_concurrent(self):
        self.assertNotIn('diodes', TOUJOURS_OMISES)
        self.assertNotIn('0,5 %', EXCLUSIVITES['diodes'][1])  # ACAL1655
        self.assertIn('aucun forfait', EXCLUSIVITES['diodes'][1])

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


class PostesDePertesTest(unittest.TestCase):
    """ACAL695 — la table étape → poste couvre EXACTEMENT ``ORDRE_ETAPES``."""

    def test_chaque_etape_a_un_poste_et_aucun_nom_inconnu(self):
        from apps.calepinage.services.regroupement_pertes import (
            POSTE_DE_L_ETAPE)

        self.assertEqual(set(POSTE_DE_L_ETAPE), set(ORDRE_ETAPES))

    def test_thermique_est_la_chaleur(self):
        # Mutant « thermique dans autres » : échec ici.
        from apps.calepinage.services.regroupement_pertes import (
            POSTE_DE_L_ETAPE)

        self.assertEqual(POSTE_DE_L_ETAPE['thermique'], 'chaleur')

    def test_les_postes_de_l_echantillon_se_recalculent(self):
        import json
        import pathlib

        chemin = (pathlib.Path(__file__).resolve().parents[1]
                  / 'contract_samples' / 'calepinage_pertes_cascade.json')
        cascade = json.loads(chemin.read_text(encoding='utf-8'))[
            'exemple']['cascade']
        bloc = cascade['postes_lisibles']
        depart = cascade['etapes'][0]['kwh_avant']
        self.assertEqual(bloc['depart_kwh'], depart)
        self.assertEqual(len(bloc['postes']), 5)
        somme = 0.0
        for poste in bloc['postes']:
            if poste['statut'] == 'non_compte':
                self.assertIsNone(poste['perte_kwh'])
                self.assertIsNone(poste['perte_pct'])
                continue
            # Formule écrite ICI : 100 × perte_kwh ÷ depart_kwh.
            self.assertAlmostEqual(poste['perte_pct'],
                                   100.0 * poste['perte_kwh'] / depart,
                                   places=2)
            somme += poste['perte_pct']
        self.assertLessEqual(abs((100.0 - somme) - bloc['arrivee_pct']), 0.1)
        autres = [p for p in bloc['postes'] if p['poste'] == 'autres'][0]
        self.assertEqual(autres['statut'], 'partiel')
        self.assertIn('spectral', [e['etape'] for e in autres['etapes']])
        for omise in autres['etapes']:
            self.assertTrue(omise['motif_omission'])

    def test_cascade_vide_motivee(self):
        from apps.calepinage.services.regroupement_pertes import regrouper

        bloc = regrouper({'etapes': [], 'total_pct': None})
        self.assertEqual(bloc['postes'], [])
        self.assertTrue(bloc['motif_absence'])


class ModulesHorsChaineTest(unittest.TestCase):
    """ACAL1602 — la cascade ne part que des modules RACCORDÉS.

    Le pan d'essai de CALX5 (12 × 710 W, un onduleur) est simulé deux fois :
    tous les modules câblés, puis les 4 derniers laissés « en réserve »
    (``chaine`` nulle dans la table d'affectation, ``electrique.chainage
    .reste``). Calcul à la main : sans écrêtage (10 kW AC pour 8,52 kWc) ni
    ombrage, l'énergie est proportionnelle au kWc entrant dans la chaîne,
    donc P50 raccordé = P50 des 12 × 8 ÷ 12 et kWc = 8 × 0,71 = 5,68 ;
    les 4 modules restent servis dans ``hors_chaine`` avec leur énergie
    possible (≈ P50 des 12 × 4 ÷ 12).
    """

    @classmethod
    def setUpClass(cls):
        from unittest import mock

        from apps.calepinage.services import agregation_electrique

        from .test_calx5_simulation import _simuler

        cls.tous = _simuler()['blocs']
        original = agregation_electrique.affectation_du_calepinage
        cls.tables = []

        def quatre_en_reserve(conception, entree_electrique=None):
            rendu = original(conception, entree_electrique)
            table = [dict(ligne) for ligne in rendu['affectation']]
            for ligne in table[-4:]:
                ligne.update(chaine=None, mppt=None, onduleur=None)
            cls.tables.append(table)
            return dict(rendu, affectation=tuple(table))

        with mock.patch.object(agregation_electrique,
                               'affectation_du_calepinage',
                               side_effect=quatre_en_reserve):
            cls.reserve = _simuler()['blocs']

    def test_le_p50_ne_compte_que_les_modules_raccordes(self):
        self.assertEqual(len(self.tables[0]), 12)
        tous = self.tous['production']['total']
        reserve = self.reserve['production']['total']
        self.assertAlmostEqual(reserve['p50_kwh'],
                               tous['p50_kwh'] * 8 / 12,
                               delta=tous['p50_kwh'] * 0.005)
        self.assertAlmostEqual(reserve['kwc'], 5.68, places=2)

    def test_la_cascade_part_des_seuls_raccordes(self):
        depart_tous = self.tous['cascade']['etapes'][0]['kwh_avant']
        depart = self.reserve['cascade']['etapes'][0]['kwh_avant']
        self.assertAlmostEqual(depart, depart_tous * 8 / 12,
                               delta=depart_tous * 0.005)
        ecretage = [etape for etape in self.reserve['cascade']['etapes']
                    if etape['etape'] == 'ecretage'][0]
        ecretage_tous = [etape for etape in self.tous['cascade']['etapes']
                         if etape['etape'] == 'ecretage'][0]
        if ecretage_tous.get('kwh_avant') is not None:
            self.assertAlmostEqual(ecretage['kwh_avant'],
                                   ecretage_tous['kwh_avant'] * 8 / 12,
                                   delta=ecretage_tous['kwh_avant'] * 0.005)

    def test_hors_chaine_reste_servi_et_l_avertissement_le_dit(self):
        hors = self.reserve['production']['hors_chaine']
        self.assertEqual(hors['modules'], 4)
        self.assertAlmostEqual(
            hors['p50_kwh'], self.tous['production']['total']['p50_kwh'] * 4 / 12,
            delta=self.tous['production']['total']['p50_kwh'] * 0.01)
        attendu = ('4 panneaux ne sont raccordés à aucun onduleur : ils ne '
                   'sont pas comptés')
        self.assertTrue(any(texte.startswith(attendu) for texte in
                            self.reserve['avertissements'][:2]),
                        self.reserve['avertissements'][:3])
        self.assertFalse(any('raccordé' in texte for texte in
                             self.tous.get('avertissements') or ()))


if __name__ == '__main__':
    unittest.main()
