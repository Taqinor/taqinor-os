# -*- coding: utf-8 -*-
"""CALX183 — la production agrégée par chaîne, MPPT et onduleur.

CE QUI EST PROUVÉ ICI
---------------------
1. **Propriété** : la somme des ``par_chaine[].p50_kwh`` égale
   ``total.p50_kwh`` à 0,1 kWh près quand tous les modules sont câblés — et,
   quand certains ne le sont pas, elle l'égale une fois ``hors_chaine``
   ajouté (un module posé mais câblé à rien compte dans le total, jamais
   dans une chaîne).
2. **Le nombre de lignes égale le nombre de chaînes de l'AFFECTATION** — la
   partition publiée est celle qui a été dimensionnée, jamais une partition
   recalculée ici.
3. **Une affectation MANUELLE enregistrée
   (``entree_electrique['affectation_manuelle']``) est celle qui SERT.**
4. **Affectation non calculable ⇒ bloc OMIS avec le motif de
   ``services/chaines.py``** — jamais une agrégation sur rien.
5. **Les deux pertes de la maille chaîne sont LUES dans la cascade** ; sans
   cascade, elles valent ``None`` avec leur motif — jamais ``0 %``.

Aucune base de données, aucun réseau : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_calx183_par_chaine
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.calepinage.services import simulation_modules
from apps.calepinage.services.agregation_electrique import (
    ETAPE_ECRETAGE, ETAPE_MISMATCH, affectation_du_calepinage,
    agregation_production,
)
from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import temperatures_site

#: La méthode d'accès solaire que le document déclare (CALX158).
METHODE = {'horizon': False, 'rangees': False,
           'nom': 'shadingEngine roofPro11'}

#: Deux heures ensoleillées : le minimum pour qu'une énergie se lise.
SERIE = {
    'pas_minutes': 60,
    'colonne_energie': 'p_w',
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
         'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
         'gi_w_m2': 1000.0, 'p_w': 4000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12,
         'gb_i_w_m2': 400.0, 'gd_i_w_m2': 100.0, 'gr_i_w_m2': 0.0,
         'gi_w_m2': 500.0, 'p_w': 2000.0},
    ],
}

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-A', 'geometry': {'count': 12, 'azimuthDeg': 180.0,
                                    'tiltDeg': 15.0}}]}


def _serie(_plan):
    return SERIE


def _plan(cle, modules):
    return {'cle': cle, 'modules': modules,
            'inclinaison_deg': 15.0, 'azimut_pvgis_deg': 0.0}


def _zone(cle, acces):
    return {'label': cle, 'geometry': {
        'solarAccess': {'values': list(acces), 'method': dict(METHODE)}}}


def _contexte(pans, affectation=None):
    contexte = {
        'plans': [_plan(cle, len(acces)) for cle, acces in pans],
        'site': {'lat': 33.5, 'lon': -7.6},
        'meteo': {'service': 'seriescalc',
                  'base_rayonnement': 'PVGIS-SARAH3'},
        'ombrage': {
            'solar_access': {'method': dict(METHODE)},
            'layout': {'zones': [_zone(cle, acces) for cle, acces in pans]},
        },
        'obtenir_serie': _serie,
    }
    if affectation is not None:
        contexte['affectation'] = affectation
    return contexte


def _affectation(cle, nombre, *, par_chaine=5):
    """Une table d'affectation de la MÊME forme que celle du module."""
    lignes = []
    for rang in range(1, nombre + 1):
        numero = (rang - 1) // par_chaine + 1
        lignes.append({'module': '%s#%d' % (cle, rang), 'pan': cle,
                       'chaine': numero, 'onduleur': 1,
                       'mppt': (numero - 1) % 2 + 1,
                       'source': 'automatique'})
    return lignes


def _production(nombre, affectation):
    return simulation_modules.production_module_par_module(
        _contexte([('PAN-A', [1.0] * nombre)], affectation=affectation))


def _conception():
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}))


class ProprietesTest(SimpleTestCase):
    """Les propriétés que la tâche exige, chiffre par chiffre."""

    def test_la_somme_des_chaines_est_le_total(self):
        table = _affectation('PAN-A', 10)
        bloc = agregation_production(_production(10, table), table)

        somme = sum(ligne['p50_kwh'] for ligne in bloc['par_chaine'])
        self.assertAlmostEqual(somme, bloc['total']['p50_kwh'], delta=0.1)

    def test_le_nombre_de_lignes_egale_le_nombre_de_chaines(self):
        table = _affectation('PAN-A', 10)
        bloc = agregation_production(_production(10, table), table)

        chaines = {ligne['chaine'] for ligne in table}
        self.assertEqual(len(bloc['par_chaine']), len(chaines))
        self.assertEqual([ligne['chaine'] for ligne in bloc['par_chaine']],
                         sorted(chaines))

    def test_un_module_non_cable_compte_hors_chaine_et_le_total_tient(self):
        table = _affectation('PAN-A', 10)
        # Le dernier module est POSÉ mais câblé à rien (réserve d'appoint).
        table[-1] = dict(table[-1], chaine=None, mppt=None, onduleur=None)
        bloc = agregation_production(_production(10, table), table)

        self.assertEqual(bloc['hors_chaine']['modules'], 1)
        somme = (sum(ligne['p50_kwh'] for ligne in bloc['par_chaine'])
                 + bloc['hors_chaine']['p50_kwh'])
        self.assertAlmostEqual(somme, bloc['total']['p50_kwh'], delta=0.1)

    def test_le_total_est_celui_de_la_simulation_repris_tel_quel(self):
        table = _affectation('PAN-A', 10)
        production = _production(10, table)

        self.assertEqual(agregation_production(production, table)['total'],
                         production['total'])


class MaillesTest(SimpleTestCase):
    """Chaîne, MPPT et onduleur — trois mailles, un seul croisement."""

    def test_les_trois_mailles_sont_publiees(self):
        table = _affectation('PAN-A', 10)
        bloc = agregation_production(_production(10, table), table)

        self.assertEqual(len(bloc['par_chaine']), 2)
        self.assertEqual(len(bloc['par_mppt']), 2)
        self.assertEqual(len(bloc['par_onduleur']), 1)
        self.assertEqual(bloc['par_onduleur'][0]['modules'], 10)

    def test_chaque_ligne_porte_les_cles_de_la_tache(self):
        table = _affectation('PAN-A', 10)
        bloc = agregation_production(_production(10, table), table)

        for ligne in bloc['par_chaine']:
            for cle in ('chaine', 'pan', 'onduleur', 'mppt', 'modules',
                        'p50_kwh', 'perte_mismatch_pct',
                        'perte_ecretage_pct', 'acces_min'):
                self.assertIn(cle, ligne, cle)

    def test_l_acces_minimal_est_celui_des_modules_de_la_chaine(self):
        table = _affectation('PAN-A', 6, par_chaine=3)
        production = simulation_modules.production_module_par_module(
            _contexte([('PAN-A', [1.0, 1.0, 0.4, 1.0, 1.0, 1.0])],
                      affectation=table))
        bloc = agregation_production(production, table)

        self.assertAlmostEqual(bloc['par_chaine'][0]['acces_min'], 40.0,
                               places=3)
        self.assertAlmostEqual(bloc['par_chaine'][1]['acces_min'], 100.0,
                               places=3)


class AffectationManuelleTest(SimpleTestCase):
    """L'affectation ENREGISTRÉE est celle qui sert."""

    def test_l_affectation_manuelle_enregistree_sert(self):
        conception = _conception()
        auto = affectation_du_calepinage(conception)['affectation']
        premier = auto[0]['module']
        # La même conception, avec UNE ligne imposée sur une autre chaîne.
        impose = [{'module': premier, 'chaine': 9, 'mppt': 2, 'onduleur': 1}]
        manuelle = affectation_du_calepinage(
            conception, {'affectation_manuelle': impose})['affectation']

        posee = [rang for rang in manuelle if rang['module'] == premier][0]
        self.assertEqual(posee['chaine'], 9)
        self.assertEqual(posee['source'], 'affectation manuelle')

    def test_l_agregation_suit_la_table_manuelle(self):
        table = _affectation('PAN-A', 10)
        manuelle = [
            dict(ligne, chaine=7, mppt=2, source='affectation manuelle')
            if ligne['module'] == 'PAN-A#1' else ligne
            for ligne in table]
        bloc = agregation_production(_production(10, table), manuelle)

        self.assertIn(7, [ligne['chaine'] for ligne in bloc['par_chaine']])
        sept = [ligne for ligne in bloc['par_chaine']
                if ligne['chaine'] == 7][0]
        self.assertEqual(sept['modules'], 1)

    def test_une_affectation_manuelle_illisible_ne_fait_pas_tomber_la_table(
            self):
        resultat = affectation_du_calepinage(
            _conception(), {'affectation_manuelle': 'pas une liste'})

        self.assertTrue(resultat['affectation'])
        self.assertTrue(resultat['avertissements'])


class OmissionsTest(SimpleTestCase):
    """Rien n'est agrégé sur une partition ou une énergie absentes."""

    def test_sans_affectation_le_bloc_est_omis_avec_son_motif(self):
        bloc = agregation_production(_production(4, _affectation('PAN-A', 4)),
                                     ())

        self.assertEqual(bloc['par_chaine'], [])
        self.assertIn('affectation', bloc['motif'])

    def test_le_motif_vient_de_services_chaines(self):
        # Layout sans aucun module posé : c'est `services/chaines.py` qui dit
        # pourquoi, jamais ce module-ci.
        vide = concevoir_par_pan(
            {'version': 2, 'zones': []}, module_specs=MODULE,
            onduleur_specs=ONDULEUR,
            temperatures=temperatures_site(
                saisie={'temperature_min_c': -5.0,
                        'temperature_max_c': 70.0}))
        resultat = affectation_du_calepinage(vide)

        self.assertEqual(resultat['affectation'], ())
        self.assertIn('aucun module posé', resultat['motif'])

    def test_fiche_incomplete_nomme_ce_qui_manque(self):
        incomplete = concevoir_par_pan(
            LAYOUT, module_specs={}, onduleur_specs=ONDULEUR,
            temperatures=temperatures_site(
                saisie={'temperature_min_c': -5.0,
                        'temperature_max_c': 70.0}))
        resultat = affectation_du_calepinage(incomplete)

        self.assertEqual(resultat['affectation'], ())
        self.assertIn('fiche incomplète', resultat['motif'])

    def test_sans_par_module_le_bloc_est_omis(self):
        table = _affectation('PAN-A', 4)
        bloc = agregation_production({'par_module': [], 'total': {},
                                      'motif': 'aucun pan'}, table)

        self.assertEqual(bloc['par_chaine'], [])
        self.assertEqual(bloc['motif'], 'aucun pan')

    def test_un_module_affecte_sans_energie_est_nomme(self):
        table = _affectation('PAN-A', 4)
        table.append({'module': 'PAN-A#99', 'pan': 'PAN-A', 'chaine': 1,
                      'onduleur': 1, 'mppt': 1, 'source': 'automatique'})
        bloc = agregation_production(_production(4, table), table)

        self.assertTrue(any('PAN-A#99' in motif
                            for motif in bloc['omissions']))


class PertesDeLaChaineTest(SimpleTestCase):
    """Mismatch et écrêtage sont LUS, jamais forfaitisés."""

    def test_sans_cascade_les_deux_pertes_sont_omises_avec_leur_motif(self):
        table = _affectation('PAN-A', 10)
        bloc = agregation_production(_production(10, table), table)

        for ligne in bloc['par_chaine']:
            self.assertIsNone(ligne['perte_mismatch_pct'])
            self.assertIsNone(ligne['perte_ecretage_pct'])
            self.assertIn('cascade', ligne['motif_mismatch'])

    def test_les_pertes_sont_lues_dans_la_cascade_de_la_chaine(self):
        table = _affectation('PAN-A', 10)
        cascades = {1: [{'etape': ETAPE_MISMATCH, 'perte_pct': 1.8,
                         'motif_omission': ''},
                        {'etape': ETAPE_ECRETAGE, 'perte_pct': 0.4,
                         'motif_omission': ''}],
                    2: [{'etape': ETAPE_MISMATCH, 'perte_pct': 0.0,
                         'motif_omission': ''}]}
        bloc = agregation_production(_production(10, table), table,
                                     cascades=cascades)
        par_chaine = {ligne['chaine']: ligne for ligne in bloc['par_chaine']}

        self.assertEqual(par_chaine[1]['perte_mismatch_pct'], 1.8)
        self.assertEqual(par_chaine[1]['perte_ecretage_pct'], 0.4)
        # Une chaîne dont la cascade N'A PAS l'étape d'écrêtage ne se voit
        # pas attribuer 0 % : la clé est omise en nommant l'étape.
        self.assertEqual(par_chaine[2]['perte_mismatch_pct'], 0.0)
        self.assertIsNone(par_chaine[2]['perte_ecretage_pct'])
        self.assertIn(ETAPE_ECRETAGE, par_chaine[2]['motif_ecretage'])

    def test_une_etape_omise_ne_devient_pas_zero(self):
        table = _affectation('PAN-A', 5)
        cascades = {1: [{'etape': ETAPE_MISMATCH, 'perte_pct': None,
                         'motif_omission': 'aucune matrice d’ombrage saisie'}]}
        bloc = agregation_production(_production(5, table), table,
                                     cascades=cascades)

        self.assertIsNone(bloc['par_chaine'][0]['perte_mismatch_pct'])
        self.assertIn('matrice', bloc['par_chaine'][0]['motif_mismatch'])
